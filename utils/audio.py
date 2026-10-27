"""FFmpeg helpers. Audio is converted to MP3 and NOTHING else is touched."""
from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

import config


class Cancelled(Exception):
    """Raised when the user pressed Stop while FFmpeg was running."""


class ConversionError(RuntimeError):
    pass


def check_ffmpeg() -> str | None:
    """Return a problem description, or None when FFmpeg is usable."""
    if not shutil.which("ffmpeg"):
        return "FFmpeg is not installed. In Termux run:  pkg install ffmpeg"
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return None
    if "libmp3lame" not in out:
        return "Your FFmpeg has no MP3 encoder (libmp3lame). In Termux run:  pkg reinstall ffmpeg"
    return None


def _quality_args() -> list[str]:
    q = config.MP3_QUALITY
    return ["-b:a", q] if q.endswith("k") else ["-q:a", q]


def to_mp3(src: Path, dst: Path, cancel: threading.Event | None = None) -> Path:
    """Re-encode the first audio stream of `src` to MP3.

    - no video, no cover art, no resampling, no channel change
    - `-map_metadata 0` copies whatever tags the source already had, unchanged
    - nothing is added (no title/artist/thumbnail/encoder tag is written by the bot)
    """
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vn", "-map", "0:a:0",
        "-map_metadata", "0",
        "-c:a", "libmp3lame", *_quality_args(),
        "-fflags", "+bitexact", "-flags:a", "+bitexact",   # don't stamp an "encoder=Lavf" tag
        "-id3v2_version", "3",
        str(dst),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    while True:
        try:
            _, err = proc.communicate(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if cancel is not None and cancel.is_set():
                proc.kill()
                proc.communicate()
                dst.unlink(missing_ok=True)
                raise Cancelled()
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        dst.unlink(missing_ok=True)
        raise ConversionError(f"FFmpeg failed: {(err or '').strip()[-300:] or 'unknown error'}")
    return dst


def make_thumbnail(video: Path, out: Path, duration: float | None = None) -> Path | None:
    """Small JPEG preview for Telegram (video uploads only). Never raises."""
    at = "1" if duration and duration > 4 else "0"
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", at, "-i", str(video), "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "5", str(out)]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001
        return None
    return out if result.returncode == 0 and out.exists() and out.stat().st_size > 0 else None
