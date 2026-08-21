# Pulse-Wurm 2.0 Tick — 2026-06-18 06:00 UTC

## Context

Cron tick ran during a 3-consecutive-empty window — the script hit its rotation threshold
and swapped to a fresh seed pool (Apple iOS, Cornell Triedman, Fortinet). The agent then
ran manual `pulse_search(depth='deep')` on all three seeds in parallel.

## Outcome Summary

| Seed | Search Result | Novel URLs | Top Quality | Notes |
|------|---------------|------------|-------------|-------|
| Apple iOS macOS security CVE 2026 | 15 ranked_candidates | 15 | 0.479 | 2 actually-relevant results |
| Cornell Triedman 13-word deep research poisoning | 20 ranked_candidates | 16 | 0.000 | All noise — topic too niche |
| Fortinet CVE-2026-35616 active zero day | TIMEOUT at 120s | 0 | n/a | `depth='deep'` exceeded sync window |

- mazemaker MCP unreachable (8+ consecutive failures) — 2 discoveries saved to fallback JSON
- State updated: visited_urls 431 → 462, consecutive_empty 0
- 31 noise URLs marked visited to prevent re-surfacing

## Discoveries

### 1. Apple iOS 26 forced update for zero-day patches

- **URL:** https://old.reddit.com/r/apple/comments/1pq4x4d/apple_is_forcing_iphones_to_update_to_ios_26_to/
- **Source:** pulse_search (Reddit, local_relevance=0.556, final_score=0.0179)
- **Label:** `discovery:pulse-wurm-20260618_7dc910d3`
- **Summary:** Apple forcing iPhones capable of running iOS 26 to update to iOS 26.2 for
  zero-day patches. Two undisclosed-at-time-of-post CVEs being shipped via forced update.
- **Quality:** medium (real news, no CVE IDs in snippet — needs corroboration from
  Apple security advisories or the original ACSCERT/CISA bulletin)
- **Status:** Pending mazemaker save (MCP down)

### 2. CVE-2026-0915: glibc fixes 30-year-old bug

- **URL:** https://old.reddit.com/r/linux/comments/1qgh9po/cve20260915_gnu_c_library_fixes_a_security_issue/
- **Source:** pulse_search (Reddit, local_relevance=0.461, final_score=0.0184)
- **Label:** `discovery:pulse-wurm-20260618_22a81f04`
- **Summary:** CVE-2026-0915 — glibc security fix for an issue present since 1996.
  Not Apple-platform-specific; surfaced via seed drift in the Apple search.
- **Quality:** low-medium (off-topic from Apple seed; real CVE worth noting)
- **Status:** Pending mazemaker save (MCP down)

## Why Most Candidates Were Noise

The `pulse_search` 22-source fan-out with `depth='deep'` returns a flat candidate list
sorted by RRF + LLM-local-relevance. For niche or highly specific topics, broad web search
cannot find the actual subject and returns whatever is lexically adjacent. Examples from
this tick:

- "Apple iOS" seed returned 9 arxiv papers about tied-boxed algebras, Ti alloys, and
  social network "ties" — the word "tied" (algebraic structure) matched on what should
  have been a security query. Lexical conflation by RRF fusion, not LLM-filter failure.
- "Cornell Triedman 13-word" returned Lobsters general IT posts (KDE 6.7, Mozilla
  leaving, Commander Keen retrospective). None of the cluster titles matched the seed.
- GitHub issue #2026 in unrelated repos (RatLoopz/sahidawa-india, dev-protocol/clubs-core)
  matched because the issue number happened to be "2026" — a date collison.

## State Changes

```json
{
  "visited_urls": {"before": 431, "after": 462, "added": 31},
  "consecutive_empty": {"before": 2, "after": 0, "rotation_triggered": true},
  "next_seeds": [
    "AF_ALG algif_aead kernel vulnerability",
    "OWASP ASI06 memory poisoning taxonomy 2026",
    "Cursor 2.0 agent mode security review",
    "DRIFT injection isolation LLM agents",
    "information-flow control AI agents"
  ],
  "saturation_increments": {
    "Apple iOS macOS security CVE 2026": "+15 (15 ranked candidates returned)",
    "Cornell Triedman 13-word deep research poisoning": "+20 (20 ranked, all off-topic)",
    "Fortinet CVE-2026-35616 active zero day": "+1 (timeout counts as 1 cycle)"
  }
}
```

## Lessons (also captured in SKILL.md pitfalls)

1. `pulse_search(depth='deep')` is too long for the 120s sync window — switch to
   `pulse_research_start` (async) for any deep work
2. mazemaker MCP fallback: write to local JSON, retry next tick
3. Quality-weighted ranking: `quality = local_relevance * 0.7 + final_score * 5`
4. Niche-topic rotation: if all candidates have `local_relevance < 0.2`, saturate and drop

## Next-Tick Actions

- Retry `mazemaker_remember` for the 2 pending discoveries when MCP recovers
- Use `pulse_research_start` (async) for the Fortinet seed (or any future deep search)
- Drop the Cornell Triedman seed from rotation — fully saturated
- Consider direct arXiv query for specific paper-title topics before routing through
  the broad fan-out
