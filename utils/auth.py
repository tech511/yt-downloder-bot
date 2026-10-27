"""Access control: if OWNER_ID is set, only that user may use the bot."""
from pyrogram import filters

import config


async def _check(_, __, update) -> bool:
    if not config.OWNER_ID:
        return True
    user = getattr(update, "from_user", None)
    return bool(user and user.id == config.OWNER_ID)


allowed = filters.create(_check, name="AllowedUser")
