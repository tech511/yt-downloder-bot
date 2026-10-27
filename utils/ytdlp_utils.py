"""Everything that talks to yt-dlp. All functions here are BLOCKING - call them with asyncio.to_thread()."""
from __future__ import annotations

import logging
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import DownloadCancelled

import config
from utils import audio

log = logging.getLogger(__name__)

YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtu.be", "www.youtu.be",
}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_LIST_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MIX_PREFIXES = ("RD", "UL")        # auto-generated "mixes" - endless, so treated as a single video
_UNAVAILABLE = {"[private video]", "[deleted video]"}

# Highest resolution first; at the same resolution prefer H.264 + AAC (plays everywhere in Telegram).
# AV1 is skipped because many phones cannot play it.
VIDEO_FORMAT = "bv*[vcodec!^=av01]+ba/bv*+ba/b"
VIDEO_SORT = ["res", "vcodec:h264", "acodec:aac"]
# Audio: the best audio stream YouTube offers for that video.
AUDIO_FORMAT = "bestaudio/best"

ProgressFn = Callable[[float, float, float | None, float | None], None]


@dataclass
class Target:
    kind: str                      # "video" | "playlist"
    url: str                       # clean URL to hand to yt-dlp
    video_url: str | None = None   # set when a playlist link also points at one specific video


@dataclass
class MediaFile:
    path: Path
    id: str
    title: str
    url: str
    duration: float | None = None
    width: int | None = None
    height: int | None = None


# --------------------------------------------------------------------------- URLs
def parse_youtube_url(text: str) -> Target | None:
    try:
        parsed = urlparse((text or "").strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in YOUTUBE_HOSTS:
        return None

    query = parse_qs(parsed.query)
    path = parsed.path.rstrip("/")
    list_id = (query.get("list") or [""])[0]

    video_id = ""
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = path.lstrip("/").split("/")[0]
    elif path == "/watch":
        video_id = (query.get("v") or [""])[0]
    else:
        match = re.match(r"^/(?:shorts|live|embed|v)/([^/?#]+)", path)
        if match:
            video_id = match.group(1)
    if not _ID_RE.match(video_id):
        video_id = ""
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None

    if list_id and _LIST_RE.match(list_id) and not (list_id.startswith(_MIX_PREFIXES) and video_id):
        return Target("playlist", f"https://www.youtube.com/playlist?list={list_id}", video_url)
    if video_url:
        return Target("video", video_url)
    return None


# --------------------------------------------------------------------------- options
def _js_runtime_opts() -> dict[str, Any]:
    """yt-dlp only enables `deno` by default; Termux has `node`, so switch it on when needed."""
    mode = config.JS_RUNTIME
    if mode == "none":
        return {}
    if mode in {"node", "deno"}:
        return {"js_runtimes": {mode: {}}}
    if shutil.which("deno"):
        return {}
    if shutil.which("node"):
        return {"js_runtimes": {"node": {}}}
    return {}


def _common_opts() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "restrictfilenames": True,
        "overwrites": True,
    }
    if config.COOKIES_FILE and Path(config.COOKIES_FILE).is_file():
        opts["cookiefile"] = config.COOKIES_FILE
    opts.update(_js_runtime_opts())
    return opts


def _duration_filter(info: dict[str, Any], *, incomplete: bool = False) -> str | None:
    if info.get("is_live"):
        return "Live streams are not supported"
    duration = info.get("duration")
    if duration and duration > config.MAX_DURATION_SECONDS:
        return f"Video is longer than the {config.MAX_DURATION_SECONDS // 60}-minute limit"
    return None


# --------------------------------------------------------------------------- reading info
def extract_single(url: str) -> dict[str, Any]:
    opts = _common_opts()
    opts.update({"skip_download": True, "ignore_no_formats_error": True})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Could not read video information.")
    reason = _duration_filter(info)
    if reason:
        raise ValueError(reason)
    return info


