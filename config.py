"""Central configuration. Everything comes from the .env file (see .env.example)."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Always read the .env that sits next to this file, whatever folder you start the bot from.
load_dotenv(BASE_DIR / ".env")


def _text(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        value = int(_text(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


# ---- Telegram ---------------------------------------------------------------
BOT_TOKEN = _text("BOT_TOKEN")
API_HASH = _text("API_HASH")
API_ID = _int("API_ID", 0)
OWNER_ID = _int("OWNER_ID", 0)  # 0 = everyone may use the bot

# ---- Limits -----------------------------------------------------------------
MAX_FILE_SIZE_MB = _int("MAX_FILE_SIZE_MB", 1800, 1)
MAX_DURATION_SECONDS = _int("MAX_DURATION_SECONDS", 7200, 1)
MAX_PLAYLIST_ITEMS = _int("MAX_PLAYLIST_ITEMS", 200, 1)
MAX_CONCURRENT_JOBS = _int("MAX_CONCURRENT_JOBS", 1, 1)

# ---- UI ---------------------------------------------------------------------
PAGE_SIZE = 8                 # playlist videos shown per page
PROGRESS_INTERVAL = 3.0       # seconds between progress-message edits (flood-safe)

# ---- Audio ------------------------------------------------------------------
MP3_QUALITY = _text("MP3_QUALITY", "0")
if not re.fullmatch(r"[0-9]|(?:64|96|128|160|192|224|256|320)k", MP3_QUALITY):
    MP3_QUALITY = "0"

# ---- yt-dlp -----------------------------------------------------------------
_cookies = _text("COOKIES_FILE")
COOKIES_FILE = str(Path(_cookies).expanduser()) if _cookies else ""
JS_RUNTIME = _text("JS_RUNTIME", "auto").lower()

# ---- Paths ------------------------------------------------------------------
_dl = Path(_text("DOWNLOAD_DIR", "downloads")).expanduser()
DOWNLOAD_DIR = _dl if _dl.is_absolute() else BASE_DIR / _dl
TEMP_ROOT = DOWNLOAD_DIR / "tmp"     # every job gets a private sub-folder in here

LOG_LEVEL = _text("LOG_LEVEL", "INFO").upper()
