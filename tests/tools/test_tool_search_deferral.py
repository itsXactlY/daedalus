"""Regression guard: progressive tool disclosure must actually defer.

`tools/tool_search.py` shipped enabled-by-default and deferred nothing for
its entire life: `is_deferrable_tool_name` called `registry.get_entry()`,
a method `ToolRegistry` has never had. The AttributeError landed in the
function's bare `except Exception: return False`, so every tool was
classified non-deferrable and the whole 1000-line module was a silent
no-op — 13,786 tokens of schemas shipped on every request.

These tests fail on that code. They assert the *outcome* (deferral
happens, core tools survive, nothing disappears), not the implementation,
so a future refactor of the predicate cannot re-break it quietly.
"""
import json

import pytest

from tools import tool_search as TS
from tools.registry import registry


def _fake_defs(names):
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"description for {n}" * 12,
                "parameters": {
                    "type": "object",
                    "properties": {"q": {"type": "string", "description": "x" * 200}},
                },
            },
        }
        for n in names
    ]


def test_registry_exposes_the_probe_the_predicate_uses():
    """The predicate must only call methods ToolRegistry actually has."""
    assert hasattr(registry, "get_toolset_for_tool")
    assert not hasattr(registry, "get_entry"), (
        "get_entry reappeared — re-check is_deferrable_tool_name still "
        "probes a method that exists"
    )


def test_a_registered_non_core_tool_is_deferrable():
    """The bug: this returned False for every tool on the planet."""
    registry.register(
        name="_ts_probe_tool",
        toolset="mcp-probe",
        schema={"name": "_ts_probe_tool", "description": "probe",
                "parameters": {"type": "object", "properties": {}}},
        handler=lambda **kw: "ok",
        check_fn=lambda: True,
    )
    try:
        assert TS.is_deferrable_tool_name("_ts_probe_tool") is True
    finally:
        registry.deregister("_ts_probe_tool")


def test_core_tools_are_never_deferrable():
    from toolsets import _DAEDALUS_CORE_TOOLS

    for name in _DAEDALUS_CORE_TOOLS:
        assert TS.is_deferrable_tool_name(name) is False, name


def test_bridge_tools_are_never_deferrable():
    for name in TS.BRIDGE_TOOL_NAMES:
        assert TS.is_deferrable_tool_name(name) is False


def test_unregistered_tool_stays_eager():
    """A tool the bridge cannot route must not be hidden behind it."""
    assert TS.is_deferrable_tool_name("_no_such_tool_anywhere_") is False


def test_assembly_activates_and_shrinks_the_array():
    """End-to-end: a catalog with deferrable tools must cost fewer tokens."""
    registered = []
    try:
        for i in range(12):
            n = f"_ts_bulk_{i}"
            registry.register(
                name=n, toolset="mcp-bulk",
                schema={"name": n, "description": "d" * 400,
                        "parameters": {"type": "object", "properties": {}}},
                handler=lambda **kw: "ok", check_fn=lambda: True,
            )
            registered.append(n)

        defs = _fake_defs(registered + ["read_file", "write_file", "terminal"])
        before = len(json.dumps(defs))

        cfg = TS.ToolSearchConfig.from_raw({"enabled": "on"})
        assembly = TS.assemble_tool_defs(defs, context_length=95000, config=cfg)
        after = len(json.dumps(assembly.tool_defs))

        assert assembly.activated is True
        assert assembly.deferred_count == len(registered)
        assert after < before, "assembly did not shrink the tools array"

        visible = {t["function"]["name"] for t in assembly.tool_defs}
        assert TS.BRIDGE_TOOL_NAMES <= visible, "bridge tools missing"
        for core in ("read_file", "write_file", "terminal"):
            assert core in visible, f"core tool {core} was deferred"
        for n in registered:
            assert n not in visible, f"{n} should have been deferred"
    finally:
        for n in registered:
            registry.deregister(n)


