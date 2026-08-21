"""Tests for agent.task_intensity — the on-the-fly reasoning gauge.

Fork feature (context-budget-manager): the gauge maps task weight to a
reasoning-effort level. Everything starts LOW; escalation happens only on
demonstrable task weight (instructions, tool density, errors, explicit
depth requests).
"""

import pytest

from agent.task_intensity import (
    GAUGE_LEVELS,
    adjust_agent_reasoning,
    clamp_level,
    estimate_level,
    level_for_score,
    score_task,
)


class _FakeAgent:
    """Minimal agent stand-in: auto flag, floor, reasoning_config."""

    def __init__(self, auto=True, floor="low", config=None):
        self.reasoning_auto = auto
        self.reasoning_floor = floor
        self.reasoning_config = config
        self.vprint_calls = []

    def _vprint(self, text, force=False):
        self.vprint_calls.append(text)


def _msg(role, content):
    return {"role": role, "content": content}


# ── Level ladder ────────────────────────────────────────────────────────

class TestLevelMapping:
    def test_gauge_levels_ascending(self):
        assert GAUGE_LEVELS == (
            "low", "medium", "high", "xhigh", "max", "ultra",
        )

    def test_floor_is_low(self):
        assert level_for_score(0) == "low"
        assert level_for_score(3) == "low"

    def test_escalation(self):
        assert level_for_score(4) == "medium"
        assert level_for_score(7) == "high"
        assert level_for_score(10) == "xhigh"
        assert level_for_score(14) == "max"
        assert level_for_score(18) == "ultra"

    def test_clamp_level_floor(self):
        assert clamp_level("low", floor="medium") == "medium"
        assert clamp_level("high", floor="medium") == "high"
        assert clamp_level("medium", floor="low") == "medium"

    def test_clamp_level_unknown_inputs(self):
        assert clamp_level("bogus") == "low"
        assert clamp_level("low", floor="bogus") == "low"


# ── Scoring signals ─────────────────────────────────────────────────────

class TestScoring:
    def test_short_chat_scores_zero(self):
        assert score_task("danke") == 0
        assert score_task("ok") == 0

    def test_tiny_turn_stays_low(self):
        assert estimate_level("danke") == "low"
        assert estimate_level("ok") == "low"

    def test_short_command_stays_low(self):
        assert estimate_level("Zeig mir die Skills.") == "low"

    def test_task_terms_add_points(self):
        base = score_task("Bitte refactore das Modul und debugge den Fehler.")
        assert base >= 2

    def test_long_instruction_escalates(self):
        text = (
            "Bitte führe einen vollständigen Audit über den daedalus "
            "harness durch: untersuche die Sicherheit, refaktoriere die "
            "schwachen Stellen, debugge die Fehler und deploye danach alles. "
            "Analysiere gründlich die Architektur und implementiere die "
            "vorgeschlagenen Änderungen vollständig und produktionsreif. "
            "Vergiss nicht, die Migration zu dokumentieren und die "
            "Sicherheitslücken zu schließen."
        )
        assert estimate_level(text) in {"high", "xhigh", "max", "ultra"}

    def test_explicit_depth_request_escalates(self):
        assert estimate_level("Denk gründlich über diese Frage nach.") in {
            "high", "xhigh",
        }
        assert estimate_level("think hard about this design") in {"high", "xhigh"}

    def test_tool_density_escalates(self):
        messages = [_msg("user", "mach das komplett")]
        for i in range(9):
            messages.append(_msg("assistant", f"tool call {i}"))
            messages.append(_msg("tool", f"result {i}"))
        assert score_task("mach das komplett", messages=messages) >= 3

    def test_tool_errors_escalate(self):
        messages = [
            _msg("user", "fixe es"),
            _msg("assistant", "call"),
            _msg("tool", "Error: Invalid JSON arguments."),
            _msg("assistant", "call"),
            _msg("tool", "Traceback (most recent call last)"),
        ]
        assert score_task("fixe es", messages=messages) >= 2

    def test_tool_success_does_not_error(self):
        messages = [
            _msg("user", "Schau dir das Ergebnis an bitte"),
            _msg("assistant", "call"),
            _msg("tool", "alles sauber durchgelaufen"),
        ]
        assert score_task("Schau dir das Ergebnis an bitte", messages=messages) >= 1  # tool density only

    def test_single_task_imperative_never_low(self):
        """One clear imperative (e.g. an audit) must clear 'low'."""
        assert estimate_level(
            "do a full deep audit over this daedalus harness. "
            "find every flaw. report back."
        ) in {"high", "xhigh", "max", "ultra"}
        assert estimate_level("Bitte refactore das Modul und debugge den Fehler.") in {
            "medium", "high", "xhigh", "max", "ultra",
        }

    def test_explicit_max_demand_jumps_to_max(self):
        assert estimate_level("use maximum reasoning on this") == "max"
        assert estimate_level("ultra reasoning please") == "max"

    def test_code_markers_add_points(self):
        assert score_task("Schau in /home/alca/projects/main.py") >= 1

    def test_casual_greeting_never_escalates(self):
        """A plain greeting must never score above 'low' — the composite
        build-verb+target signal must not false-positive on idle chat."""
        assert estimate_level("hey, how u doing") == "low"
        assert estimate_level("what's up") == "low"

    def test_build_verb_with_path_target_escalates(self):
        """A creation verb + an explicit filesystem path is never idle
        chat, even with zero formal engineering vocabulary."""
        assert estimate_level(
            "write a website from scratch into /home/alca/site/new/"
        ) in {"high", "xhigh", "max", "ultra"}

    def test_build_verb_with_deliverable_noun_escalates(self):
        """A creation verb + a named deliverable (no path) still counts."""
        assert estimate_level("create a website for me") in {
            "medium", "high", "xhigh", "max", "ultra",
        }

    def test_bare_build_verb_alone_does_not_escalate(self):
        """'write'/'create' alone (no concrete target) must NOT trip the
        composite signal — casual asks like 'write a haiku' stay low."""
        assert estimate_level("write a haiku about the sea") == "low"

    def test_status_check_after_tool_use_escalates(self):
        """A status/continue check right after real tool-call activity in
        this conversation must clear 'low' — this is exactly the pattern
        that fabricated data on 2026-08-16 (see test below): checking on
        an active task got the SAME minimal effort as idle chat."""
        messages = [
            _msg("user", "query prices"),
            _msg("assistant", "call"),
            _msg("tool", "price data ok"),
        ]
        assert estimate_level("hows the status? i thought u keep posting...", messages=messages) in {
            "medium", "high", "xhigh", "max", "ultra",
        }

    def test_bare_status_without_tool_history_stays_low(self):
        """'status'/'continue' alone, with no recent tool activity, must
        NOT escalate — the composite gate (term + tool history) is what
        keeps this from false-positiving on ordinary chat."""
        assert estimate_level("whats the status of the weather today") == "low"
        assert estimate_level("continue") == "low"

    def test_real_2026_08_16_website_task_scores_high(self):
        """Regression guard for the actual incident (2026-08-16): a
        casually-phrased but genuinely heavy multi-file build request
        scored 'low' (task intensity ~2) before this fix, causing a
        33KB-governing-skill task to run at minimum reasoning effort."""
        text = (
            "i want u to write an website from scratch into "
            "/home/alca/website-showcase/new/ with each and everything of "
            "your cutting edge skills from this daedalus harness involved to "
            "get the idea of an beast of a ctting edge todays standards "
            "website"
        )
        assert estimate_level(text) in {"high", "xhigh", "max", "ultra"}


