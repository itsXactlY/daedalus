---
name: ollama-protocol-bridge
description: Bridge Ollama-only service to local llama.cpp via proxy.
---

# Ollama-Protocol Bridge (llama.cpp ↔ Ollama-only service)

## Trigger
A service (Podman pod, FastAPI app, CLI) needs an LLM but only implements the
**Ollama protocol**: `GET /api/tags` and `POST /api/generate`. You have
**llama.cpp** running with `--api-key`, which speaks **OpenAI-compat**
(`/v1/models`, `/v1/chat/completions`) — NOT Ollama format. Direct wiring
fails: the service probes `/api/tags` and gets 404, or sends `/api/generate`
and gets an OpenAI-shaped error.

Do NOT rebuild the service. Put a thin proxy in between.

## The proxy (scripts/ollama-compat-proxy.py)
Translates:
- `GET /api/tags` → fixed model list from `LLAMA_BASE_URL/v1/models`
- `POST /api/generate` (`{model, prompt, stream, options}`) →
  `POST LLAMA_BASE_URL/v1/chat/completions` (`{model, messages, stream:false,
  temperature, max_tokens}`) → returns `{response: <text>}`.

Run it (background, persistent):
```bash
LLAMA_BASE_URL=http://127.0.0.1:8080 LLAMA_KEY=sk-llama PROXY_PORT=11435 \
  python3 scripts/ollama-compat-proxy.py
```
Then point the service at `http://host.containers.internal:<PROXY_PORT>` (rootless
Podman pod — pasta networking) or `http://127.0.0.1:<PROXY_PORT>` (same host, no container).

## Why this works
- The service only needs two endpoints; the proxy fakes both.
- llama.cpp's `/v1/chat/completions` with `stream:false` returns a clean
  `choices[0].message.content` — exactly what Ollama's `/api/generate` wraps as
  `response`. No model reload, no container rebuild, no service code change.

## Gotchas (learned the hard way, Pulse Pro pod 2026-08-04)
1. **Proxy must listen where the service reaches it.** In a rootless Podman pod
   use `host.containers.internal:<port>`, NOT `127.0.0.1` (pod's own loopback).
2. **Verify llama.cpp is actually loaded BEFORE wiring.** Probe `/v1/models`.
   If the model is still downloading, the proxy resolves `model=local` and every
   generate fails silently.
3. **Verify the actual model the service resolves** — probe its `/api/tags` path
   and confirm which model name comes back. A service hardcoded to `qwen2.5:3b`
   while only a different model is local will either fall back to a remote cloud
   model (off-topic noise) or error. Don't assume the backend is correct.
4. **"outdated gemma4 chat template" warnings from llama.cpp are harmless.**
5. **Filter collapse:** if the service uses the same LLM for a relevance filter
   and the model is "aggressive/uncensored", it may return `none` and drop
   everything — start research with `llm_filter:false` and curate manually.
6. **Real config is not the repo template.** Quadlets load from
   `~/.config/containers/systemd/*.container`, not `pod/quadlet/*.container`.
   After editing: `systemctl --user daemon-reload && podman rm -f <container> &&
   systemctl --user start <service>`. `systemctl restart` is NOT enough — the
   old container persists with stale env.

## Verify
```bash
curl http://localhost:<PROXY_PORT>/api/tags          # lists the model
curl -X POST http://localhost:<PROXY_PORT>/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"local","prompt":"reply OK","stream":false}'   # returns text
```

## Real-world use
Wired Pulse Pro pod (`pulse-pod`, :8770) to a local Gemma-4-E4B Q8 llama.cpp on
:8080. See `pulse-pro-deep-research` ("LLM backend" + "Wurm drift" sections).
