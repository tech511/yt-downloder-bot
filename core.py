"""Creates the ONE shared Pyrogram client that every handler imports.

WHY THIS FILE EXISTS (the "bot doesn't respond" bug):
The old project created `app` inside bot.py and the handlers did `from bot import app`.
When you start it with `python bot.py`, that file runs as "__main__", so the handlers
re-imported it as a *second* module and registered themselves on a *second* Client.
The Client that was actually running had zero handlers, so the bot connected to
Telegram but never answered anything. Keeping the client here fixes that.
"""
import asyncio
import logging
import shutil
import sys

# Python 3.12+ no longer creates an event loop automatically and Pyrogram 2.0.x expects one
# at import time -> create it BEFORE pyrogram is imported.
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)

from pyrogram import Client  # noqa: E402
from pyrogram.enums import ParseMode  # noqa: E402

import config  # noqa: E402
from utils import audio  # noqa: E402

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log = logging.getLogger("ytbot")


def _fail(message: str) -> None:
    print(f"\n❌ {message}\n", file=sys.stderr)
    sys.exit(1)


if not (config.BOT_TOKEN and config.API_ID and config.API_HASH):
    _fail("Set BOT_TOKEN, API_ID and API_HASH in the .env file (copy .env.example to .env).")

_ffmpeg_problem = audio.check_ffmpeg()
if _ffmpeg_problem:
    _fail(_ffmpeg_problem)

if not (shutil.which("node") or shutil.which("deno")):
    log.warning(
        "No JavaScript runtime found. YouTube may hide the best formats without one. "
        "In Termux run: pkg install nodejs"
    )
if not config.OWNER_ID:
    log.warning("OWNER_ID is not set - anyone who finds the bot can use it.")

app = Client(
    name="personal_youtube_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workdir=str(config.BASE_DIR),   # keep the .session file next to the code
    parse_mode=ParseMode.HTML,      # titles are HTML-escaped, so odd characters can't break messages
    workers=4,
    sleep_threshold=30,
)