def test_nothing_is_lost_when_disabled():
    defs = _fake_defs(["read_file", "terminal"])
    cfg = TS.ToolSearchConfig.from_raw({"enabled": "off"})
    assembly = TS.assemble_tool_defs(defs, context_length=95000, config=cfg)
    assert assembly.activated is False
    assert len(assembly.tool_defs) == len(defs)


def test_always_load_pins_a_non_core_tool_eager():
    """The hot path must not pay the bridge's round trip on every turn."""
    registry.register(
        name="_ts_hot_tool", toolset="mcp-probe",
        schema={"name": "_ts_hot_tool", "description": "hot",
                "parameters": {"type": "object", "properties": {}}},
        handler=lambda **kw: "ok", check_fn=lambda: True,
    )
    try:
        no_pin = TS.ToolSearchConfig.from_raw({"enabled": "on"})
        pinned = TS.ToolSearchConfig.from_raw(
            {"enabled": "on", "always_load": ["_ts_hot_tool"]}
        )
        assert TS.is_deferrable_tool_name("_ts_hot_tool", no_pin) is True
        assert TS.is_deferrable_tool_name("_ts_hot_tool", pinned) is False
    finally:
        registry.deregister("_ts_hot_tool")


def test_always_load_survives_a_full_assembly():
    registered = []
    try:
        for i in range(12):
            n = f"_ts_pin_{i}"
            registry.register(
                name=n, toolset="mcp-bulk",
                schema={"name": n, "description": "d" * 400,
                        "parameters": {"type": "object", "properties": {}}},
                handler=lambda **kw: "ok", check_fn=lambda: True,
            )
            registered.append(n)

        defs = _fake_defs(registered + ["read_file"])
        cfg = TS.ToolSearchConfig.from_raw(
            {"enabled": "on", "always_load": ["_ts_pin_0", "_ts_pin_1"]}
        )
        assembly = TS.assemble_tool_defs(defs, context_length=95000, config=cfg)
        visible = {t["function"]["name"] for t in assembly.tool_defs}

        assert assembly.activated is True
        assert "_ts_pin_0" in visible and "_ts_pin_1" in visible
        assert "_ts_pin_2" not in visible
        assert assembly.deferred_count == len(registered) - 2
    finally:
        for n in registered:
            registry.deregister(n)


def test_always_load_accepts_a_bare_string_and_ignores_junk():
    cfg = TS.ToolSearchConfig.from_raw({"enabled": "on", "always_load": "solo"})
    assert cfg.always_load == ("solo",)
    cfg = TS.ToolSearchConfig.from_raw({"enabled": "on", "always_load": [1, None, " x "]})
    assert cfg.always_load == ("x",)
    cfg = TS.ToolSearchConfig.from_raw({"enabled": "on"})
    assert cfg.always_load == ()


def test_bridge_schemas_carry_no_catalog_listing():
    bridge = TS.bridge_tool_schemas(3320)
    blob = json.dumps(bridge)
    assert len(blob) < 3000
    assert "3320" in blob
    assert not hasattr(TS, "build_catalog_listing")
    assert not hasattr(TS, "listing_token_budget")


def test_bridge_cost_is_flat_across_catalog_size():
    small = len(json.dumps(TS.bridge_tool_schemas(5)))
    huge = len(json.dumps(TS.bridge_tool_schemas(3320)))
    assert huge - small < 30


def test_exact_tool_name_ranks_first():
    defs = _fake_defs(["alpha_read", "alpha_read_many", "beta_read"])
    catalog = TS.build_catalog(defs)
    hits = TS.search_catalog(catalog, "alpha_read", limit=3)
    assert hits[0].name == "alpha_read"


def test_search_ranking_is_deterministic():
    defs = _fake_defs([f"tool_{i}" for i in range(20)])
    catalog = TS.build_catalog(defs)
    runs = [[e.name for e in TS.search_catalog(catalog, "tool", limit=5)] for _ in range(5)]
    assert all(r == runs[0] for r in runs)


