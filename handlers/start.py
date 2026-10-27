from pyrogram import filters
from pyrogram.types import Message

from core import app
from utils.auth import allowed

WELCOME = (
    "👋 <b>Personal YouTube Downloader</b>\n\n"
    "Send me a YouTube link:\n"
    "• <b>Video link</b> → choose 🎵 <b>MP3</b> or 🎬 <b>Video</b>\n"
    "• <b>Playlist link</b> → tick the videos you want (or all). I download them "
    "<b>one by one</b>, convert each to MP3 and upload it, deleting the temp files as I go.\n\n"
    "<b>How it works</b>\n"
    "• Best quality YouTube offers for that video\n"
    "• MP3 conversion changes only the audio format - nothing else is edited or added\n"
    "• ⛔ Stop button on every running job\n\n"
    "Use only content you own or have permission to download."
)


@app.on_message(filters.private & ~allowed, group=-1)
async def deny_message(client, message: Message):
    await message.reply_text("🔒 This is a private bot.")
    message.stop_propagation()


@app.on_callback_query(~allowed, group=-1)
async def deny_callback(client, query):
    await query.answer("🔒 This is a private bot.", show_alert=True)
    query.stop_propagation()


@app.on_message(filters.private & allowed & filters.command(["start", "help"]))
async def start_handler(client, message: Message):
    await message.reply_text(WELCOME)
