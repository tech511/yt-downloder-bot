"""Runs one job: for every chosen video, strictly one after another ->
download (best quality) -> convert to MP3 (audio jobs) -> upload -> delete that video's temp files.
When the job ends (finished, failed or stopped) the whole temp folder is removed.
"""
from __future__ import annotations

import asyncio
import logging

from pyrogram.errors import FloodWait
from yt_dlp.utils import DownloadCancelled

try:  # raising this inside an upload-progress callback aborts the upload
    from pyrogram import StopTransmission
except ImportError:  # pragma: no cover
    StopTransmission = None

import config
from keyboards.inline import stop_keyboard
from services import sessions
from services.sessions import Job
from utils import audio
from utils.files import new_job_dir, remove_dir, safe_filename
from utils.progress import Reporter
from utils.text import clean_error, esc, progress_text, short
from utils.ytdlp_utils import download_audio_mp3, download_video

log = logging.getLogger(__name__)

JOB_SEM = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)
TELEGRAM_LIMIT = 2000 * 1024 * 1024          # bots can upload up to ~2 GB


class JobStopped(Exception):
    pass


async def _acquire_slot(job: Job) -> bool:
    """Wait for a free slot, but give up immediately if the user presses Stop while queued."""
    while not job.cancel.is_set():
        try:
            await asyncio.wait_for(JOB_SEM.acquire(), timeout=1)
            return True
        except asyncio.TimeoutError:
            continue
    return False


async def _with_flood_retry(factory, tries: int = 3):
    for attempt in range(tries):
        try:
            return await factory()
        except FloodWait as exc:
            if attempt == tries - 1:
                raise
            log.warning("FloodWait %ss, retrying", exc.value)
            await asyncio.sleep(exc.value + 1)


async def _process_one(client, job: Job, reporter: Reporter, entry: dict, n: int, item_dir) -> None:
    head = f"{n}/{len(job.entries)}"
    title = entry["title"]
    is_audio = job.mode == "audio"

    def on_progress(done, size, speed, eta):          # runs in the yt-dlp thread
        reporter.post(progress_text("📥", "Downloading", head, title, done, size, speed, eta))

    def on_stage(stage):                              # runs in the yt-dlp thread
        if stage == "convert":
            reporter.post_force(progress_text("🎧", "Converting to MP3", head, title))

    await reporter.set(progress_text("📥", "Downloading", head, title), force=True)
    fetch = download_audio_mp3 if is_audio else download_video
    media = await asyncio.to_thread(fetch, entry["url"], item_dir,
                                    on_progress=on_progress, on_stage=on_stage, cancel=job.cancel)

    size = media.path.stat().st_size
    if size > TELEGRAM_LIMIT:
        raise ValueError("File is larger than Telegram's 2 GB upload limit.")
    if job.cancel.is_set():
        raise JobStopped()

    def on_upload(current, total):                    # runs in a Pyrogram worker thread
        if job.cancel.is_set() and StopTransmission:
            raise StopTransmission
        reporter.post(progress_text("⬆️", "Uploading", head, title, current, total))

    await reporter.set(progress_text("⬆️", "Uploading", head, title, 0, size), force=True)
    name = safe_filename(media.title, fallback=media.id)
    link = f"🔗 {esc(media.url)}"

    if is_audio:
        async def send():
            return await client.send_audio(
                chat_id=job.chat_id, audio=str(media.path), file_name=f"{name}.mp3",
                duration=int(media.duration or 0), caption=link, progress=on_upload)
    else:
        thumb = await asyncio.to_thread(audio.make_thumbnail, media.path, item_dir / "thumb.jpg", media.duration)

        async def send():
            return await client.send_video(
                chat_id=job.chat_id, video=str(media.path), file_name=f"{name}.mp4",
                duration=int(media.duration or 0), width=int(media.width or 0), height=int(media.height or 0),
                thumb=str(thumb) if thumb else None, supports_streaming=True,
                caption=f"{esc(short(media.title, 900))}\n{link}", progress=on_upload)

    result = await _with_flood_retry(send)
    if result is None and job.cancel.is_set():
        raise JobStopped()


async def _finish(status_msg, job: Job, sent: int, failed: list[tuple[str, str]], stopped: bool) -> None:
    total = len(job.entries)
    if stopped:
        head = f"⛔ <b>Stopped</b> - {sent} of {total} sent"
    elif failed:
        head = f"⚠️ <b>Finished</b> - {sent} of {total} sent"
    else:
        head = f"✅ <b>Done</b> - {sent} of {total} sent"

    if total == 1 and sent == 1 and not stopped:        # clean chat for the simple case
        try:
            await status_msg.delete()
            return
        except Exception:  # noqa: BLE001
            pass

    lines = [head]
    if failed:
        lines += ["", f"❌ <b>Failed ({len(failed)}):</b>"]
        for title, reason in failed[:10]:
            lines.append(f"• {esc(short(title, 60))} - <i>{esc(short(reason, 120))}</i>")
        if len(failed) > 10:
            lines.append(f"… and {len(failed) - 10} more")
    lines += ["", "🧹 Temporary files cleaned."]
    try:
        await status_msg.edit_text("\n".join(lines))     # no reply_markup -> Stop button disappears
    except Exception as exc:  # noqa: BLE001
        log.debug("final edit failed: %s", exc)


async def run_job(client, status_msg, job: Job) -> None:
    reporter = Reporter(status_msg, asyncio.get_running_loop(), markup=stop_keyboard(job.token))
    root = None
    sent = 0
    failed: list[tuple[str, str]] = []
    try:
        await reporter.set("⏳ Waiting for a free slot…" if JOB_SEM.locked() else "⏳ Starting…", force=True)
        if await _acquire_slot(job):
            try:
                root = new_job_dir()
                for n, entry in enumerate(job.entries, 1):
                    if job.cancel.is_set():
                        break
                    item_dir = root / f"{n:03d}"
                    item_dir.mkdir()
                    try:
                        await _process_one(client, job, reporter, entry, n, item_dir)
                        sent += 1
                    except (JobStopped, DownloadCancelled, audio.Cancelled):
                        break
                    except Exception as exc:  # noqa: BLE001 - one bad video must not stop the rest
                        if job.cancel.is_set():
                            break
                        log.warning("Item %s failed: %s", entry.get("id"), exc)
                        failed.append((entry["title"], clean_error(exc)))
                    finally:
                        remove_dir(item_dir)             # this video's files are gone before the next starts
            finally:
                JOB_SEM.release()
    except Exception:  # noqa: BLE001
        log.exception("Job crashed")
        failed.append(("Unexpected error", "see the bot log"))
    finally:
        remove_dir(root)
        sessions.ACTIVE_JOBS.pop(job.user_id, None)
    await _finish(status_msg, job, sent, failed, stopped=job.cancel.is_set())
