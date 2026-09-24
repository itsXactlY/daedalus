"""The 2026-09-24 failure: compaction ran 3x, grew the prompt, then died."""
import sys, types
sys.modules.setdefault("fal_client", types.ModuleType("fal_client"))
sys.modules.setdefault("firecrawl", types.ModuleType("firecrawl"))

from agent.model_metadata import (
    parse_context_limit_from_error, parse_prompt_tokens_from_error,
)

LLAMA_ERR = ("HTTP 400: request (77649 tokens) exceeds the available context "
             "size (77568 tokens), try increasing it")
LLAMA_DETAILS = ("{'code': 400, 'message': 'request (77649 tokens) exceeds the "
                 "available context size (77568 tokens)', "
                 "'n_prompt_tokens': 77649, 'n_ctx': 77568}")


class TestErrorParsing:
    def test_limit_from_parenthesised_form(self):
        """This returned None, so the caller guessed 64k/32k/16k tiers."""
        assert parse_context_limit_from_error(LLAMA_ERR) == 77568

    def test_limit_from_details_dict(self):
        assert parse_context_limit_from_error(LLAMA_DETAILS) == 77568

    def test_actual_prompt_size_extracted(self):
        assert parse_prompt_tokens_from_error(LLAMA_ERR) == 77649

    def test_actual_prompt_size_from_details(self):
        assert parse_prompt_tokens_from_error(LLAMA_DETAILS) == 77649

    def test_openai_phrasing(self):
        assert parse_prompt_tokens_from_error(
            "maximum context length is 8192 tokens. However, your messages "
            "resulted in 9000 tokens") == 9000

    def test_no_false_positive(self):
        assert parse_prompt_tokens_from_error("rate limited, try again") is None

    def test_limit_still_parses_classic_forms(self):
        assert parse_context_limit_from_error(
            "This model maximum context length is 8192 tokens") == 8192


class TestTrimLargestToolResults:
    def _agent(self):
        import run_agent
        return run_agent.AIAgent._trim_largest_tool_results

    def test_trims_the_oversized_payload(self):
        trim = self._agent()
        msgs = [{"role": "tool", "content": "X" * 90000},
                {"role": "tool", "content": "small"}]
        assert trim(msgs, target_tokens=5000) == 1
        assert len(msgs[0]["content"]) < 90000
        assert msgs[1]["content"] == "small"

    def test_marks_what_it_removed(self):
        trim = self._agent()
        msgs = [{"role": "tool", "content": "X" * 90000}]
        trim(msgs, target_tokens=1000)
        assert "[trimmed" in msgs[0]["content"]

    def test_leaves_non_tool_messages_alone(self):
        trim = self._agent()
        msgs = [{"role": "user", "content": "X" * 90000}]
        assert trim(msgs, target_tokens=100) == 0
        assert len(msgs[0]["content"]) == 90000

    def test_noop_when_already_small(self):
        trim = self._agent()
        msgs = [{"role": "tool", "content": "tiny"}]
        assert trim(msgs, target_tokens=5000) == 0

    def test_stops_once_under_budget(self):
        """Should not shred every result when trimming one is enough."""
        trim = self._agent()
        msgs = [{"role": "tool", "content": "X" * 90000},
                {"role": "tool", "content": "Y" * 9000}]
        trim(msgs, target_tokens=8000)
        assert msgs[1]["content"] == "Y" * 9000
