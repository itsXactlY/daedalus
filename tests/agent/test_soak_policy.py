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
    def test_it_uses_a_dotted_dir_in_the_working_directory(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DAEDALUS_SPILL_ROOT", raising=False)
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        root = run_agent.AIAgent._spill_root()
        assert root == str(tmp_path / ".daedalus")

    def test_it_falls_back_when_the_workdir_is_unusable(self, monkeypatch):
        monkeypatch.delenv("DAEDALUS_SPILL_ROOT", raising=False)
        monkeypatch.setenv("TERMINAL_CWD", "/proc/nonexistent/nope")
        monkeypatch.setattr(os, "getcwd", lambda: "/proc/nonexistent/nope")
        root = run_agent.AIAgent._spill_root()
        assert "daedalus-ctx-" in root, "a volatile spill beats no spill at all"

    def test_the_env_override_still_wins(self, monkeypatch, tmp_path):
        """conftest relies on this to keep the suite out of a live root."""
        monkeypatch.setenv("DAEDALUS_SPILL_ROOT", str(tmp_path / "iso"))
        monkeypatch.setenv("TERMINAL_CWD", "/home/somewhere")
        assert run_agent.AIAgent._spill_root() == str(tmp_path / "iso")
