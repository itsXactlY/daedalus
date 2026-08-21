# Bridge /hermes/mcp 500 — root cause analysis 2026-05-29

## Symptom

Architect dashboard M08 (HERMES panel) returns HTTP 500 on `/hermes/mcp`.
Bridge logs: `"GET /hermes/mcp HTTP/1.1" 500 -`
Error body: `{"error": "PyYAML not installed — pip install pyyaml", "type": "RuntimeError"}`

## Root cause

The bridge binary at `~/.local/bin/mazemaker-hermes-bridge` is a **Nuitka --onefile** compiled ELF binary (8.4 MB). It bundles its own Python interpreter but not all pip dependencies.

The build script `bin/build-host-binaries.sh` installs deps inside a `python:3.12-slim` container:

```bash
pip install --no-cache-dir nuitka==2.5.4 setuptools wheel ordered-set \
    httpx tomli requests > /dev/null     # ← pyyaml was MISSING
```

The bridge source has a defensive try/except:

```python
try:
    import yaml as _yaml          # PyYAML — for hermes config.yaml
except ImportError:
    _yaml = None
```

When `_yaml is None`, `_hermes_config()` raises `RuntimeError("PyYAML not installed")`. Every `/hermes/*` endpoint that reads `~/.hermes/config.yaml` crashes.

## Fix

1. Edit `bin/build-host-binaries.sh`: add `pyyaml` to the pip install line
2. Rebuild: `bash bin/build-host-binaries.sh` (runs inside `python:3.12-slim` via podman)
3. Binary grows from ~8.4M → ~9.2M (pyyaml bundled)
4. Deploy to machines:
   - Desk: `install -m 755 dist/host-binaries/mazemaker-hermes-bridge ~/.local/bin/`
   - Tpad: scp to /tmp, then install
   - Backend repo: git commit + push

## Verification

```bash
curl -s http://127.0.0.1:8769/hermes/mcp
# Expected: {"ok": true, "servers": [...], "count": N}
```

## Multi-machine results

| Machine | Before | After | Server count |
|---------|--------|-------|-------------|
| desk    | 500    | 200   | 3           |
| tpad    | 500    | 200   | 1           |

Server count differs per machine based on ~/.hermes/config.yaml MCP server entries.

## Affected endpoints

All `/hermes/*` routes crash when PyYAML is missing:
- `/hermes/config` — full config.yaml view
- `/hermes/mcp` — MCP server list
- `/hermes/status` — composite status (calls _hermes_mcp internally)
- `/hermes/plugins`, `/hermes/skills`, `/hermes/profiles` — unaffected (don't read config)
- `/hermes/env`, `/hermes/auth` — unaffected

## Related

- Build script: `~/projects/mazemaker-v2-stack/backend/bin/build-host-binaries.sh`
- Bridge source: `~/projects/mazemaker-v2-stack/backend/client/pod/hermes-bridge/mazemaker-hermes-bridge.py`
- Systemd unit: `~/.config/systemd/user/mazemaker-hermes-bridge.service`
- Config: `~/.hermes/config.yaml`
- Commit: `e4e0be4`
