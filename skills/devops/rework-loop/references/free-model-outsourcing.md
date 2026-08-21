# Free-Model Outsourcing for Perpetual Loops

**Captured 2026-08-03** — Pattern for running ALL loop components (workers + judge) on $0/free models.

## Operator requirement

"NO PAID MODEL FFS" — every component must be $0. The judge being on the main paid model while
workers are free is unacceptable. ALL loop processes (worker spawns AND judge spawns) must carry
`-m MODEL` pointing to a free model.

## Implementation

### 1. Define the free-model pool + judge model

```bash
# In loop-supervisor.sh, after WORKTREE_BASE:
FREE_MODELS=(
  "inclusionai/ling-3.0-flash:free"
  "poolside/laguna-s-2.1:free"
  "poolside/laguna-xs-2.1:free"
  "stepfun/step-3.7-flash:free"
  "tencent/hy3:free"
)
JUDGE_MODEL="nvidia/nemotron-3-ultra-550b-a55b:free"

pick_worker_model() {
  local round=$1 wid=$2
  local idx=$(( ((round - 1) * WORKERS + wid - 1) % ${#FREE_MODELS[@]} ))
  echo "${FREE_MODELS[$idx]}"
}
```

### 2. Worker start — round-robin across pool

```bash
WORKER_MODEL="$(pick_worker_model "$round" "$wid")"
log "  worker $wid [$branch] focus: ... | model: $WORKER_MODEL"
( cd "$wt" && "$HERMES" -z "$prompt" -m "$WORKER_MODEL" --cli ) >> "$OUT_LOG" 2>&1 &
```

Different workers in the same round get different models. A rate-limit on one model
only blocks 1 of 3 workers, not all.

### 3. Judge start — biggest free model

```bash
"$HERMES" -z "$(cat "$JUDGE_PROMPT")" -m "$JUDGE_MODEL" --cli >> "$OUT_LOG" 2>&1
```

Both the regular judge (every N rounds) AND the forced judge (queue exhausted) must
carry `-m "$JUDGE_MODEL"`.

### 4. Model ID format

OpenRouter free models use the format `provider/model-name:free` WITHOUT the `openrouter/`
prefix. Examples:
- `inclusionai/ling-3.0-flash:free` ✓
- `openrouter/inclusionai/ling-3.0-flash:free` ✗ (HTTP 400: not a valid model ID)

## Rate-limit behavior

When the OpenRouter free-tier daily limit is exhausted:
- HTTP 429: "Rate limit exceeded: free-models-per-day-high-balance"
- `hermes -z` returns **exit=0** with the error as text output (no actual LLM response)
- Supervisor treats exit=0 as success → queue stays empty → forced judge loops infinitely

**Circuit breaker pattern**: track consecutive judge failures (exit=0 but verdict file
unchanged). After N consecutive failures (e.g. 3), pause with long backoff (30min+).
Log: "CONSECUTIVE JUDGE FAILURES — likely rate-limited, pausing".

## Available free models (as of 2026-08-03)

From the operator's Nous Portal / OpenRouter:

| Model | ID | Notes |
|-------|-----|-------|
| Ling 3.0 Flash | `inclusionai/ling-3.0-flash:free` | Good general worker |
| Poolside Laguna S 2.1 | `poolside/laguna-s-2.1:free` | Strong coder |
| Poolside Laguna XS 2.1 | `poolside/laguna-xs-2.1:free` | Fast, lighter |
| StepFun Step 3.7 Flash | `stepfun/step-3.7-flash:free` | Good reasoning |
| Tencent Hy3 | `tencent/hy3:free` | General purpose |
| Nemotron 3 Ultra 550B | `nvidia/nemotron-3-ultra-550b-a55b:free` | Best reasoning (judge) |
| Gemma 4 26B | `google/gemma-4-26b-a4b-it:free` | Alternative judge |

**Removed / rate-limited**: `moonshotai/kimi-k2.6:free` (no longer on free tier).

## Pitfalls

- **OpenRouter prefix**: Do NOT prepend `openrouter/` to the model ID. Hermes resolves
  the provider from the config; the `-m` flag takes the bare model ID.
- **exit=0 on 429**: Hermes does NOT return a non-zero exit code on API errors. The error
  message is printed to stdout but the process exits 0. This is a trap for any supervisor
  that only checks exit codes.
- **Daily limit shared across models**: The "free-models-per-day-high-balance" rate limit
  appears to be account-wide, not per-model. When one free model hits 429, ALL free models
  on the same account are likely also rate-limited. Round-robin helps with per-model limits
  but NOT with the daily cap.
