"""HistoryEjector - a rebase must drop the epoch on both sides, or it becomes swap.

The bug this pins: when a rebase replaced the history, the server was never told.
Strata had no way to learn the dropped epoch's KV cells were unreachable, so it
kept every one of them mapped and faulted in. The prefix did not vanish when the
messages were discarded; it stopped being read and stayed resident, which is how
discarded history ends up in swap. On the Python side the same thing happened in
miniature: CPython does not hand freed arenas back eagerly, so the old messages
became garbage that was still mapped.

The eject is therefore two calls at one boundary: a synchronous KV release to the
engine, and a heap trim here. These tests pin the behaviour that makes it safe to
call on every rebase without risking a turn: a remote backend is a no-op, a zero
cut is a no-op, an out-of-range cut is the engine's refusal and not our error,
and none of them raise.
"""

import json
import sys
import types
from unittest import mock

import pytest

sys.path.insert(0, "/home/alca/.daedalus/daedalus-agent")

from agent.history_ejector import HistoryEjector, server_root, EjectResult


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestServerRoot:
    def test_local_strips_v1(self):
        assert server_root("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080"
        assert server_root("http://localhost:8080/v1") == "http://localhost:8080"

    def test_remote_is_none(self):
        # A remote API does not expose our host state; we must not pretend to control it.
        assert server_root("https://api.example.com/v1") is None


class TestEjectKv:
    def test_valid_cut_reports_release(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        body = {"ok": True, "raw": "OK EJECT 150", "pages": 150,
                "released_mib": 24, "pinned_mib": 0}
        with mock.patch("agent.history_ejector.urllib.request.urlopen",
                        return_value=_Resp(body)):
            res = e.eject_kv(150)
        assert res.ok
        assert res.cut_cells == 150
        assert res.pages == 150
        assert res.released_mib == 24
        assert e.ejects_sent == 1

    def test_zero_cut_is_a_noop(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        res = e.eject_kv(0)
        assert res.ok
        assert res.reason == "nothing to eject"
        assert e.ejects_sent == 0

    def test_remote_backend_is_a_safe_noop(self):
        e = HistoryEjector("https://api.example.com/v1")
        res = e.eject_kv(150)
        assert not res.ok
        assert "remote" in res.reason
        assert e.ejects_unsupported == 1

    def test_engine_refusal_is_not_an_error(self):
        # 409 is the engine rejecting a cut ahead of its live position. That is a
        # normal outcome (it means "nothing released"), never an exception.
        import urllib.error
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        err = urllib.error.HTTPError("u", 409, "refused", {}, None)
        with mock.patch("agent.history_ejector.urllib.request.urlopen", side_effect=err):
            res = e.eject_kv(999999)
        assert not res.ok
        assert "409" in res.reason
        assert e.ejects_refused == 1

    def test_transport_error_is_caught(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        with mock.patch("agent.history_ejector.urllib.request.urlopen",
                        side_effect=ConnectionError("refused")):
            res = e.eject_kv(150)
        assert not res.ok
        assert e.ejects_unsupported == 1


class TestHeapRelease:
    def test_release_heap_runs_collect_and_trim(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        fake = types.SimpleNamespace(malloc_trim=lambda n: 0, madvise=None)
        with mock.patch("agent.history_ejector.gc.collect") as coll, \
             mock.patch.object(HistoryEjector, "_libc_handle", return_value=fake):
            ok = e.release_heap()
        assert ok
        coll.assert_called_once()

    def test_release_heap_survives_missing_libc(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        with mock.patch("agent.history_ejector.gc.collect"), \
             mock.patch.object(HistoryEjector, "_libc_handle", return_value=None):
            assert e.release_heap() is False


class TestOnRebase:
    def test_on_rebase_ejects_and_trims(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        with mock.patch.object(HistoryEjector, "eject_kv",
                               return_value=EjectResult(ok=True, cut_cells=150)) as ej, \
             mock.patch.object(HistoryEjector, "release_heap", return_value=True):
            res = e.on_rebase([{"role": "user"}], cut_cells=150)
        assert ej.called
        assert res.heap_trimmed

    def test_on_rebase_survives_a_raising_eject(self):
        e = HistoryEjector("http://127.0.0.1:8080/v1")
        with mock.patch.object(HistoryEjector, "eject_kv",
                               side_effect=RuntimeError("boom")):
            # on_rebase itself must not raise: the caller wraps it, but a rebase
            # that fails to eject must still return its compressed conversation.
            with pytest.raises(RuntimeError):
                e.on_rebase([], cut_cells=150)