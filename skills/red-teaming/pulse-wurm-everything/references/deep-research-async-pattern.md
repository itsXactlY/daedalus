# Pulse Research Deep Dive — Async Multi-Job Pattern

Companion to `cron-tick-playbook.md`. The playbook covers the **6-hourly `pulse_tick.py` cron** (uses `pulse_search` quick mode + GitHub script). This document covers the **operator-explicit deep-research mode** — when the operator (or a dedicated deep-research cron) asks for `pulse_research(depth='deep')` + `pulse_dig` by name. Both modes use the same MCP pod, but the async multi-job orchestration is different enough to warrant a separate reference.

## When to Use This Pattern

The operator's prompt explicitly named `pulse_research` with `depth='deep'` and asked for `pulse_dig` calls. Do NOT substitute `pulse_search` quick mode as a "faster alternative" — they're different tools with different output semantics:
- `pulse_search` quick: ~5-30s, returns 30-60 ranked candidates, 22 sources, no recursive dig.
- `pulse_research` deep: 15-30 min, returns 6-55 candidates after recursive dig-1..4 + llm-filter, follows URLs INSIDE each result.

The operator asked for deep. Honor the latency budget. Use this pattern.

## Confirmed Working Setup (2026-06-20 tick — 3 jobs, all completed)

```python
# Launch 3-4 deep research jobs in parallel
import mcp_pulse

job_ids = []
for topic in [
    "<productive seed from prior tick's discovered_topics>",
    "<adjacent topic that re-uses saturation knowledge>",
    "<fresh angle — pick from discovered_topics or rotation pool>",
]:
    result = mcp_pulse.pulse_research_start(
        depth="deep",
        topic=topic,
        lookback_days=90,
        max_wurm_rounds=4,
        max_fetches_per_round=500,
        n=20,
        llm_filter=True,
    )
    job_ids.append(result["body"]["job_id"])
```

Each completed in 912s / 1125s / 984s respectively — all under 20 minutes wall-clock.

## Polling Cadence (3-5 minute interval)

| Elapsed | Phase Expected | Status Notes |
|---|---|---|
| 0-3 min | `search` (60 candidates collected) | Normal |
| 3-9 min | `dig-1` → `dig-2` → `dig-3` | Each adds 7-89 new candidates, growth_pct 80-130%. Productive. |
| 9-15 min | `dig-4` (often plateaus at 0-40 new candidates) | About to enter llm-filter |
| 15-20 min | `llm-filter` (drops 117-286, keeps 6-55) | Job transitions to `done` |

If state remains `done`, call `pulse_research_result(job_id=<id>)` to fetch the candidate pool.

If state remains `running` past 20 min, keep polling. Past 30 min, treat as stuck (see below).

## Stuck Threshold — Declare Stuck at heartbeat_age_seconds > 2700 (45 min)

**Confirmed 2026-06-20**: Job 1 (slop-backlash topic) was stuck in `search` phase with 60 candidates for 43+ minutes, heartbeat 2572s, state still `"running"` but no phase progression.

Root cause: the 22-source parallel search can deadlock on a single bad source (or one that takes unusually long to return, blocking the whole phase). The MCP pod keeps the state alive but no phase transitions happen.

**Action when stuck**:
1. Stop polling the stuck job. Don't keep retrying — the result will never come.
2. Do NOT bump the seed's saturation for a stuck run (it didn't actually produce).
3. Note in tick report: "job_id=X stuck in search phase at N min; topic needs narrower query."
4. Workaround for next tick: split the topic into narrower single-entity queries. Instead of one big "AI slop backlash 2026 cluster" job, run separate jobs per entity ("Bethesda DLSS5 walkback 2026", "Rob Pike email AI slop 2026", "slop PR retaliation blog 2026"). Smaller searches are less likely to deadlock.

**Don't**: kill the job, restart with the same query, or wait past 60 min. The MCP pod doesn't expose a kill endpoint for `pulse_research_start` jobs. They will sit in the pod forever; the next tick should just ignore them.

