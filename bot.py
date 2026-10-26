import logging
from pyrogram import Client

from config import BOT_TOKEN, API_ID, API_HASH, LOG_LEVEL

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

if not BOT_TOKEN or not API_ID or not API_HASH:
    raise RuntimeError("Set BOT_TOKEN, API_ID, and API_HASH in your .env file before starting the bot.")

app = Client(
    name="personal_youtube_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8,
    sleep_threshold=30,
)

# Import handlers after app creation so decorators can register them.
from handlers import start, download  # noqa: E402,F401


if __name__ == "__main__":
    logging.getLogger(__name__).info("Personal YouTube bot is starting")
    app.run()
