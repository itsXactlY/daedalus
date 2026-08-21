# Tick 41 — 2026-06-23T04:30Z — sync-scout-after-deep-breakthrough technique validated (Mythos → Fable 5 + US export controls pivot)

## CRITICAL: Sync-scout-after-deep-breakthrough technique (NEW — promoted from pattern to mandatory step)

**The pattern**: when a deep `pulse_research` job surfaces a major NEW entity (a model name, an organization, a paper), immediately follow up with a fast `pulse_search` (sync, default depth) on that specific entity. The sync search runs in 1-2 seconds, costs almost nothing, and bypasses the deep-job locale-clone filter on polymarket to find second-order stories.

**Tick 41 validation (2026-06-23 ~04:30Z)**: deep Mythos job returned 24/76 kept; the top new finding was "Introducing Claude Fable 5" (r/ClaudeAI 1u1b22l, 2026-06-09, 792 comments, u/ClaudeOfficial). The follow-up sync scout on "Claude Fable 5 Mythos-class model..." (9/39 kept) returned 7 SECOND-ORDER stories that the deep job's locale-clone filter completely missed:

1. **"It's over. Claude Fable 5 one-shots horror game live"** (r/singularity 1u1h7de, 579 comments) — capability demo
2. **Statement on the US government directive to suspend access to Fable 5 and Mythos 5** (simonwillison.net 2026-06-13) — **the export-control story**
3. **The Fable 5 Export Controls Harm US Cyber Defense** (simonwillison.net 2026-06-16) — Kate Moussouris on "jailbreak"
4. **"'Wake-up call': Europe reacts to Anthropic halting access to its Fable 5 and Mythos 5 AI models"** (r/europe 1u5l5t9, 507 comments) — geopolitical split
5. **"Any USA citizen wanna marry me? I'm tryna access Fable 5"** (r/ClaudeAI 1u4tjef, 429 comments) — geo-restriction breaking workflows
6. **"'They screwed us': Personality clashes sent Anthropic's models offline"** (simonwillison.net 2026-06-15) — Axios piece on internal conflict
7. **Claude-powered AI coding agent deletes entire company database in 9 seconds — backups zapped** (r/pcmasterrace 1sxla79) — alignment-failure with $$$ damage

**The discovery arc this tick**:
- Tick 40 carry-over: "Claude Mythos Polymarket RESOLVED at $880K vol" (Polymarket-only signal)
- Tick 41 deep job: confirmed Polymarket data + found Fable 5 announcement (r/ClaudeAI)
- **Tick 41 sync scout**: pivoted the story from "Polymarket resolution" to **"US export controls on Fable 5 AND Mythos 5 + EU crisis + Cursor/Claude-agent database deletion + internal Anthropic politics"** — a 10x bigger story than the deep job found

**Recipe** (add to any tick that surfaces a major new entity):
```python
# After pulse_research_result returns and you identify a major NEW entity
mcp__pulse__pulse_search(
    topic=f"{entity_name} {entity_class} {specific_angle} 2026",
    depth="default",
    llm_filter=true,
    llm_filter_top_n=40,
    lookback_days=60
)
# ~1-2 seconds, 9-15 substantive results typically
```

**Key parameters that work**:
- `depth="default"` (NOT deep — costs 1-2s vs 18 min)
- `llm_filter=true` (cuts the noise)
- `llm_filter_top_n=40` (default)
- `lookback_days=60` (60-90 day window catches the rollout arc)
- Topic phrasing: `{entity_name} {entity_class} {specific_claim} {date_or_year}`

**When NOT to use**: if the deep job's top finding is just a high-engagement post (not a new entity), skip the sync scout — the post itself is the signal.

**Mandatory tick-step upgrade**: every tick's deep job should be followed by AT LEAST one sync scout on the top new entity found. This is a class-level mandatory addition, not optional.

## pulse_research_result JSON TRIPLE-NESTING gotcha (TOOL — most agents hit this)

**The trap**: `mcp__pulse__pulse_research_result` returns a result that is **triple-nested JSON**. The path is:

```python
import json
outer = json.loads(raw)                  # {"result": "<json string>"}
body = json.loads(outer['result'])       # {"status": 200, "body": {...}}
result = body['body']['result']          # THE ACTUAL CANDIDATES
# NOT body['result'] — KeyError!
```

For `pulse_search` (sync) the same triple-nesting applies: `body['body']['ranked_candidates']`.

**Why it bites**: the `mcp` tool wrapper shows the result as a string (first level), the JSON inside it has `status: 200, body: {...}` (second level), and the actual payload is in `body['result']` / `body['ranked_candidates']` (third level). Most agents try `body['result']` first and get KeyError.

**Fix**: when parsing large `pulse_research_result` or `pulse_search` outputs:
1. ALWAYS start from `outer['result']` (string)
2. `json.loads(...)` once to get `body`
3. Read from `body['body']['result']` (deep) or `body['body']['ranked_candidates']` (sync) — NOT `body['result']`

**Tick 41 cost**: 4-5 minutes lost to "KeyError: 'result'" debugging before finding the right path. Encode this once in the skill and never waste time on it again.

