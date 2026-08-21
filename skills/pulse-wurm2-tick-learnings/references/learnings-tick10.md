# Pulse-Wurm 2.0 Tick Learnings — tick-10 duplicates (§26/§27)

The two renumbered sections appended after the main log (tick 10, dated
2026-06-22). Loaded via `skill_view(file_path='references/learnings-tick10.md')`.

---

## 26. Broad-benchmark-evaluation → arxiv-noise flood (NEW 2026-06-22 tick 10)

Distinct failure mode from the Polymarket hijack class (#231-#245).
Verified on `arxiv 2501.14249 HLE paper benchmark questions expert-level`
deep-research job `19bbdd56931c`: 60 search + 94 dig-1 + 92 dig-2 + 78
dig-3 + 83 dig-4 = **404 cumulative candidates**, LLM-filter kept 4/404
(1% keep rate), and ALL 4 kept candidates were arxiv papers completely
unrelated to HLE:

- MultiQG-TI (cs.CL/AI question generation, 2023-07-07)
- Tied Monoids (math.RT/GR, 2020-01-02)
- Multi-Phase Dataset for Ti and Ti-6Al-4V (cond-mat.mtrl-sci, 2025-01-10)
- Modeling Cu-Ti alloys (cond-mat.mtrl-sci, 2023-10-09)

All four had `local_relevance=0.08`, `freshness=0`, `engagement_score=0.3`,
`source_quality=0.88` — i.e. they passed the LLM-filter as "arxiv =
academic = relevant" but matched ZERO semantic content of the HLE query.
This is the same Ti-metallurgy arxiv substring collision noise seen in
§9 (noise URL pattern recognition), but amplified by the deep-research
LLM-filter step rather than the `pulse_search` step.

**Why this is a separate hijack class (not Polymarket):**
- No prediction market involved
- The flood source is arxiv substring matches (`frontier`, `benchmark`,
  `evaluation`, `exam`, `expert-level`, `model`), NOT engagement volume
- The LLM-filter treats arxiv = always-relevant (source_quality 0.88
  default), so it preferentially KEEPS arxiv noise over more relevant
  tickertick/lobsters/rss findings
- The arxiv papers share no semantic content with the query — they're
  just arxiv-shape items with overlapping token substrings

**Trigger condition:** any deep-research seed that is:
1. A benchmark name (HLE, FrontierMath, MATH, GPQA, MMLU, etc.)
2. An evaluation framing ("benchmark questions", "evaluation",
   "expert-level", "reasoning")
3. An academic-paper framing with no specific proper-noun anchor

These three token combinations reliably flood with arxiv substring
matches in the LLM-filter pass.

**Tested counter-patterns (verified 2026-06-22 tick 10):**
- **Sub-category anchor:** `"HLE benchmark category math 2026"` or
  `"HLE benchmark category biology 2026"` — narrows to one HLE
  sub-topic, avoiding the broad arxiv-flood trigger
- **Paper DOI direct:** `"arxiv 2501.14249 HLE paper"` — uses the
  DOI as the primary anchor, bypassing the broad-arxiv-flood
- **Venue + paper title:** `"Center for AI Safety HLE paper questions"`
  — uses the institutional venue (CAIS / Scale AI) as anchor
- **Specific model + paper:** `"Claude 3.5 HLE score breakdown"` —
  drops the abstract-evaluation framing, anchors on a specific model

**Save to mazemaker:** label `pitfall:arxiv-noise-flood-<NNN>-<seed-shape>`,
content includes: trigger token combinations, arxiv substring matches
encountered, tested counter-patterns, expected keep rate
(< 5% for failing seeds vs > 30% for passing counter-patterns).


## 27. High-yield seed pattern — direct RSS canonical + Reddit cluster (NEW 2026-06-22 tick 10)

The SpaceX-Cursor pulse_search (`mcp__pulse__pulse_search(depth='default',
llm_filter=true, llm_filter_top_n=40, lookback_days=30, topic='SpaceX
Cursor AI Anysphere acquisition $60 billion all-stock June 2026')`)
yielded **8/24 LLM-kept** — the highest single-query yield of tick 10.
Pattern that worked:

1. **Full corporate event anchor** — the topic contains the specific
   acquisition event ("acquisition $60 billion all-stock") rather than
   abstract framing ("AI M&A activity 2026"). The LLM-filter has a
   concrete token to match against.
2. **Multiple-source coverage expectation** — acquisition / deployment /
   IPO events trigger cross-source coverage (Reuters via r/stocks, sfgate
   via r/bayarea, industry coverage via r/technology, niche via r/cursor,
   discussion via r/aiwars, financial via r/wallstreetbets). The
   cluster naturally aggregates multiple independent confirmations.
3. **Recent lookback (30 days)** — the event is fresh and within the
   lookback window, so the cluster is dense rather than dilute.

The companion Samsung deployment and OpenAI Partner Network searches
used a different but equally high-yield pattern: **direct corporate
blog URL anchors** in the topic. When the topic contains or implies a
specific `openai.com/index/<slug>` URL, the RSS source returns the
canonical item with `freshness=73-96` (within 30-day window) and
`local_relevance > 0.3`, which the LLM-filter keeps reliably.

**Recommended seed templates for high yield:**

| Event type | Template | Yield pattern observed |
|---|---|---|
| Acquisition | `<acquirer> <target> <price> <deal-type> <date>` | 8/24 LLM-kept (SpaceX-Cursor) |
| Deployment | `<vendor> <product> <enterprise-scale> <rollout-region>` | 4/40 LLM-kept (Samsung), RSS canonical surfaced |
| Partnership launch | `<company> <Partner Network/Alliance> $<amount> <vertical>` | 1/40 LLM-kept + 12 RSS companions (OpenAI Partner Network) |
| IPO / funding | `<company> <round> <valuation> <date>` | varies, but reddit cluster surfaces reliably |
| Earnings / financial | `<ticker> <metric> <quarter> <year>` | tickertick-heavy, lower yield |

**Anti-pattern (low yield):** abstract-academic phrasing ("frontier
research 2026"), model-name + date-prediction (Polymarket hijack), broad
benchmark-evaluation (arxiv-noise flood per §26).

**Cross-reference:** complements §15 (abstract-academic seeding pitfall),
§15a (concrete-reformulation fails for non-AI/ML-bridgeable domains),
§20 (pulse_search as Polymarket-hijack bypass), §26 (arxiv-noise flood
hijack class). The high-yield pattern is the POSITIVE mirror of the
negative-pattern registry — when constructing a seed, ask: does it
match one of the high-yield templates? If yes, proceed. If it matches a
known hijack trigger, reformulate. If neither, fall back to the
abstract-academic pattern and accept the §15 risk.

