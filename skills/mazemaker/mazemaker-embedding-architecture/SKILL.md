---
name: mazemaker-embedding-architecture
description: When debugging Mazemaker embedding backend choice.
version: 1.0.0
tags: [mazemaker, embeddings, bge-m3, shared-embed-server, embedding-worker, env-knobs]
priority: high
created: 2026-08-07
---

# Mazemaker Embedding Architecture — Backend Selection

How Mazemaker chooses WHERE the embedding model lives. Three competing paths exist
(SHARED UNIX-socket server / HTTP worker on 8766 / in-process direct load); the
choice is env-var driven and differs per container. Misreading it produces the two
classic incidents: "two bge-m3 copies in VRAM" and "recall silently on CPU".

Source of truth: `/home/alca/projects/mazemaker-pro/python/embed_provider.py`,
`colbert_helper.py`, `memory_client.py`; deployment:
`/home/alca/projects/mazemaker-v2-stack/backend/client/quadlet/*.container` +
`client/pod/{embedding-worker,mazemaker,wonderland}/`.

## The three paths

1. **UNIX-socket SharedEmbedServer** (`embed_provider.py:56`): the FIRST process
   constructing `SentenceTransformerBackend()` with no reachable server becomes the
   server — loads BGE-M3 (~2.4 GB VRAM, `EMBED_MODEL`, default `BAAI/bge-m3`) and
   serves length-prefixed JSON over `EMBED_SOCKET` (engine default
   `~/.mazemaker/engine/embed.sock`). Can additionally host the canonical
   `GpuRecallEngine` (`attach_recall_engine`) → serves `recall`/`recall_batch` too.
2. **HTTP worker on 8766** (`HttpEmbeddingBackend`, `embed_provider.py:1298`):
   POST `{MM_EMBEDDING_WORKER_URL|http://localhost:8766}/embed`. Chosen ONLY via
   explicit `embedding_backend="http"` or by direct `MM_EMBEDDING_WORKER_URL`
   consumers (wonderland pre-embed, colbert_helper). **NOT in `_auto_detect`** —
   never an automatic fallback. The worker itself (`embedding-worker/main.py`,
   FastAPI/uvicorn) is the only provider-switching service (embedding.toml +
   compute.toml/JWT overlay): fastembed / sentence-transformers (bge-m3, has
   `/embed_colbert`) / cloudflare / jina / openai / voyage / together.
3. **Direct load**: fallback when server start fails AND `EMBED_CLIENT_ONLY`
   unset; `FastEmbedBackend` (ONNX, intfloat/multilingual-e5-large) NEVER uses the
   socket.

## Decision chain (embedding_backend="auto")

`EMBED_BACKEND` env override (sentence-transformers|st|sbert|fastembed) wins over
everything → else: socket client reachable? → client mode (no local model).
No server → `EMBED_CLIENT_ONLY=1`? → HARD RAISE ("refusing to spawn a redundant
model copy; start mazemaker-embedding-worker.service") → else become the server →
else direct load. `_auto_detect` order: EMBED_BACKEND > socket > CUDA ST (GPU-first,
NO fallback on failure) > FastEmbed > MPS > CPU ST > hash.

## Env knobs (quick map)

| Var | Effect |
|-----|--------|
| `EMBED_BACKEND` | forces in-process backend (st/sbert/fastembed) |
| `embedding_backend="http"` | forces HTTP worker (pod memory.py hardcodes this) |
| `EMBED_CLIENT_ONLY=1` | never spawn server, never direct-load; raise if socket dead |
| `EMBED_NO_SHARED` | disable the whole socket path |
| `EMBED_SOCKET` | socket path (containers: `/root/.mazemaker/sockets/embed.sock`) |
| `EMBED_MODEL` | model name, default `BAAI/bge-m3` |
| `EMBED_GPU_WAIT_S` / `MAZEMAKER_DEVICE_STRICT` | GPU-first wait (300s) + no silent CPU degrade; same knobs in worker `backends.py` |
| `MM_EMBEDDING_WORKER_URL` | HTTP worker base URL, default `http://localhost:8766` |
| `MM_EMBED_TIMEOUT` | HTTP/socket timeouts |
| `MM_COLBERT_ENABLED` (+ Pro `has_feature("colbert")`) | ColBERT token channel; gated by license |

## Pitfalls (measured)

- **Eject is dead code**: `eject` cmd removed, `EMBED_IDLE_TIMEOUT` kept for compat
  only. Do not tune "eject after idle" — policy is wait-for-GPU + strict.
- **v2-pod redundancy trap**: mcp quadlet sets `EMBED_CLIENT_ONLY=1` + `EMBED_SOCKET`,
  but `client/pod/mazemaker/memory.py` passes `embedding_backend="http"` → tier-1
  remote recall (`memory_client.py` ~1561) never engages (HTTP backend has no socket
  client with `recall_status`) → mcp still arms its own ~12 GB GpuRecallEngine next
  to dream-worker's ~13 GB. This IS the "redundant arm" in the quadlet OOM comments.
- **ColBERT dedup**: `colbert_helper._worker_tokens()` tries
  `{MM_EMBEDDING_WORKER_URL}/embed_colbert` first; only on 501/unreachable does it
  load a second in-process bge-m3 (~1.4 GB). Old design comments saying "loads its
  OWN copy" predate the 2026-07-08 dedup.
- **dream-worker owns the socket server**: quadlet env `EMBED_BACKEND=sentence-transformers`,
  `EMBED_SOCKET=/root/.mazemaker/sockets/embed.sock`, NO `EMBED_CLIENT_ONLY` → it
  becomes the SharedEmbedServer host and attaches its GpuRecallEngine. It still uses
  HTTP for colbert tokens (pod network makes `localhost:8766` reachable).
- **embed-server.py standalone wrapper is broken by drift**: passes
  `idle_timeout=` kwarg that `SharedEmbedServer.__init__` doesn't accept → TypeError.
  Not deployed in v2 pod; dream-worker fills the role.
- Socket dir must be bind-mounted for cross-container use; HTTP works over the pod
  network without mounts (wonderland documents the socket as "stale v1 leftover").

Full flow diagram + per-container env table:
`references/embedding-backend-decision-chain.md`.
