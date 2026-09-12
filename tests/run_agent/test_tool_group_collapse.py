"""Finished tool exchanges collapse to a line saying what happened.

Tool calls are the largest thing left in the payload that nothing prunes.
Measured over four ten-hour sessions: ~700 calls each, carrying ~50k tokens
of pure JSON envelope (id, type, the function wrapper -- no semantic content
whatsoever) plus 145k-180k tokens of arguments, of which only 10% are large
enough to reach the spill floor. The median argument is 338 characters: far
too small to be worth its own spill handle, far too numerous to keep.

So the unit is the exchange, not the argument. A finished exchange goes as a
whole -- the assistant message carrying the calls AND the tool results
answering it -- replaced by one line naming each call and where its result
was spilled. Dropping one side alone would orphan the other, which
chat-completions rejects.
"""

import json

import run_agent

_RealAIAgent = run_agent.AIAgent


def _agent(**over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    for k, v in over.items():
        setattr(a, k, v)
    return a


def _group(i, name="terminal", arg=None, spill=None, n_calls=1):
    """One assistant-with-tool_calls message plus its tool results."""
    calls, results = [], []
    for k in range(n_calls):
        cid = f"c{i}_{k}"
        args = json.dumps(arg if arg is not None else {"command": f"cmd-{i}-{k}"})
        calls.append({"id": cid, "type": "function",
                      "function": {"name": name, "arguments": args}})
        results.append({"role": "tool", "tool_call_id": cid,
                        "content": spill or f"output-{i}-{k}"})
    return [{"role": "assistant", "content": "", "tool_calls": calls}] + results


def _convo(n_groups, **kw):
    msgs = [{"role": "user", "content": "build it"}]
    for i in range(n_groups):
        msgs += _group(i, **kw)
    return msgs


class TestCollapse:
    def test_under_the_ttl_nothing_changes(self):
        a = _agent(_tool_group_ttl=8)
        msgs = _convo(5)
        assert a._collapse_aged_tool_groups(msgs) is msgs

    def test_older_groups_collapse_newest_survive(self):
        a = _agent(_tool_group_ttl=3)
        msgs = _convo(10)
        out = a._collapse_aged_tool_groups(msgs)
        surviving = [m for m in out if m.get("tool_calls")]
        assert len(surviving) == 3
        collapsed = [m for m in out if str(m.get("content", "")).startswith("[aged out")]
        assert len(collapsed) == 7

    def test_both_halves_go_together(self):
        """Dropping an assistant's tool_calls while keeping its tool results
        orphans them, and chat-completions rejects that."""
        a = _agent(_tool_group_ttl=2)
        out = a._collapse_aged_tool_groups(_convo(8))
        live_ids = set()
        for m in out:
            for c in m.get("tool_calls") or []:
                live_ids.add(c["id"])
        for m in out:
            if m.get("role") == "tool":
                assert m["tool_call_id"] in live_ids, "orphaned tool result"

    def test_the_user_message_is_never_removed(self):
        a = _agent(_tool_group_ttl=1)
        out = a._collapse_aged_tool_groups(_convo(9))
        assert any(m.get("role") == "user" for m in out)

    def test_collapsed_line_names_what_was_done(self):
        a = _agent(_tool_group_ttl=1)
        msgs = _convo(6, name="patch", arg={"file_path": "src/world.cpp"})
        out = a._collapse_aged_tool_groups(msgs)
        line = next(m["content"] for m in out if str(m.get("content", "")).startswith("[aged out"))
        assert "patch(src/world.cpp)" in line, (
            "a hole in the history invites the agent to redo the work"
        )

    def test_it_carries_the_spill_path_when_there_is_one(self):
        a = _agent(_tool_group_ttl=1)
        msgs = _convo(5, spill='[offloaded: read_file — spilled to /dev/shm/daedalus-ctx/s/0001-read.txt.]')
        out = a._collapse_aged_tool_groups(msgs)
        line = next(m["content"] for m in out if str(m.get("content", "")).startswith("[aged out"))
        assert "/dev/shm/daedalus-ctx/s/0001-read.txt" in line
        assert "read_file(path)" in line

    def test_multi_call_groups_list_every_call(self):
        a = _agent(_tool_group_ttl=1)
        out = a._collapse_aged_tool_groups(_convo(4, n_calls=3))
        line = next(m["content"] for m in out if str(m.get("content", "")).startswith("[aged out"))
        assert line.count("terminal(") == 3

    def test_ttl_zero_collapses_everything(self):
        a = _agent(_tool_group_ttl=0)
        out = a._collapse_aged_tool_groups(_convo(6))
        assert not any(m.get("tool_calls") for m in out)
        assert not any(m.get("role") == "tool" for m in out)

    def test_the_transcript_is_not_mutated(self):
        a = _agent(_tool_group_ttl=2)
        msgs = _convo(8)
        snapshot = json.dumps(msgs, sort_keys=True)
        a._collapse_aged_tool_groups(msgs)
        assert json.dumps(msgs, sort_keys=True) == snapshot, (
            "the session log, /resume and mazemaker read this list"
        )

    def test_a_conversation_with_no_tool_calls_is_untouched(self):
        a = _agent(_tool_group_ttl=0)
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        assert a._collapse_aged_tool_groups(msgs) is msgs

    def test_interleaved_plain_assistant_messages_survive(self):
        a = _agent(_tool_group_ttl=1)
        msgs = [{"role": "user", "content": "go"}]
        for i in range(5):
            msgs += _group(i)
            msgs.append({"role": "assistant", "content": f"note-{i}"})
        out = a._collapse_aged_tool_groups(msgs)
        for i in range(5):
            assert any(m.get("content") == f"note-{i}" for m in out)


class TestDescribeToolCall:
    def test_prefers_an_identifying_argument(self):
        c = {"function": {"name": "patch",
                          "arguments": json.dumps({"foo": "bar", "file_path": "a/b.cpp"})}}
        assert _RealAIAgent._describe_tool_call(c) == "patch(a/b.cpp)"

    def test_falls_back_to_any_string_argument(self):
        c = {"function": {"name": "weird", "arguments": json.dumps({"zzz": "value"})}}
        assert _RealAIAgent._describe_tool_call(c) == "weird(value)"

    def test_no_arguments_still_names_the_tool(self):
        c = {"function": {"name": "list", "arguments": "{}"}}
        assert _RealAIAgent._describe_tool_call(c) == "list()"

    def test_long_arguments_are_truncated(self):
        c = {"function": {"name": "terminal",
                          "arguments": json.dumps({"command": "x" * 500})}}
        out = _RealAIAgent._describe_tool_call(c)
        assert len(out) < 90 and out.endswith("...)")

    def test_unparseable_arguments_do_not_raise(self):
        c = {"function": {"name": "broken", "arguments": "{not json"}}
        assert "broken(" in _RealAIAgent._describe_tool_call(c)

    def test_newlines_are_flattened(self):
        c = {"function": {"name": "terminal",
                          "arguments": json.dumps({"command": "a\nb\nc"})}}
        assert "\n" not in _RealAIAgent._describe_tool_call(c)


class TestWiredIntoThePayload:
    def _source(self):
        import inspect
        return open(inspect.getsourcefile(run_agent), encoding="utf-8").read().splitlines()

    def test_collapse_runs_before_the_payload_is_built(self):
        lines = self._source()
        calls = [i for i, l in enumerate(lines)
                 if "_collapse_aged_tool_groups(" in l and "def " not in l]
        assert calls, "never called"
        loops = [i for i, l in enumerate(lines) if "for idx, msg in enumerate(_iter_messages)" in l]
        assert loops
        assert min(calls) < min(loops), "must collapse before indexing into the list"

    def test_the_current_index_is_remapped_by_identity(self):
        """Collapsing removes messages ahead of _iter_cur, so a stored index
        would point at the wrong message and the turn injections would land
        on a tool result instead of the user's question."""
        lines = self._source()
        call = next(i for i, l in enumerate(lines)
                    if "_collapse_aged_tool_groups(" in l and "def " not in l)
        window = "\n".join(lines[max(0, call - 10): call + 14])
        assert "_pre_collapse_anchor" in window
        assert "is _pre_collapse_anchor" in window, "remap must compare identity, not equality"


class TestSpillPathExtraction:
    """The bare path in a spill handle is followed by a full stop --
    "spilled to /path/x.txt. Read it back with read_file(...)" -- so a greedy
    match on the first occurrence captures the stop as part of the filename.
    Every collapsed tool-group line and every reasoning pointer carried it.
    """

    _HANDLE = ('[offloaded: read_file — result (4200 chars) spilled to '
               '/home/p/.daedalus/s/0007-read_file.txt. Retrieve it verbatim '
               'with read_file("/home/p/.daedalus/s/0007-read_file.txt").]')

    def test_the_trailing_full_stop_is_not_part_of_the_path(self):
        got = _RealAIAgent._spill_path_in(self._HANDLE)
        assert got == "/home/p/.daedalus/s/0007-read_file.txt"
        assert not got.endswith(".txt.")

    def test_it_prefers_the_quoted_form(self):
        got = _RealAIAgent._spill_path_in(self._HANDLE)
        assert got.endswith("0007-read_file.txt")

    def test_a_bare_path_still_works(self):
        got = _RealAIAgent._spill_path_in("moved to /var/x/y.txt, carry on")
        assert got == "/var/x/y.txt"

    def test_plain_content_yields_nothing(self):
        assert _RealAIAgent._spill_path_in("just some output") == ""

    def test_non_string_is_safe(self):
        assert _RealAIAgent._spill_path_in(None) == ""
        assert _RealAIAgent._spill_path_in({"a": 1}) == ""

    def test_a_project_local_workpath_is_found_too(self):
        """Spills moved off /dev/shm into <project>/.daedalus; an extractor
        hardcoded to /dev/shm/ would silently stop finding them."""
        got = _RealAIAgent._spill_path_in(
            'spilled to /home/alca/projects/mc-clone/.daedalus/sess/0003-terminal.txt.')
        assert got == "/home/alca/projects/mc-clone/.daedalus/sess/0003-terminal.txt"
