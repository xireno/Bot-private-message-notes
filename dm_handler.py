import os
import re
import aiohttp
import discord
from discord.ext import commands
from datetime import datetime

TARGET_USER_ID = 1234  # Replace with your target user ID
SAVE_PATH = r"path"  # Change to your desired save path

# Helper to sanitize filenames
def sanitize_filename(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name)[:64]

class DMHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.all_messages = []
        self.txt_filename = os.path.join(SAVE_PATH, 'messages.txt')
        self.html_filename = os.path.join(SAVE_PATH, 'messages.html')
        self._load_messages()

    def _load_messages(self):
        if os.path.exists(self.txt_filename):
            with open(self.txt_filename, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        ts_end = line.find(']')
                        ts = line[1:ts_end]
                        rest = line[ts_end+2:]
                        username, content = rest.split(': ', 1)
                        self.all_messages.append({
                            'timestamp': ts,
                            'username': username,
                            'content': content.strip(),
                            'attachments': [],
                            'avatar': None
                        })
                    except Exception:
                        continue

    def _replace_custom_emojis(self, text):
        # Replace static custom emojis
        text = re.sub(
            r'<:([a-zA-Z0-9_]+):(\d+)>',
            lambda m: f'<img src="https://cdn.discordapp.com/emojis/{m.group(2)}.png" alt=":{m.group(1)}:" style="height:1.5em;vertical-align:-0.4em;">',
            text)
        # Replace animated custom emojis
        text = re.sub(
            r'<a:([a-zA-Z0-9_]+):(\d+)>',
            lambda m: f'<img src="https://cdn.discordapp.com/emojis/{m.group(2)}.gif" alt=":{m.group(1)}:" style="height:1.5em;vertical-align:-0.4em;">',
            text)
        return text

    def _write_html(self):
        html_content = '''<html><head><meta charset="utf-8">
<style>
.discord-message { background: #313338; color: #dbdee1; font-family: 'gg sans', 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif; border-radius: 8px; padding: 16px; margin: 20px; width: 480px; }
.discord-header { display: flex; align-items: center; }
.discord-avatar { width: 40px; height: 40px; border-radius: 50%; margin-right: 12px; }
.discord-username { font-weight: 600; color: #fff; font-size: 16px; margin-right: 8px; }
.discord-timestamp { color: #949ba4; font-size: 12px; }
.discord-content { margin-left: 52px; margin-top: -8px; font-size: 15px; word-break: break-word; }
.discord-attachment { margin-left: 52px; margin-top: 8px; }
</style></head><body style="background:#232428;">
'''
        for msg in self.all_messages:
            content_html = self._replace_custom_emojis(msg['content'])
            html_content += f'''<div class="discord-message">
  <div class="discord-header">
    <img class="discord-avatar" src="{msg['avatar'] or ''}">
    <span class="discord-username">{msg['username']}</span>
    <span class="discord-timestamp">{msg['timestamp']}</span>
  </div>
  <div class="discord-content">{content_html}</div>
'''
            for att in msg.get('attachments', []):
                if att.get('is_image'):
                    html_content += f'<div class="discord-attachment"><img src="{att["filename"]}" style="max-width:320px; border-radius:8px;"></div>'
                else:
                    html_content += f'<div class="discord-attachment"><a href="{att["filename"]}">{att["orig_name"]}</a></div>'
            html_content += '</div>'
        html_content += "\n</body></html>"
        with open(self.html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Only handle DMs from the target user (not bots)
        if message.guild is None and message.author.id == TARGET_USER_ID and not message.author.bot:
            os.makedirs(SAVE_PATH, exist_ok=True)
            # Write to txt
            with open(self.txt_filename, 'a', encoding='utf-8') as txtf:
                txtf.write(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author.display_name}: {message.content}\n")
            # Download avatar
            avatar_url = message.author.display_avatar.url
            avatar_ext = os.path.splitext(avatar_url.split('?')[0])[1]
            avatar_filename = os.path.join(SAVE_PATH, f"{message.author.id}_avatar{avatar_ext}")
            if not os.path.exists(avatar_filename):
                async with aiohttp.ClientSession() as session:
                    async with session.get(avatar_url) as resp:
                        if resp.status == 200:
                            with open(avatar_filename, 'wb') as f:
                                f.write(await resp.read())
            msg_dict = {
                'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'username': message.author.display_name,
                'avatar': os.path.basename(avatar_filename),
                'content': message.content,
                'attachments': []
            }
            for i, attachment in enumerate(message.attachments):
                file_ext = os.path.splitext(attachment.filename)[1]
                att_filename = os.path.join(SAVE_PATH, f"{message.id}_att{i+1}{file_ext}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(att_filename, 'wb') as f:
                                f.write(await resp.read())
                is_image = file_ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']
                msg_dict['attachments'].append({
                    'filename': os.path.basename(att_filename),
                    'orig_name': attachment.filename,
                    'is_image': is_image
                })
            self.all_messages.append(msg_dict)
            self._write_html()
        # DO NOT call process_commands here! This prevents duplicate command execution.

async def setup(bot):
    await bot.add_cog(DMHandler(bot))
