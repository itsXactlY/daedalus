"""Deterministic skill routing for the current task.

The system prompt ships a name-only skills index to keep tokens down (see
``a55e540a2 perf(prompt): compact skills index``). That left skill selection
entirely to LLM compliance — and it failed: the curator sees
``last_activity=never`` on every skill because the model never volunteers a
``skill_view`` call when it cannot tell what a bare name does. The operator
had to command skills explicitly, killing agent autonomy.

This module closes the loop at the *harness* level. At each turn, score every
skill's name + description + category + tags against the user's current
message with a cheap deterministic token-overlap scorer, then inject the top
matches as a fenced context block into the API-bound user message. Discovery
no longer depends on LLM judgment; the model still reads the full SKILL.md
via ``skill_view`` when a routed description matches, and that load is what
bumps curator usage telemetry.

Design constraints (from run_agent.py architecture):
- Injection is API-call-time only (never persisted) so nothing leaks into
  session transcripts, and the stable system-prompt cache prefix is untouched.
- Scoring is pure Python, no LLM, no embeddings, sub-millisecond for 350
  skills. Deterministic: same message → same route.
- Respects the same filters the index uses: platform compatibility, disabled
  skills, conditional-activation rules, snapshot manifest freshness.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokenization + scoring
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Subword stop-words that carry no routing signal. Keep tiny; the min-score
# threshold already rejects most noise.
_STOP = frozenset(
    {
        "the", "a", "an", "and", "or", "for", "with", "into", "from", "that",
        "this", "your", "you", "are", "all", "is", "it", "to", "of", "in",
        "on", "i", "u", "my", "me", "we", "our", "do", "does", "did", "can",
        "could", "should", "would", "will", "not", "no", "yes", "ok", "okay",
        "please", "want", "need", "let", "get", "make", "use", "using", "how",
        "what", "when", "where", "why", "which", "who", "about", "been", "has",
        "have", "had", "at", "by", "be", "as", "if", "than", "then", "so",
        "just", "also", "via", "per", "vs",
    }
)


def _tokens(text: str) -> List[str]:
    """Lowercase alphanumeric tokens, stop-words removed."""
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 1]


# Name matches are far stronger signals than description matches.
_NAME_WEIGHT = 5.0
_CATEGORY_WEIGHT = 1.0
_DESC_WEIGHT = 1.0


def score_skill(query_tokens: List[str], entry: Dict[str, Any]) -> float:
    """Deterministic overlap score for one catalog entry against the query.

    Returns a float in [0, 1] = matched_query_fraction (0 when the query is
    empty). A token matches if it appears in the skill name (5x), category
    (1x) or description (1x). Matching is per-query-token, so a short
    one-topic query scores higher than a long multi-topic one — which is
    exactly what routing wants.
    """
    if not query_tokens:
        return 0.0
    name_text = " ".join(
        _tokens(str(entry.get("skill_name") or "") + " " + str(entry.get("frontmatter_name") or ""))
    )
    cat_text = " ".join(_tokens(str(entry.get("category") or "")))
    desc_text = " ".join(_tokens(str(entry.get("description") or "")))
    name_tokens = set(name_text.split()) if name_text else set()
    cat_tokens = set(cat_text.split()) if cat_text else set()
    desc_tokens = set(desc_text.split()) if desc_text else set()

    hit = 0.0
    for t in query_tokens:
        if t in name_tokens:
            hit += _NAME_WEIGHT
        elif t in cat_tokens:
            hit += _CATEGORY_WEIGHT
        elif t in desc_tokens:
            hit += _DESC_WEIGHT
    return min(hit / (len(query_tokens) * _NAME_WEIGHT), 1.0)


# ---------------------------------------------------------------------------
# Catalog loading (mirrors prompt_builder snapshot semantics)
# ---------------------------------------------------------------------------

def load_skill_catalog(
    available_tools: Optional[set] = None,
    available_toolsets: Optional[set] = None,
    max_age_seconds: float = 300.0,
) -> List[Dict[str, Any]]:
    """Return the routable skill catalog (name/description/category), cached.

    Uses the prompt-builder disk snapshot when fresh; falls back to a
    filesystem scan cached in-process with a TTL. Applies the same
    visibility filters as the skills index: platform, disabled, conditions.
    """
    from agent.prompt_builder import (
        _load_skills_snapshot,
        _skill_should_show,
        iter_skill_index_files,
        _parse_skill_file,
        _build_snapshot_entry,
        extract_skill_conditions,
    )
    from daedalus_constants import get_daedalus_home
    from agent.skill_utils import (
        get_disabled_skill_names,
        skill_matches_platform,
    )

    now = time.monotonic()
    cache = getattr(load_skill_catalog, "_cache", None)
    if cache is not None and now - cache[0] < max_age_seconds:
        return cache[1]

    skills_dir = get_daedalus_home() / "skills"
    if not skills_dir.exists():
        load_skill_catalog._cache = (now, [])
        return []

    entries: List[Dict[str, Any]] = []
    disabled = set(get_disabled_skill_names())

    snapshot = _load_skills_snapshot(skills_dir)
    if snapshot is not None:
        for entry in snapshot.get("skills", []):
            if not isinstance(entry, dict):
                continue
            skill_name = entry.get("skill_name") or ""
            frontmatter_name = entry.get("frontmatter_name") or skill_name
            if frontmatter_name in disabled or skill_name in disabled:
                continue
            if not skill_matches_platform({"platforms": entry.get("platforms") or []}):
                continue
            if not _skill_should_show(
                entry.get("conditions") or {},
                available_tools,
                available_toolsets,
            ):
                continue
            entries.append(entry)
    else:
        for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
            try:
                is_compatible, frontmatter, desc = _parse_skill_file(skill_file)
                if not is_compatible:
                    continue
                entry = _build_snapshot_entry(skill_file, skills_dir, frontmatter, desc)
                skill_name = entry["skill_name"]
                if entry["frontmatter_name"] in disabled or skill_name in disabled:
                    continue
                if not _skill_should_show(
                    extract_skill_conditions(frontmatter),
                    available_tools,
                    available_toolsets,
                ):
                    continue
                entries.append(entry)
            except Exception as e:
                logger.debug("skill router: could not parse %s: %s", skill_file, e)

    load_skill_catalog._cache = (now, entries)
    return entries


# ---------------------------------------------------------------------------
# Public routing API
# ---------------------------------------------------------------------------

_BUNDLE_LOADED_RE = re.compile(r"^Skills loaded: (.+)$", re.MULTILINE)
_SKILL_INVOKED_RE = re.compile(r'invoked the "([^"]+)" skill')


def already_loaded_skill_names(user_text: str) -> set:
    """Skill names already injected into *user_text* by a bundle or direct
    skill invocation this same turn (see build_bundle_invocation_message's
    "Skills loaded: ..." header and build_skill_invocation_message's
    "invoked the "<name>" skill" marker in agent/skill_commands.py).

    Used to keep the auto-router from re-suggesting a skill whose full
    content is already present in the same API-bound message -- wasted
    tokens and confusing duplicate content otherwise.
    """
    names: set = set()
    for m in _BUNDLE_LOADED_RE.finditer(user_text):
        names.update(n.strip() for n in m.group(1).split(",") if n.strip())
    for m in _SKILL_INVOKED_RE.finditer(user_text):
        names.add(m.group(1).strip())
    return names


def route_skills(
    user_text: str,
    top_n: int = 5,
    min_score: float = 0.12,
    available_tools: Optional[set] = None,
    available_toolsets: Optional[set] = None,
    exclude_names: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Return the top-N best-matching skills for *user_text*, deterministic.

    Filters out skills that match on nothing and any name in
    *exclude_names* (already loaded via a bundle/skill invocation this
    turn), then returns entries with a ``_score`` field, best first.
    Empty user text → [].
    """
    query_tokens = _tokens(user_text)
    if not query_tokens:
        return []

    entries = load_skill_catalog(available_tools, available_toolsets)
    scored = []
    for entry in entries:
        if exclude_names and entry.get("skill_name") in exclude_names:
            continue
        s = score_skill(query_tokens, entry)
        if s >= min_score:
            copy = dict(entry)
            copy["_score"] = round(s, 4)
            scored.append(copy)

    scored.sort(key=lambda e: (-e["_score"], e.get("skill_name") or ""))
    return scored[:top_n]


