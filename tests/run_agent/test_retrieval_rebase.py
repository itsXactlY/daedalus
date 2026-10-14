"""Rebase from retrieval, driven by the fast layer's watermarks.

2026-09-17: a background LLM summary of ~41k tokens timed out after six minutes
on the sidekick slot and the middle of the conversation was dropped with nothing
in its place, while the fast layer (157 pages of 256 tokens at a 1,024 MiB stage,
shared by both slots) had long since overflowed into host RAM.
"""

import json

import run_agent
from agent.kv_watermarks import HARD, HIGH, LOW, OK, Watermarks
from agent.payload_tape import PayloadTape

_RealAIAgent = run_agent.AIAgent


class _Compressor:
    protect_last_n = 6
    threshold_tokens = 36000
    context_length = 132352

    def _align_boundary_backward(self, messages, idx):
        while 0 < idx < len(messages) and messages[idx].get("role") == "tool":
            idx -= 1
        return idx

    def compress(self, *a, **k):
        raise AssertionError("the summarizer must not run")


class _Memory:
    def __init__(self, reachable=True):
        self.reachable = reachable
        self.queries = []

    def retrieval_reachable(self):
        return self.reachable

    def prefetch_all(self, query, session_id=""):
        self.queries.append(query)
        return "RECALLED: the pod lives in ~/projects/pulse-pro"


def _agent(**over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.model = "qwen3.8-27b"
    a.api_mode = "chat_completions"
    a.base_url = "http://127.0.0.1:8080/v1"
    a.session_id = "s1"
    a.context_compressor = _Compressor()
    a._memory_manager = _Memory()
    a._compaction_engine = "retrieval"
    a._todo_store = None
    a._last_state_summary_body = ""
    a._hot_swap_in_progress = False
    a._hot_swap_ready = None
    a._hot_swap_enabled = True
    a._compaction_generation = 0
    a._pinned_id_slot = 1
    a._slot_count_cache = 2
    for k, v in over.items():
        setattr(a, k, v)
    return a


def _conversation(steps=10):
    msgs = [{"role": "user", "content": "old question"},
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "where is the pulse pod?"}]
    for i in range(steps):
        cid = f"c{i}"
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": cid, "type": "function",
             "function": {"name": "terminal", "arguments": json.dumps({"command": f"ls {i}"})}}]})
        msgs.append({"role": "tool", "tool_call_id": cid, "content": f"out {i}"})
    return msgs


class TestTheBaseIsBuiltFromRetrieval:
    def test_question_first_then_note_then_tail(self):
        a = _agent()
        msgs = _conversation()
        base = a._build_retrieval_base(msgs)
        assert base[0] is msgs[2]
        assert base[1]["display_kind"] == "hidden"
        assert "auto:turn:s1:*" in base[1]["content"]
        assert "RECALLED: the pod lives" in base[1]["content"]
        assert a._memory_manager.queries == ["where is the pulse pod?"]
        assert base[2:] == msgs[-6:]

    def test_the_tail_never_starts_on_an_orphaned_tool_result(self):
        a = _agent()
        a.context_compressor.protect_last_n = 5
        base = a._build_retrieval_base(_conversation())
        assert base[2]["role"] != "tool"

    def test_no_recall_when_the_maze_is_down(self):
        a = _agent(_memory_manager=_Memory(reachable=False))
        base = a._build_retrieval_base(_conversation())
        assert "RECALLED" not in base[1]["content"]

    def test_no_empty_state_card(self):
        a = _agent()
        assert a._build_state_card() == ""
        base = a._build_retrieval_base(_conversation())
        assert "STATE CARD" not in base[1]["content"]

    def test_old_turns_are_left_to_the_maze(self):
        base = _agent()._build_retrieval_base(_conversation())
        assert all(m.get("content") != "old question" for m in base)


