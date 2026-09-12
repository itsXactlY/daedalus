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

# Captured at import. Patch THIS, never run_agent.AIAgent: other suites
# (tests/cron/test_codex_execution_paths.py, test_anthropic_error_handling.py)
# swap the module attribute for a stub, and a test that instantiates the
# captured class while patching the module attribute is patching a different
# object -- the real _prime_slot_with_messages then runs, fails to reach a
# server, and the prep records no warm slot. Green alone, red in a full run.
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
    a._hot_swap_enabled = True    # default is off; tests opt in explicitly
    a._hot_swap_prefill = True
    a._hot_swap_in_progress = False
    a._hot_swap_ready = None
    a._compaction_generation = 0
    a._hot_swap_prep_ratio = 0.75
    a._pinned_id_slot = 1
    a._slot_count_cache = 2   # a real -np 2 server; see _server_slot_count
    a._cached_system_prompt = "sys"
    for k, v in over.items():
        setattr(a, k, v)
    return a


def _msgs(n):
    return [{"role": "user", "content": f"m{i}"} for i in range(n)]


class TestPrepTrigger:
    """Prep runs on a daemon thread, so these used to assert after a fixed
    time.sleep(0.05). Under a loaded test run the thread was not always
    scheduled inside that window and the assertions flapped -- green alone,
    red in a full-suite run. They wait on an Event now; nothing here depends
    on how quickly the machine gets round to the thread."""

    def test_below_ratio_does_not_start(self, monkeypatch):
        a = _agent()
        started = threading.Event()
        monkeypatch.setattr(_RealAIAgent, "_run_hot_swap_prep",
                            lambda self, *args: started.set())
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 700, "t")  # 700 < 750
        # A negative: give a thread that should never run real time to prove it.
        assert not started.wait(0.5)
        assert a._hot_swap_in_progress is False

    def test_at_ratio_starts_once(self, monkeypatch):
        a = _agent()
        started = []
        entered = threading.Event()
        release = threading.Event()

        def fake(self, *args):
            started.append(1)
            entered.set()
            release.wait(5.0)
            self._hot_swap_in_progress = False

        monkeypatch.setattr(_RealAIAgent, "_run_hot_swap_prep", fake)
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 800, "t")
        assert entered.wait(5.0), "prep thread never started"

        # Prep is now demonstrably in flight; a second trigger must not fork.
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 900, "t")
        assert not entered.wait(0.3) or len(started) == 1
        assert started == [1]
        release.set()

    def test_disabled_never_starts(self, monkeypatch):
        a = _agent(_hot_swap_enabled=False)
        started = threading.Event()
        monkeypatch.setattr(_RealAIAgent, "_run_hot_swap_prep",
                            lambda self, *args: started.set())
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 5000, "t")
        assert not started.wait(0.5)


class TestPrep:
    def test_stores_result_and_warm_slot(self, monkeypatch):
        a = _agent()
        monkeypatch.setattr(_RealAIAgent, "_prime_slot_with_messages",
                            lambda self, slot, c, s: True)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert a._hot_swap_ready is not None
        assert a._hot_swap_ready["snapshot_len"] == 6
        assert a._hot_swap_ready["slot"] == 0        # sidekick, main is 1
        assert a._hot_swap_in_progress is False

    def test_prefill_failure_keeps_the_summary(self, monkeypatch):
        a = _agent()
        monkeypatch.setattr(_RealAIAgent, "_prime_slot_with_messages",
                            lambda self, slot, c, s: False)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert a._hot_swap_ready is not None          # summary still usable
        assert a._hot_swap_ready["slot"] is None      # but no slot to promote

    def test_compaction_during_prep_discards_it(self, monkeypatch):
        a = _agent()

        def bump_then_ok(self, slot, c, s):
            self._compaction_generation += 1          # a compaction raced us
            return True

        monkeypatch.setattr(_RealAIAgent, "_prime_slot_with_messages", bump_then_ok)
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


class TestSingleSlotServer:
    """-np 1 leaves only slot 0. Pinning main to 1 there is not a soft failure:
    get_available_slot() matches nothing and the task is deferred, never run."""

    def test_main_clamps_to_an_existing_slot(self):
        a = _agent(_slot_count_cache=1)
        assert a._effective_main_slot() == 0

    def test_sidekick_collapses_to_zero(self):
        a = _agent(_slot_count_cache=1)
        assert a._sidekick_id_slot() == 0

    def test_two_slot_server_keeps_the_split(self):
        a = _agent(_slot_count_cache=2)
        assert a._effective_main_slot() == 1
        assert a._sidekick_id_slot() == 0


