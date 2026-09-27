"""The failed-write replay must never become a turn-latency item.

Measured 2026-09-27 on this box: a mazemaker_remember costs the pod 8-25s, and
``sync_turn`` -- the call that follows every assistant response -- replayed the
whole spool inline before it even looked at the soak rate-limit. A pod under
load spools more writes, the next turn drains more of them, and each drain makes
the pod slower: a feedback loop that showed up to the user as "every tool is
glacial". These tests pin the bound, and that a failing pod stops the pass
instead of being hammered.
"""

import pytest

import plugins.memory.mazemaker as mzm


@pytest.fixture
def spool(monkeypatch):
    """An in-memory spool with N entries and no disk mirror."""
    monkeypatch.setattr(mzm, "_FAILED_WRITE_SPOOL", mzm.deque())
    monkeypatch.setattr(mzm, "_persist_spool_locked", lambda: None)
    return mzm._FAILED_WRITE_SPOOL


def _fill(n):
    for i in range(n):
        mzm._spool_write(f"decision:t{i}", f"body {i}")


def _counting(monkeypatch, fail_at=None):
    sent = []

    def _fake(name, args):
        sent.append(args["label"])
        if fail_at is not None and len(sent) == fail_at:
            raise RuntimeError("pod refused")
        return {"ok": True}

    monkeypatch.setattr(mzm, "_tool", _fake)
    return sent


def test_replay_is_bounded_by_default(spool, monkeypatch):
    """The regression itself: 50 spooled writes must not become 50 round-trips."""
    _fill(50)
    sent = _counting(monkeypatch)

    replayed = mzm._replay_failed_writes()

    assert replayed == mzm._REPLAY_BATCH
    assert len(sent) == mzm._REPLAY_BATCH
    # Oldest first, and the rest still queued -- nothing is dropped.
    assert sent == ["decision:t0", "decision:t1", "decision:t2"]
    assert len(spool) == 50 - mzm._REPLAY_BATCH


def test_replay_keeps_going_across_successive_passes(spool, monkeypatch):
    _fill(7)
    _counting(monkeypatch)

    for _ in range(3):
        mzm._replay_failed_writes()

    assert not spool


def test_replay_stops_at_the_first_refusal(spool, monkeypatch):
    """A pod that is refusing writes must get one attempt, not the whole batch."""
    _fill(10)
    sent = _counting(monkeypatch, fail_at=1)

    replayed = mzm._replay_failed_writes(limit=5)

    assert replayed == 0
    assert len(sent) == 1
    # The refused entry went back to the tail, the other nine never moved.
    assert len(spool) == 10
    assert spool[-1] == ("decision:t0", "body 0")


def test_replay_of_an_empty_spool_is_a_noop(spool, monkeypatch):
    sent = _counting(monkeypatch)

    assert mzm._replay_failed_writes(limit=5) == 0
    assert sent == []


def test_sync_turn_replays_one_write_per_turn(spool, monkeypatch):
    """sync_turn runs right behind the response, so its budget is one write."""
    _fill(20)
    sent = _counting(monkeypatch)
    provider = object.__new__(mzm.MazemakerMemoryProvider)
    provider._turn_count = 0
    provider._last_soak_ts = 0.0
    provider._session_id = "s1"
    provider._resume_block = ""
    # Force the soak itself to no-op so only the replay is under test.
    monkeypatch.setattr(mzm, "_is_non_answer", lambda _t: True)

    provider.sync_turn("q", "a")

    assert len(sent) == 1
    assert len(spool) == 19