def test_handle_function_call_routes_the_bridge():
    import model_tools as MT

    registry.register(
        name="_ts_bridge_probe", toolset="mcp-probe",
        schema={"name": "_ts_bridge_probe", "description": "probe the bridge",
                "parameters": {"type": "object",
                               "properties": {"x": {"type": "string"}},
                               "required": ["x"]}},
        handler=lambda args, **kw: json.dumps({"echoed": args.get("x")}),
        check_fn=lambda: True,
    )
    prev = MT._last_full_tool_defs
    MT._last_full_tool_defs = _fake_defs(["read_file"]) + [{
        "type": "function",
        "function": {"name": "_ts_bridge_probe", "description": "probe the bridge",
                     "parameters": {"type": "object",
                                    "properties": {"x": {"type": "string"}},
                                    "required": ["x"]}},
    }]
    try:
        found = json.loads(MT.handle_function_call("tool_search", {"query": "_ts_bridge_probe"}))
        assert found["matches"][0]["name"] == "_ts_bridge_probe"

        described = json.loads(MT.handle_function_call("tool_describe", {"name": "_ts_bridge_probe"}))
        assert described["parameters"]["required"] == ["x"]

        called = MT.handle_function_call("tool_call", {"name": "_ts_bridge_probe",
                                                       "arguments": {"x": "hi"}})
        assert "hi" in called

        missing = json.loads(MT.handle_function_call("tool_call", {"name": "_ts_bridge_probe",
                                                                   "arguments": {}}))
        assert "error" in missing
        assert "x" in missing["error"]
    finally:
        MT._last_full_tool_defs = prev
        registry.deregister("_ts_bridge_probe")


def test_bridge_refuses_out_of_scope_and_eager_tools():
    import model_tools as MT

    prev = MT._last_full_tool_defs
    MT._last_full_tool_defs = _fake_defs(["read_file"])
    try:
        eager = json.loads(MT.handle_function_call("tool_call", {"name": "read_file",
                                                                 "arguments": {}}))
        assert "error" in eager
        recursive = json.loads(MT.handle_function_call("tool_call", {"name": "tool_call",
                                                                     "arguments": {}}))
        assert "error" in recursive
    finally:
        MT._last_full_tool_defs = prev


def test_skip_assembly_returns_the_full_surface():
    import model_tools as MT

    full = MT.get_tool_definitions(quiet_mode=True, skip_tool_search_assembly=True)
    visible = MT.get_tool_definitions(quiet_mode=True)
    full_names = {t["function"]["name"] for t in full}
    visible_names = {t["function"]["name"] for t in visible}
    assert TS.BRIDGE_TOOL_NAMES & full_names == set()
    assert TS.BRIDGE_TOOL_NAMES <= visible_names
    assert len(full_names) >= len(visible_names)


def test_every_deferred_tool_survives_the_round_trip():
    import model_tools as MT

    full = MT.get_tool_definitions(quiet_mode=True, skip_tool_search_assembly=True)
    _, deferrable = TS.classify_tools(full, TS.load_config())
    if not deferrable:
        pytest.skip("no deferrable tools registered in this environment")
    for td in deferrable:
        name = td["function"]["name"]
        described = json.loads(MT.handle_function_call("tool_describe", {"name": name}))
        assert described.get("name") == name
        hits = json.loads(MT.handle_function_call("tool_search", {"query": name, "limit": 5}))
        assert hits["matches"][0]["name"] == name


def test_describing_a_tool_promotes_it_for_the_session():
    import model_tools as MT

    registry.register(
        name="_ts_promote_a", toolset="mcp-probe",
        schema={"name": "_ts_promote_a", "description": "promote me",
                "parameters": {"type": "object", "properties": {}}},
        handler=lambda args, **kw: "ok", check_fn=lambda: True,
    )
    prev = MT._last_full_tool_defs
    MT.drain_promoted_tool_defs()
    MT._last_full_tool_defs = _fake_defs(["_ts_promote_a"])
    try:
        MT.handle_function_call("tool_describe", {"name": "_ts_promote_a"})
        promoted = MT.drain_promoted_tool_defs()
        assert [t["function"]["name"] for t in promoted] == ["_ts_promote_a"]
        assert MT.drain_promoted_tool_defs() == []
    finally:
        MT._last_full_tool_defs = prev
        registry.deregister("_ts_promote_a")


