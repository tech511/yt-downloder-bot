from pyrogram import filters
from pyrogram.types import Message

from bot import app


@app.on_message(filters.private & filters.command(["start", "help"]))
async def start_handler(client, message: Message):
    await message.reply_text(
        "👋 **Personal YouTube Downloader**\n\n"
        "Send me a YouTube video link. I'll show its available information and then offer **Video** and **Audio** buttons.\n\n"
        "• Audio keeps the best available source audio stream where possible.\n"
        "• Video downloads the best available video/audio combination.\n"
        "• Long videos and oversized files are limited to protect the host.\n\n"
        "Use only content you own or have permission to download. This bot does not bypass DRM or access restrictions."
    )
