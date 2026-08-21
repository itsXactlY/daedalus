#!/usr/bin/env python3
"""
score_connectedness.py — DECIDE phase candidate scoring helper.

Parses /tmp/hermes-results/call_<hash>.txt file-dumps from mazemaker_recall
and produces per-candidate:
  - fact+decision count in top-10 (connectedness numerator)
  - total top-N results
  - max similarity to non-self memory
  - implied novelty score (1 - max_similarity)
  - top hits with id, label, similarity, kind classification

Usage:
  python3 score_connectedness.py <file.txt> [<file2.txt> ...]

Output: human-readable text summary for each file, with one section per
candidate, sorted by file order. Designed to be invoked from execute_code
when the recall result is >150KB and auto-dumps to disk.

Companion to references/decide-tool-mechanics.md "Companion cross-check:
topic-recall for novelty estimation" section. The 24-/30-decision-per-2h
saturated cycles require this per-candidate scoring to triage which
discoveries are genuinely novel vs covered by an already-written decision.

Last validated: 2026-06-22 16:30Z DECIDE cycle (30 prior decisions in
2h window, 826353 Huawei + 826406 r/singularity-641 + 826384 ecohealth
all scored as top candidates via this pattern).
"""

import json
import sys


def classify_label(label):
    """Classify a memory label into a graph-anchor category.

    `auto:turn:*` and other session-auto-save labels are EXCLUDED from
    the top-10 count entirely (filtered out before the connectedness
    denominator is computed). They are not noise, not graph-anchors —
    they are chat-session scratchpads that leaked into recall results
    and dilute the connectedness signal.
    """
    if not label:
        return "NOISE"
    if label.startswith("fact:") or label.startswith("decision:"):
        return "FACT/DEC"
    if label.startswith("discovery:"):
        return "discovery"
    # Broadened graph-anchor prefix set (2026-06-22 22:46 + 23:35 cycle):
    # security:, pitfall: act as graph anchors for security/operations
    # and diagnostic findings (cluster-bloat, PITFALL extensions).
    # Without these the script undercounts connectedness on
    # security/operations topics by 0.1-0.2.
    if label.startswith(("signal:", "bug:", "invariant:", "ops:",
                          "user:", "security:", "pitfall:")):
        return "other-typed"
    # Session auto-saves (chat scratchpads leaked into recall) — filter out
    if label.startswith("auto:turn:"):
        return "AUTO-TURN"
    return "NOISE"


def score_file(path):
    """Parse a recall file-dump and return scoring summary.

    Filters out `auto:turn:*` session-auto-save items from the top-10
    BEFORE computing connectedness (they are chat scratchpads, not
    graph anchors). The filtered count becomes the denominator so
    high-auto:turn: results don't artificially deflate connectedness.
    """
    with open(path) as f:
        raw = f.read()
    # File has double-JSON wrapper: {"result": "..."} where "..." is itself JSON
    outer = json.loads(raw)
    inner = json.loads(outer["result"])
    # Recall shape is top-level list; browse shape is {"memories": [...], "count": N}
    if isinstance(inner, list):
        items = inner
    else:
        items = inner.get("memories", [])
    # Top-10 with auto:turn:* items filtered out (2026-06-22 23:35 cycle).
    # The denominator is the filtered count, not 10, so that
    # high-auto:turn: results don't artificially deflate connectedness.
    top10_filtered = [it for it in items[:10]
                      if classify_label(it.get("label", "")) != "AUTO-TURN"]
    n_filtered = len(top10_filtered)
    fact_dec = sum(1 for it in top10_filtered
                   if classify_label(it.get("label", "")) == "FACT/DEC")
    discovery = sum(1 for it in top10_filtered
                    if classify_label(it.get("label", "")) == "discovery")
    other = sum(1 for it in top10_filtered
                if classify_label(it.get("label", "")) == "other-typed")
    noise = sum(1 for it in top10_filtered
                if classify_label(it.get("label", "")) == "NOISE")
    denom = n_filtered if n_filtered > 0 else 10
    sims = [it.get("similarity", 0.0) for it in top10_filtered]
    max_sim = max(sims) if sims else 0.0
    return {
        "path": path,
        "total_returned": len(items),
        "top10_filtered": n_filtered,
        "auto_turn_filtered": sum(
            1 for it in items[:10]
            if classify_label(it.get("label", "")) == "AUTO-TURN"
        ),
        "fact_dec_in_top10": fact_dec,
        "discovery_in_top10": discovery,
        "other_typed_in_top10": other,
        "noise_in_top10": noise,
        "connectedness": fact_dec / denom if items else 0.0,
        "max_similarity": max_sim,
        "implied_novelty": 1.0 - max_sim,
        "top10": [
            {
                "id": it.get("id"),
                "label": it.get("label", "")[:80],
                "similarity": it.get("similarity", 0.0),
                "kind": classify_label(it.get("label", "")),
            }
            for it in items[:10]
        ],
    }


def format_report(scores):
    lines = []
    for s in scores:
        lines.append(f"\n=== {s['path']} ===")
        lines.append(f"  total_returned={s['total_returned']}  top10_summary: "
                     f"fact+dec={s['fact_dec_in_top10']}/10  "
                     f"discovery={s['discovery_in_top10']}/10  "
                     f"other={s['other_typed_in_top10']}/10  "
                     f"noise={s['noise_in_top10']}/10")
        lines.append(f"  connectedness={s['connectedness']:.3f}  "
                     f"max_similarity={s['max_similarity']:.3f}  "
                     f"implied_novelty={s['implied_novelty']:.3f}")
        lines.append("  ---")
        for i, hit in enumerate(s["top10"]):
            lines.append(f"  [{i+1}] sim={hit['similarity']:.3f}  "
                         f"kind={hit['kind']:10s}  "
                         f"id={hit['id']}  {hit['label']}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <recall-dump.txt> [<dump2.txt> ...]",
              file=sys.stderr)
        sys.exit(1)
    scores = [score_file(p) for p in sys.argv[1:]]
    print(format_report(scores))


if __name__ == "__main__":
    main()
