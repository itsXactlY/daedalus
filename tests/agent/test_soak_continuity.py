"""Tests for cross-session continuity in the mazemaker soak provider.

Every fresh daedalus session seeds its system prompt with a continuity block —
the previous session's tail (auto:turn soaks) plus curated open-work goals
(decision:/status:/project:/ops: memories) — so the agent picks up where the
last session left off instead of starting from absolute scratch. Always-on,
pod-down safe (empty block on failure).
"""

from unittest.mock import patch

import plugins.memory.mazemaker as mz


def _mock_browse_response():
    """A fake mazemaker_browse result: two prior sessions + one bg-review nudge."""
    return {
        "memories": [
            {
                "id": 1001,
                "label": "auto:turn:20260809_010203_aaa:6a1",
                "content": "session:20260809_010203_aaa @ 2026-08-09T08:00:00Z\n\n=== USER ===\nplan the website showcase with mazemaker for context\n\n=== ASSISTANT ===\nhere is the plan",
            },
            {
                "id": 1002,
                "label": "auto:turn:20260809_010204_bbb:6a2",
                "content": "session:20260809_010204_bbb @ 2026-08-09T08:01:00Z\n\n=== USER ===\nReview the conversation above and consider saving or updating a skill if appropriate.",
            },
            {
                "id": 1003,
                "label": "auto:turn:20260809_010204_bbb:6a3",
                "content": "session:20260809_010204_bbb @ 2026-08-09T08:02:00Z\n\n=== USER ===\nrefine the shader approach\n\n=== ASSISTANT ===\nkeep three.webgpu local",
            },
        ]
    }


def _mock_goal_hit():
    """A fake curated goal hit the recall would return."""
    return [{
        "id": 2001,
        "label": "decision:showcase-full-website-2026-08-09",
        "similarity": 0.8,
        "content": "GOAL: mazemaker production site must serve the full /website/ experience.",
    }]


def _mock_tool(name, arguments, timeout=8.0):
    """Dispatch per tool name: stats → ready, auto:turn browse → turns, decision/ops browse → goals."""
    if name == "mazemaker_stats":
        return {"memories": 100, "connections": 0}  # brain ready
    if name == "mazemaker_browse":
        if arguments.get("label_prefix", "") == "auto:turn:":
            return _mock_browse_response()
        return {"memories": _mock_goal_hit()}
    return []


class TestContinuity:
    def test_seeds_from_prior_session(self):
        """A fresh session gets prior-session turns + open goals as continuity."""
        with patch.object(mz, "_tool", side_effect=_mock_tool):
            p = mz.MazemakerMemoryProvider()
            p.initialize("20260809_000000_new")
            cc = p.continuity_context()
        assert "Previous session" in cc              # tail section header
        assert "website showcase" in cc              # genuine turn present
        assert "shader approach" in cc               # genuine second turn present
        assert "GOAL" in cc                          # goals section present
        assert "Review the conversation above" not in cc  # bg-review filtered
        assert "20260809_000000_new" not in cc       # own session excluded
        assert "[Prior-session context only" in cc   # guidance footer present

    def test_no_history_returns_empty(self):
        """No prior turns → no continuity block."""
        with patch.object(mz, "_tool", return_value={"memories": []}):
            p = mz.MazemakerMemoryProvider()
            p.initialize("20260809_000000_new")
            cc = p.continuity_context()
        assert cc == ""

    def test_pod_down_returns_empty(self):
        """A pod failure degrades continuity to empty, never raises."""
        with patch.object(mz, "_tool", side_effect=TimeoutError("down")):
            p = mz.MazemakerMemoryProvider()
            p.initialize("20260809_000000_new")
            cc = p.continuity_context()
        assert cc == ""

    def test_cache_is_once_per_session(self):
        """The block is composed once and cached for the session."""
        calls = []

        def counting_tool(name, arguments, timeout=8.0):
            calls.append(name)
            return _mock_tool(name, arguments, timeout=timeout)

        with patch.object(mz, "_tool", side_effect=counting_tool):
            p = mz.MazemakerMemoryProvider()
            p.initialize("20260809_000000_new")
            first = p.continuity_context()
            second = p.continuity_context()
        assert first == second
        # init probe(stats) + tail browse + decision browse [+ ops browse]
        assert len(calls) <= 5
