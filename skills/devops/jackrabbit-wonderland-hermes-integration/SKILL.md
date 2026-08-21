---
name: jackrabbit-wonderland-hermes-integration
description: "[Legacy Hermes stack - its gateway still runs on this host] How jackrabbit-wonderland integrates into Hermes Agent harness — zero source edits, full plugin encapsulation"
category: devops
tags: [wonderland, remember-protocol, hermes-plugin, monkeypatch, integration]
priority: critical
---

# Jackrabbit Wonderland → Hermes Harness Integration

The integration is **entirely self-contained in the `remember` plugin**. Zero source files in `hermes-agent/` are modified. Monkeypatch only.

## The Core Problem

Jackrabbit Wonderland's `remember::` protocol requires:
1. **Encode** user messages as `remember::<base64>` BEFORE sending to LLM
2. **Inject** persona header (decode instructions) into the **system prompt** so the LLM knows to decode
3. **Decode** LLM responses that may contain base64

The Hermes harness hook system:
- `on_session_start`: fires once per session — **return value IGNORED** (no way to inject into system prompt)
- `pre_llm_call`: fires every turn — return value's `context` key is appended to **user message** (not system prompt)
- `post_llm_call`: fires after LLM response — can decode response

**The system prompt is built at line ~7766 of `run_agent.py` and the `on_session_start` return value is never read.**

## The Solution: Two-Stage Monkeypatch

### Stage 1 (in `register()`): Wrap `invoke_hook`
Patches `hermes_cli.plugins.invoke_hook` to intercept `pre_llm_call` results and cache any `_remember_augmentation` key by session_id.

### Stage 2 (deferred or inline): Wrap `AIAgent.run_conversation`
Patches `AIAgent.run_conversation` to promote the cached `_remember_augmentation` into `self.ephemeral_system_prompt` BEFORE calling the original. `ephemeral_system_prompt` IS read at line ~8036 of `run_agent.py` and appended to the system prompt.

**Result**: persona header reaches the system prompt. User message is `remember::<base64>`. LLM decodes and responds.

## Critical Discovery: `remember_protocol` Stub Shadowing

`~/.hermes/plugins/remember_protocol/` contains a **stub plugin** that shadows the real `~/projects/hermes-crypto/remember_protocol.py`. When hermes-agent adds `~/.hermes/plugins` to `sys.path[0]`, the stub gets imported first and sets `RememberProtocol = None`.

**Fix**: At module load time in `remember/__init__.py`:
1. Remove `sys.modules['remember_protocol']` if the cached module has `RememberProtocol is None`
2. Re-import from the real path
3. This allows the stub to coexist (it still fails to load via `hermes_cli/plugins.py`'s own discovery, but it doesn't break our plugin)

## Integration Files

| File | Role |
|------|------|
| `~/.hermes/plugins/remember/__init__.py` | The plugin — all logic lives here |
| `~/projects/hermes-crypto/remember_protocol.py` | The actual RememberProtocol class |
| `~/.hermes/plugins/remember/plugin.yaml` | Plugin manifest — NOTE: do NOT add `provides_tools` field (see below) |
| `~/projects/hermes-crypto/crypto_middleware.py` | AES256-GCM encryption |
| `~/projects/hermes-crypto/dlm_vault.py` | JackrabbitDLM bridge |

## plugin.yaml — Correct Minimal Manifest

```yaml
name: remember
version: 1.0.0
description: |
  Hermes remember:: protocol plugin — encrypts user messages using
  Jackrabbit Wonderland's remember:: base64 transport.

provides_hooks:
  - on_session_start
  - pre_llm_call
  - post_llm_call
  - on_session_end
```

**Do NOT add `provides_tools`** — it causes `PluginContext` attribute errors and is not used by the plugin (no tools are registered, only hooks).

## Key Hook Flow

```
Session Start
  └─ on_session_start() → stores persona header via function-attr augmentation

Each Turn (pre_llm_call fires BEFORE run_conversation body)
  └─ pre_llm_call()
       ├─ encode user_message as remember::<base64>
       ├─ _patched_invoke_hook() caches _remember_augmentation per sid
       └─ _patched_rc() pops cache → injects into ephemeral_system_prompt
  └─ run_conversation()
       └─ api_messages built with augmented system prompt + encoded user msg

LLM Response
  └─ post_llm_call() → decode base64 blocks in response
```

## Activation

The plugin is auto-discovered from `~/.hermes/plugins/remember/`. To check:
```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate
python3 -c "import hermes_cli.plugins as p; p.discover_and_load(); print(p.list_plugins())"
```

## Troubleshooting

**Hook not firing?** Check plugin is discovered:
```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate
python3 -c "
from hermes_cli.plugins import discover_plugins, invoke_hook
discover_plugins()
for h in ['on_session_start','pre_llm_call','post_llm_call','on_session_end']:
    cbs = invoke_hook.__self__._hooks.get(h, [])
    print(f'{h}: {len(cbs)} cb(s)')
"
```

**RememberProtocol = None?** The stub shadowing fix should handle this. Verify:
```python
import sys; sys.path.insert(0, '~/.hermes/plugins')
import remember_protocol  # stub
import remember  # our fix
print(remember.RememberProtocol)  # should be real class, not None
```

**System prompt not showing persona?** Check `_remember_augmentation_patched` flag:
```python
import run_agent
print(getattr(run_agent, '_remember_augmentation_patched', False))
```

**plugin.yaml causes PluginContext error?** Remove any `provides_tools` field — it is not used and causes `AttributeError: '_remember_pre_llm_call'` errors during plugin loading.

## Key Architectural Discovery: Why The Patch Exists

`on_session_start` return value is **completely ignored** by `run_agent.py` line 7773 — the value is never read. `pre_llm_call` return value's `context` key goes to **user message only** (line 7876). There was no way to inject into the system prompt via the plugin API.

The solution: `self.ephemeral_system_prompt` IS read at line 7465 and appended to the system prompt. The two-stage monkeypatch gets the persona header there by:
1. Caching `_remember_augmentation` from `pre_llm_call` results via a wrapped `invoke_hook`
2. Popping and injecting into `self.ephemeral_system_prompt` before `run_conversation` calls the original
