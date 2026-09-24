import pytest

from agent.harness_config import (
    AuxTask, ConfigError, ConfigProblem, HarnessConfig, MCPServer,
)


def kinds(cfg, kind):
    return [p.path for p in cfg.problems if p.kind == kind]


def test_defaults_when_empty():
    cfg = HarnessConfig.from_dict({})
    assert cfg.compression.engine == "retrieval"
    assert cfg.memory.provider == "mazemaker"
    assert cfg.context.payload_tape is True
    assert cfg.is_clean()


def test_unknown_key_is_reported_not_swallowed():
    cfg = HarnessConfig.from_dict({"compression": {"aggressive": True}})
    assert "compression.aggressive" in kinds(cfg, "unknown")


def test_context_engine_does_not_shadow_compression_engine():
    """The real trap: context.engine reads authoritative and is inert."""
    cfg = HarnessConfig.from_dict({
        "compression": {"engine": "retrieval"},
        "context": {"engine": "compressor"},
    })
    assert cfg.compression.engine == "retrieval"
    assert "context.engine" in kinds(cfg, "unknown")


def test_dead_section_reported():
    cfg = HarnessConfig.from_dict({"steering": {"a": 1}})
    assert "steering" in kinds(cfg, "dead")


def test_bad_enum_reported_and_default_kept():
    cfg = HarnessConfig.from_dict({"compression": {"engine": "banana"}})
    assert any(p.kind == "value" for p in cfg.problems)


def test_wrong_type_falls_back_to_default():
    cfg = HarnessConfig.from_dict({"compression": {"max_tokens": "lots"}})
    assert cfg.compression.max_tokens == 32000
    assert "compression.max_tokens" in kinds(cfg, "type")


def test_bool_is_not_an_int():
    cfg = HarnessConfig.from_dict({"compression": {"max_tokens": True}})
    assert cfg.compression.max_tokens == 32000


def test_strict_raises_on_hard_problems():
    with pytest.raises(ConfigError):
        HarnessConfig.from_dict({"compression": {"engine": "banana"}}, strict=True)


def test_strict_tolerates_unknown_keys():
    HarnessConfig.from_dict({"compression": {"nope": 1}}, strict=True)


def test_threshold_range_validated():
    cfg = HarnessConfig.from_dict({"compression": {"threshold": 1.5}})
    assert any(p.path.endswith("threshold") and p.kind == "value"
               for p in cfg.problems)


def test_watermarks_must_be_ordered():
    cfg = HarnessConfig.from_dict(
        {"compression": {"watermarks": {"low": 0.9, "high": 0.5, "hard": 0.8}}})
    assert any(p.kind == "value" for p in cfg.problems)


def test_prefetch_timeout_below_pod_latency_is_flagged():
    """The 8.0s that killed per-turn recall must not pass silently."""
    cfg = HarnessConfig.from_dict({"memory": {"prefetch_timeout_s": 8.0}})
    assert any("prefetch_timeout_s" in p.path and p.kind == "value"
               for p in cfg.problems)


def test_gateway_warning_after_timeout_is_flagged():
    cfg = HarnessConfig.from_dict(
        {"agent": {"gateway_timeout": 100, "gateway_timeout_warning": 200}})
    assert any("gateway_timeout_warning" in p.path for p in cfg.problems)


def test_mcp_http_server_needs_url():
    cfg = HarnessConfig.from_dict(
        {"mcp_servers": {"x": {"enabled": True, "transport": "http"}}})
    assert any(p.path == "mcp_servers.x.url" for p in cfg.problems)


def test_mcp_disabled_server_not_validated_for_url():
    cfg = HarnessConfig.from_dict(
        {"mcp_servers": {"x": {"enabled": False, "transport": "http"}}})
    assert not [p for p in cfg.problems if p.path == "mcp_servers.x.url"]


def test_enabled_servers_and_disabled_tools():
    cfg = HarnessConfig.from_dict({"mcp_servers": {
        "a": {"enabled": True, "transport": "http", "url": "http://x/mcp",
              "tools": {"t1": {"enabled": False}, "t2": {"enabled": True}}},
        "b": {"enabled": False, "transport": "http", "url": "http://y/mcp"},
    }})
    assert list(cfg.enabled_servers()) == ["a"]
    assert cfg.server("a").disabled_tools() == ["t1"]


def test_auxiliary_is_a_task_map():
    cfg = HarnessConfig.from_dict({"auxiliary": {
        "vision": {"provider": "custom", "base_url": "http://127.0.0.1:8080/v1"}}})
    assert isinstance(cfg.aux("vision"), AuxTask)
    assert cfg.aux("vision").base_url == "http://127.0.0.1:8080/v1"
    assert cfg.aux("nope") is None


def test_nested_section_problems_carry_full_path():
    cfg = HarnessConfig.from_dict({"memory": {"soak": {"window_turns": "eight"}}})
    assert "memory.soak.window_turns" in kinds(cfg, "type")


def test_non_mapping_section_reported():
    cfg = HarnessConfig.from_dict({"compression": ["not", "a", "map"]})
    assert "compression" in kinds(cfg, "type")
    assert cfg.compression.engine == "retrieval"


def test_get_escape_hatch_for_untyped_sections():
    cfg = HarnessConfig.from_dict({"display": {"theme": "dark"}})
    assert cfg.get("display.theme") == "dark"
    assert cfg.get("display.missing", "fallback") == "fallback"
    assert cfg.get("nothing.here") is None


def test_passthrough_sections_are_not_flagged_dead():
    cfg = HarnessConfig.from_dict({"display": {"theme": "dark"}, "tts": {"enabled": True}})
    assert not kinds(cfg, "dead")


def test_frozen():
    cfg = HarnessConfig.from_dict({})
    with pytest.raises(Exception):
        cfg.compression.engine = "compressor"
