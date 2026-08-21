---
name: mazemaker-dashboard-maintenance
description: Maintain, regenerate, and customize the Mazemaker 3D Dashboard — live server, templates, color scheme, timeline, force layout
triggers:
  - dashboard shows wrong dimension
  - dashboard color scheme update
  - dashboard 4D timeline
  - dashboard restart
  - regenerate dashboard
  - force layout adjustment
---

# Mazemaker Dashboard Maintenance

## Architecture

```
tools/dashboard/
├── generate.py          # Static dashboard generator (template.html → ~/neural_memory_dashboard.html)
├── live_server.py       # FastAPI live dashboard (localhost:8443, WebSocket updates)
├── template.html        # Static template (used by generate.py)
├── template-live.html   # Live template (served by live_server.py)
└── .certs/              # Self-signed TLS certs (auto-generated)
```

**Live Server** runs via systemd:
```bash
systemctl --user restart neural-dashboard.service
journalctl --user -u neural-dashboard.service --no-pager -n 10
```

**Static Dashboard:** `~/.hermes/venv/bin/python generate.py` → `~/neural_memory_dashboard.html`

## Critical: No Hardcoded Dimensions

**NEVER** hardcode `EMBEDDING_DIM = NNNN` in generate.py or live_server.py. Always read from DB:

```python
# SQLite
cur.execute("SELECT length(embedding) FROM memories WHERE embedding IS NOT NULL LIMIT 1")
emb_row = cur.fetchone()
actual_dim = (emb_row[0] // 4) if emb_row else 1024

# MSSQL
cur.execute("SELECT TOP 1 vector_dim FROM memories WHERE embedding IS NOT NULL")
dim_row = cur.fetchone()
mssql_dim = dim_row[0] if dim_row else 1024
```

After any embedding change (backend swap, re-embedding, model upgrade), the dashboard auto-detects the new dimension.

## Dashboard Color Scheme (Cyberpunk Neon)

Both templates use CSS variables. To restyle, update `:root` in template-live.html:

```css
:root {
    --bg: #030305;              /* void black */
    --surface: rgba(10, 15, 20, 0.92);
    --border: rgba(0, 243, 255, 0.12);
    --amber: #00f3ff;           /* primary accent (neon blue) */
    --amber-dark: #00b8cc;
    --amber-glow: rgba(0, 243, 255, 0.35);
    --red: #ff003c;             /* neon red */
    --green: #ccff00;           /* acid green */
    --purple: #bc13fe;          /* neon purple */
}
```

Also update hardcoded colors in JS:
- Graph link color: `rgba(0,243,255,${...})`
- Category colors: `'Conversation': '#00f3ff'`, `'Session': '#ff003c'`, etc.
- Plotly chart colors, tooltip borders, node labels

## CRT Scanline Overlay

```css
body::after {
    content: '';
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background:
        linear-gradient(rgba(18,16,16,0) 50%, rgba(0,0,0,0.15) 50%),
        linear-gradient(90deg, rgba(255,0,0,0.03), rgba(0,255,0,0.01), rgba(0,0,255,0.03));
    background-size: 100% 2px, 3px 100%;
    pointer-events: none; z-index: 999; opacity: 0.3;
}
```

## Force-Directed Layout (Anti-Clump)

After graph initialization, configure D3 forces:

```javascript
Graph
  .d3Force('link', Graph.d3Force('link')
    .distance(link => {
      const w = link.weight || 0.5;
      return 10 + (1 - w) * 120;  // weight=1.0 → 10px, weight=0.0 → 130px
    })
    .strength(link => {
      return 0.3 + (link.weight || 0.5) * 0.7;
    })
  )
  .d3Force('charge', Graph.d3Force('charge')
    .strength(-80)
    .distanceMax(500)
  )
  .d3Force('center', Graph.d3Force('center')
    .strength(0.05)
  );
```

- High weight connections → nodes close together
- Low weight → nodes spread apart
- Charge repulsion prevents clumping
- Weak center force lets clusters breathe

## 4D Timeline (Temporal Graph Evolution)

The timeline bar lets you watch the knowledge graph grow chronologically.

**Requirements:**
- `created_at` field in node data (from `memories.created_at`)
- `dream_sessions` in data payload (for purple markers)
- Sorted nodes/edges by creation time

**Toggle button:** `⏳` in controls (purple)

**Features:**
- Scrubber bar with click/drag
- Auto-play (50ms interval, 0.5% steps)
- Dream session markers (purple bars on track)
- Stats display: `nodes / edges` count
- Date label in German locale
- Space key for play/pause when open

**Server-side:** `live_server.py` must include `created_at` in SELECT and `dream_sessions` in return data:

```python
cur.execute("SELECT m.id, ..., m.created_at, ... FROM memories m ...")
# ...
dream_sessions = []
try:
    cur.execute("SELECT id, phase, started_at, completed_at, stats FROM dream_sessions ORDER BY started_at")
    for r in cur.fetchall():
        dream_sessions.append({"id": r[0], "phase": r[1], "started_at": r[2], "completed_at": r[3], "stats": r[4]})
except Exception:
    pass
```

## Restart Button

**API endpoint** in `live_server.py`:
```python
@app.post("/api/restart")
async def api_restart():
    import subprocess
    subprocess.Popen(["systemctl", "--user", "restart", "neural-dashboard.service"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"status": "restarting"}
```

**Button** in controls: `⟳` (red), calls POST `/api/restart`, shows ⏳→✓→reload(3s).

## Regenerate Static Dashboard

```bash
cd ~/projects/mazemaker/tools/dashboard
~/.hermes/venv/bin/python generate.py
cp ~/neural_memory_dashboard.html ~/The\ Architects\ Palace/neural_memory_dashboard.html
```

## Pitfalls

- **`~/sd-venv/` does NOT have fastembed** — use `~/.hermes/venv/` for generate.py
- **Live server caches in memory** — restart service after template/code changes
- **Bottom UI elements** must be shifted up 48px when timeline is present (controls: `bottom: 60px`, mini-charts: `bottom: 60px`)
- **Node `created_at`** must be included in both SQL SELECT and JS node mapping
- **Dream sessions** table may not exist on fresh installs — always wrap in try/except
