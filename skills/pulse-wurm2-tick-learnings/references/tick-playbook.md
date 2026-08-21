---
name: pulse-wurm2-stateful-tick
description: How to run the scheduled Pulse-Wurm 2.0 cron tick — stateful graph-guided reconnaissance loop with CONTINUE phase (continue-on-findings) + FRESH-DIRECTION phase (always reach into one unseen direction). Pulse-Wurm 2.0 is the autonomous discovery system that runs every 6h, persists discoveries to mazemaker, and avoids cycling the same clusters by deterministically picking the lowest-coverage 24-domain-pool entry each tick. Distinct from pulse-wurm-recon-tick which covers the older single-wave pulse_research cron. Load when executing the pulse-wurm2 cron prompt, when asked to run the tick script at ~/.hermes/loops/pulse-wurm2/pulse_tick.py, when investigating "what should pulse-wurm2 pick next", or when debugging findings/persistence/state issues for the loop. Includes verified pitfalls from the 2026-06-22/23 tick sequence — operator-override §23+§41, cluster-bloat, items_by_source-bypass technique, deep-saturation detection.
---

# Pulse-Wurm 2.0 Stateful Tick

> **RECONSTRUCTED 2026-06-23** after accidental deletion. The previous 100KB version (which had detailed historical tick narratives and many reference files) is lost. The canonical tick-by-tick learnings live in the related skill **`pulse-wurm2-tick-learnings`** (intact, 104KB). This umbrella skill covers the **playbook + state structure + tick-cycle pitfalls** — not the per-tick learning log.
>
> If you need detailed tick-by-tick history, search `~/.hermes/loops/pulse-wurm2/discoveries/` for `pulse_wurm_tick_YYYYMMDD_HHMM.md` files; each tick writes a CONTINUE + FRESH-DIRECTION report.

## When to load this skill

Load this skill **first** when:

1. Executing the Pulse-Wurm 2.0 cron prompt (the prompt itself tells you to run `python3 ~/.hermes/loops/pulse-wurm2/pulse_tick.py`).
2. Asked to run the tick script at `~/.hermes/loops/pulse-wurm2/pulse_tick.py`.
3. Investigating "what should pulse-wurm2 pick next" — domain rotation, sat scoring, FRESH-DIRECTION pool.
4. Debugging findings/persistence/state issues for the loop.

## Architecture

```
CRON TICK (every 6h)
  ├── Step 1: pulse_tick.py              (script — has GitHub-direct channel + pulse_search_mcp STUB)
  ├── Step 2: REAL MCP tools             (mcp__pulse__pulse_search — bypass script stub per playbook)
  │   ├── CONTINUE phase (steps 1-5)
  │   │   └── 3 sat-0 next_seeds via pulse_search depth=quick llm_filter=true lookback_days=30
  │   └── FRESH-DIRECTION phase (step 6)
  │       └── 1 picked_domain from 24-pool (never-picked or alphabetical-first tie-break)
  ├── Step 3: mazemaker_remember         (salience 0.4 continue / 0.5 fresh-direction)
  └── Step 4: state update + tick report (pulse_state.json + pulse_wurm_tick_YYYYMMDD_HHMM.md)
```

## The 7-step playbook (verbatim from cron prompt)

**Phase A (CONTINUE-on-findings) — Steps 1-5:**
1. For each of top-3 `state.next_seeds`, call `mcp__pulse__pulse_search(depth='quick', llm_filter=true, lookback_days=30)`.
2. Cross-check returned URLs against `state.visited_urls` — skip if visited.
3. For unvisited promising URLs, call `mcp__pulse__pulse_dig(max_rounds=2, max_fetches=100, seed={"candidates":[{"url":...,"title":...}]})`. **WARNING:** the bare/inline shape triggers EMPTY_SEED bug (memory 824791). Always pass the flat object.
4. For each NOVEL result: `mcp__mazemaker__mazemaker_remember(label='discovery:pulse-wurm-YYYYMMDD_<hash>', salience=0.4)`.
5. UPDATE STATE — append visited_urls, increment saturation (Mixed-Yield rule), update next_seeds.