def test_calling_a_tool_promotes_it_even_when_the_tool_fails():
    import model_tools as MT

    def _boom(args, **kw):
        raise RuntimeError("tool exploded")

    registry.register(
        name="_ts_promote_b", toolset="mcp-probe",
        schema={"name": "_ts_promote_b", "description": "explodes",
                "parameters": {"type": "object", "properties": {}}},
        handler=_boom, check_fn=lambda: True,
    )
    prev = MT._last_full_tool_defs
    MT.drain_promoted_tool_defs()
    MT._last_full_tool_defs = _fake_defs(["_ts_promote_b"])
    try:
        MT.handle_function_call("tool_call", {"name": "_ts_promote_b", "arguments": {}})
        assert [t["function"]["name"] for t in MT.drain_promoted_tool_defs()] == ["_ts_promote_b"]
    finally:
        MT._last_full_tool_defs = prev
        registry.deregister("_ts_promote_b")


def test_a_rejected_call_promotes_nothing():
    import model_tools as MT

    prev = MT._last_full_tool_defs
    MT.drain_promoted_tool_defs()
    MT._last_full_tool_defs = _fake_defs(["read_file"])
    try:
        MT.handle_function_call("tool_call", {"name": "read_file", "arguments": {}})
        MT.handle_function_call("tool_call", {"name": "_no_such_tool_", "arguments": {}})
        MT.handle_function_call("tool_describe", {"name": "_no_such_tool_"})
        assert MT.drain_promoted_tool_defs() == []
    finally:
        MT._last_full_tool_defs = prev


def test_missing_required_args_do_not_promote_before_repair():
    import model_tools as MT

    registry.register(
        name="_ts_promote_c", toolset="mcp-probe",
        schema={"name": "_ts_promote_c", "description": "needs x",
                "parameters": {"type": "object",
                               "properties": {"x": {"type": "string"}},
                               "required": ["x"]}},
        handler=lambda args, **kw: "ok", check_fn=lambda: True,
    )
    prev = MT._last_full_tool_defs
    MT.drain_promoted_tool_defs()
    MT._last_full_tool_defs = [{
        "type": "function",
        "function": {"name": "_ts_promote_c", "description": "needs x",
                     "parameters": {"type": "object",
                                    "properties": {"x": {"type": "string"}},
                                    "required": ["x"]}},
    }]
    try:
        MT.handle_function_call("tool_call", {"name": "_ts_promote_c", "arguments": {}})
        assert MT.drain_promoted_tool_defs() == []
        MT.handle_function_call("tool_call", {"name": "_ts_promote_c", "arguments": {"x": "1"}})
        assert [t["function"]["name"] for t in MT.drain_promoted_tool_defs()] == ["_ts_promote_c"]
    finally:
        MT._last_full_tool_defs = prev
        registry.deregister("_ts_promote_c")


def test_agent_absorbs_promotions_and_keeps_them():
    import model_tools as MT
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent.tools = _fake_defs(["read_file"])
    agent.valid_tool_names = {"read_file"}

    MT.drain_promoted_tool_defs()
    MT._promoted_tool_defs["_ts_absorbed"] = {
        "type": "function",
        "function": {"name": "_ts_absorbed", "description": "d",
                     "parameters": {"type": "object", "properties": {}}},
    }
    agent._absorb_promoted_tools()

    names = [t["function"]["name"] for t in agent.tools]
    assert names[-1] == "_ts_absorbed"
    assert "_ts_absorbed" in agent.valid_tool_names

    agent._absorb_promoted_tools()
    assert [t["function"]["name"] for t in agent.tools] == names
