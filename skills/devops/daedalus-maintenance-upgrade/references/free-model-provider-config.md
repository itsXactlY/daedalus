# Free Model Provider Configuration

Verified working combinations for the rework loop (2026-08-04). All $0/1M tokens.

## Working combinations (verified)

### Nous Portal (provider: `nous`)

| Model ID | Context | Notes |
|----------|---------|-------|
| `tencent/hy3:free` | 262,144 | Best free model. Verified working. |
| `inclusionai/ling-3.0-flash:free` | — | Verified working. |
| `poolside/laguna-s-2.1:free` | — | Verified working. |
| `poolside/laguna-xs-2.1:free` | — | Verified working. |
| `stepfun/step-3.7-flash:free` | — | Verified working. |

**Daedalus CLI usage:** `-m "tencent/hy3:free" --provider nous`

**Config (config.yaml):**
```yaml
providers:
  nous:
    base_url: https://inference-api.nousresearch.com/v1
    type: custom
```

**Auth:** OAuth token from auth.json credential_pool (auto-refreshed). NO api_key in config.yaml — the provider reads the OAuth token from auth.json automatically.

**CRITICAL:** The Nous provider uses `--provider nous` flag. The model ID does NOT include the provider prefix. Wrong: `nous/tencent/hy3:free`. Right: `-m tencent/hy3:free --provider nous`.

### OpenRouter Free (provider: `openrouter_free`)

| Model ID | Notes |
|----------|-------|
| `inclusionai/ling-3.0-flash:free` | Good general-purpose |
| `cohere/north-mini-code:free` | Code-focused |
| `openai/gpt-oss-20b:free` | General |
| `google/gemma-4-26b-a4b-it:free` | Good reasoning |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Strongest free (550B) |
| `nvidia/nemotron-3-super-120b-a12b:free` | Good balance |
| `poolside/laguna-xs-2.1:free` | Light |
| `poolside/laguna-xs.2:free` | Light |

**Daedalus CLI usage:** `-m "inclusionai/ling-3.0-flash:free" --provider openrouter_free`

**Config (config.yaml):**
```yaml
providers:
  openrouter_free:
    api_key: sk-or-...  # OpenRouter API key
    base_url: https://openrouter.ai/api/v1
    type: custom
```

**Daily limit:** OpenRouter free models share a daily quota (`free-models-per-day-high-balance`). When exhausted, ALL free models return 429. Resets at midnight UTC.

## Broken combinations (don't use)

| Provider | Model | Error | Why |
|----------|-------|-------|-----|
| `opencode-zen` | any | 401 "No payment method" | No credit on account |
| `nous` | `deepseek-v4-flash-latest` | 404 | Wrong model ID format |
| `nous` | `nous/tencent/hy3:free` | 401 | Double provider prefix |
| `openrouter_free` | `deepseek/deepseek-v4-flash:free` | 401 | Not a free model |

## Supervisor format for multi-provider round-robin

The loop-supervisor uses `"provider:model"` format:
```bash
FREE_MODELS=(
  "nous:tencent/hy3:free"
  "nous:inclusionai/ling-3.0-flash:free"
  "openrouter_free:inclusionai/ling-3.0-flash:free"
  "openrouter_free:google/gemma-4-26b-a4b-it:free"
)
```

Split function:
```bash
split_model() {
  WM_PROVIDER="${1%%:*}"
  WM_MODEL="${1#*:}"
}
# Usage: split_model "nous:tencent/hy3:free"
# Then: daedalus -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli
```

## Pitfalls

1. **Double provider prefix:** `nous/tencent/hy3:free` fails. Use `tencent/hy3:free --provider nous`.
2. **Missing --provider flag:** Without it, Daedalus uses the default provider (opendeepseek), which may not have the model.
3. **OpenRouter daily limit:** When 429 hits, ALL OpenRouter free models are blocked until midnight UTC. Switch to Nous Portal as fallback.
4. **OAuth token expiry:** Nous Portal tokens expire. Check `auth.json` for `expires_at`. If expired, run `daedalus auth` flow.
5. **Model not in provider's list:** Some models exist on OpenRouter but aren't in the `openrouter_free` provider's `models` list. Add them to config.yaml if needed.
