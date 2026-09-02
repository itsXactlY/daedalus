"""Route-in mission briefing: deterministic anchors injected every turn.

The amnesiac carries only the last N turns. What keeps a multi-week mission
on rails is re-injecting its STATE each turn: current status, open questions,
standing decisions. This module assembles that block deterministically from
the graph's curated labels (status:/open:/decision: — exactly what the
route-out distiller and operator sessions write), newest-first, hard-capped.

No LLM in the loop by design: this path must be boring, fast, and always
identical for identical state. (A router-model ranker slot exists behind
`delegation` config for later — earn it first.)

Fail-open: pod unreachable or empty state yields "" — turns proceed without
the briefing rather than stalling.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

BRIEFING_TTL_S = 45.0
_SECTIONS = [
    ("status:", "CURRENT STATUS", 2),
    ("open:", "OPEN QUESTIONS", 3),
    ("decision:", "STANDING DECISIONS", 3),
]
_LABEL_TS_RE = re.compile(r":([0-9a-f]{6,}):\d+$")
_BROWSE_SLACK = 16
_HEADER = "[MISSION STATE — assembled from persistent memory; anchors for this task]"
_FOOTER = ("[Mission state only — not new user input. Keep the mission on rails; "
           "recall details on demand.]")

_cache_lock = threading.Lock()
_cache: dict = {}


def briefing_stats_key() -> str:
    return "mission_briefing"


def compose_briefing(
    browse_fn: Callable[[str, int], List[dict]],
    *,
    max_chars: int = 1200,
    timeout: float = 6.0,
    content_contains: Optional[str] = None,
    label_contains: Optional[str] = None,
) -> str:
    """Assemble the briefing block. Never raises.

    Scoping (verify pass 2026-08-25): without it, every agent on the machine
    would inject every other agent's distilled state as authoritative anchors.
    - `label_contains`: keep machine-generated rows whose LABEL embeds the
      caller's mission key; rows whose label carries NO key segment after the
      prefix are operator-curated globals and always stay in scope.
    - `content_contains`: legacy substring scoper (bench support).
    The guardrail footer is RESERVED — truncation can never strip the
    "not new user input" disclaimer exactly when the block is fullest.
    """
    try:
        budget = max(0, max_chars - len(_HEADER) - len(_FOOTER) - 8)
        parts: List[Optional[str]] = []
        for prefix, heading, n in _SECTIONS:
            try:
                rows = browse_fn(prefix, n + _BROWSE_SLACK)
            except Exception:
                continue
            lines: List[str] = []
            seen = set()

            def _keep(row) -> bool:
                content = str(row.get("content", "") or "").strip()
                if not content or content in seen:
                    return False
                if content_contains and content_contains not in content:
                    return False
                if label_contains is not None:
                    seg = str(row.get("label", ""))[len(prefix):]
                    if ":" not in seg and not content:
                        return False
                    if ":" in seg and label_contains not in str(row.get("label", "")):
                        return False
                return True

            scoped = [r for r in rows or [] if _keep(r)]
            machine: List[tuple] = []
            curated: List[dict] = []
            for r in scoped:
                m = _LABEL_TS_RE.search(str(r.get("label", "")))
                if m:
                    machine.append((int(m.group(1), 16), r))
                else:
                    curated.append(r)

            picked_rows: List[dict] = []
            pick_keys = set()

            def _push(r) -> None:
                c = str(r.get("content", "") or "").strip()
                key = c[:140]
                if not c or key in pick_keys:
                    return
                pick_keys.add(key)
                picked_rows.append(r)

            for r in curated:
                if len(picked_rows) >= n:
                    break
                _push(r)
            if machine:
                machine.sort(key=lambda x: x[0])
                ordered = [machine[0][1]] + [r for _, r in reversed(machine)]
                for r in ordered:
                    if len(picked_rows) >= n:
                        break
                    _push(r)
            else:
                for r in scoped:
                    if len(picked_rows) >= n:
                        break
                    _push(r)

            for r in picked_rows:
                if len(lines) >= n:
                    break
                content = str(r.get("content", "") or "").strip()
                if not content or content in seen:
                    continue
                seen.add(content)
                lines.append(f"- {content.splitlines()[0][:220]}")
            if lines:
                section = f"{heading}:\n" + "\n".join(lines)
                parts.append(section)
        parts = [p for p in parts if p]
        if not parts:
            return ""
        used = sum(len(p) for p in parts) + 2 * (len(parts) - 1)
        while used > budget and parts:
            last = parts[-1]
            overflow = used - budget
            if len(last) > overflow + 40:
                parts[-1] = last[: max(0, len(last) - overflow - 1)].rstrip() + "…"
                break
            used -= len(last) + 2
            parts.pop()
        block = _HEADER + "\n\n" + "\n\n".join(parts) + "\n" + _FOOTER
        return block[:max_chars]
    except Exception as exc:
        logger.debug("compose_briefing failed (non-fatal): %s", exc)
        return ""


def cached_briefing(
    session_id: str,
    browse_fn: Callable[[str, int], List[dict]],
    *,
    max_chars: int = 1200,
    label_contains: Optional[str] = None,
) -> str:
    """TTL-cached briefing per session; empty results are NOT cached (pod may
    have been mid-flap — retry next turn)."""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(session_id)
        if hit and now - hit[0] < BRIEFING_TTL_S:
            return hit[1]
    block = compose_briefing(browse_fn, max_chars=max_chars, label_contains=label_contains)
    if block:
        with _cache_lock:
            _cache[session_id] = (now, block)
            if len(_cache) > 64:
                oldest = min(_cache, key=lambda k: _cache[k][0])
                _cache.pop(oldest, None)
    return block


def invalidate(session_id: Optional[str] = None) -> None:
    with _cache_lock:
        if session_id is None:
            _cache.clear()
        else:
            _cache.pop(session_id, None)
