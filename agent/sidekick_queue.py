"""One background slot, one request at a time, hygiene first.

Everything that is not the live conversation shares llama-server's sidekick
slot: compaction summaries, the hot-swap prefill, memory flushes, the
background skill/memory review. Those used to fire whenever they were ready.
On 2026-09-17 the skill review prefilled a 28k snapshot beside main while a
compaction wanted the same slot, dropping main's decode from 16 to 1.5 t/s --
and under a unified KV cache every job's prompt also eats the fast layer main
is reading from.

This gate serialises them against each other, not against main (except on a
one-conversation engine). A waiting request with a better priority always goes
next, so a compaction never waits behind a skill review; a request that is
already running is never interrupted.
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
DEFERRED = 3    # fire-and-forget: titles, curator, skill review. Waits for a quiet engine.

_TASK_PRIORITY = {
    "compression": HYGIENE,
    "hot_swap_prefill": HYGIENE,
    "flush_memories": MEMORY,
    "title_generation": DEFERRED,
    "curator": DEFERRED,
    "skills_hub": DEFERRED,
}

# On a one-conversation engine every foreign request parks the main tape first
# (32-38 s at ~30k tokens), so work nobody waits for runs only once main has
# been quiet this long, and never waits longer than the cap.
DEFER_IDLE_S = 90.0
DEFER_MAX_S = 3600.0


def priority_for_task(task: Optional[str]) -> int:
    return _TASK_PRIORITY.get(task or "", BACKGROUND)


class SidekickGate:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._busy = False
        self._waiting: list = []
        self._seq = itertools.count()
        self._reserved_until = 0.0
        self._main_depth = 0
        self._main_last_end = 0.0
        self.single_sequence = False

    # -- main interlock -------------------------------------------------
    # Only a one-conversation engine (Strata) holds background work until main
    # is done: there a foreign request parks main's tape. A llama-server with
    # -np 2+ runs the sidekick slot beside main. The 2026-09-24 interlock here
    # blamed two slots for a ggml-cuda.cu:109 MMVQ launch failure, but the same
    # crash recurred in main.log with only slot 1 busy (35B-A3B, prompt end).
    def main_begin(self) -> None:
        with self._cond:
            self._main_depth += 1

    def main_end(self) -> None:
        with self._cond:
            if self._main_depth > 0:
                self._main_depth -= 1
            if self._main_depth == 0:
                self._main_last_end = time.monotonic()
                self._cond.notify_all()

    def main_active(self) -> bool:
        with self._cond:
            return self._main_depth > 0

    @contextlib.contextmanager
    def main_turn(self):
        """Main never waits; on a one-conversation engine it blocks background work while it runs."""
        self.main_begin()
        try:
            yield
        finally:
            self.main_end()

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

    def _must_defer(self, priority: int, since: float) -> bool:
        """Work nobody waits for stays off a one-conversation engine while main is warm."""
        if priority < DEFERRED or not self.single_sequence:
            return False
        now = time.monotonic()
        if now - since >= DEFER_MAX_S:
            return False
        return now - self._main_last_end < DEFER_IDLE_S

    def acquire(self, priority: int) -> None:
        ticket = (int(priority), next(self._seq))
        since = time.monotonic()
        with self._cond:
            heapq.heappush(self._waiting, ticket)
            while (self._busy or self._waiting[0] != ticket
                   or (self.single_sequence and self._main_depth > 0)
                   or self._must_defer(ticket[0], since)
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
