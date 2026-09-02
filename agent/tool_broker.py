from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

NEED_PREFIX = "NEED:"
_NEED_RE = re.compile(r"^\s*NEED:\s*(.+?)\s*$", re.I | re.M)


_XML_CALL = re.compile(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|\Z)", re.S | re.I)
_XML_FN = re.compile(r"<function\s*=\s*([A-Za-z0-9_.-]+)\s*>", re.I)
_XML_PARAM = re.compile(r"<parameter\s*=\s*([A-Za-z0-9_.-]+)\s*>(.*?)(?:</parameter>|\Z)", re.S | re.I)
_JSON_OBJ = re.compile(r"\{.*\}", re.S)


@dataclass(frozen=True)
class ToolRequest:
    text: str
    tool: str = ""
    args: Optional[dict] = None

    @property
    def explicit(self) -> bool:
        return bool(self.tool)

    @staticmethod
    def _from_native(reply: str) -> Optional["ToolRequest"]:
        m = _XML_CALL.search(reply or "")
        if not m:
            return None
        body = m.group(1)
        fn = _XML_FN.search(body)
        if fn:
            args = {k: v.strip() for k, v in _XML_PARAM.findall(body)}
            return ToolRequest(text=f"{fn.group(1)} {' '.join(args.values())}".strip(),
                               tool=fn.group(1), args=args)
        j = _JSON_OBJ.search(body)
        if j:
            try:
                call = json.loads(j.group(0))
            except Exception:
                return None
            name = call.get("name") or call.get("function_name") or call.get("tool_name")
            if not name:
                return None
            args = call.get("arguments") or call.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            return ToolRequest(text=f"{name} {' '.join(str(v) for v in args.values())}".strip(),
                               tool=str(name), args=args)
        return None

    @staticmethod
    def parse(reply: str) -> Optional["ToolRequest"]:
        if not reply:
            return None
        m = _NEED_RE.search(reply)
        if m:
            want = m.group(1).strip()
            if want:
                return ToolRequest(want)
        return ToolRequest._from_native(reply)


@dataclass(frozen=True)
class ToolPlan:
    tool: str
    args: dict


@dataclass(frozen=True)
class ToolResult:
    request: str
    tool: str
    ok: bool
    output: str

    def as_material(self, cap: int = 4000) -> str:
        body = " ".join((self.output or "").split())[:cap]
        status = "" if self.ok else " (failed)"
        return f"RESULT of «{self.request}»{status}:\n{body}"


class ToolExecutor(ABC):
    @abstractmethod
    def run(self, tool: str, args: dict) -> str: ...

    @abstractmethod
    def available(self) -> set: ...


class CallableExecutor(ToolExecutor):
    def __init__(self, fn: Callable[[str, dict], str], names: set):
        self._fn = fn
        self._names = set(names or ())

    def available(self) -> set:
        return set(self._names)

    def run(self, tool: str, args: dict) -> str:
        return self._fn(tool, args)


class Mapper(ABC):
    @abstractmethod
    def plan(self, request: str, available: set) -> Optional[ToolPlan]: ...


class HeuristicMapper(Mapper):
    _CMD = re.compile(r"(?:run|execute|shell|command)\s*[:\-]?\s*[`\"']?(.+?)[`\"']?\s*$", re.I)
    _PATH = re.compile(r"(/[\w./\-]+|~/[\w./\-]+)")
    _READ = re.compile(r"\b(read|open|show|cat|contents? of|look at)\b", re.I)
    _WRITE = re.compile(r"^\s*write\s+(?P<path>\S+)\s*(?::|\n|$)(?P<body>.*)$",
                        re.I | re.S)
    _FIND = re.compile(r"\b(search|find|grep|locate|which files?)\b", re.I)
    _MEM = re.compile(r"\b(recall|remember|memory|notes?|earlier|previously)\b", re.I)
    _NET = re.compile(r"\b(github|http|https|api|url|fetch|curl|web)\b", re.I)

    def plan(self, request: str, available: set) -> Optional[ToolPlan]:
        r = (request or "").strip()
        if not r:
            return None
        w = self._WRITE.match(r)
        if w and "write_file" in available:
            body = (w.group("body") or "").strip()
            return ToolPlan("write_file", {"path": w.group("path"),
                                           "content": body})
        if self._MEM.search(r) and "mazemaker_recall" in available:
            return ToolPlan("mazemaker_recall", {"query": r, "limit": 5})
        path = self._PATH.search(r)
        if path and self._READ.search(r) and "read_file" in available:
            return ToolPlan("read_file", {"path": path.group(1)})
        if self._FIND.search(r) and "search_files" in available:
            return ToolPlan("search_files", {"pattern": r})
        if "terminal" in available:
            m = self._CMD.search(r)
            if m:
                cmd = m.group(1).strip()
                if cmd and "\n" not in cmd and len(cmd) <= 400:
                    return ToolPlan("terminal", {"command": cmd})
        return None


