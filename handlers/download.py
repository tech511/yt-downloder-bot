import asyncio
import logging
import os
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from pyrogram import filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import FloodWait

from bot import app
from config import OWNER_ID, MAX_FILE_SIZE_MB
from keyboards.inline import download_choices
from utils.ytdlp_utils import extract_info, format_metadata, is_youtube_url, download_media

log = logging.getLogger(__name__)
CACHE: dict[str, dict] = {}
USER_LOCKS: dict[int, asyncio.Lock] = {}
CACHE_TTL = 30 * 60


def cleanup_cache():
    now = time.time()
    for key in list(CACHE):
        if now - CACHE[key]["created"] > CACHE_TTL:
            CACHE.pop(key, None)


@app.on_message(filters.private & filters.text & ~filters.command(["start", "help"]))
async def link_handler(client, message: Message):
    url = (message.text or "").strip()
    if not is_youtube_url(url):
        await message.reply_text("Send a valid YouTube video URL, for example: `https://youtu.be/...`")
        return

    status = await message.reply_text("🔎 Reading video information...")
    try:
        info = await asyncio.to_thread(extract_info, url)
        cleanup_cache()
        token = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
        CACHE[token] = {
            "url": info.get("webpage_url") or url,
            "info": info,
            "user_id": message.from_user.id if message.from_user else 0,
            "created": time.time(),
        }
        await status.edit_text(format_metadata(info), reply_markup=download_choices(token), disable_web_page_preview=True)
    except Exception as exc:
        log.exception("Metadata extraction failed")
        text = str(exc)
        if len(text) > 350:
            text = text[:347] + "..."
        await status.edit_text(f"❌ Couldn't read this video.\n`{text}`")


@app.on_callback_query(filters.regex(r"^dl:[avx]:[A-Za-z0-9]{4,12}$"))
async def download_callback(client, query: CallbackQuery):
    parts = query.data.split(":")
    mode, token = parts[1], parts[2]
    entry = CACHE.get(token)
    if not entry or time.time() - entry["created"] > CACHE_TTL:
        CACHE.pop(token, None)
        await query.answer("This button expired. Send the link again.", show_alert=True)
        return
    if not query.from_user or query.from_user.id != entry["user_id"]:
        await query.answer("These buttons belong to the person who sent the link.", show_alert=True)
        return
    if mode == "x":
        CACHE.pop(token, None)
        await query.message.edit_text("Cancelled.")
        await query.answer()
        return

    user_id = query.from_user.id
    lock = USER_LOCKS.setdefault(user_id, asyncio.Lock())
    if lock.locked():
        await query.answer("You already have a download running. Please wait.", show_alert=True)
        return

    await query.answer("Starting download...")
    kind = "video" if mode == "v" else "audio"
    status = await query.message.reply_text(f"⏬ Downloading **{kind}**... Please wait.")
    temp_dir = tempfile.mkdtemp(prefix="ytbot_")
    try:
        async with lock:
            filepath, info = await asyncio.to_thread(download_media, entry["url"], temp_dir, kind)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            caption = f"{(info.get('title') or 'YouTube media')[:900]}\nSource: {entry['url']}"
            await status.edit_text(f"⬆️ Uploading {kind} ({size_mb:.1f} MB)...")
            if kind == "video":
                await client.send_video(
                    chat_id=query.message.chat.id,
                    video=filepath,
                    caption=caption[:1024],
                    supports_streaming=True,
                )
            else:
                ext = Path(filepath).suffix.lower()
                if ext in {".m4a", ".mp3"}:
                    await client.send_audio(
                        chat_id=query.message.chat.id,
                        audio=filepath,
                        title=(info.get("track") or info.get("title") or "Audio")[:64],
                        performer=(info.get("artist") or info.get("creator") or info.get("uploader") or "Unknown")[:64],
                        caption=caption[:1024],
                        file_name=Path(filepath).name,
                    )
                else:
                    # Preserve the original codec/quality rather than converting it to a lossy MP3.
                    await client.send_document(
                        chat_id=query.message.chat.id,
                        document=filepath,
                        caption=(caption + "\nOriginal audio format preserved.")[:1024],
                        file_name=Path(filepath).name,
                    )
            await status.delete()
    except FloodWait as exc:
        await status.edit_text(f"Telegram rate limit. Please try again in {exc.value} seconds.")
    except Exception as exc:
        log.exception("Download/upload failed")
        err = str(exc)
        if len(err) > 350:
            err = err[:347] + "..."
        await status.edit_text(f"❌ Download failed. Check the link, FFmpeg installation, available disk space, and file size limit.\n`{err}`")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
