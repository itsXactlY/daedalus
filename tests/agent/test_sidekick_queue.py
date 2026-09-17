"""The sidekick slot runs one background request at a time, hygiene first.

2026-09-17: a skill review prefilled a 28k snapshot on the sidekick slot while
a compaction wanted it, and main's decode on the other slot fell from 16 to
1.5 t/s. Background work queues now; a compaction never waits behind a review.
"""

import asyncio
import threading
import time

from agent.sidekick_queue import (
    BACKGROUND, HYGIENE, MEMORY, SidekickGate, priority_for_task,
)


def _start_waiter(gate, priority, order, name, started):
    def run():
        started.set()
        with gate.hold(priority):
            order.append(name)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _wait_queued(gate, n, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with gate._cond:
            if len(gate._waiting) >= n:
                return
        time.sleep(0.005)
    raise AssertionError(f"{n} waiters never queued")


def test_task_priorities():
    assert priority_for_task("compression") == HYGIENE
    assert priority_for_task("hot_swap_prefill") == HYGIENE
    assert priority_for_task("flush_memories") == MEMORY
    assert priority_for_task("skill_review") == BACKGROUND
    assert priority_for_task(None) == BACKGROUND


def test_hygiene_overtakes_queued_background_work():
    gate = SidekickGate()
    order = []
    gate.acquire(BACKGROUND)  # a review request is running
    threads = []
    for prio, name in ((BACKGROUND, "review-2"), (MEMORY, "flush"), (HYGIENE, "compaction")):
        ev = threading.Event()
        threads.append(_start_waiter(gate, prio, order, name, ev))
        ev.wait()
        _wait_queued(gate, len(threads))
    gate.release()
    for t in threads:
        t.join(2)
    assert order == ["compaction", "flush", "review-2"]


def test_same_priority_is_first_come_first_served():
    gate = SidekickGate()
    order = []
    gate.acquire(HYGIENE)
    threads = []
    for name in ("a", "b", "c"):
        ev = threading.Event()
        threads.append(_start_waiter(gate, BACKGROUND, order, name, ev))
        ev.wait()
        _wait_queued(gate, len(threads))
    gate.release()
    for t in threads:
        t.join(2)
    assert order == ["a", "b", "c"]


def test_a_running_request_is_never_interrupted():
    gate = SidekickGate()
    inside = threading.Event()
    leave = threading.Event()
    got_in = []

    def review():
        with gate.hold(BACKGROUND):
            inside.set()
            leave.wait(2)
            got_in.append("review-done")

    def compaction():
        with gate.hold(HYGIENE):
            got_in.append("compaction")

    t1 = threading.Thread(target=review, daemon=True)
    t1.start()
    inside.wait(2)
    t2 = threading.Thread(target=compaction, daemon=True)
    t2.start()
    _wait_queued(gate, 1)
    assert got_in == []
    leave.set()
    t1.join(2)
    t2.join(2)
    assert got_in == ["review-done", "compaction"]


def test_a_cancelled_async_waiter_does_not_lock_the_slot():
    gate = SidekickGate()

    async def scenario():
        gate.acquire(HYGIENE)

        async def waiter():
            async with gate.ahold(BACKGROUND):
                pass

        task = asyncio.ensure_future(waiter())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        gate.release()
        # the cancelled waiter's thread takes the gate and hands it back
        got = await asyncio.wait_for(asyncio.to_thread(gate.acquire, HYGIENE), 2)
        gate.release()
        return got

    asyncio.run(scenario())


def test_a_reserved_slot_only_takes_hygiene():
    gate = SidekickGate()
    gate.reserve(30)
    order = []
    ev = threading.Event()
    t = _start_waiter(gate, BACKGROUND, order, "review", ev)
    ev.wait()
    time.sleep(0.2)
    assert order == [], "a review must not overwrite a prewarmed turn 0"
    with gate.hold(HYGIENE):
        order.append("swap-prime")
    gate.release_reservation()
    t.join(3)
    assert order == ["swap-prime", "review"]


def test_a_reservation_expires_on_its_own():
    gate = SidekickGate()
    gate.reserve(0.3)
    order = []
    ev = threading.Event()
    t = _start_waiter(gate, BACKGROUND, order, "review", ev)
    t.join(3)
    assert order == ["review"]
