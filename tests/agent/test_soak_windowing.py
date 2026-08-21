"""Tests for the soak-architecture lean-context windowing.

Covers AIAgent._window_messages_for_api — the "carry nothing, let mazemaker
carry it" half of the operator's soak vision. The full transcript is written
to the pod by the provider's sync_turn; the API payload carries only the
current turn + a small recency window + any in-flight tool results.
"""

import pytest

from run_agent import AIAgent

# staticmethod — class access gives the plain callable
_window = AIAgent._window_messages_for_api


def _turns(n: int, with_tool_tail: bool = False):
    """Build n user/assistant turns. Optionally append a tool-call tail."""
    msgs = []
    for i in range(n):
        msgs.append({"role": "user", "content": f"u{i}"})
        msgs.append({"role": "assistant", "content": f"a{i}"})
    if with_tool_tail:
        msgs.append({"role": "assistant", "content": "resp", "tool_calls": [{"id": "t1"}]})
        msgs.append({"role": "tool", "content": "result"})
    return msgs


class TestWindowHelper:
    def test_windows_to_recent_plus_current(self):
        msgs = _turns(10)  # 20 messages (10 user + 10 assistant)
        cur = len(msgs) - 1  # index 19 = a9, the last assistant of the current turn
        w = _window(msgs, current_turn_user_idx=cur, window_turns=3)
        # window_turns*2 prior messages + the current turn's tail = 7
        assert len(w) == 7
        assert w[-1]["content"] == "a9"  # current turn's latest message kept
        contents = [m["content"] for m in w]
        assert "u0" not in contents
        assert "u7" in contents  # recent prior turn survives

    def test_full_soak_keeps_only_current_turn(self):
        """window_turns=0 is full soak: current turn only, history lives in pod."""
        msgs = _turns(10)  # 20 messages
        w = _window(msgs, current_turn_user_idx=len(msgs) - 1, window_turns=0)
        assert len(w) == 1
        assert w[0]["content"] == "a9"  # only the current turn's latest message

    def test_soak_off_returns_full(self):
        """window_turns=-1 = soak disabled: full carry (default)."""
        msgs = _turns(10)
        w = _window(msgs, current_turn_user_idx=len(msgs) - 1, window_turns=-1)
        assert len(w) == len(msgs)

    def test_small_history_unchanged(self):
        msgs = _turns(2)  # 4 messages
        w = _window(msgs, current_turn_user_idx=len(msgs) - 1, window_turns=3)
        assert len(w) == len(msgs)

    def test_keeps_inflight_tool_results(self):
        msgs = _turns(5, with_tool_tail=True)
        cur = 9  # the last user message before the tool tail
        w = _window(msgs, current_turn_user_idx=cur, window_turns=2)
        roles = [m["role"] for m in w]
        assert "tool" in roles  # in-flight tool result survives the window
        assert w[-1]["role"] == "tool"

    def test_does_not_mutate_input(self):
        msgs = _turns(10)
        before = [dict(m) for m in msgs]
        _window(msgs, current_turn_user_idx=len(msgs) - 1, window_turns=3)
        assert msgs == before

    def test_drops_leading_system_message(self):
        msgs = [{"role": "system", "content": "s"}] + _turns(10)
        cur = len(msgs) - 1
        w = _window(msgs, current_turn_user_idx=cur, window_turns=3)
        assert w[0]["role"] != "system"


class TestRemapCurrentTurnIndex:
    """Regression: compression replaces `messages` with a shorter list, but the
    current-turn index is captured against the OLD list. A stale index >= len
    produced an empty windowed view — the model saw no user turn and answered
    "Keine Nachricht empfangen" (the 2026-08-10 resumed-session amnesia)."""

    # staticmethod — access directly (class attribute aliasing would bind self)
    _remap = staticmethod(AIAgent._remap_current_turn_index)

    def test_index_in_range_unchanged(self):
        msgs = [{"role": "user", "content": "u0"}, {"role": "assistant", "content": "a0"}]
        assert self._remap(msgs, 0, "u0") == 0

    def test_stale_index_remapped_by_content(self):
        # Simulates: 637 messages compressed to 5, current-turn user msg kept
        # in the protected tail at index 3; stale index was 636.
        msgs = [
            {"role": "system", "content": "compressed summary"},
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "what did we work on?"},  # the current turn
            {"role": "system", "content": "[archived to mazemaker]"},
        ]
        assert self._remap(msgs, 636, "what did we work on?") == 3

    def test_stale_index_finds_last_match_when_tail_suffixed(self):
        # Compression appends a system note / todo snapshot AFTER the current
        # user turn, so the current message is not the last element — the
        # backward scan must still find it.
        msgs = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "status"},
            {"role": "user", "content": "todo: []"},
        ]
        assert self._remap(msgs, 999, "status") == 2

    def test_no_match_falls_back_to_original(self):
        msgs = [{"role": "user", "content": "other"}]
        assert self._remap(msgs, 500, "not present") == 500

    def test_window_view_not_empty_after_remap(self):
        # The end-to-end symptom: after remap, windowing must still carry the
        # current user turn.
        msgs = [
            {"role": "system", "content": "summary"},
            {"role": "user", "content": "u7"},
            {"role": "assistant", "content": "a7"},
            {"role": "user", "content": "what did we work on?"},
        ]
        repaired = self._remap(msgs, 900, "what did we work on?")
        w = AIAgent._window_messages_for_api(
            msgs, current_turn_user_idx=repaired, window_turns=3
        )
        assert any(m.get("content") == "what did we work on?" for m in w)
        assert len(w) > 0
