# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic (ISHU fork).

"""Background scheduler: periodic cleanup.

Runs a lightweight asyncio loop that prunes orphaned files in cache/ and
downloads/ to prevent disk exhaustion (the #1 cause of slow playback).
"""

import asyncio
import time
from pathlib import Path

from ishu import config, logger


# Directories we are allowed to prune. Anything outside these is never touched.
_PRUNE_DIRS = ("cache", "downloads")



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
