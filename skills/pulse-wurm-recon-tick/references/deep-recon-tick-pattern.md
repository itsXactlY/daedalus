# Deep Recon Tick — Second-Variant Pulse-Wurm Cron Pattern

This documents a **second variant** of the pulse-wurm cron job that operates alongside the first variant (see `cron-tick-playbook.md` in `pulse-wurm-everything/references/`). Where the first variant uses `pulse_state.json` with the script-driven rotation, this variant uses `~/.hermes/pulse-wurm-next-topics.json` as a hand-managed carry-over file with a **PHASE A (continue on carry-over) + PHASE B (fresh-direction pick) dual-mandate** structure.

## When to use this variant

- The first variant's rotation pool (`MCP security best practices`, `LLM agent sandboxing`, `AI model watermarking`, `Autonomous agent red teaming`, `Secure AI code generation`) is exhausted or yields 0.
- The operator wants explicit control over what's carried forward between ticks (vs the first variant's script-driven rotation).
- The cron prompt explicitly mandates a fresh-direction dig every tick (regardless of carry-over yield).

## State file

`~/.hermes/pulse-wurm-next-topics.json` — schema:

```json
{
  "tick_timestamp": "<ISO8601Z>",
  "tick_status": "<narrative summary of this tick's findings + decisions>",
  "in_flight_deep_jobs": {"<job_id>": "<status — DONE / STUCK / etc>"},
  "completed_jobs_this_tick": {"<job_id>": "<summary>"},
  "quick_search_recovery_findings": {
    "<topic_key>": {
      "kept_ratio": "<N/M substantive (PCT%)>",
      "key_findings": ["<url/title>"],
      "interpretation": "<operator reasoning>"
    }
  },
  "discovered_topics_for_next_tick": [
    "<topic>", "<topic>", ...
  ],
  "next_topics_priority": [
    "PHASE A: <topic>",
    "PHASE A: <topic>",
    "PHASE B fresh-direction N: <topic>",
    ...
  ],
  "operational_notes": ["<tick-level lesson>", ...],
  "domain_coverage_24_pool": {
    "<domain>": "<coverage status>"
  },
  "next_tick_fresh_direction_picker": {
    "rule": "<picker logic>",
    "eligible_after_<prior_tick>": ["<domain>", ...],
    "alphabetic_winner": "<domain>",
    "next_tick_fresh_pick_recommendation": "<concrete seed suggestion>",
    "concrete_alternative_seeds": ["<seed>", ...]
  }
}
```

The `discovered_topics_for_next_tick` list is the PHASE A input for the next tick. The `next_topics_priority` array is the operator-curated queue. The `domain_coverage_24_pool` tracks which of the 24 domains have been touched in the last 7 days (used for the fresh-direction picker).

## PHASE A — Continue on carry-over

1. **READ FIRST**: `~/.hermes/pulse-wurm-next-topics.json` → take entries from `discovered_topics_for_next_tick` and `next_topics_priority`.
2. **Pick 1-3 carry-over topics** (the top entries from `next_topics_priority`).
3. **Run `mcp__pulse__pulse_search` for each topic** in parallel:
   - `topic=<topic>`
   - `depth="default"` (not `"deep"` — see Polymarket anti-pattern below)
   - `lookback_days=90`
   - `llm_filter=true` (the strict LLM filter drops noise)
   - `llm_filter_top_n=25` (filter the top 25 candidates)
4. **Skip `pulse_research depth="deep"` and `pulse_dig`** for topics likely to surface Polymarket prediction-market content (Anthropic warning cluster, recursive self-improvement, AI-research-automation prediction markets, etc.) — see Polymarket anti-pattern below.

## PHASE B — Fresh-direction pick

1. **Read domain_coverage_24_pool** → pick the lowest-coverage domain NOT already in `next_topics_priority` top 5 AND NOT just covered this tick.
2. **If tie**: pick alphabetically-first under-represented domain.
3. **Generate the fresh seed**: `<picked_domain> frontier research 2026` is the default template, but **for non-AI/ML domains and low-corpora-coverage domains (startups, history, philosophy, education, music-art, gaming), use a CONCRETE ENTITY ANCHOR instead** — see "Entity-Anchor Seed Pattern" below.
4. **Run `mcp__pulse__pulse_search`** with the same parameters as PHASE A.
5. **Don't derive the fresh seed from existing mazemaker facts/decisions/discoveries** — fresh means fresh.

## Polymarket Locale-Fanout Anti-Pattern (3-tick confirmed reproduction)

**Symptom**: `mcp__pulse__pulse_research(depth="deep", topic=<X>)` for topics touching prediction markets, AI company warnings, or AI capabilities forecasting returns a final candidate pool where 80-100% of substantive items are `polymarket.com` event pages in various locales (Polymarket, Polymarket.it, Polymarket.fr, Polymarket.br, etc.). The "wurm" recursive dig amplifies this — each round of `pulse_dig` follows Polymarket locale variants deeper into the graph, exhausting the fetch budget on prediction-market content.

