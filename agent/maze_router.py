from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

WONDERLAND_URL = os.environ.get("MM_WONDERLAND_URL", "http://127.0.0.1:8765").rstrip("/")
MAX_BATCH_GET = 25

DISTILLED_PREFIXES = ("fact:", "decision:", "insight:", "rule:", "invariant:",
                      "ops:", "signal:", "bug:", "status:")
TRANSCRIPT_PREFIXES = ("auto:turn:", "auto:claude:", "auto:hermes-db:", "session:")
DISTILLED_BOOST = 1.30
TRANSCRIPT_PENALTY = 0.60


def _kind_weight(label: str) -> float:
    l = (label or "").lower()
    if l.startswith(DISTILLED_PREFIXES) or "::afe::" in l:
        return DISTILLED_BOOST
    if l.startswith(TRANSCRIPT_PREFIXES):
        return TRANSCRIPT_PENALTY
    return 1.0


class RouterError(Exception):
    pass


class PodError(RouterError):
    pass


@dataclass(frozen=True)
class Budget:
    max_angles: int = 3
    hits_per_angle: int = 5
    overfetch: int = 4
    expand_top_n: int = 6
    material_chars: int = 6000
    snippet_chars: int = 320
    recall_timeout_s: float = 75.0
    get_timeout_s: float = 45.0

    def __post_init__(self) -> None:
        if self.max_angles < 1:
            raise ValueError("max_angles must be >= 1")
        if self.hits_per_angle < 1:
            raise ValueError("hits_per_angle must be >= 1")
        if self.overfetch < 1:
            raise ValueError("overfetch must be >= 1")
        if not 0 <= self.expand_top_n <= MAX_BATCH_GET:
            raise ValueError(f"expand_top_n must be 0..{MAX_BATCH_GET}")
        if self.material_chars < 256:
            raise ValueError("material_chars must be >= 256")


@dataclass(frozen=True)
class Hit:
    memory_id: int
    label: str
    snippet: str
    score: float


@dataclass(frozen=True)
class Material:
    text: str
    hits: tuple[Hit, ...] = ()
    expanded_ids: tuple[int, ...] = ()
    angles: tuple[str, ...] = ()
    elapsed_s: float = 0.0

    @property
    def empty(self) -> bool:
        return not self.text.strip()


class PodClient(ABC):
    @abstractmethod
    def recall(self, query: str, limit: int, timeout_s: float) -> list[Hit]: ...

    @abstractmethod
    def recall_multi(self, queries: list[str], limit: int, timeout_s: float) -> list[Hit]: ...

    @abstractmethod
    def get_many(self, memory_ids: list[int], timeout_s: float) -> dict[int, str]: ...


class Planner(ABC):
    @abstractmethod
    def angles(self, turn: str, budget: Budget) -> list[str]: ...


