"""In-memory state: pending selection panels and running jobs (resets when the bot restarts)."""
from __future__ import annotations

import asyncio
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

PANEL_TTL = 30 * 60


@dataclass
class Panel:
    token: str
    user_id: int
    kind: str                       # "video" | "playlist"
    url: str
    info: dict[str, Any] | None = None          # single video metadata
    playlist: dict[str, Any] | None = None      # playlist metadata + entries
    video_url: str | None = None                # playlist link that also named one video
    selected: set[int] = field(default_factory=set)
    page: int = 0
    created: float = field(default_factory=time.time)


@dataclass
class Job:
    token: str
    user_id: int
    chat_id: int
    mode: str                       # "audio" | "video"
    entries: list[dict[str, Any]]
    cancel: threading.Event = field(default_factory=threading.Event)


PANELS: dict[str, Panel] = {}
ACTIVE_JOBS: dict[int, Job] = {}          # user_id -> running job
_TASKS: set[asyncio.Task] = set()


def _purge() -> None:
    now = time.time()
    for token in [t for t, p in PANELS.items() if now - p.created > PANEL_TTL]:
        PANELS.pop(token, None)


def new_panel(user_id: int, kind: str, url: str, **extra: Any) -> Panel:
    _purge()
    panel = Panel(token=secrets.token_hex(4), user_id=user_id, kind=kind, url=url, **extra)
    PANELS[panel.token] = panel
    return panel


def get_panel(token: str) -> Panel | None:
    _purge()
    return PANELS.get(token)


def drop_panel(token: str) -> None:
    PANELS.pop(token, None)


def spawn(coro) -> None:
    """Run a coroutine in the background and keep a reference so it is not garbage-collected."""
    task = asyncio.get_running_loop().create_task(coro)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
