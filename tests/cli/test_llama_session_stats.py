"""Whole-session llama-server statistics from its cumulative counters."""

import datetime

import pytest

from cli import DaedalusCLI
from daedalus_cli.llama_session_stats import COUNTERS, SessionCounters, parse_metrics

METRICS_TEXT = """\
# HELP llamacpp:prompt_tokens_total Number of prompt tokens processed, excluding cached tokens
# TYPE llamacpp:prompt_tokens_total counter
llamacpp:prompt_tokens_total 1000
llamacpp:prompt_tokens_cached_total 9000
llamacpp:prompt_seconds_total 2.5
llamacpp:tokens_predicted_total 600
llamacpp:tokens_predicted_seconds_total 12
llamacpp:spec_decode_num_draft_tokens_total 400
llamacpp:spec_decode_num_accepted_tokens_total 300
llamacpp:predicted_tokens_seconds 55.1
llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position="0"} 120
"""


def _m(**kw):
    base = {k: 0.0 for k in COUNTERS}
    base.update({k: float(v) for k, v in kw.items()})
    return base


def test_parse_metrics_reads_counters_and_skips_labelled_series():
    m = parse_metrics(METRICS_TEXT)
    assert m["prompt_tokens_cached_total"] == 9000
    assert m["tokens_predicted_seconds_total"] == 12
    assert not any("per_pos" in k for k in m)


def test_first_read_is_the_baseline_not_session_work():
    s = SessionCounters()
    s.update(_m(tokens_predicted_total=5000, tokens_predicted_seconds_total=100))
    assert s.summary()["gen_tokens"] == 0
    assert s.summary()["gen_tps"] is None


def test_session_averages_are_exact_ratios_of_counter_deltas():
    s = SessionCounters()
    s.update(_m(tokens_predicted_total=5000, tokens_predicted_seconds_total=100,
                prompt_tokens_total=2000, prompt_seconds_total=4,
                prompt_tokens_cached_total=10000))
    s.update(_m(tokens_predicted_total=5600, tokens_predicted_seconds_total=112,
                prompt_tokens_total=3000, prompt_seconds_total=6.5,
                prompt_tokens_cached_total=19000,
                spec_decode_num_draft_tokens_total=400,
                spec_decode_num_accepted_tokens_total=300))
    out = s.summary()
    assert out["gen_tokens"] == 600
    assert out["gen_tps"] == pytest.approx(50.0)
    assert out["prefill_tps"] == pytest.approx(400.0)
    assert out["cache_hit_pct"] == pytest.approx(90.0)
    assert out["draft_pct"] == pytest.approx(75.0)


def test_a_server_restart_keeps_what_the_session_had_accumulated():
    s = SessionCounters()
    s.update(_m(tokens_predicted_total=1000, tokens_predicted_seconds_total=20))
    s.update(_m(tokens_predicted_total=1500, tokens_predicted_seconds_total=30))   # +500 in 10 s
    s.update(_m(tokens_predicted_total=200, tokens_predicted_seconds_total=5))     # restarted
    s.update(_m(tokens_predicted_total=800, tokens_predicted_seconds_total=15))    # +600 more
    out = s.summary()
    assert out["gen_tokens"] == 500 + 800
    assert out["gen_tps"] == pytest.approx(1300 / 25)
    assert out["restarts"] == 1


def test_kv_now_average_and_peak():
    s = SessionCounters()
    for used in (1000, 3000, 2000):
        s.observe_kv(used, 10000)
    out = s.summary()
    assert out["kv_now_pct"] == pytest.approx(20.0)
    assert out["kv_avg_pct"] == pytest.approx(20.0)
    assert out["kv_peak_pct"] == pytest.approx(30.0)


def test_kv_is_unmeasured_until_a_busy_sample():
    out = SessionCounters().summary()
    assert out["kv_peak_pct"] is None and out["kv_avg_pct"] is None


def test_a_new_session_gets_fresh_counters_and_verbose_toggling_does_not():
    cli_obj = DaedalusCLI.__new__(DaedalusCLI)
    cli_obj.session_start = datetime.datetime(2026, 9, 16, 12, 0)
    first = cli_obj._llama_session_stats()
    first.update(_m(tokens_predicted_total=10))
    assert cli_obj._llama_session_stats() is first
    cli_obj.session_start = datetime.datetime(2026, 9, 16, 13, 0)
    assert cli_obj._llama_session_stats() is not first
