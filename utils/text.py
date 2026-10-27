"""Small text helpers. Everything user/YouTube-supplied is HTML-escaped before it reaches Telegram."""
from __future__ import annotations

import html
import re
from typing import Any

esc = html.escape
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def short(text: Any, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def fmt_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "Unknown"
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def human_size(num: float | int | None) -> str:
    value = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def bar(percent: float, width: int = 12) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = round(width * percent / 100)
    return "█" * filled + "░" * (width - filled)


def progress_text(icon: str, label: str, head: str, title: str,
                  done: float = 0, total: float = 0,
                  speed: float | None = None, eta: float | None = None) -> str:
    lines = [f"{icon} <b>{label}</b> · {esc(head)}", f"<i>{esc(short(title, 80))}</i>"]
    if total:
        pct = done / total * 100
        lines.append(f"<code>{bar(pct)} {pct:5.1f}%</code>")
        detail = f"{human_size(done)} / {human_size(total)}"
    elif done:
        detail = human_size(done)
    else:
        detail = ""
    if speed:
        detail += f" · {human_size(speed)}/s"
    if eta is not None:
        detail += f" · ETA {fmt_duration(eta)}"
    if detail:
        lines.append(detail.strip(" ·"))
    return "\n".join(lines)


def format_single_info(info: dict[str, Any]) -> str:
    title = info.get("title") or "Unknown title"
    artist = info.get("artist") or info.get("creator") or info.get("uploader") or info.get("channel") or "Unknown"
    channel = info.get("uploader") or info.get("channel") or "Unknown"
    upload_date = info.get("upload_date") or "Unknown"
    if len(upload_date) == 8 and upload_date.isdigit():
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    description = short(info.get("description") or "No description", 400)
    views, likes = info.get("view_count"), info.get("like_count")
    lines = [
        f"<b>{esc(short(title, 180))}</b>",
        f"👤 <b>Artist / Creator:</b> {esc(short(artist, 150))}",
        f"📺 <b>Channel:</b> {esc(short(channel, 150))}",
        f"⏱ <b>Duration:</b> {fmt_duration(info.get('duration'))}",
        f"📅 <b>Uploaded:</b> {esc(upload_date)}",
        f"👁 <b>Views:</b> {views if views is not None else 'Unknown'}   👍 <b>Likes:</b> {likes if likes is not None else 'Unknown'}",
        f"🆔 <b>ID:</b> <code>{esc(str(info.get('id') or 'Unknown'))}</code>",
        "",
        f"<b>Description:</b>\n{esc(description)}",
    ]
    return "\n".join(lines)


def format_playlist(playlist: dict[str, Any], selected: int, page: int, pages: int) -> str:
    entries = playlist["entries"]
    shown, total = len(entries), playlist.get("total") or len(entries)
    lines = [f"📃 <b>{esc(short(playlist['title'], 150))}</b>"]
    if playlist.get("uploader"):
        lines.append(f"👤 {esc(short(playlist['uploader'], 100))}")
    count = f"🎞 {shown} videos"
    if total > shown:
        count += f" (first {shown} of {total})"
    seconds = sum(e.get("duration") or 0 for e in entries)
    if seconds:
        count += f" · ⏱ {fmt_duration(seconds)}"
    lines += [
        count,
        "",
        "Tap videos to select them, then choose <b>MP3</b> or <b>Video</b>.",
        f"✅ Selected: <b>{selected}</b> / {shown}   ·   Page {page + 1}/{pages}",
    ]
    return "\n".join(lines)


def clean_error(exc: BaseException, limit: int = 220) -> str:
    """Readable one-liner from a yt-dlp / ffmpeg / Telegram exception."""
    msg = _ANSI.sub("", str(exc)).strip()
    msg = re.sub(r"^ERROR:\s*", "", msg)
    msg = re.sub(r"^\[youtube\]\s*[\w-]{11}:\s*", "", msg)
    low = msg.lower()
    hint = ""
    if "sign in to confirm" in low or "not a bot" in low:
        hint = " (YouTube wants a login - see COOKIES_FILE in the README)"
    elif "ffmpeg" in low and ("not found" in low or "no such file" in low):
        hint = " (install FFmpeg: pkg install ffmpeg)"
    elif "requested format is not available" in low or "only images are available" in low:
        hint = " (install nodejs and update: pip install -U yt-dlp yt-dlp-ejs)"
    return (short(msg, limit) or exc.__class__.__name__) + hint
