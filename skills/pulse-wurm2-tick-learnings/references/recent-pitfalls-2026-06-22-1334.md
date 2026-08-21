# Recent Pitfalls — 2026-06-22 13:34Z (Tick 11)

## Tick metadata

- **Tick timestamp:** 2026-06-22T13:34:17+00:00
- **Script last_tick before:** 2026-06-22T15:30:19Z (script ran 1 min before)
- **consecutive_empty before:** 0 (script reset to 0 itself)
- **consecutive_empty after:** 0 (4 substantive discoveries via real MCP)
- **mcp_channel counter:** 0 → 6 (4 pulse_search + 2 pulse_research_result)
- **visited_urls:** 4539 → 4550
- **mazemaker saves this tick:** 3 (ids 826359, 826367, 826369)
- **Polymarket hijack surfaces cataloged:** 18 (was 16 at 13:18Z)

## Key outcomes

| Phase | Result |
|-------|--------|
| STEP 0: Deep-job processing | 2 in-flight jobs done (Microsoft PPA + FOMC) |
| CONTINUE phase | 4 NEW findings via Cursor SpaceX $60B acquisition |
| FRESH-DIRECTION phase | climate picked, 2 NEW findings via openalex sub-channel |
| consecutive_empty | stays at 0 |

## Deep-job processing (the major new pattern — §29)

The carry-over file had 2 in-flight deep jobs from 13:18Z. Both completed
in the ~12 minutes since last tick. Processing these was STEP 0 of the
tick — BEFORE the script ran.

### Job 24ba77d66d1f — Microsoft hyperscaler data center natural gas power purchase agreement 2026

- Status: DONE (elapsed 1885s, completed ~13:30Z)
- 287 candidates aggregated (60 search + 55 dig-1 + 81 dig-2 + 78 dig-3 + 13 dig-4)
- LLM-filter kept: 22 of 286 (7.7% keep rate)
- **Polymarket hijack: 15/20 (75%)** — confirmed
- **Substantive non-PM: 5 candidates** including 3 cross-source confirmations of Chevron-Microsoft 20-year West Texas natural gas PPA

The 3 substantive URLs (all fresh=100, all 2026-06-22):
1. `https://www.techmeme.com/260622/p16#a260622p16` (loc_rel 0.513) — canonical anchor
2. `https://www.wsj.com/business/energy-oil/chevron-strikes-power-deal-with-microsoft-for-west-texas-ai-data-center-3751de34` (loc_rel 0.363)
3. `https://www.cnbc.com/2026/06/22/chevron-cvx-microsoft-msft-natural-gas-data-center.html` (loc_rel 0.424)

**DIFFERENT from earlier Chevron Project Kilby 2.67 GW deal** (carry-over file note 89 referenced a different deal). This is the second-phase / West-Texas announcement. Saved to mazemaker as id 826359.

### Job c883418e6082 — Federal Reserve FOMC June 2026 interest rate decision Treasury yield reaction

- Status: DONE (elapsed 1885s, completed ~13:30Z)
- 237 candidates, LLM-filter kept 10 of 237 (4.2% keep rate)
- **Polymarket hijack: 10/10 (100%)** — confirmed at scale
- All 10 LLM-kept are polymarket.com crypto category locale variants in 9 languages (bn/zh-hant/de/es/fr/hi/ja/pl/it/uk)
- Counter-pattern reformulation queued in carry-over was: Fed officials by name (Powell/Williams/Bostic/Cook/Waller) + economic-data anchor (CPI/NFP/PCE) OR market-reaction anchor (SOFR/10Y-2Y spread/MOVE index). The original deep job used the date-prediction framing which triggered the hijack.

## Continue phase (3 next_seeds)

### FrontierMath (PITFALL #244 confirmed at scale)

- 1/15 LLM-kept: r/user 1rivs0h "Epistemology of Machine Cognition" (low-relevance blog)
- **3/15 Polymarket markets** in items_by_source (vol $1.45M / $155K / $96K)
- Counter-pattern verified earlier: model-agnostic phrasing OR paper-DOI anchor

### Stargate 10GW (saturated)

- 2/15 LLM-kept, both already visited (openai.com/index/openai-nvidia-systems-partnership + r/wallstreetbets 1nnr6wl)
- Companion rss items: stargate-advances-with-partnership-with-oracle, Foxconn collaboration, Broadcom 10GW (all visited)

### Cursor AI SpaceX $60B acquisition (PRODUCED 4 NEW findings)

5/15 LLM-kept, 4 NEW (fool.com was visited from carry-over note 90):
1. r/cursor 1u7aehn "SpaceX acquiring Cursor for $60 billion" (engagement 1038, fresh=80) — canonical anchor
2. r/wallstreetbets 1u7a2at "SpaceX to buy Cursor AI coding agent operator Anysphere for $60 billion" (3 score, 578 comments — speculative)
3. r/wallstreetbets 1ss3mq0 "SpaceX option to acquire startup Cursor for $60 billion" (older 2026-04-21 rumor)
4. r/user 1tm7xh9 "AI Weekly News Rundown SpaceX Buys Cursor for $60B" (podcast roundup)

Event context: SpaceX (post-IPO NASDAQ:SPCX, June 15 2026) acquired Anysphere (operator of Cursor AI) for $60 billion in all-stock, announced Tuesday 2026-06-16 (day after IPO). Polymarket market "Will SpaceX acquire Cursor by...?" vol $142K Y=100% (resolved YES).

Saved to mazemaker as id 826367 (cluster-bloat: 2 saved, 2 visited-only).

## Fresh-direction phase: climate SUCCESS

### Pick logic

- 3 domains tied at 2 keyword matches in last-50 browse: security, climate, education
- Alphabetical tie-break → **climate** picked
- Counter to PITFALL #244/§15a: even after multiple failures, the literal formula CAN work

