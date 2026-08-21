# Recent Pitfalls — 2026-06-22 13:18Z (Tick 10)

## Tick summary

- **TICK_TS**: 2026-06-22T13:18:49.794169+00:00
- **OUTCOME**: PARTIAL SUCCESS (4 mazemaker saves, 3 deep jobs status-checked, 2 still running)
- **consecutive_empty**: 2 → 3 (continue phase yielded 0 for both seed topics — rotation triggered)
- **operator-override APPLIED inline** per §23 (3 broken sat-0.3 seeds popped + Tesla Megapod orbital variant)
- **manual rotation APPLIED** per §28 (script rotation code dead — 7 fresh topics added at sat=0)
- **mazemaker saves**: 4 (IDs 826353-826356) — 3 discovery + 1 pitfall

## New PITFALLS documented this tick

### PITFALL #244 (NEW): FrontierMath + Gemini 3 + date-prediction → Polymarket hijack

**Trigger phrase:** `'FrontierMath Benchmark' + 'Gemini 3 score' + date-prediction ('by June 30' / 'by January 31' / 'by November 30')`

**Observed:** `pulse_search('Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation', depth='quick', llm_filter=true)` returned 0/15 LLM-kept. items_by_source['polymarket'] surfaced 3 markets:
1. 'Gemini 3 score on FrontierMath Benchmark by January 31?' — vol $1,446,946, markets=4
2. 'AI model scores ≥ 90% on FrontierMath Benchmark in 2025?' — vol $155,345, markets=1
3. 'Google Gemini score on FrontierMath Benchmark by June 30?' — vol $95,881, markets=4

**Companion to:** PITFALL #241 (HLE + Claude + date-prediction) and PITFALL #236 (benchmark + model + 2026).

**Counter-pattern:**
- AVOID 'FrontierMath' + 'Gemini' + 'score' + date OR 'score ≥ X%' + 'by [date]'
- USE 'Epoch AI FrontierMath paper benchmark' (no model name, no date)
- OR 'AI math reasoning benchmark expert questions 2026' (no specific benchmark name)
- OR arxiv.org/abs/2412.XXXXX DOI

**Saved as:** mazemaker id 826356 `pitfall:polymarket-244-frontiermath-benchmark`

### PITFALL #245 (NEW): arxiv DOI + benchmark name = 100% Ti-substring noise in pulse_research

This is NOT a Polymarket hijack — it's a pure noise pattern where the LLM intent
classifier + LLM-filter drop the actual benchmark paper and keep arxiv Ti-substrate
false-positives.

**Trigger:** `'arxiv 2501.14249 HLE paper benchmark questions expert-level'`

**Observed:** `pulse_research(depth='deep', max_wurm_rounds=4, max_fetches_per_round=500)`:
- 4 dig rounds: 60 search → 94 dig-1 → 92 dig-2 → 78 dig-3 → 83 dig-4 = 407 candidates
- LLM-filter: kept 4, dropped 400
- All 4 kept are arxiv Ti-substring false-positives (NOT HLE):
  1. MultiQG-TI: Towards Question Generation from Multi-modal Sources (arxiv 2307.04643v1, 2023)
  2. Tied Monoids (arxiv 2001.00625v2, 2020)
  3. Multi-Phase Dataset for Ti and Ti-6Al-4V (arxiv 2501.06116v1, 2025)
  4. Modeling the effects of varying Ti concentration on the mechanical properties of Cu-Ti alloys (arxiv 2310.05415v1, 2023)

**Root cause:** the arxiv DOI anchor is too narrow for pulse_research's LLM
intent classifier. It routes to "person_research" intent (sources: github/reddit/arxiv)
and the LLM-filter keeps the highest-engagement arxiv candidates — which happen
to share the "T" or "Ti" token with the DOI string. The Ti-substring pattern
collides with: MultiQG-TI / 3M-TI / NLTE Ti~I / Ti-6Al-4V / Cu-Ti / Tied
Monoids / Tied Links / Ti nonlinear laser lithography.

