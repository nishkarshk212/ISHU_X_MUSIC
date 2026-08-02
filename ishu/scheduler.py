# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic (ISHU fork).

"""Background scheduler: daily restart + periodic cleanup.

The bot can slowly degrade over days of uptime because:
  * googlevideo stream URLs are cached in the queue and expire (~6h); a long
    uptime means more stale URLs are attempted before falling back to a download.
  * cache/ and downloads/ accumulate files, eating disk and slowing I/O.

This module runs two lightweight asyncio loops that fix both:
  1. A daily self-restart at RESTART_HOUR:RESTART_MIN (default 03:00) that
     rebuilds the process and wipes cache/ + downloads/.
  2. A periodic prune of cache/ + downloads/ for files older than CLEANUP_MAX_AGE
     (default 90 min), scanned every CLEANUP_INTERVAL (default 60 min).
"""

import asyncio
import shutil
import time
from pathlib import Path

from ishu import config, logger, restart_bot


# Directories we are allowed to prune. Anything outside these is never touched.
_PRUNE_DIRS = ("cache", "downloads")


def _time_until_next(hour: int, minute: int) -> float:
    """Seconds to wait until the next occurrence of hour:minute (local time)."""
    now = time.localtime()
    target = time.mktime(
        (
            now.tm_year,
            now.tm_mon,
            now.tm_mday,
            hour,
            minute,
            0,
            now.tm_wday,
            now.tm_yday,
            now.tm_isdst,
        )
    )
    delay = target - time.time()
    if delay <= 0:
        # Already passed today — schedule for the same time tomorrow.
        delay += 24 * 3600
    return delay


async def _daily_restart_loop() -> None:
    if config.RESTART_HOUR < 0:
        logger.info("Daily auto-restart disabled (RESTART_HOUR=%d).", config.RESTART_HOUR)
        return

    while True:
        delay = _time_until_next(config.RESTART_HOUR, config.RESTART_MIN)
        logger.info(
            "Daily auto-restart scheduled in %.1f min (at %02d:%02d local).",
            delay / 60,
            config.RESTART_HOUR,
            config.RESTART_MIN,
        )
        await asyncio.sleep(delay)
        logger.info(
            "Performing daily auto-restart at %02d:%02d to clear stale cache.",
            config.RESTART_HOUR,
            config.RESTART_MIN,
        )
        restart_bot()
        # restart_bot() re-execs the process; this coroutine won't continue.
        await asyncio.sleep(10)


def _prune_once() -> int:
    """Delete stale files in the prune dirs. Returns number of files removed."""
    now = time.time()
    removed = 0
    for d in _PRUNE_DIRS:
        base = Path(d)
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if not p.is_file():
                continue
            try:
                age = now - p.stat().st_mtime
                if age > config.CLEANUP_MAX_AGE:
                    p.unlink()
                    removed += 1
            except FileNotFoundError:
                # File vanished between listing and deletion — race with playback.
                pass
            except Exception as e:
                logger.warning("Cleanup: failed to prune %s: %s", p, e)
    return removed


async def _cleanup_loop() -> None:
    if config.CLEANUP_INTERVAL <= 0:
        logger.info("Periodic cleanup disabled (CLEANUP_INTERVAL<=0).")
        return

    while True:
        await asyncio.sleep(config.CLEANUP_INTERVAL)
        try:
            removed = _prune_once()
            if removed:
                logger.info("Cleanup: pruned %d stale file(s).", removed)
        except Exception as e:
            logger.warning("Cleanup loop error: %s", e)


class Scheduler:
    """Owns the background maintenance tasks; start/stop from main()."""

    def __init__(self):
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._tasks.append(asyncio.create_task(_cleanup_loop()))
        logger.info("Scheduler started (periodic cleanup).")

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks.clear()


# Module-level singleton used by __main__.
scheduler = Scheduler()
