"""One background slot, one request at a time, hygiene first.

Everything that is not the live conversation shares llama-server's sidekick
slot: compaction summaries, the hot-swap prefill, memory flushes, the
background skill/memory review. Those used to fire whenever they were ready.
On 2026-09-17 the skill review prefilled a 28k snapshot beside main while a
compaction wanted the same slot, dropping main's decode from 16 to 1.5 t/s --
and under a unified KV cache every job's prompt also eats the fast layer main
is reading from.

This gate serialises them. A waiting request with a better priority always
goes next, so a compaction never waits behind a skill review; a request that
is already running is never interrupted.
"""

from __future__ import annotations

import asyncio
import contextlib
import heapq
import itertools
import threading
import time
from typing import Optional

HYGIENE = 0     # compaction summaries, hot-swap prefill
MEMORY = 1      # memory flush
BACKGROUND = 2  # skill/memory review and anything else

_TASK_PRIORITY = {
    "compression": HYGIENE,
    "hot_swap_prefill": HYGIENE,
    "flush_memories": MEMORY,
}


def priority_for_task(task: Optional[str]) -> int:
    return _TASK_PRIORITY.get(task or "", BACKGROUND)


class SidekickGate:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._busy = False
        self._waiting: list = []
        self._seq = itertools.count()
        self._reserved_until = 0.0

    def reserve(self, seconds: float) -> None:
        """Hold the slot for hygiene only: it carries a prewarmed turn 0.

        2026-09-17 the title generator and the skill review ran on the sidekick
        seconds after a 16.9k-token prime finished there and overwrote it, so
        the swap had nothing to swap to. Until the swap lands (or this expires)
        only HYGIENE requests get the slot.
        """
        with self._cond:
            self._reserved_until = time.monotonic() + max(0.0, seconds)
            self._cond.notify_all()

    def release_reservation(self) -> None:
        with self._cond:
            self._reserved_until = 0.0
            self._cond.notify_all()

    def reserved(self) -> bool:
        return time.monotonic() < self._reserved_until

    def acquire(self, priority: int) -> None:
        ticket = (int(priority), next(self._seq))
        with self._cond:
            heapq.heappush(self._waiting, ticket)
            while (self._busy or self._waiting[0] != ticket
                   or (ticket[0] > HYGIENE and self.reserved())):
                self._cond.wait(timeout=1.0)
            heapq.heappop(self._waiting)
            self._busy = True

    def is_busy(self) -> bool:
        with self._cond:
            return self._busy or bool(self._waiting)

    def release(self) -> None:
        with self._cond:
            self._busy = False
            self._cond.notify_all()

    @contextlib.contextmanager
    def hold(self, priority: int):
        self.acquire(priority)
        try:
            yield
        finally:
            self.release()

    @contextlib.asynccontextmanager
    async def ahold(self, priority: int):
        waiter = asyncio.ensure_future(asyncio.to_thread(self.acquire, priority))
        try:
            await asyncio.shield(waiter)
        except asyncio.CancelledError:
            # The thread keeps waiting and will get the gate eventually; hand
            # it straight back then, or the slot stays locked for good.
            waiter.add_done_callback(lambda _f: self.release())
            raise
        try:
            yield
        finally:
            self.release()


sidekick_gate = SidekickGate()
