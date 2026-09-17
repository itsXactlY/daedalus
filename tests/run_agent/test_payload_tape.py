"""The request payload is append-only between compactions.

On the hybrid main model llama-server reuses a prompt only when the previous
prompt is an exact prefix of the new one. Measured 2026-09-17 before the tape:
every call reused exactly 12,363 tokens -- the system prompt and tool schemas
-- and re-read the whole conversation after them, because the reasoning TTL,
the tool-group collapse, the stale-result prune, the moving head window and the
turn injections all rewrote earlier messages on every call.
"""

import json

import run_agent
from agent.payload_tape import PayloadTape

_RealAIAgent = run_agent.AIAgent


class _Compressor:
    def __init__(self, threshold=65000):
        self.threshold_tokens = threshold
        self.spilled = []

    def spill_reasoning(self, content, label=""):
        self.spilled.append(content)
        return f"[offloaded: reasoning ({len(content)} chars) -> /dev/shm/r{len(self.spilled)}]"


class _Memory:
    def __init__(self, reachable=True):
        self.reachable = reachable
        self.soaked = []

    def retrieval_reachable(self):
        return self.reachable

    def soak_reasoning_all(self, text, session_id="", spill_path=""):
        self.soaked.append((text, spill_path))


def _agent(reachable=True, window_turns=-1, reasoning_window=3, tool_group_ttl=8):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.model = "qwen3.8-27b"
    a.api_mode = "chat_completions"
    a.context_compressor = _Compressor()
    a._memory_manager = _Memory(reachable)
    a._soak_window_turns = window_turns
    a._reasoning_window = reasoning_window
    a._tool_group_ttl = tool_group_ttl
    a._payload_tape_enabled = True
    a._payload_tape = PayloadTape()
    a._compaction_generation = 0
    a.session_id = "s"
    return a


def _call(a, messages, cur, injections=()):
    payload, _ = a._build_payload_messages(
        messages, cur, messages[cur]["content"], list(injections), [],
    )
    return payload


def _step(messages, i, reasoning_size=2000):
    """One agent step: an assistant message with a tool call, and its result."""
    cid = f"c{i}"
    messages.append({
        "role": "assistant", "content": "",
        "reasoning": f"thought-{i} " + "x" * reasoning_size,
        "tool_calls": [{"id": cid, "type": "function",
                        "function": {"name": "terminal",
                                     "arguments": json.dumps({"command": f"cmd-{i}"})}}],
    })
    messages.append({"role": "tool", "tool_call_id": cid, "content": f"output-{i}"})


def _is_prefix(old, new):
    return len(new) >= len(old) and json.dumps(new[:len(old)]) == json.dumps(old)


class TestThePreviousPromptStaysAPrefix:
    def test_across_many_tool_steps_past_every_ttl(self):
        a = _agent()
        messages = [{"role": "user", "content": "do the thing"}]
        prev = _call(a, messages, 0, injections=["[recall] context"])
        for i in range(20):  # far past reasoning_window=3 and tool_group_ttl=8
            _step(messages, i)
            cur = _call(a, messages, 0, injections=["[recall] context"])
            assert _is_prefix(prev, cur), f"step {i} rewrote an earlier message"
            prev = cur

    def test_across_a_new_user_turn(self):
        a = _agent(window_turns=1)
        messages = [{"role": "user", "content": "first"}]
        _step(messages, 0)
        first_turn = _call(a, messages, 0, injections=["[recall] for first"])
        messages.append({"role": "assistant", "content": "done"})
        messages.append({"role": "user", "content": "second"})
        second_turn = _call(a, messages, len(messages) - 1, injections=["[recall] for second"])
        assert _is_prefix(first_turn, second_turn)
        # last turn's injections stay where they were sent
        assert "[recall] for first" in second_turn[0]["content"]
        assert "[recall] for second" in second_turn[-1]["content"]

    def test_the_newest_reasoning_is_sent_in_full(self):
        a = _agent()
        messages = [{"role": "user", "content": "go"}]
        _call(a, messages, 0)
        for i in range(6):
            _step(messages, i)
            payload = _call(a, messages, 0)
        assert payload[-2]["reasoning_content"].startswith("thought-5 ")


