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
    def test_it_moves_tmpdir_off_the_shared_tmp(self, monkeypatch):
        """The contract is "not the shared system temp dir", not "nowhere
        below /tmp" -- under test the spill root is itself an mkdtemp under
        /tmp, and that is fine: it is private to this run."""
        import tempfile
        monkeypatch.setenv("TMPDIR", tempfile.gettempdir())
        path = run_agent.AIAgent._redirect_tmpdir()
        assert path
        assert os.path.realpath(path) != os.path.realpath(tempfile.gettempdir())
        assert path.startswith(run_agent.AIAgent._spill_root())
        assert os.environ["TMPDIR"] == path

    def test_it_sets_the_other_two_names_too(self):
        """Not everything reads TMPDIR; TMP and TEMP are both in the wild."""
        path = run_agent.AIAgent._redirect_tmpdir()
        assert os.environ["TMP"] == path == os.environ["TEMP"]

    def test_the_directory_exists_and_is_private(self):
        path = run_agent.AIAgent._redirect_tmpdir()
        assert os.path.isdir(path)
        assert oct(os.stat(path).st_mode)[-3:] == "700"

    def test_one_directory_per_process_not_per_agent(self):
        """Keyed on the session id, this made a directory for every auxiliary
        AIAgent daedalus builds -- 467 empty ones in /dev/shm within an hour,
        the same littering it was added to stop, one mount across."""
        first = run_agent.AIAgent._redirect_tmpdir()
        second = run_agent.AIAgent._redirect_tmpdir()
        assert first == second

    def test_the_purge_does_not_delete_it(self, monkeypatch, tmp_path):
        """TMPDIR points here for the life of the process. Purging it would
        leave every child process writing into a path that no longer exists."""
        monkeypatch.setenv("DAEDALUS_SPILL_ROOT", str(tmp_path))
        path = run_agent.AIAgent._redirect_tmpdir()
        (tmp_path / "some-old-session").mkdir()
        run_agent.AIAgent.purge_stale_spills(max_age_seconds=0)
        assert os.path.isdir(path), "the purge removed the process TMPDIR"
        assert not (tmp_path / "some-old-session").exists()

    def test_an_unwritable_root_leaves_tmpdir_alone(self, monkeypatch):
        """Better the shared /tmp than a TMPDIR pointing at nothing."""
        monkeypatch.setenv("TMPDIR", "/tmp")
        monkeypatch.setattr(run_agent.AIAgent, "_spill_root",
                            staticmethod(lambda: "/proc/nonexistent/nope"))
        assert run_agent.AIAgent._redirect_tmpdir() == ""
        assert os.environ["TMPDIR"] == "/tmp"
