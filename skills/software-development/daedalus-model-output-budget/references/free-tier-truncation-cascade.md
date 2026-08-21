# Free-Tier Model Truncation Cascade

## What happens

When a free-tier model (e.g. `ling-3.0-flash:free`) runs with `reasoning_effort: xhigh` and is asked to synthesize a large mazemaker-recall result (10+ entries) into a response that includes tool calls:

1. Model exhausts its output token budget during the reasoning pass.
2. It truncates mid-stream inside the tool-call JSON formatting.
3. Daedalus detects malformed `arguments` JSON in the tool call.
4. Daedalus retries up to 4 times — the model keeps producing the same truncation because the budget hasn't changed.
5. Daedalus refuses: "Truncated tool call response detected again — refusing to execute incomplete tool arguments."

## Reproduction

```
session: your session id
model: inclusionai/ling-3.0-flash:free
reasoning_effort: xhigh
query: mazemaker_recall with broad query returning 10+ entries
```

Observed at:
- session `022308` (2026-07-29): "what was my last question stored in mazemaker?" → cascade
- session `031121` (2026-07-29): same meta-recursive query → cascade

## Fix

1. Lower `reasoning_effort` to `low` or `medium` in `~/.daedalus/config.yaml`.
2. Use targeted mazemaker queries instead of broad "show everything" searches.
3. For heavy recall work, switch to a model with higher output limits.

## Related

- `daedalus-model-output-budget` skill: full coverage of this pitfall.
- `daedalus-core-capabilities`: umbrella that covers model configuration; this reference supplements it.