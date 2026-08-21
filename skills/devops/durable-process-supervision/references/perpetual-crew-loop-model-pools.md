# Multi-Provider Model Pool for Perpetual Crew Loops

## Pattern: Combined Free Provider Pool

When running a perpetual crew loop (systemd user service), use multiple free
provider pools to maximize uptime and minimize cost:

```bash
# Two separate daily limits = more total capacity
FREE_MODELS=(
  # Nous Portal Free (separate bucket from OpenRouter)
  "nous:tencent/hy3:free"
  "nous:inclusionai/ling-3.0-flash:free"
  "nous:poolside/laguna-s-2.1:free"
  "nous:poolside/laguna-xs-2.1:free"
  "nous:stepfun/step-3.7-flash:free"
  # OpenRouter Free (separate bucket)
  "openrouter_free:inclusionai/ling-3.0-flash:free"
  "openrouter_free:cohere/north-mini-code:free"
  "openrouter_free:openai/gpt-oss-20b:free"
  "openrouter_free:google/gemma-4-26b-a4b-it:free"
  "openrouter_free:poolside/laguna-xs-2.1:free"
)

# Judge uses strongest free model (not round-robin)
JUDGE_MODEL="nous:tencent/hy3:free"
```

## The `--provider` Flag is REQUIRED

`hermes -m "provider/model"` does NOT reliably route. Use explicit `--provider`:

```bash
# WRONG — uses config.yaml default provider
hermes -z "prompt" -m "nous/tencent/hy3:free" --cli

# CORRECT
hermes -z "prompt" -m "tencent/hy3:free" --provider nous --cli
```

## `split_model()` Bash Helper

```bash
split_model() {
  WM_PROVIDER="${1%%:*}"   # everything before first colon
  WM_MODEL="${1#*:}"       # everything after first colon
}

# Usage:
WORKER_MODEL="nous:tencent/hy3:free"
split_model "$WORKER_MODEL"
hermes -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli
```

## Pitfalls

1. **`--provider` flag required for ALL hermes calls** — not just workers, but judge too
2. **Nous Portal OAuth tokens** come from auth.json credential_pool (not api_key in config)
3. **OpenRouter Free daily limit** = `429 "free-models-per-day-high-balance"`. Switch to Nous pool.
4. **Changing `model.provider` in config.yaml** affects ALL `hermes -z` calls globally
5. **Judge model must be in FREE_MODELS or use explicit `--provider`** — otherwise uses config default