class TestDefaultsOff:
    """Prep competes with main for a shared, bounded resident KV pool. On a
    1024 MiB pool it starved: 19+ minutes for one summary, and main dropped to
    24% cache. Off unless asked for."""

    def test_disabled_agent_never_starts_prep(self, monkeypatch):
        a = _agent(_hot_swap_enabled=False)
        started = threading.Event()
        monkeypatch.setattr(_RealAIAgent, "_run_hot_swap_prep",
                            lambda self, *args: started.set())
        a._maybe_start_hot_swap_prep(_msgs(5), "sys", 10**6, "t")
        assert not started.wait(0.5)

    def test_prefill_is_separately_opt_in(self, monkeypatch):
        a = _agent(_hot_swap_prefill=False)
        called = []
        monkeypatch.setattr(_RealAIAgent, "_prime_slot_with_messages",
                            lambda self, slot, c, s: called.append(1) or True)
        a._run_hot_swap_prep(_msgs(6), "sys", 900, "t", 0)
        assert called == []                       # summary computed, no prefill
        assert a._hot_swap_ready is not None       # still usable
        assert a._hot_swap_ready["slot"] is None   # nothing warmed, so no swap


class TestSlotProbeDoesNotCacheFailure:
    """llama-server takes tens of seconds to load a 27B plus a draft model.
    An agent started alongside it reaches /slots before the server answers.

    Caching that miss pinned the process to single-slot for its whole life --
    main and the sidekick both landing on slot 0 -- and no later restart of
    the server could undo it. That is the "one slot doing everything"
    symptom, arriving purely from startup order.
    """

    def _probing_agent(self, responses):
        """responses: a list popped per probe; an Exception instance raises."""
        a = _agent()
        del a._slot_count_cache
        a._slot_probe_last = 0.0
        seen = []

        class _Resp:
            def __init__(self, n):
                self._n = n

            def read(self):
                import json
                return json.dumps([{"id": i} for i in range(self._n)]).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        import urllib.request
        def fake_urlopen(url, timeout=None):
            seen.append(url)
            nxt = responses.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return _Resp(nxt)

        return a, fake_urlopen, seen

    def test_failed_probe_is_retried_not_remembered(self, monkeypatch):
        import urllib.request
        a, fake, seen = self._probing_agent([OSError("connection refused"), 2])
        monkeypatch.setattr(urllib.request, "urlopen", fake)

        assert a._server_slot_count() == 1          # server still loading
        assert getattr(a, "_slot_count_cache", None) is None

        a._slot_probe_last = 0.0                    # past the retry interval
        assert a._server_slot_count() == 2          # server is up now
        assert a._slot_count_cache == 2
        assert len(seen) == 2

    def test_retry_is_rate_limited(self, monkeypatch):
        import urllib.request
        a, fake, seen = self._probing_agent([OSError("refused")])
        monkeypatch.setattr(urllib.request, "urlopen", fake)

        assert a._server_slot_count() == 1
        assert a._server_slot_count() == 1   # inside the window: no second probe
        assert len(seen) == 1, "a down server must not cost a timeout per call"

    def test_successful_probe_is_cached(self, monkeypatch):
        import urllib.request
        a, fake, seen = self._probing_agent([2])
        monkeypatch.setattr(urllib.request, "urlopen", fake)

        assert a._server_slot_count() == 2
        assert a._server_slot_count() == 2
        assert len(seen) == 1

    def test_main_and_sidekick_split_once_the_server_answers(self, monkeypatch):
        import urllib.request
        a, fake, _ = self._probing_agent([OSError("refused"), 2])
        monkeypatch.setattr(urllib.request, "urlopen", fake)

        assert a._effective_main_slot() == 0   # collapsed while the server loads
        assert a._sidekick_id_slot() == 0

        a._slot_probe_last = 0.0
        assert a._effective_main_slot() == 1   # and recovers, rather than staying stuck
        assert a._sidekick_id_slot() == 0

    def test_remote_backend_is_cached_as_single_slot(self, monkeypatch):
        a = _agent(base_url="https://api.example.com/v1")
        del a._slot_count_cache
        a._slot_probe_last = 0.0
        assert a._server_slot_count() == 1
        assert a._slot_count_cache == 1        # no server to come up later
