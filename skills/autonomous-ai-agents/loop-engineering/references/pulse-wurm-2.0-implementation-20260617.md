# Pulse-Wurm 2.0 Implementation — 2026-06-17

## Overview

Pulse-Wurm 2.0 is a stateful pulse reconnaissance loop that actively seeks what it DOESN'T know. It uses saturation scores to prioritize low-explored topics and maintains state across ticks.

## Core Components

### State File Schema (`~/.hermes/loops/pulse-wurm2/pulse_state.json`)

```json
{
  "discovery_topics": ["list of all topics ever discovered"],
  "visited_urls": ["list of all URLs already explored (dedup)"],
  "saturation_scores": {"topic": count},
  "last_tick": "ISO timestamp",
  "consecutive_empty": 0,
  "next_seeds": ["up to 5 topics to try next"]
}
```

### Execution Flow

1. **Initialize** - Run `pulse_tick.py` to get state and seeds
2. **Search** - For each seed, call `pulse_search(depth='deep')`
3. **Filter** - Check results against `visited_urls`, skip duplicates
4. **Dig** - For unvisited URLs, call `pulse_dig(max_rounds=2, max_fetches=100)`
5. **Remember** - Write triple-memory pattern for each novel finding
6. **Update State** - Append URLs, increment saturation, reset consecutive_empty

## Triple-Memory Pattern

For each discovery, create three linked memories:

1. **Discovery Entry**
   ```
   discovery:pulse-wurm-YYYYMMDD_<hash>
   - topic, url, title, source, summary, source_seed, findings
   ```

2. **Fact Entry**
   ```
   fact:pulse-discovered-<topic>
   - Core insight linking to discovery's key finding
   ```

3. **Decision Entry**
   ```
   decision:pulse-wurm-action-YYYYMMDD_<hash>
   - Links discovery to potential actions
   ```

## Saturation Score Management

```python
# Track discoveries per topic
saturation_scores = {
    "Autonomous AI coding agents": 26,
    "ControlFlowMonitor agents": 21,
    "VLLM framework vulnerabilities": 14
}

# Next seeds = lowest saturation topics first
next_seeds = sorted(saturation_scores.items(), key=lambda x: x[1])[:5]
```

### Saturation Thresholds
- **0-5**: Fresh exploration priority
- **6-15**: Active discovery phase
- **16-30**: Consider rotating to fresh topics
- **30+**: Saturated - rotate or dig deeper into specifics

## Key Implementation Details (2026-06-17)

### Result Parsing Pattern
```python
# Pulse search returns nested JSON
outer = json.loads(response)
inner = json.loads(outer['result'])
candidates = inner['body']['ranked_candidates']

# Extract candidate details
for c in candidates:
    url = c.get('url')
    title = c.get('title')
    source = c.get('source')
    snippet = c.get('snippet')
```

### URL Deduplication
- Always check against `visited_urls` from state
- Filter out `.git` URLs
- Mark Reddit and certain sites as visited to prevent retry loops

### Fallback Chain
1. `pulse_search(depth='deep')` — primary
2. `pulse_search(depth='quick')` — faster fallback
3. `pulse_research(depth='default')` — final fallback
4. Browser tools for web content (works even when direct HTTP is blocked)
5. Direct API calls for scholarly papers
6. PDF extraction for papers

**Important:** Some sources (Reddit, certain sites) block automated access - mark as visited to prevent retry loops.

## Browser Fallback Pattern (2026-06-17)

When `pulse_dig` requires a seed_report parameter that's not available, use browser tools as fallback:

```python
# Instead of pulse_dig, use browser_navigate + browser_snapshot
browser_navigate(url=url)
snapshot = browser_snapshot(full=True)
# Extract content from snapshot
```

This was used successfully for:
- https://arstechnica.com/... (Ars Technica article on CVE-2026-48710)
- https://app.opencve.io/cve/CVE-2026-48710
- https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr
- https://github.com/Kludex/starlette/commit/764dab0

## Content Extraction from Browser Snapshots

Browser snapshots return accessibility tree data. Key patterns:

```python
# Extract from snapshot['content']['article']['paragraph']
# Look for StaticText elements containing the main content
# For code blocks, look for code elements
# For links, extract href attributes
```

## Sample Execution Results (2026-06-17 12:30-13:40)

### Tick Summary
- **Seeds processed:** 3
- **Novel discoveries:** 4 (all VLLM framework vulnerabilities)
- **Visited URLs:** 564 total
- **Consecutive empty ticks:** 0

### Key Discoveries
| Topic | URL | Finding |
|-------|-----|---------|
| VLLM framework vulnerabilities | arstechnica.com/... | CVE-2026-48710 (BadHost) in Starlette affects vLLM, LiteLLM, MCP servers |
| VLLM framework vulnerabilities | opencve.io/cve/CVE-2026-48710 | Host header validation missing, request.url.path can be bypassed |
| VLLM framework vulnerabilities | github.com/.../GHSA-86qp-5c8j-p5mr | Advisory published, affected versions <= 1.0.0, patched in 1.0.1 |
| VLLM framework vulnerabilities | github.com/.../commit/764dab0 | Fix commit adding RFC 9112/3986 Host header validation |

## Sample Execution Results (2026-06-17 19:15) - Pencil Skills Discovery

