"""Tests for agent/turn_context.py's reanchor_current_turn_user_idx()."""

from agent.turn_context import reanchor_current_turn_user_idx


class TestReanchorCurrentTurnUserIdx:
    def test_exact_content_match_wins(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]
        assert reanchor_current_turn_user_idx(messages, "hello") == 1

    def test_empty_messages_returns_negative_one(self):
        assert reanchor_current_turn_user_idx([], "hello") == -1

    def test_no_user_message_returns_negative_one(self):
        messages = [{"role": "system", "content": "sys"}]
        assert reanchor_current_turn_user_idx(messages, "hello") == -1

    def test_fallback_to_last_user_message_when_no_exact_match(self):
        # merge-summary-into-tail rewrote the content, so no exact match --
        # fall back to the last (only) user message.
        messages = [
            {"role": "user", "content": "[summary]\n\nrewritten hello"},
        ]
        assert reanchor_current_turn_user_idx(messages, "hello") == 0

    def test_fallback_skips_synthetic_todo_snapshot_row(self):
        # Reproduces the bug found by today's audit: _compress_context()
        # (run_agent.py) can merge-summary-into-tail rewrite the current
        # turn's user message (so the exact-content match below misses it)
        # AND append a todo-snapshot user message after it in the same
        # pass. Without the display_kind guard, the fallback lands on the
        # synthetic snapshot instead of the real, rewritten turn.
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "ack"},
            {"role": "user", "content": "[handoff summary...]\n\nplease continue with wave two"},
            {"role": "user", "content": "[TODO SNAPSHOT]\n- item 1", "display_kind": "hidden"},
        ]
        idx = reanchor_current_turn_user_idx(messages, "please continue with wave two")
        assert idx == 2, "fallback must anchor on the real turn, not the tagged synthetic row"

    def test_fallback_returns_negative_one_if_only_synthetic_rows_survive(self):
        # If the ONLY user-role row left is synthetic and there's no exact
        # match, there is no genuine turn to anchor on -- -1 is correct
        # here, not the synthetic row's index. Every call site already
        # guards with `0 <= current_turn_user_idx < len(messages)` before
        # using the value (see turn_context.py ~1129/1202), so -1 is a
        # safe, already-supported "no anchor" signal, not a crash risk.
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "[TODO SNAPSHOT]\n- item 1", "display_kind": "hidden"},
        ]
        assert reanchor_current_turn_user_idx(messages, "no longer present anywhere") == -1

    def test_exact_match_on_tagged_row_still_returns_it(self):
        # The exact-content check runs before the display_kind guard --
        # if the caller's user_message somehow matches a tagged row's
        # content verbatim, that's still the strongest possible signal.
        messages = [
            {"role": "user", "content": "same text", "display_kind": "hidden"},
        ]
        assert reanchor_current_turn_user_idx(messages, "same text") == 0
