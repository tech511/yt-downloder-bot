"""Temp-folder handling and safe file names."""
from __future__ import annotations

import re
import shutil
import tempfile
import unicodedata
from pathlib import Path

import config

_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def ensure_temp_root() -> None:
    config.TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def new_job_dir() -> Path:
    """A private, empty folder for one job."""
    ensure_temp_root()
    return Path(tempfile.mkdtemp(prefix="job_", dir=config.TEMP_ROOT))


def remove_dir(path: Path | str | None) -> None:
    if path:
        shutil.rmtree(path, ignore_errors=True)


def clear_all_temp() -> None:
    """Delete every temp file (called at start-up and on exit)."""
    remove_dir(config.TEMP_ROOT)


def safe_filename(name: str | None, fallback: str = "audio", max_len: int = 100) -> str:
    name = unicodedata.normalize("NFC", name or "")
    name = _ILLEGAL.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name[:max_len].strip(" .") or fallback)
