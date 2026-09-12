"""How the tool-guidance blocks are assembled into the system prompt.

These blocks are markdown with their own headings. They were joined with a
single space, which ran them together mid-sentence and left

    ...before asking them to repeat themselves. # Mazemaker — persistent
    memory (MANDATORY)\\nYour context window carries...

so the MANDATORY heading was not a heading at all, just more prose inside a
wall of it. Mazemaker also came after session_search, which reads as a
competing first move for the same job.

Both are formatting, not wording, and formatting is what a model skims.
"""

from unittest.mock import MagicMock, patch

import run_agent
from agent.prompt_builder import (MEMORY_GUIDANCE, SESSION_SEARCH_GUIDANCE,
                                  SKILLS_GUIDANCE, build_mazemaker_guidance)


def _prompt(tools=("mazemaker_recall", "memory", "session_search", "skill_manage")):
    """A real AIAgent -- the assembly under test lives in _build_system_prompt,
    so constructing it by hand would test a different code path."""
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = run_agent.AIAgent(api_key="test-key-1234567890", quiet_mode=True,
                              skip_context_files=True, skip_memory=True)
    a.client = MagicMock()
    a.valid_tool_names = set(tools)
    a._soak_window_turns = 3
    a.router_prompt = ""
    a._pony_mode = None
    a._cached_system_prompt = None
    return a._build_system_prompt()


class TestBlocksAreSeparated:
    def test_the_mandatory_heading_starts_a_line(self):
        prompt = _prompt()
        assert "\n# Mazemaker — persistent memory (MANDATORY)" in prompt \
            or prompt.lstrip().startswith("# Mazemaker"), (
            "a heading buried mid-line is not a heading; it is prose"
        )

    def test_no_block_runs_into_the_next_mid_sentence(self):
        prompt = _prompt()
        for block in (MEMORY_GUIDANCE, SESSION_SEARCH_GUIDANCE, SKILLS_GUIDANCE):
            tail = block.strip()[-40:]
            i = prompt.find(tail)
            if i < 0:
                continue
            after = prompt[i + len(tail): i + len(tail) + 2]
            assert after in ("", "\n\n", "\n"), (
                f"block ends and the next begins with {after!r}, not a break"
            )

    def test_every_heading_is_at_a_line_start(self):
        prompt = _prompt()
        for line_start_heading in ("# Mazemaker", "# session_search"):
            assert any(l.startswith(line_start_heading) for l in prompt.splitlines()), \
                f"{line_start_heading} is not at the start of any line"


class TestOrdering:
    def test_mazemaker_precedes_session_search(self):
        """session_search is a strict subset of what mazemaker indexes.
        Whichever appears first reads as the first move."""
        prompt = _prompt()
        assert prompt.index("# Mazemaker") < prompt.index("# session_search")

    def test_mazemaker_precedes_the_generic_memory_tool_guidance(self):
        prompt = _prompt()
        assert prompt.index("# Mazemaker") < prompt.index(MEMORY_GUIDANCE.strip()[:40])

    def test_session_search_defers_instead_of_competing(self):
        assert "strict subset" in SESSION_SEARCH_GUIDANCE
        assert "recall from it first" in SESSION_SEARCH_GUIDANCE


class TestTheRuleIsFirst:
    def test_retrieve_before_you_work_is_near_the_top(self):
        """It used to sit sixth, after the tool list and four bullets."""
        block = build_mazemaker_guidance(3)
        head = "\n".join(block.splitlines()[:3])
        assert "RETRIEVE BEFORE YOU WORK" in head

    def test_it_names_the_failure_it_prevents(self):
        block = build_mazemaker_guidance(3)
        assert "not a re-read" in block and "not starting over" in block

    def test_it_says_recall_comes_before_the_first_tool_call(self):
        block = build_mazemaker_guidance(3)
        assert "BEFORE the first terminal command, file read or search" in block

    def test_it_explains_the_aged_out_marker(self):
        """The collapsed tool-exchange line is new; without this the model
        can read its own completed work as a suggestion to do it."""
        block = build_mazemaker_guidance(3)
        assert "[aged out of context]" in block
        assert "not a suggestion to redo it" in block

    def test_it_still_names_every_tool(self):
        block = build_mazemaker_guidance(3)
        for tool in ("mazemaker_recall", "mazemaker_get",
                     "mazemaker_think", "mazemaker_remember"):
            assert tool in block


class TestWindowLine:
    def test_it_states_what_the_window_actually_carries(self):
        assert "last 3 turns" in build_mazemaker_guidance(3)

    def test_full_history_case(self):
        assert "full history is carried in context" in build_mazemaker_guidance(-1)

    def test_current_turn_only_case(self):
        assert "only the current turn" in build_mazemaker_guidance(0)


class TestOnlyIncludesWhatIsAvailable:
    def test_no_mazemaker_tools_no_mazemaker_block(self):
        prompt = _prompt(tools=("memory",))
        assert "# Mazemaker" not in prompt

    def test_no_session_search_no_session_search_block(self):
        prompt = _prompt(tools=("mazemaker_recall",))
        assert "# session_search" not in prompt
        assert "# Mazemaker" in prompt
