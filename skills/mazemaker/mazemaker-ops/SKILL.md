---
name: mazemaker-ops
description: |
  Operational tasks for the Mazemaker backend and its adjacent marketing/content assets.
  Covers VPS administrative operations (rootless pod, SQLite DB, systemd timers, comp-Pro
  grants) AND refreshing a multi-file launch/marketing/docs asset library with live facts
  pulled from the Mazemaker memory graph. Use when the user asks to admin the Mazemaker
  backend or refresh Mazemaker-adjacent launch assets.
---

# Mazemaker Ops

Class-level skill for Mazemaker operational work. The original narrow skills
`mazemaker-backend-admin` and `mazemaker-content-refresh` are absorbed as the two
sections below; their support files live under `references/<source>/`.

## A — Backend administration (absorbed from `mazemaker-backend-admin`)

VPS administrative operations for the Mazemaker backend:

- **Rootless pod** — the backend runs as a rootless container; admin via the pod, not
  the host root.
- **SQLite DB** — schema, backups, and safe in-place edits.
- **systemd timers** — scheduled jobs that drive the backend loops.
- **comp-Pro grants** — request/condition the compute grants the backend needs.

Support: `references/mazemaker-backend-admin/comp-pro-grants-july-2026.md`.

## B — Content / asset refresh (absorbed from `mazemaker-content-refresh`)

Refresh a multi-file launch / marketing / docs asset library for a Mazemaker-adjacent
project, using **LIVE facts pulled from the Mazemaker memory graph** (not stale
assumptions). Use when the operator wants the asset library re-synced with current
graph state.

- `references/mazemaker-content-refresh/launch-asset-pattern.md` — the asset-library
  layout and refresh convention.
- `templates/mazemaker-content-refresh/numbers-crosscheck.md` — cross-check template
  for figures quoted in launch copy.

## C — Direct MCP HTTP queries (fallback when terminal / native tools are broken)

The pod MCP server listens on `127.0.0.1:8765` (endpoint `/mcp`). If the
`terminal` tool or native mazemaker_* tools are unavailable (e.g. terminal fails
with `TypeError: host_cwd` during environment creation), query the pod directly
from `execute_code` with plain Python — stdlib only, no curl, no shell:

```python
import json, urllib.request
URL = "http://127.0.0.1:8765/mcp"
def call(name, args):
    payload = {"jsonrpc":"2.0","id":name,"method":"tools/call",
               "params":{"name":name,"arguments":args}}
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())

s = call("mazemaker_stats", {})
txt = s["result"]["content"][0]["text"]   # JSON string -> json.loads
```

Response shapes (everything arrives as a JSON **string** in `result.content[0].text`):

| Tool | text content |
|---|---|
| `mazemaker_stats` | flat JSON status line: memories, connections, embedding_dim, embedding_backend, retrieval_mode, lazy_graph, hnsw_enabled |
| `mazemaker_browse` | **dict** `{"memories": [...], "count": N}` — iterate `data["memories"]`, NOT the text itself (parsing it as a list fails with `'str' object has no attribute 'get'`) |
| `mazemaker_recall` | hits array; each hit has id, label, content, similarity |

Pitfalls:
- Always `json.loads` the text before touching fields.
- Timeout 90s — recall over 200k memories takes a while.
- Works even when the shell/terminal layer is down; pure stdlib, no deps.

## See also

- `maze-crew-iteration` — the visualization iteration loop (separate concern).
- `marketing/mazemaker-content-refresh` is the live asset set this refreshes.