class ToolAdvisor:
    _RULES = (
        (re.compile(r"\b(github|http|api|url|web|online|latest release|commit)\b", re.I),
         "a shell command can reach the network (curl, gh, git)"),
        (re.compile(r"\b(read|open|show|cat|contents? of|config|file)\b", re.I),
         "a file can be read for you"),
        (re.compile(r"\b(search|find|grep|locate|where is)\b", re.I),
         "the codebase can be searched for you"),
        (re.compile(r"\b(run|execute|build|test|install|start|stop|restart|deploy|log)\b", re.I),
         "a command can be run for you"),
        (re.compile(r"\b(do|make|give|generate|draft|design|produce|write|create|"
                    r"scaffold|implement)\b.{0,30}\b(website|site|page|landing|script|"
                    r"dashboard|chart|diagram|doc|docs|report|readme|demo|app|tool|"
                    r"api|endpoint|config|template|mockup|intro)\b", re.I),
         "a file can be written for you - say NEED: write <path> then the content"),
        (re.compile(r"\b(remember|recall|earlier|previously|notes?|decided)\b", re.I),
         "past memory can be looked up for you"),
        (re.compile(r"\b(who|what|when|where|which)\b.{0,40}\b(is|are|was|were|made|"
                    r"created|built|wrote|owns|maintains|released|founded|invented|"
                    r"behind)\b", re.I),
         "this can be verified rather than guessed - a shell command reaches the "
         "network, and past notes can be looked up"),
    )

    def advise(self, turn: str) -> str:
        hits = [txt for rx, txt in self._RULES if rx.search(turn or "")]
        if not hits:
            return ""
        return "; ".join(dict.fromkeys(hits)[:3] if isinstance(hits, dict) else list(dict.fromkeys(hits))[:3])


class ToolBroker:
    def __init__(self, executor: Optional[ToolExecutor] = None,
                 mapper: Optional[Mapper] = None, output_cap: int = 4000):
        self._exec = executor
        self._mapper = mapper or HeuristicMapper()
        self._cap = output_cap
        self._served = 0
        self._refused = 0
        self._failed = 0

    @property
    def stats(self) -> dict:
        return {"served": self._served, "refused": self._refused, "failed": self._failed}

    def serve(self, reply: str) -> Optional[ToolResult]:
        req = ToolRequest.parse(reply)
        if req is None or self._exec is None:
            return None
        plan = None
        if req.explicit:
            if req.tool in self._exec.available():
                plan = ToolPlan(req.tool, dict(req.args or {}))
            else:
                self._refused += 1
                av = self._exec.available()
                useful = [t for t in ("terminal", "read_file", "write_file",
                                      "search_files", "patch", "execute_code")
                          if t in av]
                rest = sorted(t for t in av if t not in useful)[:6]
                return ToolResult(
                    req.text, "", False,
                    f"There is no tool called '{req.tool}' here. Do not plan - act. "
                    f"Use one of: {', '.join(useful)}"
                    + (f" (also: {', '.join(rest)})" if rest else "")
                    + ". Reply with a single tool call, or NEED: <what you need>.")
        else:
            try:
                plan = self._mapper.plan(req.text, self._exec.available())
            except Exception:
                plan = None
        if plan is None:
            self._refused += 1
            return ToolResult(req.text, "", False,
                              "No matching capability. State the need differently.")
        try:
            out = self._exec.run(plan.tool, plan.args)
            self._served += 1
            return ToolResult(req.text, plan.tool, True, str(out))
        except Exception as exc:
            self._failed += 1
            logger.debug("tool broker %s failed: %s", plan.tool, exc)
            return ToolResult(req.text, plan.tool, False, f"{type(exc).__name__}: {exc}")
