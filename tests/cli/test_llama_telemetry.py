"""llama-server telemetry in the status bar.

Since 2026-10-14 it runs for any local endpoint, /verbose or not: the stats
used to come only bundled with the debug log flood. The poller must never run
for a remote backend, and the render path must never touch the network (a
blocking call from prompt_toolkit's bottom-toolbar render path would make
typing lag the moment the server is slow).
"""

import time

from cli import DaedalusCLI
from daedalus_cli import status_bar as sb


def _make_cli(verbose=False, base_url="http://127.0.0.1:8080/v1"):
    cli_obj = DaedalusCLI.__new__(DaedalusCLI)
    cli_obj.verbose = verbose
    cli_obj.base_url = base_url
    return cli_obj


def _text(snapshot, width=400, main_slot=1):
    return "".join(t for _, t in sb.fit(sb.segments(snapshot, main_slot), width))


def _snap(**telemetry):
    return {"model_short": "m", "duration": "3m", "context_percent": 40, "context_length": 57344,
            "context_used_label": "22.9K", "context_total_label": "57.3K", "llama_telemetry": telemetry}


class TestSegments:
    def test_nothing_from_the_server_until_the_first_poll(self):
        text = _text(_snap())
        assert "gen" not in text and "draft" not in text and "slots" not in text

    def test_main_decoding_shows_live_and_session_rate(self):
        text = _text(_snap(slots=[{"id": 0, "phase": "decode", "tape": 900, "decode_tps": 80.0},
                                  {"id": 1, "phase": "decode", "tape": 30000, "decode_tps": 34.27}],
                           session={"gen_tps": 30.96}))
        assert "gen 34.3 ⌀31.0 t/s" in text, "live rate is main's, not the busiest slot's"

    def test_idle_shows_only_the_session_rate(self):
        text = _text(_snap(slots=[{"id": 1, "phase": "idle", "tape": 30000}], session={"gen_tps": 31.2}))
        assert "gen ⌀31.2 t/s" in text

    def test_prefill_shows_progress_and_rate(self):
        text = _text(_snap(slots=[{"id": 1, "phase": "prefill", "tape": 20480,
                                   "prompt_processed": 12345, "prefill_tps": 478.2}]))
        assert "prefill +12.3K 478 t/s" in text

    def test_slot_map_marks_main_and_tapes(self):
        text = _text(_snap(slots=[{"id": 0, "phase": "idle", "tape": 1115},
                                  {"id": 1, "phase": "decode", "tape": 32588},
                                  {"id": 2, "phase": "idle", "tape": 0}]))
        assert "slots ◇1.1K ◆32.6K ◇" in text

    def test_draft_cache_vram(self):
        text = _text(_snap(vram=(15202, 16380),
                           session={"draft_pct": 66.8, "draft_per_step": 3.69, "cache_hit_pct": 90.2}))
        assert "draft 67% ×3.7" in text
        assert "cache 90%" in text
        assert "vram 14.8/16.0G" in text

    def test_gauge_has_eighth_cell_resolution(self):
        assert sb.gauge(0) == "░" * 10
        assert sb.gauge(100) == "█" * 10
        assert sb.gauge(56) == "█████▋░░░░"
        assert all(len(sb.gauge(p)) == 10 for p in range(101))

    def test_fit_keeps_context_and_duration_and_never_overflows(self):
        snap = _snap(vram=(15202, 16380), session={"gen_tps": 31.0, "draft_pct": 60.0, "cache_hit_pct": 90.0},
                     slots=[{"id": 0, "phase": "idle", "tape": 1}, {"id": 1, "phase": "idle", "tape": 2}])
        for width in range(24, 220):
            frags = sb.fit(sb.segments(snap), width)
            text = "".join(t for _, t in frags)
            if width >= 30:
                assert sb.cell_width(text) <= width, width
                assert "40%" in text and "3m" in text, width  # "work 3m" or bare "3m"

    def test_optional_segments_shorten_before_any_is_dropped(self):
        snap = _snap(vram=(15202, 16380), session={"gen_tps": 31.0, "draft_pct": 60.0, "cache_hit_pct": 90.0},
                     slots=[{"id": 0, "phase": "idle", "tape": 1}, {"id": 1, "phase": "idle", "tape": 2}])
        full = sb.cell_width(_text(snap))
        text = _text(snap, width=full - 8)
        assert "vram 93%" in text and "slots" in text


