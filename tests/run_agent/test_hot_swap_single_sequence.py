"""Hot-swap on a one-conversation engine (Strata): prewarm, cancel, promote, evict.

On the fork the next epoch is prefilled into a second slot, promoted to main, and the demoted slot is erased.
Strata has no second slot: the prewarm is an ordinary max_tokens=1 request that leaves the next epoch parked, a
prewarm still reading when main wants in is cancelled, and after the promotion the dead epoch is dropped.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import run_agent
from agent import strata_cache
from agent.strata_cache import CANCELLED, DONE, FAILED, cancellable_post, drop_parked

_RealAIAgent = run_agent.AIAgent


# -- a local HTTP server standing in for Strata ---------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    delay = 0.0
    status = 200
    reply = {"ok": True}
    seen = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        type(self).seen.append((self.path, json.loads(self.rfile.read(n) or b"{}")))
        time.sleep(type(self).delay)
        raw = json.dumps(type(self).reply).encode()
        try:
            self.send_response(type(self).status)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except OSError:
            pass                                  # the client closed the connection: the point of the cancel test

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    _Handler.delay, _Handler.status, _Handler.reply, _Handler.seen = 0.0, 200, {"ok": True}, []
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


class TestCancellablePost:
    def test_a_finished_request_is_done(self, server):
        assert cancellable_post(server + "/v1/chat/completions", {"max_tokens": 1}, lambda: False) == DONE
        assert _Handler.seen[0][0] == "/v1/chat/completions" and _Handler.seen[0][1] == {"max_tokens": 1}

    def test_main_arriving_cancels_a_prewarm_that_is_still_reading(self, server):
        _Handler.delay = 6.0                      # a long prefill
        flip = threading.Timer(0.4, lambda: flags.append(True))
        flags = []
        flip.start()
        t0 = time.monotonic()
        out = cancellable_post(server + "/x", {}, lambda: bool(flags), poll=0.1)
        assert out == CANCELLED
        assert time.monotonic() - t0 < 3.0, "the cancel must not wait out the prefill"

    def test_an_error_status_or_a_dead_server_is_failed(self, server):
        _Handler.status = 500
        assert cancellable_post(server + "/x", {}, lambda: False) == FAILED
        assert cancellable_post("http://127.0.0.1:9/x", {}, lambda: False, timeout=2) == FAILED


class TestDropParked:
    def test_posts_to_the_cache_endpoint_and_returns_the_answer(self, server):
        _Handler.reply = {"ok": True, "dropped": 1, "released_mib": 2038}
        assert drop_parked(server + "/v1") == {"ok": True, "dropped": 1, "released_mib": 2038}
        assert _Handler.seen[-1][0] == "/v1/cache/drop_parked"

    def test_a_refusal_or_a_remote_backend_is_none(self, server):
        _Handler.status = 409
        assert drop_parked(server + "/v1") is None
        assert drop_parked("https://api.example.com/v1") is None


# -- the agent side ---------------------------------------------------------------------------------------------

def _agent(**over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.base_url = "http://127.0.0.1:8080/v1"
    a._hot_swap_in_progress = False
    a._hot_swap_ready = None
    a._compaction_generation = 0
    a._hot_swap_prefill = True
    a._pinned_id_slot = 1
    a._slot_count_cache = 1
    a._cached_system_prompt = "sys"
    a.ephemeral_system_prompt = None
    a._compaction_engine = "summary"
    for k, v in over.items():
        setattr(a, k, v)
    return a


class _Compressor:
    threshold_tokens = 1000

    def compress(self, messages, current_tokens=None):
        return [{"role": "user", "content": "SUMMARY"}]


def _single(monkeypatch, value=True):
    monkeypatch.setattr("agent.backend_kind.is_single_sequence", lambda base_url, timeout=1.5: value)


class TestPrewarmSingleSequence:
    def _stub_rendering(self, a):
        a._build_payload_messages = lambda *x, **k: ([{"role": "user", "content": "x"}], None)
        a._normalise_system_messages = lambda m: m
        a._sanitize_api_messages = lambda m: m
        a._build_api_kwargs = lambda m: {"model": "m", "messages": m, "stream": True, "max_tokens": 4000,
                                         "extra_body": {"chat_template_kwargs": {"x": 1}}, "timeout": 30}

    def test_prime_takes_the_single_sequence_path_without_an_id_slot(self, monkeypatch):
        _single(monkeypatch)
        a = _agent()
        self._stub_rendering(a)
        sent = {}

        def fake_post(url, body, should_cancel, **kw):
            sent.update(url=url, body=body, cancel=should_cancel)
            return DONE
        monkeypatch.setattr(strata_cache, "cancellable_post", fake_post)
        assert a._prime_slot_with_messages(0, [{"role": "user", "content": "hi"}], "sys") is True
        assert sent["url"] == "http://127.0.0.1:8080/v1/chat/completions"
        body = sent["body"]
        assert body["max_tokens"] == 1 and body["stream"] is False
        assert "id_slot" not in body and "extra_body" not in body and "timeout" not in body
        assert body["chat_template_kwargs"] == {"x": 1}, "extra_body fields are flattened into the request"
        assert body["messages"][0] == {"role": "system", "content": "sys"}

    def test_main_activity_cancels_it(self, monkeypatch):
        _single(monkeypatch)
        a = _agent()
        self._stub_rendering(a)
        from agent.sidekick_queue import sidekick_gate
        seen = {}

        def fake_post(url, body, should_cancel, **kw):
            seen["idle"] = should_cancel()
            sidekick_gate.main_begin()
            try:
                seen["busy"] = should_cancel()
            finally:
                sidekick_gate.main_end()
            return CANCELLED
        monkeypatch.setattr(strata_cache, "cancellable_post", fake_post)
        assert a._prime_slot_with_messages(0, [{"role": "user", "content": "hi"}], "sys") is False
        assert seen == {"idle": False, "busy": True}

    def test_a_multi_slot_server_still_uses_the_slot_path(self, monkeypatch):
        _single(monkeypatch, False)
        a = _agent(_slot_count_cache=2)
        self._stub_rendering(a)
        monkeypatch.setattr(_RealAIAgent, "_prewarm_single_sequence",
                            lambda self, kw: pytest.fail("the slot path must not be bypassed"))
        a._ensure_primary_openai_client = lambda reason="": type("C", (), {"chat": type("H", (), {
            "completions": type("K", (), {"create": staticmethod(lambda **kw: kw)})})})()
        assert a._prime_slot_with_messages(0, [{"role": "user", "content": "hi"}], "sys") is True


class TestPrepAndApplyOnSingleSequence:
    def test_prep_records_a_prewarmed_copy_not_a_slot_and_does_not_reserve(self, monkeypatch):
        _single(monkeypatch)
        a = _agent(context_compressor=_Compressor())
        monkeypatch.setattr(_RealAIAgent, "_prime_slot_with_messages", lambda self, slot, c, s: True)
        from agent.sidekick_queue import sidekick_gate
        sidekick_gate.release_reservation()
        a._run_hot_swap_prep([{"role": "user", "content": f"m{i}"} for i in range(6)], "sys", 900, "t", 0)
        ready = a._hot_swap_ready
        assert ready["slot"] is None and ready["prewarmed_single"] is True
        assert not sidekick_gate.reserved(), "a one-conversation engine must not stall aux calls for 15 minutes"

    def test_apply_leaves_the_pinned_slot_alone_and_schedules_the_drop(self):
        a = _agent()
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "SUMMARY"}], "snapshot_len": 1,
                             "generation": 0, "slot": None, "prewarmed_single": True}
        merged = a._apply_pending_hot_swap_if_ready([{"role": "user", "content": "m0"}])
        assert [m["content"] for m in merged] == ["SUMMARY"]
        assert a._pinned_id_slot == 1
        assert a._drop_parked_pending is True

    def test_a_fork_swap_does_not_schedule_a_drop(self):
        a = _agent(_slot_count_cache=2)
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "S"}], "snapshot_len": 1,
                             "generation": 0, "slot": None}
        a._apply_pending_hot_swap_if_ready([{"role": "user", "content": "m0"}])
        assert not getattr(a, "_drop_parked_pending", False)

    def test_the_drop_goes_out_once_after_the_promoted_request(self, monkeypatch):
        calls = []
        done = threading.Event()
        monkeypatch.setattr(strata_cache, "drop_parked", lambda base: calls.append(base) or done.set() or {"ok": True})
        a = _agent()
        a._flush_pending_drop_parked()                         # nothing pending: no call
        a._drop_parked_pending = True
        a._flush_pending_drop_parked()
        assert done.wait(2.0)
        a._flush_pending_drop_parked()                         # already sent: no second call
        time.sleep(0.1)
        assert calls == ["http://127.0.0.1:8080/v1"]
        assert a._drop_parked_pending is False
