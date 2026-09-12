"""What goes into mazemaker, and what does not.

The contract, stated by the operator: mazemaker is a signpost, not a
warehouse. Tool calls and their output never go in -- that is this session's
working material and belongs in the project's own workpath. Reasoning does:
it is what days and weeks of work accumulate into, and the one thing a later
session cannot reconstruct by reading the files.

And a turn that produced no answer is not a turn. Storing the user's question
next to "Operation interrupted: waiting for model response (43.3s elapsed)"
creates a row that matches a recall and says nothing -- a future session gets
its own question handed back and starts over from zero. That is worse than a
miss, because a miss sends it looking elsewhere.
"""

import os

import pytest

import run_agent
from plugins.memory.mazemaker import _is_non_answer


class TestNonAnswersAreNotSoaked:
    @pytest.mark.parametrize("text", [
        "Operation interrupted: waiting for model response (43.3s elapsed).",
        "Operation interrupted: retrying API call after rate limit (retry 2/5).",
        "Operation interrupted: handling API error (timeout).",
        "[Request interrupted by user]",
        "Interrupted by user before the tool ran",
        "",
        "   \n  ",
    ])
    def test_recognised(self, text):
        assert _is_non_answer(text)

    @pytest.mark.parametrize("text", [
        "The build succeeded. verts=69336, idx=104004.",
        "Operation completed: the mesh now renders.",
        "I interrupted the build because the linker flags were wrong.",
        "No response was needed here, so I moved on to the shader.",
    ])
    def test_real_answers_survive(self, text):
        assert not _is_non_answer(text), "a real answer was dropped"

    def test_the_word_interrupted_alone_is_not_enough(self):
        """It has to LEAD with the notice. An answer that merely mentions an
        interruption is still an answer."""
        assert not _is_non_answer("The run was interrupted, so I retried with -j4 and it passed.")


class TestReasoningIsSoakedButToolsAreNot:
    class _Manager:
        def __init__(self):
            self.reasoning = []

        def soak_reasoning_all(self, text, *, session_id="", spill_path=""):
            self.reasoning.append((text, session_id, spill_path))

    class _Compressor:
        def spill_reasoning(self, content, label=""):
            return f'[offloaded: reasoning ({len(content)} chars) spilled to /dev/shm/x.txt. read_file("/dev/shm/x.txt")]'

    def _agent(self, mm):
        a = run_agent.AIAgent.__new__(run_agent.AIAgent)
        a.model = "qwen3.8-27b"
        a.session_id = "sess-1"
        a._memory_manager = mm
        a.context_compressor = self._Compressor()
        a._reasoning_window = 1
        return a

    def _msgs(self, n):
        out = []
        for i in range(n):
            out.append({"role": "assistant", "content": "",
                        "reasoning": f"thought {i} " + "x" * 2000})
            out.append({"role": "tool", "tool_call_id": f"c{i}",
                        "content": "BUILD LOG " + "y" * 3000})
        return out

    def test_aged_reasoning_reaches_the_graph(self):
        mm = self._Manager()
        self._agent(mm)._reasoning_payload(self._msgs(5))
        assert len(mm.reasoning) == 4, "every block past the TTL should be soaked"
        assert all(s == "sess-1" for _, s, _ in mm.reasoning)

    def test_the_spill_path_travels_with_it(self):
        """mazemaker is the signpost; the full text stays in the workpath."""
        mm = self._Manager()
        self._agent(mm)._reasoning_payload(self._msgs(3))
        assert all(p == "/dev/shm/x.txt" for _, _, p in mm.reasoning)

    def test_tool_output_is_never_soaked(self):
        mm = self._Manager()
        self._agent(mm)._reasoning_payload(self._msgs(5))
        soaked = " ".join(t for t, _, _ in mm.reasoning)
        assert "BUILD LOG" not in soaked, "tool output must not reach the graph"

    def test_fresh_reasoning_is_not_soaked_yet(self):
        """Inside the TTL it is still in the window; soaking it now would
        write the same block twice."""
        mm = self._Manager()
        self._agent(mm)._reasoning_payload(self._msgs(1))
        assert mm.reasoning == []

    def test_a_broken_memory_manager_does_not_break_the_turn(self):
        class _Boom:
            def soak_reasoning_all(self, *a, **k):
                raise RuntimeError("pod down")

        out = self._agent(_Boom())._reasoning_payload(self._msgs(4))
        assert len(out) == 4

    def test_no_memory_manager_is_fine(self):
        a = self._agent(None)
        assert len(a._reasoning_payload(self._msgs(3))) == 3


