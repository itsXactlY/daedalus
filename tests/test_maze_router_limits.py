"""The pod caps recall limit at 50 and answers 422 above it.

routing.hits_per_angle 15 * overfetch 4 = 60. Every single turn asked for
60, got 422, and MazeRouter.fetch() swallows PodError and returns empty
material -- so the agent received zero recalled context, silently, with
nothing in the log. Months of prompt wording and gating changes were
adjustments to a wire that was not connected.

Clamped at the client, not in the budget: a budget is a preference, this is
the API's hard edge, and crossing it does not degrade gracefully.
"""

import pytest

from agent.maze_router import Budget, HttpPodClient, MazeRouter, PodError


class _Recorder:
    """Stands in for the pod; records what limit it was asked for."""

    def __init__(self, cap=50):
        self.cap = cap
        self.limits = []

    def _call(self, name, arguments, timeout_s):
        # recall uses "limit"; recall_multi uses "k".
        limit = arguments.get("limit", arguments.get("k"))
        self.limits.append(limit)
        if limit is not None and limit > self.cap:
            raise PodError(f"{name}: HTTP Error 422: Unprocessable Entity")
        return [{"id": i, "label": f"l{i}", "content": "c", "similarity": 0.5}
                for i in range(1, (limit or 0) + 1)]


def _client(cap=50):
    c = HttpPodClient.__new__(HttpPodClient)
    c._url = "http://unused/tools/call"
    rec = _Recorder(cap)
    c._call = rec._call
    return c, rec


class TestTheLimitIsClamped:
    def test_an_over_budget_request_is_clamped_not_rejected(self):
        c, rec = _client()
        hits = c.recall("q", 60, 5.0)
        assert rec.limits == [50]
        assert len(hits) == 50

    def test_recall_multi_is_not_capped(self):
        """mazemaker_recall_multi declares no maximum on `k`. Imposing one
        here would quietly cost breadth across angles for no reason."""
        c, rec = _client(cap=10_000)
        c.recall_multi(["a", "b"], 60, 5.0)
        assert rec.limits == [60]

    def test_a_request_under_the_cap_is_untouched(self):
        c, rec = _client()
        c.recall("q", 20, 5.0)
        assert rec.limits == [20]

    def test_zero_and_negative_become_one(self):
        """A budget of 0 would ask for nothing and look identical to a miss."""
        c, rec = _client()
        c.recall("q", 0, 5.0)
        c.recall("q", -5, 5.0)
        assert rec.limits == [1, 1]

    def test_memory_id_zero_is_not_dropped(self):
        """`r.get("id") or r.get("memory_id")` treats a real key of 0 as
        absent and silently loses that row."""
        from agent.maze_router import HttpPodClient as H
        hits = H._as_hits([{"id": 0, "label": "zero", "content": "c", "similarity": 0.9}])
        assert [h.memory_id for h in hits] == [0]

    def test_the_cap_matches_the_pod_schema(self):
        assert HttpPodClient.MAX_RECALL_LIMIT == 50


class TestTheRealBudgetWouldHaveFailed:
    def test_the_shipped_routing_config_exceeds_the_cap(self):
        """hits_per_angle 15 * overfetch 4 = 60. This is not a hypothetical
        configuration -- it is what ~/.daedalus/config.yaml carries."""
        b = Budget(hits_per_angle=15, overfetch=4)
        assert b.hits_per_angle * b.overfetch > HttpPodClient.MAX_RECALL_LIMIT

    def test_and_now_survives_it(self):
        c, rec = _client()
        b = Budget(hits_per_angle=15, overfetch=4)
        hits = c.recall("q", b.hits_per_angle * b.overfetch, 5.0)
        assert hits, "the configured budget still returns nothing"


class TestFetchSwallowsPodErrors:
    """Why this went unnoticed: fetch() returns empty material on PodError.
    That is the right call at runtime -- memory being down must not break a
    turn -- but it means a permanently broken recall looks exactly like a
    corpus with no relevant hits."""

    def test_a_pod_error_yields_empty_material_not_an_exception(self):
        class _Dead:
            def recall(self, *a, **k):
                raise PodError("HTTP Error 422: Unprocessable Entity")
            def recall_multi(self, *a, **k):
                raise PodError("HTTP Error 422: Unprocessable Entity")
            def get(self, *a, **k):
                return []

        r = MazeRouter(_Dead(), None, Budget())
        assert r.fetch("continue the build").text == ""
