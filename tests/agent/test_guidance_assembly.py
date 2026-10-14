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
        assert "\n# Mazemaker — memory" in prompt \
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


class TestRecallIsAToolNotARitual:
    """2026-10-14: this block, the SOUL and a config prompt each demanded a recall
    before any command, "no exceptions"; the model spent its thinking reciting
    protocol instead of working."""

    def test_no_ritual(self):
        block = build_mazemaker_guidance(3)
        for ritual in ("RETRIEVE BEFORE YOU WORK", "no exceptions", "MANDATORY",
                       "BEFORE the first terminal command"):
            assert ritual not in block
        assert "do not recall as a ritual" in block

    def test_one_recall_for_what_the_conversation_does_not_show(self):
        block = build_mazemaker_guidance(3)
        assert "does not show" in block and "one focused" in block

    def test_the_aged_out_marker_matches_what_the_harness_writes(self):
        """The harness line says to run a call again when there is no path; the
        guidance used to forbid exactly that."""
        block = build_mazemaker_guidance(3)
        assert "[aged out of context]" in block
        assert "read_file(path)" in block and "run the call again" in block

    def test_it_still_names_every_tool(self):
        block = build_mazemaker_guidance(3)
        for tool in ("mazemaker_recall", "mazemaker_get",
                     "mazemaker_think", "mazemaker_remember"):
            assert tool in block


class TestWindowLine:
    def test_it_states_what_the_window_actually_carries(self):
        assert "last 3 turns" in build_mazemaker_guidance(3)

    def test_full_history_case(self):
        assert "the whole conversation" in build_mazemaker_guidance(-1)

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