**Note**: large results (>100KB) are saved to `/tmp/hermes-results/call_<id>.txt` as single-line JSON. Use `execute_code` to parse them, NOT `read_file` (single-line file can't be paginated).

## Story-SHIFT detection on carry-over topics (NEW META-PATTERN)

**The pattern**: a priority-1 carry-over topic can SHIFT semantic frame between ticks without the topic string changing. The agent must detect the shift and pivot the search angle.

**Tick 41 example**:
- Tick 40 carry-over: "Claude Mythos Polymarket RESOLVED $880K vol" (story: prediction-market resolution)
- Tick 41 evidence: Claude Fable 5 was released on June 9 (story: model release); then June 13 US export controls suspended access to BOTH Fable 5 AND Mythos 5 (story: AI export controls + geopolitics)
- **The story SHIFTED**: from "did the Polymarket resolve" to "what was actually released, by whom, and why is the US government now restricting it"
- **The pivot**: instead of re-running the same Mythos/Polymarket query, drill on Fable 5 specifics, BIS notification text, EU response, Anthropic compliance mechanics

**Detection heuristic** (use in next tick when reviewing carry-over topics):
1. Read the prior tick's "key_findings" / "discovery" string for the carry-over topic
2. Compare to the new evidence surfaced this tick
3. If the new evidence contains a NEW ENTITY (model name, organization, law, paper) that wasn't in the prior tick's findings, the story has SHIFTED
4. Pivot the next tick's search to the new entity, not the carry-over string

**Apply this in the carry-over file**: when writing the next tick's `discovered_topics_for_next_tick`, the priority-1 entries should reference the NEW entity, not the original carry-over string. Example: instead of "Claude Mythos Polymarket RESOLVED", write "Claude Fable 5 vs Mythos 5 — US export controls June 13 2026, EU access halt".

## Open-source fresh-direction pick VALIDATED (tick 40 PITFALL recommendation confirmed)

**Tick 40 hypothesis**: open-source is a high-yield fresh-direction pick after climate/energy/gaming exhausted (1/240, 10/89, 11/71 keep rates).

**Tick 41 result (open-source deep job `d4b74cfb0c1d`)**:
- 36 candidates kept / 114 total aggregated (32% keep rate — by far the best of any tested domain)
- Total runtime 864s (14.4 min — fastest of the 3 deep jobs, 2 min ahead of Mythos/Opus jobs)
- dig-1 found 54 new candidates (+90% growth — strongest single dig round of any job)
- **Top signal**: Polymarket "What day will OpenAI next release a new frontier model?" at $9,297,494 vol — LARGEST single financial signal of the tick
- **Open-source model releases surfaced**: Gemma 4 (26B MoE + 31B dense), Qwen3.6-35B-A3B (Apache 2.0 MoE 35B/3B), Qwen 3.6 27B MTP (2.5x faster, 262k context fits 48GB), LFM2.5-8B-A1B (40 tok/s CPU-only from LiquidAI)
- **Human-interest story**: 19yo Abhinav Anand from Bihar solo-built 5.82B multimodal at 93.45 OmniDocBench (no team/investors/CS degree, $11,560 personal savings)
- **AI coding agent ecosystem**: smallcode (4B model at 87% benchmark), Swival (CLI coding agent), CodeGraphContext (MCP server), budget-aware-mcp

**Update to fresh-pick strategy**:
- **Skip list (confirmed thin)**: climate, energy, gaming (3 failures)
- **High-yield list (confirmed rich)**: open-source, AI/ML (always — dominantly covered), finance (tick 42 pulse-wurm2 found 3 finance URLs)
- **Untried alphabetical after this tick**: hardware, programming, philosophy, music-art, science, infrastructure, space, physics, math, legal
- **Alphabetically-first eligible fresh pick for tick 42 pulse-wurm cron**: **hardware** (or **programming** if hardware already covered)
- **Suggested hardware seed**: `"hardware frontier research 2026 NVIDIA Blackwell B200 GB300 AMD MI400 Apple M5 Qualcomm AI 100 rack-scale AI datacenter power"`
- **Hot signal seed alternative**: `"geopolitics frontier research 2026 US AI export controls Anthropic Mythos Fable 5 EU access sovereign AI national security"` (this tick's export-control story warrants a dedicated geopolitics deep dive)

## Three parallel deep jobs handled cleanly (operational confirmation)

Tick 41 ran 3 deep jobs in parallel via `mcp__pulse__pulse_research_start` (async):
- Mythos Polymarket: 1310s, 24/76 kept
- Opus 4.8 / Sonnet 4.7 / loophole: 1310s, 9/130 kept (heavy filter)
- Open-source frontier: 864s, 36/114 kept

**No MCP server overload** — pod handled 3 simultaneous deep jobs without timeout or crash. The 1080-1310s runtime suggests the MCP client wrapper is killing the sync call at ~1080s (deep job times out) but the result is preserved. The async pattern (`pulse_research_start` + poll + `pulse_research_result`) works.

**Pattern**: always use `pulse_research_start` for depth="deep" (not the sync `pulse_research` which gets killed at ~120s for deep). The 3-job-parallel pattern is the right tick budget.

## Open-source domain coverage for the 24-domain pool

After this tick, open-source is now a CONFIRMED-VIABLE fresh-direction pick. Update the picker state:
- **CONFIRMED VIABLE**: open-source (this tick), AI/ML (always), finance (tick 42 pulse-wurm2)
- **CONFIRMED THIN/EXHAUSTED**: climate, energy, gaming (tick 40), infrastructure (tick 40 0037 reference), education (tick 36), history (exhausted per tick 15a)
- **UNTESTED**: hardware, programming, philosophy, music-art, science, space, physics, math, legal
- **ALPHABETICALLY-FIRST UNTRIED FRESH PICK**: hardware (or programming, depending on operator choice)
- **OPERATIONAL PITFALL** (tick 40 0037 reference): don't try `infrastructure-systems-design` as a fresh pick — script literal stub drift bug