class HttpPodClient(PodClient):
    def __init__(self, base_url: str = WONDERLAND_URL):
        self._url = base_url.rstrip("/") + "/tools/call"

    def _call(self, name: str, arguments: dict, timeout_s: float) -> Any:
        body = json.dumps({"name": name, "arguments": arguments}).encode()
        req = urllib.request.Request(self._url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                payload = json.loads(resp.read())
        except Exception as exc:
            raise PodError(f"{name}: {exc}") from exc
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise PodError(f"{name}: {payload.get('error')}")
        return payload.get("result") if isinstance(payload, dict) else payload

    @staticmethod
    def _as_hits(result: Any) -> list[Hit]:
        rows = result if isinstance(result, list) else (result or {}).get("memories") or []
        out: list[Hit] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            mid = r.get("id") or r.get("memory_id")
            if mid is None:
                continue
            try:
                mid = int(mid)
            except (TypeError, ValueError):
                continue
            score = r.get("similarity", r.get("score", 0.0))
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0
            out.append(Hit(mid, str(r.get("label") or ""),
                           str(r.get("content") or r.get("snippet") or ""), score))
        return out

    def recall(self, query: str, limit: int, timeout_s: float) -> list[Hit]:
        return self._as_hits(self._call("mazemaker_recall",
                                        {"query": query, "limit": limit}, timeout_s))

    def recall_multi(self, queries: list[str], limit: int, timeout_s: float) -> list[Hit]:
        return self._as_hits(self._call("mazemaker_recall_multi",
                                        {"angles": queries, "k": limit}, timeout_s))

    def get_many(self, memory_ids: list[int], timeout_s: float) -> dict[int, str]:
        if not memory_ids:
            return {}
        res = self._call("mazemaker_get",
                         {"memory_ids": [int(i) for i in memory_ids[:MAX_BATCH_GET]]}, timeout_s)
        if isinstance(res, list):
            rows = res
        else:
            res = res or {}
            rows = res.get("results") or res.get("memories") or []
        out: dict[int, str] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            if r.get("found") is False:
                continue
            body = r.get("memory") if isinstance(r.get("memory"), dict) else r
            mid = body.get("id", r.get("id", r.get("memory_id")))
            content = body.get("content")
            if mid is None or not content:
                continue
            try:
                out[int(mid)] = str(content)
            except (TypeError, ValueError):
                continue
        return out


class HeuristicPlanner(Planner):
    _SPLIT = re.compile(r"\s*(?:\band\b|\bund\b|\bsowie\b|;|\?|,)\s*", re.I)
    _NOISE = re.compile(r"^(please|bitte|hey|hi|ok|okay|lol|ffs)\b[\s,:-]*", re.I)

    def angles(self, turn: str, budget: Budget) -> list[str]:
        text = self._NOISE.sub("", " ".join((turn or "").split())).strip()
        if not text:
            return []
        parts = [p.strip() for p in self._SPLIT.split(text) if len(p.strip()) >= 12]
        seen, out = set(), []
        for p in ([text] + parts):
            k = p.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
            if len(out) >= budget.max_angles:
                break
        return out


class LlmPlanner(Planner):
    SYSTEM = (
        "You split a user request into distinct retrieval queries for a memory graph. "
        'Reply with ONE JSON array of short query strings and nothing else, e.g. ["a","b"]. '
        "One topic means one element. Never explain."
    )
    _ARRAY = re.compile(r"\[.*\]", re.DOTALL)
    _THINK = re.compile(r"<think>.*?</think>", re.DOTALL)

    def __init__(self, base_url: str, model: str, api_key: str = "",
                 timeout_s: float = 20.0, fallback: Optional[Planner] = None):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._key = api_key
        self._timeout = timeout_s
        self._fallback = fallback or HeuristicPlanner()

    def angles(self, turn: str, budget: Budget) -> list[str]:
        body = json.dumps({
            "model": self._model,
            "messages": [{"role": "system", "content": self.SYSTEM},
                         {"role": "user", "content": turn}],
            "temperature": 0.2, "max_tokens": 200,
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode()
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            req = urllib.request.Request(self._url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                txt = json.loads(resp.read())["choices"][0]["message"].get("content") or ""
            txt = self._THINK.sub(" ", txt)
            m = self._ARRAY.search(txt)
            if not m:
                raise ValueError("no array")
            arr = json.loads(m.group(0))
            out = [str(x).strip() for x in arr if str(x).strip()]
            if not out:
                raise ValueError("empty")
            return out[: budget.max_angles]
        except Exception:
            return self._fallback.angles(turn, budget)


class Assembler:
    def __init__(self, budget: Budget):
        self._b = budget

    def build(self, hits: list[Hit], full: dict[int, str]) -> str:
        blocks, used = [], 0
        for h in hits:
            body = full.get(h.memory_id) or h.snippet
            body = " ".join(str(body).split())
            if not body:
                continue
            cap = self._b.material_chars if h.memory_id in full else self._b.snippet_chars
            body = body[:cap]
            head = f"[{h.memory_id}]" + (f" {h.label}" if h.label else "")
            block = f"{head}\n{body}"
            if used + len(block) > self._b.material_chars:
                remaining = self._b.material_chars - used
                if remaining < 120:
                    break
                block = block[:remaining]
            blocks.append(block)
            used += len(block)
            if used >= self._b.material_chars:
                break
        return "\n\n".join(blocks)


class RouterTelemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._c = {"routed": 0, "failed_open": 0, "recall_calls": 0,
                   "get_calls": 0, "hits": 0, "expanded": 0}

    def bump(self, key: str, n: int = 1) -> None:
        with self._lock:
            if key not in self._c:
                raise KeyError(key)
            self._c[key] += n

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._c)


class MazeRouter:
    def __init__(self, pod: PodClient, planner: Optional[Planner] = None,
                 budget: Optional[Budget] = None):
        self._pod = pod
        self._planner = planner or HeuristicPlanner()
        self._budget = budget or Budget()
        self._asm = Assembler(self._budget)
        self._tel = RouterTelemetry()

    @property
    def telemetry(self) -> RouterTelemetry:
        return self._tel

    def _dedupe(self, hits: list[Hit]) -> list[Hit]:
        best: dict[int, Hit] = {}
        for h in hits:
            cur = best.get(h.memory_id)
            if cur is None or h.score > cur.score:
                best[h.memory_id] = h
        return sorted(best.values(),
                      key=lambda h: h.score * _kind_weight(h.label), reverse=True)

    def fetch(self, turn: str) -> Material:
        started = time.perf_counter()
        b = self._budget
        try:
            angles = self._planner.angles(turn, b)
            if not angles:
                return Material(text="", elapsed_s=time.perf_counter() - started)
            want = b.hits_per_angle * b.overfetch
            if len(angles) == 1:
                hits = self._pod.recall(angles[0], want, b.recall_timeout_s)
            else:
                hits = self._pod.recall_multi(angles, want, b.recall_timeout_s)
            self._tel.bump("recall_calls")
            hits = self._dedupe(hits)[: b.hits_per_angle * 2]
            self._tel.bump("hits", len(hits))

            expand = [h.memory_id for h in hits[: b.expand_top_n]]
            full: dict[int, str] = {}
            if expand:
                full = self._pod.get_many(expand, b.get_timeout_s)
                self._tel.bump("get_calls")
                self._tel.bump("expanded", len(full))

            text = self._asm.build(hits, full)
            self._tel.bump("routed")
            return Material(text=text, hits=tuple(hits), expanded_ids=tuple(full.keys()),
                            angles=tuple(angles), elapsed_s=time.perf_counter() - started)
        except Exception:
            self._tel.bump("failed_open")
            return Material(text="", elapsed_s=time.perf_counter() - started)


def router_from_config(config: dict) -> MazeRouter:
    d = (config or {}).get("delegation") or {}
    r = (config or {}).get("routing") or {}
    budget = Budget(
        max_angles=int(r.get("max_angles", 3)),
        hits_per_angle=int(r.get("hits_per_angle", 5)),
        overfetch=int(r.get("overfetch", 4)),
        expand_top_n=int(r.get("expand_top_n", 6)),
        material_chars=int(r.get("material_chars", 6000)),
    )
    pod = HttpPodClient(os.environ.get("MM_WONDERLAND_URL", WONDERLAND_URL))
    planner: Planner = HeuristicPlanner()
    if r.get("llm_planner", False) and d.get("base_url") and d.get("model"):
        planner = LlmPlanner(str(d["base_url"]), str(d["model"]), str(d.get("api_key") or ""))
    return MazeRouter(pod, planner, budget)
