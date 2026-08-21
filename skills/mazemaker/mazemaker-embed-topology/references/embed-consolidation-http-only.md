# Single-bge Consolidation Design (Option A: HTTP-only) — 2026-08-07

Goal: exactly ONE bge-m3 in VRAM on the 16 GB card (was 15473/16380 MiB used).

## Current VRAM attribution (measured)
```
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
2458366, python,   2392 MiB   # embedding-worker — bge-m3, canonical HTTP server
2577269, python3,  5668 MiB   # dream-worker — OWN bge-m3 (UNIX-socket server) + GpuRecallEngine tensor (215134 vec)
2824999, python,   2260 MiB   # mcp — NO bge; own recall tensor ("GPU recall ARMED (load_from_store)")
2827835, /opt/llm/llama-server, 4460 MiB   # AFE Stage C — stays
```
PID→container mapping: `podman ps --format '{{.Names}} {{.Pid}}'` (host PIDs).

## Why HTTP-only wins
- mcp + wonderland + colbert_helper ALREADY use HTTP (log-proven; ~850 colbert
  calls/day through the worker, all 200 OK). The socket server has NO external
  clients — it died twice and re-bound at 09:20:44 in one day (fragile legacy).
- Loopback HTTP adds <5 ms; same GPU/inference; ColBERT cycle already runs over HTTP.

## Changes (exact)
1. **embed_provider.py — BOTH dispatch points** (in the dream-worker image source):
   - `EmbeddingProvider.__init__` forced-branch (~line 1429):
     `if forced == 'http': self.backend = HttpEmbeddingBackend(); print(...); return`
   - `_auto_detect` forced-branch (~line 1484): `if forced == 'http': return HttpEmbeddingBackend()`
   - Rebuild ONLY the `localhost/mazemaker-v2-mcp:gpu` image (dream-worker's
     image). Do NOT touch `:latest` (mcp runs it). Backup tag FIRST:
     `podman tag localhost/mazemaker-v2-mcp:gpu localhost/mazemaker-v2-mcp:gpu-before-embed-http`
2. **Drop-in** `~/.config/containers/systemd/mazemaker-dream-worker.container.d/embed-http.conf`:
   ```
   [Container]
   Environment=EMBED_BACKEND=http
   Environment=EMBED_CLIENT_ONLY=1
   ```
   (EMBED_CLIENT_ONLY=1 → any stray `SentenceTransformerBackend()` construction
   raises instead of loading — the hard guarantee of no 2nd bge.)
   Also add `'--embedding-backend','http'` to the Exec line in the main unit
   (belt + suspenders: env-only is NOT enough without the code patch, see gotcha).
3. `systemctl --user daemon-reload` (quadlet regenerates; takes effect on next start).

## Rollout order (protects running dream cycle + Claude's build)
1. Stop dream at a phase boundary: `systemctl --user stop mazemaker-dream.target`
   (BindsTo → graceful SIGTERM → "finishing current phase", phases commit
   individually; StopTimeout 150 < TimeoutStopSec 180). Wait for log
   "dream daemon stopped after N cycles". Never `podman kill` mid-cycle.
2. `systemctl --user restart mazemaker-dream-worker` (Pull=never → local :gpu image).
3. Check logs BEFORE resuming: `journalctl --user -u mazemaker-dream-worker -n 50`
   must show `HttpEmbeddingBackend → http://localhost:8766 (BAAI/bge-m3, 1024d)`
   and NO `[embed-server] Listening` / `Loading ... on cuda`.
4. `systemctl --user start mazemaker-dream.target`.
5. After ≥1 full cycle: `rm ~/.mazemaker/sockets/embed.sock` (stale, no listener);
   drop socket mounts / `EMBED_SOCKET` / `EMBED_CLIENT_ONLY` from units at the
   next regular refresh (mcp's copies are inert — it uses HTTP).

mcp and embedding-worker are NOT restarted → Claude's MCP session and llama-server unaffected.

## Verification
- `nvidia-smi --query-compute-apps=...`: dream-worker PID drops 5668 → ~2.5–3.2 GB
  (recall tensor + CUDA ctx, NO bge). Exactly ONE ~2392 MiB python process
  (embedding-worker). Expected total ≈ 11.9 GB → ~4.4 GB free.
- Dream-worker logs show `POST http://localhost:8766/embed` (NEW — before only
  `/embed_colbert`) and colbert still 200 OK.
- Socket probe → ConnectionRefused (expected):
  ```python
  import socket, json, struct
  s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(2)
  s.connect('/home/alca/.mazemaker/sockets/embed.sock')
  msg = json.dumps({'cmd':'status'}).encode()
  s.sendall(struct.pack('!I', len(msg)) + msg)
  print(s.recv(struct.unpack('!I', s.recv(4))[0]).decode())
  ```
- In-container probe:
  `podman exec systemd-mazemaker-dream-worker python3 -c "from embed_provider import EmbeddingProvider; print(type(EmbeddingProvider('auto').backend).__name__)"`
  → must print `HttpEmbeddingBackend` (proves the forced-http patch covers the auto path too).
- One full cycle completes: "cycle #N done in Xs" — duration comparable to before.

## Gotchas learned
- `ss -xlpn` does NOT show rootless-podman container UNIX sockets (userns quirk) —
  direct probe is authoritative. Socket file mtime is NOT a liveness signal
  (rebind on an existing file can keep the old mtime).
- Dream-worker cycle failures are non-fatal: loop logs `cycle #N failed` and
  continues. Only the STARTUP HttpEmbeddingBackend probe is fatal →
  Restart=on-failure + RestartSec=60 covers it.
- If embedding-worker is down at dream-worker start, HttpEmbeddingBackend raises
  (no retry). Optional hardening: `After=mazemaker-embedding-worker.service` in
  the dream-worker unit.
- The embedding-worker has NO idle eject (backends.py differs from the engine's
  embed_provider.py SMART EJECT) — the model stays resident. No eject-timer risk.

## Rollback
Delete the drop-in → `systemctl --user daemon-reload` → restart dream-worker;
restore `:gpu-before-embed-http` tag if the image was rebuilt. <2 min.

## Optional phase 2 (out of scope for "one bge")
mcp's 2260 MiB and dream-worker's tensors are NOT bge — allowed to stay. Adding a
`/recall` endpoint to the embedding-worker HTTP API would let clients drop their
tensors too (~3 GB more free). The RemoteGpuRecallClient-over-socket path exists in
code but was never active in mcp (it constructs HttpEmbeddingBackend, not
SharedEmbedClient).