class TestTheWorkpathIsBesideTheProject:
    def test_it_uses_a_dedicated_spill_dir_in_the_working_directory(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DAEDALUS_SPILL_ROOT", raising=False)
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        assert run_agent.AIAgent._spill_root() == str(tmp_path / ".daedalus" / "spill")

    def test_it_falls_back_when_the_workdir_is_unusable(self, monkeypatch):
        monkeypatch.delenv("DAEDALUS_SPILL_ROOT", raising=False)
        monkeypatch.setenv("TERMINAL_CWD", "/proc/nonexistent/nope")
        monkeypatch.setattr(os, "getcwd", lambda: "/proc/nonexistent/nope")
        assert "daedalus-ctx-" in run_agent.AIAgent._spill_root()

    def test_the_env_override_still_wins(self, monkeypatch, tmp_path):
        """conftest relies on this to keep the suite out of a live root."""
        monkeypatch.setenv("DAEDALUS_SPILL_ROOT", str(tmp_path / "iso"))
        monkeypatch.setenv("TERMINAL_CWD", "/home/somewhere")
        assert run_agent.AIAgent._spill_root() == str(tmp_path / "iso")


class TestItCanNeverLandOnDaedalusHome:
    """purge_stale_spills rmtree's whole subdirectories of the spill root.

    An earlier version returned <workdir>/.daedalus directly. The agent's
    working directory is $HOME, so that resolved to the operator's real
    ~/.daedalus -- and the purge deleted venv/, cron/ and logs/ out of it.
    The spill root must be a directory daedalus owns outright, and it must
    never be, or sit inside, DAEDALUS_HOME.
    """

    def test_a_workdir_whose_dot_daedalus_is_the_home_is_refused(self, monkeypatch, tmp_path):
        home = tmp_path / ".daedalus"
        home.mkdir()
        monkeypatch.delenv("DAEDALUS_SPILL_ROOT", raising=False)
        monkeypatch.setenv("DAEDALUS_HOME", str(home))
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        root = os.path.realpath(run_agent.AIAgent._spill_root())
        # With the separator, not a bare string prefix: ".daedalus-spill" is
        # a prefix-match of ".daedalus" and is NOT inside it. Getting that
        # wrong here is the same mistake that, in the code, would have let
        # the purge loose on DAEDALUS_HOME.
        real_home = os.path.realpath(str(home))
        assert root != real_home and not root.startswith(real_home + os.sep), (
            f"spill root sits in DAEDALUS_HOME: {root}"
        )
        # The sibling on disk is preferred over volatile RAM.
        assert root == os.path.realpath(str(tmp_path / ".daedalus-spill"))

    def test_a_different_project_is_still_fine(self, monkeypatch, tmp_path):
        home = tmp_path / "home" / ".daedalus"
        home.mkdir(parents=True)
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.delenv("DAEDALUS_SPILL_ROOT", raising=False)
        monkeypatch.setenv("DAEDALUS_HOME", str(home))
        monkeypatch.setenv("TERMINAL_CWD", str(proj))
        assert run_agent.AIAgent._spill_root() == str(proj / ".daedalus" / "spill")


class TestThePurgeRefusesForeignDirectories:
    def test_an_unmarked_root_is_left_alone(self, monkeypatch, tmp_path):
        """Exactly the shape of ~/.daedalus: real directories, no marker."""
        monkeypatch.setenv("DAEDALUS_SPILL_ROOT", str(tmp_path))
        for name in ("venv", "cron", "logs", "sessions"):
            (tmp_path / name).mkdir()
        assert run_agent.AIAgent.purge_stale_spills(max_age_seconds=0) == 0
        for name in ("venv", "cron", "logs", "sessions"):
            assert (tmp_path / name).is_dir(), f"{name} was deleted from an unmarked root"

    def test_a_marked_root_is_purged_normally(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DAEDALUS_SPILL_ROOT", str(tmp_path))
        (tmp_path / run_agent.AIAgent._SPILL_MARKER).write_text("x")
        (tmp_path / "old-session").mkdir()
        assert run_agent.AIAgent.purge_stale_spills(max_age_seconds=0) >= 1
        assert not (tmp_path / "old-session").exists()

    def test_writing_a_spill_lays_down_the_marker(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DAEDALUS_SPILL_ROOT", str(tmp_path))
        run_agent.AIAgent._archive_context_chunk("s1", 0, "terminal", "output")
        assert (tmp_path / run_agent.AIAgent._SPILL_MARKER).is_file()
