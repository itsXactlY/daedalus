"""Route-out distiller: turns raw turns into durable mission state.

The amnesiac architecture soaks every turn verbatim (auto:turn:*) — perfect
recall of WHAT WAS SAID, useless as STATE. This module is the route-OUT
intelligence: after the raw soak, one cheap structured call to the delegation
endpoint (whatever small model holds that seat) extracts what the
mission should REMEMBER:

    {"decisions": [...], "facts": [...], "open_questions": [...], "status": "..."}

Each non-empty item lands in the graph as a curated label (decision:/fact:/
open:/status:) that the deterministic mission briefing reads back IN on every
later turn. Raw soaks are never touched — distillation is purely additive,
fail-open, and bounded (<= MAX_ITEMS per category, <= ITEM_CHARS per item).

Reliability contract: ANY exception, parse failure, or junk verdict returns
None and logs at DEBUG/INFO. The loop degrades to today's behavior, never
worse. Stats counters expose the yield so the bench can grade the router.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_ITEMS = 3
ITEM_CHARS = 400
REQUEST_TIMEOUT = 6.0
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_S = 120.0
MAX_TURNS_CHARS = 2600

_DISTILL_SYSTEM_PROMPT = (
    "Du bist der Gedachtnis-Destillator eines Langzeit-Agenten. Extrahiere aus "
    "dem Dialog NUR dauerhaft relevanten Missionszustand. Antworte AUSSCHLIESSLICH "
    "mit einem JSON-Objekt, keine weiteren Zeichen:\n"
    '{"decisions": ["..."], "facts": ["..."], '
    '"open_questions": ["..."], "status": "..."}\n'
    "Regeln: max 3 Eintrage pro Liste, jeder Eintrag ein pragnanter Satz, "
    "keine Wiederholung des Offensichtlichen, leere Listen ok. "
    '"status" = ein Satz zum aktuellen Stand. Wenn NICHTS dauerhaft Relevantes '
    "vorliegt: alle Listen leer.\n"
    "WICHTIG — WOERTLICHKEIT: Bezeichner wie GOAL-a, DECISION-f, NEEDLE-z1, "
    "Ticket-/Feature-Namen oder Code-Namen MUESSEN Wort fuer Wort im Eintrag "
    "stehen. Paraphrasiere sie NIEMALS weg ('goal a b c' ist ein FEHLER)."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_ID_TOKEN_RE = re.compile(r"\b[A-Z]{3,}(?:-[A-Za-z0-9]+)+\b")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n+")


def _verbatim_guard(user: str, asst: str,
                    parsed: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Return EXTRA (prefix, item) writes for identifier tokens the model
    paraphrased away. Deterministic, cheap, capped."""
    p = parsed or {}
    joined = " ".join(
        list(p.get("decisions", []) or [])
        + list(p.get("facts", []) or [])
        + list(p.get("open_questions", []) or [])
        + ([p["status"]] if isinstance(p.get("status"), str) else list(p.get("status", []) or []))
    )
    covered = set(_ID_TOKEN_RE.findall(joined))
    extras: List[Tuple[str, str]] = []
    for text in (user or "", asst or ""):
        for sent in _SENTENCE_SPLIT_RE.split(text):
            tokens = set(_ID_TOKEN_RE.findall(sent))
            fresh = tokens - covered
            if not fresh:
                continue
            low = sent.lower()
            prefix = ("decision:" if ("decid" in low or "entscheid" in low)
                      else "open:" if any(t.startswith("GOAL") for t in fresh)
                      else "fact:")
            item = f"{'/'.join(sorted(fresh))}: {sent.strip()[:220]}"
            extras.append((prefix, item))
            covered |= fresh
            if len(extras) >= 4:
                return extras
    return extras

_DISTILL_VERBATIM = ("Quote identifiers (GOAL-x, DECISION-y, NEEDLE-z1, ticket/"
                     "feature/codenames) VERBATIM inside items — never paraphrase them away.")
DISTILL_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {"type": "array", "items": {"type": "string"},
                       "description": _DISTILL_VERBATIM},
        "facts": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "status": {"type": "string"},
    },
    "required": ["decisions", "facts", "open_questions", "status"],
}

_stats = {"calls": 0, "parsed": 0, "junk": 0, "errors": 0, "items_written": 0,
          "circuit_skips": 0}
_stats_lock = threading.Lock()
_seen_hashes: set = set()
_seen_lock = threading.Lock()
_consecutive_errors = 0
_breaker_open_until = 0.0


