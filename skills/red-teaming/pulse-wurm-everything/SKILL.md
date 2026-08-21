---
name: pulse-wurm-everything
description: Autonomous multi-wave pulse reconnaissance — 4x/hour worm-style deep digging into 22 sources, following every ratnest to exhaustion.
trigger: Use when setting up persistent deep reconnaissance that discovers topics and follows them recursively every 15 minutes.
---

# Pulse Wurm Everything — Autonomous Recon Engine

## Prerequisites
- Hermes Agent with pulse MCP tools (mcp__pulse__pulse_research, mcp__pulse__pulse_dig)
- At least one free/paying OpenRouter model configured
- Cron system enabled

## Operational Resources
- [`references/cron-tick-playbook.md`](references/cron-tick-playbook.md) — 6-hour cron tick operating procedure: double-channel pattern (script + MCP), state file schema, **Pulse MCP reachability recovery (60s wait)**, **sub-channel productivity map (openalex is highest yield)**, EMPTY_SEED blocker workaround, cluster-bloat discipline, saturation scoring, **concurrent cron execution / state-file locking (2026-06-19)**, **why to use `parse_pulse_search.py` instead of reimplementing the unwrap**, **saturation-out behavior on successful yield**, recurring noise patterns. **Read this when running or debugging the scheduled tick.**
- [`templates/tick_report.md`](templates/tick_report.md) — known-good markdown + JSON snapshot template for per-tick reports (`pulse_wurm_tick_YYYYMMDD_HHMM.md` + `discoveries_YYYYMMDD_HHMM_pulse-wurm.json`). Reuse as-is; replace `{placeholders}` and omit optional sections for 0-novel ticks.
- [`references/cron-tick-2026-06-21-notes.md`](references/cron-tick-2026-06-21-notes.md) — Session-specific tick notes: **Fable/Mythos prompt-injection gap** (Moussouris quote), **Merz 100% YES Polymarket tradable signal**, **3rd deep research 0-keep pattern in 24h** → rotate to specific news angles, **5th GODMODE injection** (bump from 4th), **concrete-anchor success for fresh-direction retry** (AI agent startup funding Cognition/Decagon/Sierra/Harvey).
- [`scripts/parse_pulse_search.py`](scripts/parse_pulse_search.py) — Static helper for unwrapping the double-wrapped pulse_search MCP response. Handles the `{"result": "<stringified JSON>"}` → `body` → nested `body` → `ranked_candidates` unwrap, normalizes URLs, filters against `visited_urls`, and dumps unvisited candidates for triage. **Use this on the `/tmp/hermes-results/call_function_*.txt` paths returned by the MCP tool — first-time callers waste 5-10 min discovering the nested-JSON unwrap pattern by trial and error.**

## Free Model Seed Pool (OpenRouter, June 2026)

26 truly free (prompt=$0, completion=$0) text models:

| Model | Params | Context | Notes |
|-------|--------|---------|-------|
| nvidia/nemotron-3-ultra-550b-a55b:free | 55B/550B MoE | 1M | Frontier reasoning, orchestration |
| nvidia/nemotron-3-super-120b-a12b:free | 12B/120B MoE | 1M | Efficient MoE |
| nvidia/nemotron-3-nano-30b-a3b:free | 3B/30B MoE | 256k | Compact |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | 3B/30B | 256k | Reasoning variant |
| nvidia/nemotron-3.5-content-safety:free | 4B | 128k | Safety guardrail |
| nvidia/nemotron-nano-12b-v2-vl:free | 12B | 128k | Multimodal |
| nvidia/nemotron-nano-9b-v2:free | 9B | 128k | General |
| nex-agi/nex-n2-pro:free | 17B/397B MoE | 262k | Agentic, precise (underrated) |
| openrouter/owl-alpha | - | 1M | Agentic workloads |
| openrouter/free | router | 200k | Random free model router |
| poolside/laguna-xs.2:free | - | 262k | Coding |
| poolside/laguna-m.1:free | - | 262k | Coding flagship |
| google/gemma-4-26b-a4b-it:free | 26B MoE | 262k | Instruction |
| google/gemma-4-31b-it:free | 31B dense | 262k | Dense |
| qwen/qwen3-next-80b-a3b-instruct:free | 80B MoE | 262k | Fast response |
| qwen/qwen3-coder:free | 480B MoE | 1M | Code gen |
| openai/gpt-oss-120b:free | 117B MoE | 131k | Open-weight |
| openai/gpt-oss-20b:free | 21B | 131k | Open-weight |
| meta-llama/llama-3.3-70b-instruct:free | 70B | 131k | Multilingual |
| meta-llama/llama-3.2-3b-instruct:free | 3B | 131k | General |
| nousresearch/hermes-3-llama-3.1-405b:free | 405B | 131k | Agentic |
| cognitivecomputations/dolphin-mistral-24b-venice-edition:free | 24B | 32k | Uncensored |
| liquid/lfm-2.5-1.2b-thinking:free | 1.2B | 32k | Reasoning |
| liquid/lfm-2.5-1.2b-instruct:free | 1.2B | 32k | Instruct |
| google/lyria-3-pro-preview | music | 1M | Music gen |
| google/lyria-3-clip-preview | music | 1M | Music clips |