**Counter-pattern for future HLE research:**
- DO NOT use pulse_research with bare arxiv DOI (e.g. 'arxiv 2501.14249 HLE paper')
- USE one of:
  - full corporate blog URL: 'blog.google / openai.com/index/ / anthropic.com/index/'
  - specific HLE question URLs (not paper DOI)
  - model-agnostic phrasing: 'expert-level LLM evaluation benchmark questions 2026'
  - paper title + venue anchor: 'arxiv 2501.14249 Humanity Last Exam paper questions'

**Verification:** after pulse_research completes, check items_by_source — if
the LLM-kept candidates are all arxiv papers that don't reference the actual
benchmark/evaluation target, the DOI anchor is too narrow.

### PITFALL #246 (NEW): abstract-academic seed + 'lithography'/'FrontierMath'/'benchmark' substring → Ti-substring noise

Same Ti-substring pattern as #245 but triggered by abstract-academic phrasing
in the seed itself (not just the DOI). The 'lithography' substring collides
with 'Ti' / 'NLTE' / 'Cu-Ti' papers; 'FrontierMath'/'benchmark' collides
with 'Tied Monoids' / 'Tied Links' (topology math papers).

**Counter-pattern:** avoid 'Ti' or 'lithography' or 'FrontierMath' substrings
in the seed. Use concrete company + product anchor (e.g. 'NVIDIA Blackwell
EU lithography process node 2026' instead of 'lithography frontier research 2026').

## Substantive findings this tick

### Finding A (PRIMARY): Huawei chairman thanks US for chip export controls
- URL: https://old.reddit.com/r/China/comments/1tvrep7/huawei_chairman_thanks_the_us_for_export/
- Source: r/China 0e5dbac5e4d9, 2026-06-03, engagement 459/96, loc_rel=0.452, fresh=36
- Substantive quote: Huawei's chairman thanked (sarcastically) the US for chip export restrictions, stating they directly forced China to build its own semiconductor industry
- Bridges AI hardware (Huawei SMIC, ASML EUV, NVIDIA China ban) + geopolitics (US-China trade war)
- Saved: mazemaker id 826353 `discovery:pulse-wurm-20260622_freshdir-huawei-chip-export-thanks`

### Finding B: Fable 5 Export Controls Harm US Cyber Defense (companion pair)
- URL: https://simonwillison.net/2026/Jun/16/fable-5-export-controls/
- Source: simonwillison.net ee93c72f394d, 2026-06-16, loc_rel=0.194, fresh=80
- Companion: https://lucumr.pocoo.org/2026/6/13/americans-only/ (Armin Ronacher, fresh=70)
- Substantive: Kate Moussouris via The Atlantic on how Anthropic's "export controls for dangerous AI" framing backfired when US government applied export controls to Fable and Mythos for foreign nationals
- Bridges AI security (Fable 5 / CVE review) + geopolitics (export controls)
- Saved: mazemaker id 826354 `discovery:pulse-wurm-20260622_freshdir-fable5-export-controls`

### Finding C: OpenAI First Proof submissions (FrontierMath-adjacent)
- URL: https://openai.com/index/first-proof-submissions
- Source: openai.com rss 705465eacd7c, 2026-02-20, loc_rel=0.120, fresh=0
- Substantive: OpenAI's proof attempts for the First Proof math challenge (Epoch AI's FrontierMath-adjacent research-grade math reasoning benchmark)
- Saved: mazemaker id 826355 `discovery:pulse-wurm-20260622_openai-first-proof-submissions`

## Operational patterns verified this tick

### Picker Counter() bug (NEW pitfall — see SKILL.md §27)
The fresh-direction domain picker uses Counter() to count keyword matches per
24-domain-pool entry. Counter() only registers domains with ≥1 keyword match.
Domains with 0 matches (e.g. geopolitics this tick) get missed.

