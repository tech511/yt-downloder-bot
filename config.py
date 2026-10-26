import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_ID_RAW = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()

try:
    API_ID = int(API_ID_RAW) if API_ID_RAW else 0
except ValueError:
    API_ID = 0

try:
    OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW else 0
except ValueError:
    OWNER_ID = 0

# Keep downloads below Telegram's practical upload limit and protect small hosts.
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "1800"))
MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", "7200"))
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
