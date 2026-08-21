# Wiring a local llama.cpp model as the pulse-pro LLM backend

## Why
The Pro Pod defaults `OLLAMA_MODEL=qwen2.5:3b` and `OLLAMA_BASE_URL=
http://host.containers.internal:11434` (Ollama protocol). For niche tech
research you want a stronger local model (e.g. Gemma-4-E4B Q8) served by
llama.cpp on :8080 — but llama.cpp speaks OpenAI-compat, NOT Ollama protocol.
The Pod cannot talk to it directly. Solution: an Ollama-compat proxy.

## Steps
1. **Start llama.cpp** (background, not nohup):
   ```
   ./build/bin/llama-server -m <gguf> --host 0.0.0.0 --port 8080 \
     --n-gpu-layers 999 --ctx-size 8192 --api-key sk-llama
   ```
   GGUF path note: if pulled via HF, it lives under
   `~/.cache/huggingface/hub/models--<org>--<name>/snapshots/<hash>/<file>.gguf`
   (NOT a standalone file). Verify: `curl http://localhost:8080/v1/models`.

2. **Run the proxy** (`scripts/ollama-compat-proxy.py`): translates
   `/api/tags` + `/api/generate` → llama.cpp `/v1/chat/completions`.
   Listens on :11435. Verify: `curl http://localhost:11435/api/tags`.

3. **Patch the REAL quadlet** — `~/.config/containers/systemd/pulse-api.container`
   (NOT `pod/quadlet/pulse-api.container`, that is only a template!):
   ```
   Environment=OLLAMA_BASE_URL=http://host.containers.internal:11435
   Environment=OLLAMA_MODEL=Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf
   ```

4. **Redeploy** (daemon-reload + rm + start — restart alone keeps old env):
   ```
   systemctl --user daemon-reload
   podman rm -f systemd-pulse-api
   systemctl --user start pulse-api.service
   ```
   Verify env took: `podman inspect systemd-pulse-api | grep OLLAMA`

5. **Verify the Pod reaches Gemma**: start a research job; the llama.cpp
   server log will show new prompt-eval / completion activity as the Wurm's
   LLM planner + filter call Gemma.

## Gotchas
- `systemctl restart pulse-api.service` does NOT apply new quadlet env — the
  container is persistent, must `rm` + `start`.
- The proxy must run on the HOST (not in the Pod) so `host.containers.internal`
  from the Pod resolves to it.
- If you patched Pod CODE (worm.py / app.py), also `podman build -f
  pod/Containerfile -t localhost/pulse-pod:latest .` then redeploy.
