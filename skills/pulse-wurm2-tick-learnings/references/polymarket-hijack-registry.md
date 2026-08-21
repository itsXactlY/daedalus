# Polymarket Hijack Surface Registry

Living registry of Polymarket prediction-market URLs that hijack the
`pulse_research` pipeline (dig rounds + LLM-filter rerank) via
engagement-volume ranking across 13+ locale variants.

**Why this exists:** Polymarket markets are engagement-weighted by volume.
The dig-follower pulls URLs from the body of high-engagement pages,
which causes 13+ locale variants of the same market to dominate the
candidate pool. A seed like `"Claude score on Humanity's Last Exam by
June 30"` returns en/zh/de/ja/bn/pt/es/it/tl/th/fr/uk/ru/hu variants
(13+ locales, $375K volume) — all of the SAME market — and they crowd
out substantive findings from tickertick/lobsters/arxiv.

**Adjacent failure mode (NEW 2026-06-22 tick 10):** the
**broad-benchmark-evaluation → arxiv-noise flood** (#244) is NOT a
Polymarket hijack but shares the same operational symptom (deep-research
yields no signal). See hijack class #8 below.

**When to add a new surface:** when a pulse_research result has
≥80% Polymarket contamination AND the dominant market is a token
pattern not already in the table below, OR when a deep-research seed
triggers the arxiv-noise flood pattern (#244 class). Add a new row,
increment `polymarket_hijack_surface_count` in carry-over file,
document the counter-pattern that avoids the hijack.

**Counter-pattern discipline:** for every surface, identify at least
one tested reformulation that bypasses the hijack. The reformulation
should use specific proper nouns (corporate blog URL, paper DOI,
deployment venue, funding round) — NOT abstract or vague terms.

## Active Hijack Surfaces (16, plus class #8 — arxiv-noise flood, class #9 — non-AI-entity+year)

| # | Hijack trigger (AVOID in seeds) | Market name | Locale count | Counter-pattern (USE) |
|---|---|---|---|---|
| 231 | 'best AI model' + '2026' | Which company has best AI model end of 2026 | 12+ | model-agnostic "AI model comparison 2026" |
| 232 | arxiv PDF + specific DOI | (deep-parse timeout, not a market) | n/a | use arxiv listing URL |
| 233 | 'Gemini 3.5' / 'Claude 4' + released verb | Claude/GPT-5/Gemini release markets | 12+ | use full corporate blog URL (blog.google, openai.com/index) |
| 234 | 'Y Combinator' standalone | Meek Mill gets Y Combinator funding | n/a | specific company name + funding round |
| 235 | narrow K-12 product (Khanmigo) | Khanmigo outcomes market | n/a | broader "AI tutoring K-12 deployment" |
| 236 | 'benchmark' + model name + 2026 | (meta-pattern, multiple markets) | varies | venue + paper title (NOT benchmark + model) |
| 237 | 'AI ruining' + 'Nature' + skills | Which company has best AI model end of 2026 | 12+ | drop subjective verb; "critical thinking AI measurement 2026" |
| 238 | 'Figure' / 'Optimus' / 'Unitree' standalone | # of Packages Pushed by Figure F.03 | 12+ | specific deployment venue (BMW Spartanburg, Tesla factory) |
| 239 | 'AI safety' + 'bill' | U.S. enacts AI safety bill in 2025 | 12+ | drop both; use "CAIS HLE paper" alone |
| 240 | 'data center' + 'moratorium' + 2026/2027 | AI data center moratorium passed before 2027 | 12+ | "AI infrastructure energy consumption" or "data center GPU H100 deployment 2026" |
| **241** | **'humanity's last exam' + 'Claude/Anthropic' + date-prediction** | **Claude score on Humanity's Last Exam by June 30?** | **13+** | **paper DOI arxiv.org/abs/2501.14249; or model-agnostic "expert-level LLM evaluation benchmark questions"** |
| **242** | **'energy infrastructure' + 'policy' / 'ceasefire' / 'Ukraine'** | **Energy infrastructure ceasefire in Ukraine in March?** | **12+** | **corporate-anchor + "PPA" / "power deal" ("Microsoft data center natural gas power deal")** |
| **243** | **'FOMC' + date-prediction + 'rate decision' / 'Treasury yield' / 'by [date]'** | **US 10Y Treasury yield above 5% by June 30?** | **12+** | **Fed officials by name (Powell/Williams/Bostic/Cook/Waller) + economic-data anchor (CPI/NFP/PCE) OR market-reaction anchor (SOFR/10Y-2Y spread/MOVE index)** |
| **244** | **'HLE' / 'Humanity's Last Exam' standalone deep-research seed (NOT Polymarket hijack — LLM-filter arxiv-noise flood)** | **n/a — different failure mode: LLM-filter keeps 4/404 arxiv papers all unrelated to HLE** | **n/a** | **specific HLE sub-category anchor ("HLE benchmark category math 2026"); paper DOI arxiv.org/abs/2501.14249** |
| **245** | **'Figure F.03 BMW Spartanburg' + delivery-volume metric (re-surface of #238 with added venue specificity)** | **# of Packages Pushed by Figure F.03 (1/40 LLM-kept, Polymarket-only)** | **12+** | **vendor press release URL (figure.ai/blog/...) OR specific deployment metric already in corpus (e.g. "238000 packages")** |
| **246** | **'SpaceX' (or other non-AI PM-traded entity) + 2026 year anchor** (NEW 2026-06-22 tick 19, PITFALL #263 confirmation on Cursor/SpaceX seed) | **How many SpaceX Starship launches reach space in 2026?** | **18+** | **drop the PM-traded entity anchor entirely; use named-AI-product + named-event ("Anysphere Cursor AI coding agent valuation 2026")** |

## Hijack class taxonomy (8 classes, 2026 pattern recognition)

The 15 surfaces cluster into ~8 hijack classes by load-bearing token
combination. New surfaces often fit an existing class:

1. **MODEL-NAME + DATE-PREDICTION** — Surfaces #233 (release verb),
   #241 (HLE+Claude+date), #231/#237 (best AI model + 2026).
   Class reformulation: drop date OR drop model name; use venue + paper
   title or model-agnostic framing.

2. **ACCELERATOR-NAME + FUNDING** — Surface #234 (Y Combinator standalone).
   Class reformulation: use specific company name + funding round.

3. **VENDOR-NAME + NUMERIC-DELIVERABLE** — Surface #238 (Figure F.03
   packages count), #245 (Figure F.03 BMW Spartanburg re-surface).
   Class reformulation: use specific deployment venue OR vendor's full
   corporate blog URL.

4. **POLICY-NAME + GEOGRAPHIC-CONFLICT** — Surface #239 (AI safety bill),
   #240 (data center moratorium), #242 (energy infrastructure
   ceasefire). Class reformulation: drop the policy/bill/geopolitical
   term; use corporate-anchor + "PPA" / "power deal" / "deployment".

5. **BENCHMARK-NAME + MODEL-NAME + YEAR** — Surface #236 (benchmark +
   model + 2026). Class reformulation: venue + paper title without
   model name.

6. **NARROW-PRODUCT + VAGUE-ANCHOR** — Surface #235 (Khanmigo narrow
   K-12), #237 (Nature + AI ruining). Class reformulation: broader
   framing without subjective verbs.

