---
name: pulse-pro-pod-ops
description: Run pulse-pro pod research; bridge llama.cpp Ollama proxy.
---

# Pulse-Pro Pod Ops

Operate the local **pulse-pro** research engine: a license-gated FastAPI pod on
`http://127.0.0.1:8770` behind a stdio MCP adapter (`pod/pulse_mcp_adapter.py`).
This is the REAL engine — NOT the community `pulse` skill CLI under
`~/.hermes/skills/devops/pulse` (that copy is weaker: fewer sources, worse scoring,
no wurm). When the operator says "pulse", "/pulse", or wants deep research, target
the Pro Pod via its REST surface, never the community `scripts/pulse.py`.

## Architecture
```
pulse_mcp_adapter.py  (stdio MCP, mirrors pod REST)  ─┐
                                                       ├─> http://127.0.0.1:8770
hermes / direct curl  ───────────────────────────────┘      (FastAPI, license-gated)
                                                              ├─ /research/start  (async job)
                                                              ├─ /research/jobs/{id}
                                                              ├─ /research/jobs/{id}/result
                                                              ├─ /search  /dig  /lineage/{run_id}
                                                              └─ /healthz  /license  /diagnostics
```
- Pod runs as rootless Podman quadlet `systemd-pulse-api` inside `pulse.pod`.
- LLM planner + post-rank filter need an Ollama-protocol backend (see "Wiring a local LLM").

## CRITICAL: deep / --wurm runs are ASYNC
The MCP adapter kills tool calls at ~120s. A deep wurm dive legitimately runs
**30–120 minutes**. NEVER call `/research` (synchronous) for deep; use the job flow:
1. `POST /research/start`  → returns `{"job_id": "...", "state": "running"}`
2. Poll `GET /research/jobs/{job_id}` every few minutes. Watch `state`,
   `heartbeat_age_seconds` (fresh = <60s), and `phases[]` (search → dig-1..N →
   llm-filter). A run is "stuck" ONLY if `state=running` AND
   `heartbeat_age_seconds > ~2700` (45 min) with no new phase.
3. `GET /research/jobs/{job_id}/result` → full ranked candidates when `state=done`.

Start payload (JSON):
```json
{"topic":"...","depth":"deep","wurm":true,"max_wurm_rounds":6,
 "lookback_days":100,"llm_filter":true,"n":40,"emit":"md"}
```

## LLM-filter collapse — recovery
`_llm_filter_candidates` calls the LLM (Ollama) to drop off-topic items. Failure
modes seen:
- **Keeps wrong cluster**: filter returns 7 GitHub-Copilot localization pages for a
  "WebGL rendering" query (worm re-seeded into "Github" signal, filter kept densest
  cluster). Fix: set `"llm_filter": false` in the start payload to recover the RAW
  aggregated pool (483 candidates), then curate manually.
- **Drops everything**: narrow seed → `dig-1` growth 0% → 0 returned. Fix: broaden
  the topic string; don't over-narrow.
- If `llm_filter` is on and Ollama is unreachable, `_llm_filter_candidates` returns
  candidates AS-IS (no filtering) — so a missing LLM doesn't crash, it just passes
  through unfiltered.

## Wiring a local LLM (llama.cpp → Ollama protocol bridge)
The pod ONLY speaks Ollama protocol (`GET /api/tags`, `POST /api/generate`).
llama.cpp speaks OpenAI-compat (`/v1/chat/completions`). Bridge with a thin proxy
(see `scripts/ollama-compat-proxy.py`): it listens on `:11435`, answers `/api/tags`
with the llama.cpp model name, and translates `/api/generate` → OpenAI chat
completions. Then point the pod at the proxy.

Steps:
1. Start llama.cpp: `./build/bin/llama-server -m <gguf> --host 0.0.0.0 --port 8080
   --n-gpu-layers 999 --ctx-size 8192 --api-key sk-llama` (background process).
   Verify: `curl localhost:8080/v1/models`.
2. Start the proxy (background): `python3 scripts/ollama-compat-proxy.py`
   (env: `LLAMA_BASE_URL=http://127.0.0.1:8080`, `LLAMA_KEY=sk-llama`, `PROXY_PORT=11435`).
   Verify: `curl localhost:11435/api/tags` → model name;
   `curl -X POST localhost:11435/api/generate -d '{"prompt":"hi","stream":false}'`.
3. Point the pod at the proxy (see Quadlet gotcha below):
   `OLLAMA_BASE_URL=http://host.containers.internal:11435`
   `OLLAMA_MODEL=<exact llama.cpp model name from /v1/models>`.

