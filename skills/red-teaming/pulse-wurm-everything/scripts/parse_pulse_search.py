#!/usr/bin/env python3
"""
parse_pulse_search.py — Helper for unwrapping mcp__pulse__pulse_search output.

The MCP tool returns a double-wrapped JSON structure:
    {"result": "<STRINGIFIED JSON>"}      ← MCP transport wrapper
      └─ json.loads(outer["result"])      ← unwrap to API response
          └─ {"status": 200, "body": {    ← API envelope (nested "body")
              "topic": "...",
              "ranked_candidates": [...], ← NOT "candidates"
              "items_by_source": {...},
              ...

Usage from execute_code:
    import sys
    sys.path.insert(0, "/home/alca/.hermes/skills/pulse-wurm-everything/scripts")
    from parse_pulse_search import parse_search_file, filter_unvisited

    cands = parse_search_file("/tmp/hermes-results/call_function_*.txt")
    unvisited = filter_unvisited(cands, visited_urls_set, source_seed="...")

What this script does NOT do:
    - It does not call pulse_search — that's the MCP tool's job.
    - It does not call pulse_dig. (As of 2026-06-20, pulse_dig IS functional —
      the prior EMPTY_SEED blocker was a JSON-format issue, not a server bug.
      Use the format documented in references/cron-tick-playbook.md
      "Known Blocker: pulse_dig EMPTY_SEED Format Error" section.)
    - It does not call mazemaker_remember — that's the operator's decision after triage.

Cluster-bloat discipline still applies: most unvisited URLs will fit existing
clusters (OpenAI engineering, agent-security papers, etc.). Mark visited,
skip mazemaker_remember for cluster bloat — see references/cron-tick-playbook.md
"Cluster Bloat Discipline" section for the decision rule.
"""

import json
from typing import Any


def parse_search_text(raw_text: str) -> dict:
    """Unwrap a raw pulse_search MCP response text and return the inner body.

    Returns the inner body dict (the one with topic, ranked_candidates, etc.).
    Raises ValueError on malformed input.

    Handles two envelope shapes:
      1. Plain MCP transport: `{"result": "<stringified JSON>"}`  (most common)
      2. Persisted-to-/tmp variant: the above wrapped inside
         `<untrusted_tool_result>...</untrusted_tool_result>` tags plus a leading
         explanatory paragraph. The persisted variant appears when the result
         was large enough to be saved to /tmp/hermes-results/call_*.txt and
         re-loaded later. (Confirmed 2026-06-20 ~08:00 UTC tick: the helper
         raised `ValueError: outer JSON parse failed` on persisted results;
         manual regex-strip was needed as a workaround.)
    """
    text = raw_text
    # Strip the persisted /tmp file wrapper if present. The wrapper is
    # `<untrusted_tool_result source="...">`, then a free-form explanation
    # paragraph, then the JSON envelope, then `</untrusted_tool_result>`.
    if "<untrusted_tool_result" in text:
        # Find the first `{` after the opening tag (skips the explanation).
        import re as _re
        m = _re.search(r"\{", text)
        if not m:
            raise ValueError("untrusted_tool_result wrapper present but no JSON object found")
        text = text[m.start():]
        text = _re.sub(r"</untrusted_tool_result>\s*$", "", text)

    try:
        outer = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"outer JSON parse failed: {e}")

    result_str = outer.get("result")
    if not isinstance(result_str, str):
        raise ValueError(f"outer['result'] is not a string: {type(result_str).__name__}")

    try:
        api_response = json.loads(result_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"inner API JSON parse failed: {e}")

    body = api_response.get("body")
    if not isinstance(body, dict):
        raise ValueError(f"api_response['body'] is not a dict: {type(body).__name__}")

    return body


def parse_search_file(file_path: str) -> dict:
    """Read a /tmp/hermes-results/call_function_*.txt file and unwrap it."""
    with open(file_path) as f:
        raw_text = f.read()
    return parse_search_text(raw_text)


