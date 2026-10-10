"""Strata holds one conversation: work nobody waits for must not park the main tape.

A foreign request makes the engine park main first (32-38 s at ~30k tokens), so
fire-and-forget jobs wait until main has been quiet, with a cap.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agent import sidekick_queue as sq
from agent.backend_kind import _cache, is_single_sequence


@pytest.fixture
def gate(monkeypatch):
    g = sq.SidekickGate()
    g.single_sequence = True
    monkeypatch.setattr(sq, "DEFER_IDLE_S", 0.3)
    return g


def test_task_priorities():
    assert sq.priority_for_task("title_generation") == sq.DEFERRED
    assert sq.priority_for_task("curator") == sq.DEFERRED
    assert sq.priority_for_task("compression") == sq.HYGIENE
    assert sq.priority_for_task("approval") == sq.BACKGROUND     # blocks the user: never deferred


def test_deferred_waits_for_a_quiet_main(gate):
    gate.main_begin()
    gate.main_end()                                              # main just finished
    t0 = time.monotonic()
    with gate.hold(sq.DEFERRED):
        waited = time.monotonic() - t0
    assert waited >= 0.25


def test_background_and_hygiene_are_not_delayed(gate):
    gate.main_begin()
    gate.main_end()
    t0 = time.monotonic()
    for prio in (sq.HYGIENE, sq.MEMORY, sq.BACKGROUND):
        with gate.hold(prio):
            pass
    assert time.monotonic() - t0 < 0.2


def test_multi_slot_engine_is_unaffected(gate):
    gate.single_sequence = False
    gate.main_begin()
    gate.main_end()
    t0 = time.monotonic()
    with gate.hold(sq.DEFERRED):
        pass
    assert time.monotonic() - t0 < 0.2


def test_deferral_is_capped(gate, monkeypatch):
    monkeypatch.setattr(sq, "DEFER_IDLE_S", 60.0)
    monkeypatch.setattr(sq, "DEFER_MAX_S", 0.3)
    gate.main_begin()
    gate.main_end()
    t0 = time.monotonic()
    with gate.hold(sq.DEFERRED):
        pass
    assert 0.25 <= time.monotonic() - t0 < 2.0


class _Metrics(BaseHTTPRequestHandler):
    body = {}

    def do_GET(self):
        raw = json.dumps(self.body).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def _serve(body):
    _Metrics.body = body
    srv = HTTPServer(("127.0.0.1", 0), _Metrics)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_detects_strata_by_its_metrics(monkeypatch):
    monkeypatch.delenv("DAEDALUS_SINGLE_SEQUENCE", raising=False)
    _cache.clear()
    srv = _serve({"engine": {"expert_slots": 3993, "kv": "int8"}})
    try:
        assert is_single_sequence(f"http://127.0.0.1:{srv.server_port}/v1") is True
    finally:
        srv.shutdown()


def test_llama_server_is_not_single_sequence(monkeypatch):
    monkeypatch.delenv("DAEDALUS_SINGLE_SEQUENCE", raising=False)
    _cache.clear()
    srv = _serve({"slots": []})
    try:
        assert is_single_sequence(f"http://127.0.0.1:{srv.server_port}/v1") is False
    finally:
        srv.shutdown()


def test_remote_and_override(monkeypatch):
    _cache.clear()
    monkeypatch.delenv("DAEDALUS_SINGLE_SEQUENCE", raising=False)
    assert is_single_sequence("https://api.example.com/v1") is False
    monkeypatch.setenv("DAEDALUS_SINGLE_SEQUENCE", "1")
    assert is_single_sequence("https://api.example.com/v1") is True