### Tick Summary
- **Seeds processed:** 3
- **Novel discoveries:** 1 (Agent Skills for Large Language Models)
- **Visited URLs:** 57 total
- **Consecutive empty ticks:** 0

### Key Discoveries
| Topic | URL | Finding |
|-------|-----|---------|
| Agent Skills for Large Language Models | github.com/xp13910818313/pencil-skills | Pencil Skills guide LLMs to use Agent Skills for effective UI design with Pencil MCP. Modular framework for extending Claude's capabilities through community-developed skills. |

### Saturation Score Progression
| Topic | Old Score | New Score |
|-------|-----------|-----------|
| Agent Skills for Large Language Models | 22 | 32 |
| VLLM inference optimization | 12 | 12 (no change) |
| RL-Jailbreaking | 21 | 21 (no change) |

## Verification Checklist

After each tick:
- [ ] State file updated with new URLs
- [ ] Saturation scores incremented
- [ ] Next seeds prioritized by lowest saturation
- [ ] Discovery memories created in mazemaker
- [ ] Consecutive empty counter reset (if findings found)

## When pulse_tick.py Returns 0 Novel — Bypass Pattern (2026-06-18)

Once `visited_urls` exceeds ~850 entries, the legacy `pulse_tick.py` script's GitHub-only search path returns 0 novel results on every seed — it is exhausted. But the MCP `pulse_search(depth='deep')` path (22-source fan-out) still surfaces 5–15% unvisited URLs from the same seeds. The tick script's job at that point is purely state housekeeping; the real discovery work must be done by the agent invoking MCP tools directly.

**Bypass sequence when the script returns 0 novel:**

1. Parse `next_seeds` from state (top 3).
2. For each seed, call `mcp__pulse__pulse_search(depth='deep', lookback_days=30, topic=<seed>)`.
3. Parse the nested JSON result (`result.body.ranked_candidates` is the field; `body` may also be a JSON string depending on transport).
4. Filter against `visited_urls` from state; the unvisited subset is the real yield.
5. For each unvisited URL, call `mcp__pulse__pulse_dig(max_rounds=2, max_fetches=100, seed_report={candidates:[{url,title}]}, topic=<refined>)`. **If the seed_report parameter is awkward to construct, you can omit it and let pulse_dig re-seed from the topic directly.**
6. **Pitfall:** Pulse dig returns 0 follow-ups for bare stub URLs (e.g. cve.org records with no embedded links). Don't waste the second dig call on those — save them as bare discoveries via `mazemaker_remember` and move on.
7. For each novel finding, call `mcp__mazemaker__mazemaker_remember(content, label='discovery:pulse-wurm-YYYYMMDD_<short-hash>')`. **Retry once on "Internal tool execution error"** — that error is transient and the same payload usually succeeds.
8. Append the visited URL to state, bump `saturation_scores[seed]` by the number of novel findings, and **reset `consecutive_empty` to 0** (not +1) since the MCP bypass path found yield even when the script path didn't.
9. Re-sort `next_seeds` by lowest `saturation_scores` and trim to top 5. Always include 1–2 fresh rotation seeds that have no entry in `saturation_scores` yet.

**Why this matters:** the script and the MCP path look like the same loop, but they have different exhaustion curves. The script hits its wall around 800 visited URLs (GitHub API dedup); the MCP path keeps finding novel signal because its 22 sources (Reddit, HN, ArXiv, OpenAlex, Lobsters, Bluesky, Polymarket, Metaculus, Manifold, Dev.to, RSS, Tickertick, etc.) have far more overlap. The fix is to treat the script as a state-hygiene daemon only, and put the discovery engine on the MCP path.

**Evidence from 2026-06-18 13:35Z tick:** `pulse_tick.py` returned 0/0/0 novel on 3 seeds. Bypass path: Claude 5 seed → 5 novel URLs from 28 candidates (CVE-2026-42530 saved to mazemaker as memory 808740); Linux kernel seed → 0 novel from 23 (all in visited); Quantum seed → truncated in transport. Net: 1 concrete CVE finding from 1 tick where the script reported nothing.

## Concrete Tick Results Log

### 2026-06-18 13:35Z — CVE-2026-42530 (nginx HTTP/3 QUIC UAF)
- **Seed:** "Anthropic Claude 5 release enterprise features 2026" (saturation 0 → 5)
- **Yield:** 5 unvisited URLs from 28 candidates (Claude 5 seed); 0 from 23 (kernel); quantum truncated
- **Saved:** CVE-2026-42530 (use-after-free in nginx HTTP/3 QUIC module, cve.org) → mazemaker memory 808740 (`discovery:pulse-wurm-20260618_cve-nginx-quic`). Pulse dig returned 0 follow-ups (bare cve.org stub). Real signal: nginx HTTP/3 is widely deployed; QUIC UAF could enable RCE/DoS.
- **Off-topic saves skipped:** 4 Reddit posts (r/accelerate, r/MachineLearning, r/microsoft_365_copilot) — off-topic for the Claude 5 enterprise seed, low concrete signal, would dilute the graph.
- **Tick observation saved:** memory 808739 (`discovery:pulse-wurm-20260618_tick-observation`) — documents the script-vs-MCP exhaustion divergence for future runs.
- **State after:** visited 858→863, consecutive_empty 2→0, next_seeds rotated to Linux kernel / Quantum / Healthcare AI / Geothermal / AISI OpenAI.