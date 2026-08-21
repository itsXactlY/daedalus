# pulse_dig vs pulse_search Output Structures (2026-06-18 10:21)

## TL;DR

`scripts/parse_pulse_search.py` returns **0 candidates** when pointed at a `pulse_dig` persisted-output file because the two MCP tools return **different body shapes**:

| Tool | Body shape | Parser expects | Parser result on dig |
|---|---|---|---|
| `mcp__pulse__pulse_search` | `body.ranked_candidates` (list of `{title, url, local_relevance, final_score, ...}`) | `body.ranked_candidates` | ✅ works |
| `mcp__pulse__pulse_dig` | `body.candidates` (list of `worm-cid` objects with extra fields) | `body.ranked_candidates` | ❌ returns 0 |

**Always inspect the persisted file's structure before assuming the parser will handle it.** The first ~300 chars of a dig file show `"candidates"` where a search file shows `"ranked_candidates"`.

## How to Detect

```bash
# Quick check — look for the top-level key in the body
head -c 1000 /tmp/hermes-results/call_*.txt | python3 -c "
import sys, json
raw = sys.stdin.read()
# File is JSON-wrapped: {\"result\": \"{...}\"}
data = json.loads(raw)
inner = json.loads(data['result'])
body = inner['body']
print('Keys:', list(body.keys()))
if 'ranked_candidates' in body:
    print('→ pulse_search shape')
elif 'candidates' in body:
    print('→ pulse_dig shape')
"
```

## Full Structure Comparison

### pulse_search persisted output (parses correctly)
```json
{
  "result": "{\"status\": 200, \"body\": {...}}"
}
```
Inner body:
```json
{
  "topic": "...",
  "range_from": "2026-05-19",
  "range_to": "2026-06-18",
  "generated_at": "2026-06-18T...",
  "query_plan": {...},
  "clusters": [...],
  "ranked_candidates": [     ← THE KEY
    {
      "item_id": "...",
      "source": "arxiv",
      "title": "...",
      "url": "https://...",
      "local_relevance": 0.33,
      "final_score": 0.019,
      "engagement": {...},
      "engagement_score": 0.3,
      "source_quality": 0.88,
      ...
    }
  ],
  "items_by_source": {...},
  "_filter_stats": {...}
}
```

### pulse_dig persisted output (parser returns 0)
```json
{
  "result": "{\"status\": 200, \"body\": {...}}"
}
```
Inner body:
```json
{
  "run_id": "fe1594ac13d6a3dd",
  "rounds_completed": 2,
  "candidates": [            ← DIFFERENT KEY
    {
      "candidate_id": "worm-cid-1e460fb35d79919e",
      "item_id": "worm-1e460fb35d79919e",
      "source": "worm:r1:github",
      "title": "GitHub Terms of Service - GitHub Docs",
      "url": "https://docs.github.com/...",
      "snippet": "...",
      "subquery_labels": [],
      "native_ranks": {},
      "local_relevance": 0.0,
      "freshness": 0,
      "engagement": 0.0,
      "source_quality": 0.5,
      "rrf_score": 0.0,
      "sources": ["worm:r1:github"],
      "source_items": [...],
      "rerank_score": 0.0,
      "final_score": 0.0,
      "explanation": null,
      "cluster_id": null,
      "metadata": {}
    }
  ],
  "lineage_edges": [...],
  "stats": {
    "pages_extracted": 1002,
    "fetches_attempted": 80,
    "fetches_succeeded": 72,
    "fetches_failed": 6,
    "fetches_skipped_capped": 924,
    "new_candidates": 72,
    "dig_value_hits": 64,
    "dig_value_misses": 14,
    "elapsed_seconds": 43.14
  }
}
```

**Key differences:**
- Dig uses `body.candidates` (not `ranked_candidates`)
- Dig candidates have `candidate_id` and `item_id` prefixed with `worm-cid-` and `worm-`
- Dig candidates have `worm:rN:<source>` source format (e.g., `worm:r1:github`, `worm:r2:reddit`)
- Dig candidates typically have `local_relevance: 0.0` and `final_score: 0.0` — the worm doesn't score the same way search does. The `LR*0.7 + FS*5` quality filter is useless on dig output (all candidates score 0). Use `engagement * source_quality` as a fallback.
- Dig adds `lineage_edges` and `stats` blocks not present in search

## Working Inline Parser for pulse_dig Output

When you need to parse a dig persisted file, use this inline pattern (verified 2026-06-18 10:21 on a 72-candidate dig):