def _circuit_open() -> bool:
    """True while the breaker is open (recent repeated failures) — callers
    skip the HTTP leg entirely so a hung router endpoint can never stall the
    serialized soak worker turn after turn."""
    global _consecutive_errors, _breaker_open_until
    now = time.monotonic()
    if _breaker_open_until > now:
        return True
    if _breaker_open_until and _breaker_open_until <= now:
        _breaker_open_until = 0.0
        _consecutive_errors = BREAKER_THRESHOLD - 1
    return False


def _note_success():
    global _consecutive_errors
    _consecutive_errors = 0


def _note_error():
    global _consecutive_errors, _breaker_open_until
    _consecutive_errors += 1
    if _consecutive_errors >= BREAKER_THRESHOLD:
        _breaker_open_until = time.monotonic() + BREAKER_COOLDOWN_S


def distill_stats() -> dict:
    with _stats_lock:
        return dict(_stats)


def _bump(key: str, n: int = 1) -> None:
    with _stats_lock:
        _stats[key] += n


def _dedupe_ok(item: str) -> bool:
    h = hashlib.sha256(item.strip().lower().encode()).hexdigest()
    with _seen_lock:
        if h in _seen_hashes:
            return False
        _seen_hashes.add(h)
        if len(_seen_hashes) > 4096:
            _seen_hashes.clear()
        return True


def _parse_reply(text: str) -> Optional[Dict[str, List[str]]]:
    """Extract the JSON object; tolerate fences/prose around it."""
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    def _lst(key: str) -> List[str]:
        v = obj.get(key)
        if not isinstance(v, list):
            return []
        out = []
        for item in v[:MAX_ITEMS]:
            if isinstance(item, str) and item.strip():
                out.append(item.strip()[:ITEM_CHARS])
        return out

    status = obj.get("status")
    parsed = {
        "decisions": _lst("decisions"),
        "facts": _lst("facts"),
        "open_questions": _lst("open_questions"),
        "status": [status.strip()[:ITEM_CHARS]]
        if isinstance(status, str) and status.strip() else [],
    }
    return parsed


def distill_turn(user: str, asst: str,
                 base_url: str, api_key: str, model: str) -> Optional[List[Tuple[str, str]]]:
    """Ask the router seat to distill one turn.

    Returns a list of (label_prefix, content) write instructions, or None on
    any failure/junk. NEVER raises.
    """
    try:
        if _circuit_open():
            _bump("circuit_skips")
            return None
        user_c = (user or "")[:MAX_TURNS_CHARS // 2]
        asst_c = (asst or "")[:MAX_TURNS_CHARS // 2]
        body = json.dumps({
            "model": model or "local-distiller",
            "messages": [
                {"role": "system", "content": _DISTILL_SYSTEM_PROMPT},
                {"role": "user", "content":
                    f"=== USER ===\n{user_c}\n\n=== ASSISTANT ===\n{asst_c}"},
            ],
            "temperature": 0.0,
            "max_tokens": 380,
            "response_format": {"type": "json_schema",
                                 "json_schema": {"name": "distill",
                                                  "strict": True,
                                                  "schema": DISTILL_SCHEMA}},
        }).encode()
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}" if api_key else "",
            },
        )
        _bump("calls")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = json.loads(resp.read())
        text = (raw.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        _note_success()
        logger.debug("distill raw reply (%d chars): %s", len(text), text[:400])
        parsed = _parse_reply(text)
        if parsed is None:
            _bump("junk")
            return None
        writes: List[Tuple[str, str]] = []
        for prefix, items in (("decision:", parsed["decisions"]),
                              ("fact:", parsed["facts"]),
                              ("open:", parsed["open_questions"]),
                              ("status:", parsed["status"])):
            for item in items:
                if not _dedupe_ok(f"{prefix}{item}"):
                    continue
                writes.append((prefix, item))
        try:
            for prefix, item in _verbatim_guard(user_c, asst_c, parsed):
                if len(writes) >= 6:
                    break
                if _dedupe_ok(f"{prefix}{item}"):
                    writes.append((prefix, item))
        except Exception:
            pass
        if not writes:
            _bump("junk")
            return None
        _bump("parsed")
        _bump("items_written", len(writes))
        return writes
    except Exception as exc:
        _note_error()
        _bump("errors")
        logger.debug("distill_turn failed (non-fatal): %s", exc)
        return None
