"""Flood-safe live progress message.

`post()` may be called from any thread (yt-dlp hooks, Pyrogram upload callbacks); it is
throttled so Telegram is never asked to edit the message more often than PROGRESS_INTERVAL.
"""
from __future__ import annotations

import asyncio
import logging
import time

from pyrogram.errors import FloodWait, MessageNotModified

import config

log = logging.getLogger(__name__)


class Reporter:
    def __init__(self, message, loop: asyncio.AbstractEventLoop, markup=None,
                 interval: float = config.PROGRESS_INTERVAL):
        self.message = message
        self.loop = loop
        self.markup = markup
        self.interval = interval
        self._last_text: str | None = None
        self._last_edit = 0.0
        self._last_post = 0.0
        self._blocked_until = 0.0

    async def set(self, text: str, force: bool = False) -> None:
        now = time.monotonic()
        if text == self._last_text or now < self._blocked_until:
            return
        if not force and now - self._last_edit < self.interval:
            return
        self._last_text, self._last_edit = text, now
        try:
            await self.message.edit_text(text, reply_markup=self.markup)
        except MessageNotModified:
            pass
        except FloodWait as exc:
            self._blocked_until = time.monotonic() + exc.value
        except Exception as exc:  # noqa: BLE001 - a failed progress edit must never kill a download
            log.debug("progress edit failed: %s", exc)

    def post(self, text: str) -> None:
        """Thread-safe and throttled; drops updates that arrive too quickly."""
        now = time.monotonic()
        if now - self._last_post < self.interval:
            return
        self._last_post = now
        asyncio.run_coroutine_threadsafe(self.set(text), self.loop)

    def post_force(self, text: str) -> None:
        """Thread-safe, always sent (use for stage changes)."""
        asyncio.run_coroutine_threadsafe(self.set(text, force=True), self.loop)