# ── Live hook ───────────────────────────────────────────────────────────

class TestAdjustAgent:
    def test_auto_off_does_nothing(self):
        agent = _FakeAgent(auto=False, config={"enabled": True, "effort": "max"})
        assert adjust_agent_reasoning(agent, [_msg("user", "hallo")]) is None
        assert agent.reasoning_config["effort"] == "max"

    def test_auto_starts_low(self):
        agent = _FakeAgent(auto=True, config={"enabled": True, "effort": "ultra"})
        level = adjust_agent_reasoning(agent, [_msg("user", "danke")])
        assert level == "low"
        assert agent.reasoning_config == {"enabled": True, "effort": "low"}

    def test_heavy_task_escalates(self):
        agent = _FakeAgent(auto=True, config={"enabled": True, "effort": "low"})
        text = (
            "Führe einen vollständigen Sicherheitsaudit durch: untersuche "
            "alle Schwachstellen, refaktoriere den Code, debugge die Fehler "
            "und implementiere die Fixes vollständig."
        )
        level = adjust_agent_reasoning(agent, [_msg("user", text)])
        assert level in {"medium", "high", "xhigh", "max", "ultra"}
        assert agent.reasoning_config["effort"] == level

    def test_floor_respected(self):
        agent = _FakeAgent(auto=True, floor="medium", config=None)
        level = adjust_agent_reasoning(agent, [_msg("user", "danke")])
        assert level == "medium"
        assert agent.reasoning_config == {"enabled": True, "effort": "medium"}

    def test_disabled_config_never_reenabled(self):
        agent = _FakeAgent(auto=True, config={"enabled": False})
        assert adjust_agent_reasoning(agent, [_msg("user", "hallo")]) is None
        assert agent.reasoning_config == {"enabled": False}

    def test_no_change_no_vprint(self):
        agent = _FakeAgent(auto=True, config={"enabled": True, "effort": "low"})
        adjust_agent_reasoning(agent, [_msg("user", "danke")])
        assert agent.vprint_calls == []

    def test_change_vprints(self):
        agent = _FakeAgent(auto=True, config={"enabled": True, "effort": "ultra"})
        adjust_agent_reasoning(agent, [_msg("user", "danke")])
        assert len(agent.vprint_calls) == 1
        assert "low" in agent.vprint_calls[0]

    def test_tool_round_escalates_mid_flight(self):
        """The loop calls the gauge before EVERY API call, so a task that
        grows through tool rounds gets more reasoning on the next call."""
        agent = _FakeAgent(auto=True, config={"enabled": True, "effort": "low"})
        messages = [_msg("user", "implementiere das komplette System")]
        # First pass: instruction alone.
        first = adjust_agent_reasoning(agent, messages)
        assert first in {"medium", "high", "xhigh", "max", "ultra"}
        # Tool round with errors arrives.
        messages.append(_msg("assistant", "call"))
        messages.append(_msg("tool", "Error: failed to connect"))
        messages.append(_msg("assistant", "call"))
        messages.append(_msg("tool", "Traceback: broken"))
        second = adjust_agent_reasoning(agent, messages)
        assert second is not None
        assert second == agent.reasoning_config["effort"]
