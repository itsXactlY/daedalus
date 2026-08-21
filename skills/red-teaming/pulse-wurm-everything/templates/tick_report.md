# Pulse-Wurm 2.0 Tick Report Template

Filename: `pulse_wurm_tick_YYYYMMDD_HHMM.md`
Path: `~/.hermes/loops/pulse-wurm2/`

Write one per tick (cron-scheduled or manual). Use this template to keep reports
consistent and grep-able across the 6-hour tick series. Sections marked optional
can be omitted for 0-novel or low-context ticks.

---

```markdown
# Pulse-Wurm 2.0 Tick Report — {YYYY-MM-DD HH:MM} UTC

**Tick time**: {ISO timestamp}
**State before**: consecutive_empty={N}, last_tick={ISO}
**State after**: consecutive_empty={N}, visited_urls={count}, next_seeds rotated {yes/no}

## Script (`pulse_tick.py`) output

{N} seeds processed via GitHub channel, **{K} novel findings** {expected false-zero for academic seeds per playbook | confirmed via MCP channel below}.

| Seed | Saturation before | Novel |
|---|---|---|
| {seed name} | {sat} | {novel count} |
| ... | ... | ... |

Script bumped consecutive_empty: {N} → {N}.

## MCP channel (`pulse_search depth='quick' lookback_days=14`)

{All | M of N} seeds queried in parallel. **{K} novel findings** — {all candidates already in visited_urls | M productive candidates | pure noise}.

### Seed {N} — {seed name short label} ({cluster status: productive | exhausted | mixed | noise})
| Paper | Status |
|---|---|
| arxiv {id} "{title}" | {VISITED — saved tick HH:MM | NOVEL — saved id {N} | cluster bloat} |

{Repeat for each seed with productive candidates.}

## Decision rationale

- **{No mazemaker saves | N saves}** — {rationale: all candidates already saved earlier tick HH:MM | all candidates new cluster | cluster bloat discipline applied | etc.}
- **consecutive_empty {stays at N | reset to 0}** — {rationale: script increment confirmed by MCP | any novel found}
- **Saturation bumped** on {N} processed seeds to break re-pick loop (per playbook workaround): {old sats} → {new sats}. The next-lowest unsaturated pool is at sat {N}, so sat {N+2} puts the processed seeds below.
- **Pulse dig** {skipped — known intermittent EMPTY_SEED blocker | attempted — {result} | not applicable}
- **Noise URLs**: {N} added to visited ({source breakdown: Ti metallurgy/Tied Links arxiv cluster, Reddit drama, etc.}); {M} already present from prior ticks.

## State changes summary

- `last_tick`: → {ISO}
- `consecutive_empty`: {N} ({change vs script output})
- `next_seeds` rotated {to 5 lowest-saturation pool | unchanged}: {seed list}
- `saturation_scores`:
  - {seed}: {old} → {new} ({bumped | bumped by len(novel) | unchanged})
- `visited_urls`: {count} ({+/-N})
- `discovery_topics`: {count} entries ({+/-1} narrative appended)
- `pulse_dig`: {skipped | attempted}

## Observations

1. {Pattern observed — e.g., "channel-mismatch false zero confirmed: script's GitHub channel returned 0 for all 3 academic seeds (expected per playbook), and the MCP channel also genuinely returned 0 — the seeds are FULLY saturated, not channel-limited."}
2. {Second pattern — e.g., "Cluster exhaustion: Both productive clusters (X, Y) were fully mined by earlier ticks today (HH:MM and HH:MM). The 6-hour cadence has caught up with yesterday's discoveries."}
3. {Third pattern — e.g., "next_seeds pool drained: All 5 lowest-saturation seeds are at exactly sat 2 (previously mined to that level). After this tick's bump, the next tick will retry these 5, and at least some should yield new findings via fresh angles."}

## Predictions for next tick

- {Most likely outcome — e.g., "Most likely 0-novel outcome: sat-2 seeds return cluster-bloat only."}
- {Possible novel — e.g., "Possible novel: if the sat-2 seeds can be reformulated with concrete technology names (per playbook's 'concrete reformulation' recommendation), each could surface 1-3 genuinely fresh papers."}
- {Risk — e.g., "If all 5 sat-2 seeds return 0: consecutive_empty → 2 (next tick triggers rotation if also 0)."}
```

---

## Companion: discoveries JSON snapshot

Filename: `discoveries_YYYYMMDD_HHMM_pulse-wurm.json`
Path: `~/.hermes/loops/pulse-wurm2/`

A machine-readable companion to the markdown report. Useful for grep/parse
across the series and for downstream automation.

```json
{
  "tick_time": "2026-06-20T08:11:00+00:00",
  "script_novel": 0,
  "mcp_novel": 0,
  "mazemaker_saves": [],
  "processed_seeds": [
    {"name": "seed 1", "sat_before": 0, "sat_after": 4, "novel": 0, "note": "4 papers all visited, saved earlier tick 05:51"},
    {"name": "seed 2", "sat_before": 1, "sat_after": 4, "novel": 0, "note": "pure noise — Ti metallurgy, Tied Links, Reddit off-topic"},
    {"name": "seed 3", "sat_before": 1.3, "sat_after": 4, "novel": 0, "note": "6 papers all visited (RecurGuard + 5 cluster companions)"}
  ],
  "consecutive_empty_before": 0,
  "consecutive_empty_after": 1,
  "noise_urls_added": 0,
  "noise_urls_already_visited": 9
}
```