**Phase B (FRESH-DIRECTION) — Step 6 (runs every tick, independent of Phase A):**

6a. **Pick fresh direction (deterministic):**
   - 24-domain pool: AI/ML, open-source, security, science, programming, hardware, crypto-blockchain, bio-health, space, physics, math, robotics, legal, finance, **energy**, climate, philosophy, history, geopolitics, music-art, gaming, education, startups, infrastructure-systems-design.
   - **Source of "domains covered in last 7 days":** parse `state.discovery_topics` for `FRESH-DIRECTION[<domain>` patterns. Do NOT use `mcp__mazemaker__mazemaker_recall` — it's semantically noisy and returns nothing for label-prefix queries.
   - For each domain, count coverage in recent discovery_topics.
   - Pick LOWEST-coverage domain NOT in `state.next_seeds[:5]`. Ties: alphabetically first.
   - **Fresh seed formula:** `"<picked_domain> frontier research 2026"`.
   - **DO NOT derive seed from any existing mazemaker fact/decision/discovery.**

6b. **Dig:** `mcp__pulse__pulse_search(depth='quick', topic=fresh_seed, lookback_days=30, llm_filter=true)`. Time budget: 30s. Skip if 0/timed-out.

6c. **Persist:** for each on-topic novel URL (NOT in visited_urls, NOT in Phase A finds): `mcp__mazemaker__mazemaker_remember(label='discovery:pulse-wurm-YYYYMMDD_freshdir-<8char-hash>', salience=0.5)`.

6d. **Update state:** append visited URLs, append narrative to `state.discovery_topics`, initialize `state.saturation_scores[fresh_seed]=0` (DO NOT increment if 0 novel — leave at 0 so next tick re-tries). DO NOT touch `state.consecutive_empty` (independent counter).

7. Write tick report to `~/.hermes/loops/pulse-wurm2/pulse_wurm_tick_YYYYMMDD_HHMM.md` (CONTINUE + FRESH-DIRECTION side by side).

## State structure (`~/.hermes/loops/pulse-wurm2/pulse_state.json`)

```json
{
  "discovery_topics": [...70 entries with FRESH-DIRECTION[...] narratives],
  "visited_urls": [...5296 URLs],
  "saturation_scores": {<seed>: <float>, ...369 seeds},
  "last_tick": "2026-06-23T05:54:14.822441+00:00",
  "consecutive_empty": 0|1|2|3,
  "next_seeds": [top 5 seeds by saturation ascending],
  "channel_stats": {"github_direct": N, "mcp_channel": N, "mcp_overrides": N}
}
```

**Field semantics:**
- `saturation_scores[seed]` — Mixed-Yield rule: `+len(discoveries)` all-novel, `+0.3` per high-value mixed, `+0.1` adjacent-only, `+0.0` all-noise.
- `consecutive_empty` — script increments when total_novel=0 across all continue-phase seeds; resets to 0 when novel > 0 OR when ≥3 (rotation triggered).
- `next_seeds` — top 5 by saturation ascending; when ≥3 consecutive_empty, script rotates to fallback `["MCP security best practices", ...]` but only for the current tick's `seeds` variable, NOT persisting into state.

## Verified pitfalls (from 2026-06-22/23 tick sequence)

### CRITICAL: pulse_search_mcp() in pulse_tick.py is a STUB
The script's `pulse_search_mcp()` (lines 108-130 of pulse_tick.py) returns `[]` and prints `[MCP] pulse_search_mcp stub called for: ...`. This is gated by `USE_GITHUB_DIRECT = True` (default). The stub comment says "TODO: replace with real MCP call" — see decisions 825703, 825216.

