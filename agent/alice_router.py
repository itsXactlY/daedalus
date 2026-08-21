"""Delegation router for memory-provider tool calls.

Routes a memory tool call through a small, fast router model that picks which
call to make, instead of letting the main model choose. The router's own
argument guesses are ignored — the caller's query always wins.

Endpoint comes from ``delegation.base_url`` in config; nothing is hardcoded.
Every failure path fails OPEN to a direct provider call, so the router is an
optimisation and never a dependency.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ALICE_ROUTE_TOOLS: frozenset = frozenset({
    "mazemaker_recall",
    "mazemaker_recall_multi",
})
ALICE_ROUTE_TIMEOUT = 30.0  # Alice call budget — fail open to direct pod

# ── Coalescing (operator 2026-08-11: "not ONE single call per alice!") ──────
# The bridge must not fire one Alice round-trip per mazemaker call. When a
# burst of mazemaker calls arrives (e.g. 15 x mazemaker_get in one turn),
# only the FIRST routable call within the window consults Alice; the rest
# fail open to the direct pod call. Deterministic tools (get/browse/think/
# stats/remember) are never routed anyway — the guard also makes that
# explicit and cheap before any config load.
ALICE_COALESCE_WINDOW = 2.0  # seconds — one Alice decision per burst
_alice_last_route_ts: float = 0.0
_alice_last_route_lock = threading.Lock()


def _alice_coalesce_allowed() -> bool:
    """True when this call may consult Alice (outside the coalesce window).

    Thread-safe: the concurrent path may fire several mazemaker calls in
    parallel; a lock keeps the decision atomic.
    """
    global _alice_last_route_ts
    now = time.monotonic()
    with _alice_last_route_lock:
        if now - _alice_last_route_ts < ALICE_COALESCE_WINDOW:
            return False
        _alice_last_route_ts = now
        return True


_ROUTE_PROMPT = (
    "Du bist ALICE, der mazemaker-Delegations-Router. "
    "Waehle GENAU EINEN dieser Tools und antworte nur mit "
    "<tool_call>{json}</tool_call>: "
    + ", ".join(sorted(ALICE_ROUTE_TOOLS))
)


def _load_delegation_config() -> dict:
    """Read the delegation block the same way delegate_tool does."""
    try:
        from cli import CLI_CONFIG
        dcfg = (CLI_CONFIG.get("delegation") or {})
    except Exception:
        dcfg = {}
    if not dcfg:
        try:
            from daedalus_cli.config import load_config
            dcfg = (load_config().get("delegation") or {})
        except Exception:
            dcfg = {}
    return dcfg or {}


def normalise_route_name(raw_name: Optional[str]) -> Optional[str]:
    """Map ALICE's tool-name spelling onto the canonical pod name.

    ALICE may emit ``mazemaker_recall``, ``recall`` or ``mazemaker:recall``
    depending on how the query routes. Returns the canonical name when it is
    one of the routable recall tools, else None (-> fail open).
    """
    if not raw_name:
        return None
    norm = str(raw_name).strip().lower().replace(":", "_").replace(" ", "_")
    for canonical in ALICE_ROUTE_TOOLS:
        canonical_low = canonical.lower()
        if norm == canonical_low or norm.endswith(canonical_low.replace("mazemaker_", "")):
            return canonical
    return None


def _parent_query_and_limit(function_args: dict):
    """Extract the parent's truthful query + limit from either call shape.

    recall parents pass ``query``; recall_multi parents pass ``angles``
    (list, first element is the raw user query) + ``k``.
    """
    query = str(function_args.get("query") or "")
    angles = function_args.get("angles")
    if not query and isinstance(angles, list) and angles:
        query = str(angles[0])
    limit = function_args.get("limit") or function_args.get("k") or 3
    return query.strip(), int(limit)


def _parse_alice_choice(alice_text: str, fallback: Optional[str] = None) -> Optional[str]:
    """Scan ALL of Alice's <tool_call> blocks, keep the FIRST recall name.

    The ChatML masker bug (bug:alice-turn-closure-imend-2026-08-11) makes her
    chain 2-3 blocks, the first often carrying an invented query — we only
    need the tool TYPE from her, never her args.

    ``fallback`` is the parent's own tool name: when Alice replies with an
    UNKNOWN name (e.g. hallucinated ``mazemaker_burst`` — not one of
    ALICE_ROUTE_TOOLS), we still treat the bridge as active and route to the
    parent's tool rather than dropping the route (operator 2026-08-11: the
    bridge must not silently vanish on a bad Alice reply).
    """
    for m in re.finditer(r"<tool_call>", alice_text):
        seg = alice_text[m.end():].split("</tool_call>")[0].strip()
        if not seg.startswith("{"):
            continue
        try:
            call = json.loads(seg)
        except Exception:
            continue
        candidate = call.get("function_name") or call.get("name")
        candidate = normalise_route_name(candidate)
        if candidate:
            return candidate
    # ALICE answered but with no routable recall name — keep the bridge
    # active with the parent's tool (parent query still wins).
    if fallback:
        return normalise_route_name(fallback)
    return None


def route_mcp_through_alice(
    function_name: str,
    function_args: dict,
    *,
    execute: Callable[[str, Dict[str, Any]], str],
    is_router: bool = False,
    delegate_depth: int = 0,
    alice_timeout: Optional[float] = None,
) -> Optional[str]:
    """Route a mazemaker_* call through ALICE; return the routed wrapper JSON.

    Returns None when routing is off / not applicable / fails — the caller
    then falls through to its direct pod call. ``execute(name, args)`` runs
    the chosen call against the pod and returns the raw result string (the
    PARENT executes so the raw id/sim result survives for citation).
    ``alice_timeout`` bounds ONLY the ALICE round-trip; the pod call budget
    is the executor's concern. Background paths (prefetch/bootstrap) pass a
    tight budget so a hung router never stalls a turn.
    """
    try:
        if function_name not in ALICE_ROUTE_TOOLS:
            return None
        # Coalesce: only ONE Alice round-trip per burst. Subsequent routable
        # calls within the window fail open to the direct pod call — no
        # per-call router latency: one batched call, not one per item.
        if not _alice_coalesce_allowed():
            return None
        # A routed child (ALICE herself) or a delegated agent must never
        # re-enter the router — that is the recursion the depth guard only
        # catches late, degrading recall into a delegation-error blob.
        if is_router:
            return None
        if delegate_depth > 0:
            return None

        dcfg = _load_delegation_config()
        if not dcfg.get("route_mcp_through_router"):
            return None

        base_url = str(dcfg.get("base_url") or "").strip().rstrip("/")
        api_key = str(dcfg.get("api_key") or "").strip()
        if not base_url:
            return None
        chat_url = base_url.rstrip("/") + "/chat/completions"

        parent_query, parent_limit = _parent_query_and_limit(function_args)
        if not parent_query:
            return None

        import urllib.request
        _user_msg = (
            f"Richte die folgende Anfrage an den passenden mazemaker-"
            f"Tool-Aufruf (genau einer, im Format "
            f"<tool_call>{{json}}</tool_call>):\n\n{parent_query}"
        )
        body = json.dumps({
            "model": str(dcfg.get("model") or "alice-qwen"),
            "messages": [
                {"role": "system", "content": _ROUTE_PROMPT},
                {"role": "user", "content": _user_msg},
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }).encode()
        req = urllib.request.Request(
            chat_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}" if api_key else "",
            },
        )
        _alice_budget = alice_timeout if alice_timeout is not None else ALICE_ROUTE_TIMEOUT
        with urllib.request.urlopen(req, timeout=_alice_budget) as resp:
            raw = json.loads(resp.read())
        alice_text = (
            (raw.get("choices") or [{}])[0]
            .get("message", {}).get("content", "")
            or ""
        )

        chosen_name = _parse_alice_choice(alice_text, fallback=function_name)
        if not chosen_name:
            # ALICE didn't route to a recall (or chained only non-recall
            # names) — fall open to the parent's original call. Never drop
            # the turn.
            return None

        # ALWAYS execute with the PARENT's original query + limit. Build
        # tool-appropriate args (recall_multi requires `angles`, NOT `query`
        # — bug:alice-router-mazemaker-calls-2026-08-11: query-only args make
        # the pod 422).
        if chosen_name == "mazemaker_recall_multi":
            angles = function_args.get("angles")
            chosen_args = {
                "angles": angles if (isinstance(angles, list) and angles) else [parent_query],
                "k": parent_limit,
            }
        else:
            chosen_args = {
                "query": parent_query,
                "limit": parent_limit,
            }

        # The PARENT executes the chosen call against the pod so the raw
        # id/sim result survives for the citation contract.
        routed = execute(chosen_name, chosen_args)
        try:
            routed_json = json.loads(routed) if isinstance(routed, str) else routed
        except Exception:
            routed_json = routed

        # Safety net: transient pod error -> retry ONCE with identical args.
        _routed_is_error = False
        if isinstance(routed_json, dict) and (
            routed_json.get("error")
            or routed_json.get("detail")
            or not routed_json
        ):
            _routed_is_error = True
        elif isinstance(routed_json, str) and (
            "error" in routed_json[:200].lower()
            or not routed_json.strip().startswith("{")
        ):
            _routed_is_error = True

        if _routed_is_error:
            logger.debug(
                "Pod call with parent query errored (%s) — one retry",
                str(routed_json)[:120],
            )
            routed = execute(chosen_name, chosen_args)
            try:
                routed_json = json.loads(routed) if isinstance(routed, str) else routed
            except Exception:
                routed_json = routed

        try:
            _exec_q = json.dumps(chosen_args, ensure_ascii=False)[:200]
        except Exception:
            _exec_q = str(chosen_args)[:200]
        return json.dumps({
            "result": routed_json,
            "executed_query": _exec_q,
            "router": "alice",
            "router_tool": chosen_name,
            "router_args": chosen_args,
            "router_note": "ALICE waehlte diesen mazemaker-Call. Roh-Ergebnis unten.",
        }, ensure_ascii=False)
    except Exception as exc:
        logger.debug("ALICE route failed — fail open to direct call: %s", exc)
        return None
