"""Every inline-button press (see keyboards/inline.py for the callback_data map)."""
import asyncio
import logging

from pyrogram import filters
from pyrogram.types import CallbackQuery

import config
from core import app
from services import sessions
from services.runner import run_job
from services.sessions import Job
from services.views import render_playlist, render_single, safe_edit
from utils import ytdlp_utils
from utils.auth import allowed
from utils.text import clean_error

log = logging.getLogger(__name__)


async def _panel(query: CallbackQuery, token: str):
    panel = sessions.get_panel(token)
    if not panel:
        await query.answer("This panel expired. Send the link again.", show_alert=True)
        return None
    if panel.user_id != query.from_user.id:
        await query.answer("These buttons belong to the person who sent the link.", show_alert=True)
        return None
    return panel


async def _launch(client, query: CallbackQuery, panel, mode: str, entries: list[dict]) -> None:
    user_id = query.from_user.id
    if user_id in sessions.ACTIVE_JOBS:
        await query.answer("You already have a job running. Stop it or wait for it to finish.", show_alert=True)
        return
    job = Job(token=panel.token, user_id=user_id, chat_id=query.message.chat.id,
              mode="audio" if mode == "a" else "video", entries=entries)
    sessions.ACTIVE_JOBS[user_id] = job
    sessions.drop_panel(panel.token)
    await query.answer("Starting…")
    sessions.spawn(run_job(client, query.message, job))     # background task - the Stop button stays responsive


# ----------------------------------------------------------------------- single video
@app.on_callback_query(filters.regex(r"^dl:[avx]:[0-9a-f]{8}$") & allowed)
async def single_callback(client, query: CallbackQuery):
    _, action, token = query.data.split(":")
    panel = await _panel(query, token)
    if not panel:
        return
    if action == "x":
        sessions.drop_panel(token)
        await query.message.edit_text("Cancelled.")
        await query.answer()
        return
    info = panel.info or {}
    entry = {"id": info.get("id"), "url": panel.url, "duration": info.get("duration"),
             "title": info.get("title") or info.get("id") or "YouTube video"}
    await _launch(client, query, panel, action, [entry])


# ----------------------------------------------------------------------- playlist
@app.on_callback_query(filters.regex(r"^pl:[a-z]:[0-9a-f]{8}(?::\w+)?$") & allowed)
async def playlist_callback(client, query: CallbackQuery):
    parts = query.data.split(":")
    action, token = parts[1], parts[2]
    arg = parts[3] if len(parts) > 3 else ""
    panel = await _panel(query, token)
    if not panel:
        return
    if panel.kind != "playlist":
        await query.answer()
        return

    entries = panel.playlist["entries"]
    count = len(entries)

    if action == "x":
        sessions.drop_panel(token)
        await query.message.edit_text("Cancelled.")
        await query.answer()
        return
    if action == "i":
        await query.answer()
        return

    if action == "d":
        if not panel.selected:
            await query.answer("Select at least one video first.", show_alert=True)
            return
        chosen = [entries[i] for i in sorted(panel.selected) if i < count]
        await _launch(client, query, panel, arg, chosen)
        return

    if action == "o":                                    # switch to the single linked video
        await query.answer("Reading video…")
        try:
            info = await asyncio.to_thread(ytdlp_utils.extract_single, panel.video_url)
        except Exception as exc:  # noqa: BLE001
            log.exception("Linked video failed")
            await query.answer(clean_error(exc)[:180], show_alert=True)
            return
        panel.kind, panel.info, panel.url = "video", info, panel.video_url
        text, markup = render_single(panel)
        await safe_edit(query.message, text, markup)
        return

    page_size = config.PAGE_SIZE
    if action == "t" and arg.isdigit() and int(arg) < count:
        panel.selected ^= {int(arg)}
    elif action == "p" and arg.isdigit():
        panel.page = int(arg)
    elif action == "a":
        panel.selected = set(range(count))
    elif action == "n":
        panel.selected.clear()
    elif action == "s":
        page_ids = set(range(panel.page * page_size, min((panel.page + 1) * page_size, count)))
        if page_ids <= panel.selected:
            panel.selected -= page_ids
        else:
            panel.selected |= page_ids

    await query.answer()
    text, markup = render_playlist(panel)
    await safe_edit(query.message, text, markup)


# ----------------------------------------------------------------------- stop a running job
@app.on_callback_query(filters.regex(r"^jb:s:[0-9a-f]{8}$") & allowed)
async def stop_callback(client, query: CallbackQuery):
    token = query.data.split(":")[2]
    job = sessions.ACTIVE_JOBS.get(query.from_user.id)
    if not job or job.token != token:
        await query.answer("This job already finished.", show_alert=True)
        return
    job.cancel.set()
    await query.answer("⛔ Stopping…")