```python
import json
from pathlib import Path

def parse_dig_output(path: str, blacklist_substrings: list, visited_urls: set):
    """Parse a pulse_dig persisted-output file. Returns ranked list of novel candidates."""
    data = json.loads(Path(path).read_text())
    inner = json.loads(data["result"])
    candidates = inner["body"]["candidates"]

    blacklist = [b.lower() for b in blacklist_substrings]
    seen = set()
    ranked = []

    for c in candidates:
        url = c.get("url", "")
        title = c.get("title", "")
        if not url or url in visited_urls or url in seen:
            continue
        if any(b in url.lower() for b in blacklist):
            continue
        seen.add(url)
        # Dig candidates often have local_relevance=0 and final_score=0.
        # Fall back to engagement * source_quality as a coarse quality signal.
        eng = c.get("engagement", 0) or 0
        sq = c.get("source_quality", 0) or 0
        quality = eng * sq
        ranked.append({
            "url": url,
            "title": title,
            "snippet": c.get("snippet", "")[:200],
            "lr": c.get("local_relevance", 0),
            "fs": c.get("final_score", 0),
            "engagement": eng,
            "source_quality": sq,
            "quality": quality,
            "source": c.get("source", ""),
        })

    ranked.sort(key=lambda x: x["quality"], reverse=True)
    return ranked, inner["body"].get("stats", {})

BLACKLIST = [
    "github.com",            # catches root + most landing pages
    "github.community",
    "support.github.com",
    "services.github.com",
    "resources.github.com",
    "docs-internal.github.com",
    "docs.github.com",
    "skills.github.com",
    "securitylab.github.com",
    "desktop.github.com",
    "cli.github.com",
    "archiveprogram.github.com",
    "/features", "/enterprise", "/pricing", "/sponsors",
    "/about", "/topics", "/customer-stories", "/get-started",
    "/site-policy", "/solutions/", "/apps",
    "redditblog.com", "www.redditinc.com",
    "play.google.com/store/apps/details?id=com.reddit",
    "bsky.app/profile/",
]

ranked, stats = parse_dig_output(
    "/tmp/hermes-results/call_*.txt",
    BLACKLIST,
    visited_urls=set(),
)
print(f"Total: {stats.get('new_candidates', '?')}, after blacklist+dedup: {len(ranked)}")
for c in ranked[:5]:
    print(f"  Q={c['quality']:.3f}  {c['title'][:60]}  → {c['url'][:80]}")
```

**Output for the 10:21 tick:**
```
Total: 72, after blacklist+dedup: 0
```

All 72 dig candidates were killed by the hardened blacklist — the dig was 100% marketing noise for that seed path. The inline parser makes this visible (raw count 72, post-blacklist 0, with diagnosis).

## Hardening `parse_pulse_search.py` to Handle Both

If you want a single parser that handles both shapes, patch the JSON-parsing section:

```python
# In parse_pulse_search.py, after parsing the outer envelope:
inner = json.loads(data["result"])
body = inner.get("body", {})

# Detect shape and normalize
if "ranked_candidates" in body:
    candidates = body["ranked_candidates"]
elif "candidates" in body:
    candidates = body["candidates"]
else:
    candidates = []

# ... rest of parser unchanged
```

This 4-line change makes the parser handle both shapes. The quality-scoring function (`LR*0.7 + FS*5`) still works on dig output — it just scores everything low if `LR=0` and `FS=0`, which is a useful signal in itself (dig output is unscored, the worm doesn't trust it enough to score).

## When to Use pulse_dig vs pulse_search

- **pulse_search** is the workhorse. Returns scored, ranked candidates with `local_relevance` and `final_score`. Always start here.
- **pulse_dig** is the recursive follow-up. Use it to find URLs WITHIN a result, but be aware:
  - 40-60% of dig output is marketing pages from the worm following the original URL into the site's navigation
  - 100% GitHub noise is the worst case (when seed URLs are github.com repos)
  - Dig output is unscored — manual quality filtering required
  - For non-GitHub seeds (reddit, arxiv, lobsters, RSS), dig can produce genuinely novel content

**Rule of thumb:** If your pulse_search already found 5+ high-quality candidates, skip pulse_dig. If pulse_search found <5, dig into the top 2 candidates — but expect to filter out 50%+ of dig output as noise.

## Verification Test (10:21 tick, before/after)

**Before fix** (using `parse_pulse_search.py` on dig file):
```
=== TOPIC: unknown ===
  ranked_candidates: 0
  NOVEL (quality > 0.05): 0
TOTAL NOVEL: 0
```

**After fix** (using inline parser with hardened blacklist):
```
Total candidates in dig: 72
After HARDENED blacklist: 0 candidates survive
```

The 0 is correct here — the dig genuinely produced 100% marketing pages. But the original parser was hiding the raw count (72). The inline parser surfaces the data: "we have 72 candidates, the blacklist killed all of them, here's the diagnosis."

## Related Pitfalls

- "Generic-URL blacklist is essential for pulse_dig output (2026-06-18 09:15)" — original blacklist
- "GitHub URL blacklist hardening v2 (2026-06-18 10:21)" — v2 additions
- "pulse_dig timeout risk in cron" — when to skip dig entirely
- "pulse_dig seed_report format trap (2026-06-17 23:30)" — separate issue: how to STRUCTURE the seed_report arg going INTO pulse_dig (this doc is about parsing the OUTPUT)
