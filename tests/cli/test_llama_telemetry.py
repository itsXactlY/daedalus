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

    def test_idle_falls_back_to_session_average(self):
        label = DaedalusCLI._format_llama_telemetry_label(
            {"busy": False, "avg_gen_tps": 31.2, "kv_used": 0, "kv_ctx": 81920}
        )
        assert "~31 tok/s" in label

    def test_dflash_only_shown_once_metrics_available(self):
        without = DaedalusCLI._format_llama_telemetry_label(
            {"busy": True, "live_tps": 10.0, "kv_used": 1, "kv_ctx": 100}
        )
        assert "dflash" not in without

        with_dflash = DaedalusCLI._format_llama_telemetry_label(
            {"busy": True, "live_tps": 10.0, "kv_used": 1, "kv_ctx": 100, "dflash_pct": 71.4}
        )
        assert "dflash 71%" in with_dflash

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
