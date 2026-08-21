# Wonderland /mcp Pod Integration — Full Pattern

A reference for any 3D experience (or web app) that needs to display live
data from the running mazemaker pod. The pod is **wonderland** (FastAPI)
serving on `http://127.0.0.1:8765`.

## Endpoints (verified 2026-06-22)

| Method | Path | Status | Returns |
|--------|------|--------|---------|
| `GET`  | `/health`             | 200 | `{status: "ok"}` (or empty `{}`) — liveness |
| `GET`  | `/config/embedding`   | 200 | `{dim, backend, model, ...}` — embedding fingerprint |
| `GET`  | `/dream/cycles`       | 200 | Cycle history (newest first) |
| `POST` | `/mcp`                | 200/405 | JSON-RPC; GET returns 405, only POST works |
| `GET`  | `/manifest`           | 404 | *not implemented* — do not use |
| `GET`  | `/memory/recent`      | 422 | *validation error* — prefer `mazemaker_browse` via /mcp |
| `GET`  | `/memory/{id}`        | 404 | *not implemented* — use `mazemaker_get` via /mcp |

The MCP tool surface (via `POST /mcp` `tools/call`) is the canonical way
to read or write pod state.

## JSON-RPC envelope

**Request** (`POST /mcp` with `Content-Type: application/json`):
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": <number>,
  "params": {
    "name": "mazemaker_recall",
    "arguments": { "query": "dream engine federation", "limit": 8 }
  }
}
```

**Response** (success — note the **double-wrapping**):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"id\":707967,\"label\":\"auto:turn:...\",\"content\":\"Dream Engine: dein System träumt nachts...\",\"similarity\":0.593,\"score\":0.035}, ...]"
      }
    ]
  }
}
```

The tool result lives at `result.content[0].text` and is a **JSON-stringified**
array. You must `JSON.parse(result.content[0].text)` to get the actual data.

**Response** (error):
```json
{ "jsonrpc": "2.0", "id": 1, "error": { "code": -32603, "message": "..." } }
```

## Available MCP tools (live query 2026-06-22)

From `POST /mcp` with `{"method":"tools/list"}`:
- `mazemaker_recall` — `arguments: {query, limit}` — semantic search
- `mazemaker_remember` — `arguments: {content, label, embedding_b64?}` — store memory
- `mazemaker_think` — `arguments: {memory_id, depth}` — graph traversal
- `mazemaker_graph` — `arguments: {limit}` — knowledge graph top edges
- `mazemaker_stats` — `arguments: {}` — `{memories, connections, dim, backend, ...}`
- `mazemaker_dream_stats` — `arguments: {}` — last cycle results
- `mazemaker_prune` — `arguments: {threshold, dry_run}` — decay weak edges
- `mazemaker_browse` — `arguments: {limit, label_prefix?}` — recent memories
- `mazemaker_get` — `arguments: {memory_id}` — single memory by ID
- `mazemaker_dream` — `arguments: {phase?}` — trigger a consolidation cycle
- `mazemaker_health` — `arguments: {}` — pod health
- `mazemaker_supersedes_log` — `arguments: {limit?, since?}` — recent conflict detections

## The full client (browser ESM)

