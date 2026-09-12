"""The throughput watchdog: restart the main server when generation collapses.

The whole point of restarting rather than tolerating it is that a cold KV
cache is cheap *here* -- daedalus keeps its transcript in mazemaker and sends
only a window, so the next prompt is small. That makes the watchdog viable,
but it also means a spurious restart is still a real cost, so the tests below
are mostly about NOT restarting: idle must not look slow, a failed scrape must
not look slow, and a busy machine must not produce a restart loop.
"""

import daedalus_cli.stack as stack


class TestSampleDecodeRate:
    def test_rate_is_a_window_not_a_lifetime_average(self):
        prev = {"tokens_predicted_total": 1000.0, "tokens_predicted_seconds_total": 10.0}
        cur = {"tokens_predicted_total": 1100.0, "tokens_predicted_seconds_total": 20.0}
        assert stack.sample_decode_rate(prev, cur) == 10.0   # 100 tokens / 10 s

    def test_idle_window_gives_no_verdict(self):
        """An idle server produces no tokens. Zero tokens in zero seconds is
        not 'slow' -- reading it as slow would restart a healthy idle server."""
        same = {"tokens_predicted_total": 500.0, "tokens_predicted_seconds_total": 25.0}
        assert stack.sample_decode_rate(same, dict(same)) is None

    def test_counter_going_backwards_gives_no_verdict(self):
        """The server restarted underneath us; counters reset to zero."""
        prev = {"tokens_predicted_total": 900.0, "tokens_predicted_seconds_total": 30.0}
        cur = {"tokens_predicted_total": 12.0, "tokens_predicted_seconds_total": 0.4}
        assert stack.sample_decode_rate(prev, cur) is None

    def test_missing_scrape_gives_no_verdict(self):
        assert stack.sample_decode_rate({}, {"tokens_predicted_total": 5.0}) is None
        assert stack.sample_decode_rate({"tokens_predicted_total": 5.0}, {}) is None

    def test_zero_elapsed_gives_no_verdict(self):
        prev = {"tokens_predicted_total": 100.0, "tokens_predicted_seconds_total": 5.0}
        cur = {"tokens_predicted_total": 150.0, "tokens_predicted_seconds_total": 5.0}
        assert stack.sample_decode_rate(prev, cur) is None


class TestReadMetrics:
    def _serve(self, monkeypatch, body):
        class _R:
            def read(self_inner):
                return body.encode()

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        monkeypatch.setattr(stack.urllib.request, "urlopen",
                            lambda url, timeout=None: _R())

    def test_parses_counters_and_strips_the_prefix(self, monkeypatch):
        self._serve(monkeypatch, (
            "# HELP llamacpp:tokens_predicted_total Number of generation tokens\n"
            "# TYPE llamacpp:tokens_predicted_total counter\n"
            "llamacpp:tokens_predicted_total 4242\n"
            "llamacpp:tokens_predicted_seconds_total 101.5\n"
        ))
        m = stack.read_metrics("127.0.0.1", 8080)
        assert m["tokens_predicted_total"] == 4242.0
        assert m["tokens_predicted_seconds_total"] == 101.5

    def test_labelled_series_are_skipped(self, monkeypatch):
        """spec_decode_num_accepted_tokens_per_pos_total is emitted per
        position; it is not a scalar and must not be parsed as one."""
        self._serve(monkeypatch, (
            'llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position="0"} 7\n'
            "llamacpp:tokens_predicted_total 10\n"
        ))
        m = stack.read_metrics("127.0.0.1", 8080)
        assert list(m) == ["tokens_predicted_total"]

    def test_an_unreachable_server_is_empty_not_an_exception(self, monkeypatch):
        def boom(url, timeout=None):
            raise OSError("connection refused")

        monkeypatch.setattr(stack.urllib.request, "urlopen", boom)
        assert stack.read_metrics("127.0.0.1", 8080) == {}

    def test_a_scrape_failure_never_reads_as_slow(self, monkeypatch):
        """read_metrics returning {} must flow into sample_decode_rate as
        'no verdict'. A watchdog that treats its own broken scrape as a slow
        server restarts a healthy one."""
        def boom(url, timeout=None):
            raise OSError("refused")

        monkeypatch.setattr(stack.urllib.request, "urlopen", boom)
        prev = {"tokens_predicted_total": 100.0, "tokens_predicted_seconds_total": 4.0}
        assert stack.sample_decode_rate(prev, stack.read_metrics("h", 1)) is None


class TestWiring:
    def test_watch_is_registered_with_its_knobs(self):
        import argparse
        p = argparse.ArgumentParser()
        stack.register_cli(p)
        args = p.parse_args(["watch", "--threshold", "15", "--trips", "2"])
        assert args.func is stack.cmd_watch
        assert args.threshold == 15.0
        assert args.trips == 2

    def test_defaults_are_conservative(self):
        import argparse
        p = argparse.ArgumentParser()
        stack.register_cli(p)
        args = p.parse_args(["watch"])
        assert args.threshold == 20.0
        assert args.trips >= 2, "a single slow window must not trigger a restart"
        assert args.cooldown >= 60, "too short a cooldown allows a restart loop"

    def test_it_refuses_to_watch_a_server_without_metrics(self, monkeypatch, capsys):
        """Without --metrics the endpoint 501s, every scrape is empty, and the
        watchdog would sit silently forever believing the server is idle."""
        monkeypatch.setattr(stack, "port_up", lambda h, p, timeout=2.0: True)
        monkeypatch.setattr(stack, "read_metrics", lambda h, p, timeout=3.0: {})
        import argparse
        p = argparse.ArgumentParser()
        stack.register_cli(p)
        assert stack.cmd_watch(p.parse_args(["watch"])) == 1
        assert "metrics" in capsys.readouterr().out.lower()

    def test_it_refuses_when_the_server_is_down(self, monkeypatch, capsys):
        monkeypatch.setattr(stack, "port_up", lambda h, p, timeout=2.0: False)
        import argparse
        p = argparse.ArgumentParser()
        stack.register_cli(p)
        assert stack.cmd_watch(p.parse_args(["watch"])) == 1
