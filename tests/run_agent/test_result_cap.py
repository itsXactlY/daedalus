"""A tool result enters the payload capped; one batch shares one budget.

2026-10-15, Strata at 65,536: six parallel 450-line doc reads took a subagent
from 30k to 69,591 tokens. The server refused the request, the window was
stepped down to 64k and then 32k, the compaction check read "50,132 -> 61,253"
and 'list_files' was repaired into 'write_file'.

While the maze answers nothing goes to disk and no path enters the payload:
Mazemaker is the history, a cut result is a narrower call away.
"""

import json
import os

import run_agent
from agent.context_compressor import ContextCompressor

_RealAIAgent = run_agent.AIAgent

STRATA_ERR = ("HTTP 400: request exceeds the context window: prompt (69591 tokens) "
              "leaves no room to answer in the context (65536); requests are never "
              "truncated")


class _Memory:
    def __init__(self, reachable):
        self.reachable = reachable

    def retrieval_reachable(self):
        return self.reachable


def _agent(tmp_path, monkeypatch, ctx=65536, maze=True):
    root = str(tmp_path / "spill")
    monkeypatch.setattr(_RealAIAgent, "_spill_root", classmethod(lambda cls: root))
    c = ContextCompressor(model="test/model", quiet_mode=True)
    c.session_label = "20261015_000000_cafebabe"
    c.archiver = _RealAIAgent._archive_context_chunk
    c.context_length = ctx
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.context_compressor = c
    a.api_mode = "chat_completions"
    a.model = "qwen3.8-flash-next-coder-iq1_m"
    a._memory_manager = _Memory(maze)
    return a


def _doc(i, lines=450):
    body = "\n".join(f"{n:6d}|doc {i} line {n}: the pod publishes 8765 and 5432 on loopback"
                     for n in range(1, lines + 1))
    return json.dumps({"content": body, "total_lines": 2172, "file_size": 90000})


def _batch(tool, contents, args=lambda i: {}):
    calls = [{"id": f"c{i}", "type": "function",
              "function": {"name": tool, "arguments": json.dumps(args(i))}}
             for i in range(len(contents))]
    msgs = [{"role": "user", "content": "summarize the docs"},
            {"role": "assistant", "content": "", "tool_calls": calls}]
    msgs += [{"role": "tool", "tool_call_id": f"c{i}", "content": c}
             for i, c in enumerate(contents)]
    return msgs


def _render(agent, msgs, msg):
    out = agent._render_payload_message(msg, is_current=False, reasoning_text=None,
                                        injections=[], bootstrap_messages=[], source=msgs)
    return out[0]["content"]


