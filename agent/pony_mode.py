from __future__ import annotations

import logging
import os
import re
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from agent.maze_router import Budget, MazeRouter, router_from_config
from agent.tool_broker import NEED_PREFIX, ToolAdvisor, ToolBroker, ToolResult

logger = logging.getLogger(__name__)

DEFAULT_PONY_PROMPT = (
    "You are a focused assistant. Answer the user directly and concisely. "
    "When a CONTEXT block is present it contains everything relevant that is "
    "already known; use it as fact and do not ask for it again. "
    "Never mention the context block, tools, memory, or how you were given "
    "information. Just answer."
)

ENV_HEADER = "ENVIRONMENT (you are here, now):"
MATERIAL_HEADER = "CONTEXT (known facts, use directly):"
TASK_HEADER = "TASK:"
TOOL_NOTE = (
    "AVAILABLE FOR THIS TASK: {advice}. To use it, reply with exactly one line:\n"
    "NEED: <what you need, in plain words>\n"
    "It will be carried out and the result given to you. Ask for nothing else."
)
TOOL_NOTE_GENERIC = (
    "If you need a file read, a command run, a search, or something looked up, "
    "reply with exactly one line:\nNEED: <what you need, in plain words>\n"
    "It will be carried out and the result given to you."
)


@dataclass(frozen=True)
class Need:
    material: bool = False
    tools: bool = False

    @property
    def nothing(self) -> bool:
        return not self.material and not self.tools


class NeedsAssessor(ABC):
    @abstractmethod
    def assess(self, turn: str) -> Need: ...


class HeuristicNeeds(NeedsAssessor):
    _TRIVIAL = re.compile(
        r"^\s*(hi|hey|hello|yo|ok|okay|thanks|thank you|danke|ja|nein|yes|no|lol|"
        r"sure|cool|nice|good|morning|servus|moin)[\s!.?,]*$", re.I)
    _MEMORY = re.compile(
        r"\b(remember|recall|erinner|was war|earlier|before|last time|previously|"
        r"we (?:did|had|decided|discussed)|my |our |the plan|status|why did|"
        r"notes?|decided|history)\b", re.I)
    _ACTION = re.compile(
        r"\b(read|open|show|cat|list|find|grep|search|run|execute|build|test|"
        r"install|start|stop|restart|edit|write|patch|fix|create|delete|deploy|"
        r"check|log|file|command|script|repo|commit)\b", re.I)
    _MAKE = re.compile(
        r"\b(do|make|give|generate|draft|design|produce|whip up|put together|"
        r"knock up|set up|scaffold|implement|add)\b.{0,30}\b(website|site|page|"
        r"landing|script|dashboard|chart|diagram|doc|docs|report|readme|demo|"
        r"app|tool|api|endpoint|test|suite|config|template|mockup|intro)\b", re.I)

    _FACTUAL = re.compile(
        r"\b(who|what|when|where|which)\b.{0,40}\b(is|are|was|were|made|created|"
        r"built|wrote|owns|maintains|released|founded|invented|behind)\b", re.I)
    _QUESTION = re.compile(r"\?\s*$")

    def assess(self, turn: str) -> Need:
        t = (turn or "").strip()
        if not t or self._TRIVIAL.match(t):
            return Need(False, False)
        if len(t) < 8:
            return Need(False, False)
        factual = bool(self._FACTUAL.search(t))
        return Need(
            material=(bool(self._MEMORY.search(t)) or factual
                      or bool(self._QUESTION.search(t)) or len(t.split()) >= 6),
            tools=bool(self._ACTION.search(t)) or factual
                  or bool(self._MAKE.search(t)))


@dataclass(frozen=True)
class PonyConfig:
    enabled: bool = False
    prompt: str = DEFAULT_PONY_PROMPT
    strip_tools: bool = True
    strip_guidance: bool = False
    material_header: str = MATERIAL_HEADER
    task_header: str = TASK_HEADER
    tool_note: str = TOOL_NOTE
    remind_tools: bool = True
    include_environment: bool = True

    @staticmethod
    def from_config(config: dict) -> "PonyConfig":
        p = (config or {}).get("pony") or {}
        return PonyConfig(
            enabled=bool(p.get("enabled", False)),
            prompt=str(p.get("prompt") or DEFAULT_PONY_PROMPT),
            strip_tools=bool(p.get("strip_tools", True)),
            strip_guidance=bool(p.get("strip_guidance", False)),
            material_header=str(p.get("material_header") or MATERIAL_HEADER),
            task_header=str(p.get("task_header") or TASK_HEADER),
            tool_note=str(p.get("tool_note") or TOOL_NOTE),
            remind_tools=bool(p.get("remind_tools", True)),
            include_environment=bool(p.get("include_environment", True)),
        )


class EnvironmentFacts:
    def snapshot(self) -> str:
        parts = []
        try:
            parts.append(f"cwd: {os.getcwd()}")
        except Exception:
            pass
        try:
            parts.append(f"user: {os.environ.get('USER') or os.environ.get('LOGNAME') or '?'}"
                         f"@{socket.gethostname()}")
        except Exception:
            pass
        try:
            parts.append(f"home: {os.path.expanduser('~')}")
        except Exception:
            pass
        try:
            parts.append("date: " + time.strftime("%Y-%m-%d %H:%M %Z"))
        except Exception:
            pass
        try:
            entries = sorted(os.listdir(os.getcwd()))
            shown = [e for e in entries if not e.startswith(".")][:12]
            if shown:
                more = "" if len(entries) <= len(shown) else f" (+{len(entries)-len(shown)} more)"
                parts.append("here: " + ", ".join(shown) + more)
        except Exception:
            pass
        return "\n".join(parts)


