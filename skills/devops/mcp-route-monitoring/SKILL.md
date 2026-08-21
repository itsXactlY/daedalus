---
name: mcp-route-monitoring
description: "Build/run a monitor proving WHICH MCP server routes Daedalus tool calls — config parse, live initialize handshake, listener-owner resolution, cron alerting."
category: devops
---

# MCP route monitoring — prove who routes your MCP calls

## Trigger
- User asks "who routes your MCP calls" / "monitor MCP routing" / "is my MCP call hitting the local pod or something else?"
- Need to verify an MCP endpoint is local (podman pod, not a third party) and stays up.
- Want cron alerting when an enabled MCP server goes down or the route changes.

## Working reference implementation
`~/.hermes/scripts/mcp-route-monitor.py` (run with `~/.hermes/venv/bin/python`).
Log: `~/.hermes/logs/mcp-route.log`. Cron job: "MCP route monitor" (job id 8c0a75f9d734, every 6h, deliver origin) — created 2026-08-11.

Verified output (2026-08-11):
```
[mazemaker] OK url=http://127.0.0.1:8765/mcp server=mazemaker v2.0.0 18ms owner=passt.avx2 (pid 1374485) container=? via-podman=mazemaker-infra
[btquant] DISABLED (transport=http, url=http://127.0.0.1:8910/mcp)
```

## Build steps
1. **Parse `mcp_servers` from `~/.hermes/config.yaml`** (naive line scan is fine — no PyYAML needed):
   - Enter block on `^mcp_servers:`; exit on the first line that is non-empty and does NOT start with a space (next top-level key).
   - Server entries: `^  name:` (exactly 2 spaces). Nested keys: `^    enabled|transport|url:` (4 spaces).
   - CRITICAL PITFALL: other top-level blocks follow `mcp_servers:` in config.yaml (e.g. `session_reset:` with sub-keys `mode:`, `at_hour:`). Without the "stop at next non-indented line" rule, the parser treats `mode:`/`at_hour:` as MCP servers with no URL → crash `ValueError: unknown url type: '?'`. Also require `not s.startswith("    ")` on the 2-space server regex so 4-space keys don't spawn phantom servers.
2. **Probe each enabled endpoint with a real MCP `initialize` handshake** (not just curl GET — the server only answers POST):
   - POST `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":...,"version":"1.0"}}}` with `Accept: application/json, text/event-stream`.
   - Response is SSE: strip `data:` prefixes, parse the JSON line, read `result.serverInfo` → name + version. Measure latency.
3. **Resolve the listener owner** (`ss -tlnp`):
   - PITFALL: under rootless podman the PID on the port is `passt.avx2` (the port forwarder), NOT the container. PID→container via `podman ps --format "{{.Names}} {{.Pid}}"` gives `container=?`.
   - FIX: also map port→container via `podman ps --format "{{.Names}} {{.Ports}}"` and match `:{port}->` in the Ports column. Append `via-podman=<container>` to the owner line.
4. **Log + exit code for cron**: append timestamped report to the log file; `exit 0` only if ALL enabled servers respond, `exit 1` otherwise (cron prompt can branch on it).
5. **Schedule**: `cronjob` action=create, schedule `every 6h`, deliver `origin`, prompt says: run the script; if exit 0 reply one compact line `🟢 MCP route OK — ...`; if nonzero reply the FAILED line verbatim with 🔴 and exit code.

## Verification
```bash
~/.hermes/venv/bin/python ~/.hermes/scripts/mcp-route-monitor.py; echo "exit=$?"
tail -3 ~/.hermes/logs/mcp-route.log
```
Expect: one line per configured server, `OK` + server name/version for enabled ones, exit 0.

## Related
- `hermes-mcp-visibility` — different problem (tools invisible under `tool_search=auto`); this skill is about verifying the endpoint/route itself.
- Routing fact: Alice-Router (:8801) is the delegation MODEL, not an MCP router. Hermes MCP calls stay local: hermes client → 127.0.0.1:8765 → passt → mazemaker-infra pod.
