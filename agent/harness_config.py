"""Typed, validated configuration for the daedalus harness.

Replaces `cfg.get("a", {}).get("b", default)` chains with one object that
knows its own shape. Three rules:

  1. Every field here is READ by the code. Nothing aspirational.
  2. Unknown keys are REPORTED, never silently swallowed — a key that looks
     meaningful and is inert (config.yaml's `context.engine`, which nothing
     reads, while `compression.engine` is the live one) costs more time than
     a missing key ever does.
  3. Wrong types fail loudly at load, not at the call site three hours in.

    cfg = HarnessConfig.load()
    cfg.compression.engine          # typed, defaulted, validated
    for p in cfg.report(): print(p) # unknown / dead / shadowed keys
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, MISSING
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, get_args, get_origin

__all__ = ["HarnessConfig", "ConfigProblem", "ConfigError"]

T = TypeVar("T", bound="Section")


class ConfigError(ValueError):
    """A config value is the wrong type or outside its allowed set."""


@dataclass(frozen=True)
class ConfigProblem:
    path: str
    kind: str          # unknown | type | value | dead
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.path}: {self.detail}"


_HINTS: Dict[type, Dict[str, Any]] = {}


def _hints(cls: type) -> Dict[str, Any]:
    if cls not in _HINTS:
        import typing
        _HINTS[cls] = typing.get_type_hints(cls)
    return _HINTS[cls]


def _type_ok(value: Any, tp: Any) -> bool:
    origin = get_origin(tp)
    if origin is None:
        if tp is Any:
            return True
        if tp is float:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if tp is int:
            return isinstance(value, int) and not isinstance(value, bool)
        return isinstance(value, tp)
    if origin is list:
        args = get_args(tp)
        return isinstance(value, list) and (
            not args or all(_type_ok(v, args[0]) for v in value))
    if origin is dict:
        return isinstance(value, dict)
    # Optional[X] / Union
    return any(_type_ok(value, a) for a in get_args(tp) if a is not type(None)) \
        or value is None


@dataclass(frozen=True)
class Section:
    """Base: builds from a dict, records anything it did not expect."""

    @classmethod
    def build(cls: Type[T], raw: Any, path: str,
              problems: List[ConfigProblem]) -> T:
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            problems.append(ConfigProblem(path, "type",
                                          f"expected a mapping, got {type(raw).__name__}"))
            raw = {}
        # `from __future__ import annotations` stores hints as strings, so
        # resolve them once instead of isinstance()-ing a str.
        hints = _hints(cls)
        known = {f.name: f for f in fields(cls)}
        kwargs: Dict[str, Any] = {}
        for name in known:
            if name not in raw:
                continue
            value = raw[name]
            tp = hints.get(name, Any)
            if isinstance(tp, type) and issubclass(tp, Section):
                kwargs[name] = tp.build(value, f"{path}.{name}", problems)
                continue
            if not _type_ok(value, tp):
                problems.append(ConfigProblem(
                    f"{path}.{name}", "type",
                    f"expected {getattr(tp, '__name__', tp)}, "
                    f"got {type(value).__name__} ({value!r}) — using the default"))
                continue
            kwargs[name] = value
        for key in raw:
            if key not in known:
                problems.append(ConfigProblem(f"{path}.{key}", "unknown",
                                              "nothing in the harness reads this"))
        obj = cls(**kwargs)
        obj._validate(path, problems)
        return obj

    def _validate(self, path: str, problems: List[ConfigProblem]) -> None:
        """Override for cross-field or enum checks."""

    def _one_of(self, path: str, name: str, allowed: Tuple[str, ...],
                problems: List[ConfigProblem]) -> None:
        v = getattr(self, name)
        if v not in allowed:
            problems.append(ConfigProblem(f"{path}.{name}", "value",
                                          f"{v!r} not in {allowed}"))


# ── sections ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Watermarks(Section):
    low: float = 0.6
    high: float = 0.8
    hard: float = 0.9

    def _validate(self, path, problems):
        if not (0 < self.low <= self.high <= self.hard <= 1.0):
            problems.append(ConfigProblem(path, "value",
                f"must satisfy 0 < low <= high <= hard <= 1, got "
                f"{self.low}/{self.high}/{self.hard}"))


@dataclass(frozen=True)
class Compression(Section):
    enabled: bool = True
    threshold: float = 0.5
    max_tokens: int = 32000
    engine: str = "retrieval"          # retrieval | compressor
    fast_layer_tokens: int = 0
    hot_swap_prep_ratio: float = 0.0
    protect_last_n: int = 6
    protect_first_n: int = 4
    target_ratio: float = 0.1
    tail_budget: int = 3200
    watermarks: Watermarks = field(default_factory=Watermarks)

    def _validate(self, path, problems):
        self._one_of(path, "engine", ("retrieval", "compressor"), problems)
        if not 0.0 < self.threshold <= 1.0:
            problems.append(ConfigProblem(f"{path}.threshold", "value",
                                          f"{self.threshold} must be in (0, 1]"))


@dataclass(frozen=True)
class Context(Section):
    """Working-context shape. NOTE: no `engine` here — that lives in
    `compression`. A stray `context.engine` is inert and gets reported
    rather than quietly shadowing the real one."""
    reasoning_window: int = 2
    tool_group_ttl: int = 3
    payload_tape: bool = True


@dataclass(frozen=True)
class Soak(Section):
    enabled: bool = True
    window_turns: int = 8
    prefetch_on_turn: bool = True
    ttl_seconds: int = 3600
    state_reinject_every: int = 2


@dataclass(frozen=True)
class Memory(Section):
    provider: str = "mazemaker"        # mazemaker | mcp | builtin
    prefetch_timeout_s: float = 30.0
    soak: Soak = field(default_factory=Soak)

    def _validate(self, path, problems):
        self._one_of(path, "provider", ("mazemaker", "mcp", "builtin"), problems)
        if self.prefetch_timeout_s < 10.0:
            problems.append(ConfigProblem(
                f"{path}.prefetch_timeout_s", "value",
                f"{self.prefetch_timeout_s}s is under pod recall latency "
                "(5-19s under GPU contention); the join times out and the turn "
                "gets no memory context"))


@dataclass(frozen=True)
class AuxTask(Section):
    """One background task's model endpoint. Every aux task inherits the main
    model unless it overrides here — per-task routing to a cloud default is
    what leaked private turns on 2026-09-16."""
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout: float = 120.0
    download_timeout: float = 30.0
    api_mode: str = ""
    effort: str = ""
    context_length: int = 0


@dataclass(frozen=True)
class Skills(Section):
    enabled: bool = True
    auto_route: bool = True
    external_dirs: List[str] = field(default_factory=list)
    disabled: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolSearch(Section):
    enabled: bool = True
    threshold: int = 0
    always_load: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MCPServer(Section):
    enabled: bool = False
    transport: str = "http"            # http | stdio
    url: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    description: str = ""
    tools: Dict[str, Any] = field(default_factory=dict)

    def _validate(self, path, problems):
        self._one_of(path, "transport", ("http", "stdio"), problems)
        if self.enabled and self.transport == "http" and not self.url:
            problems.append(ConfigProblem(f"{path}.url", "value",
                                          "http transport with no url"))
        if self.enabled and self.transport == "stdio" and not self.command:
            problems.append(ConfigProblem(f"{path}.command", "value",
                                          "stdio transport with no command"))

    def disabled_tools(self) -> List[str]:
        return sorted(n for n, v in (self.tools or {}).items()
                      if isinstance(v, dict) and v.get("enabled") is False)


@dataclass(frozen=True)
class Agent(Section):
    max_turns: int = 400
    gateway_timeout: int = 1800
    gateway_timeout_warning: int = 900
    gateway_notify_interval: int = 600
    restart_drain_timeout: int = 60
    tool_use_enforcement: str = "auto"
    service_tier: str = ""
    reasoning_effort: str = ""
    reasoning_auto: bool = True
    reasoning_floor: str = ""
    system_prompt: str = ""
    verbose: bool = False

    def _validate(self, path, problems):
        self._one_of(path, "tool_use_enforcement", ("auto", "required", "off"), problems)
        if self.gateway_timeout_warning >= self.gateway_timeout:
            problems.append(ConfigProblem(
                f"{path}.gateway_timeout_warning", "value",
                f"{self.gateway_timeout_warning}s >= gateway_timeout "
                f"{self.gateway_timeout}s — the warning can never fire"))


# ── root ────────────────────────────────────────────────────────────────────

_SECTIONS: Dict[str, Type[Section]] = {
    "compression": Compression,
    "context": Context,
    "memory": Memory,
    "skills": Skills,
    "tool_search": ToolSearch,
    "agent": Agent,
}

# Read by code but not yet typed here. Passed through untouched, NOT reported
# as unknown — typing them is the next step, pretending they do not exist is
# how a config grows a second, undocumented half.
_PASSTHROUGH = frozenset({
    "model", "providers", "credential_pool_strategies", "toolsets", "terminal",
    "browser", "checkpoints", "smart_model_routing", "display", "privacy",
    "tts", "stt", "voice", "human_delay", "delegation", "prefill_messages_file",
    "timezone", "discord", "approvals", "command_allowlist", "security", "cron",
    "logging", "curator", "_config_version", "network", "session_reset", "pony",
    "routing", "tools", "fallback_providers", "honcho", "personalities",
    "quick_commands", "whatsapp",
})


@dataclass(frozen=True)
class HarnessConfig:
    compression: Compression = field(default_factory=Compression)
    context: Context = field(default_factory=Context)
    memory: Memory = field(default_factory=Memory)
    auxiliary: Dict[str, AuxTask] = field(default_factory=dict)
    skills: Skills = field(default_factory=Skills)
    tool_search: ToolSearch = field(default_factory=ToolSearch)
    agent: Agent = field(default_factory=Agent)
    mcp_servers: Dict[str, MCPServer] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)
    problems: Tuple[ConfigProblem, ...] = ()

    # -- construction ---------------------------------------------------
    @classmethod
    def from_dict(cls, raw: Dict[str, Any], *, strict: bool = False) -> "HarnessConfig":
        raw = raw or {}
        problems: List[ConfigProblem] = []
        built = {name: tp.build(raw.get(name), name, problems)
                 for name, tp in _SECTIONS.items()}

        aux: Dict[str, AuxTask] = {}
        for tname, traw in (raw.get("auxiliary") or {}).items():
            aux[tname] = AuxTask.build(traw, f"auxiliary.{tname}", problems)

        servers: Dict[str, MCPServer] = {}
        for sname, sraw in (raw.get("mcp_servers") or {}).items():
            servers[sname] = MCPServer.build(sraw, f"mcp_servers.{sname}", problems)

        for key in raw:
            if key not in _SECTIONS and key not in _PASSTHROUGH and key not in ("mcp_servers", "auxiliary"):
                problems.append(ConfigProblem(key, "dead",
                                              "no code path reads this section"))

        cfg = cls(**built, auxiliary=aux, mcp_servers=servers, raw=raw, problems=tuple(problems))
        if strict:
            hard = [p for p in problems if p.kind in ("type", "value")]
            if hard:
                raise ConfigError("; ".join(str(p) for p in hard))
        return cfg

    @classmethod
    def load(cls, path: Optional[os.PathLike] = None, *,
             strict: bool = False) -> "HarnessConfig":
        import yaml
        p = Path(path or os.environ.get("DAEDALUS_CONFIG")
                 or Path.home() / ".daedalus" / "config.yaml")
        if not p.exists():
            return cls()
        with open(p, "r", encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh) or {}, strict=strict)

    # -- access ---------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        """Escape hatch for sections not yet typed. `cfg.get("display.theme")`."""
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def aux(self, task: str) -> Optional[AuxTask]:
        return self.auxiliary.get(task)

    def server(self, name: str) -> Optional[MCPServer]:
        return self.mcp_servers.get(name)

    def enabled_servers(self) -> Dict[str, MCPServer]:
        return {n: s for n, s in self.mcp_servers.items() if s.enabled}

    # -- diagnostics ----------------------------------------------------
    def report(self) -> List[str]:
        return [str(p) for p in self.problems]

    def is_clean(self) -> bool:
        return not self.problems


def _main(argv: Optional[List[str]] = None) -> int:
    """`python3 -m agent.harness_config [--strict] [path]` — audit a config."""
    import argparse
    ap = argparse.ArgumentParser(description="audit a daedalus config.yaml")
    ap.add_argument("path", nargs="?", default=None)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on type/value problems")
    a = ap.parse_args(argv)
    try:
        cfg = HarnessConfig.load(a.path, strict=a.strict)
    except ConfigError as exc:
        print(f"INVALID: {exc}")
        return 2
    by = {}
    for p in cfg.problems:
        by.setdefault(p.kind, []).append(p)
    if cfg.is_clean():
        print("clean — every key is read by the harness")
    for kind in ("value", "type", "dead", "unknown"):
        for p in by.get(kind, []):
            print(p)
    print(f"\n{len(cfg.problems)} problem(s); "
          f"{len(cfg.enabled_servers())} mcp server(s) enabled; "
          f"{len(cfg.auxiliary)} aux task(s)")
    return 1 if any(k in by for k in ("value", "type")) else 0


if __name__ == "__main__":
    raise SystemExit(_main())
