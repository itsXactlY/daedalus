"""The pod tool surface is shipped as a dispatcher, not 30-odd schemas.

The pod speaks one endpoint. Exploding it into a schema per tool cost ~16k
tokens of prompt; the previous fix was an allowlist that deleted 22 tools from
the model's awareness. These tests hold the third answer in place: every tool
stays visible and callable, only the argument schemas are fetched on demand.
"""

import json

import pytest

import plugins.memory.mazemaker as mzm


POD_TOOLS = [
    {"name": f"mazemaker_{n}",
     "description": f"Tool {n}. " + ("Detail sentence. " * 12),
     "inputSchema": {"type": "object",
                     "properties": {f"p{i}": {"type": "string",
                                              "description": "x" * 60}
                                    for i in range(6)},
                     "required": ["p0"]}}
    for n in ("recall", "remember", "think", "graph", "get", "browse", "stats",
              "health", "prune", "dream", "dream_rem", "dream_nrem", "ablate",
              "rebake", "quota", "diagnose", "afe_facts", "recall_multi",
              "classify_intent", "synth_lineage", "supersedes_log",
              "connections_import", "delete_by_labels", "dream_stats",
              "dream_afe", "dream_dae", "dream_config", "dream_control",
              "dream_insight", "dream_synthesize", "recall_advanced",
              "list_by_label_prefix", "count_by_label_prefix", "dream_supersedes")
]


@pytest.fixture(autouse=True)
def catalogue_loaded(monkeypatch):
    monkeypatch.setattr(mzm, "_catalogue_state", {"tools": [], "ts": 0.0})
    monkeypatch.setattr(mzm, "_fetch_catalogue", lambda: list(POD_TOOLS))
    monkeypatch.setattr(mzm, "_POD_HEALTH", mzm._PodHealth())
    return POD_TOOLS


def _schemas():
    return mzm.MazemakerMemoryProvider().get_tool_schemas()


# --- nothing is taken away ----------------------------------------------

def test_every_pod_tool_stays_reachable():
    schemas = {s["name"]: s for s in _schemas()}
    dispatcher = schemas[mzm.DISPATCH_TOOL]
    enum = dispatcher["parameters"]["properties"]["tool"]["enum"]
    assert set(enum) == {t["name"] for t in POD_TOOLS}, (
        "the dispatcher enum is the model's tool surface — it must list all of them"
    )


def test_every_pod_tool_stays_visible():
    """Callable is not enough — a tool the model cannot see, it cannot choose."""
    dispatcher = {s["name"]: s for s in _schemas()}[mzm.DISPATCH_TOOL]
    listed = dispatcher["description"]
    for t in POD_TOOLS:
        if t["name"] in mzm.NATIVE_TOOLS:
            continue
        assert t["name"] in listed


def test_hot_tools_keep_native_schemas():
    schemas = {s["name"]: s for s in _schemas()}
    for name in mzm.NATIVE_TOOLS:
        assert name in schemas
        assert schemas[name]["parameters"]["properties"]


def test_shipped_surface_is_a_fraction_of_the_full_schemas():
    full = json.dumps([
        {"name": t["name"], "description": t["description"],
         "parameters": t["inputSchema"]} for t in POD_TOOLS
    ])
    shipped = json.dumps(_schemas())
    ratio = len(shipped) / len(full)
    assert ratio < 0.30, f"expected a large cut, got {100*(1-ratio):.1f}%"


# --- the dispatcher dispatches ------------------------------------------

def test_dispatch_unwraps_to_the_inner_call(monkeypatch):
    seen = {}

    def _fake(name, args, timeout=8.0):
        seen.update(name=name, args=args, timeout=timeout)
        return {"ok": True}

    monkeypatch.setattr(mzm, "_tool", _fake)
    out = mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_TOOL, {"tool": "mazemaker_browse", "args": {"limit": 5}}
    )
    assert seen["name"] == "mazemaker_browse"
    assert seen["args"] == {"limit": 5}
    assert json.loads(out) == {"ok": True}


def test_dispatch_applies_the_slow_timeout_to_the_inner_tool(monkeypatch):
    seen = {}
    monkeypatch.setattr(mzm, "_tool",
                        lambda n, a, timeout=8.0: seen.update(timeout=timeout) or {})
    mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_TOOL, {"tool": "mazemaker_recall_advanced", "args": {}}
    )
    assert seen["timeout"] == 30.0