## JSON Shape for `pulse_research_result` (DIFFERENT from `pulse_search`)

The existing `scripts/parse_pulse_search.py` helper is for `pulse_search` output (`{"ranked_candidates": [...]}` under `body`). The `pulse_research` endpoint has a different shape — do NOT reuse the helper.

```python
# CORRECT unwrap for pulse_research_result (used after job.state == "done"):
import json

raw = open('/tmp/hermes-results/call_<hash>.txt').read()
outer = json.loads(raw)              # outer wrapper
inner = json.loads(outer["result"])   # FIRST unwrap (stringified JSON)
body = inner["body"]                  # API response body (dict, not string)
result = body["result"]               # SECOND unwrap — different from pulse_search!
candidates = result["candidates"]     # NOTE: "candidates" not "ranked_candidates"
history = result["history"]           # phase-by-phase log

# Each candidate: {
#   candidate_id, item_id, source, title, url, snippet,
#   final_score, local_relevance, engagement, cluster_id,
#   source_items: [...], metadata: {...}
# }
```

Compare with `pulse_search`:
```python
# WRONG (pulse_search shape, won't work for pulse_research):
body = json.loads(outer["result"])["body"]
cands = body["ranked_candidates"]  # KEY ERROR — pulse_research uses "candidates"
```

## `pulse_dig` Synchronous Calls Time Out at 120s

**Confirmed unworkable for deep mode** (2026-06-20):
- `pulse_dig(topic, seed_report={...}, max_fetches=300, max_per_round=40, max_rounds=2)` returned `MCP call timed out after 120.0s`.
- The async equivalent doesn't exist — `pulse_dig` is sync-only.
- Workaround: skip standalone `pulse_dig` and rely on `pulse_research_start` which already runs dig rounds internally. The `dig-1` through `dig-4` phases ARE pulse_dig-equivalent calls, but they're orchestrated by the pod and don't hit the MCP-client 120s timeout.
- Reserve `pulse_dig` only for tiny quick-mode scans where 120s is enough (i.e. the cron-tick workflow in `cron-tick-playbook.md`).

## Handoff File Pattern — `~/.hermes/pulse-wurm-next-topics.json`

For one-off deep-research cron ticks that don't follow the standard 6h `pulse_tick.py` cadence, write a standalone handoff file at the end of the tick. Distinct from the cron state file at `~/.hermes/loops/pulse-wurm2/pulse_state.json`.

**Schema** (observed 2026-06-20):
```json
{
  "timestamp": "<ISO 8601 UTC>",
  "pulse_mcp_status": "<free-text summary of tool health this tick>",
  "topics_searched": [
    "<topic with depth + lookback params>",
    "..."
  ],
  "jobs": {
    "<job_id>": {
      "state": "done|running-stuck",
      "elapsed_s": 912.3,
      "phases": ["search", "dig-1", "dig-2", "dig-3", "dig-4", "llm-filter"],
      "candidates_aggregated": 292,
      "kept": 6
    }
  },
  "findings_saved_ids": [824766, 824767, 824768, ...],
  "findings_summary": [
    "id 824766: signal:manus-no-function-calling-2026 — MorroHsu post: ...",
    "..."
  ],
  "unprocessed_signals": [
    "<high-value findings not saved because already covered by prior tick>"
  ],
  "dig_calls": [
    {"attempted": "...", "result": "MCP 120s timeout — synchronous dig calls fail"}
  ],
  "discovered_topics": [
    "<fresh angles for next tick — minimum 10>",
    "..."
  ],
  "saturation_notes": {
    "<topic>": "<productive|saturated|adjacent — verdict>"
  },
  "tool_health": {
    "pulse_research_start": "OK",
    "pulse_dig": "TIMEOUT at 120s",
    "mazemaker_remember": "OK"
  }
}
```