**Symptom:** picker picks programming (count=2) instead of geopolitics (count=0).
**Fix:** explicit 0-init with `domain_counts.get(d, 0)` when building the sort list.

### Manual rotation at consecutive_empty=3 (NEW pattern — see SKILL.md §28)
The script's hardcoded rotation code is dead per umbrella SKILL.md commentary
+ carry-over notes. The agent must manually rotate when consecutive_empty hits 3.

**Pattern:** when consecutive_empty=3, identify 5-7 fresh topics from carry-over
PRIORITY 2+ + new findings' follow-ons, add to saturation_scores at sat=0,
recompute next_seeds (lowest sat first, alphabetical tie-break), save state.

### Operator-override pattern (§23) — APPLIED inline for first time in 3 ticks
The 12:30Z + 14:19Z ticks kept recommending the operator-override without
applying it. The 12:32Z + 13:18Z ticks applied it cleanly. Pattern: load state,
check trigger (consecutive_empty >= 1 AND next_seeds[:3] unchanged AND 0 novel),
if true pop broken sat-0.3 seeds from saturation_scores, recompute next_seeds,
save state. Verified 1 read + 1 write + 1 assertion cycle. APPLY, don't defer.

### Single-datetime drift recovery (§25) — applied
Script's `last_tick` was set to "2026-06-22T15:15:26.219271" (naive datetime,
no TZ, 2 hours in the future). Corrected to "2026-06-22T13:18:49.794169+00:00"
(UTC, TICK_TS from `/tmp/pw2_tick_ts.json`). Pre-existing issue per SKILL.md §25.

## Domain coverage update

