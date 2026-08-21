# State File Type Drift — `discovery_topics` Mixed-Type Crash

**Date discovered**: 2026-06-20 ~08:30 UTC tick

## Symptom

`python3 ~/.hermes/loops/pulse-wurm2/pulse_tick.py` exits with:

```
AttributeError: 'dict' object has no attribute 'lower'
  File ".../pulse_tick.py", line 53, in process_seed
    is_dup = any(seed.lower() in title.lower() or seed.lower() in desc.lower()
             for _ in [1] if seed.lower() in [t.lower() for t in discovery_topics[-50:]])
```

## Root Cause

A prior tick's state-update code wrote a `dict` (not a `str`) to `state['discovery_topics']`. The list, which is supposed to be `list[str]`, now contains mixed types like:

```python
{"ts": "2026-06-20T07:37:09.146259", "topic": "reasoning-token consumption attacks / LLM DoS",
 "url": "https://arxiv.org/pdf/2606.07968", "mazemaker_id": 824637, "source_seed": "...",
 "relevance": "high"}
```

The script's `[t.lower() for t in discovery_topics[-50:]]` crashes on the first dict entry.

## Why the dict got there (suspected)

A prior cron agent passed a structured dict (treating `discovery_topics` as a structured log) instead of a string narrative. The dict holds more info (ts, mazemaker_id, url, relevance) than a string, so it looked useful at write-time — but the script never expected it.

## Defensive Recovery Pattern

Apply at the start of any tick, before invoking the script:

```python
import json
with open('/home/hermes/loops/pulse-wurm2/pulse_state.json') as f:
    state = json.load(f)
# Filter out any non-string entries — they crash the script's .lower() calls
bad = [i for i, t in enumerate(state.get('discovery_topics', [])) if not isinstance(t, str)]
if bad:
    print(f"WARNING: {len(bad)} non-string entries in discovery_topics, filtering")
    state['discovery_topics'] = [t for t in state['discovery_topics'] if isinstance(t, str)]
    with open('/home/hermes/loops/pulse-wurm2/pulse_state.json', 'w') as f:
        json.dump(state, f, indent=2)
```

## Fix the script for good

One-line patch in `pulse_tick.py:53`:

```python
# Before:
is_dup = any(seed.lower() in title.lower() or seed.lower() in desc.lower()
             for _ in [1] if seed.lower() in [t.lower() for t in discovery_topics[-50:]])
# After:
is_dup = any(seed.lower() in title.lower() or seed.lower() in desc.lower()
             for _ in [1] if seed.lower() in [str(t).lower() for t in discovery_topics[-50:] if isinstance(t, str)])
```

Apply the same `isinstance(t, str)` filter defensively to **every** loop over `discovery_topics` in the script. Line 123 (`[d["title"] for d in all_discoveries]`) is fine because `all_discoveries` is the script's own list, but a future contributor adding more `discovery_topics` writers should use `str(t)` defensively.

## Don'ts

**Don't** re-parse the dict entry back into a string and re-append it. The data inside (ts, mazemaker_id, url, relevance) is preserved in the tick reports and mazemaker itself — losing it is fine. The crash is the cost; the data isn't worth keeping in this format.

**Don't** refactor `discovery_topics` to be a list of dicts instead of strings. The script, the playbook, and 12+ prior tick reports all assume `list[str]`. The mixed-type situation is one-off pollution, not a signal to redesign.

## Defensive lesson for all cron agents

When writing to a `list[str]` field that's accumulated over many ticks by many agents, always append `str(value)` not `value`. Even if your value IS a string today, the next contributor might pass a dict thinking "this holds more useful info" — and that breaks every reader downstream. `str(dict_entry)` produces an ugly repr but never crashes.

This generalizes beyond Pulse-Wurm: any append-only state file with a `list[str]` field is fragile to the same drift pattern. The fix is `str(value)` at every write site.