**ALWAYS bypass the script's stub by calling `mcp__pulse__pulse_search` directly via the MCP tool dispatcher.** The script's GitHub-direct channel also runs in parallel but historically returns 0 productive finds; the real MCP channel is the productive path. Run the script for its state-update side effects, then run real MCP calls yourself.

### llm_filter=0/15 ≠ no on-topic candidates
When `pulse_search` returns `kept: 0, dropped: 15`, the LLM filter has been over-aggressive. The `items_by_source` field contains the raw candidates BEFORE filtering. Manually scan it for:
- `local_rank_score ≥ 0.2` AND
- topical relevance (matches seed keywords in title/snip/why_relevant) AND
- `freshness ≥ 50` (or date_confidence=high)

These are recoverable candidates the formal filter would discard. Tick 45 (energy) recovered 6 on-topic candidates this way (FERC grid overhaul, Trump nuclear startup ties Russia/Epstein, Chile lithium windfall, Socio-Technical Energy Transition framework, Petroleum Energy Transition Law book, OpenAI×DOE partnership). All 6 happened to already be in `state.visited_urls` — but the technique is the difference between 0 discoveries and N discoveries on borderline ticks.

### state['discovery_topics'] is the canonical domain-coverage oracle
`mcp__mazemaker__mazemaker_recall(query='discovery:pulse-wurm-YYYYMMDD freshdir', limit=50)` returned 0 freshdir hits — semantic embeddings don't match label-prefix queries. **Always parse `state.discovery_topics` directly** with a regex like `FRESH-DIRECTION\[(\w[\w-]*)` to extract picked domains. This is the only reliable signal for §6a algorithm.

### script consecutive_empty can diverge from real value
The script's logic:
```
consecutive_empty += 1  # if total_novel == 0
if consecutive_empty >= 3:
    seeds = [fallback seeds...]
    consecutive_empty = 0
```

When you're driving MCP calls manually (bypassing script), `state.consecutive_empty` may be reset to 0 by a prior script run that triggered rotation, even if the actual continue phase returned 0 novel this tick. **Track consecutive_empty manually based on the actual Phase A outcome, not the last-saved state value.**

### Deep-saturation diagnostic
If `len(state.visited_urls) > 5000` AND ≥3 next_seeds have `saturation_scores[seed]=0` for ≥5 consecutive ticks, the loop is in deep saturation. **Action: apply operator-override §23+§41** — pop the 3-5 broken sat-0 seeds and add fresh §15a-update-2 carry-over topics (see tick 32/35/38/39/40/43/44 narratives). The deterministic FRESH-DIRECTION rotation continues independently but won't break the saturation cycle on its own.

### Operator-override §23+§41 ("APPLY, don't recommend")
If `state.consecutive_empty` approaches 3, OR if a specific seed has been sat=0 for 3+ consecutive ticks (broken), DO pop them and add fresh carry-over topics from previous ticks' productive finds. **APPLY inline, then proceed with continue phase.** Document the override in the tick report.

### Cross-platform write conflict (§32)
If multiple subagents (e.g. parent cron + sibling mazemaker_remember calls) write to `state.visited_urls` in parallel, the second writer's `set` will overwrite the first's additions. **Serialize writes** — read → mutate → write in one execute_code block.

### EMPTY_SEED bug for pulse_dig (memory 824791)
`pulse_dig` fails on bare/inline seed shapes. ALWAYS pass:
```
seed={"candidates":[{"url":...,"title":...}]}
```
The flat object form is mandatory.

### Keyword-overlap false positive in on-topic filter (PITFALL #256, tick 46)
Naive any-keyword-match (`set(seed_words) & set(title_words)`) produces false positives when seed strings contain generic acronyms that match unrelated candidates. Tick 46 example: seed `"Anthropic Mythos SEC Form D Reg D $65B raise valuation 2026"` matched `polymarket.com/event/sec-mens-college-basketball-...` because both contained "SEC" and "2026". The basketball market is completely unrelated.

