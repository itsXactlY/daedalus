"""Per-turn retrieval: one bounded recall, readable hits, tools the model can use.

Measured 2026-09-25: recall_multi took ~28s, the prefetch timed out 69 times
and those turns ran with no memory at all; think returned contentless nodes;
get with memory_ids rendered "Memory #: Label: | Score: 0.000".
"""

import json

import plugins.memory.mazemaker as mzm

P = mzm.MazemakerMemoryProvider
SOAKED = "session:20260924_131217_3fb5f8 @ 2026-09-24T11:16:19Z\n\n=== REASONING ===\n"
BODY = "The prefetch join budget was 8s while pod recall took 5-19s, so every turn lost its memory."


def _provider():
    return P.__new__(P)


def test_soak_header_is_stripped_and_date_kept():
    line = P._hit_line({"id": 7, "label": "auto:reasoning:x:y", "content": SOAKED + BODY,
                        "similarity": 0.61}, 400)
    assert line.startswith("[id 7, reasoning, 2026-09-24, sim 0.61] The prefetch")
    assert "REASONING" not in line


def test_stale_and_crumb_rows_are_unusable():
    assert not P._usable({"content": "[SUPERSEDED] [SUPERSEDED] Q: weiter"})
    assert not P._usable({"label": "auto:compression:6ab5", "content": BODY})
    assert not P._usable({"content": SOAKED + "Run the probe once more."})
    assert P._usable({"label": "bug:x", "content": BODY})


def test_prefetch_is_one_recall_never_multi(monkeypatch):
    calls = []

    def _tool(name, args, timeout=None):
        calls.append((name, timeout))
        if name == "mazemaker_recall":
            return [{"id": 1, "label": "bug:x", "content": BODY, "similarity": 0.7}]
        if name == "mazemaker_think":
            return [{"id": 2, "label": "auto:turn:s:1", "content": ""}]
        if name == "mazemaker_get":
            return {"results": [{"found": True, "memory": {"id": 2, "label": "auto:turn:s:1",
                                                           "content": "=== USER ===\n" + BODY}}]}
        return []

    monkeypatch.setattr(mzm, "_tool", _tool)
    block = _provider()._build_enriched_context("recall timeout")
    names = [c[0] for c in calls]
    assert names.count("mazemaker_recall") == 1
    assert "mazemaker_recall_multi" not in names
    assert all(t is not None and t < 30 for _, t in calls if t is not None)
    assert "[id 1, bug:x" in block
    assert "RELATED" in block and "[id 2, turn" in block


def test_queue_prefetch_does_not_touch_the_pod(monkeypatch):
    monkeypatch.setattr(mzm, "_tool", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    _provider().queue_prefetch("the turn that just ended")


def test_get_batch_renders_every_memory():
    out = mzm._format_tool_result({"count": 2, "results": [
        {"id": 5, "found": True, "memory": {"id": 5, "label": "bug:a", "content": "alpha",
                                            "created_at": 1790249783.0}},
        {"id": 9, "found": False, "nearest_below": [{"id": 8, "label": "l", "content_preview": "p"}]},
    ]}, "mazemaker_get")
    assert "=== #5 bug:a 2026-" in out and "alpha" in out
    assert "#9: NOT FOUND." in out and "id=8" in out


def test_think_nodes_are_filled_with_content():
    out = mzm._format_tool_result(
        [{"id": 3, "label": "auto:turn:s:1", "content": ""}], "mazemaker_think",
        fetch=lambda ids: [{"id": 3, "label": "auto:turn:s:1", "content": BODY}])
    assert "[id 3, turn" in out and "prefetch join budget" in out


def test_recall_list_is_text_with_ids():
    out = mzm._format_tool_result(
        [{"id": 4, "label": "fact:x", "content": BODY, "similarity": 0.5},
         {"id": 5, "label": "fact:y", "content": "[SUPERSEDED] old"}], "mazemaker_recall")
    assert "[id 4, fact:x" in out and "id 5" not in out


def test_unknown_tools_pass_through_as_json():
    res = {"memories": [{"id": 1, "label": "fact:x"}]}
    assert json.loads(mzm._format_tool_result(res, "mazemaker_browse")) == res