class TestWatermarks:
    def test_levels(self):
        wm = Watermarks(fast_layer_tokens=40192)
        assert wm.level(10_000) == OK
        assert wm.level(25_000) == LOW
        assert wm.level(33_000) == HIGH
        assert wm.level(37_000) == HARD
        assert wm.hard_tokens == int(40192 * 0.9)

    def test_pool_counts_what_the_sidekick_slot_still_holds(self, monkeypatch):
        a = _agent(_watermarks=Watermarks(fast_layer_tokens=40192))
        slots = [{"id": 0, "n_prompt_tokens": 12000, "is_processing": False},
                 {"id": 1, "n_prompt_tokens": 20000, "is_processing": True}]
        monkeypatch.setattr("agent.kv_watermarks.read_slots", lambda base_url: slots)
        assert a._kv_pool_tokens(20000) == 32000

    def test_low_watermark_erases_an_idle_sidekick(self, monkeypatch):
        a = _agent(_watermarks=Watermarks(fast_layer_tokens=40192))
        a._last_slots = [{"id": 0, "n_prompt_tokens": 12000, "is_processing": False}]
        erased = []
        monkeypatch.setattr("agent.kv_watermarks.erase_slot",
                            lambda base_url, slot: erased.append(slot) or True)
        a._kv_free_idle_sidekick(26000)
        assert erased == [0]

    def test_a_prewarmed_turn0_is_never_erased(self, monkeypatch):
        a = _agent(_watermarks=Watermarks(fast_layer_tokens=40192))
        a._hot_swap_ready = {"slot": 0}
        a._last_slots = [{"id": 0, "n_prompt_tokens": 9000, "is_processing": False}]
        erased = []
        monkeypatch.setattr("agent.kv_watermarks.erase_slot",
                            lambda base_url, slot: erased.append(slot) or True)
        a._kv_free_idle_sidekick(38000)
        assert erased == []

    def test_below_low_nothing_is_touched(self, monkeypatch):
        a = _agent(_watermarks=Watermarks(fast_layer_tokens=40192))
        a._last_slots = [{"id": 0, "n_prompt_tokens": 12000, "is_processing": False}]
        erased = []
        monkeypatch.setattr("agent.kv_watermarks.erase_slot",
                            lambda base_url, slot: erased.append(slot) or True)
        a._kv_free_idle_sidekick(15000)
        assert erased == []


class TestNothingBlocksTheRebase:
    def test_at_the_limit_a_retrieval_rebase_runs_now(self):
        a = _agent()
        assert a._defer_compaction_to_background(37000, [], "", "t") is False

    def test_a_prime_in_flight_is_waited_for(self, monkeypatch):
        a = _agent(_hot_swap_in_progress=True)
        monkeypatch.setattr(a, "_maybe_start_hot_swap_prep", lambda *x, **k: None)
        assert a._defer_compaction_to_background(37000, [], "", "t") is True

    def test_the_swap_erases_the_slot_main_left(self, monkeypatch):
        a = _agent(_payload_tape_enabled=True, _payload_tape=PayloadTape())
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "q"}],
                             "snapshot_len": 0, "generation": 0, "slot": 0}
        erased = []
        monkeypatch.setattr("agent.kv_watermarks.erase_slot",
                            lambda base_url, slot: erased.append(slot) or True)
        merged = a._apply_pending_hot_swap_if_ready([], tokens=37000)
        assert merged is not None
        assert a._pinned_id_slot == 0
        assert erased == [1]


class TestPrewarmOnlyBetweenTurns:
    def test_mid_turn_prep_does_not_start(self, monkeypatch):
        a = _agent(_hot_swap_prep_ratio=0.8)
        started = []
        monkeypatch.setattr("threading.Thread.start", lambda self: started.append(1))
        a._maybe_start_hot_swap_prep([], "sys", 35000, "t")
        assert started == []

    def test_between_turns_it_starts(self, monkeypatch):
        a = _agent(_hot_swap_prep_ratio=0.8)
        started = []
        monkeypatch.setattr("threading.Thread.start", lambda self: started.append(1))
        a._maybe_start_hot_swap_prep([], "sys", 35000, "t", between_turns=True)
        assert started == [1]

    def test_applying_or_discarding_the_swap_releases_the_slot(self, monkeypatch):
        from agent.sidekick_queue import sidekick_gate
        a = _agent(_payload_tape_enabled=True, _payload_tape=PayloadTape())
        monkeypatch.setattr("agent.kv_watermarks.erase_slot", lambda base_url, slot: True)
        sidekick_gate.reserve(60)
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "q"}],
                             "snapshot_len": 0, "generation": 0, "slot": 0}
        a._apply_pending_hot_swap_if_ready([], tokens=37000)
        assert not sidekick_gate.reserved()