```js
const POD = {
  url:    'http://127.0.0.1:8765',
  online: false,
  health: null,
  stats:  null,
  dream:  null,
  embedding: null,
  browse: [],
  lastRecall: [],
  recallHistory: [],
};

// Mock fallback — keep these numbers close to the live values so the
// UI looks real even when the pod is offline.
const MOCK = {
  memories: 208810,
  connections: 103859,
  dim: 1024,
  backend: 'HttpEmbeddingBackend',
  dream: {
    sessions: 23732, strengthened: 77_200_000, pruned: 21_100_000,
    bridges: 34_700_000, insights: 8_300_000,
  },
  embedding: { dim: 1024, backend: 'HttpEmbeddingBackend', model: 'bge-m3' },
  browse: [
    { id: 826082, label: 'bug:pandoras-box-tdz',  content: 'TDZ fix · let elapsed hoisted' },
    { id: 826068, label: 'fact:pandoras-box',     content: '27 walkable chambers · live pod' },
    { id: 765000, label: 'fact:dream-engine',     content: '29.9M sessions · 167M edges' },
  ],
};

async function podHealth() {
  try {
    const r = await fetch(`${POD.url}/health`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    POD.health = await r.json().catch(() => ({}));
    POD.online = true;
    return true;
  } catch (e) {
    POD.online = false;
    POD.health = false;
    return false;
  }
}

async function mcpCall(tool, args = {}) {
  const r = await fetch(`${POD.url}/mcp`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0', method: 'tools/call', id: Date.now(),
      params: { name: tool, arguments: args },
    }),
  });
  if (!r.ok) throw new Error(`mcp ${tool} → HTTP ${r.status}`);
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || 'rpc error');
  const text = j.result?.content?.[0]?.text;
  return text ? JSON.parse(text) : j.result;
}

async function podInit() {
  if (!await podHealth()) {
    POD.stats = { memories: MOCK.memories, connections: MOCK.connections,
                  embedding_dim: MOCK.dim, embed_fingerprint: 'HttpEmbeddingBackend::1024::offline-mock' };
    POD.dream = MOCK.dream;
    POD.embedding = MOCK.embedding;
    POD.browse = MOCK.browse;
    return false;
  }
  // Parallel fetch — Promise.allSettled so a single failure doesn't block
  const [emb, stats, dream, browse] = await Promise.allSettled([
    fetch(`${POD.url}/config/embedding`).then(r => r.json()),
    mcpCall('mazemaker_stats'),
    mcpCall('mazemaker_dream_stats'),
    mcpCall('mazemaker_browse', { limit: 25 }),
  ]);
  if (emb.status === 'fulfilled')    POD.embedding = emb.value;
  if (stats.status === 'fulfilled')  POD.stats     = stats.value;
  if (dream.status === 'fulfilled')  POD.dream     = dream.value;
  if (browse.status === 'fulfilled') POD.browse    = browse.value || [];
  return true;
}

async function podRecall(query, k = 8) {
  if (!POD.online) {
    return MOCK.browse
      .filter(c => (c.content + ' ' + c.label).toLowerCase().includes(query.toLowerCase()))
      .slice(0, k);
  }
  try {
    const res = await mcpCall('mazemaker_recall', { query, limit: k });
    return (res || []).map(r => ({
      id: r.id, label: r.label, content: r.content,
      similarity: r.similarity, score: r.score,
    }));
  } catch (e) {
    console.warn('[pod] recall failed', e.message);
    return [];
  }
}

// Boot: fire-and-forget so the page paints the splash without waiting
podInit().then(ok => {
  console.info(ok ? '%c[pod] connected ' + POD.url
                  : '%c[pod] offline — mock fallback',
              'color:' + (ok ? '#10b981' : '#f59e0b') + ';font-weight:bold');
});
```

## HUD binding pattern

```js
function fmtN(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return n.toLocaleString('en-US');
  return String(n);
}

function paintHudFromPod() {
  if (POD.stats) {
    document.getElementById('hud-mem').textContent   = fmtN(POD.stats.memories);
    document.getElementById('hud-edges').textContent = fmtN(POD.stats.connections);
    if (POD.stats.embedding_dim)
      document.getElementById('hud-dim').textContent  = POD.stats.embedding_dim;
  } else {
    // Show mock values so the HUD never reads "—"
    document.getElementById('hud-mem').textContent   = fmtN(MOCK.memories);
    document.getElementById('hud-edges').textContent = fmtN(MOCK.connections);
    document.getElementById('hud-dim').textContent   = MOCK.dim;
  }
  const d = POD.dream || MOCK.dream;
  document.getElementById('hud-sessions').textContent     = fmtN(d.sessions);
  document.getElementById('hud-strengthened').textContent = fmtN(d.strengthened);
  document.getElementById('hud-pruned').textContent       = fmtN(d.pruned);
  document.getElementById('hud-bridges').textContent      = fmtN(d.bridges);
  document.getElementById('hud-insights').textContent     = fmtN(d.insights);

  const pill = document.getElementById('hud-pod');
  if (POD.online) {
    pill.textContent = 'connected'; pill.style.color = 'var(--ok)';
  } else if (POD.health === false) {
    pill.textContent = 'offline · mock'; pill.style.color = 'var(--warn)';
  } else {
    pill.textContent = 'connecting…'; pill.style.color = 'var(--text-mute)';
  }
}
paintHudFromPod();  // immediate

// Live poll — every 5s, refresh stats so the dashboard tracks ongoing ingest
setInterval(async () => {
  if (!POD.online) return;
  try { POD.stats = await mcpCall('mazemaker_stats'); paintHudFromPod(); } catch (e) {}
}, 5000);
```