class TestPollerLifecycle:
    def _stub_loop(self, monkeypatch, cli_obj, started):
        def fake_loop(self, stop_event):
            started.append(True)
            stop_event.wait(5.0)  # blocks until the test's stop_event.set()

        monkeypatch.setattr(DaedalusCLI, "_llama_telemetry_loop", fake_loop)

    def test_starts_when_verbose_and_local(self, monkeypatch):
        cli_obj = _make_cli(verbose=True, base_url="http://127.0.0.1:8080/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)

        assert started == [True]
        assert cli_obj._llama_telemetry_thread.is_alive()
        cli_obj._llama_telemetry_stop.set()

    def test_starts_for_a_local_backend_without_verbose(self, monkeypatch):
        cli_obj = _make_cli(verbose=False, base_url="http://127.0.0.1:8080/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)

        assert started == [True]
        cli_obj._llama_telemetry_stop.set()

    def test_does_not_start_for_a_remote_backend(self, monkeypatch):
        cli_obj = _make_cli(verbose=True, base_url="https://api.example.com/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)

        assert started == []

    def test_stops_when_the_backend_turns_remote(self, monkeypatch):
        cli_obj = _make_cli(base_url="http://127.0.0.1:8080/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)
        thread = cli_obj._llama_telemetry_thread
        assert thread.is_alive()

        cli_obj.base_url = "https://api.example.com/v1"
        cli_obj._ensure_llama_telemetry_poller()
        thread.join(timeout=1.0)

        assert not thread.is_alive()
        assert cli_obj._llama_telemetry_thread is None
        assert cli_obj._llama_telemetry is None

    def test_snapshot_never_blocks_on_network(self, monkeypatch):
        """The render path (_get_status_bar_snapshot) must only ever read the
        cache, never fetch -- this is the whole point of the poller."""
        cli_obj = _make_cli(verbose=True, base_url="http://127.0.0.1:8080/v1")

        def boom(*a, **k):
            raise AssertionError("snapshot must not fetch directly")

        monkeypatch.setattr(DaedalusCLI, "_fetch_llama_telemetry", staticmethod(boom))

        started = []
        self._stub_loop(monkeypatch, cli_obj, started)
        cli_obj.session_start = __import__("datetime").datetime.now()
        cli_obj.model = "test-model"
        cli_obj.agent = None

        snapshot = cli_obj._get_status_bar_snapshot()

        assert snapshot["llama_telemetry"] is None
        cli_obj._llama_telemetry_stop.set()


class TestFetchSlots:
    """Per-slot phase, tape and windowed rates from a real /slots answer."""

    @staticmethod
    def _serve(payloads):
        import http.server
        import json
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/slots":
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(payloads.pop(0) if len(payloads) > 1 else payloads[0]).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    @staticmethod
    def _slot(sid, busy, task, tape, decoded, processed):
        return {"id": sid, "n_ctx": 57344, "is_processing": busy, "id_task": task,
                "n_prompt_tokens": tape, "n_prompt_tokens_processed": processed,
                "next_token": [{"n_decoded": decoded}]}

    def test_phases_and_rate_over_the_window(self, monkeypatch):
        clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: clock[0])
        server = self._serve([
            [self._slot(0, True, 7, 500, 0, 300), self._slot(1, True, 9, 30000, 100, 0)],
            [self._slot(0, True, 7, 900, 0, 700), self._slot(1, True, 9, 30060, 160, 0)],
        ])
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}"
            last = {}
            DaedalusCLI._fetch_llama_telemetry(url, last)
            clock[0] += 2.0
            snap = DaedalusCLI._fetch_llama_telemetry(url, last)
        finally:
            server.shutdown()
            server.server_close()
        prefill, decode = snap["slots"]
        assert prefill["phase"] == "prefill" and prefill["prefill_tps"] == 200.0
        assert decode["phase"] == "decode" and decode["decode_tps"] == 30.0
        assert decode["tape"] == 30060

    def test_a_new_task_restarts_the_window(self, monkeypatch):
        clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: clock[0])
        server = self._serve([
            [self._slot(1, True, 9, 30000, 500, 0)],
            [self._slot(1, True, 10, 30010, 10, 0)],
        ])
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}"
            last = {}
            DaedalusCLI._fetch_llama_telemetry(url, last)
            clock[0] += 2.0
            snap = DaedalusCLI._fetch_llama_telemetry(url, last)
        finally:
            server.shutdown()
            server.server_close()
        assert "decode_tps" not in snap["slots"][0], "one sample of a new task is no rate"


