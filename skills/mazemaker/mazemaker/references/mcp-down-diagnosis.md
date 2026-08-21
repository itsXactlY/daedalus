# mcp-down-diagnosis.md — Mazemaker MCP server dead: diagnosis & recovery

## Topology (don't get fooled)
- Hermes `mcp_servers.mazemaker` → `http://127.0.0.1:8765/mcp` (HTTP transport).
- Pod `mazemaker` publishes `:8765` (host) → `mazemaker-wonderland` proxy (inside pod) → forwards `/mcp` to the mcp container's `:8000` (MM_PORT).
- `mazemaker-mcp.service` (Image `localhost/mazemaker-v2-mcp:latest`, `Pod=mazemaker.pod`) is THE MCP server.
- `mazemaker-dream-worker.service` (Image `:gpu`) joins the pod network (NOT a pod member) and shares the pod's `:8765` published surface, but does NOT serve `/mcp`. It runs dream consolidation. Do not confuse it for the server.
- When mcp is dead, these are usually FINE: pgvector, wonderland, license-client, embedding-worker, dream-worker. Only `mazemaker-mcp.service` is blocked.

## Symptom
- `mcp__mazemaker__mazemaker_*` tools absent from the agent's toolset.
- `curl :8765/health` → 200; `curl -X POST :8765/mcp` → 502 `mazemaker-mcp unreachable: All connection attempts failed`.
- `mazemaker-mcp-warmup.service` death-loops: `stats status=502 — engine not ready yet`.

## Diagnostic (copy-paste)
```bash
# 1. Is the service looping / preflight-failing?
systemctl --user status mazemaker-mcp.service        # activating (auto-restart), ExecStartPre exit 1
journalctl --user -u mazemaker-mcp.service -n 20     # ERROR: engine source changed since image build (image=X expected=Y)

# 2. Proxy up but engine down? (the 502 signature)
curl -fsS -m5 http://127.0.0.1:8765/health           # 200
curl -fsS -m8 -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"p","version":"1"}}}'   # 502

# 3. Compare baked image label vs live Pro source fingerprint
podman image inspect localhost/mazemaker-v2-mcp:latest --format '{{index .Config.Labels "org.mazemaker.engine_sha"}}'
podman image inspect localhost/mazemaker-v2-mcp:gpu   --format '{{index .Config.Labels "org.mazemaker.engine_sha"}}'
bash /home/alca/.mazemaker/bin/engine-sha.sh /home/alca/projects/mazemaker-pro/python   # Pro tree (tier=pro) — MUST match for gate to pass
# If image label != Pro-source fingerprint → that is the gate failure.
# (The free tree ~/projects/mazemaker/python hashes to a DIFFERENT sha and is irrelevant to the gate.)
```

## Root cause
`mazemaker-mcp-preflight` (ExecStartPre) hashes the engine source and compares to the image's `org.mazemaker.engine_sha` label. Two checks:
1. Tier: db.toml=postgres but image lacks `postgres_store.so` → block (never valid).
2. Staleness: live engine fingerprint != baked label → block (exit 1).
The image was built (e.g. 2026-07-10) from an OLDER Pro commit; Pro source advanced since; so every mcp restart hits the gate and the container never starts. Recurs whenever Pro source is committed without a rebuild.

## Fix
```bash
cd /home/alca/projects/mazemaker-v2-stack/backend
bash bin/build-all-locked.sh --only=mcp        # rebuilds :latest + :gpu locally from MAZEMAKER_PRO_ENGINE_SRC (~/projects/mazemaker-pro/python); bakes engine_sha = current Pro fingerprint. NO --push → no registry needed. Nuitka + C++ libmazemaker.so compile: 10–25 min.
systemctl --user restart mazemaker-mcp.service   # preflight passes → container starts → :8000 up
# verify 200:
curl -fsS -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"p","version":"1"}}}'
```

## Re-register tools in the live agent (separate step)
The running Hermes gateway (`hermes-gateway.service`, MainPID from `~/.hermes/gateway.pid`) loaded `mcp_servers` at startup — with mcp down, the 31 tools are NOT registered even after the server returns. Restart the gateway to re-discover:
```bash
systemctl --user restart hermes-gateway.service   # drops current session — expected
```
Do this LAST, after the build + mcp restart + `/mcp` 200 verification.

## Pitfalls
- Pro vs Free source trap: preflight hashes `~/projects/mazemaker-pro/python` (Pro) when tier=pro; the public `~/projects/mazemaker/python` is a different repo with a different sha. Rebuild from the Pro tree only (`build-all-locked.sh` does this automatically).
- Rebuilding `:gpu` does NOT kill the running dream-worker (it keeps the old image by ID until restarted).
- Build needs network for base image layers + pip; runs locally, no registry push without `--push`.
- The restart loop counter climbing into the hundreds is benign (failing closed); the fix is the rebuild, not stopping the loop.