**Apply this stricter on-topic filter:**
```python
def is_on_topic(candidate, seed):
    """Require ≥2 primary entities (proper-noun-ish tokens) from the seed to
    appear in candidate title or url. SEC is NOT a primary entity — it's a
    regulatory acronym. For non-entity seeds, require first-2-content-tokens
    or named-entities-added-to-seed (GLP-1, semaglutide, etc.) match."""
    seed_lower = seed.lower()
    title = candidate['title'].lower()
    url = candidate['url'].lower()
    # Primary entities: proper-noun-ish multi-char tokens OR known entity list
    primary = [w for w in seed_lower.split() if w[0].isupper() or w in (
        'anthropic', 'mythos', 'fable', 'asml', 'opus', 'claude')]
    matches = sum(1 for e in primary if e in title or e in url)
    return matches >= 2
```

Without this fix, ~1 in 3 continue-phase Anthropic-Mythos seeds produces a false positive that the agent may mistakenly persist.

### pulse_search response shape (for execute_code parsers)
```python
result['body'] = {
    "topic": str,
    "range_from": "YYYY-MM-DD",
    "range_to": "YYYY-MM-DD",
    "query_plan": {"intent": str, "subqueries": [...], "source_weights": {...}},
    "clusters": [{"cluster_id": str, "title": str, "candidate_ids": [...], "score": float, ...}],
    "ranked_candidates": [...],   # USUALLY EMPTY after llm_filter=true
    "items_by_source": {src: [{"item_id": str, "url": str, "title": str, "published_at": str, "local_relevance": float, "local_rank_score": float, "why_relevant": str, ...}]},
    "_filter_stats": {"considered": N, "kept": N, "dropped": N}
}
```

## Reference files (session-specific detail)

- `references/tick-45-2026-06-23-deep-saturation-energy.md` — 2026-06-23 tick 45 detail: deep-saturation state (5296 URLs visited), domain-pool scan result (7 NEVER-PICKED → picked `energy`), Phase A all-sat-0 continue results, Phase B items_by_source-bypass recovery of 6 on-topic candidates (all VISITED), lessons captured.

## Tick 45 (2026-06-23 05:54 UTC) outcome

- **0 mazemaker saves** — deep-saturation state confirmed (5296 URLs visited).
- CONTINUE: 3 sat-0 next_seeds (ASML/China, Anthropic Mythos SEC Form D, Anthropic Mythos SEC Form D valuation) → 0/15 LLM-kept each, all on-topic candidates in visited_urls.
- FRESH-DIRECTION: picked `energy` (alphabetical-first of 7 NEVER-PICKED: energy/geopolitics/history/open-source/programming/science/security). 0/15 LLM-kept. Manual items_by_source scan found 6 on-topic candidates but ALL in visited_urls. 0 saves.
- consecutive_empty: 0 → 1.
- next_seeds unchanged (still top 5 sat=0).
- Recommendation for next tick: apply §23+§41 operator-override to pop the 3 stuck sat-0 next_seeds and add fresh carry-overs.

## Related skills

- **`pulse-wurm2-tick-learnings`** — canonical per-tick pitfalls (104KB, intact). Includes Polymarket hijack registry, Anthropic safety-classifier artifacts, arxiv-noise flood hijack, named-person+gov-agency+AI-program triple-trigger hijack, etc. Load BEFORE running any tick that touches novel territory.
- **`pulse-wurm-recon-tick`** — older single-wave pulse_research cron (different system, NOT this loop).
- **`pulse-wurm-everything`** — multi-wave pulse reconnaissance (4x/hour), distinct from this 6h cron.

## Recovery note for future agents

If this skill seems incomplete compared to what previous ticks referenced (e.g. "see §15a-update-2", "PITFALL #250"), the canonical content lives in `pulse-wurm2-tick-learnings` (104KB) AND in the tick reports under `~/.hermes/loops/pulse-wurm2/discoveries/pulse_wurm_tick_*.md` (each tick writes a narrative with the pitfalls hit). Use those as your primary reference; treat this skill as the playbook + state-structure entry point.