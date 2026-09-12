"""Slot hot-swap: background compaction prep and the turn-boundary swap.

See docs/slot-hot-swap-design.md. The properties that matter:

- prep never blocks a turn and never runs twice concurrently
- a compaction landing while prep runs invalidates it, rather than the prep
  overwriting a history it no longer describes
- turns appended after the snapshot survive the swap
- prefill failure degrades to "summary only", it does not lose the prep
- the swap moves main to the warm slot and the sidekick follows
"""

import threading
import time

import run_agent

_RealAIAgent = run_agent.AIAgent


class _Compressor:
    def __init__(self, threshold=1000):
        self.threshold_tokens = threshold
        self.protect_first_n = 1
        self.protect_last_n = 1
        self.calls = []

    def compress(self, messages, current_tokens=None):
        self.calls.append(len(messages))
        return [{"role": "user", "content": "SUMMARY"}]


def _agent(**over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.base_url = "http://127.0.0.1:8080/v1"
    a.context_compressor = _Compressor()
    a._hot_swap_enabled = True
    a._hot_swap_in_progress = False
    a._hot_swap_ready = None
    a._compaction_generation = 0
    a._hot_swap_prep_ratio = 0.75
    a._pinned_id_slot = 1
    a._cached_system_prompt = "sys"
    for k, v in over.items():
        setattr(a, k, v)
    return a


def _msgs(n):
    return [{"role": "user", "content": f"m{i}"} for i in range(n)]


class TestPrepTrigger:
    def test_below_ratio_does_not_start(self, monkeypatch):
        a = _agent()
        started = []
        monkeypatch.setattr(run_agent.AIAgent, "_run_hot_swap_prep",
                            lambda self, *args: started.append(1))
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 700, "t")  # 700 < 750
        time.sleep(0.05)
        assert started == []
        assert a._hot_swap_in_progress is False

    def test_at_ratio_starts_once(self, monkeypatch):
        a = _agent()
        started = []
        done = threading.Event()

        def fake(self, *args):
            started.append(1)
            done.wait(2.0)
            self._hot_swap_in_progress = False

        monkeypatch.setattr(run_agent.AIAgent, "_run_hot_swap_prep", fake)
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 800, "t")
        time.sleep(0.05)
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 900, "t")  # must not double-start
        time.sleep(0.05)
        assert started == [1]
        done.set()

    def test_disabled_never_starts(self, monkeypatch):
        a = _agent(_hot_swap_enabled=False)
        started = []
        monkeypatch.setattr(run_agent.AIAgent, "_run_hot_swap_prep",
                            lambda self, *args: started.append(1))
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 5000, "t")
        time.sleep(0.05)
        assert started == []


class TestPrep:
    def test_stores_result_and_warm_slot(self, monkeypatch):
        a = _agent()
        monkeypatch.setattr(run_agent.AIAgent, "_prime_slot_with_messages",
                            lambda self, slot, c, s: True)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert a._hot_swap_ready is not None
        assert a._hot_swap_ready["snapshot_len"] == 6
        assert a._hot_swap_ready["slot"] == 0        # sidekick, main is 1
        assert a._hot_swap_in_progress is False

    def test_prefill_failure_keeps_the_summary(self, monkeypatch):
        a = _agent()
        monkeypatch.setattr(run_agent.AIAgent, "_prime_slot_with_messages",
                            lambda self, slot, c, s: False)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert a._hot_swap_ready is not None          # summary still usable
        assert a._hot_swap_ready["slot"] is None      # but no slot to promote

    def test_compaction_during_prep_discards_it(self, monkeypatch):
        a = _agent()

        def bump_then_ok(self, slot, c, s):
            self._compaction_generation += 1          # a compaction raced us
            return True

        monkeypatch.setattr(run_agent.AIAgent, "_prime_slot_with_messages", bump_then_ok)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert a._hot_swap_ready is None

    def test_failure_clears_the_in_progress_flag(self, monkeypatch):
        a = _agent()
        a._hot_swap_in_progress = True

        def boom(self, messages, current_tokens=None):
            raise RuntimeError("summarizer down")

        monkeypatch.setattr(_Compressor, "compress", boom)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert a._hot_swap_ready is None
        assert a._hot_swap_in_progress is False       # a later attempt can run


