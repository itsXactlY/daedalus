"""Wedge detection for the mazemaker memory provider.

Both defects these cover produced the same symptom on 2026-08-30: the engine
stalled, ``GET /health`` kept answering 200 out of the front's process state,
and the agent ran for ~2h with no memory and no warning, three times.
"""

import json
import urllib.error

import pytest

import plugins.memory.mazemaker as mzm


@pytest.fixture(autouse=True)
def fresh_pod_health(monkeypatch):
    """Each test gets its own detector — the real one is a module singleton."""
    monkeypatch.setattr(mzm, "_POD_HEALTH", mzm._PodHealth())
    monkeypatch.setattr(mzm, "_BREAKER", mzm._Breaker())
    return mzm._POD_HEALTH


def _wedge(health, calls=None):
    for _ in range(calls or mzm._WEDGE_FAIL_THRESHOLD):
        health.record_fail("mazemaker_recall", TimeoutError("timed out"))


def _raiser(exc):
    def _fake(req, timeout=None):
        raise exc
    return _fake


# --- the detector --------------------------------------------------------

def test_wedge_declared_only_after_threshold(fresh_pod_health):
    for _ in range(mzm._WEDGE_FAIL_THRESHOLD - 1):
        fresh_pod_health.record_fail("mazemaker_recall", TimeoutError("t"))
        assert fresh_pod_health.is_wedged() is False
    fresh_pod_health.record_fail("mazemaker_recall", TimeoutError("t"))
    assert fresh_pod_health.is_wedged() is True


def test_wedge_declared_once_and_recovery_measured(fresh_pod_health, caplog):
    caplog.set_level("ERROR")
    _wedge(fresh_pod_health, calls=mzm._WEDGE_FAIL_THRESHOLD + 3)
    degraded = [r for r in caplog.records if "MEMORY DEGRADED" in r.message]
    assert len(degraded) == 1, "the outage must announce itself exactly once"

    fresh_pod_health.record_ok("mazemaker_recall")
    assert fresh_pod_health.is_wedged() is False
    assert fresh_pod_health.snapshot()["consecutive_failures"] == 0
    recovered = [r for r in caplog.records if "MEMORY RECOVERED" in r.message]
    assert len(recovered) == 1


def test_client_error_is_not_a_wedge(monkeypatch, fresh_pod_health):
    """A 4xx means the engine answered and rejected the args — not an outage."""
    monkeypatch.setattr(
        mzm.urllib.request, "urlopen",
        _raiser(urllib.error.HTTPError(mzm.TOOL_CALL_URL, 422, "bad", {}, None)),
    )
    for _ in range(mzm._WEDGE_FAIL_THRESHOLD + 2):
        with pytest.raises(urllib.error.HTTPError):
            mzm._tool("mazemaker_recall", {"query": "x"})
    assert fresh_pod_health.is_wedged() is False


@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("u", 503, "unavailable", {}, None),
    urllib.error.URLError("connection refused"),
    TimeoutError("read timed out"),
])
def test_server_side_failures_declare_a_wedge(monkeypatch, fresh_pod_health, exc):
    monkeypatch.setattr(mzm.urllib.request, "urlopen", _raiser(exc))
    for _ in range(mzm._WEDGE_FAIL_THRESHOLD):
        with pytest.raises(Exception):
            mzm._tool("mazemaker_recall", {"query": "x"})
    assert fresh_pod_health.is_wedged() is True


# --- the sticky READY verdict -------------------------------------------

def _stats_stub(calls, health, ok=True):
    def _fake(name, args, timeout=8.0):
        calls.append(name)
        if not ok:
            health.record_fail(name, TimeoutError("timed out"))
            raise TimeoutError("timed out")
        health.record_ok(name)
        return {"memories": 222203, "connections": 1506573}
    return _fake


def test_ready_verdict_expires_and_is_reprobed(monkeypatch, fresh_pod_health):
    """The core regression: READY used to be trusted for the whole session."""
    calls = []
    monkeypatch.setattr(mzm, "_tool", _stats_stub(calls, fresh_pod_health))
    provider = mzm.MazemakerMemoryProvider()

    assert provider.brain_ready() is True
    assert len(calls) == 1
    assert provider.brain_ready() is True
    assert len(calls) == 1, "inside the TTL the verdict is cached"

    provider._brain_checked_at -= mzm._BRAIN_POSITIVE_TTL_S + 1
    assert provider.brain_ready() is True
    assert len(calls) == 2, "an expired READY must be re-probed, not trusted"


def test_live_wedge_outranks_a_cached_ready(monkeypatch, fresh_pod_health):
    calls = []
    monkeypatch.setattr(mzm, "_tool", _stats_stub(calls, fresh_pod_health))
    provider = mzm.MazemakerMemoryProvider()
    assert provider.brain_ready() is True

    _wedge(fresh_pod_health)
    assert provider.brain_ready() is False
    assert provider.is_available() is False


