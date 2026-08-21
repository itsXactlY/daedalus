# Sources Filter Recipe — VALIDATED 2026-06-21 07:00Z

## What this is

A working fix for the topic-drift-to-polymarket pattern that affected 3/3 deep jobs in the 2026-06-20 tick. Pass an explicit `sources` list to `pulse_research_start` to exclude `polymarket` from the 23-source fan-out. Validated 2026-06-21: 3/3 deep jobs reached dig-1 with growth 105-128%, no drift, vs the prior-tick 3/3 jobs that degenerated to 95% polymarket locale noise.

## When to use

**USE the filter (no polymarket)** for:
- Benchmarks and evals (HLE, ProgramBench, METR, SWE-bench, FrontierMath, etc.)
- Research papers and arxiv findings
- Model release announcements (HuggingFace, GitHub)
- Open-source community threads (r/LocalLLaMA, r/MachineLearning, HackerNews)
- Engineering / capability / frontier model topics
- Anything where the load-bearing signal is in arxiv / GitHub / blog / Reddit / News

**DO NOT USE the filter (keep polymarket)** for:
- Forward-looking / speculation topics (OpenAI social, IPO dates, M&A, ban/suspension)
- Topics where the question is "what will happen by date X"
- Topics where the load-bearing signal is in Polymarket prediction markets
- Topics that mention "ban", "suspend", "halted", "restored", "approved", "filed" — event-track

## The recipe — copy-pasteable

```python
SOURCES_NO_POLYMARKET = [
    "arxiv",
    "bing_news",
    "bluesky",
    "devto",
    "github",
    "hackernews",
    "huggingface",
    "lemmy",
    "lobsters",
    "manifold",
    "metaculus",
    "news",
    "openalex",
    "reddit",
    "rss",
    "sem_scholar",
    "serpapi_news",
    "stackexchange",
    "tickertick",
    "twitter_browser",
    "web",
    "youtube",
]
# 22 sources, polymarket excluded. Use this list verbatim in pulse_research_start(sources=...)

mcp__pulse__pulse_research_start(
    depth="deep",
    lookback_days=90,
    max_fetches_per_round=500,
    max_per_round=50,
    max_wurm_rounds=4,
    n=20,
    sources=SOURCES_NO_POLYMARKET,
    topic="<your research-track topic here>",
)
```

## Time cost (measured)

| Phase | Default (polymarket included) | Filter (polymarket excluded) |
|-------|-------------------------------|------------------------------|
| Search | ~60s | ~180s (3 min) |
| Dig-1 | ~120s | ~120s (same) |
| Dig-2..4 | ~150-200s each | ~150-200s each (same) |
| LLM filter | ~30s | ~30s (same) |
| **Total** | **~25-30 min** | **~30-35 min** |

**Net cost**: +5-10 min per job. **Net win**: avoids the entire drift-to-noise pattern. The 5-10 min is the price of admission for not having to re-run a drifted job (which itself costs 30+ min and returns noise).

## Topic-class decision rule (before launch)

Ask: does the topic contain event-nouns ("launch", "ban", "resolves", "restored", "halted", "approved", "filed", "by date X")?

- **YES** → keep polymarket in sources (load-bearing signal)
- **NO** AND topic is research/eval/benchmark/capability oriented → use the no-polymarket filter

## Detection signal — when to abort and re-run

If a deep job shows 3+ dig rounds with >50% of lineage edges pointing to a single domain (Polymarket, archive.org, UFC, etc.), declare the job drifted. Routes to recover:

1. **Re-run with this filter** (the validated fix)
2. OR use the cheaper `pulse_search(depth='default', llm_filter=false)` pattern and parse `items_by_source` manually
3. OR direct-fetch canonical URLs (arxiv.org, anthropic.com, blog posts) and skip pulse_research entirely

## Companion Pattern 14 (PM locale pollution)

The Polymarket locale-clone pollution is a SEPARATE bug. The Pattern 14 mitigation (post-filter for `polymarket.com/<non-en-locale>/event/...` URLs) is still needed when polymarket IS in the sources. The two patterns compose: this filter prevents drift at the source; Pattern 14 cleans the noise that arises when polymarket is included for legitimate reasons.

## Validation log

| Date | Tick | Recipe applied | Result |
|------|------|----------------|--------|
| 2026-06-20 06:45Z | Prior | Default (polymarket included) | 3/3 jobs degenerated to 95% polymarket locale noise by dig-4 |
| 2026-06-21 07:00Z | This | 22-source list, polymarket excluded | 3/3 jobs healthy at dig-1 with 105-128% growth, zero PM drift |

## Memory IDs

- 825299 — bug:sources-filter-slower-search-phase (search phase ~3min vs 60s default, but dig stages unaffected)
- 825305 — decision:sources-filter-recipe-validated (full validation analysis)
