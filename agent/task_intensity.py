"""Task-intensity gauge — maps the current task to a reasoning-effort level.

Operator decision 2026-08-07 (fork: context-budget-manager):
  * EVERYTHING starts LOW. Chatting must not burn thinking budget.
  * The gauge escalates only on demonstrable task weight (multi-step
    instructions, code/system work, tool density, tool errors, explicit
    depth requests).
  * It re-evaluates ON THE FLY: the conversation loop calls it before
    every API call, so a task that grows mid-flight (more tool rounds,
    errors, retries) gets more reasoning automatically.
  * Manual ``/reasoning <level>`` switches auto OFF; ``/reasoning auto``
    switches it back ON. ``agent.reasoning_auto`` is the switch,
    ``agent.reasoning_floor`` the minimum level (default ``low``).

Pure functions, no state, no heavy imports — unit-testable in isolation.
The level set is daedalus_constants.VALID_REASONING_EFFORTS minus
"minimal"/"none": the gauge never selects minimal (reserved for manual
use); its floor is "low" by default.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ── Level ladder ────────────────────────────────────────────────────────
# Gauge levels (ascending). "minimal"/"none" are manual-only.
GAUGE_LEVELS = ("low", "medium", "high", "xhigh", "max", "ultra")
DEFAULT_FLOOR = "low"
_LEVEL_INDEX = {lv: i for i, lv in enumerate(GAUGE_LEVELS)}

# ── Score → level mapping ───────────────────────────────────────────────
# 0-3   → low      (chat, short commands)
# 4-6   → medium   (real task, a few steps)
# 7-9   → high     (multi-step task with tools)
# 10-13 → xhigh    (complex task, tool-heavy, errors)
# 14-17 → max      (deep engineering/audit work)
# 42+   → ultra    (largest, most demanding sessions) # aLca :: this is usually set at 18, but we can set it to 42 for the sake of most local LLM are like 3 generations behind SOTA what fits lower VRAM customer hw.
_SCORE_LEVELS = (
    (42, "ultra"),
    (14, "max"),
    (10, "xhigh"),
    (7, "high"),
    (4, "medium"),
    (0, "low"),
)

# ── Signal lexicons ────────────────────────────────────────────────────
# Heavy task verbs / domains — each occurrence costs points.
_TASK_TERMS = (
    # engineering / analysis imperatives (exact words)
    "audit", "refactor", "redesign", "architect", "architecture",
    "debug", "root cause", "root-cause", "troubleshoot", "investigate",
    "implement", "deploy", "migrate", "migration", "restructure",
    "optimize", "benchmark", "security", "vulnerability", "exploit",
    "deep dive", "deep-dive", "comprehensive", "thorough", "exhaustive",
    "gründlich", "vollständig", "komplett", "architektur", "sicherheit",
    # sustained/unattended-work markers — casual register, but never used
    # for idle chat in practice ("be autonomous", "from scratch", "end to
    # end") the way "comprehensive"/"thorough" aren't either. Added
    # 2026-08-16 after a real build task ("write a website from scratch
    # into <path>... be damn autonomous") scored 2 (low) because none of
    # the formal engineering verbs above matched a casually-phrased but
    # genuinely heavy multi-file build.
    "autonomous", "autonomously", "from scratch", "end to end",
    "end-to-end", "production-ready", "production ready",
)
_TASK_RE = re.compile(
    r"\b(" + "|".join(re.escape(t.strip()) for t in _TASK_TERMS) + r")\b",
    re.IGNORECASE,
)

# German verb stems — prefix-matched so conjugated forms ("debugge",
# "implementiere", "analysiere") hit too. No trailing boundary on purpose.
_TASK_STEMS = (
    "auditier", "analysier", "untersuch", "debug", "refaktorier",
    "implementier", "entwickl", "migrier", "optimier", "sicher",
    "bau", "komplett", "schwachstell", "lück",
)
_TASK_STEM_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in _TASK_STEMS) + r")",
    re.IGNORECASE,
)

# Creation-verb + a concrete target (an explicit filesystem path, or a
# named multi-file deliverable) — gated composite signal, not a bare verb
# match. "write"/"build"/"create" alone are too common in idle chat
# ("write a haiku") to score on their own; combined with a real target
# they are never idle chat ("write a website into /home/x/y/z" is always
# a real, consequential build). This is what a keyword-only classifier
# was missing for casually-phrased-but-heavy tasks — see the 2026-08-16
# note on _TASK_TERMS above.
_BUILD_VERBS = (
    "write", "build", "create", "generate", "produce", "ship",
    "rewrite", "redo", "put together", "spin up", "stand up",
)
_BUILD_VERB_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _BUILD_VERBS) + r")\b",
    re.IGNORECASE,
)
_DELIVERABLE_NOUNS = (
    "website", "site", "app", "application", "page", "system",
    "service", "pipeline", "dashboard", "api", "tool", "script",
    "plugin", "extension", "bot", "agent", "server", "database",
)
_DELIVERABLE_NOUN_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _DELIVERABLE_NOUNS) + r")s?\b",
    re.IGNORECASE,
)


def _build_hit(text: str) -> bool:
    """True when a creation verb co-occurs with a concrete target (an
    explicit path or a named deliverable noun) — the composite signal
    for a real build/deliverable task regardless of formal vocabulary."""
    text = text or ""
    if not _BUILD_VERB_RE.search(text):
        return False
    return bool(_PATH_RE.search(text) or _DELIVERABLE_NOUN_RE.search(text))


# Continuation/status-check phrasing WITHIN an active tool-using task —
# gated composite signal, not a bare word match. "status"/"continue"/
# "keep going" alone are far too common in idle chat to score on their
# own; combined with recent tool-call history in this conversation, they
# mean "don't lose the thread on active work" and deserve at least the
# floor a real task gets. Added 2026-08-16 after a live incident: a
# "poll every minute" follow-up (task intensity 1, low effort) and its
# "hows the status?" check (also low) both fabricated data, while the
# ORIGINAL tool-invoking turn just before them ran at xhigh — the
# fabrication tracked the reasoning-effort drop, not just model quality.
_CONTINUATION_TERMS = (
    "status", "continue", "keep going", "proceed", "go on",
    "any update", "progress", "still there", "you there",
    "weiter", "geht's voran", "wie ist der stand", "stand der dinge",
)
_CONTINUATION_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _CONTINUATION_TERMS) + r")\b",
    re.IGNORECASE,
)


def _continuation_hit(text: str, messages: Optional[List[Dict[str, Any]]]) -> bool:
    """True when a short continuation/status-check message follows recent
    tool-call activity in this conversation — checking on an active task,
    not a generic question that happens to contain the word "status"."""
    text = text or ""
    if not _CONTINUATION_RE.search(text):
        return False
    tools, _errors = _tool_stats(messages or [])
    return tools > 0

# Explicit "reasoning depth" requests — big, immediate jump.
_DEPTH_TERMS = (
    "think hard", "thinking hard", "reason deeply", "deep reasoning",
    "reason about", "denk gründlich", "denke gründlich", "überlege gründlich",
    "denk tief", "denke tief", "tief nachdenken", "deep think",
    "deep audit", "full audit", "deep dive", "deep-dive",
)
_DEPTH_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _DEPTH_TERMS) + r")\b",
    re.IGNORECASE,
)

# Maximum-depth demands — floor jumps straight to max.
_MAX_DEPTH_TERMS = (
    "use maximum reasoning", "max reasoning", "ultra reasoning",
    "maximales reasoning", "maximum reasoning", "ultra",
)
_MAX_DEPTH_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _MAX_DEPTH_TERMS) + r")\b",
    re.IGNORECASE,
)

# Pure-chat acknowledgments — negative points when the turn is tiny.
_CHAT_ACKS = (
    "danke", "ok", "okay", "gut", "weiter", "genau", "aha", "cool",
    "perfekt", "super", "nice", "thanks", "thx", "ja", "nein", "yep",
    "sure", "fine", "great", "klingt gut", "alles klar", "verstanden",
)
_CHAT_ACK_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(a) for a in _CHAT_ACKS) + r")\b",
    re.IGNORECASE,
)

# Code / system-work markers.
_CODE_RE = re.compile(r"```|/\w[\w./-]*\.(?:py|sh|js|ts|yaml|yml|json|md|cpp|h)\b|\.git\b|branch|repo")
_PATH_RE = re.compile(r"(?:/home/|/etc/|/var/|/usr/|~/)")

# Tool-result error markers (message role == "tool").
_ERROR_RE = re.compile(
    r"^\s*(?:Error|Traceback|Exception|FAILED|Failed|❌|✗|timed out|timeout)",
    re.IGNORECASE,
)

# ── Helpers ────────────────────────────────────────────────────────────

def _text_of(message: Dict[str, Any]) -> str:
    """Extract plain text from a message dict (str or multimodal parts)."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part.get("content"), str):
                    parts.append(part["content"])
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return ""