def extract_playlist(url: str) -> dict[str, Any]:
    opts = _common_opts()
    opts.update({
        "noplaylist": False,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "playlistend": config.MAX_PLAYLIST_ITEMS,
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Could not read the playlist.")

    entries: list[dict[str, Any]] = []
    for entry in info.get("entries") or []:
        if not entry:
            continue
        vid = entry.get("id") or ""
        title = entry.get("title") or vid
        if not _ID_RE.match(vid) or title.lower() in _UNAVAILABLE:
            continue
        entries.append({
            "id": vid,
            "title": title,
            "duration": entry.get("duration"),
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    if not entries:
        raise ValueError("No downloadable videos found (empty or private playlist?).")
    return {
        "title": info.get("title") or "Playlist",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "entries": entries,
        "total": info.get("playlist_count") or len(entries),
    }


# --------------------------------------------------------------------------- downloading
def _make_hook(cancel: threading.Event | None, on_progress: ProgressFn | None):
    def hook(d: dict[str, Any]) -> None:
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled("Stopped by user")
        if on_progress and d.get("status") == "downloading":
            on_progress(
                d.get("downloaded_bytes") or 0,
                d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
                d.get("speed"),
                d.get("eta"),
            )
    return hook


def _find_output(info: dict[str, Any], out_dir: Path) -> Path | None:
    for item in info.get("requested_downloads") or []:
        path = item.get("filepath")
        if path and Path(path).is_file() and Path(path).stat().st_size > 0:
            return Path(path)
    vid = info.get("id") or ""
    skip = {".part", ".ytdl", ".temp", ".json", ".jpg", ".webp", ".png", ".vtt", ".srt"}
    candidates = [p for p in out_dir.glob(f"{vid}*")
                  if p.is_file() and p.suffix.lower() not in skip and p.stat().st_size > 0]
    return max(candidates, key=lambda p: p.stat().st_size) if candidates else None


def _download(url: str, out_dir: Path, fmt: str, extra: dict[str, Any],
              on_progress: ProgressFn | None, cancel: threading.Event | None) -> tuple[dict[str, Any], Path]:
    if cancel is not None and cancel.is_set():
        raise DownloadCancelled("Stopped by user")
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = _common_opts()
    opts.update({
        "format": fmt,
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "max_filesize": config.MAX_FILE_SIZE_MB * 1024 * 1024,
        "match_filter": _duration_filter,
        "progress_hooks": [_make_hook(cancel, on_progress)],
        # No postprocessors on purpose: yt-dlp must not rewrite tags or embed anything.
    })
    opts.update(extra)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    path = _find_output(info, out_dir) if info else None
    if path is None:
        reason = _duration_filter(info or {})
        if reason:
            raise ValueError(reason)
        raise RuntimeError(
            f"Nothing was downloaded (the file may be bigger than the {config.MAX_FILE_SIZE_MB} MB limit)."
        )
    return info, path


def download_audio_mp3(url: str, out_dir: Path, *, on_progress: ProgressFn | None = None,
                       on_stage: Callable[[str], None] | None = None,
                       cancel: threading.Event | None = None) -> MediaFile:
    """Best audio stream -> MP3. Only the container/codec changes; tags are left exactly as they were."""
    info, source = _download(url, out_dir, AUDIO_FORMAT, {}, on_progress, cancel)
    if source.suffix.lower() == ".mp3":
        final = source
    else:
        if on_stage:
            on_stage("convert")
        final = audio.to_mp3(source, out_dir / f"{info['id']}.mp3", cancel)
        source.unlink(missing_ok=True)       # free the space right away
    return MediaFile(final, info["id"], info.get("title") or info["id"], url, info.get("duration"))


def download_video(url: str, out_dir: Path, *, on_progress: ProgressFn | None = None,
                   on_stage: Callable[[str], None] | None = None,
                   cancel: threading.Event | None = None) -> MediaFile:
    """Highest quality video + audio merged into MP4."""
    extra = {"format_sort": VIDEO_SORT, "merge_output_format": "mp4"}
    info, path = _download(url, out_dir, VIDEO_FORMAT, extra, on_progress, cancel)
    return MediaFile(path, info["id"], info.get("title") or info["id"], url,
                     info.get("duration"), info.get("width"), info.get("height"))
