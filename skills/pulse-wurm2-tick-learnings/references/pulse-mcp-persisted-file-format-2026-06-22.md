# Pulse-MCP Persisted File Format Reference (2026-06-22)

## Context: format mismatch between in-memory and persisted file

During tick 33 (2026-06-22T21:31Z) the agent attempted to read
`/tmp/hermes-results/pulse_search_*.json` to confirm `_filter_stats.kept` values
that had been reported in the directly-returned MCP response. The persisted
files showed DIFFERENT values (e.g. Mistral Large 3 reported `kept=0/15` in
the MCP context but `kept=5/15` in the persisted file with the closest
timestamp). The root cause: **the persisted files are not necessarily
the in-memory MCP returns for the most recent call — they may be leftover
outputs from a prior tick still on disk**.

## On-disk format vs operational-reference description

The operational reference (`pulse-wurm2-stateful-tick/references/operational-reference.md`)
describes the persisted format as:

```python
{"result": "<STRINGIFIED JSON>"}              # outer wrapper
  → {"status": 200, "body": {...}}             # middle layer
    → {"topic": "...", "ranked_candidates": [...], ...}
```

**This is the in-memory / in-context format. The on-disk /tmp/hermes-results/
file format is DIFFERENT.** The on-disk format observed at tick 33:

```json
{
  "ok": true,
  "elapsed": 1.234,
  "data": "{\"ok\": true, \"elapsed\": ..., \"topic\": \"...\", \"items_by_source\": {...}, \"_filter_stats\": {...}}",
  "topic": "..."
}
```

Two-key observations:
1. The on-disk file has a top-level `data` field that is a STRINGIFIED JSON.
2. The stringified JSON inside `data` does NOT have a `body` wrapper — it has
   `topic`, `items_by_source`, `_filter_stats` etc. directly at the top level.

## Correct on-disk parser

```python
import json
import os

# Find the most recent N files by mtime
files = sorted([f for f in os.listdir('/tmp/hermes-results/')
                if f.startswith('pulse_search_')],
               key=lambda f: os.path.getmtime(f'/tmp/hermes-results/{f}'))
newest = files[-3:]

for fname in newest:
    path = f'/tmp/hermes-results/{fname}'
    with open(path) as f:
        d = json.load(f)
    # d has 'ok', 'elapsed', 'data' (stringified JSON), 'topic'
    data = d.get('data', {})
    if isinstance(data, str):
        data = json.loads(data)
    # data has 'topic', 'items_by_source', '_filter_stats' at top level
    stats = data.get('_filter_stats', {})
    tickertick = data.get('items_by_source', {}).get('tickertick', [])
```

## CRITICAL: persist file staleness warning

The mtime of the persisted file is not always the time of the MCP call that
produced the values in your context. At tick 33, the persisted file mtime
for "Mistral Large 3" was 23:20 local (1h49min AFTER the tick's 21:31Z
execution). The contents in that file corresponded to a prior tick (likely
tick 27 at 21:30Z).

**Rule:** treat persisted `/tmp/hermes-results/pulse_search_*.json` files as
**HINTS about what the MCP might return**, not as authoritative copies of
your current call's response. The directly-returned MCP value in your
context is the source of truth.

If you need to read a persisted file to confirm a value, **verify the file
mtime is within ±2 minutes of your current call timestamp** before trusting
its contents. Stale files (>5 min old) are likely from a prior tick.

## Implication for cross-tick noise-cluster analysis

The 26 noise URLs added to `visited_urls` at tick 33 were sourced from the
DIRECTLY-RETURNED MCP values in context, not from the persisted files. This
was the right call — the persisted files would have given slightly different
noise URLs from the prior tick, leading to `visited_urls` divergence from
the actual MCP call results.

## State file timestamp anomaly (2026-06-22T21:31Z tick)

Pre-tick `state['last_tick']` was `2026-06-22T23:17:10.155874` — 1h46min in
the FUTURE of the actual tick execution time. The corresponding tick report
file `pulse_wurm_tick_20260622_2317.md` does exist in the directory, so
the timestamp is not fabricated, but it appears to be a clock-drift artifact
in the prior tick that wrote to state.

**Rule:** when reading pre-tick `last_tick`, do not trust it as a "time
since last tick" metric. Use the tick report filenames
(`pulse_wurm_tick_YYYYMMDD_HHMM.md`) for actual tick-time archaeology.
Always overwrite `state['last_tick']` with the current tick's `TICK_TS_ISO`
captured at the start of the tick per §21 single-datetime discipline.
