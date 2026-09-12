from __future__ import annotations

import logging
import os
import re
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from agent.maze_router import (Budget, HeuristicNeeds, MazeRouter, Need,
                               NeedsAssessor, router_from_config)
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
    # No router. Pony used to construct one here, and only when it was
    # enabled, which made a persona switch decide whether the harness
    # recalled anything from mazemaker at all. Retrieval belongs to the agent
    # (run_agent._fetch_maze_material) and runs whether pony is on or off.
    #
    # PonyMode still ACCEPTS a router, so material_for/augment remain usable
    # and testable on their own; the production path simply does not hand it
    # one, and material_for returns "" without it.
    return PonyMode(cfg, None)