## Debounced live recall with request tagging

```js
let recallReqSeq = 0;
recallInput.addEventListener('input', () => {
  const q = recallInput.value.trim();
  if (!q) { recallResults.innerHTML = ''; return; }
  const req = ++recallReqSeq;
  recallResults.innerHTML = '<div class="k">↳ querying pod at ' + POD.url + '…</div>';
  clearTimeout(recallInput._t);
  recallInput._t = setTimeout(async () => {
    const hits = await podRecall(q, 8);
    if (req !== recallReqSeq) return;   // a newer query superseded this one
    POD.lastRecall = hits;
    POD.recallHistory.unshift({ q, hits, t: Date.now() });
    if (POD.recallHistory.length > 20) POD.recallHistory.pop();
    recallResults.innerHTML = hits.length
      ? hits.map(h => `<div class="hit"><span class="lbl">id=${h.id} · sim=${(h.similarity||0).toFixed(3)} · ${h.label||''}</span><span>${h.content||''}</span></div>`).join('')
      : '<div class="k">no hits · try: dream · recall · federation</div>';
  }, 180);
});
```

The `recallReqSeq` monotonic counter is the **debounce-of-debounce**. If
the user types "d", "dr", "dre" in rapid succession, the third call's
`recallReqSeq === 3`, and the first two `setTimeout` callbacks
early-return when their (slower) response lands. Without it, out-of-order
responses overwrite fresh ones.

## CORS / same-origin considerations

The pod at `127.0.0.1:8765` is **loopback-only**. If the HTML page is
served from a different origin (e.g. `https://mazemaker.online`), the
browser will block the cross-origin fetch unless the pod sends the
right CORS headers.

For a self-hosted pod on the same machine: serve the HTML from a
local server (`python3 -m http.server 9017`) and the page is on
`http://127.0.0.1:9017` — same origin as the pod's `127.0.0.1:8765`
iff you also set the pod's CORS allow-origin to `http://127.0.0.1:9017`.
For development, browsers treat `127.0.0.1` as a secure origin and
may allow the fetch even without explicit CORS — but this is fragile
and should not be relied on in production.

If the pod returns 403/CORS errors, the diagnostic is:
```js
fetch('http://127.0.0.1:8765/health').then(r => console.log('status', r.status))
  .catch(e => console.error('CORS or network error:', e.message));
```

## Verification recipe

After wiring pod integration, walk through this checklist:

```bash
# 1. Pod is running
curl -s -o /dev/null -w "health: %{http_code}\n" http://127.0.0.1:8765/health

# 2. MCP works
curl -s -X POST http://127.0.0.1:8765/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":1,"params":{"name":"mazemaker_stats","arguments":{}}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('memories:', json.loads(d['result']['content'][0]['text'])['memories'])"

# 3. HTML page serves
cd /path/to/architect && python3 -m http.server 9017
curl -s -o /dev/null -w "page: %{http_code} · %{size_download} bytes\n" \
  http://127.0.0.1:9017/pandoras-box.html
```

In the browser:
1. Open DevTools console — expect `[pod] connected http://127.0.0.1:8765` in green
2. HUD `#hud-pod` reads `connected` in green (or `offline · mock` in amber if pod is down)
3. HUD `#hud-mem` reads a number that matches `mazemaker_stats.memories` for the current pod
4. Type into the recall input — after 180ms + network, hits appear with real IDs and similarity scores
5. Test offline: stop the pod, reload — page still works, HUD shows mock numbers in amber

## Common failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Console: `TypeError: Cannot read properties of null (reading 'content')` | `result` is `null` because MCP returned an error envelope | Check `j.error` first; fall back to mock |
| HUD shows `—` forever | `paintHudFromPod()` not called or DOM IDs don't match | Verify element IDs, call `paintHudFromPod()` immediately at module load |
| Recall returns no hits | Query too specific or `POD.online` is false | Test offline path with mock fallback; lower the similarity threshold |
| Browser blocks fetch as CORS error | Pod origin differs from page origin | Serve page from same `127.0.0.1` or add CORS allow-origin to pod |
| Recall shows stale results after rapid typing | No `recallReqSeq` guard | Add monotonic counter, early-return on mismatch (see above) |
