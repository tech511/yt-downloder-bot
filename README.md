# Personal YouTube Downloader Bot

A small personal-use Telegram bot built with Python, Pyrogram, and yt-dlp. It reads public YouTube video metadata and offers **Video** and **Audio** buttons.

## Features
- Shows title, description/caption, creator/uploader, duration, upload date, views, likes, video ID, and source URL when available.
- Video: downloads the best available video/audio combination and merges to MP4 when FFmpeg is available.
- Audio: prefers the best M4A audio stream, otherwise uses the best available audio stream. It preserves the original stream instead of converting it to a potentially lower-quality MP3. Non-MP3/M4A audio is sent as a document to avoid Telegram audio-format restrictions.
- Per-user download lock, temporary folders, cache expiry, retries, duration/file-size limits, and error messages.
- Separate files for configuration, handlers, keyboards, and utilities.

## Requirements
- Python 3.10+
- FFmpeg installed and available on PATH (needed for video merging and embedding metadata)
- Telegram bot token from BotFather
- Telegram API ID and API hash from https://my.telegram.org

## Setup
1. Install FFmpeg using your host's package manager. On Debian/Ubuntu: `apt-get update && apt-get install -y ffmpeg`.
2. Create a virtual environment (recommended): `python -m venv .venv` and activate it.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in `BOT_TOKEN`, `API_ID`, and `API_HASH`.
5. Start: `python bot.py`.

## Configuration
- `MAX_FILE_SIZE_MB`: default 1800 MB.
- `MAX_DURATION_SECONDS`: default 7200 seconds (2 hours).
- `LOG_LEVEL`: default INFO.

## Important notes
- This project is designed for personal use. Only download material you own or are authorized to download, and follow YouTube's terms and applicable copyright law.
- It does not bypass DRM, paywalls, private videos, or other access restrictions. Some videos may fail due to regional restrictions, YouTube changes, age checks, or unavailable formats.
- YouTube frequently changes its delivery mechanisms. Keep yt-dlp updated if extraction stops working: `pip install -U yt-dlp`.
- The metadata cache is in memory and resets when the bot restarts. Do not run multiple replicas unless you add shared state/locking.
- A free host may not have enough disk, memory, execution time, or outbound bandwidth for large media. Configure limits accordingly.
