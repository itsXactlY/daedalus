# Tri-State Cadence Loop — Deployment Reference (June 14, 2026)

Initial deployment: June 13, 2026. **Updated June 14, 2026** after quota crisis and model hygiene fixes.
**Updated June 15, 2026** to add ACT phase recovery patterns.

## Key Post-Deployment Changes (June 14)

| Issue | Resolution | Memory |
|-------|------------|--------|
| **Quota exhaustion** — 15-min crons burned free tier in hours | All 15-min schedules pulled to **6-hour staggered** (4×/day per cron) | 708330 |
| **Dead model** — `moonshotai/kimi-k2.6:free` removed from OpenRouter free tier | 3 affected crons remapped; **dual OpenRouter keys** (custom + fallback) for load balancing | 708328 |
| **Pulse-Wurm 2.0 verified** — 15 URLs visited, 1 discovery seeded in first ticks | Stateful loop operational, rotating seeds on saturation | 708329 |

## Key Changes Verified (June 15)

| Item | Status | Verification Method |
|------|--------|-------------------|
| **Bridge bind fix** | Already complete | `ssid0tlnp` showed `0.0.0.0:8769` listening |
| **pulse-wurm-everything decommission** | Already complete | `jobs.json` shows `enabled: false` + paused_reason |
| **Prompt injection defense skill** | Already created | File exists at `~/.hermes/skills/red-teaming/prompt-injection-defense/SKILL.md` |

## All 9 Cron Jobs — CURRENT STATE

### Tri-State Cadence (4 jobs)

| Phase | Job ID | Model | Schedule | OpenRouter Key | Label pattern |
|-------|--------|-------|----------|---------------|---------------|
| DISCOVER | acc219417ec5 | poolside/laguna-xs.2:free | `0 */6 * * *` (every 6h, :00) | openrouter_fallback | `discovery:pulse-tick-<date>-<hash>` |
| DECIDE | 08ad815ec546 | **nvidia/nemotron-3-ultra-550b-a55b:free** | `0 * * * *` (hourly) | openrouter_fallback | `decision:rank-<date>-<priority>` |
| ACT | db0f8da579d9 | poolside/laguna-m.1:free | `0 6 * * *` (daily 6AM) | openrouter_custom | `ops:tick-<date>-<action_type>` |
| MEASURE | 03b3a562bd59 | nvidia/nemotron-3-ultra-550b-a55b:free | `0 0 * * 0` (weekly Sunday midnight) | openrouter_custom | `signal:convergence-YYYY-Www` |

### Graph-Native Loops (5 jobs)

| Loop | Job ID | Model | Schedule | OpenRouter Key | Label pattern |
|------|--------|-------|----------|---------------|---------------|
| Pulse-Wurm 2.0 | f908a03e5655 | poolside/laguna-xs.2:free | `15 */6 * * *` (every 6h, :15) | openrouter_custom | `discovery:pulse-wurm-<date>-<hash>` |
| Skill Rot Detector | 355891ce87eb | nvidia/nemotron-3-ultra-550b-a55b:free | `0 3 * * 1` (weekly Monday 3AM) | openrouter_custom | `signal:skill-drift-*` / `ops:skill-check-*` |
| Failure Pattern Hardener | d11f140dd420 | **nousresearch/hermes-3-llama-3.1-405b:free** | `0 2 * * 1` (weekly Monday 2AM) | openrouter_fallback | `ops:guard-created-<pattern>` |
| Intent Debt Auditor | 5e0fd603dd9d | openai/gpt-oss-120b:free | `0 4 * * 1` (weekly Monday 4AM) | openrouter_fallback | `signal:intent-drift-<week>` |
| Oracle Loop | 9b9f8205ca8b | **nvidia/nemotron-3-ultra-550b-a55b:free** | `0 5 * * *` (daily 5AM) | openrouter_custom | `signal:oracle-cluster-*` / `signal:oracle-summary-*` |

## OpenRouter Key Assignment (Dual-Key Load Balancing)

| Key | ID Suffix | Crons Assigned | Models Used |
|-----|-----------|----------------|-------------|
| `openrouter_custom` | ...03cb | ACT, MEASURE, Pulse-Wurm 2.0, Skill Rot, Oracle | laguna-m.1, nemotron-3-ultra, laguna-xs.2 |
| `openrouter_fallback` | ...8b5c | DISCOVER, DECIDE, Failure Hardener, Intent Debt | laguna-xs.2, nemotron-3-ultra, hermes-3-405b, gpt-oss-120b |

## Verified Free Models (as of June 14, 2026)

- `poolside/laguna-m.1:free` — coding ✅
- `poolside/laguna-xs.2:free` — fast, cheap ✅
- `nvidia/nemotron-3-ultra-550b-a55b:free` — 1M ctx, 550B ✅
- `nvidia/nemotron-3-super-120b-a12b:free` — 1M ctx, 120B ✅
- `nousresearch/hermes-3-llama-3.1-405b:free` — 405B ✅
- `openai/gpt-oss-120b:free` — 120B MoE ✅
- `qwen/qwen3-coder:free` — 1M ctx, 480B MoE (new discovery) ✅

**Removed:** `moonshotai/kimi-k2.6:free` — no longer on free tier (base model is paid)

## Scripts directory: `~/.hermes/loops/`

```
~/.hermes/loops/
├── shared/loop_utils.sh                    # Shared bash utils
├── tri-state/
│   ├── discover_seed.py                    # DISCOVER phase seed generator
│   ├── decide_rank.py                      # DECIDE phase ranking seed
│   ├── act_implement.py                    # ACT phase implementation seed
│   └── measure_converge.py                 # MEASURE phase convergence seed
├── skill-rot/
│   └── audit_skills.py                     # Weekly skill audit
├── failure-hardener/
│   ├── audit_failures.py                   # Weekly failure classifier
│   └── guards_created.json                 # Dedup registry (auto-managed)
├── pulse-wurm2/
│   ├── pulse_tick.py                       # Stateful pulse tick
│   └── pulse_state.json                    # Tick state (auto-managed)
├── intent-debt/
│   ├── audit_debt.py                       # Weekly debt auditor
│   └── drift_history.json                  # Time series (auto-managed)
└── oracle/
    ├── oracle_reading.py                   # Daily oracle reader
    └── oracle_history.json                 # Cluster history (auto-managed)
```

## Architecture Notes

- Each script writes structured JSON to its phase directory. The cron agent reads this JSON, follows the instructions, and uses MCP tools (mazemaker, pulse) to execute.
- No flat file coordination between phases. Each phase writes to mazemaker with a distinct label prefix. Other phases read via `mazemaker_recall(prefix:*)`.
- **Recovery pattern when mazemaker is unavailable:** See `references/act-phase-recovery.md` for alternative verification methods using session_search, cron/jobs.json, and local tool checks (systemctl, ss, file checks).
- Saturation detection: the MEASURE phase computes `unique_discoveries / total_discoveries`. Below 0.4 = saturated (reduce discovery cadence). Above 0.6 = diverging (maintain or increase).
- State files (pulse_state.json, guards_created.json, drift_history.json, oracle_history.json) persist between cron ticks so stateful logic works across restarts.