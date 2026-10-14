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
        return {"memories": 100, "connections": 0}
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
        assert "Previous session" in cc
        assert "shader approach" in cc
        assert "website showcase" not in cc, "one session's tail, never a mix of sessions"
        assert "GOAL" in cc
        assert "Review the conversation above" not in cc
        assert "20260809_000000_new" not in cc
        assert "[Prior-session context only" in cc

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
        assert len(calls) <= 5


class TestTailIsTheRealPreviousSession:
    """2026-10-14: turns spooled while the pod was down replayed days later with a
    fresh write time, so a 3-day-old cron refiner became "previous session" and the
    footer told the model to continue it. The tail now follows the session files."""

    @staticmethod
    def _session_file(sid, pairs):
        import json, os
        from pathlib import Path
        msgs = []
        for u, a in pairs:
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        path = Path(os.environ["DAEDALUS_HOME"]) / "sessions" / f"session_{sid}.json"
        path.write_text(json.dumps({"messages": msgs}))

    @staticmethod
    def _tool(rows_by_prefix):
        def _t(name, arguments, timeout=8.0):
            if name == "mazemaker_browse":
                return {"memories": rows_by_prefix.get(arguments.get("label_prefix", ""), [])}
            return {"memories": 0}
        return _t

    def test_replayed_old_turns_lose_to_the_real_previous_session(self):
        self._session_file("20261014_155834_ff904c", [("gather optuna", "done")])
        rows = {
            "auto:turn:": [{"label": "auto:turn:20261011_191359_cbde91:6acbc6ca",
                            "content": "h\n=== USER ===\nrefine seven-showcase\n\n=== ASSISTANT ===\nok"}],
            "auto:turn:20261014_155834_ff904c:": [
                {"label": "auto:turn:20261014_155834_ff904c:6acf1000",
                 "content": "h\n=== USER ===\ngather optuna branches\n\n=== ASSISTANT ===\nlisted 9"}],
        }
        with patch.object(mz, "_tool", side_effect=self._tool(rows)):
            block = mz.MazemakerMemoryProvider.__new__(mz.MazemakerMemoryProvider)._compose_resume(
                "20261014_164351_451552")
        assert "gather optuna branches" in block
        assert "seven-showcase" not in block
        assert "Previous session (started 2026-10-14 15:58)" in block

    def test_unsoaked_previous_session_comes_from_its_file(self):
        self._session_file("20261014_155834_ff904c", [("first", "a1"), ("strip secrets on tpad", "stripped")])
        with patch.object(mz, "_tool", side_effect=self._tool({})):
            block = mz.MazemakerMemoryProvider.__new__(mz.MazemakerMemoryProvider)._compose_resume(
                "20261014_164351_451552")
        assert "strip secrets on tpad" in block

    def test_a_continued_session_shows_its_own_turns(self):
        self._session_file("20261014_155834_ff904c", [("older", "x")])
        rows = {"auto:turn:20261014_164351_451552:": [
            {"label": "auto:turn:20261014_164351_451552:6acf2000",
             "content": "h\n=== USER ===\nconsolidate optuna\n\n=== ASSISTANT ===\nbranch made"}]}
        with patch.object(mz, "_tool", side_effect=self._tool(rows)):
            block = mz.MazemakerMemoryProvider.__new__(mz.MazemakerMemoryProvider)._compose_resume(
                "20261014_164351_451552")
        assert "This session so far" in block and "consolidate optuna" in block
