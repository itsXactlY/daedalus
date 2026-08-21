# Multi-Provider Model Routing for Loops -- Pitfalls (2026-08-03)

Learned from configuring a perpetual crew loop to use free/$0 models across multiple
providers (OpenRouter, opencode-zen, Nous Portal).

## Provider registration required

A provider MUST be in config.yaml under providers: for `hermes -m provider/model` to work.
Credential pool entries in auth.json alone are NOT sufficient.

## ENV variables not exported in systemd sessions

~/.hermes/.env variables are NOT automatically exported in systemd user service sessions.
When a provider api_key is `env:VAR_NAME`, the variable must be set in the service
environment OR the key written directly in config.yaml.

Fix: Either Environment=VAR_NAME=sk-... in the systemd unit, or write the key directly.

## Model ID format varies by provider

| Provider | Format | Example |
|----------|--------|---------|
| OpenRouter free | model/name:free | inclusionai/ling-3.0-flash:free |
| OpenRouter paid | model/name | deepseek/deepseek-v4-flash-latest |
| opencode-zen | bare name | deepseek-v4-flash |
| Nous Portal | varies | check portal UI |

Critical: OpenRouter IDs do NOT use openrouter/ prefix when provider is registered
as openrouter_free. Using openrouter/model/name causes HTTP 400.

## THE `-m provider/model` 401 TRAP (session-blocking, 2026-08-03)

`hermes -z "x" -m "tencent/hy3:free"` → `HTTP 401: Model hy3:free is not supported`.
`hermes -z "x" -m "nous/tencent/hy3:free"` → `HTTP 401: Model tencent/hy3:free is not supported`.
Both FAIL. The `-m` flag does NOT auto-select the provider — it picks the DEFAULT provider
(whatever `model.provider` is in config.yaml) and passes the whole string as the model name.

**The ONLY working invocation:** split provider and model into separate flags:
```
hermes -z "x" -m "tencent/hy3:free" --provider nous --cli
hermes -z "x" -m "inclusionai/ling-3.0-flash:free" --provider nous --cli
hermes -z "x" -m "inclusionai/ling-3.0-flash:free" --provider openrouter_free --cli
```
(Verified 2026-08-03: `tencent/hy3:free --provider nous` returns real output, 262k context.)

**Supervisor pattern that works:** store models as `provider:model` (colon-separated), then:
```bash
split_model() { WM_PROVIDER="${1%%:*}"; WM_MODEL="${1#*:}"; }
# worker launch:
split_model "$WORKER_MODEL"
( cd "$wt" && "$HERMES" -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli ) >> "$OUT_LOG" 2>&1 &
# judge launch:
split_model "$JUDGE_MODEL"
"$HERMES" -z "$(cat "$JUDGE_PROMPT")" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli >> "$OUT_LOG" 2>&1
```
Test every model string BEFORE deploying the loop:
```
for spec in "nous tencent/hy3:free" "nous inclusionai/ling-3.0-flash:free" "openrouter_free inclusionai/ling-3.0-flash:free"; do
  set -- $spec; /home/alca/.local/bin/hermes -z "Say: ok" -m "$2" --provider "$1" --cli 2>&1 | tail -1
done
```
If you see 401/400, the provider or model name is wrong — fix before trusting the loop.

## Nous Portal working free models (2026-08-03, verified)

`tencent/hy3:free` (via `--provider nous`) is the operator's confirmed daily-driver free model
(262,144-token context). Also available on Nous Portal free tier (same `--provider nous` pattern):
`inclusionai/ling-3.0-flash:free`, `poolside/laguna-s-2.1:free`, `poolside/laguna-xs-2.1:free`,
`stepfun/step-3.7-flash:free`. These are a SEPARATE free bucket from OpenRouter free — round-robin
across BOTH providers doubles the daily free quota. Configure `nous` in config.yaml providers: with
the OAuth access_token from auth.json (NOT api_key — Nous uses OAuth, base_url
`https://inference-api.nousresearch.com/v1`).

## OpenRouter free-tier rate limits

HTTP 429 free-models-per-day-high-balance = daily budget exhausted for ALL free models
on the account. Not per-model. Round-robin helps only if limits reset per-model.

## hermes -z exit code deception

hermes -z returns exit=0 even on API failures (429, 400, 401). Error is TEXT in stdout,
not reflected in exit code. A supervisor treating exit=0 as success loops infinitely:
queue empty -> forced judge -> 429 -> exit=0 -> queue still empty -> forced judge -> ...

Detection: grep log for 429 / Rate limit / API call failed after judge rounds.
After N consecutive failures, pause with 30min+ backoff.

## opencode-zen requires payment

opencode.ai/zen returns HTTP 401 No payment method without credits. NOT free.

## Nous Portal OAuth

Uses OAuth tokens (access_token + refresh_token) in auth.json credential pool.
Provider must be registered in config.yaml. Model IDs must match portal exactly.

## Architecture: $0 loop

| Component | Source | Selection |
|-----------|--------|-----------|
| Workers (3 parallel) | OpenRouter free | Round-robin across N free models |
| Judge (every 5th) | OpenRouter free | Largest available (nemotron-550b) |
| Main session | Paid (operator choice) | Never mixed into the loop |