**Next-tick agent behavior**:
1. At tick start, `cat ~/.hermes/pulse-wurm-next-topics.json` (if exists).
2. Read `discovered_topics` — these are the candidate seeds for THIS tick.
3. Read `saturation_notes` — skip topics marked `saturated`. Focus on `productive` + `adjacent`.
4. Pick 2-3 topics, run the multi-job pattern above, fetch results, save new findings.
5. Write the file back at tick end with the new tick's discoveries.

**Don't**: re-pick topics marked saturated in the previous tick's notes without a fresh angle. The notes are there for a reason.

## Save Pattern for Deep-Research Findings

Use `mazemaker_remember` with curated labels matching the cluster type:
- `signal:<topic>-YYYY` — first-occurrence evidence (Reddit testimonial, vendor walkback, etc.)
- `discovery:<project-name>` — new open-source project / GitHub repo discovered
- `fact:<topic>` — durable factual claim (semantic cache = 80% cost reduction, etc.)

**Multiple saves per tick is expected** — 6 saves is normal for a productive deep-research tick. The 6-save batch from 2026-06-20 covered Manus no-function-calling, semantic cache 80% cost cut, MTP 2.5x inference, little-coder harness, local-LLM skeptic Reddit thread, vllm-blackwell-guide.

**Body 60-300 words**: lead with WHAT IS TRUE, then WHY IT MATTERS, then HOW TO ACT.

## Worked Example — 2026-06-20 Deep-Research Tick

3 jobs launched in parallel at tick start:
1. `AI slop backlash 2026 cross-vendor cluster Bethesda DLSS5 walkback Rob Pike retaliation blog` — **STUCK** at 43min in search phase (heartbeat 2572s, state still running). Reported as stuck, topic needs narrower query next tick.
2. `OpenLumara esobold KoboldCPP fork local AI agent framework token-efficient modular 2026` — DONE in 912s. 292 candidates aggregated, 6 kept. Top hit was OpenLumara Reddit post (378 upvotes) — but already saved as id 824713 in prior tick. New adjacent finding: MorroHsu "I stopped using function calling entirely" (Manus backend lead, 424 comments) → saved as `signal:manus-no-function-calling-2026` (id 824766).
3. `LLM prompt caching inference optimization cost reduction 2026 Mastering Inference Caching` — DONE in 1125s. 274 candidates, 20 kept. Top hits: semantic-cache 80% cost cut (1317 engagement), Qwen 3.6 MTP 2.5x inference, GPTCache, omlx, little-coder. → saved 4 memories (824767-824770).
4. `semantic cache LLM cost reduction GPTCache little-coder small model harness 2026` — DONE in 984s. 128 candidates, 11 kept. Top hits: "I'm done with local LLMs for coding" (854 comments), vllm-blackwell-guide, caliber-ai-org/ai-setup, vllm v0.20.0. → saved 2 more memories (824781-824782).

**Total**: 4 jobs, 3 completed (avg 17 min), 1 stuck (43 min). 6 memories saved. Handoff file written.

**Discoveries** → 16 new topics for next tick (in `discovered_topics` of the handoff file).

## When NOT to Use This Pattern

- The operator's cron is the standard 6h `pulse_tick.py` rhythm — use the cron-tick playbook instead.
- The operator wants quick triage of one topic — use `pulse_search(depth='quick')` directly (~30s).
- The operator asks for a one-off `pulse_research` call (single topic, single job) — the pattern above still applies (async start + poll + fetch), just with 1 job instead of 3-4.
- The MCP pod is unreachable (`pulse_health` returning error) — wait 60-90s for recovery, then check `pulse_license` before launching.

## See Also

- `cron-tick-playbook.md` — the 6h `pulse_tick.py` workflow (complementary; same MCP pod, different orchestration)
- `templates/tick_report.md` — format for the per-tick summary report
- `scripts/parse_pulse_search.py` — helper for `pulse_search` output (NOT applicable to `pulse_research` — different JSON shape, see above)