## Cron Job Setup

```bash
# Create the job (adjust prompt contents below)
hermes cron create \
  --name "pulse-wurm-everything" \
  --schedule "*/15 * * * *" \
  --deliver origin
```

## Prompt Template

When creating the cron job prompt, include:

1. **Seed topic pool** — cycle through: AI/ML, open source, security, science, programming, hardware, crypto/blockchain, bio/health, space, physics, math, robotics, legal, finance, energy, climate, philosophy, history, geopolitics, music/art, gaming, education, startups, infrastructure, systems design.

2. **Wave 1** — `mcp__pulse__pulse_research(topic, depth='deep', max_wurm_rounds=4, max_fetches_per_round=500, n=20, lookback_days=90)` on 2-3 topics.

3. **Dig deeper** — For each result: `mcp__pulse__pulse_dig(topic, seed_report=..., max_rounds=3, max_fetches=500)`.

4. **Extract new topics** — From dig output, find at least 5 new topics/entities.

5. **Wave 2** — pulse_research on new topics discovered.

6. **Persistence** — Store discovered topics in `~/.hermes/pulse-wurm-next-topics.json` so next tick continues where last left off.

7. **Report** — TOP-10 most interesting findings + list of 10+ new topics for next tick.


## Pitfalls (quick list)

- Pulse_research rate limits: 3 concurrent running tasks max (for this user)
- Delivery set to 'origin' sends to the creating conversation — change to 'all' for fan-out
- MCP tools MUST be available — don't restrict `enabled_toolsets` or pulse tools won't load
- Deep research (`depth='deep'`) runs take 30-120 minutes to complete (longer with llm_filter=true). Cron jobs should use `pulse_research_start` + poll pattern, NOT direct blocking calls.
- Quick research (`depth='quick'`) with `max_fetches_per_round=200, max_wurm_rounds=2` completes in under 2 minutes - use this for reliable cron tick updates.
- MCP timeout (120s) affects all pulse tools. For cron jobs, use direct curl to http://localhost:8770/search with depth='quick' for reliable <60s results.
- MCP server unreachable backoff: After 3 consecutive failures, pulse MCP enters ~43-60s auto-retry period. Wait this duration before retrying. Verified via: tool returns "auto-retry available in ~43s" message.
- pulse_research_start also subject to MCP timeout - when in backoff, fall back to `depth='quick'` searches and separate dig operations, then resume normal flow once recovered.
- **LLM filter over-aggressiveness:** Even with `llm_filter=true`, jobs may keep only 2-6 of 60+ initial candidates. This is expected filtering for relevance, but may indicate need for broader topic queries to get more diverse results.
- **Async job timing:** Even `depth='quick'` jobs can run 300+ seconds with multiple phases (search→dig-1→dig-2→llm-filter). Poll status every 60s for long-running jobs.
- **pulse_dig timeout risk in cron:** The `mcp__pulse__pulse_dig` tool has 120s hard timeout. During MCP backoff/cooldown periods, skip dig calls entirely - let the wurm rounds in pulse_research handle the deep crawling. The research jobs' built-in dig phases are more reliable than manual dig calls when server is under load. See `references/cron-timeout-20260613-worm.md` for proven hybrid strategy using pulse_search + pulse_lineage instead.
- **pulse_dig seed_report format trap (2026-06-17 23:30):** Wrong nesting causes `400 EMPTY_SEED — seed_report.candidates is empty`. The `candidates` array must contain FLAT objects `{"title": "...", "url": "..."}` — NOT wrapped in an extra `{"item": {...}}` layer, NOT wrapped in any other envelope. Correct shape:

**Full catalogue:** 73 pitfalls in
`references/pitfalls-full.md` — load with
`skill_view(file_path='references/pitfalls-full.md')`.

## Hybrid GitHub-Script + MCP-Pulse_Search Pattern

The `pulse_tick.py` script (GitHub-API-only) and direct `mcp__pulse__pulse_search` (broad 22-source fan-out) return **strictly non-overlapping result sets**:

