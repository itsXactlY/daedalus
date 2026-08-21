# Hermes LAN Gateway — LLM Routing for BTQuant Agency

**Why this exists:** the operator's hard rule on 2026-06-18 was "KEIN
OLLAMA! via HERMES SEINEM GATEWAY!". Any session touching the BTQuant
agency LLM must route through this gateway, not Ollama local.

## Architecture

```
+-----------------+       +----------------------+       +-------------------+
|  llm_adapter.py |       |  Hermes LAN gateway  |       |   Upstream LLM    |
|  (in agency)    +-----> +  https://8443/v1     +-----> +  (e.g. MiniMax)   |
|  BTQ_LLM_* env  |  TLS  |  Self-signed cert     |  HTTPS|  api.minimax.io   |
+-----------------+       |  systemd:             |       +-------------------+
                          |  mazemaker-apk-gateway |       ERROR 2056:
                          +----------------------+       Token Plan limit
```

The gateway is `projects/hermes-crypto/lan_gateway.py` (PID 202687
in the operator's machine). It serves `/v1/chat/completions`,
`/v1/models`, plus the token-authenticated APK paths.

## Available Models (verified 2026-06-18)

```bash
curl -sk https://localhost:8443/v1/models
```

| ID | Type | Notes |
|----|------|-------|
| `wonderland` | alias | routes through to upstream; safe default |
| `hermes-agent` | alias | same upstream; same as `wonderland` |
| `MiniMax-M2.7` | real | the actual model the gateway proxies to |

All three share the same upstream (currently MiniMax). 204800 context
window, 131072 max completion tokens. Pricing/billing is shared —
all three consume from one Token Plan quota.

## Systemd Unit — EnvironmentFile Fix (mandatory)

The systemd unit at
`~/.config/systemd/user/mazemaker-apk-gateway.service` originally
**did not** load `gateway.env`, so `WONDERLAND_UPSTREAM_*` vars were
missing and the gateway returned `Wonderland upstream is not
configured`. Fix:

```ini
# /home/alca/.config/systemd/user/mazemaker-apk-gateway.service
[Service]
# ... existing ExecStart, WorkingDirectory, HERMES_CRYPTO_HOME, MM_POD_URL ...
EnvironmentFile=%h/projects/hermes-crypto/container/gateway.env
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user restart mazemaker-apk-gateway.service
systemctl --user status mazemaker-apk-gateway.service
```

Verify upstream is wired:

```bash
curl -sk https://localhost:8443/v1/models
# Should show 3 models with context_length=204800, max_completion_tokens=131072
```

## gateway.env (redacted — never echo in chat)

```bash
WONDERLAND_UPSTREAM_PROVIDER=minimax     # (typo in source for "minimax")
WONDERLAND_UPSTREAM_BASE_URL=https://api.minimax.io/v1
WONDERLAND_UPSTREAM_MODEL=MiniMax-M2.7
WONDERLAND_UPSTREAM_API_KEY=***          # operator's key
SESSION_TTL=3000
PROXY_MODEL_ALIASES=wonderland,hermes-agent,proxy,default
DLM_RETRY=1
DLM_RETRY_SLEEP=0.2
DLM_TIMEOUT=2
```

To swap upstream (e.g. if MiniMax quota is exhausted):

1. Edit `gateway.env` (new provider, base URL, model, key).
2. `systemctl --user restart mazemaker-apk-gateway.service`.
3. Agency auto-picks up the change on next LLM call (no restart needed).

## Self-Signed Cert — SSL Verification

The gateway uses a self-signed cert. The agency's
`llm_adapter.LLMClient` honors:

| Env | Effect |
|-----|--------|
| `BTQ_LLM_INSECURE=1` | skip cert verification (use for local gateway) |
| `BTQ_LLM_CA_BUNDLE=/path/to/cert.pem` | pin the CA cert |
| (neither) | system trust store (will FAIL on self-signed) |

Default for the agency: `insecure=True` if `BTQ_LLM_INSECURE=1`,
else strict verification. The cert at `~/.hermes-crypto/gateway.crt`
is the right CA bundle if you want pinned verification.

## Rate Limit Behavior (error 2056)

When the upstream is at quota, the gateway returns:

```json
{"type":"error","error":{"type":"rate_limit_error",
 "message":"Token Plan usage limit reached: Upgrade your Token Plan
  or purchase Credits for more usage. (2056)","http_code":"429"}}
```

The agency's `hypothesis_generator._call_ai_model` catches this and
returns the deterministic `_fallback_text_response()` so the loop
keeps producing strategies. Stats show 0 LLM hits in the cycle, but
the cycle itself completes.

When the upstream recovers (credits added, plan upgraded), the
next cycle's LLM call works automatically. No restart needed.

## Common Pitfalls

1. **Picking Ollama by reflex** — the operator banned this. If you
   see `127.0.0.1:11434` in `LLMConfig`, that's a bug. Use
   `https://localhost:8443/v1`.

2. **Forgetting `EnvironmentFile` after editing `gateway.env`** —
   systemd doesn't auto-reload env files. You need
   `daemon-reload && restart`.

3. **Hardcoding `api_key` in env vars** — `gateway.env` already
   has the key. The agency's `BTQ_LLM_API_KEY` should be empty for
   the gateway path (the gateway injects its own upstream key).

4. **Confusing "hermes-agent" (gateway alias) with the local Hermes
   Agent's messaging gateway** — they are unrelated services.
   `hermes-agent` here is just a model name string.

5. **Trying to use `stream=true`** — the gateway is non-streaming.
   Always set `stream=false` (the default in `llm_adapter.py`).

## Verification

```bash
# 1. Gateway alive
curl -sk https://localhost:8443/v1/models | head -3

# 2. Agency can call it
cd ~/projects/PubBTQuant
BTQ_LLM_INSECURE=1 BTQ_LLM_BASE_URL=https://localhost:8443/v1 \
  BTQ_LLM_MODEL=wonderland python3 -c "
import sys; sys.path.insert(0, '.')
from autonomous_agency.llm_adapter import LLMClient
c = LLMClient()
print(c.chat([{'role':'user','content':'ping'}], max_tokens=5))"

# 3. Full loop
python3 -m autonomous_agency.run_loop --max 1 --hypotheses 1
```
