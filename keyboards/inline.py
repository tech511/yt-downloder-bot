"""All inline keyboards.

callback_data map (max 64 bytes each):
  dl:a|v|x:<token>            single video  -> MP3 / Video / Cancel
  pl:t:<token>:<index>        playlist      -> toggle one video
  pl:p:<token>:<page>         playlist      -> go to page
  pl:a|s|n:<token>            playlist      -> select all / select this page / clear
  pl:d:<token>:a|v            playlist      -> download selection as MP3 / Video
  pl:o:<token>                playlist      -> only the video the link pointed at
  pl:x:<token> | pl:i:<token> playlist      -> cancel / (page label, does nothing)
  jb:s:<token>                running job   -> Stop
"""
from __future__ import annotations

from pyrogram.types import InlineKeyboardButton as Btn
from pyrogram.types import InlineKeyboardMarkup as Markup

from utils.text import short


def single_choices(token: str) -> Markup:
    return Markup([
        [Btn("🎵 MP3 audio", callback_data=f"dl:a:{token}"),
         Btn("🎬 Video", callback_data=f"dl:v:{token}")],
        [Btn("✖️ Cancel", callback_data=f"dl:x:{token}")],
    ])


def stop_keyboard(token: str) -> Markup:
    return Markup([[Btn("⛔ Stop", callback_data=f"jb:s:{token}")]])


def playlist_keyboard(token: str, entries: list[dict], selected: set[int], page: int,
                      page_size: int, has_linked_video: bool) -> Markup:
    pages = max(1, -(-len(entries) // page_size))
    page = min(max(page, 0), pages - 1)
    first = page * page_size

    rows = []
    for idx in range(first, min(first + page_size, len(entries))):
        mark = "✅" if idx in selected else "⬜"
        rows.append([Btn(f"{mark} {idx + 1}. {short(entries[idx]['title'], 42)}",
                         callback_data=f"pl:t:{token}:{idx}")])

    if pages > 1:
        rows.append([
            Btn("⬅️", callback_data=f"pl:p:{token}:{max(page - 1, 0)}"),
            Btn(f"{page + 1}/{pages}", callback_data=f"pl:i:{token}"),
            Btn("➡️", callback_data=f"pl:p:{token}:{min(page + 1, pages - 1)}"),
        ])
    rows.append([
        Btn("☑️ All", callback_data=f"pl:a:{token}"),
        Btn("📄 Page", callback_data=f"pl:s:{token}"),
        Btn("🧹 None", callback_data=f"pl:n:{token}"),
    ])
    rows.append([
        Btn(f"🎵 MP3 ({len(selected)})", callback_data=f"pl:d:{token}:a"),
        Btn(f"🎬 Video ({len(selected)})", callback_data=f"pl:d:{token}:v"),
    ])
    if has_linked_video:
        rows.append([Btn("▶️ Only the linked video", callback_data=f"pl:o:{token}")])
    rows.append([Btn("✖️ Cancel", callback_data=f"pl:x:{token}")])
    return Markup(rows)
