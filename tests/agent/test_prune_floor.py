"""The spill floor tightens under pressure.

At a flat 2000 chars the spill only ever caught big results. Across four
ten-hour sessions, 480-590 aged tool results sat below that floor and were
carried uncut for the life of the run -- individually cheap, collectively
~77k-99k tokens each and the largest thing nothing was pruning.

Spilling costs the model a read_file round-trip, so the floor stays relaxed
while there is room and only tightens once the payload is actually large.
"""

import agent.context_compressor as cc

ContextCompressor = cc.ContextCompressor


def _compressor(threshold=100_000):
    c = ContextCompressor.__new__(ContextCompressor)
    c.threshold_tokens = threshold
    return c


class TestPruneFloor:
    def test_relaxed_while_there_is_room(self):
        c = _compressor()
        assert c._prune_floor(10_000) == cc._PRUNE_MIN_CHARS

    def test_tightens_at_the_pressure_ratio(self):
        c = _compressor()
        at = int(100_000 * cc._PRUNE_PRESSURE_RATIO)
        assert c._prune_floor(at) == cc._PRUNE_MIN_CHARS_UNDER_PRESSURE
        assert c._prune_floor(at + 1) == cc._PRUNE_MIN_CHARS_UNDER_PRESSURE

    def test_just_below_the_ratio_stays_relaxed(self):
        c = _compressor()
        assert c._prune_floor(int(100_000 * cc._PRUNE_PRESSURE_RATIO) - 1) == cc._PRUNE_MIN_CHARS

    def test_no_threshold_means_no_pressure_signal(self):
        """threshold_tokens == 0 is 'compaction disabled'. Without a scale
        there is nothing to be a fraction of, so do not guess -- stay relaxed
        rather than spilling aggressively on every session."""
        assert _compressor(threshold=0)._prune_floor(10**9) == cc._PRUNE_MIN_CHARS

    def test_the_tightened_floor_is_not_so_low_it_thrashes(self):
        """Below a few hundred chars the spill handle approaches the size of
        what it replaces, and every spill is a read_file the model may need."""
        assert cc._PRUNE_MIN_CHARS_UNDER_PRESSURE >= 400
        assert cc._PRUNE_MIN_CHARS_UNDER_PRESSURE < cc._PRUNE_MIN_CHARS


class TestItActuallyReachesThePruner:
    class _Archiver:
        def __init__(self):
            self.seen = []

        def __call__(self, tool_name, content, subject=""):
            self.seen.append(len(content))
            return f"[spilled {tool_name} -> /dev/shm/x{len(self.seen)}]"

    def _messages(self, size, n=40):
        out = []
        for i in range(n):
            out.append({"role": "assistant", "tool_calls": [
                {"id": f"c{i}", "function": {"name": "read_file", "arguments": "{}"}}]})
            out.append({"role": "tool", "tool_call_id": f"c{i}", "content": "x" * size})
        return out

    def _compressor_with_archiver(self, threshold=100_000):
        c = _compressor(threshold)
        c.live_window_messages = 12
        c.offloaded = []
        arch = self._Archiver()
        c.archiver = arch
        return c, arch

    def test_a_mid_sized_result_survives_when_there_is_room(self, monkeypatch):
        c, arch = self._compressor_with_archiver()
        monkeypatch.setattr(c, "_offload", lambda *a, **k: None)
        out, pruned = c.prune_stale_tool_results(self._messages(1200), current_tokens=1000)
        assert pruned == 0, "a 1200-char result must not spill while the window is empty"

    def test_the_same_result_spills_under_pressure(self, monkeypatch):
        c, arch = self._compressor_with_archiver()
        calls = []
        monkeypatch.setattr(c, "_offload",
                            lambda name, content, subject="": calls.append(len(content)) or "[spilled]")
        out, pruned = c.prune_stale_tool_results(self._messages(1200), current_tokens=90_000)
        assert pruned > 0, "at 90% of threshold a 1200-char aged result must spill"
        assert all(n == 1200 for n in calls)

    def test_tiny_results_never_spill_even_under_pressure(self, monkeypatch):
        c, arch = self._compressor_with_archiver()
        monkeypatch.setattr(c, "_offload", lambda *a, **k: "[spilled]")
        out, pruned = c.prune_stale_tool_results(self._messages(120), current_tokens=99_000)
        assert pruned == 0, "a 120-char result is smaller than its own spill handle"
