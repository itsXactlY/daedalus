"""Tests for agent/context_compressor.py — compression logic, thresholds, truncation fallback."""

import pytest
from unittest.mock import patch, MagicMock

from agent.context_compressor import ContextCompressor, SUMMARY_PREFIX


@pytest.fixture()
def compressor():
    """Create a ContextCompressor with mocked dependencies."""
    with patch("agent.context_compressor.get_model_context_length", return_value=100000):
        c = ContextCompressor(
            model="test/model",
            threshold_percent=0.85,
            protect_first_n=2,
            protect_last_n=2,
            quiet_mode=True,
        )
        return c


class TestShouldCompress:
    def test_below_threshold(self, compressor):
        compressor.last_prompt_tokens = 50000
        assert compressor.should_compress() is False

    def test_above_threshold(self, compressor):
        compressor.last_prompt_tokens = 90000
        assert compressor.should_compress() is True

    def test_exact_threshold(self, compressor):
        compressor.last_prompt_tokens = 85000
        assert compressor.should_compress() is True

    def test_explicit_tokens(self, compressor):
        assert compressor.should_compress(prompt_tokens=90000) is True
        assert compressor.should_compress(prompt_tokens=50000) is False


class TestShouldCompressPreflight:
    def test_short_messages(self, compressor):
        msgs = [{"role": "user", "content": "short"}]
        assert compressor.should_compress_preflight(msgs) is False

    def test_long_messages(self, compressor):
        msgs = [{"role": "user", "content": "x" * 400000}]
        assert compressor.should_compress_preflight(msgs) is True


class TestUpdateFromResponse:
    def test_updates_fields(self, compressor):
        compressor.update_from_response({
            "prompt_tokens": 5000,
            "completion_tokens": 1000,
            "total_tokens": 6000,
        })
        assert compressor.last_prompt_tokens == 5000
        assert compressor.last_completion_tokens == 1000
        assert compressor.last_total_tokens == 6000

    def test_missing_fields_default_zero(self, compressor):
        compressor.update_from_response({})
        assert compressor.last_prompt_tokens == 0

    def test_missing_fields_do_not_zero_a_prior_nonzero_value(self, compressor):
        """A provider response with a real usage object but no prompt_tokens
        (seen with some OpenAI-compatible providers on some calls) must not
        wipe out a previously-tracked, larger value — that's a status-bar
        "context size reset to 0" regression, not the prompt actually
        shrinking. See update_from_response()'s docstring."""
        compressor.update_from_response({
            "prompt_tokens": 40000,
            "completion_tokens": 500,
            "total_tokens": 40500,
        })
        compressor.update_from_response({})
        assert compressor.last_prompt_tokens == 40000
        assert compressor.last_completion_tokens == 500
        assert compressor.last_total_tokens == 40500


class TestGetStatus:
    def test_returns_expected_keys(self, compressor):
        status = compressor.get_status()
        assert "last_prompt_tokens" in status
        assert "threshold_tokens" in status
        assert "context_length" in status
        assert "usage_percent" in status
        assert "compression_count" in status

    def test_usage_percent_calculation(self, compressor):
        compressor.last_prompt_tokens = 50000
        status = compressor.get_status()
        assert status["usage_percent"] == 50.0


class TestCompress:
    def _make_messages(self, n):
        return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(n)]

    def test_too_few_messages_returns_unchanged(self, compressor):
        msgs = self._make_messages(4)
        result = compressor.compress(msgs)
        assert result == msgs

    def test_truncation_fallback_no_client(self, compressor):
        msgs = [{"role": "system", "content": "System prompt"}] + self._make_messages(10)
        result = compressor.compress(msgs)
        assert len(result) < len(msgs)
        assert result[0]["role"] == "system"
        assert compressor.compression_count == 1

    def test_compression_increments_count(self, compressor):
        msgs = self._make_messages(10)
        compressor.compress(msgs)
        assert compressor.compression_count == 1
        compressor.compress(msgs)
        assert compressor.compression_count == 2

    def test_protects_first_and_last(self, compressor):
        msgs = self._make_messages(10)
        result = compressor.compress(msgs)
        assert result[-1]["content"] == msgs[-1]["content"]
        assert msgs[-2]["content"] in result[-2]["content"]


