import os
import re
import glob
import logging
from pathlib import Path
from typing import Any

import yt_dlp

from config import MAX_FILE_SIZE_MB, MAX_DURATION_SECONDS

log = logging.getLogger(__name__)

YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtu.be", "www.youtu.be",
}


def is_youtube_url(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in YOUTUBE_HOSTS
    except ValueError:
        return False


def readable_duration(seconds: int | None) -> str:
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_metadata(info: dict[str, Any]) -> str:
    title = info.get("title") or "Unknown title"
    artist = info.get("artist") or info.get("creator") or info.get("uploader") or info.get("channel") or "Unknown"
    upload_date = info.get("upload_date") or "Unknown"
    if len(upload_date) == 8 and upload_date.isdigit():
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    description = (info.get("description") or "No description")
    if len(description) > 700:
        description = description[:697] + "..."
    views = info.get("view_count")
    likes = info.get("like_count")
    lines = [
        f"**{title[:180]}**",
        f"👤 **Artist / Creator:** {str(artist)[:150]}",
        f"📺 **Channel / Uploader:** {str(info.get('uploader') or info.get('channel') or 'Unknown')[:150]}",
        f"⏱ **Duration:** {readable_duration(info.get('duration'))}",
        f"📅 **Upload date:** {upload_date}",
        f"👁 **Views:** {views if views is not None else 'Unknown'}",
        f"👍 **Likes:** {likes if likes is not None else 'Unknown'}",
        f"🆔 **Video ID:** {info.get('id') or 'Unknown'}",
        f"🔗 **URL:** {info.get('webpage_url') or info.get('original_url') or ''}",
        "",
        f"**Description / Caption:**\n{description}",
    ]
    return "\n".join(lines)


def _base_options(output_dir: str) -> dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "file_access_retries": 2,
        "overwrites": True,
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
        "match_filter": lambda info, *, incomplete=False: (
            "Video duration exceeds configured limit"
            if info.get("duration") and info["duration"] > MAX_DURATION_SECONDS
            else None
        ),
    }


def extract_info(url: str) -> dict[str, Any]:
    if not is_youtube_url(url):
        raise ValueError("Please send a valid YouTube video link.")
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 2,
        "extract_flat": False,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Could not read video information.")
    if info.get("duration") and info["duration"] > MAX_DURATION_SECONDS:
        raise ValueError(f"This video is longer than the {MAX_DURATION_SECONDS // 60}-minute limit.")
    return info


def download_media(url: str, output_dir: str, mode: str) -> tuple[str, dict[str, Any]]:
    if not is_youtube_url(url):
        raise ValueError("Please send a valid YouTube video link.")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    options = _base_options(output_dir)
    options["format"] = "bestvideo*+bestaudio/best" if mode == "video" else "bestaudio[ext=m4a]/bestaudio"
    options["postprocessors"] = [{"key": "FFmpegMetadata", "add_metadata": True}]
    if mode == "video":
        options["merge_output_format"] = "mp4"
    # Keep the original best audio stream; do not transcode it to a lower-quality format.
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
    if not info:
        raise RuntimeError("Download did not return video information.")

    candidates = []
    for path in glob.glob(os.path.join(output_dir, "*")):
        if not os.path.isfile(path):
            continue
        if path.endswith((".part", ".ytdl", ".json", ".description", ".jpg", ".webp", ".png")):
            continue
        if os.path.getsize(path) > 0:
            candidates.append(path)
    if not candidates:
        raise RuntimeError("Downloaded file was not found. Check that FFmpeg is installed for merging/metadata.")
    candidates.sort(key=os.path.getmtime, reverse=True)
    filepath = candidates[0]
    if os.path.getsize(filepath) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"File exceeds the configured {MAX_FILE_SIZE_MB} MB limit.")
    return filepath, info