**Reproduction history**:
- 2026-06-20: PHASE A carry-over Anthropic warning cluster — 26/242 kept, 100% Polymarket (CONFIRMED 1st time).
- 2026-06-20: PHASE B wave-2 OpenAI NVIDIA 10GW — 100% Polymarket (DeepSeek banned chips variants, 2nd reproduction).
- 2026-06-20: PHASE B wave-2 Jack Clark Nobel Prize — 100% Polymarket (Nobel Peace Prize variants, 3rd reproduction).

**Fix (recommended)**: For PHASE A carry-over topics, **default to `pulse_search(llm_filter=true, depth="default")` as the primary tool**. Reserve `pulse_research(depth="deep")` for topics confirmed to lack Polymarket candidates in the seed graph (the 22-source fan-out will surface any Polymarket content within the first 5-10 candidates if it's there). For everything else, pulse_search alone has produced 3-8 saves per tick when productive.

**Detection signal for "topic will locale-fanout"**:
- Seed text contains "Polymarket" explicitly
- Seed text references a company with active prediction markets (Anthropic, OpenAI, Tesla, NVIDIA)
- Seed text references a regulatory or business event (Nobel, Fable restoration, social network launch, infrastructure project)
- Seed text references an AI capabilities prediction (recursive self-improvement, AGI timeline, 30%/60% automation forecast)

**Don't**: Call `pulse_research(depth="deep")` on these topics and hope for the best. Three consecutive reproductions establish this as a structural anti-pattern, not a transient one.

## 45-Minute Stuck-Job Threshold

**Rule**: If an in-flight `pulse_research` or `pulse_dig` job has heartbeat > 45 minutes (heartbeat_age_seconds > 2700) for **2 consecutive ticks**, kill the job and remove from `in_flight_deep_jobs`.

**Why 45 minutes**: Pulse_research depth="deep" is documented as 30-120 minutes wall-clock. 45 minutes is the lower bound of the upper half — past this, the job is either stuck or has expanded beyond the dig's design envelope. 2 consecutive ticks of stuck = structural issue, not transient.

**Confirmation procedure**:
1. At tick start, read `in_flight_deep_jobs` from the carry-over file.
2. For each in-flight job, call `mcp__pulse__pulse_research_status(job_id=...)` to check heartbeat.
3. If heartbeat_age_seconds > 2700, the job is over the 45-min threshold.
4. Check the `tick_status` field for prior-tick mention. If the job was already noted as STUCK in the prior tick, **kill it** (mark for removal in the next `in_flight_deep_jobs` write, do not call `mcp__pulse__pulse_research_result`).
5. If this is the first tick the job appeared stuck, leave it and re-check next tick.

**Real case (2026-06-21)**: Hardware frontier deep job `de7e9fd4fab5` stuck at dig-1 with heartbeat 1700s+ (28+ min) at first tick. By the second tick, heartbeat was unchanged (job never advanced), confirming structural stuck. **Recommended kill on third tick.**

## Entity-Anchor Seed Pattern (extends Fresh-Direction Seed Template Failure Mode)

The "Fresh-Direction Seed Template Failure Mode" section in `cron-tick-playbook.md` documents that `<domain> frontier research 2026` returns 0 for non-AI/ML domains. It proposes a mitigation hierarchy: drop "frontier" → drop "2026" → use concrete sub-topic from recent cluster.

**This third mitigation conflicts with the fresh-direction picker rule** that says "DO NOT derive the seed from any existing mazemaker fact/decision/discovery — fresh means fresh." When the picker generates a fresh-direction for a low-corpora-coverage domain like startups, history, philosophy, or music-art, there's no useful sub-topic to derive from existing discoveries.

**Resolution: Entity-Anchor Seed Pattern (Level 4 mitigation)**. For low-corpora-coverage domains, use a concrete **entity anchor** — a specific person, company, or event name from public knowledge that's well-known enough to have substantial 2026 coverage but isn't derived from existing mazemaker facts. Examples:

| Domain | Bad seed (template) | Good seed (entity-anchored) |
|---|---|---|
| startups | "startups frontier research 2026" | "Mira Murati Thinking Machines 2026" or "Ilya Sutskever Safe Superintelligence SSI 2026" or "Anthropic safety researcher departure startup 2026" |
| history | "history frontier research 2026" | "AI historian synthesis ancient text 2026" or "DeepMind Isi Gellért medieval manuscript 2026" |
| philosophy | "philosophy frontier research 2026" | "Dawkins AI consciousness 2026" or "Gary Marcus LLM understanding 2026" |
| music-art | "music-art frontier research 2026" | "Suno Udio AI music copyright lawsuit 2026" or "Lightricks LTX-2 audio-video foundation model 2026" |
| education | "education frontier research 2026" | "Khan Academy GPT-4 classroom pilot 2026" or "ChatGPT Futures Class of 2026" |

**What makes a good entity anchor**:
- The person/company/event is a known public figure with documented 2026 activity.
- The seed is specific enough that pulse_search will surface actual content, not 22-source noise.
- The entity is NOT a derivation from existing mazemaker facts (e.g. "Mira Murati Thinking Machines" is a well-known public fact, not something found in a prior mazemaker discovery).
- The entity is recent enough (2024-2026) to have substantial current coverage.

**Detection signal for "domain needs entity anchor"**:
- Domain has 0-1 prior discoveries in mazemaker for the last 7 days.
- The default `<domain> frontier research 2026` template has been tried and returned 0 (kept_ratio ≤ 5%).
- The domain keywords don't naturally intersect with AI/ML research terminology.

**Don't**: Use entity-anchored seeds for AI/ML, security, programming, infrastructure — those domains work fine with the template or sub-topic derivation patterns. The entity-anchor pattern is specifically for **low-corpora-coverage** domains.

## Pulse_Search vs Pulse_Research Tool Tier (4-tick confirmation)

| Tool | Speed | Use when |
|---|---|---|
| `mcp__pulse__pulse_search(depth="default", llm_filter=true)` | 5-30s | **DEFAULT for all PHASE A carry-over work**. Fastest, safest, avoids Polymarket locale-fanout. |
| `mcp__pulse__pulse_search(depth="quick")` | 5-15s | When budget is tight (e.g. 60s remaining in cron window). Less depth but same 22-source fan-out. |
| `mcp__pulse__pulse_research(depth="default")` | 60-180s (often times out at 120s) | When topic is confirmed to lack Polymarket candidates AND you have 3+ minutes of cron budget remaining. |
| `mcp__pulse__pulse_research(depth="deep")` | 30-120 min (sync call killed at 120s) | **NEVER in cron ticks** — use `mcp__pulse__pulse_research_start` for async. Confirmed 3x produces Polymarket locale-fanout. |
| `mcp__pulse__pulse_dig(seed_report=...)` | 10-30s per round | Only for productive dig seeds (GitHub repos, blog posts, OpenAI engineering posts). Arxiv `/abs/` and `/pdf/` URLs are unproductive dig targets. |

## Tick Workflow (deep-recon-tick variant)

1. **Read carry-over file**: `~/.hermes/pulse-wurm-next-topics.json` → extract `discovered_topics_for_next_tick`, `next_topics_priority`, `domain_coverage_24_pool`, `in_flight_deep_jobs`.
2. **Check in-flight jobs**: For each entry in `in_flight_deep_jobs`, call `mcp__pulse__pulse_research_status(job_id)`. Apply the 45-min stuck-job rule. Either kill (mark for removal) or leave for next tick.
3. **PHASE A**: Pick 1-3 topics from `next_topics_priority` (PHASE A entries). Run `mcp__pulse__pulse_search` in parallel (default depth, llm_filter=true, lookback_days=90, llm_filter_top_n=25).
4. **PHASE B**: Pick fresh-direction from lowest-coverage eligible domain per picker rule. Use entity-anchor pattern if the picked domain is low-corpora-coverage. Run `mcp__pulse__pulse_search` with the same parameters.
5. **Synthesize**: From each search result, extract substantive findings (filter out noise — Polymarket locale-fanout, NBA/wedding drama, "Tied Monoids" arxiv noise, etc.).
6. **Save to mazemaker**: For each genuinely novel finding, call `mcp__mazemaker__mazemaker_remember` with a curated label (e.g. `fact:<topic>`, `decision:<area>`, `discovery:pulse-wurm-YYYYMMDD_<8char-hash>`).
7. **Write carry-over file**: Update `~/.hermes/pulse-wurm-next-topics.json` with this tick's findings, new `discovered_topics_for_next_tick`, updated `next_topics_priority`, updated `domain_coverage_24_pool`, and operational notes.
8. **Deliver report**: Final response is auto-delivered to the cron destination. Format with PHASE A / PHASE B sections, TOP-10 entries, new topics list, operational notes.

## Don't do (cross-cutting)

- **Don't call `pulse_research(depth="deep")` synchronously** in a cron tick — use `pulse_research_start` for async, or stay with `pulse_search`.
- **Don't trust pulse_search for "startups" / low-corpora-coverage domains without an entity-anchor seed** — the template seeds return 0 noise.
- **Don't re-implement the carry-over file** as a one-off — the schema is stable and other cron consumers may read it.
- **Don't skip PHASE A because PHASE B was productive** — the operator mandates BOTH every tick.
- **Don't skip PHASE B because PHASE A was productive** — same reason.
- **Don't mark a stuck job as "still running" without checking heartbeat** — the in-flight status may show 0 progress for hours.
- **Don't write the carry-over file before saving to mazemaker** — if mazemaker fails, the carry-over is the durable backup.
