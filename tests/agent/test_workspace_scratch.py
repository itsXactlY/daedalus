"""Scratch output stays with the project, not in the shared /tmp.

Observed: the agent ran `cmake --build build > /tmp/build.log 2>&1` and
`> /tmp/cmake_cfg.log`. On this machine /tmp is a RAM-backed tmpfs shared
with the user, and filling it does not degrade gracefully -- it takes the
shell down for every process on the box, the agent included, mid-task. It
happened during this project's own development.

Two halves, because one does not cover the other:
  - a command that names /tmp lands there whatever the environment says,
    so the prompt has to say not to;
  - everything that calls tempfile or mkstemp follows TMPDIR, and no prompt
    rule reaches inside a compiler.
"""

import os
import shutil

import run_agent
from agent.prompt_builder import WORKSPACE_GUIDANCE


class TestTheRule:
    def test_it_names_tmp_as_the_thing_to_avoid(self):
        assert "/tmp" in WORKSPACE_GUIDANCE

    def test_it_says_where_to_write_instead(self):
        assert "build directory" in WORKSPACE_GUIDANCE or "inside the project" in WORKSPACE_GUIDANCE

    def test_it_gives_a_concrete_example(self):
        """Abstract advice loses to a habit. A worked line does not."""
        assert "build/build.log" in WORKSPACE_GUIDANCE

    def test_it_explains_the_consequence_not_just_the_rule(self):
        assert "tmpfs" in WORKSPACE_GUIDANCE
        assert "shell down" in WORKSPACE_GUIDANCE

    def test_it_points_at_tmpdir_for_genuinely_disposable_files(self):
        assert "$TMPDIR" in WORKSPACE_GUIDANCE


class TestItReachesThePrompt:
    def _prompt(self, tools):
        from unittest.mock import MagicMock, patch
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

    def test_present_when_the_agent_can_run_commands(self):
        assert "# Scratch files stay with the project" in self._prompt(("terminal",))

    def test_absent_when_it_cannot(self):
        """No shell, no scratch files, no reason to spend the tokens."""
        assert "# Scratch files stay with the project" not in self._prompt(("memory",))


class TestTmpdirRedirect:
    def _cleanup(self, path):
        if path:
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    def test_it_moves_tmpdir_off_the_shared_tmp(self, monkeypatch):
        monkeypatch.setenv("TMPDIR", "/tmp")
        path = run_agent.AIAgent._redirect_tmpdir("sess-a")
        try:
            assert path and not path.startswith("/tmp")
            assert os.environ["TMPDIR"] == path
        finally:
            self._cleanup(path)

    def test_it_sets_the_other_two_names_too(self, monkeypatch):
        """Not everything reads TMPDIR; TMP and TEMP are both in the wild."""
        path = run_agent.AIAgent._redirect_tmpdir("sess-b")
        try:
            assert os.environ["TMP"] == path == os.environ["TEMP"]
        finally:
            self._cleanup(path)

    def test_the_directory_exists_and_is_private(self, monkeypatch):
        path = run_agent.AIAgent._redirect_tmpdir("sess-c")
        try:
            assert os.path.isdir(path)
            assert oct(os.stat(path).st_mode)[-3:] == "700"
        finally:
            self._cleanup(path)

    def test_sessions_do_not_share_a_directory(self, monkeypatch):
        a = run_agent.AIAgent._redirect_tmpdir("sess-d")
        b = run_agent.AIAgent._redirect_tmpdir("sess-e")
        try:
            assert a != b
        finally:
            self._cleanup(a)
            self._cleanup(b)

    def test_a_hostile_session_id_cannot_escape_the_root(self, monkeypatch):
        path = run_agent.AIAgent._redirect_tmpdir("../../../etc/evil")
        try:
            assert run_agent.AIAgent._spill_root() in path
            assert ".." not in path
        finally:
            self._cleanup(path)

    def test_an_unwritable_root_leaves_tmpdir_alone(self, monkeypatch):
        """Better the shared /tmp than a TMPDIR pointing at nothing."""
        monkeypatch.setenv("TMPDIR", "/tmp")
        monkeypatch.setattr(run_agent.AIAgent, "_spill_root",
                            staticmethod(lambda: "/proc/nonexistent/nope"))
        assert run_agent.AIAgent._redirect_tmpdir("sess-f") == ""
        assert os.environ["TMPDIR"] == "/tmp"