def normalize_url(url: str) -> str:
    """Strip trailing slash, query, fragment, lowercase — for visited-set membership.

    Also collapses arxiv /pdf/ and /abs/ URL variants of the same paper to one
    canonical form. The same arxiv paper can surface in either form across
    ticks (one tick returns /pdf/2606.08671, the next returns /abs/2606.08671)
    — without this dedup, the second surface looks "novel" when it isn't.

    Bug found 2026-06-19: SkillHone (arxiv 2606.08671) was first saved in
    /pdf/ form, then re-surfaced in /abs/ form 4+ hours later. The naive
    `rstrip("/").split("?")[0]` would NOT have caught this — the two URLs
    differ in the literal "/pdf/" vs "/abs/" segment.
    """
    u = url.rstrip("/").split("?")[0].split("#")[0].lower()
    # arxiv: collapse /pdf/ and /abs/ variants to /abs/ form.
    # Examples: https://arxiv.org/pdf/2606.08671v1 → https://arxiv.org/abs/2606.08671
    import re as _re
    m = _re.match(r"^(https?://arxiv\.org/)(pdf|abs)/(\d+\.\d+)(v\d+)?$", u)
    if m:
        u = f"{m.group(1)}abs/{m.group(3)}"
    return u


def get_ranked_candidates(body: dict) -> list:
    """Return the top-level ranked_candidates list. Correct key — NOT 'candidates'."""
    return body.get("ranked_candidates", [])


def get_items_by_source(body: dict) -> dict:
    """Return the items_by_source dict, e.g. {'openalex': [...], 'reddit': [...], ...}."""
    return body.get("items_by_source", {})


def get_openalex(body: dict) -> list:
    """The highest-yield sub-channel for 2026 AI/agent topics. Returns the openalex candidates."""
    return get_items_by_source(body).get("openalex", [])


def filter_unvisited(candidates: list, visited_urls: set, source_seed: str = "") -> list:
    """Return candidates whose URL is NOT in visited_urls. Adds _source_seed metadata."""
    visited_norm = {normalize_url(u) for u in visited_urls}
    seen = set()
    out = []
    for c in candidates:
        url = c.get("url", "")
        if not url:
            continue
        n = normalize_url(url)
        if n in visited_norm or n in seen:
            continue
        seen.add(n)
        c2 = dict(c)
        c2["_source_seed"] = source_seed
        out.append(c2)
    return out


def score_of(candidate: dict) -> float:
    """Robust score extraction — handles final_score, score, local_relevance, relevance."""
    return float(
        candidate.get("final_score")
        or candidate.get("score")
        or candidate.get("local_relevance")
        or candidate.get("relevance")
        or 0.0
    )


def summarize_unvisited(unvisited: list, top_n: int = 40) -> str:
    """Format the top N unvisited candidates as a readable summary for triage."""
    sorted_cands = sorted(unvisited, key=score_of, reverse=True)
    lines = []
    for c in sorted_cands[:top_n]:
        url = c.get("url", "")
        title = (c.get("title", "") or "")[:100]
        s = score_of(c)
        src = c.get("source", c.get("source_id", ""))
        lines.append(f"  {s:.3f} [{src}] {title}")
        lines.append(f"    {url}")
    return "\n".join(lines)


# ----- CLI usage -----

def _cli():
    import argparse

    ap = argparse.ArgumentParser(
        description="Unwrap a pulse_search MCP result file and dump unvisited URLs.",
    )
    ap.add_argument("file_path", help="Path to /tmp/hermes-results/call_function_*.txt")
    ap.add_argument(
        "--visited",
        default="/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json",
        help="State JSON whose visited_urls field filters out already-seen URLs.",
    )
    ap.add_argument("--seed", default="", help="Source seed string (for _source_seed metadata).")
    ap.add_argument("--top", type=int, default=40, help="Top-N to print.")
    args = ap.parse_args()

    body = parse_search_file(args.file_path)
    cands = get_ranked_candidates(body) + sum(get_items_by_source(body).values(), [])

    with open(args.visited) as f:
        state = json.load(f)
    visited = set(state.get("visited_urls", []))

    unvisited = filter_unvisited(cands, visited, source_seed=args.seed)
    print(f"Total candidates: {len(cands)}")
    print(f"Unvisited: {len(unvisited)}")
    print()
    print(summarize_unvisited(unvisited, top_n=args.top))


if __name__ == "__main__":
    _cli()