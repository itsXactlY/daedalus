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
        messages = [
            {"role": "user", "content": "[summary]\n\nrewritten hello"},
        ]
        assert reanchor_current_turn_user_idx(messages, "hello") == 0

    def test_fallback_skips_synthetic_todo_snapshot_row(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "ack"},
            {"role": "user", "content": "[handoff summary...]\n\nplease continue with wave two"},
            {"role": "user", "content": "[TODO SNAPSHOT]\n- item 1", "display_kind": "hidden"},
        ]
        idx = reanchor_current_turn_user_idx(messages, "please continue with wave two")
        assert idx == 2, "fallback must anchor on the real turn, not the tagged synthetic row"

    def test_fallback_returns_negative_one_if_only_synthetic_rows_survive(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "[TODO SNAPSHOT]\n- item 1", "display_kind": "hidden"},
        ]
        assert reanchor_current_turn_user_idx(messages, "no longer present anywhere") == -1

    def test_exact_match_on_tagged_row_still_returns_it(self):
        messages = [
            {"role": "user", "content": "same text", "display_kind": "hidden"},
        ]
        assert reanchor_current_turn_user_idx(messages, "same text") == 0
