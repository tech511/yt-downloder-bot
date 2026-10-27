"""Builds the (text, keyboard) pair for each panel and edits messages safely."""
from __future__ import annotations

import math

from pyrogram.errors import MessageNotModified

import config
from keyboards.inline import playlist_keyboard, single_choices
from services.sessions import Panel
from utils.text import format_playlist, format_single_info


def render_playlist(panel: Panel):
    entries = panel.playlist["entries"]
    pages = max(1, math.ceil(len(entries) / config.PAGE_SIZE))
    panel.page = min(max(panel.page, 0), pages - 1)
    text = format_playlist(panel.playlist, len(panel.selected), panel.page, pages)
    markup = playlist_keyboard(panel.token, entries, panel.selected, panel.page,
                               config.PAGE_SIZE, bool(panel.video_url))
    return text, markup


def render_single(panel: Panel):
    return format_single_info(panel.info), single_choices(panel.token)


async def safe_edit(message, text: str, markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass
