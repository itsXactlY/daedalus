# Recent Pitfalls — 2026-06-22 14:01Z (Tick 14:01)

## Tick metadata

- **Tick timestamp:** 2026-06-22T14:01:36+00:00
- **Script last_tick before:** 2026-06-22T16:00:19.888100 (clock-skewed 1h59m FORWARD vs real UTC; script uses `datetime.now().isoformat()` without timezone — see §25 + this note)
- **consecutive_empty before:** 2 (post-script)
- **consecutive_empty after:** 3 (rotation trigger fired)
- **mcp_channel counter:** 0 → 4 (3 continue + 1 fresh-direction)
- **visited_urls:** 4580 → 4616 (+36)
- **mazemaker saves this tick:** 3 (ids 826383, 826384, 826385 — all fresh-direction climate)
- **Manual rotation applied per §28:** 5 broken seeds popped, 7 fresh sat-0 added

## Key outcomes

| Phase | Result |
|-------|--------|
| STEP 0: Deep-job processing | SKIPPED — in_flight_deep_jobs is empty (all 5 from 13:55Z tick completed previously) |
| CONTINUE phase | 3 sat-0 next_seeds processed, 0 novel — consecutive_empty 2→3 |
| FRESH-DIRECTION phase | climate picked (3-way tie, alphabetically-first), 3 NEW findings via openalex+sem_scholar sub-channels |
| Manual rotation (§28) | 5 broken popped, 7 fresh added, next_seeds top 5 rotated to Fable 5 follow-ons + 2 independent |

## Continue phase (3 next_seeds — all sat-0 fresh, all yielded 0 novel)

### Seed 1: Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation

- **1/15 LLM-kept** (vs. 3/15 at 13:34Z tick when #244 was at 100% hijack scale)
- Kept candidate: `old.reddit.com/user/enoumen/comments/1rivs0h/the_epistemology_of_machine_cognition_an/` (loc=0.015, fresh=0) — off-topic (HLE not FrontierMath) personal blog post
- 8 clusters surfaced — top "Autonomous Architecture Inference Discovery" (cluster-a8e3eca3, score=0.192) and "Generation Question Multi Modal" (arxiv, 0.098) — both noise patterns
- **No Polymarket hijack this tick** (3/15 PM markets at 13:34Z → 0/15 PM markets at 14:01Z)
- **PITFALL #244 LOW-SCALE MODE confirmed** — see new pitfall section below

### Seed 2: Samsung Electronics ChatGPT Enterprise Codex deployment worldwide 2026

- **1/15 LLM-kept**: `openai.com/index/samsung-electronics-chatgpt-codex-deployment` (rss, loc=0.467, fresh=96, published 2026-06-21) — **VISITED**
- 5 rss items in items_by_source: openai.com partner-network canonical (visited) + Endava/Simplex/CyberAgent/B2B Signals companions (stale 2026-04 to 2026-05, fresh=0). Cluster bloat — same OpenAI enterprise-deployment cluster
- 14 ranked dropped: arxiv Ti-noise (6), tickertick Apple/Samsung/AMZN/MSFT financial noise (5), polymarket ChatGPT Outage June 2026 ($11K vol), github /pull/2026 collisions (5), lobsters Nature AI ruining skills + wigglegram + LLM poisoning artwork + postmarketOS v26.06 + Chesterton + Deno Desktop (all visited cluster)
- **Cluster fully saturated at canonical-URL level. No novel findings.**

### Seed 3: OpenAI Partner Network $150M Fortune 500 enterprise deployment 2026

- **1/15 LLM-kept**: `openai.com/index/introducing-openai-partner-network` (rss, loc=0.421, fresh=73, published 2026-06-14) — **VISITED**
- items_by_source RSS: Partner Network canonical (visited), SAP for Germany global-affairs (visited, 2025-09-24), Pacific Northwest National Lab (NEW URL but fresh=0 / 2026-02-26), Snowflake partnership (NEW URL but fresh=0 / 2026-02-02), Instacart partnership (NEW URL but fresh=0 / 2025-12-08). New URLs are outside 30-day lookback window
- 24 arxiv items (Ti-substring noise, all visited), 24 lobsters items (recurring noise cluster), 24 github items (/pull/2026 collisions + 247wallst etc.), 2 polymarket (OpenAI social network, Apple-Siri partnership — both stale)
- **Cluster fully saturated at canonical-URL level. No novel findings within 30-day window.**

## Fresh-direction phase: climate SUCCESS (2nd consecutive)

### Pick logic

- 3 domains tied at 3 keyword matches in last-50 browse: climate / crypto-blockchain / music-art
- Alphabetical tie-break → **climate** picked (alphabetically-first under-represented, NOT in next_seeds top 5)
- This is the 2nd consecutive successful climate fresh-direction in 3 ticks (13:11 fail, 13:30 fail, 13:34 success, 14:01 success)

### Why this tick worked

Same as 13:34Z: `query_plan.intent == "learning"` routing to openalex sub-channel with weight 1.2144 (highest of all sources) + sem_scholar 1.17. The stochastic intent classification is the load-bearing factor.

### 5/15 LLM-kept candidates (highest yield for climate fresh-direction in 6 ticks)

| Rank | Source | Score | Fresh | URL | Title | Action |
|---|---|---|---|---|---|---|
| 1 | openalex | 0.214 | 14 | egusphere-2026-1024 | NUKLEUS – A First Kilometre Scale Multi-model Climate Ensemble for Germany: Evaluation | VISITED (already in visited_urls) |
| 2 | openalex | 0.230 | 7 | lib.icimod.org/.../ICIMOD_Monsoon_Outlook_2026.pdf | HKH Monsoon Outlook 2026 | **SAVED** (id 826383) |
| 3 | sem_scholar | 0.208 | 0 | semanticscholar.org/paper/042dfbfbee5dfaacaf62e27a69189abc70b9d2e2 | Northeast India as the Next Frontier of EcoHealth and One Health Research | **SAVED** (id 826384) |
| 4 | reddit | 0.164 | 0 | old.reddit.com/r/collapse/comments/1q3q26t/ | Last Week in Collapse: December 28, 2025 — January 3, 2026 | cluster-bloat (off-topic) — VISITED |
| 5 | openalex | 0.200 | 71 | egusphere-2026-2379 | Comment on egusphere-2026-2379 (HHA-Net groundwater) | VISITED |

**Adjacent candidates (sem_scholar + openalex, marked visited only):**
- Mediterranean N2O+CH4 air-sea flux dataset (essd-2026-259) — VISITED
- Sustainable Vehicle Routing Problems bibliometric audit (mdpi logistics10060136) — VISITED
- Comment on egusphere-2026-2019 AI Aerosol AOD retrieval — **SAVED** (id 826385, AI/ML-bridge)
- Mozambique coal frontier decarbonisation labour — visited
- Transparent West-Pacific Earth System Science — visited
- Antarctic epistemic opacity — visited
- Egypt ESG climate factors — visited
- AI-Driven IoT Climate Decision Making (sem_scholar 5cdc5a1b) — visited (lower relevance than AI Aerosol AOD)

### 3-angle climate yield from a single seed

This tick's 3 saved discoveries span **3 distinct sub-domains from a single climate seed**:

1. **Climate observation** (HKH Monsoon Outlook 2026 — concrete regional seasonal forecast)
2. **Climate + bio-health bridge** (Northeast India EcoHealth/OneHealth — bridges climate with pandemic-preparedness/biodiversity)
3. **Climate + AI/ML bridge** (AI Aerosol Optical Depth Retrieval — bridges climate observation with AI/ML methodology)

**Insight:** when the openalex sub-channel activates via intent=learning routing, a single climate seed can yield multi-domain bridges. The "fresh direction" picks are not just narrow-domain discoveries — they're often trans-disciplinary. The 3-angle yield is a multiplier effect that justifies the fresh-direction phase budget (30s) even when the continue-phase yields 0.

## PITFALL #244 LOW-SCALE MODE (new sub-mode documented)

**PITFALL #244** was previously documented as: "FrontierMath Benchmark + Gemini 3 score + date-prediction → 100% Polymarket hijack (3 markets, vol $1.45M / $155K / $95K)"

This tick surfaced a **distinct sub-mode** of the same pitfall:

**PITFALL #244 LOW-SCALE MODE:** Abstract-academic seed with `benchmark` substring + no specific model + no specific date — the planner routes to `person_research` intent with openalex sub-channel fully SUPPRESSED. LLM-filter keeps 1/15 candidate maximum, and that 1 candidate is a low-relevance off-topic user post (not a real benchmark result).

**Comparison table:**

| Sub-mode | Polymarket hijack | LLM-kept | Topic relevance | Counter-pattern |
|---|---|---|---|---|
| **HIGH-SCALE** (cataloged at 13:34Z) | YES (3/15 markets, vol $1.45M) | 1/15 of REAL relevance = 3 PM | off-topic via hijack | paper-DOI anchor OR model-agnostic phrasing |
| **LOW-SCALE** (this tick) | NO (0/15 PM markets) | 1/15 (off-topic user post) | off-topic via sub-channel suppression | corporate-anchor (specific company + product) OR fresh concrete reformulation |

**Refined rule:** the FrontierMath seed phrase `Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation` triggers PITFALL #244 in BOTH sub-modes. The high-scale mode is more dangerous (3 hijacked markets) but the low-scale mode is more common (intent=person_research on abstract-academic seed). **Do not retry this seed phrase.** The counter-patterns:
- Use full corporate URL (e.g. `epoch.ai/frontiermath` direct URL)
- Use paper DOI (e.g. `arxiv.org/abs/<FrontierMath paper ID>`)
- Use specific model + paper (e.g. `Claude 3.5 FrontierMath score breakdown`)
- Use sub-category anchor (e.g. `FrontierMath category math 2026`)

## High-yield seed pattern §27 CLARIFICATION

The umbrella SKILL.md §27 documents "high-yield seed patterns" — concrete corporate-anchor templates (acquisition: `<acquirer> <target> <price>`, deployment: `<vendor> <product> <enterprise-scale>`, etc.) that reliably surface the canonical URL.

**Clarification from this tick:** the high-yield pattern reliably surfaces the **canonical URL** (1/15 LLM-kept with loc=0.4+ and fresh within 30-day window) but **yields 0 novel findings when the cluster is already saturated**. The canonical URL is then in `visited_urls` from prior coverage, and the sub-partner URLs are stale (outside 30-day window) and don't trigger fresh saves.

**Refined rule:** the high-yield pattern is reliable for:
1. **Coverage verification** — confirms the cluster is comprehensively covered (if canonical is visited, cluster is done)
2. **Initial discovery** — first time the topic is searched, the canonical surfaces reliably

The pattern is **NOT reliable for re-mining** once the cluster is saturated. Don't expect novel findings from a 2nd-time high-yield seed run on the same topic — expect canonical-URL confirmation only.

**Implication for the next-tick plan:** the Anthropic Fable 5 follow-on seeds (Project Glasswing, $965B IPO, macOS protection bypass) are concrete corporate-anchor templates (high-yield pattern). First-time searches should reliably surface canonical URLs with loc=0.4+ and fresh within 30-day. But the 826376 deep-job save from 13:55Z already covered these. The next tick's continue-phase may yield 0 novel on Fable 5 follow-ons if the 826376 deep-job has already touched them.

## Clock-skew detection (this tick's anomaly)

The script's `last_tick` was `2026-06-22T16:00:19.888100` when the agent loaded state. This is **1h59m in the FUTURE** relative to the real UTC (14:01:36). Possible causes:
- Script uses `datetime.now().isoformat()` without timezone (per tick-learnings §25) — the script's "now" may be local time interpreted as UTC
- System clock skew — the host system may have a non-UTC clock that drift-corrected
- Sandbox clock vs. real wall-clock difference

**Detection signal:** when `state['last_tick']` is in the future vs. `datetime.now(timezone.utc)`, the script-side timestamp is clock-skewed. The agent should:
1. Capture TICK_TS_ISO = `datetime.now(timezone.utc).isoformat()` at the START of the tick (single-datetime discipline §21/§25)
2. Overwrite `state['last_tick'] = TICK_TS_ISO` after all state mutations
3. Verify with `assert state['last_tick'] == TICK_TS_ISO` (caught drift in this tick)
4. Use TICK_TS_ISO for the report filename and narrative timestamps

**Side effect on `discovery_topics` narrative:** the script-side `last_tick` is a separate marker from the narrative `tick_timestamp`. The narrative should use the agent's TICK_TS_ISO (the real time when the work was done), not the script-side `last_tick` (which may be clock-skewed).

## Manual rotation applied (per §28)

**Popped 5 broken seeds:**
1. `Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation` (sat 0) — PITFALL #244 confirmed at low-scale this tick
2. `Samsung Electronics ChatGPT Enterprise Codex deployment worldwide 2026` (sat 0) — cluster exhausted
3. `OpenAI Partner Network $150M Fortune 500 enterprise deployment 2026` (sat 0) — cluster exhausted
4. `Anthropic Fable 5 Mythos US export controls foreign nationals cyber defense 2026` (sat 0) — deep job `cc46d44f58d0` fully covered (826376)
5. `Forward deployed engineer FDE role Google OpenAI Anthropic 2026 hiring` (sat 0) — deep job `de3f5938f188` covered (PITFALL #249 + 826378)

**Added 7 fresh sat=0 topics:**
1. `Anthropic Project Glasswing cyberdefender Mythos 5 deployment government collaboration 2026` (carry-over PRIORITY 0)
2. `Anthropic $965B IPO 2026 timing valuation` (carry-over PRIORITY 0)
3. `Howard Lutnick Commerce Department AI export controls directive 2026` (carry-over PRIORITY 1)
4. `Anthropic macOS protection bypass CVE jailbreak demonstration 2026` (carry-over PRIORITY 2)
5. `TanStack npm security follow-on 2026` (carry-over PRIORITY 4)
6. `Qwen3-Coder-480B-A35B-Instruct blog.qwenlm.github.io 2026 production deployment` (carry-over PRIORITY 5)
7. `TypeScript 6.0 release 2026 compiler optimization performance` (programming reformulation per §15a)

**Recomputed next_seeds (lowest sat first, alphabetical tie-break):**
1. `Anthropic $965B IPO 2026 timing valuation` (sat 0)
2. `Anthropic Project Glasswing cyberdefender Mythos 5 deployment government collaboration 2026` (sat 0)
3. `Anthropic macOS protection bypass CVE jailbreak demonstration 2026` (sat 0)
4. `Cloudflare Workers AI inference gateway production 2026` (sat 0, pre-existing)
5. `Howard Lutnick Commerce Department AI export controls directive 2026` (sat 0)

**§28 manual rotation pattern worked end-to-end** — no edge cases encountered. The pattern is reliable for handling consecutive_empty=3 with healthy next_seeds-pool after the override.

## State at end of tick

```json
{
  "last_tick": "2026-06-22T14:01:36.210517+00:00",
  "consecutive_empty": 3,
  "next_seeds": [
    "Anthropic $965B IPO 2026 timing valuation",
    "Anthropic Project Glasswing cyberdefender Mythos 5 deployment government collaboration 2026",
    "Anthropic macOS protection bypass CVE jailbreak demonstration 2026",
    "Cloudflare Workers AI inference gateway production 2026",
    "Howard Lutnick Commerce Department AI export controls directive 2026"
  ],
  "channel_stats": {
    "github_direct": 0,
    "mcp_channel": 4,
    "mcp_overrides": 0
  },
  "visited_urls_count": 4616,
  "saturation_scores_count": 280
}
```

## Next-tick recommendations

1. **Process the 5 newly-sorted next_seeds** (all Fable 5 follow-ons + Cloudflare Workers AI + Howard Lutnick Commerce)
2. **PITFALL #244 LOW-SCALE MODE added to pitfall catalog** — do not retry `Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation` seed shape
3. **Fresh-direction next-tick picker:** crypto-blockchain (next-lowest count=3 after climate ticked). Concrete reformulation: "Hyperliquid AI agent on-chain transaction 2026" (already in sat=0 pool) OR "stablecoin de-dollarization BRICS settlement 2026"
4. **Consider starting a new deep job** for next-tick async work — candidate: "Anthropic Project Glasswing Mythos 5 government deployment 2026" (companion to Fable 5 export controls)
5. **consecutive_empty=3 going in** — if continue-phase yields 0, → 4 (no further rotation needed; next_seeds already rotated)
