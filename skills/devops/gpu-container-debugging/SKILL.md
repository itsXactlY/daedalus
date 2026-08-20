---
name: gpu-container-debugging
description: "Use when GPU containers show active but CUDA ops fail OOM"
version: 1.0.0
author: Daedalus Agent
license: MIT
platforms: [linux]
metadata:
  daedalus:
    tags: [gpu, cuda, vram, podman, containers, debugging, oom]
    related_skills: [systematic-debugging, docker-to-podman-migration]
---

# GPU Container Debugging

## When to Load

- Services show `active` but all GPU operations fail with `CUDA error: out of memory`
- `nvidia-smi` shows GPU nearly full (>90% VRAM used)
- Embedding/inference containers return HTTP 500 but process is running
- Multiple GPU containers share one card and one or more are broken
- Journal shows `torch.OutOfMemoryError` or `CUDA error: out of memory`

## Core Insight

`systemctl --user is-active` only checks if the process is alive, not if it's
functional. A service with a corrupted CUDA context is `active` but completely
broken. **Only functional testing (actually calling the API) reveals the failure.**

## The OOM Cascade Pattern

When multiple GPU-hungry containers share one card, the failure cascade is:

1. External model loads onto GPU, consuming most VRAM
2. Container A starts → loads its model (transient peak during load)
3. Container B tries to use GPU → CUDA OOM
4. Container B returns 500 to Container A
5. Container A's dependent operations all fail
6. Both containers show `active` but are completely broken
7. Corrupted CUDA state persists across all subsequent operations

**Key detail:** Transient GPU peaks during model loading can be 2-3x the steady
state. A model that uses 800 MiB at rest might need 2+ GiB during load (PyTorch
CUDA allocator creates temporary tensors). Check VRAM AFTER warmup completes.

## Diagnostic Sequence

```bash
# 1. Check GPU memory — who's using what
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# 2. Check total VRAM usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits

# 3. Test functional health (not just is-active)
# For pod-internal endpoints, use podman exec with python (minimal images lack curl):
podman exec <container> python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:<port>/<endpoint>',
    data=json.dumps({...}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f'HTTP {resp.status}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
except Exception as e:
    print(f'FAIL: {e}')
"

# 4. Check journal for async OOM traces
journalctl --user -u <service> -n 80 | grep -i 'out of memory\|CUDA error\|OOM'
```

## Fix Sequence

**Order matters.** Restart the downstream GPU dependency first:

```bash
# 1. Stop the competing GPU process
kill <pid>

# 2. Restart the GPU provider service FIRST
systemctl --user restart <gpu-provider-service>
sleep 10  # wait for model to load

# 3. Restart the dependent service
systemctl --user restart <gpu-consumer-service>

# 4. Wait for warmup (some services have multi-minute GPU tensor loading)
# 5. Verify with functional tests, not just is-active
```

## Common Pitfalls

- **Don't just restart the failing service.** If Service A depends on Service B
  for GPU, and B's CUDA context is corrupted, restarting A alone won't help.
  Restart B first, then A.

- **`nvidia-smi` shows current state, not peak.** If you check AFTER the OOM,
  the transient peak has passed and everything looks fine. The OOM happened
  during the load window.

- **Async CUDA errors.** `CUDA error: out of memory` is often reported
  asynchronously at a DIFFERENT call site than where the OOM actually happened.
  The stack trace may point to a small allocation — the real culprit was an
  earlier large allocation.

- **Minimal containers lack curl.** Use python's `urllib.request` for HTTP
  calls inside minimal containers (no curl/wget installed).

- **Pod-internal ports not exposed to host.** Services running inside a pod
  network (e.g., port 8766) are not reachable from the host. Use `podman exec`
  into a container that shares the pod network to test them.

## Pattern-Matched Journal Signatures

```bash
# CUDA OOM
if echo "$j" | grep -qE "CUDA error: out of memory|OutOfMemoryError|torch\.OutOfMemoryError"; then
    fail "  └─ root cause: CUDA OOM — GPU VRAM exhausted"
    hint "Another process is likely hogging the GPU. Run: nvidia-smi"
    return
fi

# Embedding service 500 (often caused by GPU OOM)
if echo "$j" | grep -qE "Unexpected embedding error|500 Internal Server Error.*embed"; then
    fail "  └─ root cause: embedding service returning 500 — likely GPU OOM"
    return
fi
```

## VRAM Budget Planning

When deploying multiple GPU containers, calculate the budget:

| Component | Typical VRAM | Notes |
|---|---|---|
| Embedding model (BGE-M3, etc.) | 2-3 GB | Steady state after load |
| Recall/search engine (tensor cache) | 0.5-1 GB | Scales with corpus size |
| Inference model (LLM) | 4-8 GB | Depends on model size |
| Desktop (Xorg, compositor) | 0.3-0.5 GB | If running GUI |
| CUDA context overhead | 0.2-0.5 GB | Per process |
| **Transient peak during load** | **2-3x steady** | PyTorch allocator |

Rule of thumb: keep total steady-state under 70% of VRAM to leave headroom for
transient peaks during model loading.

## Diagnostic Script Enhancement

When writing `debug.sh`-style diagnostic scripts for GPU container stacks:

1. **Add a GPU section** after network checks: nvidia-smi VRAM usage, competing
   process detection (>90% = FAIL, >70% = WARN)
2. **Add functional smoke tests** after service state checks: actually call the
   API endpoints, not just check `is-active`
3. **Add CUDA OOM pattern** to journal analysis: match `CUDA error`, `OutOfMemoryError`
4. **Test pod-internal services** via `podman exec` with python, not host curl

## References

- `references/gpu-vram-contention-cascade.md` — full error transcripts and
  timeline from a a verified incident
