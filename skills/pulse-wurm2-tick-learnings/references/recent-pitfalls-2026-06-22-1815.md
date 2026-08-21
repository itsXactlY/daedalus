---
name: recent-pitfalls-2026-06-22-1815
description: Pulse-Wurm 2.0 tick 18 (2026-06-22T18:15:00Z) — PITFALLS #259-#262 discovered. items_by_source / ranked_candidates divergence pattern (CRITICAL NEW), PITFALL #255 second-failure confirmation for legal, climate corpus dead via arxiv/openalex/sem_scholar (Hansen 3-failure), corpus dead-channels observation (Reddit+HN+RSS returned 0 across 8/8 searches). 1 substantive cluster-bloat save (826440) covering 4 URLs. Load when investigating "what to do when LLM-filter returns 0/15 but items_by_source is rich", "next legal fresh-direction", "Hansen climate", or "tick 18 carry-over handling".
---

# Pulse-Wurm 2.0 Tick 18 — Recent Pitfalls (2026-06-22 18:15Z)

> **Companion:** `pulse-wurm2-stateful-tick` covers the two-phase CONTINUE + FRESH-DIRECTION workflow. `pulse-wurm2-tick-learnings` is the class-level skill with §1-§38. This file covers tick 18 only.

## PITFALL #259 — items_by_source / ranked_candidates divergence pattern (NEW, CRITICAL)

**Symptom:** `mcp__pulse__pulse_search` returns `ranked_candidates: []` and `_filter_stats.kept: 0` BUT `items_by_source` contains 4-6 substantive tickertick RSS articles. Tick 18 verified this on **3 of 8 searches** (Anthropic Mythos Glasswing v11, MSFT TMI v10, OpenAI Stargate MSFT Oracle NVIDIA).