def test_native_call_still_works_unwrapped(monkeypatch):
    seen = {}
    monkeypatch.setattr(mzm, "_tool",
                        lambda n, a, timeout=8.0: seen.update(name=n) or {"r": 1})
    mzm.MazemakerMemoryProvider().handle_tool_call(
        "mazemaker_recall", {"query": "x"}
    )
    assert seen["name"] == "mazemaker_recall"


def test_json_string_args_are_accepted(monkeypatch):
    seen = {}
    monkeypatch.setattr(mzm, "_tool",
                        lambda n, a, timeout=8.0: seen.update(args=a) or {})
    mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_TOOL, {"tool": "mazemaker_browse", "args": '{"limit": 3}'}
    )
    assert seen["args"] == {"limit": 3}


def test_unknown_tool_offers_the_nearest_name():
    out = json.loads(mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_TOOL, {"tool": "mazemaker_recal", "args": {}}
    ))
    assert "unknown mazemaker tool" in out["error"]
    assert "mazemaker_recall" in out["did_you_mean"]


def test_missing_tool_name_is_an_error_not_a_pod_call(monkeypatch):
    monkeypatch.setattr(mzm, "_tool", lambda *a, **k: pytest.fail("called the pod"))
    out = json.loads(mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_TOOL, {"args": {"limit": 1}}
    ))
    assert "requires a 'tool' name" in out["error"]


# --- help is local -------------------------------------------------------

def test_help_returns_the_full_schema_without_touching_the_pod(monkeypatch):
    monkeypatch.setattr(mzm, "_tool", lambda *a, **k: pytest.fail("called the pod"))
    out = json.loads(mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_HELP_TOOL, {"tool": "mazemaker_ablate"}
    ))
    assert out["tool"] == "mazemaker_ablate"
    assert out["parameters"]["properties"]["p0"]


def test_help_on_a_typo_offers_the_nearest_name():
    out = json.loads(mzm.MazemakerMemoryProvider().handle_tool_call(
        mzm.DISPATCH_HELP_TOOL, {"tool": "mazemaker_dreem"}
    ))
    assert out["did_you_mean"]


# --- a down pod must not erase the surface -------------------------------

def test_catalogue_survives_a_down_pod_via_disk(monkeypatch):
    assert mzm.catalogue()  # warm + persist to disk
    monkeypatch.setattr(mzm, "_catalogue_state", {"tools": [], "ts": 0.0})

    def _down():
        raise OSError("connection refused")

    monkeypatch.setattr(mzm, "_fetch_catalogue", _down)
    assert len(mzm.catalogue()) == len(POD_TOOLS), (
        "a pod that is down at boot must not silently strip every memory tool"
    )


# --- last resort: pod down AND cache cold --------------------------------

def test_fallback_keeps_memory_callable_when_pod_is_down_and_cache_cold(monkeypatch):
    """Zero tools is the worst outcome: the model cannot recall and cannot say why."""
    monkeypatch.setattr(mzm, "_catalogue_state", {"tools": [], "ts": 0.0})
    monkeypatch.setattr(mzm, "_fetch_catalogue",
                        lambda: (_ for _ in ()).throw(OSError("refused")))
    monkeypatch.setattr(mzm, "_catalogue_cache_path", lambda: None)

    schemas = mzm.MazemakerMemoryProvider().get_tool_schemas()
    assert schemas, "a down pod must not strip the memory surface to nothing"
    enum = [s for s in schemas if s["name"] == mzm.DISPATCH_TOOL][0][
        "parameters"]["properties"]["tool"]["enum"]
    assert len(enum) == len(mzm._FALLBACK_TOOL_NAMES)
    recall = [s for s in schemas if s["name"] == "mazemaker_recall"][0]
    assert "query" in recall["parameters"]["properties"], (
        "the hot path must stay usable without the pod's own schema"
    )


def test_fallback_is_never_cached(monkeypatch):
    """The next call must retry the real pod, not settle for the built-in list."""
    monkeypatch.setattr(mzm, "_catalogue_state", {"tools": [], "ts": 0.0})
    monkeypatch.setattr(mzm, "_fetch_catalogue",
                        lambda: (_ for _ in ()).throw(OSError("refused")))
    monkeypatch.setattr(mzm, "_catalogue_cache_path", lambda: None)
    mzm.catalogue()
    assert mzm._catalogue_state["tools"] == []

    monkeypatch.setattr(mzm, "_fetch_catalogue", lambda: list(POD_TOOLS))
    assert len(mzm.catalogue()) == len(POD_TOOLS)