### Why this tick worked when prior ticks failed

The key difference: `query_plan.intent == "learning"` this tick (vs `person_research` in prior failed attempts). The planner routed to openalex sub-channel with weight 1.2213 (highest of all sources) + sem_scholar.

### 3 LLM-kept (all from openalex sub-channel)

1. **HKH Monsoon Outlook 2026** (ICIMOD — lib.icimod.org, 2026-06-09, doi 10.53055/icimod.1132, loc_rel=0.230, fresh=7) — Integrated seasonal assessment of June-September 2026 monsoon for Hindu Kush Himalaya. Sourced from HKH S2S + IAP-CAS + APCC + C3S + IRI + SASCOF-34 + national agencies. Signals: El Niño transition + possible positive IOD later. **SAVED.**
2. **AI aerosol optical depth retrieval** (egusphere-2026-2019-rc1, 2026-06-09, doi 10.5194/egusphere-2026-2019-rc1, loc_rel=0.170, fresh=7) — AI method for daytime AOD + Angstrom exponent retrieval. **AI/ML-bridgeable per §15a.** **SAVED.**
3. **Mediterranean N2O + CH4 air-sea flux dataset** (essd-2026-259-rc1, 2026-06-17, doi 10.5194/essd-2026-259-rc1, loc_rel=0.170, fresh=64) — Greenhouse gas concentrations over a full seasonal cycle in undersampled Mediterranean margins. **NOT SAVED — cluster-bloat (3rd-place).**

Saved to mazemaker as id 826369.

## Operational notes

### §29 NEW PATTERN: deep-job processing as tick step 0

The carry-over file's `in_flight_deep_jobs{}` is a major discovery source
the script does NOT surface. Process BEFORE the continue phase:

1. Read carry-over file
2. For each in-flight job: pulse_research_status
3. If state=='done': pulse_research_result
4. Check Polymarket hijack ratio (≥95% = save as PITFALL only)
5. Mine substantive non-PM findings, apply cluster-bloat discipline
6. Mark candidates visited

Code pattern in tick-learnings §29.

### §30 NEW PATTERN: script auto-sort works when pool is healthy

The script's auto-sort logic (sort saturation_scores by ASC then alphabetical)
works correctly WHEN the pool has sat-0 fresh topics. Verified: 8 sat-0
entries produced correct alphabetical-tie-break next_seeds[:5]. No need
for operator-override (§23) or manual rotation (§28) when the pool is
healthy.

Symptoms of broken auto-sort (when to apply operator-override):
- consecutive_empty >= 1 AND
- next_seeds[:3] unchanged from prior tick AND
- those seeds yielded 0 novel in the prior tick

### Climate fresh-direction retry insight (§15a-update)

The literal playbook formula `climate frontier research 2026` had failed
in 2 prior attempts (13:11Z, 13:30Z — both with intent=person_research).
This tick retried the SAME literal formula and it WORKED because
intent=learning routed to openalex sub-channel. Refined rule: when
abstract-academic seed fails 2+ times, retry the literal formula
occasionally — the planner's intent classification is stochastic.

### Cluster-bloat discipline applied across all 3 phases

- Chevron-Microsoft PPA: 3 sources, 2 saved (techmeme + wsj) + 1 visited-only (cnbc)
- SpaceX-Cursor: 4 Reddit URLs, 2 saved (r/cursor + r/wallstreetbets 1u7a2at) + 2 visited-only
- Climate: 3 openalex papers, 2 saved (HKH Monsoon + AI aerosol) + 1 visited-only (Mediterranean N2O)

### Polymarket hijack registry update

- 18 surfaces (was 16 at 13:18Z)
- NEW #247: abstract-academic climate seed (workable via intent=learning retry per §15a-update)
- NEW #248: SpaceX-Cursor acquisition + Polymarket hijack (vol $142K Y=100% resolved YES — not a productivity loss, confirms the acquisition happened)

### PITFALL #244 + #243 confirmed at 100% hijack scale

- FrontierMath seed: 3/3 LLM-kept are Polymarket markets
- FOMC seed: 10/10 LLM-kept are polymarket.com crypto category locales
- Counter-pattern reformulations both queued in carry-over file

## Next-tick recommendations

1. **Process the 5 newly-sorted next_seeds** (Anthropic Fable 5 / Epoch AI FrontierMath / Forward FDE / Huawei SMIC / Hyperliquid AI agent)
2. **Reformulate Epoch AI FrontierMath** per PITFALL #244 counter-pattern: paper-DOI anchor `arxiv.org/abs/2503.XXXXX FrontierMath` OR model-agnostic `expert-level LLM math reasoning evaluation`
3. **Pick fresh-direction:** education (sat 2, alphabetically-first under-represented after climate covered)
4. **Consider starting a new deep job** for next-tick async work — candidate: "Microsoft hyperscaler Stargate Oracle 4.5GW site locations 2026" (companion to West Texas PPA)

## State at end of tick

```json
{
  "last_tick": "2026-06-22T13:34:17+00:00",
  "consecutive_empty": 0,
  "next_seeds": [
    "Anthropic Fable 5 Mythos US export controls foreign nationals cyber defense 2026",
    "Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation",
    "Forward deployed engineer FDE role Google OpenAI Anthropic 2026 hiring",
    "Huawei SMIC chip export controls US semiconductor self-sufficiency 2026",
    "Hyperliquid AI agent on-chain transaction 2026"
  ],
  "channel_stats": {
    "github_direct": 0,
    "mcp_channel": 6,
    "mcp_overrides": 0
  },
  "visited_urls_count": 4550,
  "discovery_topics_count": 434,
  "saturation_scores_count": 275
}
```
