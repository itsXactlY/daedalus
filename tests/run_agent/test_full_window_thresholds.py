"""Using the full window: the limits that stack on it, and the one that used to be a constant.

A 65,536-token window with threshold 0.5, fast_layer_tokens 56128 and a fixed 0.85 inline ceiling rebased at 32,768,
started the prewarm at 29k, kept a 6.5k tail and, if the threshold was simply raised, turned every crossing into an
inline rebase because it already sat above the 55,705 ceiling.
"""

import pytest

from agent.kv_watermarks import Watermarks
from run_agent import hot_swap_hard_ratio_from


class TestHardRatioIsConfigurable:
    def test_default_is_the_old_constant(self):
        assert hot_swap_hard_ratio_from({}) == 0.85
        assert hot_swap_hard_ratio_from(None) == 0.85

    def test_a_configured_value_is_used(self):
        assert hot_swap_hard_ratio_from({"hot_swap_hard_ratio": 0.97}) == 0.97

    @pytest.mark.parametrize("bad", [0.2, 0.5, 1.0, 1.5, -1, "x", None])
    def test_a_value_outside_the_sane_range_falls_back(self, bad):
        assert hot_swap_hard_ratio_from({"hot_swap_hard_ratio": bad}) == 0.85


class TestTheFullWindowNumbers:
    """The chain for the config this machine runs, computed the way ContextCompressor/_setup_fast_layer_watermarks do."""

    CTX = 65536

    def chain(self, threshold, max_tokens, fast, wm, hard_ratio):
        w = Watermarks(fast_layer_tokens=fast, **wm)
        eff_max = w.hard_tokens
        trigger = max(1, min(int(self.CTX * threshold), eff_max))
        return {"trigger": trigger, "prep_at": int(trigger * w.high_ratio_of_hard),
                "inline_ceiling": int(self.CTX * hard_ratio)}

    def test_the_old_config_rebased_at_half_the_window(self):
        c = self.chain(0.5, 60000, 56128, {"low": 0.6, "high": 0.8, "hard": 0.9}, 0.85)
        assert c == {"trigger": 32768, "prep_at": 29127, "inline_ceiling": 55705}

    def test_raising_only_the_threshold_would_disable_the_hot_swap(self):
        c = self.chain(0.92, 64000, 65536, {"low": 0.7, "high": 0.88, "hard": 0.95}, 0.85)
        assert c["trigger"] > c["inline_ceiling"], "every crossing would already be past the ceiling: inline rebase"

    def test_the_full_window_config_keeps_prep_below_trigger_below_ceiling(self):
        c = self.chain(0.92, 64000, 65536, {"low": 0.7, "high": 0.88, "hard": 0.95}, 0.97)
        assert c["prep_at"] < c["trigger"] < c["inline_ceiling"] < self.CTX
        assert c["trigger"] == 60293 and c["inline_ceiling"] == 63569
        assert c["trigger"] - c["prep_at"] >= 4000, "room for a few turns while the next epoch is prewarmed"