class PonyMode:
    def __init__(self, cfg: PonyConfig, router: Optional[MazeRouter] = None,
                 needs: Optional[NeedsAssessor] = None,
                 advisor: Optional[ToolAdvisor] = None,
                 broker: Optional[ToolBroker] = None,
                 env: Optional["EnvironmentFacts"] = None):
        self._cfg = cfg
        self._router = router
        self._needs = needs or HeuristicNeeds()
        self._advisor = advisor or ToolAdvisor()
        self._broker = broker
        self._env = env or EnvironmentFacts()
        self._stripped_tools = 0
        self._stripped_persona = 0

    @property
    def strip_tools(self) -> bool:
        """Whether pony mode withholds the tool surface (config: pony.strip_tools)."""
        return bool(self._cfg.strip_tools)

    @property
    def strip_guidance(self) -> bool:
        """Whether pony mode also drops capability guidance (config: pony.strip_guidance).

        Default False. The minimal prompt is meant to cut *persona*, not the
        blocks that tell the model which capabilities exist and how to reach
        them. With them gone the agent cannot know it has memory or skills at
        all, and it goes looking on the filesystem for what the prompt should
        have stated.
        """
        return bool(self._cfg.strip_guidance)

    @property
    def enabled(self) -> bool:
        return self._cfg.enabled

    @property
    def stripped_tools(self) -> int:
        return self._stripped_tools

    @property
    def stripped_persona(self) -> int:
        return self._stripped_persona

    @property
    def router(self) -> Optional[MazeRouter]:
        return self._router

    @property
    def broker(self) -> Optional[ToolBroker]:
        return self._broker

    def attach_broker(self, broker: ToolBroker) -> None:
        self._broker = broker

    def environment(self) -> str:
        if not self._cfg.include_environment:
            return ""
        try:
            snap = self._env.snapshot()
        except Exception:
            return ""
        return f"{ENV_HEADER}\n{snap}" if snap else ""

    def tool_note_for(self, turn: str) -> str:
        if not self._cfg.remind_tools:
            return ""
        advice = ""
        try:
            advice = self._advisor.advise(turn)
        except Exception:
            advice = ""
        if advice:
            return self._cfg.tool_note.format(advice=advice)
        return TOOL_NOTE_GENERIC

    def serve(self, reply: str) -> Optional[ToolResult]:
        if not self._cfg.enabled or self._broker is None:
            return None
        try:
            return self._broker.serve(reply)
        except Exception:
            return None

    def apply(self, agent: Any) -> bool:
        if not self._cfg.enabled:
            return False
        try:
            agent.router_prompt = self._cfg.prompt
            if getattr(agent, "ephemeral_system_prompt", None):
                self._stripped_persona = len(agent.ephemeral_system_prompt)
                agent.ephemeral_system_prompt = None
            if self._cfg.strip_tools:
                self._stripped_tools = len(getattr(agent, "tools", None) or [])
                agent.tools = []
                agent.valid_tool_names = set()
                mm = getattr(agent, "_memory_manager", None)
                if mm is not None:
                    try:
                        mm.get_tool_schemas = lambda *a, **k: []
                    except Exception:
                        pass
            return True
        except Exception as exc:
            logger.warning("pony mode not applied: %s", exc)
            return False

    def assess(self, turn: str) -> Need:
        try:
            return self._needs.assess(turn)
        except Exception:
            return Need(False, False)

    def material_for(self, turn: str) -> str:
        if not self._cfg.enabled or self._router is None or not (turn or "").strip():
            return ""
        if not self.assess(turn).material:
            return ""
        try:
            return self._router.fetch(turn).text
        except Exception as exc:
            logger.debug("pony material fetch failed: %s", exc)
            return ""

    def augment(self, turn: str) -> str:
        if not self._cfg.enabled:
            return turn
        need = self.assess(turn)
        if need.nothing:
            return turn
        blocks = []
        env = self.environment()
        if env:
            blocks.append(env)
        material = self.material_for(turn) if need.material else ""
        if material:
            blocks.append(f"{self._cfg.material_header}\n{material}")
        if need.tools:
            note = self.tool_note_for(turn)
            if note:
                blocks.append(note)
        if not blocks:
            return turn
        blocks.append(f"{self._cfg.task_header}\n{turn}")
        return "\n\n".join(blocks)


def _load_config() -> dict:
    try:
        from cli import CLI_CONFIG
        if isinstance(CLI_CONFIG, dict) and CLI_CONFIG:
            return CLI_CONFIG
    except Exception:
        pass
    try:
        from daedalus_cli.config import load_config
        return load_config() or {}
    except Exception:
        return {}


def build_pony_mode(config: Optional[dict] = None) -> PonyMode:
    if config is None:
        config = _load_config()
    cfg = PonyConfig.from_config(config)
    router = None
    if cfg.enabled:
        try:
            router = router_from_config(config)
        except Exception as exc:
            logger.warning("pony router unavailable: %s", exc)
    return PonyMode(cfg, router)