def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    """Return the text of the most recent user message (best effort)."""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return _text_of(message)
    return ""


def _tool_stats(messages: List[Dict[str, Any]]) -> tuple[int, int]:
    """Count tool results and tool-error results in the visible history."""
    tools = 0
    errors = 0
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        tools += 1
        content = message.get("content")
        if isinstance(content, str) and _ERROR_RE.match(content.strip()):
            errors += 1
    return tools, errors


# ── Scoring ────────────────────────────────────────────────────────────

def score_task(
    user_text: str,
    *,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Score the weight of the current task. Higher = heavier.

    Signals:
      * user-message length & structure (word count, bullet density)
      * task imperatives / heavy domain terms (cap 6)
      * explicit reasoning-depth requests (cap 4)
      * code/system markers (cap 2)
      * tool-call density in history (0/1-3/4-8/>8 → 0/1/2/3)
      * tool errors in history (cap 3)
      * pure-chat acknowledgments (negative, floor -2)
    """
    score = 0

    # 1. Length & structure of the driving instruction.
    words = len(re.findall(r"\S+", user_text or ""))
    if words > 300:
        score += 3
    elif words > 120:
        score += 2
    elif words > 40:
        score += 1

    # Bullet / numbered / line-broken requirement density (cap 3).
    bullets = len(re.findall(r"(?:^|\n)\s*(?:[-*•]|\d+[.)])\s+", user_text or ""))
    score += min(bullets // 3, 3)

    # 2. Task imperatives — exact words + German verb stems + creation-verb
    #    with a concrete target (combined cap 8, each hit worth 2: a real
    #    task must clear "low" immediately). Shared with estimate_level's
    #    floor-jump logic via _task_hits so both use the same signal.
    task_hits = _task_hits(user_text or "", messages)
    score += min(task_hits, 8) * 2

    # 3. Explicit depth requests (cap 8) — a direct "think hard" demand
    #    jumps straight past medium.
    score += min(len(_DEPTH_RE.findall(user_text or "")), 8) * 8

    # 4. Code / system markers (cap 2).
    if _CODE_RE.search(user_text or ""):
        score += 1
    if _PATH_RE.search(user_text or ""):
        score += 1

    # 5. Tool density from visible history (cap 3).
    tools, errors = _tool_stats(messages or [])
    if tools > 8:
        score += 3
    elif tools > 3:
        score += 2
    elif tools > 0:
        score += 1

    # 6. Tool errors — the model is struggling; give it more budget (cap 3).
    score += min(errors, 3)

    # 7. Pure-chat acknowledgment on a tiny turn (negative, floor -2).
    #    Only applies when the turn is BOTH short and a chat ack — a short
    #    task ("implementiere das System") must never be discounted.
    if words <= 25 and _CHAT_ACK_RE.match((user_text or "").strip()):
        score -= 1
    if words <= 5 and _CHAT_ACK_RE.match((user_text or "").strip()):
        score -= 1

    return max(score, 0)


def level_for_score(score: int, floor: str = DEFAULT_FLOOR) -> str:
    """Map a score to a gauge level, clamped to the floor."""
    level = "low"
    for threshold, candidate in _SCORE_LEVELS:
        if score >= threshold:
            level = candidate
            break
    return clamp_level(level, floor)


def clamp_level(level: str, floor: str = DEFAULT_FLOOR) -> str:
    """Raise *level* to at least *floor* (both gauge levels)."""
    if level not in _LEVEL_INDEX:
        level = DEFAULT_FLOOR
    if floor not in _LEVEL_INDEX:
        floor = DEFAULT_FLOOR
    if _LEVEL_INDEX[level] < _LEVEL_INDEX[floor]:
        return floor
    return level


def _task_hits(
    user_text: str, messages: Optional[List[Dict[str, Any]]] = None
) -> int:
    """Count combined task-imperative hits (exact words + verb stems +
    creation-verb-with-concrete-target, worth 2 hits since a named build
    target is unambiguous — never idle chat; plus continuation/status-
    check phrasing within an active tool-using task, worth 1 hit)."""
    text = user_text or ""
    hits = len(_TASK_RE.findall(text)) + len(_TASK_STEM_RE.findall(text))
    if _build_hit(text):
        hits += 2
    if _continuation_hit(text, messages):
        hits += 1
    return hits


def estimate_level(
    user_text: str,
    *,
    messages: Optional[List[Dict[str, Any]]] = None,
    floor: str = DEFAULT_FLOOR,
) -> str:
    """Estimate the reasoning-effort level for the current task.

    Score-based mapping (length, structure, tool density, errors) PLUS
    explicit floor jumps, so a single clear task imperative can never sit
    at "low":

      * any task imperative        → at least medium
      * 3+ imperatives / depth ask → at least high
      * 6+ imperatives             → at least xhigh
      * explicit max/ultra demand  → at least max

    Args:
        user_text: The driving user instruction (last user message).
        messages: Optional full message history (tool density/errors).
        floor: Minimum level to return (default "low").

    Returns:
        One of GAUGE_LEVELS, never below *floor*.
    """
    score = score_task(user_text, messages=messages)
    level = level_for_score(score, floor=floor)

    text = user_text or ""
    hits = _task_hits(text, messages)
    if _MAX_DEPTH_RE.search(text):
        level = clamp_level(level, "max")
    elif _DEPTH_RE.search(text):
        level = clamp_level(level, "high")
    elif hits >= 6:
        level = clamp_level(level, "xhigh")
    elif hits >= 3:
        level = clamp_level(level, "high")
    elif hits >= 1:
        level = clamp_level(level, "medium")
    return level


# ── Live hook ──────────────────────────────────────────────────────────

def adjust_agent_reasoning(
    agent: Any,
    messages: List[Dict[str, Any]],
    *,
    floor: Optional[str] = None,
) -> Optional[str]:
    """On-the-fly reasoning adjustment for an agent object.

    Auto mode is OFF unless ``agent.reasoning_auto`` is truthy (the CLI
    enables it from ``agent.reasoning_auto`` in config.yaml). When auto is
    on, re-estimates the task from *messages* and updates
    ``agent.reasoning_config`` in place — the request builder reads it per
    API call, so the very next call uses the new level.

    Never downgrades below ``agent.reasoning_floor`` (default "low").
    Respects explicit disable: ``{"enabled": False}`` stays disabled.

    Returns the applied level, or None when auto is off / disabled.
    """
    if not getattr(agent, "reasoning_auto", False):
        return None

    current = getattr(agent, "reasoning_config", None)
    if isinstance(current, dict) and current.get("enabled") is False:
        return None

    effective_floor = floor or getattr(agent, "reasoning_floor", None) or DEFAULT_FLOOR
    user_text = _last_user_text(messages)
    level = estimate_level(user_text, messages=messages, floor=effective_floor)

    current_effort = ""
    if isinstance(current, dict):
        current_effort = str(current.get("effort") or "").strip().lower()

    if current_effort != level:
        agent.reasoning_config = {"enabled": True, "effort": level}
        vprint = getattr(agent, "_vprint", None)
        if callable(vprint):
            try:
                vprint(
                    f"⚙ reasoning auto: {current_effort or 'unset'} → {level} "
                    f"(task intensity {score_task(user_text, messages=messages)})",
                    force=True,
                )
            except Exception:
                pass
    return level