7. **ARXIV-PDF-DEEP-PARSE-TIMEOUT** — Surface #232 (not a Polymarket
   market, an infrastructure failure mode). Class reformulation: use
   arxiv listing URL instead of direct PDF.

8. **BROAD-BENCHMARK-EVALUATION → ARXIV-NOISE FLOOD** (#244, NEW 2026-06-22
   tick 10). Distinct from classes 1-7 — not a Polymarket hijack but
   shares the operational symptom of "deep-research yields no signal."
   Trigger: deep-research seeds containing (benchmark name) + (evaluation
   framing) + (no specific proper-noun anchor). Mechanism: LLM-filter
   defaults to keeping arxiv items at source_quality=0.88, which causes
   substring-token-matched arxiv papers (Ti metallurgy's "frontier",
   MultiQG's "expert-level", Tied Monoids' "T" token) to dominate the
   kept-candidate pool. Verified yield: 4/404 LLM-kept, 0/4 related to
   the actual query. Counter-pattern: specific sub-category anchor
   ("HLE math", "HLE biology"), paper DOI, venue + paper title, specific
   model + paper (NOT benchmark + model + 2026).

9. **NON-AI-ENTITY + YEAR-ANCHOR** (#246, NEW 2026-06-22 tick 19, PITFALL
   #263). Distinct from classes 1-7 — the hijacked entity is NOT an AI
   model/company. Trigger: any seed that contains a PM-traded entity name
   (SpaceX, Tesla, Bitcoin, Figure, NVIDIA stock, Apple stock, etc.) AND
   a year anchor (2026, 2027, by-June-30). Mechanism: the planner routes
   to the highest-volume PM contract for that entity, ignoring the rest of
   the seed's tokens. Verified on Cursor/SpaceX seed: 18/20 top results =
   localized PM Starship-launch pages in 18 languages, ZERO Cursor URLs.
   Counter-pattern: drop the PM-traded entity anchor entirely; rephrase
   with named-AI-product + named-event + 2026 (e.g. "Anysphere Cursor
   AI coding agent valuation 2026" instead of "SpaceX Cursor Anysphere
   $60B acquisition 2026"). The misleading "kept=101" stat in tick 19 was
   kept-for-SpaceX not kept-for-Cursor — always verify which subtopic the
   kept pool matches.

## Successful bypass patterns (counter-pattern set v7)

When constructing a seed that has high hijack risk, prefer these
patterns over abstract/generic framings:

- **Paper DOI**: `arxiv.org/abs/2501.14249` (for HLE)
- **Full corporate blog URL**: `blog.google/...`, `openai.com/index/...`
- **Full press release URL**: `tesla.com/AI`, `figure.ai/blog`
- **Venue + paper title**: `"FrontierMath Epoch AI math reasoning"`
  (NOT `"FrontierMath benchmark math model 2026"`)
- **Specific company + funding round**: `"Anthropic Series F 2026"`
  (NOT `"Y Combinator 2026 batch"`)
- **Broader educational framing**: `"Khan Academy classroom integration"`
  (NOT `"Khanmigo outcomes"`)
- **Specific deployment venue**: `"BMW Spartanburg humanoid robot 2026"`
  (NOT `"Figure Optimus humanoid robot deployment"`)
- **Specific model + 'paper' or 'arxiv' WITHOUT 'safety' + 'bill'**
- **`"AI infrastructure energy consumption"` or `"data center GPU H100
  deployment 2026"`** (NOT `"data center moratorium 2026"` or
  `"energy infrastructure policy 2026"`)
- **Corporate-anchor + "PPA" / "power deal"**: `"Microsoft data center
  natural gas power deal"`, `"Amazon AWS nuclear power agreement"` (for
  energy infrastructure topics)
- **NEW v7 (2026-06-22 ticks 9-10):**
  - Fed officials by name (Powell/Williams/Bostic/Cook/Waller) +
    economic-data anchor (CPI/NFP/PCE) OR market-reaction anchor
    (SOFR/10Y-2Y spread/MOVE index) — replaces PITFALL #243 hijacked seeds
  - Specific HLE sub-category anchor (`"HLE math"` or `"HLE biology"`)
    — NOT `"HLE"` / `"Humanity's Last Exam"` standalone (PITFALL #244)
  - Specific Figure delivery-volume metric (e.g. `"Figure F.03 BMW
    238000 packages"`) — replaces Figure F.03 venue-only seed
    (PITFALL #245 re-surface)

## High-yield seed pattern (POSITIVE mirror, NEW 2026-06-22 tick 10)

The SpaceX-Cursor pulse_search yielded **8/24 LLM-kept** — highest
single-query yield of tick 10. Pattern that worked:

1. **Full corporate event anchor** — topic contains specific event
   ("acquisition $60 billion all-stock") rather than abstract framing
   ("AI M&A activity 2026"). The LLM-filter has concrete tokens to match.
2. **Multiple-source coverage expectation** — acquisition / deployment /
   IPO events trigger cross-source coverage (Reuters via r/stocks,
   sfgate via r/bayarea, industry via r/technology, niche via r/cursor,
   discussion via r/aiwars, financial via r/wallstreetbets). The
   cluster naturally aggregates multiple independent confirmations.
3. **Recent lookback (30 days)** — event is fresh within window, so
   cluster is dense rather than dilute.

**Recommended high-yield seed templates:**

| Event type | Template | Yield pattern observed |
|---|---|---|
| Acquisition | `<acquirer> <target> <price> <deal-type> <date>` | 8/24 LLM-kept (SpaceX-Cursor) |
| Deployment | `<vendor> <product> <enterprise-scale> <rollout-region>` | 4/40 LLM-kept (Samsung), RSS canonical surfaced |
| Partnership launch | `<company> <Partner Network/Alliance> $<amount> <vertical>` | 1/40 LLM-kept + 12 RSS companions (OpenAI Partner Network) |
| IPO / funding | `<company> <round> <valuation> <date>` | varies, but reddit cluster surfaces reliably |
| Earnings / financial | `<ticker> <metric> <quarter> <year>` | tickertick-heavy, lower yield |

**Anti-pattern (low yield):** abstract-academic phrasing ("frontier
research 2026"), model-name + date-prediction (Polymarket hijack),
broad benchmark-evaluation (arxiv-noise flood per class #8).

When constructing a seed, ask: does it match one of the high-yield
templates? If yes, proceed. If it matches a known hijack trigger
(classes 1-7 or #244), reformulate per the counter-pattern. If
neither, fall back to the abstract-academic pattern and accept the §15
risk.

## Pulse_research hijack bypass via pulse_search

When `pulse_research` returns ≥95% Polymarket contamination, run
`pulse_search` with the SAME topic to recover substantive findings.
See SKILL.md section 20 for the operational pattern.

**Successful bypass examples:**
- Topic "geopolitics AI infrastructure energy policy 2026 data center
  power grid": pulse_research returned 20/20 Polymarket.
  pulse_search recovered:
  - Chevron-Microsoft 20-year natural gas PPA for West Texas data
    center (techmeme.com, msft tag)
  - Hyperscaler backlog $2.1 trillion (cloudwars.com)
  - Nature "Is AI ruining our skills?" article
    (nature.com/articles/d41586-026-01947-1)
- Topic "Figure F.03 humanoid robot BMW Spartanburg manufacturing
  packages 2026" (re-surface of PITFALL #238): pulse_research would
  hijack to Polymarket. pulse_search returned 1/40 LLM-kept — the
  Polymarket market itself, confirming the hijack. Result: confirmed
  counter-pattern needed (specific deployment-volume metric).

## Update protocol

When a new hijack surface is discovered:

1. Add a row to the active surfaces table above (and a new class row
   if it doesn't fit an existing class taxonomy entry)
2. Identify the load-bearing token combination (which class does it fit?)
3. Test at least one counter-pattern (reformulation that bypasses the
   hijack) and document it in the "Counter-pattern" column
4. Save to mazemaker with label `pitfall:polymarket-<NNN>-<short-name>`
   (for Polymarket surfaces) or `pitfall:arxiv-noise-flood-<NNN>-<seed-shape>`
   (for #244 class surfaces)
   Content includes: locale count (n/a for #244), market volume as of
   date, tested counter-pattern, known failure modes
5. Increment `polymarket_hijack_surface_count` in
   `~/.hermes/pulse-wurm-next-topics.json` (only for Polymarket surfaces;
   arxiv-noise-flood surfaces get a separate `arxiv_noise_flood_count`)
6. Append the surface to the carry-over file's
   `next_tick_fresh_direction_picker.polymarket_hijack_counter_pattern_set`
7. Patch this reference file + the parent SKILL.md (§21 table) +
   the description frontmatter with the new surface count