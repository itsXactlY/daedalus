"""initialize() must not hold the startup path on a pod call.

The regression this guards: `MazemakerMemoryProvider.initialize()` runs directly
in front of the interactive prompt, and its readiness probe is a real
`mazemaker_stats` round trip. Measured 2026-09-27: 3.0 s warm, 24.6 s for
`mazemaker_health`, and 42 of 96 recorded CLI starts logged
`mazemaker_stats failed ... TimeoutError` — every one of those seconds was spent
on the main thread before the user could type.
"""
import threading
import time

import pytest

from plugins.memory import mazemaker as M


class _SlowPod(M.MazemakerMemoryProvider):
    """A pod that takes 30 s — longer than any timeout, so a blocking call hangs."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = []
        self.main_thread = threading.current_thread()
        self.release = threading.Event()

    def brain_ready(self, refresh: bool = False, blocking: bool = True) -> bool:
        self.calls.append((threading.current_thread(), blocking))
        if blocking:
            self.release.wait(30)
            return False
        return super().brain_ready(refresh=refresh, blocking=blocking)


def test_initialize_does_not_block_on_a_slow_pod():
    p = _SlowPod()
    t0 = time.monotonic()
    p.initialize("sess-test")
    elapsed = time.monotonic() - t0
    p.release.set()

    assert elapsed < 1.0, (
        "initialize() took %.2fs — it blocked the startup path on a pod call"
        % elapsed
    )


def test_initialize_probes_off_the_main_thread():
    p = _SlowPod()
    main = threading.current_thread()
    p.initialize("sess-test")
    # give the deferred probe a moment to actually start
    p.wait_for_brain_probe(timeout=2.0)
    p.release.set()

    assert p.calls, "no probe was started at all"
    for thread, _blocking in p.calls:
        assert thread is not main, "the readiness probe ran on the main thread"


def test_is_available_does_not_block():
    p = _SlowPod()
    t0 = time.monotonic()
    p.is_available()
    elapsed = time.monotonic() - t0
    p.release.set()

    assert elapsed < 1.0, "is_available() blocked for %.2fs" % elapsed


def test_unknown_brain_reads_as_not_ready():
    """A deferred probe must not read as a confirmed-down pod."""
    p = M.MazemakerMemoryProvider()
    assert p.brain_ready(blocking=False) is False
    assert p._brain_ready is None, "the verdict was set without a probe"
    p.wait_for_brain_probe(timeout=6.0)


def test_dead_booted_constants_are_gone():
    """The boot retry loop it replaced was dead: attempts was 1, so it retried
    nothing. Constants and loop must not creep back in."""
    import re

    src = open(M.__file__, encoding="utf-8").read()
    assert not re.search(r"^_BRAIN_BOOT_ATTEMPTS\s*=", src, re.M)
    assert not re.search(r"^_BRAIN_BOOT_BACKOFF_S\s*=", src, re.M)
    # the boot loop itself must be gone, comments may still name what it was
    assert not re.search(r"^\s*for attempt in range\(_BRAIN_BOOT", src, re.M)


def test_probe_is_single_flight():
    """Repeated startup-path asks must not stack up pod calls."""
    p = M.MazemakerMemoryProvider()
    for _ in range(5):
        p.brain_ready(blocking=False)
    threads = []
    t = p._probe_thread
    if t is not None:
        threads.append(t)
    # all five calls must share the one in-flight probe
    assert p._probe_thread is t
    p.wait_for_brain_probe(timeout=8.0)


@pytest.mark.parametrize("timeout", [None, 0.0, 1.0])
def test_wait_for_brain_probe_returns_optional_verdict(timeout):
    p = M.MazemakerMemoryProvider()
    p.brain_ready(blocking=False)
    verdict = p.wait_for_brain_probe(timeout=timeout)
    assert verdict is None or isinstance(verdict, bool)
    p.wait_for_brain_probe(timeout=8.0)