| Source | URL types returned | Strength |
|---|---|---|
| `pulse_tick.py` (GitHub API) | github.com repos only | High-recall for new repos, no rate limit cost |
| `mcp__pulse__pulse_search` | reddit, arxiv, RSS (openai.com, blog.pragmaticengineer.com, etc.), lobsters, hackernews, bluesky, dev.to | Catches discussion threads and analysis that GitHub-only misses |

**Verified 08:45 tick:** 10 GitHub + 5 MCP = 15 unique discoveries, zero overlap. The 4-thread "AI coding dev-vs-prod gap" cluster (vibecoding-db-deletion + $4000-spent + Amazon-blames + productivity-data) was entirely from MCP and would have been completely missed by the GitHub-only script.

**Execution order in cron tick:**
1. Run `pulse_tick.py` to get state, update `visited_urls` with GitHub discoveries
2. Call `mcp__pulse__pulse_search` on the 1-2 highest-yield `next_seeds` with `depth='default'`, `llm_filter=true`, `llm_filter_top_n=30`
3. Parse persisted output (or in-band JSON) with `scripts/parse_pulse_search.py`
4. Filter `ranked_candidates` against `visited_urls` from state
5. Save the 3-5 highest-quality novel URLs to mazemaker (use `LR*0.7 + FS*5` quality metric)
6. Update state file: append new URLs to `visited_urls`, bump saturation scores for productive seeds
7. Generate the discoveries JSON + tick report markdown

The hybrid pattern is the default — don't run the script alone unless the cron budget is constrained.

## Async Job Timing Patterns (Observed)

**Timing data from live execution (June 2026):**
- `pulse_research_start(depth='deep')`: 460-480 seconds total, 2 dig rounds + llm-filter
- Even `depth='quick'` with llm_filter=True can hit MCP timeout (multiple phases run sequentially)
- Status phases: search-start → search (40 candidates) → dig-1 (72-79 new) → dig-2 (44-67 more) → llm-filter (keeps ~6-63)
- Growth pattern: ~180% → ~60-93% → llm-filter reduction (keeps high-relevance subset)
- Heartbeat age >60s indicates stuck job - may need fresh start

**Reliable Cron Tick Pattern:**
```
# Start 2-3 deep async jobs
pulse_research_start(topic, depth='deep', lookback_days=45, max_fetches=200, max_wurm_rounds=2)

# While jobs run, immediately get quick results
pulse_search(topic, llm_filter_top_n=20, lookback_days=60, max_per_round=30)

# Poll async status periodically (every 60s)
pulse_research_status(job_id)

# On timeout: continue with other work, jobs persist in background
pulse_research_result(job_id)  # Get results when ready
```

## Topic Cycling Strategy

The discovery pipeline naturally surfaces tangential topics. For controlled research:

1. Read `~/.hermes/pulse-wurm-next-topics.json` for previously discovered topics
2. Select 2-3 varied domains from the list (cycle through: physics, AI, security, legal, finance, infrastructure)
3. Prefer topics with specific technical details (model names, CVE references, paper titles) over general concepts
4. If list exhausted, cycle through: AI/ML, open source, security, science, programming, hardware, crypto/blockchain, bio/health, space, physics, math, robotics, legal, finance, energy, climate, philosophy, history, geopolitics, music/art, gaming, education, startups, infrastructure, systems design

**Topic selection heuristic (from session observations):**
- Pick topics spanning different domains for each tick (e.g., one AI/agents, one security, one science)
- Prioritize topics that explicitly name entities (specific malware, court cases, research papers, stock tickers)
- Choose topics with recent engagement signals (>100 score counts indicate active discussion)
- **ArXiv category targeting:** Query topics with `cs.CL` (reasoning), `quant-ph` (quantum theory), `cs.RO` (robotics), or `cs.CR` (cybersecurity) for domain-specific papers
- **Source-specific focus:** Add `source=<platform>` to topic queries to prioritize specific communities (Reddit cybersecurity, Lobsters law tag, RSS OpenAI)


## Verification

Full verification procedure moved to
`references/verification.md` — load with
`skill_view(file_path='references/verification.md')`.

## LLM Filter Yield Guidance (June 2026)
- Deep jobs with `llm_filter=true`: expect 1-12% retention of initial candidates
- Very low yield (<1%) may indicate topic is too narrow or novelty expired
- Topics with higher yield typically have broader academic/Reddit coverage
- When yield is low, either broaden the topic query or accept that the research space is mature/niche

### Pulse-Wurm 2.0 Implementation Verified (2026-06-17)

**Actual working implementation from this tick:**

```python

## Operational code

State-file schema and URL-extraction helpers moved to
`references/operational-code.md` — load with
`skill_view(file_path='references/operational-code.md')`.
