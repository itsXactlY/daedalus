"""Verbose-mode llama-server telemetry in the status bar.

/verbose is supposed to turn this on automatically and off just as cleanly --
the poller must never run (or keep running) when verbose is off or the
backend isn't a local llama-server, and the render path must never touch the
network directly (see _ensure_llama_telemetry_poller's own docstring for why:
a blocking call from prompt_toolkit's bottom-toolbar render path would make
typing feel laggy the moment the server is slow).
"""

import time

from cli import DaedalusCLI


def _make_cli(verbose=False, base_url="http://127.0.0.1:8080/v1"):
    cli_obj = DaedalusCLI.__new__(DaedalusCLI)
    cli_obj.verbose = verbose
    cli_obj.base_url = base_url
    return cli_obj


class TestFormatLabel:
    def test_empty_when_no_telemetry_yet(self):
        assert DaedalusCLI._format_llama_telemetry_label(None) == ""
        assert DaedalusCLI._format_llama_telemetry_label({}) == ""

    def test_busy_slot_shows_live_tps(self):
        label = DaedalusCLI._format_llama_telemetry_label(
            {"busy": True, "live_tps": 27.9, "kv_used": 32000, "kv_ctx": 81920}
        )
        assert "28 tok/s" in label
        assert "kv 39%" in label

    def test_idle_shows_the_whole_session_average(self):
        label = DaedalusCLI._format_llama_telemetry_label(
            {"busy": False, "kv_used": 0, "kv_ctx": 81920, "session": {"gen_tps": 31.2}}
        )
        assert "⌀31 tok/s" in label

    def test_busy_shows_live_and_session_average_together(self):
        label = DaedalusCLI._format_llama_telemetry_label(
            {"busy": True, "live_tps": 58.4, "kv_used": 8192, "kv_ctx": 81920,
             "session": {"gen_tps": 49.6, "kv_avg_pct": 7.2, "kv_peak_pct": 31.0,
                         "cache_hit_pct": 87.4, "draft_pct": 71.4}}
        )
        assert "58 ⌀50 tok/s" in label
        assert "kv 10% ⌀7% ▲31%" in label
        assert "cache 87%" in label
        assert "draft 71%" in label

    def test_session_stats_only_shown_once_measured(self):
        label = DaedalusCLI._format_llama_telemetry_label(
            {"busy": True, "live_tps": 10.0, "kv_used": 1, "kv_ctx": 100}
        )
        assert "⌀" not in label and "cache" not in label and "draft" not in label

    def test_zero_ctx_does_not_divide_by_zero(self):
        label = DaedalusCLI._format_llama_telemetry_label(
            {"busy": True, "live_tps": 5.0, "kv_used": 0, "kv_ctx": 0}
        )
        assert "kv" not in label


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

    def test_does_not_start_when_not_verbose(self, monkeypatch):
        cli_obj = _make_cli(verbose=False, base_url="http://127.0.0.1:8080/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)

        assert started == []
        assert getattr(cli_obj, "_llama_telemetry_thread", None) is None

    def test_does_not_start_for_a_remote_backend(self, monkeypatch):
        cli_obj = _make_cli(verbose=True, base_url="https://api.example.com/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)

        assert started == []

    def test_stops_when_verbose_is_toggled_off(self, monkeypatch):
        cli_obj = _make_cli(verbose=True, base_url="http://127.0.0.1:8080/v1")
        started = []
        self._stub_loop(monkeypatch, cli_obj, started)

        cli_obj._ensure_llama_telemetry_poller()
        time.sleep(0.05)
        thread = cli_obj._llama_telemetry_thread
        assert thread.is_alive()

        cli_obj.verbose = False
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