class TestGenerateSummaryNoneContent:
    """Regression: content=None (from tool-call-only assistant messages) must not crash."""

    def test_none_content_does_not_crash(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[CONTEXT SUMMARY]: tool calls happened"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True)

        messages = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"function": {"name": "search"}}
            ]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "content": None},
            {"role": "user", "content": "thanks"},
        ]

        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            summary = c._generate_summary(messages)
        assert isinstance(summary, str)
        assert summary.startswith(SUMMARY_PREFIX)

    def test_none_content_in_system_message_compress(self):
        """System message with content=None should not crash during compress."""
        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=2, protect_last_n=2)

        msgs = [{"role": "system", "content": None}] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(10)
        ]
        result = c.compress(msgs)
        assert len(result) < len(msgs)


class TestNonStringContent:
    """Regression: content as dict (e.g., llama.cpp tool calls) must not crash."""

    def test_dict_content_coerced_to_string(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = {"text": "some summary"}

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True)

        messages = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": "ok"},
        ]

        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            summary = c._generate_summary(messages)
        assert isinstance(summary, str)
        assert summary.startswith(SUMMARY_PREFIX)

    def test_none_content_coerced_to_empty(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True)

        messages = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": "ok"},
        ]

        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            summary = c._generate_summary(messages)
        assert summary is not None
        assert summary == SUMMARY_PREFIX

    def test_summary_call_does_not_force_temperature(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True)

        messages = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": "ok"},
        ]

        with patch("agent.context_compressor.call_llm", return_value=mock_response) as mock_call:
            c._generate_summary(messages)

        kwargs = mock_call.call_args.kwargs
        assert "temperature" not in kwargs


class TestSummaryFailureCooldown:
    def test_summary_failure_enters_cooldown_and_skips_retry(self):
        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True)

        messages = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": "ok"},
        ]

        with patch("agent.context_compressor.call_llm", side_effect=Exception("boom")) as mock_call:
            first = c._generate_summary(messages)
            second = c._generate_summary(messages)

        assert first is None
        assert second is None
        assert mock_call.call_count == 1


class TestSummaryPrefixNormalization:
    def test_legacy_prefix_is_replaced(self):
        summary = ContextCompressor._with_summary_prefix("[CONTEXT SUMMARY]: did work")
        assert summary == f"{SUMMARY_PREFIX}\ndid work"

    def test_existing_new_prefix_is_not_duplicated(self):
        summary = ContextCompressor._with_summary_prefix(f"{SUMMARY_PREFIX}\ndid work")
        assert summary == f"{SUMMARY_PREFIX}\ndid work"