def test_wedge_can_end_on_its_own(monkeypatch, fresh_pod_health):
    calls = []
    monkeypatch.setattr(mzm, "_tool", _stats_stub(calls, fresh_pod_health))
    provider = mzm.MazemakerMemoryProvider()
    provider.brain_ready()
    _wedge(fresh_pod_health)
    assert provider.brain_ready() is False

    provider._brain_checked_at -= mzm._BRAIN_NEGATIVE_TTL_S + 1
    assert provider.brain_ready() is True, "the negative TTL must allow a re-probe"
    assert fresh_pod_health.is_wedged() is False


def test_shaped_but_empty_stats_is_not_ready(monkeypatch, fresh_pod_health):
    monkeypatch.setattr(mzm, "_tool", lambda *a, **k: {"memories": None})
    assert mzm.MazemakerMemoryProvider().brain_ready() is False


def test_probe_timeout_is_not_the_old_hair_trigger():
    assert mzm._BRAIN_PROBE_TIMEOUT_S > 1.5


# --- the outage is visible ----------------------------------------------

def test_tool_result_carries_the_outage(monkeypatch, fresh_pod_health):
    def _fake(name, args, timeout=8.0):
        raise TimeoutError("timed out")
    monkeypatch.setattr(mzm, "_tool", _fake)
    _wedge(fresh_pod_health)

    payload = json.loads(
        mzm.MazemakerMemoryProvider().handle_tool_call(
            "mazemaker_recall", {"query": "status"}
        )
    )
    assert "MEMORY DEGRADED" in payload["error"]
    assert payload["memory_status"]["wedged"] is True
    assert payload["memory_status"]["consecutive_failures"] >= mzm._WEDGE_FAIL_THRESHOLD


def test_prefetch_says_memory_is_down_instead_of_returning_nothing(
    monkeypatch, fresh_pod_health
):
    _wedge(fresh_pod_health)
    block = mzm.MazemakerMemoryProvider().prefetch(
        "how is the router work going", session_id="s1"
    )
    assert block.startswith("[memory unavailable]")


def test_prefetch_is_normal_when_healthy(monkeypatch, fresh_pod_health):
    monkeypatch.setattr(
        mzm.MazemakerMemoryProvider, "_build_enriched_context",
        lambda self, q: "recalled context",
    )
    monkeypatch.setattr(mzm, "_mission_control_flags", lambda: (False, False, 1200))
    block = mzm.MazemakerMemoryProvider().prefetch("a real query", session_id="s1")
    assert block == "recalled context"


class TestBreakerGoesColdInsteadOfRetryingForever:
    def _reset(self, M):
        M._BREAKER.reset()
        M._POD_HEALTH.__init__()

    def test_a_hanging_pod_costs_the_timeout_only_until_it_is_declared_cold(self, monkeypatch):
        import time
        import urllib.request
        import plugins.memory.mazemaker as M

        self._reset(M)

        def _hang(*a, **k):
            raise TimeoutError("timed out")

        monkeypatch.setattr(urllib.request, "urlopen", _hang)

        attempted = 0
        cold = 0
        for _ in range(10):
            try:
                M._tool("mazemaker_stats", {}, timeout=0.01)
                attempted += 1
            except M.PodOffline:
                cold += 1
            except TimeoutError:
                attempted += 1

        assert attempted == M._WEDGE_FAIL_THRESHOLD
        assert cold == 10 - M._WEDGE_FAIL_THRESHOLD
        self._reset(M)

    def test_a_cold_pod_touches_no_socket(self, monkeypatch):
        import urllib.request
        import plugins.memory.mazemaker as M

        self._reset(M)
        M._BREAKER.trip()

        def _boom(*a, **k):
            raise AssertionError("a cold breaker must not open a socket")

        monkeypatch.setattr(urllib.request, "urlopen", _boom)
        with pytest.raises(M.PodOffline):
            M._tool("mazemaker_stats", {}, timeout=1.0)
        self._reset(M)

    def test_the_probe_interval_backs_off_instead_of_hammering(self):
        import plugins.memory.mazemaker as M

        self._reset(M)
        M._BREAKER.trip()
        waits = []
        for _ in range(5):
            waits.append(M._BREAKER.snapshot()["next_probe_s"])
            M._BREAKER._open_since = 0.0
            M._BREAKER.is_open()
        assert waits == sorted(waits)
        assert waits[0] < waits[-1]
        assert waits[-1] == M._OFFLINE_BACKOFF_S[-1]
        self._reset(M)

    def test_one_good_call_closes_the_breaker(self, monkeypatch):
        import json
        import urllib.request
        import plugins.memory.mazemaker as M

        self._reset(M)
        M._BREAKER.trip()
        M._BREAKER._open_since = 0.0

        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"result": {"memories": 5}}).encode()

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
        assert M._tool("mazemaker_stats", {}) == {"memories": 5}
        assert M._BREAKER.snapshot() == {"open": False}
        self._reset(M)
