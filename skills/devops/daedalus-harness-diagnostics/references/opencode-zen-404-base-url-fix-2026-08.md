# OpenCode Zen 404 — Stale base_url in credential pool (2026-08-03)

## Symptom

User ran `opencode -s ses_040ff3f22ffe3Bp9D6JXB2uIRR` (free models via OpenCode Zen).
Every request failed with HTTP 404:

```
Endpoint: https://opencode.ai/zen/v1/chat/completions/v1
Error: HTTP 404 — Not Found | opencode
```

Tried models `deepseek-v4-flash-free` and `hy3-preview-free` — both 404'd.

## Root cause

The credential pool in `~/.daedalus/auth.json` had a stale `base_url`:

```json
"credential_pool": {
  "opencode-zen": [
    {
      "base_url": "https://opencode.ai/zen/v1/chat/completions",  // WRONG
      ...
    }
  ]
}
```

The OpenAI SDK appends `/chat/completions` to the base_url, so actual requests went to:
`https://opencode.ai/zen/v1/chat/completions/v1/chat/completions` → 404

The provider is registered correctly with `base_url="https://opencode.ai/zen/v1"` in
`plugins/model-providers/opencode-zen/__init__.py`. But the credential pool persisted a
resolved URL (including `/chat/completions`) from a previous session, and it was never
cleaned up.

## How the URL gets doubled

1. Provider registers: `base_url = "https://opencode.ai/zen/v1"` ✓
2. OpenAI SDK appends: `/chat/completions` → `https://opencode.ai/zen/v1/chat/completions` ✓
3. TUI/gateway persists the **full resolved URL** to credential pool in auth.json
4. Next session loads credential pool URL: `https://opencode.ai/zen/v1/chat/completions`
5. OpenAI SDK appends again: `/chat/completions` → doubled URL → 404

The `normalize_opencode_base_url()` function (hermes_cli/models.py:4163) only ensures
`/v1` is present — it does NOT strip `/chat/completions`.

## Fix

```python
# Read auth.json, fix credential pool base_url
import json
with open('auth.json') as f:
    data = json.load(f)
for prov, creds in data.get('credential_pool', {}).items():
    if not isinstance(creds, list): continue
    for c in creds:
        url = c.get('base_url', '')
        for suffix in ['/v1/chat/completions', '/chat/completions', '/v1/responses', '/responses']:
            if url.endswith(suffix):
                c['base_url'] = url[:-len(suffix)]
                if 'opencode.ai' in c['base_url'] and not c['base_url'].endswith('/v1'):
                    c['base_url'] += '/v1'
                print(f'FIXED: {url} -> {c["base_url"]}')
with open('auth.json', 'w') as f:
    json.dump(data, f, indent=2)
```

Result: `https://opencode.ai/zen/v1/chat/completions` → `https://opencode.ai/zen/v1`

## Detection

```bash
cd ~/.daedalus && python3 -c "
import json
with open('auth.json') as f:
    data = json.load(f)
for prov, creds in data.get('credential_pool', {}).items():
    if not isinstance(creds, list): continue
    for c in creds:
        url = c.get('base_url', '')
        if '/chat/completions' in url or '/responses' in url:
            print(f'STALE [{prov}]: {url}')
"
```

## Key insight

The `normalize_opencode_base_url()` function is correct for its purpose (ensuring `/v1`
suffix exists for chat_completions mode after an anthropic-mode switch stripped it). But
it can't fix a credential pool that stores the full endpoint path. The persistence layer
should only store the base URL, not the resolved endpoint.
