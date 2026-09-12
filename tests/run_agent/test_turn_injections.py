"""Per-turn context injections are built once, not once per API call.

The blocks land on the current turn's USER message, which sits ahead of that
turn's tool calls and results. Rebuilding them mid-turn rewrites a message the
entire tail is cached against, so llama.cpp re-prefills everything after it on
every iteration -- a twenty-tool-call turn pays it twenty times.

Two blocks were genuinely unstable: the mazemaker history pointer (it embeds a
live "down for N seconds" duration while the pod is wedged, and is a pod
round-trip besides) and the spill notice (changes the moment a result is
offloaded mid-turn).
"""

import run_agent

_RealAIAgent = run_agent.AIAgent


class _Compressor:
    def __init__(self, notice=""):
        self.notice = notice
        self.calls = 0

    def offload_notice(self):
        self.calls += 1
        return self.notice


class _MemoryManager:
    """history_pointer_all is a network call to the pod; count every one."""

    def __init__(self, pointer="stored in mazemaker"):
        self._pointer = pointer
        self.calls = 0

    def history_pointer_all(self, *, session_id=""):
        self.calls += 1
        # Mimics the wedged-pod pointer, which embeds a live duration.
        return f"{self._pointer} ({self.calls}s)"


def _agent(**over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.session_id = "sess"
    a.verbose_logging = False
    a._soak_window_turns = 3
    a._memory_manager = _MemoryManager()
    a.context_compressor = _Compressor()
    a._skill_route_block = ""
    for k, v in over.items():
        setattr(a, k, v)
    return a


class TestBuiltOncePerTurn:
    def test_one_pod_round_trip_per_call_not_per_iteration(self):
        a = _agent()
        a._build_turn_injections("", "")
        assert a._memory_manager.calls == 1
        assert a.context_compressor.calls == 1

    def test_the_block_is_a_stable_snapshot(self):
        """Two builds differ (the pointer ticks) -- which is exactly why the
        caller must build once and reuse, rather than call per iteration."""
        a = _agent()
        first = a._build_turn_injections("", "")
        second = a._build_turn_injections("", "")
        assert first != second, (
            "the pointer is time-varying; if this ever becomes stable the "
            "hoist is still correct, but the round-trip argument stands"
        )


class TestContents:
    def test_includes_each_configured_block(self):
        a = _agent(_skill_route_block="ROUTED SKILLS")
        a.context_compressor = _Compressor(notice="moved x to /dev/shm/x")
        out = "\n".join(a._build_turn_injections("RECALLED", "PLUGIN CTX"))
        assert "RECALLED" in out
        assert "[mazemaker]" in out
        assert "[context spill] moved x to /dev/shm/x" in out
        assert "PLUGIN CTX" in out
        assert "ROUTED SKILLS" in out

    def test_empty_when_nothing_to_say(self):
        a = _agent(_soak_window_turns=-1, _memory_manager=None)
        assert a._build_turn_injections("", "") == []

    def test_pointer_skipped_when_soak_is_off(self):
        a = _agent(_soak_window_turns=-1)
        a._build_turn_injections("", "")
        assert a._memory_manager.calls == 0

    def test_a_failing_pod_does_not_break_the_turn(self):
        class _Boom:
            def history_pointer_all(self, *, session_id=""):
                raise OSError("pod unreachable")

        a = _agent(_memory_manager=_Boom())
        out = a._build_turn_injections("RECALLED", "")
        assert len(out) == 1 and "RECALLED" in out[0]   # fenced by build_memory_context_block
        assert not any("[mazemaker]" in b for b in out)

    def test_a_failing_compressor_does_not_break_the_turn(self):
        class _Boom:
            def offload_notice(self):
                raise RuntimeError("compressor down")

        a = _agent(context_compressor=_Boom())
        out = a._build_turn_injections("", "")
        assert any("[mazemaker]" in b for b in out)


class TestWiredIntoTheLoop:
    """Structural: the injection build must sit OUTSIDE the per-API-call loop.

    This is wiring, not logic -- the same class of mistake as the hot-swap
    being hooked only into the preflight path. Guard it by position.
    """

    def _source(self):
        import inspect
        return open(inspect.getsourcefile(run_agent), encoding="utf-8").read().splitlines()

    def test_build_is_not_inside_the_iteration_loop(self):
        lines = self._source()
        builds = [i for i, l in enumerate(lines)
                  if "_build_turn_injections(" in l and "def " not in l]
        assert builds, "no call site found"
        loops = [i for i, l in enumerate(lines)
                 if "while api_call_count < self.max_iterations" in l]
        assert loops, "iteration loop not found"
        for b in builds:
            nearest = [l for l in loops if l < b]
            if not nearest:
                continue
            # A call after a loop header must be indented no deeper than the
            # header itself, i.e. it is not in the loop body.
            header_indent = len(lines[nearest[-1]]) - len(lines[nearest[-1]].lstrip())
            call_indent = len(lines[b]) - len(lines[b].lstrip())
            assert call_indent <= header_indent, (
                f"line {b+1} builds injections inside the per-API-call loop; "
                "that re-prefills the turn's whole tail on every iteration"
            )
