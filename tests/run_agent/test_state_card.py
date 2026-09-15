"""Tests for the periodic state re-anchoring card.

After a compaction the rolling window no longer contains the goals / open
work / where-things-stand the model had. The state card re-injects those from
live in-memory state (the last compaction summary body + the current todo
list) the first turn after a compaction and every N turns afterwards, so the
agent can re-anchor without re-reading its own history.

Covered here:
- card assembly (summary / todo / both / neither -> fallback pointer)
- the injection gate in _build_turn_injections (pending flag vs cadence vs
  agent-without-soak-subsystem)

Note on the fake agent: AIAgent.__init__ pulls in the whole runtime, so these
tests bypass it with __new__ and set exactly the attributes the two methods
under test actually read.
"""

import pytest

from run_agent import AIAgent


class _FakeTodoStore:
    """Stands in for the real todo store; _build_state_card calls
    format_for_injection() on it and renders whatever string it returns."""

    def __init__(self, text):
        self._text = text

    def format_for_injection(self):
        return self._text


def _make_state_agent():
    """A minimal AIAgent with just the attributes the card + gate read.

    The state card and the injection gate read only in-memory attributes (no
    __init__ side effects), so we bypass __init__ with __new__ and set exactly
    what they touch:
      - _build_state_card: _last_state_summary_body, _todo_store, session_id,
        _state_card_path, _state_card_max_chars
      - _build_turn_injections gate: _turns_since_state_card,
        _state_reinject_every, _state_card_pending, session_id, and the
        context-compressor / memory-manager / skill-route / verbose attrs it
        reads further down the body.
    """
    agent = AIAgent.__new__(AIAgent)
    agent.session_id = "test-session"
    agent.verbose_logging = False            # read at the end of _build_turn_injections
    agent._state_card_path = ""              # -> "STATE.md" in the fallback line
    agent._state_card_max_chars = 0          # 0 -> no truncation
    agent._last_state_summary_body = ""      # last compaction summary body
    agent._turns_since_state_card = 0
    agent._state_reinject_every = 3
    agent._state_card_pending = False
    agent._todo_store = None
    # _build_turn_injections reads these further down; give them safe defaults.
    agent._soak_window_turns = -1            # keeps the memory-manager branch off
    agent._memory_manager = None
    agent._skill_route_block = ""
    agent.context_compressor = None          # offload_notice() is try/excepted
    return agent


@pytest.fixture
def agent():
    return _make_state_agent()


class TestBuildStateCard:
    def test_includes_summary_and_todo(self, agent):
        agent._last_state_summary_body = "summary text about the current work"
        agent._todo_store = _FakeTodoStore("1. [ ] build the thing\n2. [/] wire it up")
        card = agent._build_state_card()
        assert "STATE CARD" in card
        assert "Where things stand" in card
        assert "summary text about the current work" in card
        assert "Active tasks" in card
        assert "build the thing" in card

    def test_includes_only_summary(self, agent):
        agent._last_state_summary_body = "just the summary"
        card = agent._build_state_card()
        assert "just the summary" in card
        # no todo text rendered, so the todo marker line is absent
        assert "Active tasks" not in card

    def test_includes_only_todo(self, agent):
        agent._todo_store = _FakeTodoStore("- [x] done thing")
        card = agent._build_state_card()
        assert "done thing" in card
        assert "Active tasks" in card
        assert "just the summary" not in card

    def test_fallback_pointer_only(self, agent):
        # No summary body, no todo store -> fallback pointer line only.
        card = agent._build_state_card()
        assert "STATE CARD" in card
        assert "auto:turn:" in card          # mazemaker label pointer
        assert "STATE.md" in card            # crash-resistant pointer

    def test_truncates_to_max_chars(self, agent):
        agent._last_state_summary_body = "x" * 500
        agent._state_card_max_chars = 80
        card = agent._build_state_card()
        assert "state card truncated" in card
        assert len(card) <= 80 + len("\n...[state card truncated]")


class TestWiredIntoTheLoop:
    def test_pending_flag_forces_first_turn_card(self, agent):
        # Right after a compaction the pending flag is set -> card on turn 1.
        agent._turns_since_state_card = 0
        agent._state_reinject_every = 3
        agent._state_card_pending = True
        agent._last_state_summary_body = "summary text"
        injections = agent._build_turn_injections(
            ext_prefetch="", plugin_context="")
        joined = "\n".join(injections)
        assert "STATE CARD" in joined
        # injection resets both so the next turn starts the cadence count
        assert agent._state_card_pending is False
        assert agent._turns_since_state_card == 0

    def test_no_card_before_cadence_due(self, agent):
        # turn 1, cadence 3, nothing pending -> not yet due
        agent._turns_since_state_card = 0
        agent._state_reinject_every = 3
        agent._state_card_pending = False
        injections = agent._build_turn_injections(
            ext_prefetch="", plugin_context="")
        assert "STATE CARD" not in "\n".join(injections)

    def test_cadence_due_injects_and_resets(self, agent):
        # two turns passed (counter at 2) -> 2+1 >= 3 -> due
        agent._turns_since_state_card = 2
        agent._state_reinject_every = 3
        agent._state_card_pending = False
        agent._last_state_summary_body = "summary text"
        injections = agent._build_turn_injections(
            ext_prefetch="", plugin_context="")
        assert "STATE CARD" in "\n".join(injections)
        assert agent._turns_since_state_card == 0  # reset after injection

    def test_cadence_counter_increments_until_due(self, agent):
        # Regression: the counter must advance every turn on its own. The
        # earlier tests set the counter by hand, which masked a bug where
        # the loop never incremented it -- the card then only fired the
        # first turn after a compaction and never again. Here we drive three
        # turns from a reset state and assert the card lands exactly on the
        # cadence turn (turn 3 with reinject_every=3).
        agent._turns_since_state_card = 0
        agent._state_reinject_every = 3
        agent._state_card_pending = False
        agent._last_state_summary_body = "summary text"

        first = "\n".join(agent._build_turn_injections(ext_prefetch="", plugin_context=""))
        assert "STATE CARD" not in first          # turn 1: 0 -> 1, not yet due
        second = "\n".join(agent._build_turn_injections(ext_prefetch="", plugin_context=""))
        assert "STATE CARD" not in second         # turn 2: 1 -> 2, not yet due
        third = "\n".join(agent._build_turn_injections(ext_prefetch="", plugin_context=""))
        assert "STATE CARD" in third              # turn 3: 2 -> 3 >= 3, due
        assert agent._turns_since_state_card == 0  # reset after injection

    def test_agent_without_soak_gets_no_card(self, agent):
        # the turn counter only exists when the soak subsystem is on; without
        # it no card and no AttributeError.
        agent._turns_since_state_card = None
        agent._state_reinject_every = 3
        agent._state_card_pending = False
        injections = agent._build_turn_injections(
            ext_prefetch="", plugin_context="")
        assert "STATE CARD" not in "\n".join(injections)
