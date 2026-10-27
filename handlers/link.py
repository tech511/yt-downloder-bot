"""Receives a YouTube link and shows either the video panel or the playlist picker."""
import asyncio
import logging
import re

from pyrogram import filters
from pyrogram.types import Message

from core import app
from services import sessions
from services.views import render_playlist, render_single
from utils import ytdlp_utils
from utils.auth import allowed
from utils.text import clean_error, esc

log = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://[^\s<>]+")


@app.on_message(filters.private & filters.text & allowed & ~filters.command(["start", "help"]))
async def link_handler(client, message: Message):
    match = URL_RE.search(message.text or "")
    target = ytdlp_utils.parse_youtube_url(match.group(0).rstrip(").,;!")) if match else None
    if not target:
        await message.reply_text(
            "Send a YouTube <b>video</b> or <b>playlist</b> link, e.g. <code>https://youtu.be/…</code>")
        return

    status = await message.reply_text("🔎 Reading playlist…" if target.kind == "playlist" else "🔎 Reading video…")
    user_id = message.from_user.id if message.from_user else 0
    try:
        if target.kind == "playlist":
            playlist = await asyncio.to_thread(ytdlp_utils.extract_playlist, target.url)
            panel = sessions.new_panel(user_id, "playlist", target.url,
                                       playlist=playlist, video_url=target.video_url)
            text, markup = render_playlist(panel)
        else:
            info = await asyncio.to_thread(ytdlp_utils.extract_single, target.url)
            panel = sessions.new_panel(user_id, "video", target.url, info=info)
            text, markup = render_single(panel)
        await status.edit_text(text, reply_markup=markup)
    except Exception as exc:  # noqa: BLE001
        log.exception("Reading link failed")
        await status.edit_text(f"❌ Couldn't read this link.\n<code>{esc(clean_error(exc))}</code>")