class TestCompressWithClient:
    def test_summarization_path(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[CONTEXT SUMMARY]: stuff happened"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=2, protect_last_n=2)

        msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(10)]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)

        contents = [m.get("content", "") for m in result]
        assert any(c.startswith(SUMMARY_PREFIX) for c in contents)
        assert len(result) < len(msgs)

    def test_summarization_does_not_split_tool_call_pairs(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[CONTEXT SUMMARY]: compressed middle"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(
                model="test",
                quiet_mode=True,
                protect_first_n=3,
                protect_last_n=4,
            )

        msgs = [
            {"role": "user", "content": "Could you address the reviewer comments in PR#71"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_a", "type": "function", "function": {"name": "skill_view", "arguments": "{}"}},
                    {"id": "call_b", "type": "function", "function": {"name": "skill_view", "arguments": "{}"}},
                ],
            },
            {"role": "tool", "tool_call_id": "call_a", "content": "output a"},
            {"role": "tool", "tool_call_id": "call_b", "content": "output b"},
            {"role": "user", "content": "later 1"},
            {"role": "assistant", "content": "later 2"},
            {"role": "tool", "tool_call_id": "call_x", "content": "later output"},
            {"role": "assistant", "content": "later 3"},
            {"role": "user", "content": "later 4"},
        ]

        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)

        answered_ids = {
            msg.get("tool_call_id")
            for msg in result
            if msg.get("role") == "tool" and msg.get("tool_call_id")
        }
        for msg in result:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    assert tc["id"] in answered_ids

    def test_summary_role_avoids_consecutive_user_messages(self):
        """Summary role should alternate with the last head message to avoid consecutive same-role messages."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[CONTEXT SUMMARY]: stuff happened"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=2, protect_last_n=2)

        msgs = [
            {"role": "user", "content": "msg 0"},
            {"role": "assistant", "content": "msg 1"},
            {"role": "user", "content": "msg 2"},
            {"role": "assistant", "content": "msg 3"},
            {"role": "user", "content": "msg 4"},
            {"role": "assistant", "content": "msg 5"},
        ]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)
        summary_msg = [
            m for m in result if (m.get("content") or "").startswith(SUMMARY_PREFIX)
        ]
        assert len(summary_msg) == 1
        assert summary_msg[0]["role"] == "user"

    def test_summary_role_avoids_consecutive_user_when_head_ends_with_user(self):
        """When last head message is 'user', summary must be 'assistant' to avoid two consecutive user messages."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[CONTEXT SUMMARY]: stuff happened"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=3, protect_last_n=2)

        msgs = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "msg 1"},
            {"role": "user", "content": "msg 2"},
            {"role": "assistant", "content": "msg 3"},
            {"role": "user", "content": "msg 4"},
            {"role": "assistant", "content": "msg 5"},
            {"role": "user", "content": "msg 6"},
            {"role": "assistant", "content": "msg 7"},
        ]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)
        summary_msg = [
            m for m in result if (m.get("content") or "").startswith(SUMMARY_PREFIX)
        ]
        assert len(summary_msg) == 1
        assert summary_msg[0]["role"] == "assistant"

    def test_summary_role_flips_to_avoid_tail_collision(self):
        """When summary role collides with the first tail message but flipping
        doesn't collide with head, the role should be flipped."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "summary text"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=2, protect_last_n=2)

        msgs = [
            {"role": "user", "content": "msg 0"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "t", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": "result 1"},
            {"role": "assistant", "content": "msg 3"},
            {"role": "user", "content": "msg 4"},
            {"role": "assistant", "content": "msg 5"},
            {"role": "user", "content": "msg 6"},
            {"role": "assistant", "content": "msg 7"},
        ]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)
        for i in range(1, len(result)):
            r1 = result[i - 1].get("role")
            r2 = result[i].get("role")
            if r1 in ("user", "assistant") and r2 in ("user", "assistant"):
                assert r1 != r2, f"consecutive {r1} at indices {i-1},{i}"

    def test_double_collision_merges_summary_into_tail(self):
        """When neither role avoids collision with both neighbors, the summary
        should be merged into the first tail message rather than creating a
        standalone message that breaks role alternation.

        Common scenario: head ends with 'assistant', tail starts with 'user'.
        summary='user' collides with tail, summary='assistant' collides with head.
        """
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "summary text"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=3, protect_last_n=3)

        msgs = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "msg 1"},
            {"role": "assistant", "content": "msg 2"},
            {"role": "user", "content": "msg 3"},
            {"role": "assistant", "content": "msg 4"},
            {"role": "user", "content": "msg 5"},
            {"role": "user", "content": "msg 6"},
            {"role": "assistant", "content": "msg 7"},
            {"role": "user", "content": "msg 8"},
        ]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)

        for i in range(1, len(result)):
            r1 = result[i - 1].get("role")
            r2 = result[i].get("role")
            if r1 in ("user", "assistant") and r2 in ("user", "assistant"):
                assert r1 != r2, f"consecutive {r1} at indices {i-1},{i}"

        first_tail = [m for m in result if "msg 6" in (m.get("content") or "")]
        assert len(first_tail) == 1
        assert "summary text" in first_tail[0]["content"]

    def test_double_collision_user_head_assistant_tail(self):
        """Reverse double collision: head ends with 'user', tail starts with 'assistant'.
        summary='assistant' collides with tail, 'user' collides with head → merge."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "summary text"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=2, protect_last_n=2)

        msgs = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "msg 1"},
            {"role": "assistant", "content": "msg 2"},
            {"role": "user", "content": "msg 3"},
            {"role": "assistant", "content": "msg 4"},
            {"role": "assistant", "content": "msg 5"},
            {"role": "user", "content": "msg 6"},
        ]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)

        for i in range(1, len(result)):
            r1 = result[i - 1].get("role")
            r2 = result[i].get("role")
            if r1 in ("user", "assistant") and r2 in ("user", "assistant"):
                assert r1 != r2, f"consecutive {r1} at indices {i-1},{i}"

        first_tail = [m for m in result if "msg 5" in (m.get("content") or "")]
        assert len(first_tail) == 1
        assert "summary text" in first_tail[0]["content"]

    def test_no_collision_scenarios_still_work(self):
        """Verify that the common no-collision cases (head=assistant/tail=assistant,
        head=user/tail=user) still produce a standalone summary message."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "summary text"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(model="test", quiet_mode=True, protect_first_n=2, protect_last_n=2)

        msgs = [
            {"role": "user", "content": "msg 0"},
            {"role": "assistant", "content": "msg 1"},
            {"role": "user", "content": "msg 2"},
            {"role": "assistant", "content": "msg 3"},
            {"role": "assistant", "content": "msg 4"},
            {"role": "user", "content": "msg 5"},
        ]
        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)
        summary_msgs = [m for m in result if (m.get("content") or "").startswith(SUMMARY_PREFIX)]
        assert len(summary_msgs) == 1, "should have a standalone summary message"
        assert summary_msgs[0]["role"] == "user"

    def test_summarization_does_not_start_tail_with_tool_outputs(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[CONTEXT SUMMARY]: compressed middle"

        with patch("agent.context_compressor.get_model_context_length", return_value=100000):
            c = ContextCompressor(
                model="test",
                quiet_mode=True,
                protect_first_n=2,
                protect_last_n=3,
            )

        msgs = [
            {"role": "user", "content": "earlier 1"},
            {"role": "assistant", "content": "earlier 2"},
            {"role": "user", "content": "earlier 3"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_c", "type": "function", "function": {"name": "search_files", "arguments": "{}"}},
                ],
            },
            {"role": "tool", "tool_call_id": "call_c", "content": "output c"},
            {"role": "user", "content": "latest user"},
        ]

        with patch("agent.context_compressor.call_llm", return_value=mock_response):
            result = c.compress(msgs)

        called_ids = {
            tc["id"]
            for msg in result
            if msg.get("role") == "assistant" and msg.get("tool_calls")
            for tc in msg["tool_calls"]
        }
        for msg in result:
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                assert msg["tool_call_id"] in called_ids


class TestSummaryTargetRatio:
    """Verify that summary_target_ratio properly scales budgets with context window."""

    def test_tail_budget_scales_with_context(self):
        """Tail token budget should be threshold_tokens * summary_target_ratio."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            c = ContextCompressor(model="test", quiet_mode=True, summary_target_ratio=0.40)
        assert c.tail_token_budget == 40_000

        with patch("agent.context_compressor.get_model_context_length", return_value=1_000_000):
            c = ContextCompressor(model="test", quiet_mode=True, summary_target_ratio=0.40)
        assert c.tail_token_budget == 200_000

    def test_summary_cap_scales_with_context(self):
        """Max summary tokens should be 5% of context, capped at 12K."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            c = ContextCompressor(model="test", quiet_mode=True)
        assert c.max_summary_tokens == 10_000

        with patch("agent.context_compressor.get_model_context_length", return_value=1_000_000):
            c = ContextCompressor(model="test", quiet_mode=True)
        assert c.max_summary_tokens == 12_000

    def test_ratio_clamped(self):
        """Ratio should be clamped to [0.10, 0.80]."""
        with patch("agent.context_compressor.get_model_context_length", return_value=100_000):
            c = ContextCompressor(model="test", quiet_mode=True, summary_target_ratio=0.05)
        assert c.summary_target_ratio == 0.10

        with patch("agent.context_compressor.get_model_context_length", return_value=100_000):
            c = ContextCompressor(model="test", quiet_mode=True, summary_target_ratio=0.95)
        assert c.summary_target_ratio == 0.80

    def test_default_threshold_is_50_percent(self):
        """Default compression threshold should be 50%."""
        with patch("agent.context_compressor.get_model_context_length", return_value=100_000):
            c = ContextCompressor(model="test", quiet_mode=True)
        assert c.threshold_percent == 0.50
        assert c.threshold_tokens == 50_000

    def test_default_protect_last_n_is_20(self):
        """Default protect_last_n should be 20."""
        with patch("agent.context_compressor.get_model_context_length", return_value=100_000):
            c = ContextCompressor(model="test", quiet_mode=True)
        assert c.protect_last_n == 20


class TestHardwareCeiling:
    def _c(self, **kw):
        from agent.context_compressor import ContextCompressor

        kw.setdefault("model", "test-model")
        kw.setdefault("quiet_mode", True)
        kw.setdefault("config_context_length", 256_800)
        kw.setdefault("threshold_percent", 0.95)
        return ContextCompressor(**kw)

    def test_without_a_ceiling_the_percentage_decides(self):
        assert self._c().threshold_tokens == int(256_800 * 0.95)

    def test_a_ceiling_below_the_window_wins(self):
        assert self._c(max_tokens=100_000).threshold_tokens == 100_000

    def test_a_ceiling_above_the_window_does_not_raise_the_trigger(self):
        assert self._c(max_tokens=999_999).threshold_tokens == int(256_800 * 0.95)

    def test_zero_means_no_ceiling(self):
        assert self._c(max_tokens=0).threshold_tokens == int(256_800 * 0.95)


class TestPruneStaleToolResults:
    def _msgs(self, n, size=9000):
        out = []
        for i in range(n):
            out.append({"role": "assistant",
                        "tool_calls": [{"id": f"t{i}",
                                        "function": {"name": "read_file", "arguments": "{}"}}]})
            out.append({"role": "tool", "tool_call_id": f"t{i}", "content": "X" * size})
        return out

    def _c(self):
        from agent.context_compressor import ContextCompressor

        return ContextCompressor(model="test-model", quiet_mode=True,
                                 threshold_percent=0.95, protect_last_n=3,
                                 config_context_length=256_800, max_tokens=100_000)

    def test_quiet_below_half_the_threshold(self):
        c = self._c()
        msgs = self._msgs(40)
        out, n = c.prune_stale_tool_results(msgs, 40_000)
        assert n == 0
        assert out is msgs

    def test_prunes_once_the_context_grows(self):
        c = self._c()
        out, n = c.prune_stale_tool_results(self._msgs(40), 60_000)
        assert n > 0

    def test_the_tail_is_left_intact(self):
        c = self._c()
        msgs = self._msgs(40)
        out, _ = c.prune_stale_tool_results(msgs, 90_000)
        for original, pruned in zip(msgs[-12:], out[-12:]):
            assert original["content" if "content" in original else "role"] == \
                pruned["content" if "content" in pruned else "role"]

    def test_small_results_are_kept(self):
        c = self._c()
        out, n = c.prune_stale_tool_results(self._msgs(40, size=50), 90_000)
        assert n == 0

    def test_pruning_is_idempotent(self):
        c = self._c()
        once, n1 = c.prune_stale_tool_results(self._msgs(40), 90_000)
        twice, n2 = c.prune_stale_tool_results(once, 90_000)
        assert n1 > 0 and n2 == 0

    def test_structure_survives(self):
        c = self._c()
        msgs = self._msgs(40)
        out, _ = c.prune_stale_tool_results(msgs, 90_000)
        assert len(out) == len(msgs)
        for original, pruned in zip(msgs, out):
            assert original["role"] == pruned["role"]
            if original["role"] == "tool":
                assert original["tool_call_id"] == pruned["tool_call_id"]


class TestSpillToTmpfs:
    def _agent_archiver(self):
        from run_agent import AIAgent

        return AIAgent._archive_context_chunk

    def _c(self, archiver):
        from agent.context_compressor import ContextCompressor

        c = ContextCompressor(model="test-model", quiet_mode=True,
                              threshold_percent=0.95, protect_last_n=3,
                              config_context_length=256_800, max_tokens=100_000,
                              archiver=archiver)
        c.session_label = "pytest-spill"
        return c

    def _msgs(self, n, size=9000):
        out = []
        for i in range(n):
            out.append({"role": "assistant",
                        "tool_calls": [{"id": f"t{i}",
                                        "function": {"name": "read_file", "arguments": "{}"}}]})
            out.append({"role": "tool", "tool_call_id": f"t{i}", "content": "X" * size})
        return out

    def test_content_survives_on_disk_and_the_handle_points_at_it(self):
        import os

        c = self._c(self._agent_archiver())
        out, n = c.prune_stale_tool_results(self._msgs(30), 90_000)
        assert n > 0
        assert c.offloaded
        path = c.offloaded[0]["path"]
        assert os.path.isfile(path)
        assert open(path).read() == "X" * 9000
        handles = [m["content"] for m in out
                   if m.get("role") == "tool" and m["content"].startswith("[offloaded")]
        assert handles and path in handles[0]

    def test_nothing_is_dropped_when_a_spill_target_exists(self):
        c = self._c(self._agent_archiver())
        out, n = c.prune_stale_tool_results(self._msgs(30), 90_000)
        dropped = [m for m in out if m.get("role") == "tool"
                   and m["content"].startswith("[Old tool output")]
        assert dropped == []

    def test_a_failing_archiver_falls_back_to_the_placeholder(self):
        c = self._c(lambda *a: None)
        out, n = c.prune_stale_tool_results(self._msgs(30), 90_000)
        assert n > 0
        assert not c.offloaded
        assert any(m.get("content", "").startswith("[Old tool output") for m in out)

    def test_the_notice_names_the_paths(self):
        c = self._c(self._agent_archiver())
        c.prune_stale_tool_results(self._msgs(30), 90_000)
        notice = c.offload_notice()
        assert "read_file" in notice and "/" in notice
        assert "read_file(path)" in notice

    def test_no_notice_without_spills(self):
        c = self._c(self._agent_archiver())
        assert c.offload_notice() == ""

    def test_purge_removes_stale_directories(self):
        from run_agent import AIAgent

        c = self._c(self._agent_archiver())
        c.prune_stale_tool_results(self._msgs(30), 90_000)
        assert AIAgent.purge_stale_spills(max_age_seconds=0) >= 1


class TestSpillCallArguments:
    def _c(self):
        from agent.context_compressor import ContextCompressor
        from run_agent import AIAgent

        c = ContextCompressor(model="test-model", quiet_mode=True,
                              threshold_percent=0.95, protect_last_n=3,
                              config_context_length=256_800, max_tokens=100_000,
                              archiver=AIAgent._archive_context_chunk)
        c.session_label = "pytest-args"
        return c

    def _msgs(self, n, arg_size=9000):
        import json as _json

        out = []
        for i in range(n):
            payload = _json.dumps({"file_path": f"/tmp/f{i}.txt", "content": "Y" * arg_size})
            out.append({"role": "assistant",
                        "tool_calls": [{"id": f"t{i}",
                                        "function": {"name": "write_file",
                                                     "arguments": payload}}]})
            out.append({"role": "tool", "tool_call_id": f"t{i}", "content": "ok"})
        return out

    def _first_spilled(self, messages):
        import json as _json

        for msg in messages:
            for call in (msg.get("tool_calls") or []):
                args = _json.loads(call["function"]["arguments"])
                if any(isinstance(v, dict) and "_spilled_to" in v for v in args.values()):
                    return args
        return None

    def test_the_bulky_value_moves_and_stays_readable(self):
        import os

        c = self._c()
        out, n = c.prune_stale_tool_results(self._msgs(30), 90_000)
        assert n > 0
        args = self._first_spilled(out)
        assert args is not None
        path = args["content"]["_spilled_to"]
        assert os.path.isfile(path)
        assert open(path).read() == "Y" * 9000

    def test_the_identifying_value_stays_inline(self):
        c = self._c()
        out, _ = c.prune_stale_tool_results(self._msgs(30), 90_000)
        args = self._first_spilled(out)
        assert args is not None
        assert args["file_path"].startswith("/tmp/f")
        assert isinstance(args["file_path"], str)

    def test_a_spilled_result_names_what_it_was_about(self):
        import json as _json

        c = self._c()
        msgs = []
        for i in range(30):
            msgs.append({"role": "assistant", "tool_calls": [
                {"id": f"r{i}", "function": {"name": "read_file",
                                             "arguments": _json.dumps({"file_path": f"/src/mod{i}.py"})}}]})
            msgs.append({"role": "tool", "tool_call_id": f"r{i}", "content": "Z" * 9000})
        out, _ = c.prune_stale_tool_results(msgs, 90_000)
        handles = [m["content"] for m in out
                   if m.get("role") == "tool" and m["content"].startswith("[offloaded")]
        assert handles
        assert "/src/mod0.py" in handles[0]

    def test_every_argument_stays_valid_json(self):
        import json as _json

        c = self._c()
        out, _ = c.prune_stale_tool_results(self._msgs(30), 90_000)
        for msg in out:
            for call in (msg.get("tool_calls") or []):
                _json.loads(call["function"]["arguments"])

    def test_small_arguments_are_untouched(self):
        c = self._c()
        out, n = c.prune_stale_tool_results(self._msgs(30, arg_size=10), 90_000)
        assert n == 0

    def test_the_live_tail_keeps_its_arguments(self):
        msgs = self._msgs(30)
        c = self._c()
        out, _ = c.prune_stale_tool_results(msgs, 90_000)
        for original, kept in zip(msgs[-c.live_window_messages:],
                                  out[-c.live_window_messages:]):
            assert original == kept

    def test_spilling_is_idempotent(self):
        c = self._c()
        once, n1 = c.prune_stale_tool_results(self._msgs(30), 90_000)
        twice, n2 = c.prune_stale_tool_results(once, 90_000)
        assert n1 > 0 and n2 == 0

    def test_without_an_archiver_arguments_are_left_alone(self):
        from agent.context_compressor import ContextCompressor

        c = ContextCompressor(model="test-model", quiet_mode=True,
                              threshold_percent=0.95, protect_last_n=3,
                              config_context_length=256_800, max_tokens=100_000)
        msgs = self._msgs(30)
        out, _ = c.prune_stale_tool_results(msgs, 90_000)
        for msg in out:
            for call in (msg.get("tool_calls") or []):
                assert "_spilled_to" not in call["function"]["arguments"]


class TestVerboseSpillReporting:
    def _c(self):
        from agent.context_compressor import ContextCompressor
        from run_agent import AIAgent

        c = ContextCompressor(model="test-model", quiet_mode=True,
                              threshold_percent=0.95, protect_last_n=3,
                              config_context_length=73728, max_tokens=40000,
                              archiver=AIAgent._archive_context_chunk)
        c.session_label = "pytest-verbose"
        return c

    def _msgs(self, n):
        import json as _json

        out = []
        for i in range(n):
            out.append({"role": "assistant", "tool_calls": [
                {"id": f"t{i}", "function": {"name": "read_file",
                                             "arguments": _json.dumps({"file_path": f"/src/m{i}.py"})}}]})
            out.append({"role": "tool", "tool_call_id": f"t{i}", "content": "X" * 9000})
        return out

    def test_the_ledger_records_what_each_spill_was_about(self):
        c = self._c()
        c.prune_stale_tool_results(self._msgs(30), 30_000)
        assert c.offloaded
        assert c.offloaded[0]["subject"] == "/src/m0.py"
        assert c.offloaded[0]["tool"] == "read_file"
        assert c.offloaded[0]["chars"] == 9000

    def test_the_report_names_files_and_paths(self, capsys):
        from run_agent import AIAgent, _message_payload_chars

        c = self._c()
        msgs = self._msgs(30)
        before = _message_payload_chars(msgs)
        out, pruned = c.prune_stale_tool_results(msgs, 30_000)

        class _Agent:
            verbose_logging = True
            _report_context_spill = AIAgent._report_context_spill

        _Agent._report_context_spill(_Agent(), c, 0, pruned, before,
                                     _message_payload_chars(out))
        printed = capsys.readouterr().out
        assert "context spill" in printed
        assert "/src/m0.py" in printed
        assert "/dev/shm" in printed or "read_file(path)" in printed

    def test_the_injection_report_labels_every_block(self, capsys):
        from run_agent import AIAgent

        class _Agent:
            verbose_logging = True
            _report_context_injections = AIAgent._report_context_injections

        _Agent._report_context_injections(_Agent(), [
            ("mazemaker recall", "<memory-context>hit</memory-context>"),
            ("context spill", "3 bulky tool result(s) were spilled"),
        ])
        printed = capsys.readouterr().out
        assert "turn injections" in printed
        assert "mazemaker recall" in printed
        assert "context spill" in printed

    def test_payload_chars_counts_arguments_too(self):
        from run_agent import _message_payload_chars

        msgs = [{"role": "assistant",
                 "tool_calls": [{"id": "a", "function": {"name": "w", "arguments": "12345"}}]},
                {"role": "tool", "tool_call_id": "a", "content": "abc"}]
        assert _message_payload_chars(msgs) == 8

    def test_reports_never_raise_on_odd_input(self, capsys):
        from run_agent import AIAgent

        class _Agent:
            verbose_logging = True
            _report_context_spill = AIAgent._report_context_spill
            _report_context_injections = AIAgent._report_context_injections

        class _Broken:
            offloaded = None
            live_window_messages = 12

        _Agent._report_context_spill(_Agent(), _Broken(), 0, 1, 100, 50)
        _Agent._report_context_injections(_Agent(), [])


class TestAdaptiveTailBreaksTheCompressionLoop:
    def _c(self, threshold=40000):
        from agent.context_compressor import ContextCompressor
        from run_agent import AIAgent

        c = ContextCompressor(model="test-model", quiet_mode=True,
                              threshold_percent=0.95, protect_last_n=3,
                              config_context_length=73728, max_tokens=threshold,
                              archiver=AIAgent._archive_context_chunk)
        c.session_label = "pytest-loop"
        return c

    def _post_compaction(self, pairs=5, chars=32000):
        import json as _json

        msgs = [{"role": "user", "content": "continue"}]
        for i in range(pairs):
            msgs.append({"role": "assistant", "tool_calls": [
                {"id": f"t{i}", "function": {"name": "read_file",
                                             "arguments": _json.dumps({"file_path": f"/src/b{i}.py"})}}]})
            msgs.append({"role": "tool", "tool_call_id": f"t{i}", "content": "X" * chars})
        return msgs

    def test_a_short_but_heavy_list_still_spills(self):
        c = self._c()
        msgs = self._post_compaction()
        assert len(msgs) < 12, "the regression needs fewer messages than the old fixed tail"
        out, pruned = c.prune_stale_tool_results(msgs, 40000)
        assert pruned > 0
        assert c._payload_chars(out) < c._payload_chars(msgs) / 2

    def test_the_tail_shrinks_only_as_far_as_the_floor(self):
        from agent.context_compressor import _LIVE_WINDOW_FLOOR

        c = self._c()
        assert c._adaptive_tail(self._post_compaction(pairs=8, chars=60000)) == _LIVE_WINDOW_FLOOR

    def test_a_light_list_keeps_the_full_tail(self):
        c = self._c()
        msgs = self._post_compaction(pairs=8, chars=50)
        assert c._adaptive_tail(msgs) == min(c.live_window_messages, len(msgs))

    def test_the_newest_messages_are_never_spilled(self):
        from agent.context_compressor import _LIVE_WINDOW_FLOOR

        c = self._c()
        msgs = self._post_compaction()
        out, _ = c.prune_stale_tool_results(msgs, 40000)
        for original, kept in zip(msgs[-_LIVE_WINDOW_FLOOR:], out[-_LIVE_WINDOW_FLOOR:]):
            assert original == kept

    def test_the_budget_follows_the_compression_threshold(self):
        assert self._c(threshold=40000).live_window_chars == 80000
        assert self._c(threshold=20000).live_window_chars == 40000

    def test_repeated_passes_converge_instead_of_looping(self):
        c = self._c()
        msgs = self._post_compaction()
        first, n1 = c.prune_stale_tool_results(msgs, 40000)
        second, n2 = c.prune_stale_tool_results(first, 40000)
        assert n1 > 0 and n2 == 0
