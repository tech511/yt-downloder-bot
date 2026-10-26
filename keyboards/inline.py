from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def download_choices(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Video", callback_data=f"dl:v:{token}"),
            InlineKeyboardButton("🎵 Audio", callback_data=f"dl:a:{token}"),
        ],
        [InlineKeyboardButton("✖️ Cancel", callback_data=f"dl:x:{token}")],
    ])
