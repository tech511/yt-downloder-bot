"""Entry point:  python bot.py"""
import atexit

from pyrogram import idle

import core
from core import app, log
from utils.files import clear_all_temp, ensure_temp_root

# Importing the handler modules registers them on the shared client.
from handlers import start, link, callbacks  # noqa: F401,E402


async def main() -> None:
    try:
        await app.start()
    except Exception as exc:  # noqa: BLE001
        log.error("Could not start the bot: %s", exc)
        log.error(
            "Check: 1) BOT_TOKEN / API_ID / API_HASH in .env  2) internet connection  "
            "3) phone date & time set to AUTOMATIC (a wrong clock is a very common cause)."
        )
        return
    me = await app.get_me()
    log.info("✅ Bot is online as @%s - send it a YouTube link", me.username)
    await idle()
    await app.stop()


if __name__ == "__main__":
    clear_all_temp()          # leftovers from a previous crash
    ensure_temp_root()
    atexit.register(clear_all_temp)
    try:
        core.LOOP.run_until_complete(main())
    except KeyboardInterrupt:
        pass