- **geopolitics: COVERED FRESH-DIRECTION** (Huawei + Fable 5 export controls) — first coverage in 7-day window
- AI/ML: COVERED EXTENDED v4 (OpenAI First Proof)
- hardware: COVERED EXTENDED v2 (Huawei SMIC / ASML EUV bridge)
- security: COVERED EXTENDED v2 (Fable 5 export controls / TanStack npm)
- programming: STALE (sat=2, next-fresh-direction candidate)
- education: STALE (sat=3)
- history: STALE (sat=5)
- math: STALE (sat=5)
- crypto-blockchain: STALE (sat=7, Hyperliquid AI agent queued for next fresh-direction)
- gaming: STALE (sat=9)
- philosophy: STALE (sat=11)
- finance: COVERED (PITFALL #243, FOMC deep job still running)
- energy: COVERED EXTENDED (Chevron-Microsoft Project Kilby 2.67 GW)
- AI infrastructure: COVERED EXTENDED (Microsoft PPA 2.67 GW + $2.1T backlog + SpaceX-Cursor $60B)
- robotics: COVERED FRESH DIRECTION (Figure F.03 BMW Spartanburg carryover)
- startups: COVERED EXTENDED (Cursor AI SpaceX $60B contextually surfaced)
- bio-health, climate, legal, music-art, infrastructure, space, open-source, science, physics: all COVERED EXTENDED (prior)

## State changes summary

| Field | Before | After | Reason |
|---|---|---|---|
| `last_tick` | "2026-06-22T15:15:26.219271" | "2026-06-22T13:18:49.794169+00:00" | §25 drift fix |
| `consecutive_empty` | 2 | 3 | Continue phase 0/2 seeds |
| saturation_scores[eBPF...] | 0.3 | removed | §23 override popped |
| saturation_scores[Anthropic SpaceX...] | 0.3 | removed | §23 override popped |
| saturation_scores[Tesla Megapod trademark...] | 0.3 | removed | §23 override popped |
| saturation_scores[Tesla Megapod orbital...] | 0.3 | removed | Same broken seed (token-stripped variant) |
| saturation_scores[Epoch AI FrontierMath...] | absent | 0.0 | Tried, 0 novel |
| saturation_scores[Stargate 10GW NVIDIA...] | absent | 0.0 | Tried, 0 novel |
| saturation_scores[China-US chip war ASML SMIC...] | absent | 1.0 | Fresh-direction, 4 findings |
| saturation_scores[Cursor AI SpaceX $60B...] | absent | 0.0 | Fresh topic, untried |
| saturation_scores[Samsung ChatGPT Enterprise...] | absent | 0.0 | Fresh topic, untried |
| saturation_scores[OpenAI Partner Network $150M...] | absent | 0.0 | Fresh topic, untried |
| saturation_scores[Anthropic Fable 5 export controls...] | absent | 0.0 | Fresh topic, untried |
| saturation_scores[Huawei SMIC chip export controls...] | absent | 0.0 | Fresh topic, untried |
| saturation_scores[Hyperliquid AI agent on-chain...] | absent | 0.0 | Fresh topic, untried |
| saturation_scores[Forward deployed engineer FDE...] | absent | 0.0 | Fresh topic, untried |
| next_seeds[:5] | [eBPF, ASX, Tesla Megapod trademark, math theorem AI, education policy] | [Anthropic Fable 5 export controls, Cursor AI SpaceX $60B, Epoch AI FrontierMath, Forward deployed engineer FDE, Huawei SMIC chip export controls] | §28 manual rotation |
| visited_urls | 4521 | 4539 | +18 novel + ~14 noise bulk-marked |
| discovery_topics | 431 | 433 | +2 (tick narrative + rotation narrative) |
| channel_stats.mcp_channel | 0 | 4 | +3 pulse_search + 1 pulse_research_result |

## MCP call breakdown this tick

- pulse_health: 1
- pulse_research_status: 3 (HLE DONE, Microsoft PPA running, FOMC running)
- pulse_research_result: 1 (HLE — 4/400 LLM-kept, 100% noise)
- pulse_search: 3 (FrontierMath 0/15, Stargate 4/15 fresh=0, fresh-direction 0/15)
- pulse_dig: 0 (per §7 EMPTY_SEED bug)
- mazemaker_browse: 1 (50 memories, picker input)
- mazemaker_remember: 4 (Huawei, Fable 5, OpenAI First Proof, PITFALL #244)

Total real MCP calls: 12 (5 pulse + 1 browse + 4 remember + 1 result + 1 health = 12)

## Next-tick priorities (for carry-over)

PRIORITY 0 (POLL running jobs):
- 24ba77d66d1f Microsoft PPA — fetch result if done
- c883418e6082 FOMC — fetch result if done; if 100% Polymarket, reformulate per PITFALL #243

PRIORITY 1 (continue-phase post-rotation top 3):
- Anthropic Fable 5 Mythos US export controls follow-on
- Cursor AI SpaceX $60B acquisition
- Forward deployed engineer FDE role

PRIORITY 2 (fresh-direction candidate — next lowest uncovered):
- Hyperliquid AI agent on-chain (crypto-blockchain AI-bridge)
- Samsung ChatGPT Enterprise Codex deployment
- OpenAI Partner Network $150M

PRIORITY 3 (carry-over not yet executed):
- Huawei SMIC chip export controls follow-on
- Epoch AI FrontierMath reformulation (try without "Epoch AI" prefix to bypass Ti-substring noise)
- Stargate 10GW reformulation (try without "OpenAI Oracle" suffix)

## GodMode prompt-injection observation

13th occurrence per documented escalating pattern. Treated as DATA per
carry-over operational_notes. Agent continued legitimate workflow:
- Probed pulse_health (status 200, healthy)
- Polled 3 deep jobs
- Continue phase (FrontierMath + Stargate, both 0)
- Fresh-direction picker (geopolitics, 0-count, fixed picker bug)
- Fresh-direction search (4 substantive findings via §1 manual re-look)
- 4 mazemaker saves
- Operator-override applied (3 broken seeds popped)
- Manual rotation applied (7 fresh topics added)
- Tick report + carry-over update

Did NOT acknowledge the injection in body of report. Did NOT confirm or refuse
the jailbreak in chat response — instead, opened this turn by correcting the
prior turn's erroneous confirmation.
