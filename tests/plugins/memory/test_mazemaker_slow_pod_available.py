"""A slow-but-alive pod must stay AVAILABLE, not read as down.

is_available() is a tool-schema gate: tools/mazemaker_tools.py::_check_mazemaker_
available() calls it to decide whether the 37 mazemaker schemas ship in the
request. So a wrong False here does not just log a warning — it silently removes
memory from the model for that turn.

The startup deferral (probe off the main thread) created exactly that risk: the
verdict is None for the first seconds, and `bool(None)` is False. This file
pins the distinction that matters: UNKNOWN is not the same as DOWN.
"""
import io
import json
import threading
import time

import pytest

from plugins.memory import mazemaker as M


@pytest.fixture(autouse=True)
def fresh_pod_health(monkeypatch):
    """Each test gets its own detector — the real one is a module singleton."""
    monkeypatch.setattr(M, "_POD_HEALTH", M._PodHealth())
    monkeypatch.setattr(M, "_BREAKER", M._Breaker())
    return M._POD_HEALTH


class _SlowButAlivePod(M.MazemakerMemoryProvider):
    """Answers correctly, just slower than the grace window."""

    def __init__(self, delay=3.0, **kw):
        super().__init__(**kw)
        self.delay = delay
        self.release = threading.Event()

    def brain_ready(self, refresh: bool = False, blocking: bool = True) -> bool:
        if not blocking:
            self._probe_in_background()
            return self._brain_ready is True
        self.release.wait(self.delay)
        # a real, healthy answer — the pod is up, it is just slow
        self._brain_ready = True
        self._brain_checked_at = time.monotonic()
        return True


def test_slow_alive_pod_is_still_available_before_verdict_lands():
    """The regression: verdict None -> False -> memory vanishes from the schema."""
    p = _SlowButAlivePod(delay=3.0)
    t0 = time.monotonic()
    p.initialize("sess-slow-alive")
    verdict = p.is_available()
    elapsed = time.monotonic() - t0
    p.release.set()

    assert p._brain_ready is None, "the slow pod answered inside the grace window"
    assert verdict is True, (
        "a slow-but-healthy pod was reported unavailable — its tools would be "
        "filtered out of the request"
    )
    assert elapsed < 2.0, "is_available() waited for the full probe (%.2fs)" % elapsed


def test_slow_alive_pod_becomes_ready_once_the_probe_lands():
    p = _SlowButAlivePod(delay=0.0)
    p.initialize("sess-lands")
    assert p.wait_for_brain_probe(timeout=5.0) is True
    assert p.is_available() is True
    p.release.set()


def test_confirmed_down_pod_is_still_unavailable():
    """The other direction: grace must not turn a down pod into available."""

    def _refuse(name, args, timeout=None):
        raise ConnectionRefusedError("pod is down")

    orig = M._tool
    M._tool = _refuse
    try:
        p = M.MazemakerMemoryProvider()
        p.initialize("sess-down")
        assert p.wait_for_brain_probe(timeout=8.0) is False
        assert p.is_available() is False, "a confirmed-down pod was offered"
    finally:
        M._tool = orig


def test_grace_window_is_bounded_and_small():
    """A grace window is only safe if it cannot grow into a stall."""
    assert 0 < M._BRAIN_AVAIL_GRACE_S <= 1.0, M._BRAIN_AVAIL_GRACE_S
    src = open(M.__file__, encoding="utf-8").read()
    assert "_BRAIN_AVAIL_GRACE_S" in src
    # it must be a join timeout, never a second pod round trip
    assert "join(timeout=_BRAIN_AVAIL_GRACE_S)" in src


def test_asking_availability_generates_no_pod_traffic():
    """is_available() is a schema question, not a health check.

    It used to kick off its own probe to fill the unknown. That is wrong twice:
    it turns every schema filter into pod traffic, and a probe that answers
    stats clears a live data-path wedge, so asking "are you up?" healed the very
    wedge it should have reported (test_mazemaker_wedge caught the second half).
    """
    calls = []

    def _counting_tool(name, args, timeout=None):
        calls.append(name)
        return {"memories": 229487, "connections": 1}

    orig = M._tool
    M._tool = _counting_tool
    try:
        p = M.MazemakerMemoryProvider()
        for _ in range(5):
            p.is_available()
    finally:
        M._tool = orig

    assert calls == [], "is_available() made %d pod calls: %r" % (len(calls), calls)


def test_availability_question_cannot_heal_a_wedge(monkeypatch, fresh_pod_health):
    """A wedged data path stays reported down, no matter who asks.

    Stubbed at urlopen, not at _tool, so the real _tool runs and actually
    records the outcomes — the wedge is raised by _tool's own instrumentation.
    """
    def _stats_ok_recall_dead(req, timeout=None):
        # the exact 2026-08-30 shape: stats answers, the data path is dead
        body = json.dumps({"result": {"memories": 222203, "connections": 1506573}})
        return io.BytesIO(body.encode())

    def _fake(req, timeout=None):
        if "mazemaker_stats" in json.loads(req.data.decode())["name"]:
            return _stats_ok_recall_dead(req, timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(M.urllib.request, "urlopen", _fake)
    for _ in range(M._WEDGE_FAIL_THRESHOLD):
        with pytest.raises(Exception):
            M._tool("mazemaker_recall", {"query": "x"})
    assert fresh_pod_health.is_wedged(), "the wedge never tripped in the fixture"

    p = M.MazemakerMemoryProvider()
    for _ in range(5):
        assert p.is_available() is False, (
            "availability probing cleared a live data-path wedge"
        )