class TestApply:
    def test_carries_forward_turns_added_since_the_snapshot(self):
        a = _agent()
        a._hot_swap_ready = {
            "compressed": [{"role": "user", "content": "SUMMARY"}],
            "snapshot_len": 4, "generation": 0, "slot": 0,
        }
        live = _msgs(4) + [{"role": "user", "content": "after-1"},
                           {"role": "user", "content": "after-2"}]
        merged = a._apply_pending_hot_swap_if_ready(live)
        assert [m["content"] for m in merged] == ["SUMMARY", "after-1", "after-2"]

    def test_swap_moves_main_and_publishes_the_new_sidekick(self, monkeypatch):
        import agent.auxiliary_client as aux
        monkeypatch.setattr(aux, "_SIDEKICK_ID_SLOT", 0, raising=False)
        a = _agent()
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "S"}],
                             "snapshot_len": 2, "generation": 0, "slot": 0}
        a._apply_pending_hot_swap_if_ready(_msgs(2))
        assert a._pinned_id_slot == 0          # main promoted to the warm slot
        assert aux.get_sidekick_id_slot() == 1  # hygiene follows to the other
        assert a._sidekick_id_slot() == 1

    def test_no_slot_means_no_swap_but_still_applies(self):
        a = _agent()
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "S"}],
                             "snapshot_len": 2, "generation": 0, "slot": None}
        merged = a._apply_pending_hot_swap_if_ready(_msgs(2))
        assert merged is not None
        assert a._pinned_id_slot == 1          # unchanged

    def test_stale_generation_is_refused(self):
        a = _agent()
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "S"}],
                             "snapshot_len": 2, "generation": 0, "slot": 0}
        a._compaction_generation = 1           # a compaction landed meanwhile
        assert a._apply_pending_hot_swap_if_ready(_msgs(2)) is None
        assert a._pinned_id_slot == 1

    def test_history_shorter_than_snapshot_is_refused(self):
        a = _agent()
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "S"}],
                             "snapshot_len": 9, "generation": 0, "slot": 0}
        assert a._apply_pending_hot_swap_if_ready(_msgs(3)) is None

    def test_nothing_ready_is_a_noop(self):
        a = _agent()
        assert a._apply_pending_hot_swap_if_ready(_msgs(3)) is None

    def test_applying_consumes_it(self):
        a = _agent()
        a._hot_swap_ready = {"compressed": [{"role": "user", "content": "S"}],
                             "snapshot_len": 2, "generation": 0, "slot": None}
        assert a._apply_pending_hot_swap_if_ready(_msgs(2)) is not None
        assert a._apply_pending_hot_swap_if_ready(_msgs(2)) is None


class TestPrefillGuard:
    def test_remote_backend_is_not_prefilled(self):
        a = _agent(base_url="https://api.example.com/v1")
        assert a._prime_slot_with_messages(0, [{"role": "user", "content": "x"}], "sys") is False


class TestWiredIntoThePathThatActuallyFires:
    """The first version hooked only the preflight check at the top of a turn.

    In a real session that path fired 3 times while the mid-turn path -- after
    tool results are posted, inside the iteration loop -- fired 60. The feature
    was live for days of log and never once ran. Wiring, not logic, so guard it
    structurally: both hot-swap calls must sit next to the should_compress()
    trigger that actually decides to compact.
    """

    def _source(self):
        import inspect
        return inspect.getsourcefile(run_agent), open(
            inspect.getsourcefile(run_agent), encoding="utf-8"
        ).read().splitlines()

    def test_hooks_surround_the_real_compaction_trigger(self):
        _, lines = self._source()
        trigger = [i for i, l in enumerate(lines) if "should_compress(" in l and "def " not in l]
        assert trigger, "should_compress() call site not found"

        for t in trigger:
            window = "\n".join(lines[max(0, t - 30): t + 30])
            assert "_apply_pending_hot_swap_if_ready(" in window, (
                f"no hot-swap apply near the should_compress() trigger at line {t+1}; "
                "the feature will never run on this path"
            )
            assert "_maybe_start_hot_swap_prep(" in window, (
                f"no hot-swap prep start near the should_compress() trigger at line {t+1}"
            )

    def test_prep_is_reachable_from_more_than_the_preflight_path(self):
        _, lines = self._source()
        starts = [i for i, l in enumerate(lines) if "_maybe_start_hot_swap_prep(" in l and "def " not in l]
        assert len(starts) >= 2, (
            "prep is wired into only one call path; the preflight check alone is "
            "not where compaction fires in practice"
        )
