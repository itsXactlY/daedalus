"""The local KV ceiling only counts while this box serves the turn.

compression.max_tokens / fast_layer_tokens exist because the local llama-server
swaps well before the 256K window it advertises is full. Against a remote
provider that is not a limit at all: the window is real and mostly empty, so the
harness must trigger off the percentage -- except when compacting already
spares tokens either way.
"""

from unittest.mock import patch

from agent.context_compressor import ContextCompressor


CTX = 100_000
CEILING = 32_000


def _make(**over):
    kw = dict(
        model="test/model",
        threshold_percent=0.85,
        protect_first_n=2,
        protect_last_n=2,
        max_tokens=CEILING,
        quiet_mode=True,
    )
    kw.update(over)
    with patch("agent.context_compressor.get_model_context_length", return_value=CTX):
        return ContextCompressor(**kw)


def _local(**over):
    return _make(base_url="http://127.0.0.1:8080/v1", provider="local", **over)


def _remote(**over):
    return _make(base_url="https://api.openai.com/v1", provider="openai", **over)


class TestWhereTheCeilingCounts:
    def test_local_keeps_the_ceiling_as_the_trigger(self):
        c = _local()
        assert c._ceiling_applies() is True
        assert c.threshold_tokens == CEILING
        assert c.should_compress(CEILING) is True
        assert c.should_compress(CEILING - 1) is False

    def test_remote_ignores_the_ceiling_and_uses_the_real_window(self):
        c = _remote()
        assert c._ceiling_applies() is False
        assert c.threshold_tokens == int(CTX * 0.85)
        assert c.should_compress(CEILING) is False
        assert c.should_compress(c.threshold_tokens) is True

    def test_no_base_url_is_treated_as_local(self):
        c = _make()
        assert c._ceiling_applies() is True
        assert c.threshold_tokens == CEILING

    def test_local_provider_name_wins_over_a_foreign_url(self):
        c = _make(base_url="http://doctor.internal.lan:9090/v1", provider="llamacpp")
        assert c._ceiling_applies() is True
        assert c.threshold_tokens == CEILING

    def test_no_ceiling_configured_means_nothing_to_scope(self):
        c = _remote(max_tokens=None)
        assert c.threshold_tokens == int(CTX * 0.85)
        assert c.should_compress(60_000) is False


class TestRemoteSparingTrigger:
    """Early compaction off-box, only where it is plainly the cheaper move."""

    def test_fires_once_the_saving_is_clear(self):
        c = _remote()
        fired = c._sparing_trigger(50_000)
        assert fired > 0
        assert c.should_compress(50_000) is True
        assert c.should_compress(47_999) is False  # 1.5x the local line, minus one
        assert c.should_compress(48_000) is True   # exactly 1.5x the local line

    def test_stays_quiet_just_above_the_local_line(self):
        c = _remote()
        # Past the line a local session draws, but not yet 1.5x past it: the
        # provider's window still has room and the saving is not clear.
        assert c._sparing_trigger(CEILING) == 0
        assert c._sparing_trigger(47_000) == 0
        assert c.should_compress(CEILING) is False
        assert c.should_compress(47_000) is False

    def test_stays_quiet_when_a_compaction_would_not_halve_it(self):
        # Huge tail budget against a small real window: the summary would be
        # nearly as big as what it replaces, so hold the real context instead.
        c = _remote(summary_target_ratio=0.9)
        assert c._sparing_trigger(84_000) == 0
        assert c.should_compress(84_000) is False
        assert c.should_compress(c.threshold_tokens) is True

    def test_never_fires_for_a_local_session(self):
        c = _local()
        assert c._sparing_trigger(90_000) == 0
        assert c.should_compress(30_000) is False  # under the ceiling: nothing fires
        assert c.should_compress(90_000) is True   # the ceiling itself still decides

    def test_silent_when_the_real_trigger_is_closer(self):
        # A ceiling above the percentage threshold is not a ceiling at all.
        c = _make(
            base_url="https://api.anthropic.com",
            provider="anthropic",
            max_tokens=90_000,
        )
        assert c.threshold_tokens == int(CTX * 0.85)
        assert c._sparing_trigger(60_000) == 0

    def test_preflight_agrees_with_the_real_estimate(self):
        c = _remote()
        big = [{"role": "user", "content": "x" * 400_000}]
        assert c.should_compress_preflight(big) is True
        assert c.should_compress_preflight([{"role": "user", "content": "short"}]) is False


class TestWindowSizingFollowsTheVerdict:
    def test_tail_budget_scales_with_the_real_window_off_box(self):
        local, remote = _local(), _remote()
        assert remote.tail_token_budget > local.tail_token_budget
        assert remote.tail_token_budget == int(remote.threshold_tokens * 0.20)


class TestThresholdRederivation:
    """Model swap, fallback and a context step-down all re-derive the trigger.

    They must go through the verdict, not straight to the percentage: a raw
    percent silently un-caps the local fast-layer ceiling.
    """

    def test_rederivation_keeps_the_ceiling_locally_and_drops_it_off_box(self):
        local, remote = _local(), _remote()
        assert local._effective_threshold(CTX) == CEILING
        assert remote._effective_threshold(CTX) == int(CTX * 0.85)

    def test_redetected_window_still_honours_the_verdict(self):
        # maybe_refresh_context_length() and the API step-down both re-probe.
        local = _local()
        local._context_probed = True
        local._ctx_refreshed_at -= local.CTX_REFRESH_INTERVAL + 1
        with patch("agent.context_compressor.get_model_context_length", return_value=262_144):
            assert local.maybe_refresh_context_length(allow_post_probe=True) is True
        assert local.context_length == 262_144
        assert local.threshold_tokens == CEILING

    def test_no_site_re_derives_the_trigger_from_a_raw_percentage(self):
        import re
        from pathlib import Path

        src = Path(__file__).resolve().parents[2] / "run_agent.py"
        text = src.read_text(encoding="utf-8")
        offenders = re.findall(
            r"threshold_tokens\s*=\s*int\([^)]*threshold_percent", text
        )
        assert offenders == [], f"raw-percent threshold re-derivation: {offenders}"
