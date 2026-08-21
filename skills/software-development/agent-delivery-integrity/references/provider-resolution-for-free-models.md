# Provider Resolution for Free Models — Nous Portal + OpenRouter

## The Problem

Hermes agent has free model providers (Nous Portal, OpenRouter Free) but the CLI invocation format differs from what you'd expect. Getting the format wrong means 401/429 errors that look like auth failures but are actually format errors.

## Nous Portal Free Models

**Correct invocation:**
```bash
hermes -z "prompt" -m "tencent/hy3:free" --provider nous --cli
```

**Wrong (gives 401 "Model not supported"):**
```bash
hermes -z "prompt" -m "nous/tencent/hy3:free" --cli
```

**Why:** Nous is a custom provider. When `-m` contains `nous/`, Hermes tries to find `nous` in its built-in registry. Must use `--provider nous` flag explicitly.

**Config:**
```yaml
providers:
  nous:
    base_url: https://inference-api.nousresearch.com/v1
    type: custom
```

**Auth:** OAuth token in auth.json credential_pool. Has `expires_at` — if 401 "No payment method", token may be stale.

**Known free models:**
- `tencent/hy3:free` — 262,144 context, verified working
- `inclusionai/ling-3.0-flash:free`
- `poolside/laguna-s-2.1:free`
- `poolside/laguna-xs-2.1:free`
- `stepfun/step-3.7-flash:free`

## OpenRouter Free Models

Same split pattern needed:
```bash
hermes -z "prompt" -m "inclusionai/ling-3.0-flash:free" --provider openrouter_free --cli
```

**Rate limit:** `free-models-per-day-high-balance` (429 when exhausted). Nous Portal uses a DIFFERENT bucket — rotate when OpenRouter hits 429.

## Supervisor/Cron Pattern

For scripts orchestrating multiple free models, use `provider:model` format:

```bash
FREE_MODELS=("nous:tencent/hy3:free" "openrouter_free:inclusionai/ling-3.0-flash:free")

split_model() {
  WM_PROVIDER="${1%%:*}"
  WM_MODEL="${1#*:}"
}

WORKER_MODEL="nous:tencent/hy3:free"
split_model "$WORKER_MODEL"
hermes -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli
```

## Pitfalls

| # | Pitfall | Fix |
|---|---------|-----|
| 1 | `nous/model` format gives 401 | Split into `-m model --provider nous` |
| 2 | 401 "No payment method" on opencode-zen | Not a free provider; needs credits |
| 3 | 429 "free-models-per-day" on OpenRouter | Rotate to Nous Portal (different bucket) |
| 4 | Nous OAuth token expires | Refresh via `hermes auth` |
| 5 | Judge on paid model in loop | Ensure judge also uses `--provider nous --m model` |
| 6 | `openrouter_free/model` prefix doesn't work | Same split: `--provider openrouter_free --m model` |
| 7 | Supervisor uses old branch name | Hardcode `main` not `visual/cockpit-demo` in worktree commands |