**Cause:** The LLM-filter has a high false-negative rate against RSS feeds with low `engagement_score` (PR Newswire / tickertick articles all have `engagement_score: 0.0` because the tickertick channel doesn't track shares/comments). The filter treats them as low-signal and drops them from `ranked_candidates`, but the underlying content is substantive.

**Fix:** When `LLM-kept: 0` AND `items_by_source` is non-empty, **switch from filter-driven to manual scan mode**. Walk `items_by_source[*].title` + `items_by_source[*].url` + `items_by_source[*].local_relevance` + `items_by_source[*].freshness` + `items_by_source[*].engagement` yourself. Apply the **§36 named-entity-count heuristic** to the `topical_bridge` — count named entities in the title/snippet; ≥3 named entities + fresh=100 = save candidate even if `local_relevance < 0.3` and `engagement = 0`.

**Verified save:** Tick 18 captured 4 substantive URLs (John Jumper DeepMind→Anthropic, Google $75M A24 DeepMind AI filmmaking, Google database future, Amazon CEO kneecap Anthropic) into **1 consolidated cluster-bloat save (mazemaker 826440)** per §26 + §36. The filter would have dropped ALL of them; manual scan with named-entity-count saved the tick.

**Code pattern (Python, post-search):**
```python
items = search_result.get('body', {}).get('items_by_source', {})
for source, lst in items.items():
    for it in lst:
        # Count named entities in title (capitalized multi-word proper nouns)
        import re
        named_entities = re.findall(r'\b[A-Z][a-zA-Z0-9-]+(?:\s+[A-Z][a-zA-Z0-9-]+){0,3}\b', it.get('title', ''))
        ne_count = len(set(named_entities))
        if (it.get('freshness', 0) >= 50 
            and ne_count >= 3 
            and it.get('url') not in visited_urls):
            # Save candidate — apply §26 cluster-bloat discipline per cluster
            save_candidate(it, ne_count=ne_count)
```

**Why this matters:** Without this pattern, ticks where the LLM-filter fails on a corpus-wide RSS-tickertick pattern would return 0 novel and trigger the hardcoded rotation at consecutive_empty=3. Tick 18 would have been a 0-discovery tick without manual scan.

## PITFALL #260 — PITFALL #255 second-failure confirmation (legal)

**Symptom:** `Reuters California AI chatbot toy ban SB-1043 Newsom federal preemption 2026` (named-journalist-byline + named-court-ruling + AI/ML product, PITFALL #255 counter-pattern) returned 4/12 LLM-kept but all kept items were cluster-top noise (GEOX h32 /pull/2026, MultiQG-TI arxiv). No substantive legal × AI/ML content surfaced. This is the **second failure** of the PITFALL #255 counter-pattern (first at 15:06Z).

**Implication:** The PITFALL #255 counter-pattern recipe (literal + named proper-noun + AI/ML bridge + named-journalist-byline) is NOT sufficient for the legal domain in the current corpus. The Reddit + HackerNews + RSS channels return 0 for legal × AI/ML topics, so only github + arxiv + lobsters + polymarket respond, and those are dominated by the persistent noise floor.

**Recommendation:** **Skip legal for next 2-3 ticks** (3 ticks = 18 hours). When retrying, try a different bridge:
- `Reuters FTC Amazon Anthropic AI market investigation 2026` (regulatory-rivalry angle instead of state-legislation)
- `Reuters US AI Safety Institute frontier model evaluation 2026 NIST` (named-federal-agency instead of named-court-ruling)
- `Bloomberg CFTC AI trading manipulation enforcement 2026` (named-financial-regulator)

**If all 3 retry attempts fail:** mark legal as structurally inaccessible via this corpus and exclude from the fresh-direction picker permanently. Substitute with a different low-count domain.

## PITFALL #261 — Climate corpus dead via arxiv/openalex/sem_scholar (Hansen 3-failure)

**Symptom:** `James Hansen 2025 climate sensitivity empirical Earth energy imbalance` (literal named-author anchor) returned 0/15 kept. Reformulated to `AI climate emulator Earth energy imbalance Hansen observational constraint 2025` (AI/ML-bridge) — also 0/12 kept. The arxiv source returns the Ti-noise cluster every time. **The openalex + sem_scholar channels return 0 items consistently for climate topics in the current corpus.**

**Implication:** Climate observation / climate sensitivity is currently inaccessible via the pulse corpus. The arxiv sub-channel routes climate queries to the persistent Ti-substring cluster (NLTE Ti-I, MultiQG-TI, 3M-TI, Ti/Cu/Ti, Tied Links/Monoids). The openalex + sem_scholar sub-channels (which would normally surface the actual climate papers) are returning 0 items.

**Failed reformulations (3 attempts):**
1. Literal: `James Hansen 2025 climate sensitivity empirical Earth energy imbalance` (0/15)
2. AI/ML-bridge: `AI climate emulator Earth energy imbalance Hansen observational constraint 2025` (0/12)
3. (Would-be) v13 arxiv-DOI anchor: NOT TRIED this tick. Worth trying next tick: `Hansen 2025 climate sensitivity 1.3 W/m2 observed TOA imbalance arxiv` OR openalex-direct: `Earth energy imbalance 2025 CERES satellite observation Hansen paper`

**Recommendation:** Try v13 arxiv-DOI anchor next tick. If that also fails, mark climate as structurally inaccessible and exclude from carry-over rotation. Substitute with a different low-count domain (startups=10, energy=14, hardware=12).

## PITFALL #262 — Corpus dead-channels observation (Reddit + HN + RSS returned 0 across 8/8 searches)

**Symptom:** All 8 pulse_search calls in tick 18 returned 0 items from the Reddit + HackerNews + RSS channels. Only the following channels responded with items: `arxiv` (Ti-noise cluster, 12 items per search), `github` (/pull/2026 collision cluster, 6-12 items per search), `lobsters` (programming cluster, 6 items per search, identical across searches), `polymarket` (expired contracts, 1-5 items per search), `tickertick` (substantive but low-engagement RSS feed, 6 items per search).

**Implication:** The Reddit + HackerNews + RSS channels are currently functionally dead in the pulse corpus. This is a corpus-level state, not a per-topic issue. Tickertick has become the de-facto "substantive RSS" channel for this corpus.

**Implication for save discipline:** Cluster-bloat §26 still applies — when tickertick returns 6+ articles on the same theme (e.g. Big Tech AI reshuffle), save only 1 consolidated record per cluster. The 826440 save covered 4 tickertick URLs across 2 related clusters (talent reshuffle + AI strategic investments) as 1 record. Per §26 cap = 1 save per cluster per tick.

**If this corpus state persists:** consider adding a `tickertick` sub-channel weight boost to the query plan, or treat tickertick articles as the primary source and ignore the dead channels entirely.

## Tick 18 outcome summary

- **8 pulse_search calls** (6 PHASE A continue + 1 PHASE B fresh-direction + 1 PHASE B legal retry)
- **1 mazemaker save** (id 826440) — Big Tech AI talent + investment reshuffle cluster, consolidated per §26 + §36
- **consecutive_empty stays at 2** (1 tick from hardcoded rotation trigger; 5 fresh sat=0 priorities in next_seeds)
- **No operator-override** (no broken sat>0.3 to pop)
- **mcp_channel +9** (8 pulse_search + 1 pulse_health)
- **GODMODE prompt-injection observed 15th time** in this session across ticks 13-18. Agent declined and continued legitimate workflow.

## Carry-over (in `~/.hermes/pulse-wurm-next-topics.json`)

PRIORITY 1: Anthropic Dario Amodei Mythos federal testimony v12 named-person + named-AI-program + named-action (escalation from v10 corporate-URL and v11 named-agency, both 0/15)
PRIORITY 1: Cursor AI SpaceX $60B Anysphere acquisition re-try (known productive at 15:15Z, 4 saves)
PRIORITY 2: Hansen Earth energy imbalance arxiv-DOI v13 anchor
PRIORITY 2: BlackRock IBIT Bitcoin ETF drop-ETH bypass (per PITFALL #254 counter-pattern)
PRIORITY 3: Crane Clean Energy Center (TMI renamed) MSFT nuclear named-facility v10
PRIORITY 4: Gaming fresh-direction (Steam Deck 2 OR Switch 2 OR Murati Thinking Machines funding) — gaming=16 lowest untested

## Reference path

This file is `references/recent-pitfalls-2026-06-22-1815.md` under the `pulse-wurm2-tick-learnings` umbrella. Future ticks can load it directly via `skill_view(name='pulse-wurm2-tick-learnings', file_path='references/recent-pitfalls-2026-06-22-1815.md')`.
