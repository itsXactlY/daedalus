---
name: mazemaker-embed-topology
description: "Mazemaker pod VRAM/embed: bge holders, HTTP vs socket."
category: devops
---

# Mazemaker v2 Embedding Topology & Single-bge Consolidation

## When to Load
- VRAM pressure on the mazemaker pod (16 GB card): "how many bge are loaded?", "why is VRAM full?"
- Changing `EMBED_*` env vars or quadlets for embedding-worker / dream-worker / mcp
- Any socket-vs-HTTP question about `~/.mazemaker/sockets/embed.sock`
- Consolidating duplicate embedding models to exactly ONE bge in VRAM
- Verifying which container owns which GPU memory

## Core Facts (measured 2026-08-07, log-verified)

1. **All pod containers share ONE network namespace.** `podman inspect --format '{{.HostConfig.NetworkMode}}'` on any `systemd-mazemaker-*` container → `container:<infra-id>`. Consequence: `localhost:8766` is reachable from EVERY container in the pod — pod-wide HTTP needs no host networking, no service discovery. (Common assumption "containers can't share localhost" is WRONG inside one pod.)
2. **Canonical bge-m3 holder = `embedding-worker`** (uvicorn, `EW_PORT=8766`, provider from `~/.mazemaker/embedding.toml` → `sentence-transformers`/`BAAI/bge-m3`, `device=auto`). Endpoints: `POST /embed`, `POST /embed_colbert`, `GET /health`. Its `backends.py` has NO idle eject — model stays in VRAM (~2392 MiB). Model is re-read per request from `embedding.toml` (hot provider switch).
3. **mcp + wonderland are pure HTTP clients** (log-verified `HttpEmbeddingBackend → http://localhost:8766`; wonderland `embed_client.py` docstring calls the socket a "stale v1 leftover"). ColBERT runs over HTTP too (`colbert_helper.py`, `MM_EMBEDDING_WORKER_URL`, default `http://localhost:8766`, fallback = local in-process bge if worker unreachable — the fallback is what silently re-adds VRAM!).
4. **The UNIX socket (`~/.mazemaker/sockets/embed.sock`, bind-mounted into dream-worker + mcp) works container-to-container** (same host, bind mount) but is legacy: only dream-worker self-serves it. dream-worker still loads its OWN bge-m3 (`EMBED_BACKEND=sentence-transformers` forced in its quadlet) = the REDUNDANT 2nd copy (~5668 MiB incl. its GpuRecallEngine tensor).

## The EMBED_BACKEND=http Gotcha (critical)

`EMBED_BACKEND=http` is NOT handled by the forced-env branch in `embed_provider.py`:
- `EmbeddingProvider.__init__` (~line 1429) and `_auto_detect` (~line 1484) only special-case `'sentence-transformers'/'st'/'sbert'` and `'fastembed'`.
- Env-only switching to `http` falls through to auto-detect → SharedEmbedClient probe (socket) or CUDA direct load → **a second bge stays loaded**.

Working switches to HTTP-client mode:
- **Constructor arg**: `EmbeddingProvider(backend="http")` → `HttpEmbeddingBackend()` (how mcp does it; add `--embedding-backend http` to dream-worker's Exec line).
- **Code fix** (robust, covers ALL construction paths): accept `forced == 'http'` → `HttpEmbeddingBackend()` at BOTH dispatch points in embed_provider.py.
- **`EMBED_CLIENT_ONLY=1` semantics**: any direct `SentenceTransformerBackend()` construction RAISES ("Refusing to spawn a redundant model copy") instead of loading a model. Use as a safety net on every client so an unexpected code path can never quietly load a 2nd bge.

`HttpEmbeddingBackend` (embed_provider.py ~1298): `MM_EMBEDDING_WORKER_URL` (default http://localhost:8766), `MM_EMBED_TIMEOUT` (default 10, mcp uses 120 via drop-in), dim probed via 1-token embed at construction. Construction FAILS HARD (raises) if worker unreachable → process start fails → `Restart=on-failure` covers it.

## Verification Techniques

1. **VRAM → container attribution**: `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv` + `podman ps --format '{{.Names}} {{.Pid}}'` (PIDs are host PIDs, directly comparable). Reference split (2026-08-07): embedding-worker 2392 MiB (bge), dream-worker 5668 MiB (bge + recall tensor), mcp 2260 MiB (recall tensor ONLY — no bge), llama-server 4460 MiB (AFE Stage C).
2. **Which backend a process actually uses**: log grep for `HttpEmbeddingBackend →` (HTTP), `Embedding backend: SentenceTransformerBackend ... [forced via EMBED_BACKEND=...]` (local load), `colbert: using the embedding-worker's shared bge-m3` (colbert via HTTP) vs `colbert: BGE-M3 token-emitter ARMED` (local colbert copy!).
3. **Socket liveness**: `ss -xlpn` does NOT show rootless-podman container UNIX sockets (userns quirk) — `ss` output is NOT evidence of a dead socket. Probe the file directly with the status command (see `references/embed-consolidation-http-only.md`). Socket file mtime is also NOT a liveness signal (rebind can keep old mtime).
4. **In-container backend probe**: `podman exec systemd-mazemaker-dream-worker python3 -c "from embed_provider import EmbeddingProvider; print(type(EmbeddingProvider('auto').backend).__name__)"` → must print `HttpEmbeddingBackend` after a consolidation.

## Full Consolidation Design
See `references/embed-consolidation-http-only.md`: current-state VRAM table, Option A (HTTP-only) rollout steps with exact file/env names, rollout order protecting a running dream cycle, verification checklist, rollback (image tag backup), and optional phase 2 (HTTP /recall endpoint to also dedupe recall tensors).

## Pitfalls
- **Dream-worker cycle errors are non-fatal**: the dream_worker loop catches per-cycle exceptions (`cycle #N failed`) and continues; only the STARTUP HttpEmbeddingBackend probe is fatal (covered by Restart=on-failure + RestartSec=60).
- **Graceful dream stop**: `systemctl --user stop mazemaker-dream.target` (BindsTo → SIGTERM finishes current phase, phases commit individually; StopTimeout 150 < TimeoutStopSec 180). Never `podman kill` mid-cycle.
- **Image tags**: dream-worker runs `localhost/mazemaker-v2-mcp:gpu`; mcp runs `:latest`. Rebuilds via `build-all-locked.sh` tag `registry.mazemaker.dev/...` — manual retag to localhost names required. Tag a backup (`:gpu-before-embed-http`) before rebuilding.
- **ColBERT fallback silently re-adds VRAM**: if `/embed_colbert` is unreachable/501, colbert_helper loads a local in-process bge-m3 (~1.4 GB, gated on >1800 MiB free). After any worker restart, verify colbert logs still show the worker path.
- **Socket bind fights**: multiple processes constructing `SentenceTransformerBackend()` without `EMBED_CLIENT_ONLY` race to bind the socket; stale-file unlink+rebind cycles observed (server died twice in one day). The HTTP-only topology eliminates this class entirely.