class TestANewEpochOnlyWhenTheHistoryIsReplaced:
    def test_a_compaction_starts_a_new_epoch_with_hygiene(self):
        a = _agent()
        messages = [{"role": "user", "content": "go"}]
        _call(a, messages, 0)
        for i in range(12):
            _step(messages, i)
            _call(a, messages, 0)
        # a compaction hands back copies and bumps the generation
        a._compaction_generation += 1
        compacted = [m.copy() for m in messages]
        payload = _call(a, compacted, 0)
        collapsed = [m for m in payload
                     if str(m.get("content", "")).startswith("[aged out of context]")]
        assert collapsed, "the rebase must apply the tool-group TTL once"

    def test_copies_alone_do_not_pass_for_the_same_history(self):
        a = _agent()
        messages = [{"role": "user", "content": "go"}]
        _step(messages, 0)
        _call(a, messages, 0)
        blocks, _ = a._payload_tape.matched_blocks([m.copy() for m in messages], 0)
        assert blocks == 0

    def test_a_thinking_prefill_is_never_frozen(self):
        a = _agent()
        messages = [{"role": "user", "content": "go"}]
        _call(a, messages, 0)
        messages.append({"role": "assistant", "content": "partial", "_thinking_prefill": True})
        with_prefill = _call(a, messages, 0)
        assert with_prefill[-1]["content"] == "partial"
        messages.pop()
        _step(messages, 0)
        after = _call(a, messages, 0)
        assert all(m.get("content") != "partial" for m in after)


class TestRetrievalIsTheMemory:
    def test_reasoning_is_soaked_the_first_time_it_is_sent(self):
        a = _agent()
        messages = [{"role": "user", "content": "go"}]
        _call(a, messages, 0)
        _step(messages, 0)
        _call(a, messages, 0)
        _call(a, messages, 0)
        assert [t for t, _ in a._memory_manager.soaked] == [messages[1]["reasoning"]]

    def test_maze_up_aged_reasoning_is_dropped_without_a_disk_copy(self):
        a = _agent(reachable=True)
        messages = [{"role": "user", "content": "go"}]
        for i in range(6):
            _step(messages, i)
        payload = _call(a, messages, 0)  # epoch start: TTL applies once
        assert a.context_compressor.spilled == []
        with_reasoning = [m for m in payload if m.get("reasoning_content")]
        assert len(with_reasoning) == 3
        assert not any("offloaded" in str(m.get("reasoning_content")) for m in payload)

    def test_maze_down_aged_reasoning_goes_to_disk_with_a_path(self):
        a = _agent(reachable=False)
        messages = [{"role": "user", "content": "go"}]
        for i in range(6):
            _step(messages, i)
        payload = _call(a, messages, 0)
        assert len(a.context_compressor.spilled) == 3
        assert sum("offloaded" in str(m.get("reasoning_content")) for m in payload) == 3

    def test_bookkeeping_keys_never_reach_the_wire(self):
        a = _agent()
        messages = [{"role": "user", "content": "go"}]
        _call(a, messages, 0)
        _step(messages, 0)
        payload = _call(a, messages, 0)
        assert not any(k.startswith("_") for m in payload for k in m)


class TestARebaseWaitsForTheBudget:
    def _ready(self, a):
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "summary"}],
                             "snapshot_len": 0, "generation": 0, "slot": None}
        a._pinned_id_slot = None

    def test_a_ready_prep_is_held_below_the_budget(self):
        a = _agent()
        self._ready(a)
        assert a._apply_pending_hot_swap_if_ready([], tokens=40000) is None
        assert a._hot_swap_ready is not None, "the prep must be kept for later"

    def test_it_applies_at_the_budget(self):
        a = _agent()
        self._ready(a)
        assert a._apply_pending_hot_swap_if_ready([], tokens=65000) is not None