class TestScrapeReportsWhy:
    """/usage used to drop its server section silently when /metrics failed.

    Observed: a llama-server shutting down answered 503, and /usage printed
    nothing about the local server at all. The scrape now says why.
    """

    @staticmethod
    def _serve(status, body=b""):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def _scrape(self, status, body=b""):
        server = self._serve(status, body)
        try:
            cli_obj = _make_cli(base_url=f"http://127.0.0.1:{server.server_address[1]}/v1")
            return cli_obj, cli_obj._scrape_llama_session(timeout=2.0)
        finally:
            server.shutdown()
            server.server_close()

    def test_503_means_loading_or_not_ready(self):
        assert "503" in self._scrape(503)[1]

    def test_501_means_started_without_metrics(self):
        assert "--metrics" in self._scrape(501)[1]

    def test_unreachable_names_the_error(self):
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cli_obj = _make_cli(base_url=f"http://127.0.0.1:{port}/v1")
        assert cli_obj._scrape_llama_session(timeout=2.0).startswith("nicht erreichbar")

    def test_success_returns_none_and_takes_the_baseline(self):
        body = b"llamacpp:tokens_predicted_total 10\nllamacpp:prompt_tokens_total 5\n"
        cli_obj, error = self._scrape(200, body)
        assert error is None
        assert cli_obj._llama_session_stats().has_baseline

    def test_usage_prints_the_section_with_the_reason(self, monkeypatch, capsys):
        import datetime
        import types
        cli_obj = _make_cli()
        cli_obj.session_start = datetime.datetime.now()
        cli_obj.conversation_history = []
        cli_obj.agent = types.SimpleNamespace(
            model="m", provider="custom", base_url=cli_obj.base_url,
            session_api_calls=1, session_input_tokens=0, session_output_tokens=0,
            session_cache_read_tokens=0, session_cache_write_tokens=0,
            session_total_tokens=0, context_compressor=None, model_ledger={},
            call_ledger=[], session_estimated_cost_usd=0.0,
            session_cost_status="included", session_cost_source="local",
        )
        monkeypatch.setattr(cli_obj, "_scrape_llama_session",
                            lambda timeout=1.5: "server lädt oder ist nicht bereit (503)")
        cli_obj._show_usage()
        out = capsys.readouterr().out
        assert "LOKALER SERVER" in out
        assert "nicht bereit (503)" in out


class TestStrataMetrics:
    """Strata answers /metrics with JSON; the bar used to show nothing on it."""

    PAYLOAD = {"engine": {"max_context": 65536},
               "live": {"state": "generating", "prompt_tokens": 33000, "generated": 400, "tok_s": 52.3},
               "totals": {"prompt_tokens": 100000, "reused": 95000, "output_tokens": 5000,
                          "prompt_ms": 10000.0, "decode_ms": 100000.0,
                          "drafts_offered": 4000, "drafts_accepted": 3000}}

    def test_counters_and_the_live_slot(self):
        from daedalus_cli.llama_session_stats import SessionCounters, strata_snapshot
        counters, slot = strata_snapshot(self.PAYLOAD)
        assert slot == {"id": 0, "phase": "decode", "n_ctx": 65536, "tape": 33400, "decode_tps": 52.3}
        stats = SessionCounters()
        stats.update({k: 0 for k in counters})
        stats.update(counters)
        s = stats.summary()
        assert s["gen_tps"] == 50.0 and s["prefill_tps"] == 500.0
        assert round(s["cache_hit_pct"]) == 95 and s["draft_pct"] == 75.0
        assert s["draft_per_step"] is None

    def test_not_strata_is_none(self):
        from daedalus_cli.llama_session_stats import strata_snapshot
        assert strata_snapshot({"foo": 1}) == (None, None)

    def test_the_single_slot_is_main(self):
        _, slot = __import__("daedalus_cli.llama_session_stats", fromlist=["x"]).strata_snapshot(self.PAYLOAD)
        text = _text(_snap(slots=[slot], session={"gen_tps": 50.0}), main_slot=1)
        assert "gen 52.3 ⌀50.0 t/s" in text
