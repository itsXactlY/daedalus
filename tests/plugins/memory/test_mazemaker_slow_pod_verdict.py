"""A slow pod must still produce a correct verdict after the startup deferral.

Fast startup is worthless if a slow pod now yields a wrong READY. Measured
2026-09-27: 42 of 96 recorded CLI starts logged
`mazemaker_stats failed ... TimeoutError`; every one of those seconds used to be
spent on the main thread in front of the prompt.
"""
import time

from plugins.memory import mazemaker as M


class _TimingOutPod(M.MazemakerMemoryProvider):
    """Verdict bookkeeping stays real; only the verdict VALUE is forced False."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.probes = 0

    def brain_ready(self, refresh: bool = False, blocking: bool = True) -> bool:
        self.probes += 1
        if not blocking:
            self._probe_in_background()
            return bool(self._brain_ready)
        # what the real code does when _tool("mazemaker_stats") blows its budget
        self._brain_ready = False
        self._brain_checked_at = time.monotonic()
        return False


def test_slow_pod_yields_offline_not_ready():
    p = _TimingOutPod()
    assert p.brain_ready(refresh=True, blocking=True) is False
    assert p.is_available() is False, "a timing-out pod reported itself available"


def test_slow_pod_startup_fast_and_verdict_correct():
    p = _TimingOutPod()
    t0 = time.monotonic()
    p.initialize("sess-slow")
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, "initialize() blocked %.2fs on a timing-out pod" % elapsed

    verdict = p.wait_for_brain_probe(timeout=15.0)
    assert verdict is False, "deferred probe concluded %r for a timing-out pod" % (verdict,)
    assert p.probes >= 1, "no probe actually ran"
    assert p.is_available() is False, "a timing-out pod became available afterwards"


def test_deferred_probe_keeps_the_real_budget():
    """The deferral must not quietly widen or drop the 4 s pod budget."""
    calls = []

    def _slow_tool(name, args, timeout=None):
        calls.append((name, timeout))
        time.sleep((timeout or 0) + 0.5)
        raise TimeoutError("timed out")

    orig = M._tool
    M._tool = _slow_tool
    try:
        p = M.MazemakerMemoryProvider()
        t0 = time.monotonic()
        p.initialize("sess-budget")
        assert time.monotonic() - t0 < 1.0, "initialize() blocked on the real _tool"
        assert p.wait_for_brain_probe(timeout=20.0) is False
    finally:
        M._tool = orig

    assert calls, "the deferred probe never called the pod"
    assert calls[0][0] == "mazemaker_stats", calls[0]
    assert calls[0][1] == M._BRAIN_PROBE_TIMEOUT_S, "budget changed: %r" % (calls[0][1],)


def test_warm_pod_still_reports_ready():
    """The common case must not regress into a permanent UNKNOWN."""
    def _fast_tool(name, args, timeout=None):
        return {"memories": 229487, "connections": 1}

    orig = M._tool
    M._tool = _fast_tool
    try:
        p = M.MazemakerMemoryProvider()
        p.initialize("sess-warm")
        assert p.wait_for_brain_probe(timeout=10.0) is True
        assert p.is_available() is True
    finally:
        M._tool = orig
