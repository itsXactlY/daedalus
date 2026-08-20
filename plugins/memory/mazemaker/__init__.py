"""Mazemaker memory provider.

Implements the ``MemoryProvider`` ABC. Enable with ``memory.provider: mazemaker``
in config.yaml. Talks to a Mazemaker pod over HTTP; the endpoint defaults to
``http://127.0.0.1:8765`` and is overridden with ``MM_WONDERLAND_URL``.

Two responsibilities:
  * ``sync_turn``  — writes each completed turn to the pod. Fire-and-forget:
    it never blocks the turn.
  * ``prefetch``   — before each model call, asks the pod for context relevant
    to the current query and injects it.

Degrades safely: if the pod is unreachable both paths fail silently and the
agent runs on its normal context window, so a missing pod is a no-op rather
than an error.

Tunables are the module-level constants below; each is documented inline.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

WONDERLAND_URL = os.environ.get("MM_WONDERLAND_URL", "http://127.0.0.1:8765")
TOOL_CALL_URL = WONDERLAND_URL + "/tools/call"
MAX_CONTENT_CHARS = 3200

# ── prefetch tuning ────────────────────────────────────────────────
# Deliberately small: prefetch runs before each LLM call and must not
# stall the turn. The per-query cache makes the repeated API calls inside
# one agent turn (same query) free.
SIM_FLOOR = 0.40            # match the policy's "answer-from-hit" threshold
RECALL_LIMIT = 6            # how many hits to ask the pod for
RECALL_SHOW = 3             # how many hits to inject (leave budget for the layers)
RECALL_CLIP = 230           # per-hit content preview length
THINK_DEPTH = 2             # spreading-activation depth around the top hit
THINK_SHOW = 5              # graph neighbours to inject
AFE_SHOW = 4                # atomic facts (from the top hit) to inject
PREFETCH_TTL = 5.0          # seconds a per-query prefetch result is reused
MIN_QUERY_LEN = 2

# how often (in seconds) a turn may actually hit the pod — soak is
# fire-and-forget, but a hard outage shouldn't turn into a retry storm.
_SOAK_MIN_INTERVAL = 0.1

# ── session-resume tuning ───────────────────────────────────────────
# Cross-session continuity: on a fresh session the provider seeds the
# system prompt ONCE with the previous session's tail + open goals (see
# continuity_context / session_resume_context). Cheap, bounded, pod-down
# safe — boot must never stall on this.
RESUME_QUERY = "current task ongoing work open goals status"
RESUME_TAIL_FETCH = 24          # auto:turn rows to scan for the tail (Claude and
                                # other agents soak too — need room to find THIS
                                # agent family's sessions in the recency window)
RESUME_TAIL_LIMIT = 3           # turns from the tail session to show
RESUME_GOALS_LIMIT = 3          # curated goal hits to show
RESUME_GOAL_PREFIXES = ("decision:", "ops:")
# Daedalus sessions soak with timestamp ids (YYYYMMDD_HHMMSS_*); Claude/UUID and
# other agents are a different family and must not leak into the daedalus tail.
_DAEDALUS_SESSION_RE = re.compile(r"^\d{8}_\d{6}_")
RESUME_BLOCK_CHARS = 2400       # hard ceiling for the whole block (~650 tokens)
RESUME_TIMEOUT = 1.8            # per pod call — compose must never stall boot


def _tool(name: str, arguments: dict, timeout: float = 8.0) -> Any:
    """Call a wonderland tool and return its ``result``, or None on any failure."""
    body = json.dumps({"name": name, "arguments": arguments}).encode()
    req = urllib.request.Request(
        TOOL_CALL_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    result = data.get("result") if isinstance(data, dict) else None
    return result


def _pod_tool_result_json(name: str, arguments: dict) -> str:
    """Call the pod and return the result as a JSON string (error JSON on failure).

    Executor callback for the ALICE delegation bridge: the router needs the
    raw pod result as a string so it can attach executed_query metadata.
    """
    try:
        res = _tool(name, arguments, timeout=30.0)
    except Exception as exc:
        return json.dumps({"error": f"mazemaker tool {name} failed: {exc}"})
    if res is None:
        return json.dumps({"error": f"mazemaker tool {name} returned nothing"})
    if isinstance(res, str):
        return res
    return json.dumps(res, ensure_ascii=False)


def _remember(label: str, content: str) -> Optional[int]:
    """POST a mazemaker_remember call to the local wonderland pod."""
    try:
        res = _tool("mazemaker_remember", {"label": label, "content": content})
        if isinstance(res, dict):
            return res.get("id")
        return None
    except Exception as e:
        logger.debug("mazemaker_remember failed (non-fatal): %s", e)
        return None


class MazemakerMemoryProvider(MemoryProvider):
    """Soak + on-demand recall against the local mazemaker pod."""

    def __init__(self, **kwargs) -> None:
        self._session_id = ""
        self._turn_count = 0
        self._prefetch_cache: Dict[str, tuple] = {}
        self._cache_lock = threading.Lock()
        self._last_soak_ts = 0.0
        self._resume_block = ""
        self._brain_ready: Optional[bool] = None

    # ── lifecycle ────────────────────────────────────────────────────

    def name(self) -> str:
        return "mazemaker"

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id or ""
        self._turn_count = 0
        self._resume_block = ""
        # Brain-readiness boot probe — one cheap call, non-blocking. Soak,
        # recall, continuity and skill awareness all degrade gracefully until
        # the brain answers; is_available() reports this flag.
        self._brain_ready = self.brain_ready()
        logger.info(
            "mazemaker provider: brain %s (session=%s)",
            "READY" if self._brain_ready else "OFFLINE", self._session_id,
        )

    def brain_ready(self, refresh: bool = False) -> bool:
        """Cached liveness probe for the mazemaker brain (wonderland MCP front).

        One cheap mazemaker_stats call per session; ``refresh=True`` re-probes
        (used lazily when a later call needs to find the brain back online).
        """
        if self._brain_ready is not None and not refresh:
            return self._brain_ready
        try:
            res = _tool("mazemaker_stats", {}, timeout=1.5)
            self._brain_ready = isinstance(res, dict) and "memories" in res
        except Exception:
            self._brain_ready = False
        return self._brain_ready

    def is_available(self) -> bool:
        return self.brain_ready()

    def get_config_schema(self) -> List[Dict[str, Any]]:
        """Zero-config provider — no setup prompts needed."""
        return []

    # ── per-turn hooks ───────────────────────────────────────────────

    def sync_turn(self, user: str, asst: str, **kwargs) -> None:
        """SOAK this turn into the mazemaker pod (fire-and-forget).

        Called by the MemoryManager after every assistant response.
        Writes label ``auto:turn:<session_id>:<ts>`` so the full history
        lives in the graph — recallable on demand, not carried in context.
        """
        self._turn_count += 1
        now = time.time()
        if now - self._last_soak_ts < _SOAK_MIN_INTERVAL:
            return
        self._last_soak_ts = now

        ts = int(now)
        label = f"auto:turn:{self._session_id}:{ts:x}"
        content = (
            f"session:{self._session_id} @ "
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n"
            f"=== USER ===\n{user}\n\n"
            f"=== ASSISTANT ===\n{asst}"
        )
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n…[truncated]"
        _remember(label, content)

    def prefetch(self, query: str, *, session_id: str = "", **kwargs) -> str:
        """Inject the recall hit PLUS its graph neighbours and AFE facts.

        Returns plain text (the MemoryManager wraps it in <memory-context>).
        Cached per query for PREFETCH_TTL so the repeated API calls inside
        one agent turn don't re-hit the pod. Never raises — any failure
        degrades to fewer layers or an empty string.
        """
        if not query or len(query.strip()) < MIN_QUERY_LEN:
            return ""
        q = query.strip()
        now = time.time()
        with self._cache_lock:
            cached = self._prefetch_cache.get(q)
            if cached and now - cached[0] < PREFETCH_TTL:
                return cached[1]

        block = self._build_enriched_context(q)
        with self._cache_lock:
            self._prefetch_cache[q] = (now, block)
        return block

    def queue_prefetch(self, query: str, *, session_id: str = "", **kwargs) -> None:
        """Prefetch now; the cache makes the loop's later prefetch calls free."""
        self.prefetch(query, session_id=session_id)

    def history_pointer(self, session_id: str = "") -> str:
        """Return a compact pointer to this conversation's soaked history.

        The full transcript lives in the pod as ``auto:turn:<session>:*``
        memories (see sync_turn). Instead of carrying it in context, the agent
        ships this pointer — the model knows the history is recallable on
        demand via mazemaker_get / mazemaker_recall / the pod's tools.
        """
        sid = session_id or self._session_id
        if not sid:
            return ""
        return (
            f"Full conversation history for this session ({sid}) is stored in "
            f"mazemaker as auto:turn:{sid}:* memories. It is NOT carried in "
            f"context — recall specific turns with mazemaker_get, or ask the pod "
            f"via mazemaker_recall when you need something from earlier in this "
            f"conversation."
        )

    def on_session_switch(
        self, new_session_id: str, *, parent_session_id: str = "", reset: bool = False, **kwargs
    ) -> None:
        """Update internal session_id when compression or /resume rotates it."""
        self._session_id = new_session_id or ""
        if reset:
            # Genuinely new conversation — recompose the resume block.
            self._resume_block = ""

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """Archive conversation turns before compression discards them."""
        try:
            ts = int(time.time())
            label = f"auto:compression:{ts:x}"
            content = (
                f"Compression archive at "
                f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n"
            )
            turn_pairs = []
            for msg in reversed(messages):
                role = msg.get("role", "")
                if role in ("user", "assistant") and msg.get("content"):
                    turn_pairs.insert(
                        0, f"=== {role.upper()} ===\n{msg.get('content', '')}"
                    )
                if len(turn_pairs) >= 12:
                    break
            if turn_pairs:
                content += "\n\n".join(turn_pairs)
            _remember(label, content[:MAX_CONTENT_CHARS])
            return f"[{len(messages)} turns archived to mazemaker before compression]"
        except Exception as e:
            logger.debug("on_pre_compress failed: %s", e)
            return ""

    # ── cross-session continuity ──────────────────────────────────────
    # Implements the MemoryProvider ABC `continuity_context` hook that
    # MemoryManager.continuity_context_all() fans out to. run_agent seeds
    # the session's system prompt with this block once (via
    # _build_system_prompt), so a fresh session picks up where the last one
    # left off instead of starting from zero. Composed lazily, cached for
    # the session, never blocks boot (RESUME_TIMEOUT-bound, pod-down safe).

    def continuity_context(self, session_id: str = "") -> str:
        """Return the cross-session resume block (previous tail + open goals)."""
        return self.session_resume_context(session_id=session_id)

    def session_resume_context(self, session_id: str = "") -> str:
        """Compose the resume block once per session; cache the result.

        Tail: the last few soaked ``auto:turn`` rows (this session's own on
        continuation, else the most recent other session). Goals: curated
        status/decision/project/ops/fact memories about the current task.
        Hard-clipped to RESUME_BLOCK_CHARS. Never raises — pod down yields "".
        """
        if self._resume_block:
            return self._resume_block
        if self._brain_ready is False:
            # Brain was offline at boot — cheap re-probe; it may be back now.
            self.brain_ready(refresh=True)
        block = self._compose_resume(session_id or self._session_id or "")
        self._resume_block = block
        return block

    def _compose_resume(self, session_id: str) -> str:
        parts = []

        # ── tail: recent soaked turns from THIS agent family ─────────
        # Only daedalus-family sessions (id = YYYYMMDD_HHMMSS_*). Claude/UUID and
        # other agents soak auto:turn too — letting them leak in would make the
        # block show the wrong "where I left off".
        tail_lines = []
        try:
            res = _tool("mazemaker_browse", {
                "label_prefix": "auto:turn:", "limit": RESUME_TAIL_FETCH,
            }, timeout=RESUME_TIMEOUT)
            rows = []
            if isinstance(res, dict):
                rows = res.get("memories") or res.get("result") or []
            elif isinstance(res, list):
                rows = res
            turns = []
            for m in rows:
                label = str(m.get("label", "") or "")
                content = str(m.get("content", "") or "")
                if not label.startswith("auto:turn:"):
                    continue
                if "Review the conversation above" in content:
                    continue  # auto-nudge, not real content
                _sid = label[len("auto:turn:"):].rsplit(":", 1)[0]
                if not _DAEDALUS_SESSION_RE.match(_sid):
                    continue  # not this agent family — skip
                turns.append((_sid, content))
            if turns:
                # Most recent genuine daedalus turns — that IS "where we left
                # off". On a continued session it's the current session's own
                # tail; on a fresh session the previous daedalus session(s)'.
                for _s, c in turns[-RESUME_TAIL_LIMIT:]:
                    # strip the "session:...@..." header line
                    body = c.split("\n", 1)[1] if "\n" in c else c
                    body = self._clip(self._clean(body), RECALL_CLIP)
                    if body:
                        tail_lines.append(f"[session {_s[:16]}] {body}")
        except Exception as e:
            logger.debug("session_resume tail failed: %s", e)

        if not tail_lines:
            return ""  # no own-session history → nothing to resume

        parts.append("Previous session — last turns (recalled from mazemaker):")
        parts.extend(tail_lines)

        # ── goals: recent curated work (decision:/ops:) ──────────────
        # Browse by recency instead of fuzzy recall: the most recent decisions
        # and ops ARE the operator's actual ongoing work. Skip status: (pod
        # test snapshots are noise) — it drifted into the block before.
        goal_lines = []
        try:
            seen = set()
            for prefix in RESUME_GOAL_PREFIXES:
                res = _tool("mazemaker_browse", {
                    "label_prefix": prefix, "limit": RESUME_GOALS_LIMIT + 2,
                }, timeout=RESUME_TIMEOUT)
                rows = []
                if isinstance(res, dict):
                    rows = res.get("memories") or res.get("result") or []
                elif isinstance(res, list):
                    rows = res
                for m in rows:
                    if len(goal_lines) >= RESUME_GOALS_LIMIT:
                        break
                    label = str(m.get("label", "") or "")
                    body = self._clip(self._clean(m.get("content", "")), RECALL_CLIP)
                    if body and label not in seen:
                        seen.add(label)
                        goal_lines.append(f"[{label}] {body}")
                if len(goal_lines) >= RESUME_GOALS_LIMIT:
                    break
        except Exception as e:
            logger.debug("session_resume goals failed: %s", e)

        if goal_lines:
            parts.append("Open work / ongoing goals (curated from mazemaker):")
            parts.extend(goal_lines)

        parts.append(
            "[Prior-session context only — not new user input. Continue the work "
            "above; full history is recallable on demand via mazemaker_recall / "
            "mazemaker_get.]"
        )
        block = "\n".join(parts)
        return block[:RESUME_BLOCK_CHARS]

    # ── tool surface (expose the pod's mazemaker tools to the agent) ───
    # The agent can call mazemaker_recall / mazemaker_remember / mazemaker_get /
    # mazemaker_think / ... directly (dispatched to the pod's /tools/call), on
    # top of the automatic soak prefetch. Schemas are fetched live from the pod
    # so the surface never drifts from the engine's actual tool set.
    #
    # CURATED allowlist (2026-08-10): the pod exposes 34 tools, but only the
    # context-maintenance core belongs in the agent's function-calling surface.
    # The rest (prune, delete_by_labels, ablate, rebake, connections_import,
    # dream_* phase triggers, list/count_by_label_prefix, diagnose, quota, …)
    # are operator/admin surface — shipping their verbose schemas on every
    # request bloated the harness prompt past the 32K context of the small
    # orchestrator model (32,837 tok measured). If a tool is not in this set
    # it is still callable by the pod itself and by this provider's internal
    # _tool() paths — it is just not offered to the LLM.
    AGENT_TOOL_ALLOWLIST = frozenset({
        "mazemaker_recall",
        "mazemaker_recall_multi",
        "mazemaker_remember",
        "mazemaker_think",
        "mazemaker_get",
        "mazemaker_graph",
        "mazemaker_stats",
        "mazemaker_health",
        "mazemaker_browse",
        "mazemaker_dream_stats",
        "mazemaker_classify_intent",
        "mazemaker_afe_facts",
    })

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return the pod's mazemaker MCP tools in OpenAI function format.

        Filtered to ``AGENT_TOOL_ALLOWLIST`` — the context-maintenance core.
        """
        try:
            with urllib.request.urlopen(
                f"{WONDERLAND_URL}/tools", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tools = data if isinstance(data, list) else (
                data.get("tools") or data.get("result") or []
            )
            schemas: List[Dict[str, Any]] = []
            for t in tools:
                if not isinstance(t, dict) or not t.get("name"):
                    continue
                if t["name"] not in self.AGENT_TOOL_ALLOWLIST:
                    continue
                # FLAT format: memory_manager.add_provider / get_all_tool_schemas
                # read schema.get("name") at the TOP level to build routing +
                # the agent tool surface; run_agent wraps this as
                # {"type": "function", "function": schema}.
                schemas.append({
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {
                        "type": "object", "properties": {},
                    }),
                })
            return schemas
        except Exception as e:
            logger.debug("get_tool_schemas failed (pod reachable?): %s", e)
            return []

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """Dispatch a mazemaker tool call to the pod and return its result."""
        # Context-critical calls get a longer timeout. recall / recall_multi /
        # think do a live embed + graph search over the 200k+ memory corpus and
        # can legitimately exceed the 8s default under load — on a resumed,
        # just-compressed session the bootstrap recall timed out at 8s and the
        # agent got NO history path (the "trashtier amnesia"). Everything else
        # stays at the tight default.
        _timeout = (
            30.0
            if tool_name in (
                "mazemaker_recall",
                "mazemaker_recall_multi",
                "mazemaker_think",
                "mazemaker_get",
            )
            else 8.0
        )
        result = _tool(tool_name, args, timeout=_timeout)
        if result is None:
            return json.dumps({"error": f"mazemaker tool {tool_name} failed"})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    def shutdown(self) -> None:
        pass

    # ── internals ─────────────────────────────────────────────────────

    def _multi_angle_recall(self, query: str) -> List[Dict[str, Any]]:
        """Recall with a couple of rephrasings and fuse the results.

        When a delegation router is configured the recall is routed through it;
        the provider's own angles always execute regardless of what the router
        returns. The router call has a tight timeout and any failure fails OPEN
        to the direct pod calls below, so a slow or dead router never stalls a
        turn.
        """
        angles = [
            query,
            self._angles(query),
        ]
        try:
            from agent.alice_router import route_mcp_through_alice as _alice_route
            _routed = _alice_route(
                "mazemaker_recall_multi",
                {"angles": angles, "k": RECALL_LIMIT},
                execute=_pod_tool_result_json,
                alice_timeout=8.0,
            )
            if _routed is not None:
                try:
                    _rw = json.loads(_routed)
                except Exception:
                    _rw = None
                if isinstance(_rw, dict):
                    _res = _rw.get("result")
                    if isinstance(_res, list):
                        return _res
                    if isinstance(_res, dict) and not (_res.get("error") or _res.get("detail")):
                        return [_res]
        except Exception:
            pass  # fall through to the direct pod calls below
        try:
            res = _tool("mazemaker_recall_multi", {"angles": angles, "k": RECALL_LIMIT},
                        timeout=30.0)
            if isinstance(res, list):
                return res
            if isinstance(res, dict) and "result" in res:
                r = res["result"]
                if isinstance(r, list):
                    return r
        except Exception as e:
            logger.debug("mazemaker_recall_multi failed: %s", e)
        # fall back to single recall
        try:
            res = _tool("mazemaker_recall", {"query": query, "limit": RECALL_LIMIT},
                        timeout=30.0)
            if isinstance(res, list):
                return res
        except Exception as e:
            logger.debug("mazemaker_recall failed: %s", e)
        return []

    def _angles(self, query: str) -> str:
        """A mild rephrasing for the multi-angle recall."""
        stripped = query.strip()
        if not stripped:
            return query
        return f"{stripped} context history past decisions"

    def _think_neighbours(self, memory_id: int) -> List[Dict[str, Any]]:
        """Graph-connected neighbours around a memory id (spreading activation)."""
        try:
            res = _tool(
                "mazemaker_think",
                {"memory_id": int(memory_id), "depth": THINK_DEPTH},
                timeout=30.0,
            )
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                # wonderland may wrap as {"nodes": [...]} or {"result": [...]}
                for key in ("nodes", "result", "neighbours"):
                    val = res.get(key)
                    if isinstance(val, list):
                        return val
        except Exception as e:
            logger.debug("mazemaker_think failed: %s", e)
        return []

    def _afe_facts(self, memory_id: int) -> List[Dict[str, Any]]:
        """Atomic facts extracted from the top hit."""
        try:
            res = _tool(
                "mazemaker_afe_facts",
                {"source_id": int(memory_id), "limit": AFE_SHOW},
            )
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                val = res.get("facts") or res.get("result")
                if isinstance(val, list):
                    return val
        except Exception as e:
            logger.debug("mazemaker_afe_facts failed: %s", e)
        return []

    def _build_enriched_context(self, query: str) -> str:
        """Compose the recall block: hits + neighbours + AFE facts."""
        parts = []
        hits = self._multi_angle_recall(query)
        strong = [h for h in hits if float(h.get("similarity", 0) or 0) >= SIM_FLOOR]
        shown = strong[:RECALL_SHOW] if strong else hits[:RECALL_SHOW]

        if shown:
            hit_lines = []
            for h in shown:
                cid = h.get("id")
                sim = h.get("similarity", 0)
                body = self._clean(h.get("content", ""))
                preview = self._clip(body, RECALL_CLIP)
                hit_lines.append(
                    f"[id {cid}, sim {sim:.2f}] {preview}"
                )
            parts.append("RECALLED FROM MAZEMAKER:\n" + "\n".join(hit_lines))

            # Layers around the top hit
            top_id = shown[0].get("id")
            if top_id is not None:
                neighbours = self._think_neighbours(top_id)
                if neighbours:
                    nb_lines = []
                    for n in neighbours[:THINK_SHOW]:
                        nb_lines.append(
                            self._clip(self._clean(n.get("content", "")), RECALL_CLIP)
                        )
                    parts.append("RELATED (graph neighbours):\n" + "\n".join(nb_lines))

                facts = self._afe_facts(top_id)
                if facts:
                    fact_lines = []
                    for f in facts[:AFE_SHOW]:
                        fact_lines.append(self._clip(self._clean(str(f.get("fact", f))), RECALL_CLIP))
                    parts.append("ATOMIC FACTS:\n" + "\n".join(fact_lines))

        if not parts:
            return ""
        return "\n\n".join(parts)

    @staticmethod
    def _clean(text: Any) -> str:
        if not text:
            return ""
        return str(text).replace("\x00", "")

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "…[truncated]"
