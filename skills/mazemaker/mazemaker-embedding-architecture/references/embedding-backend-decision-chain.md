# Embedding backend decision chain — full diagram (audit 2026-08-07)

Verified against `/home/alca/projects/mazemaker-pro/python/embed_provider.py` (1741
lines), `colbert_helper.py`, `memory_client.py`, `dream_worker.py`, and
`/home/alca/projects/mazemaker-v2-stack/backend/client/quadlet/*.container` +
`client/pod/{embedding-worker,mazemaker,wonderland}/`.

## Decision chain

```
EmbeddingProvider(backend=…)
│
├─ EMBED_BACKEND env set? (embed_provider.py:1429, 1484)
│   ├─ sentence-transformers|st|sbert → SentenceTransformerBackend() ──┐
│   └─ fastembed                       → FastEmbedBackend()  (direct load,
│                                        ONNX e5-large; NEVER uses socket)
│
├─ backend == "http"? (only explicit; v2-pod memory.py:158 hardcodes "http")
│   └─ HttpEmbeddingBackend → POST {MM_EMBEDDING_WORKER_URL|:8766}/embed
│        (dense embeddings from embedding-worker; no local model)
│
└─ backend == "auto" → _auto_detect (embed_provider.py:1464):
    1. EMBED_BACKEND override (above)
    2. EMBED_NO_SHARED unset AND socket reachable? (SharedEmbedClient, 5x
       backoff 0.2→3.2s; FileNotFound/ConnectionRefused fail FAST)
         yes → CLIENT mode: no model in this process, socket proxy
         no  ↓
    3. EMBED_CLIENT_ONLY=1?
         yes → HARD RAISE ("refusing to spawn a redundant model copy.
               Start mazemaker-embedding-worker.service first")
         no  ↓
    4. SharedEmbedServer.start() (EMBED_SOCKET, EMBED_MODEL=BAAI/bge-m3,
       GPU-first: EMBED_GPU_WAIT_S=300, MAZEMAKER_DEVICE_STRICT=1 default)
         yes → THIS process loads bge-m3 directly (~2.4 GB VRAM) and is the
               server; dream_worker additionally attaches its GpuRecallEngine
               (dream_worker.py:209-223) → socket serves embed + recall cmds
         no  ↓
    5. Direct load (SentenceTransformer/FastEmbed/Hash) — only when
       EMBED_CLIENT_ONLY unset (ad-hoc/standalone)

ColBERT channel (MM_COLBERT_ENABLED=1 AND has_feature("colbert"),
memory_client.py:1517-1519):
  encode_tokens() → _worker_tokens() → POST {MM_EMBEDDING_WORKER_URL}/embed_colbert
      ├─ 200 → tokens from embedding-worker (NO second model)
      ├─ 501 → _worker_colbert=False → _load_once(): in-process bge-m3
      │        (~1.4 GB VRAM, cached as fallback)
      └─ unreachable → same local fallback
```

## Roles in the v2 pod

| Container | Env (quadlet) | Embeddings come from | Recall engine |
|-----------|---------------|----------------------|---------------|
| embedding-worker (8766) | EW_PORT=8766, EW_HOST=0.0.0.0, MAZEMAKER_EMBEDDING_TOML, HF_HOME | holds bge-m3 itself (if provider=sentence-transformers); serves /embed + /embed_colbert | none |
| dream-worker | EMBED_BACKEND=sentence-transformers, EMBED_MODEL=BAAI/bge-m3, EMBED_SOCKET=/root/.mazemaker/sockets/embed.sock, NO EMBED_CLIENT_ONLY; sockets dir + HF cache bind-mounted; --pod=mazemaker | its OWN socket server (it IS the server) | canonical GpuRecallEngine attached to socket (~13 GB arm) |
| mcp | EMBED_BACKEND= (empty), EMBED_SOCKET set, EMBED_CLIENT_ONLY=1, sockets dir mounted | HTTP /embed (memory.py passes embedding_backend="http") | arms its OWN local GpuRecallEngine (~12 GB) — tier-1 remote never engages (see pitfall) |
| wonderland | — | HTTP /embed (embed_client.py; plaintext BEFORE AES encryption; socket documented as "stale v1 leftover") | none |
| host/plugin (hermes) | config embedding_backend: auto | socket client → server spawn → direct load | local engine |

## Why the dream-worker loads its own bge-m3 (the "two bge" question)

1. It is the DESIGNATED SharedEmbedServer host: quadlet forces
   `EMBED_BACKEND=sentence-transformers` without `EMBED_CLIENT_ONLY`, and the socket
   dir is bind-mounted — so at boot it finds no server and becomes one. A socket
   server must physically hold the model.
2. The HTTP worker on 8766 offers embeddings only — no GpuRecallEngine. The
   dream-worker needs the recall engine for its cycles and serves it to client pods
   over the same socket (RemoteGpuRecallClient), which requires the model in-process.
3. ColBERT tokens are NOT the reason: since 2026-07-08 colbert_helper dedups via
   `/embed_colbert` on the HTTP worker (pod network makes localhost:8766 reachable);
   INCIDENTS.md shows `POST /embed_colbert 200 OK` from the dream-worker's journal.

## Env vars controlling the choice

- `EMBED_BACKEND` — hard override (sentence-transformers|st|sbert|fastembed); empty
  string = no override (mcp quadlet sets `EMBED_BACKEND=` deliberately).
- `embedding_backend=` kwarg — "http" → HttpEmbeddingBackend; "auto" → _auto_detect.
- `EMBED_CLIENT_ONLY=1` — client-only contract: no server spawn, no direct load.
- `EMBED_NO_SHARED` — disable shared-server path entirely.
- `EMBED_SOCKET` — default `~/.mazemaker/engine/embed.sock`; containers override to
  `/root/.mazemaker/sockets/embed.sock`.
- `EMBED_MODEL` — default `BAAI/bge-m3` (1024d, max_seq_length capped 2048 engine /
  512 worker).
- `EMBED_DEVICE`, `EMBED_GPU_WAIT_S` (300), `MAZEMAKER_DEVICE_STRICT` (default 1),
  `MAZEMAKER_GPU_MIN_FREE_MB` (2000), `MM_GPU_RECALL_WAIT_S` (30, recall arm only).
- `MM_EMBEDDING_WORKER_URL` — default `http://localhost:8766`.
- `MM_EMBED_TIMEOUT` — socket client default 300, HTTP default 10, colbert 60.
- `MM_COLBERT_ENABLED` — ColBERT channel toggle (AND-ed with Pro license feature).
- `MM_MODEL_DIRS` — extra model snapshot search dirs for colbert_helper.

## Stale/incorrect things seen in the wild (as of 2026-08-07)

- Skill `neural-memory-production-architecture` (older) describes the eject/inject
  cycle and `~/.mazemaker/sockets/embed.sock` as THE socket; the engine default is
  `~/.mazemaker/engine/embed.sock` and eject is removed. Its "SUPERSEDED 2026-05-08"
  note (dream_worker as standalone host) is correct and matches current reality.
- `embed-server.py` (97-line standalone wrapper) passes `idle_timeout=` to
  `SharedEmbedServer.__init__`, which accepts only model_name/device/recall_engine →
  TypeError at startup. It is not deployed in the v2 pod.
- colbert_helper.py header comment "loads its OWN copy of BGE-M3 in-process" is
  pre-2026-07-08; the worker dedup path is tried first now.
