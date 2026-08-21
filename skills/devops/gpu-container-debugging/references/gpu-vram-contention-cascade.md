# GPU VRAM Contention Cascade — Mazemaker Stack Incident

**Date:** 2026-08-02  
**Hardware:** RTX 4060 Ti, 16 GB VRAM  
**Root cause:** External model consuming ~12 GB VRAM alongside mazemaker containers

## Symptoms

1. MCP service shows `active` but all tools return `Internal tool execution error`
2. Embedding worker shows `active` but returns HTTP 500 to MCP
3. `mazemaker_recall` fails with `RuntimeError: CUDA error: out of memory` in `_build_gpu_ppr_adjacency`
4. `mazemaker_remember` fails with `httpx.HTTPStatusError: 500 Internal Server Error for url 'http://localhost:8766/embed'`

## Timeline

```
20:34:56  Both MCP and embedding worker containers start
20:34:59  Embedding worker loads BGE-M3 model (~2.3 GB on GPU)
20:35:03  Embedding worker ready
20:37:46  MCP starts GpuRecallEngine.load_from_store() — loads 213,758 vectors
20:38:57  GpuRecallEngine armed (835 MiB tensor on GPU)
20:38:58  Embedding worker tries to embed → CUDA OOM
          "GPU 0 has a total capacity of 15.60 GiB of which 39.75 MiB is free"
          → returns HTTP 500 to MCP
20:39:00  MCP recall/remember all fail with 500 from embed endpoint
20:40:41  Python OutOfMemoryError
20:44:05  PPR fails: RuntimeError: CUDA error: out of memory
          → _build_gpu_ppr_adjacency (torch.sparse_coo_tensor.coalesce)
20:44:12  Same error repeats — corrupted CUDA state persists
```

## Fix Applied

```bash
# 1. External model was stopped by user
# 2. Restart embedding worker first (clean CUDA context)
systemctl --user restart mazemaker-embedding-worker.service
# 3. Wait for BGE-M3 to load (~10s)
# 4. Restart MCP (clean CUDA context + GpuRecallEngine reload)
systemctl --user restart mazemaker-mcp.service
# 5. Wait for GpuRecallEngine (~4 min)
# 6. Verified: nvidia-smi shows ~3.3 GB used, recall works
```

## Key Diagnostic Commands Used

```bash
# GPU memory per process
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# Test embedding worker (pod-internal, no curl in container)
podman exec systemd-mazemaker-mcp python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:8766/embed',
    data=json.dumps({'texts':['test']}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f'HTTP {resp.status}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
except Exception as e:
    print(f'FAIL: {e}')
"

# Test recall end-to-end
curl -s -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"mazemaker_recall","arguments":{"query":"test","limit":1}}}'
```

## VRAM Budget (RTX 4060 Ti, 16 GB)

| Component | VRAM |
|---|---|
| Embedding worker (BGE-M3) | ~2.3 GB |
| GpuRecallEngine (213K vectors) | ~0.95 GB |
| Desktop (Xorg + picom + browser) | ~0.5 GB |
| **Mazemaker total** | **~3.3 GB** |
| **Available for other models** | **~12 GB** |

## debug.sh Gaps Fixed

Added to `backend/installer/linux/debug.sh`:
1. **GPU section:** nvidia-smi VRAM check, competing process detection
2. **Functional smoke tests:** embedding worker /embed, mazemaker_recall
3. **Journal patterns:** CUDA OOM pattern, embedding worker 500 pattern
