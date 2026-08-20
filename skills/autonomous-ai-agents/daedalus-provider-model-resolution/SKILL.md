---
name: daedalus-provider-model-resolution
description: How Daedalus resolves providers and models - hardcoded defaults, aliases, env vars, config precedence
category: autonomous-ai-agents
version: 1.0
tags: [daedalus, provider, model, config, kilocode, openrouter, resolution, default]
priority: critical
---

# Daedalus Provider & Model Resolution

The most confusing part of the Daedalus harness. Getting this wrong means "401 paid model required" forever.

## VERIFIED 2026-08-07 (installed v0.20.0, branch context-budget-manager)

**The old hardcoded-default trap is FIXED in current code.** Verified in source:
- `agent/agent_init.py` signature: `model: str = ""` (no more `"anthropic/claude-opus-4.6"` default; the docstring at line ~543 is STALE and still mentions the old default — ignore it).
- `daedalus_cli/main.py:969` reads `DEFAULT_CONFIG.get("model","")` and compares against live config; CLI passes the configured model through.
- `agent/agent_init.py:2169+` falls back to `config.yaml -> model.default` when model is empty.

Resolution chain (current):
```
1. CLI arg: daedalus chat -m model-name        (highest priority)
2. Config:  config.yaml -> model.default      (now honored by CLI)
3. Empty string / provider registry default  (last resort)
```
If you still see `claude-opus-4.6` being used despite config: check `~/.daedalus/auth.json` `active_provider` vs `config.yaml model.provider` — a mismatch (e.g. auth says `nous`, config says `deepseek`) can route to the wrong provider. That mismatch was live on this host 2026-08-07.

## Provider Aliases (daedalus_cli/auth.py)

```
_PROVIDER_ALIASES = {
    "kilo": "kilocode",
    "kilo-code": "kilocode",
    "kilo-gateway": "kilocode",
    ...
}
```

The provider name in config MUST be one of these aliases or a registered provider ID.

## Known Providers (PROVIDER_REGISTRY)

| Provider ID | Base URL | Env Var |
|-------------|----------|---------|
| nous | inference-api.nousresearch.com/v1 | NOUS_API_KEY |
| kilocode | api.kilo.ai/api/gateway | KILOCODE_API_KEY |
| anthropic | api.anthropic.com | ANTHROPIC_API_KEY |
| openrouter | openrouter.ai/api/v1 | OPENROUTER_API_KEY |

## Correct Config for Kilo Free

```yaml
model:
  api_key: "YOUR_JWT_TOKEN"
  base_url: https://api.kilo.ai/api/gateway
  default_model: kilo-auto/free
  provider: kilo

providers:
  kilo:
    api: https://api.kilo.ai/api/gateway
    api_key: "YOUR_JWT_TOKEN"
    default_model: kilo-auto/free
    name: Kilo Code
    transport: chat_completions
```

## .env

```
KILOCODE_API_KEY=YOUR_JWT_TOKEN
```

## Launcher Fix

Since config default_model is ignored by CLI:
```bash
if [ $# -eq 0 ]; then
    python3 -m daedalus_cli.main chat -m kilo-auto/free
else
    python3 -m daedalus_cli.main "$@"
fi
```

## Free Models on Kilo.ai

| Model | Notes |
|-------|-------|
| kilo-auto/free | Auto-routes to free models. Works. |
| arcee-ai/trinity-large-thinking:free | Reasoning model |
| bytedance-seed/dola-seed-2.0-pro:free | Reasoning |

## Pitfalls

1. **provider: nous** requires Nous Portal auth, defaults to claude-opus-4.6
2. **provider: kilo-auto-free** NOT recognized — must be `kilo` (alias -> kilocode)
3. **Config default_model ignored** by CLI chat command — must use `-m` flag
4. **402 "Paid Model"** = wrong model ID or no credits. Check model list with `client.models.list()`
5. **401 "Not logged in"** = wrong provider name or missing auth