## QUADLET GOTCHA (cost real time once)
The pod reads its config from the **REAL** quadlet at
`~/.config/containers/systemd/pulse-api.container` — NOT the template copy in
`/home/alca/projects/pulse-pro/pod/quadlet/pulse-api.container`. Patching the
template does nothing. To apply:
```bash
# edit ~/.config/containers/systemd/pulse-api.container (OLLAMA_* env)
systemctl --user daemon-reload
podman rm -f systemd-pulse-api          # must remove; start won't rebuild from new file
systemctl --user start pulse-api.service
# verify: podman inspect systemd-pulse-api | grep OLLAMA
curl http://127.0.0.1:8770/healthz     # {"status":"ok"}
```
`systemctl --user restart` can fail on a dependency job and leave the container
down — prefer `stop`/`rm` + `start`. The container name is `systemd-pulse-api`
(systemd prefix), not `pulse-api`.

## Broken image reference → Pull=never (verified 2026-08-16)
If the quadlet's Image= points to a registry that can't be reached (TLS cert expired,
registry down), systemd-quadlet silently tries to pull on every restart and fails.
The container stays down forever because `systemctl --user start` sees "already running"
and skips. Fix: add `Pull=never` to the REAL quadlet file so systemd never attempts
a pull, then rebuild from scratch:
```bash
# Add Pull=never to ~/.config/containers/systemd/pulse-api.container
sed -i '/^Image=/s/$/\nPull=never/' ~/.config/containers/systemd/pulse-api.container
systemctl --user daemon-reload
podman rm -f systemd-pulse-api
podman build -t localhost/pulse-pod:latest -f pod/Containerfile .  # rebuild from repo
systemctl --user start pulse-api.service
```

## Verification checklist
- [ ] Pod health: `curl 127.0.0.1:8770/healthz` → ok
- [ ] Proxy reachable from host: `curl localhost:11435/api/tags`
- [ ] llama.cpp loaded: `curl localhost:8080/v1/models` shows model
- [ ] Pod env points at :11435: `podman inspect systemd-pulse-api | grep OLLAMA_BASE_URL`
- [ ] Test run: start a job, confirm `dig-1` shows `new_candidates > 0` (proves the
      LLM planner is routing correctly — if it's 0, the LLM backend is too weak or
      the topic too narrow)

## NO-OLLAMA mode (operator directive 2026-08-08)
The operator wants the pod to use NO Ollama for planning/filtering ("use ur self, deepseek").
Set `Environment=OLLAMA_BASE_URL=http://127.0.0.1:1` (dead) in the REAL quadlet so the
planner's `_check_ollama()` probe fails fast → falls back to the no-LLM heuristic router,
and keep `llm_filter:false`. Then the pod digs mechanically and the Hermes agent (deepseek)
does all curation. Result is honest raw candidates you must curate yourself — the heuristic
ranking still surfaces Polymarket volume (skews rrf) and arxiv Ti-substring junk
(PITFALL #250), so filter by local_relevance + on-topic judgment.

## Stale published image loses topic_anchor (verified 2026-08-08)
The published `remainder.online/pulse-pod/<ver>.tar` may be built from an OLDER repo and be
MISSING the `topic_anchor` worm lock. Symptom: deep run drifts into Polymarket/relationship
junk. Verify immediately after load:
`podman exec systemd-pulse-api grep -c topic_anchor /app/lib/worm.py` (must be >0).
If 0, rebuild from the repo: `cd ~/projects/pulse-pro && podman build -t localhost/pulse-pod:latest -f pod/Containerfile .`
then `systemctl --user stop pulse-api.service && podman rm -f systemd-pulse-api && systemctl --user start pulse-api.service`.
After rebuild the anchor-filter phase appears and dig stays on-topic.

## /search (synchronous) — the fast focused path
For tight per-frontier research use `POST /search` (not the async worm). Body keys:
`topic` (str, req), `sources` MUST BE A LIST (`["arxiv","hackernews"]`) — a comma string
returns 422 `list_type`. Response key is `ranked_candidates` (NOT `candidates`). Use
`use_llm:false`, `llm_filter:false`, `depth:"deep"`, `lookback_days:30`. arxiv full-text
returns heavy Ti-cluster/monoid noise — prefer openalex/github/hackernews and filter by
local_relevance. openalex results carry arxiv pdf/abstract URLs.

## Pitfalls
- Don't call `/research` synchronously for deep — MCP timeout ~120s. Use `/research/start`.
- Don't patch `pod/quadlet/pulse-api.container` — it's a template. Edit
  `~/.config/containers/systemd/pulse-api.container`.
- `OLLAMA_MODEL` must EXACTLY match the name llama.cpp reports in `/v1/models`
  (e.g. `Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf`), not a short alias.
- lineage endpoint returns only `edges` (graph), not candidate lists — you can't
  recover pre-filter candidates from it. Use `llm_filter:false` from the start if you
  suspect filter collapse.
- The community `pulse` skill CLI is a different, weaker engine. Don't confuse the
  two; the Pro Pod is the source of truth.
