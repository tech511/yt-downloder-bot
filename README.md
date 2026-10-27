# Personal YouTube Downloader Bot (Pyrogram + yt-dlp)

Send a YouTube **video** or **playlist** link to your bot.

- **Video link** → buttons: 🎵 MP3 / 🎬 Video
- **Playlist link** → pick videos (✅ toggles, ☑️ All, 📄 Page, 🧹 None, paging) → press **MP3** or **Video**.
  The bot works through your selection **one by one**: download → convert to MP3 → upload → delete that video's temp files → next one.
- Live progress bar, **⛔ Stop** button, a failed video never stops the rest, and a summary at the end.
- Best quality available (best audio stream for MP3; highest resolution for Video, MP4 merged).
- MP3 conversion changes **only the audio format**: no tags, cover art or title are added/edited, same sample rate and channels, FFmpeg's own "encoder" tag is suppressed. Tags the source already had are carried over unchanged.

## Termux setup

```bash
pkg update && pkg upgrade -y
pkg install -y python ffmpeg nodejs unzip
# optional, faster uploads (needs a compiler):  pkg install -y clang && pip install TgCrypto

termux-setup-storage                       # once, to read your Downloads folder
cd ~ && unzip ~/storage/downloads/youtube_personal_bot.zip && cd youtube_personal_bot

pip install -r requirements.txt
cp .env.example .env && nano .env          # BOT_TOKEN, API_ID, API_HASH, OWNER_ID
python bot.py
```

You should see `✅ Bot is online as @yourbot`. Keep Termux alive with `termux-wake-lock` (or the notification's *Acquire wakelock*).

`nodejs` matters: current yt-dlp needs a JavaScript runtime to see YouTube's best formats. Termux has `node`; the bot enables it automatically.

Update when YouTube changes something (always update both together):

```bash
pip install -U yt-dlp yt-dlp-ejs
```

## Settings (.env)

| Variable | Meaning |
|---|---|
| `OWNER_ID` | Your Telegram id (ask @userinfobot). If set, only you can use the bot. |
| `MAX_PLAYLIST_ITEMS` | Max videos read from a playlist (default 200) |
| `MAX_DURATION_SECONDS` / `MAX_FILE_SIZE_MB` | Per-video limits (2 h / 1800 MB) |
| `MP3_QUALITY` | `0` = best VBR (default) … `9`, or fixed like `320k` |
| `COOKIES_FILE` | Path to a `cookies.txt`, only if YouTube says "Sign in to confirm you're not a bot" |
| `JS_RUNTIME` | `auto` (default), `node`, `deno`, `none` |
| `MAX_CONCURRENT_JOBS` | Jobs running at once (default 1; extra ones wait in a queue) |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Bot online but silent | Fixed in this version (see below). Make sure only **one** copy of the bot is running (`pkill -f bot.py`). |
| Won't start / auth errors | Check the `.env` values; set the phone's date & time to **automatic**. |
| `FFmpeg ... not installed` | `pkg install ffmpeg` |
| Only low quality / "format not available" | `pkg install nodejs` then `pip install -U yt-dlp yt-dlp-ejs` |
| "Sign in to confirm you're not a bot" | Export cookies.txt from a logged-in browser, set `COOKIES_FILE` |
| pip fails on `Pyrogram` with a very new Python | `pip install kurigram` instead (same `pyrogram` import) |

## What was wrong with the original

`bot.py` created the Pyrogram client, and the handlers did `from bot import app`. Started as `python bot.py`, that file is `__main__`, so the handlers imported it a **second** time and attached themselves to a **second** client; the client that actually ran had no handlers, so the bot connected but never answered. The client now lives in `core.py` and everything imports it from there.
Other fixes: the event loop is created before Pyrogram is imported (Python 3.12+), `.env` is found regardless of the current folder, titles are HTML-escaped (odd characters used to be able to break messages), the unused `OWNER_ID` is now enforced, temp files live in `downloads/tmp` and are wiped on start/exit, and `TgCrypto` is optional so `pip install` can't fail on it.

## Layout

```
bot.py            entry point
core.py           the one shared Pyrogram client (+ start-up checks)
config.py         settings from .env
handlers/         start.py (welcome, access gate) · link.py (reads a link) · callbacks.py (buttons)
services/         runner.py (one-by-one pipeline) · sessions.py (state) · views.py (panels)
keyboards/        inline.py (all buttons)
utils/            ytdlp_utils.py · audio.py (FFmpeg) · progress.py · files.py · text.py · auth.py
```

Use only content you own or are allowed to download. The bot does not bypass DRM or access restrictions.