class TestABatchSharesOneBudget:
    def test_six_parallel_reads_fit_the_window_together(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("read_file", [_doc(i) for i in range(6)],
                      args=lambda i: {"path": f"/docs/D{i}.md", "offset": 1, "limit": 450})
        raw = sum(len(m["content"]) for m in msgs if m["role"] == "tool")
        assert raw / 4 > 65536 * 0.5, "the batch as it was would not fit"
        rendered = [_render(a, msgs, m) for m in msgs if m["role"] == "tool"]
        assert sum(len(r) for r in rendered) / 4 < 65536 * 0.45

    def test_a_read_continues_in_the_file_itself(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("read_file", [_doc(i) for i in range(6)],
                      args=lambda i: {"path": f"/docs/D{i}.md", "offset": 1, "limit": 450})
        out = _render(a, msgs, msgs[2])
        head, marker = out.split(_RealAIAgent._RESULT_CUT)
        last = int(head.rstrip().rsplit("\n", 1)[-1].split("|")[0])
        assert f'read_file(path="/docs/D0.md", offset={last + 1}' in marker
        assert f"Lines {last + 1}-450" in marker
        assert not os.path.exists(tmp_path / "spill"), "the file is its own spill"

    def test_a_small_result_is_untouched(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("terminal", ['{"output": "ok"}'])
        assert _render(a, msgs, msgs[2]) == '{"output": "ok"}'

    def test_the_rendering_is_stable_for_the_tape(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("execute_code", [json.dumps({"output": "x" * 60000})])
        assert _render(a, msgs, msgs[2]) == _render(a, msgs, msgs[2])

    def test_with_the_maze_up_nothing_goes_to_disk(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("execute_code", [json.dumps({"output": "row\n" * 20000})])
        out = _render(a, msgs, msgs[2])
        assert "narrower call" in out
        assert "read_file(" not in out
        assert not os.path.exists(tmp_path / "spill")
        assert a.context_compressor.offloaded == []

    def test_a_dead_maze_falls_back_to_disk_as_readable_text(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch, maze=False)
        text = "\n".join(f"section {n}: the release pushes through the tunnel"
                         for n in range(3000))
        msgs = _batch("execute_code", [json.dumps({"status": "success", "output": text})])
        out = _render(a, msgs, msgs[2])
        path = out.split('read_file("', 1)[1].split('"', 1)[0]
        with open(path) as f:
            assert f.read() == text, "the spill is the output, not its JSON envelope"
        assert [e["path"] for e in a.context_compressor.offloaded] == [path]

    def test_a_denser_tokenizer_shrinks_the_budget(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        before = a._result_budget_chars(6)
        a._note_token_ratio(69591, 50132)
        assert a._result_budget_chars(6) < before / 1.3


class TestTheNextRequestIsCountedBeforeItIsSent:
    def test_pending_results_are_counted_as_rendered(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("read_file", [_doc(i) for i in range(6)],
                      args=lambda i: {"path": f"/docs/D{i}.md"})
        pending = a._pending_result_tokens(msgs)
        assert 65536 * 0.3 < pending < 65536 * 0.45

    def test_nothing_pending_after_an_answer(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        msgs = _batch("terminal", ["x" * 9000]) + [{"role": "assistant", "content": "done"}]
        assert a._pending_result_tokens(msgs) == 0


class TestAConfirmedWindowIsNotSteppedDown:
    def test_strata_names_window_and_prompt(self):
        from agent.model_metadata import (
            parse_context_limit_from_error, parse_prompt_tokens_from_error)
        assert parse_context_limit_from_error(STRATA_ERR) == 65536
        assert parse_prompt_tokens_from_error(STRATA_ERR) == 69591

    def test_the_same_window_stays(self):
        assert _RealAIAgent._stepped_window(65536, STRATA_ERR) == (None, 65536)

    def test_a_smaller_window_is_adopted(self):
        err = "request (77649 tokens) exceeds the available context size (40960 tokens)"
        assert _RealAIAgent._stepped_window(65536, err) == (40960, 40960)

    def test_an_unnamed_window_still_probes(self):
        new, named = _RealAIAgent._stepped_window(65536, "context length exceeded")
        assert named is None and new is not None and new < 65536


class TestRepairKeepsTheVerb:
    def _agent(self):
        a = _RealAIAgent.__new__(_RealAIAgent)
        a.valid_tool_names = {"read_file", "write_file", "search_files", "terminal",
                              "mazemaker"}
        return a

    def test_list_files_is_not_a_write(self):
        assert self._agent()._repair_tool_call("list_files") is None

    def test_typos_are_still_repaired(self):
        a = self._agent()
        assert a._repair_tool_call("read_files") == "read_file"
        assert a._repair_tool_call("Read-File") == "read_file"
        assert a._repair_tool_call("raed_file") == "read_file"

    def test_a_sub_tool_lands_on_its_dispatcher(self):
        assert self._agent()._repair_tool_call("mazemaker_get") == "mazemaker"


class TestOldResultsLeaveAsALine:
    def _conversation(self, groups=4):
        msgs = [{"role": "user", "content": "build it"}]
        for i in range(groups):
            msgs.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": f"c{i}", "type": "function",
                 "function": {"name": "terminal", "arguments": json.dumps({"command": f"ls {i}"})}}]})
            msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "entry\n" * 400})
        return msgs

    def test_with_the_maze_up_an_old_result_names_its_call_and_nothing_else(
            self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        out = a._spill_tool_results(self._conversation())
        old = [m["content"] for m in out[:5] if m["role"] == "tool"]
        assert all(c.startswith(_RealAIAgent._RESULT_LEFT) for c in old)
        assert all("run the call again" in c and "read_file(" not in c for c in old)
        assert out[-1]["content"] == "entry\n" * 400, "the newest exchanges stay"
        assert not os.path.exists(tmp_path / "spill")

    def test_a_dead_maze_still_spills(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch, maze=False)
        out = a._spill_tool_results(self._conversation())
        assert "[SPILLED RESULT" in out[2]["content"]


class TestTheTurnNoteNamesCallsNotPaths:
    def test_dropped_calls_are_named_and_nothing_is_written(self, tmp_path, monkeypatch):
        a = _agent(tmp_path, monkeypatch)
        dropped = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "x", "type": "function", "function": {
                    "name": "execute_code", "arguments": json.dumps({"code": "print(1)"})}}]},
            {"role": "tool", "tool_call_id": "x", "content": json.dumps({"output": "r\n" * 900})},
        ]
        note = a._turn_so_far_note(dropped)
        assert "execute_code" in note and "read_file(" not in note
        assert not os.path.exists(tmp_path / "spill")
