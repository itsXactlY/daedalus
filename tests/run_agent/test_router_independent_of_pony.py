"""Retrieval is the agent's, not pony's.

The mazemaker router used to be constructed inside build_pony_mode(), and
only when pony was enabled. A persona switch therefore decided whether the
harness recalled anything at all -- in a design whose whole premise is that
the agent carries no history of its own and must recall it.

Worse, the fallback that would have fetched memory another way was gated on
`not _ext_prefetch_cache`, and pony's environment block alone made that
non-empty. So with pony on and the router returning nothing, the turn got no
memory from either path.
"""

import run_agent

_RealAIAgent = run_agent.AIAgent


class _Router:
    def __init__(self, text="RECALLED", raises=None):
        self.text, self.raises, self.calls = text, raises, 0

    def fetch(self, turn):
        self.calls += 1
        if self.raises:
            raise self.raises
        return type("M", (), {"text": self.text})()


class _Needs:
    def __init__(self, material=True):
        self._material = material
        self.seen = []

    def assess(self, turn):
        self.seen.append(turn)
        return type("N", (), {"material": self._material, "tools": False})()


def _agent(router=None, needs=None, **over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a._maze_router = router
    a._maze_needs = needs
    for k, v in over.items():
        setattr(a, k, v)
    return a


class TestRetrievalDoesNotDependOnPony:
    def test_material_is_fetched_with_pony_absent(self):
        r = _Router()
        a = _agent(router=r, _pony_mode=None)
        assert a._fetch_maze_material("continue the build") == "RECALLED"
        assert r.calls == 1

    def test_material_is_fetched_with_pony_disabled(self):
        r = _Router()
        a = _agent(router=r, _pony_mode=type("P", (), {"enabled": False})())
        assert a._fetch_maze_material("continue the build") == "RECALLED"

    def test_no_router_is_not_an_error(self):
        assert _agent(router=None)._fetch_maze_material("x") == ""

    def test_an_empty_turn_is_not_routed(self):
        r = _Router()
        assert _agent(router=r)._fetch_maze_material("   ") == ""
        assert r.calls == 0

    def test_a_dead_pod_is_non_fatal(self):
        r = _Router(raises=RuntimeError("pod down"))
        assert _agent(router=r)._fetch_maze_material("continue") == ""


class TestTheNeedsGate:
    def test_a_trivial_turn_is_not_routed(self):
        r, n = _Router(), _Needs(material=False)
        assert _agent(router=r, needs=n)._fetch_maze_material("ok") == ""
        assert r.calls == 0, "a greeting must not cost a pod round-trip"

    def test_a_real_turn_is_routed(self):
        r, n = _Router(), _Needs(material=True)
        assert _agent(router=r, needs=n)._fetch_maze_material("weiter") == "RECALLED"
        assert r.calls == 1

    def test_a_broken_gate_routes_rather_than_going_silent(self):
        class _Boom:
            def assess(self, turn):
                raise ValueError("bad regex")

        r = _Router()
        assert _agent(router=r, needs=_Boom())._fetch_maze_material("go on") == "RECALLED"


class TestTheGateDefaultsToRetrieving:
    """These exact turns returned material=False under the old heuristic --
    the canonical recall triggers were the only ones guaranteed to get none."""

    def _needs(self):
        from agent.maze_router import HeuristicNeeds
        return HeuristicNeeds()

    def test_continuations_ask_for_material(self):
        n = self._needs()
        for turn in ("continue", "weiter", "mach weiter", "go on", "finish it",
                     "push it", "fix the mesh generation bug"):
            assert n.assess(turn).material, f"{turn!r} must trigger a recall"

    def test_greetings_and_acks_still_do_not(self):
        n = self._needs()
        for turn in ("ok", "thanks", "danke", "hi", "lol", "nice", "yes"):
            assert not n.assess(turn).material, f"{turn!r} must not cost a round-trip"


class TestWiring:
    def _source(self):
        import inspect
        return open(inspect.getsourcefile(run_agent), encoding="utf-8").read().splitlines()

    def test_the_router_is_built_outside_the_pony_block(self):
        """Comments are stripped first -- the one above the call explains why
        this is NOT pony's, and would otherwise trip the check itself."""
        lines = self._source()
        built = [i for i, l in enumerate(lines) if "router_from_config(" in l]
        assert built, "the agent never builds a router of its own"
        for i in built:
            code = [l for l in lines[max(0, i - 12): i]
                    if l.strip() and not l.strip().startswith("#")]
            assert not any("pony" in l.lower() for l in code), (
                "router construction sits inside the pony branch again:\n"
                + "\n".join(code)
            )

    def test_the_fallback_keys_on_material_not_on_the_blob(self):
        """`not _ext_prefetch_cache` was the bug: pony's environment block
        alone made it non-empty, so the fallback could not run even when
        nothing had been recalled."""
        lines = self._source()
        i = next(i for i, l in enumerate(lines) if "_memory_manager" in l and "not _" in l)
        assert "not _material" in lines[i], lines[i]

    def test_pony_no_longer_supplies_material(self):
        lines = self._source()
        assert not any("material_for(" in l for l in lines), (
            "run_agent is taking material from pony again"
        )
