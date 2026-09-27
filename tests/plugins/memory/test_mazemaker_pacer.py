"""Write pacing for the mazemaker pod.

The harness was the load generator. A pod write costs an embed plus a connect
pass, measured at 8-25s on this corpus; sync_turn fired one every 0.1s plus a
failed-write replay and the distillation block, so the pod's queue grew faster
than it drained and every write took longer than the last. The pacer makes the
write cadence a function of the measured write, and keeps retries and optional
work out of the way while the pod is busy.
"""

import time

import pytest

import plugins.memory.mazemaker as mzm


@pytest.fixture(autouse=True)
def fresh_pacer(monkeypatch):
    """Each test gets its own pacer — the real one is a module singleton."""
    pacer = mzm._PodPacer()
    monkeypatch.setattr(mzm, "_PACER", pacer)
    monkeypatch.setattr(mzm, "_BREAKER", mzm._Breaker())
    return pacer


def _age(pacer, seconds):
    """Pretend the last write happened `seconds` ago."""
    with pacer._lock:
        pacer._last_write_ts -= seconds


# --- the cadence ---------------------------------------------------------

def test_fresh_pacer_is_ready(fresh_pacer):
    """No write yet means no back-pressure: the old behaviour."""
    assert fresh_pacer.ready() is True
    assert fresh_pacer.is_slow() is False


def test_slow_write_sets_the_cadence_from_the_measurement(fresh_pacer):
    fresh_pacer.note("mazemaker_remember", 15.0)
    assert fresh_pacer.interval() == pytest.approx(15.0 * mzm._PACE_FACTOR)
    assert fresh_pacer.ready() is False
    _age(fresh_pacer, 15.0 * mzm._PACE_FACTOR)
    assert fresh_pacer.ready() is True


def test_fast_pod_keeps_the_old_cadence(fresh_pacer):
    """A 0.2s write must not slow a normal chat turn down."""
    fresh_pacer.note("mazemaker_remember", 0.2)
    assert fresh_pacer.interval() == mzm._PACE_MIN_S
    assert fresh_pacer.ready() is False
    _age(fresh_pacer, mzm._PACE_MIN_S)
    assert fresh_pacer.ready() is True


def test_reads_do_not_set_the_write_cadence(fresh_pacer):
    """Recall costs 10s+ here in normal operation. It is not back-pressure."""
    fresh_pacer.note("mazemaker_recall", 12.0)
    assert fresh_pacer.ready() is True
    assert fresh_pacer.is_slow() is False


def test_failed_write_does_not_pace_against_a_fiction(fresh_pacer):
    """A timeout must not become the cadence for the rest of the session."""
    fresh_pacer.note("mazemaker_remember", 30.0)
    fresh_pacer.forget()
    assert fresh_pacer.ready() is True
    assert fresh_pacer.is_slow() is False


def test_is_slow_tracks_the_write_path_only(fresh_pacer):
    fresh_pacer.note("mazemaker_remember", 8.0)
    assert fresh_pacer.is_slow() is True
    fresh_pacer.note("mazemaker_recall", 0.1)
    assert fresh_pacer.is_slow() is True, "a fast read does not un-slow the writes"


# --- what sync_turn does with it -----------------------------------------

def _provider():
    p = mzm.MazemakerMemoryProvider.__new__(mzm.MazemakerMemoryProvider)
    p._turn_count = 0
    p._last_soak_ts = 0.0
    p._brain_ready = False
    p._session_id = "20260927_000000_000000"
    return p


def test_sync_turn_defers_the_soak_while_the_pod_is_busy(monkeypatch, fresh_pacer):
    """The load reduction: a second turn does not add a second write."""
    calls = []
    monkeypatch.setattr(mzm, "_remember", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(mzm, "_FAILED_WRITE_SPOOL", __import__("collections").deque(maxlen=5))
    fresh_pacer.note("mazemaker_remember", 15.0)
    p = _provider()
    p.sync_turn("wie gehts", "gute frage", session_id=p._session_id)
    assert calls == [], "the pod is mid-write; do not queue behind it"
    assert fresh_pacer.stats()["deferred"] == 1

    _age(fresh_pacer, 15.0 * mzm._PACE_FACTOR)
    p.sync_turn("wie gehts", "gute frage", session_id=p._session_id)
    assert len(calls) == 1


def test_sync_turn_still_writes_on_a_healthy_pod(monkeypatch, fresh_pacer):
    calls = []
    monkeypatch.setattr(mzm, "_remember", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(mzm, "_FAILED_WRITE_SPOOL", __import__("collections").deque(maxlen=5))
    p = _provider()
    p.sync_turn("wie gehts", "gute frage", session_id=p._session_id)
    assert len(calls) == 1
    assert calls[0][0].startswith(f"auto:turn:{p._session_id}:")


# --- retries ------------------------------------------------------------

def test_no_replay_into_a_cold_pod(fresh_pacer, monkeypatch):
    """Popping and re-spooling a refused write moves it nowhere."""
    mzm._BREAKER.trip()
    assert mzm._replay_allowed() is False


def test_no_replay_before_the_cadence(fresh_pacer):
    fresh_pacer.note("mazemaker_remember", 15.0)
    assert mzm._replay_allowed() is False
    _age(fresh_pacer, 15.0 * mzm._PACE_FACTOR)
    assert mzm._replay_allowed() is True


def test_replay_is_not_vetoed_forever_by_a_slow_pod(fresh_pacer):
    """Otherwise the spool fills to its cap and drops the oldest turns."""
    fresh_pacer.note("mazemaker_remember", 15.0)
    _age(fresh_pacer, 15.0 * mzm._PACE_FACTOR)
    assert fresh_pacer.is_slow() is True
    assert mzm._replay_allowed() is True


def test_status_exposes_the_pressure(monkeypatch, fresh_pacer):
    fresh_pacer.note("mazemaker_remember", 15.0)
    fresh_pacer.defer()
    status = _provider().memory_status()
    assert status["pacer"]["last_write_s"] == 15.0
    assert status["pacer"]["deferred"] == 1
    assert "spool" in status
