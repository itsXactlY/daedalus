# Config Gotchas for Large-Context Models

## The Trash-Model Default Trap

Daedalus ships with `openrouter_free` as the default provider, using `inclusionai/ling-3.0-flash:free` — a tiny free model. This causes:

1. **Small context window** — the model can't hold large conversations
2. **Compression at 55%** — when context hits 55% of max, compression triggers
3. **Trash summarizer** — compression uses the same tiny model, producing garbage summaries
4. **Context nuked to ~128K** — even if the original model had 1M context

**User frustration signal**: "NO WONDER ALL U FUCKS TURN IN CIRCLES" — the agent loses context and repeats itself.

## Valid reasoning_effort Values

The `reasoning_effort` parameter controls chain-of-thought allocation. Invalid values crash the session.

| Value | Effect | Use Case |
|-------|--------|----------|
| `max` | Maximum reasoning | Complex tasks, debugging |
| `xhigh` | High reasoning | Default for most sessions |
| `high` | Moderate-high | General use |
| `medium` | Balanced | Simple tasks |
| `low` | Minimal reasoning | Quick queries |
| `minimal` | Near-zero | Trivial tasks |
| `none` | No chain-of-thought | Raw output only |

**NEVER use `ultra`** — it is NOT a valid option. Causes:
```
BadRequestError: reasoning_effort: Invalid option: expected one of "max"|"xhigh"|"high"|"medium"|"low"|"minimal"|"none"
```

## Config Key Gotchas

Some config keys need the `--force` flag:
```bash
daedalus config set agent.reasoning_effort max --force  # may warn "not a recognized config key"
```

The warning is cosmetic — the value IS saved and works. The `--force` flag suppresses the "did you mean X?" suggestion.

## Provider Configuration Patterns

### OpenRouter with large-context models
```yaml
model:
  provider: opendeepseek  # or whatever you named the provider
  default: xiaomi/mimo-v2.5  # 1M context
providers:
  opendeepseek:
    api_key: sk-or-...
    base_url: https://openrouter.ai/api/v1
    default_model: google/gemma-4-31b-it:free
    models:
      - xiaomi/mimo-v2.5
      - xiaomi/mimo-v2.5-pro
    extra_body:
      provider:
        allow_fallbacks: false
        order:
          - xiaomi/fp8
    type: custom
```

### Nous Research inference API
```yaml
model:
  provider: nous
  default: deepseek/deepseek-v4-flash  # 1M context
providers:
  nous:
    api_key: ...
    base_url: https://inference-api.nousresearch.com/v1
    models:
      - deepseek/deepseek-v4-flash
      - qwen/qwen3.6-plus
```

## Verification Commands

```bash
# Check current model
daedalus config get model

# Check compression status
daedalus config get compression

# Check reasoning_effort
daedalus config get agent.reasoning_effort

# Full config dump
daedalus config
```

## Session Recovery

If the session is already broken (context nuked, circles):
1. Fix config as above
2. Start a NEW session (old context is gone)
3. Re-read critical files from scratch
4. Do NOT try to "recover" the old context — it's gone