def build_skill_route_block(
    user_text: str,
    top_n: int = 5,
    min_score: float = 0.12,
    available_tools: Optional[set] = None,
    available_toolsets: Optional[set] = None,
    exclude_names: Optional[set] = None,
) -> str:
    """Build the fenced route block to inject into the API-bound user message.

    Empty string when nothing matches above threshold (no injection, no
    token cost). The block carries name + description + category so the
    model can pick the right one deterministically surfaced, then points at
    skill_view for the full instructions.

    *exclude_names*, when omitted, is auto-detected from *user_text* itself
    via already_loaded_skill_names() -- covers the common case (a bundle or
    skill invocation expanded straight into this same message) without the
    caller needing to thread loaded-name state through separately. Pass an
    explicit set to exclude names that aren't detectable that way.
    """
    if exclude_names is None:
        exclude_names = already_loaded_skill_names(user_text)
    routed = route_skills(user_text, top_n, min_score, available_tools, available_toolsets, exclude_names)
    if not routed:
        return ""

    lines = [
        "[auto-routed skills for this task — matched by the harness, deterministic]"
    ]
    for entry in routed:
        name = entry.get("skill_name") or entry.get("frontmatter_name") or "?"
        cat = entry.get("category") or ""
        desc = (entry.get("description") or "").strip().replace("\n", " ")
        if len(desc) > 220:
            desc = desc[:217].rstrip() + "..."
        prefix = f"[{cat}] " if cat else ""
        lines.append(f"• {name} {prefix}— {desc}" if desc else f"• {name} {prefix}")
    lines.append(
        "If any of these matches the task, load its full instructions with "
        "skill_view(\"<name>\") and follow them."
    )
    return "\n".join(lines)
