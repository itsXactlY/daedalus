# Three.js Living Viz — Advanced Layers (§20 Live Pod + §21 GLSL)

Advanced visual layers, formerly inline in SKILL.md: §20 Live Pod Integration
(Wonderland /mcp JSON-RPC) and §21 Custom GLSL ShaderMaterial for
particle/edge systems. Load with
`skill_view(file_path='references/advanced-layers.md')`.

---

### 20. Live Pod Integration (Wonderland /mcp JSON-RPC)

A 3D scene that visualizes "the mazemaker" should pull live data from the
running pod, not from a hardcoded `CORPUS = { memories: 208810, ... }`
constant. The pod is **wonderland** (FastAPI) at
`http://127.0.0.1:8765`, and it exposes both REST and JSON-RPC surfaces.

| Endpoint | Returns | Used for |
|----------|---------|----------|
| `GET /health` | `{status: "ok"}` or similar | Liveness probe — sets `POD.online` |
| `GET /config/embedding` | `{dim, backend, model}` | Embedding fingerprint in the HUD |
| `GET /dream/cycles` | Cycle history | DREAM ENGINE panel |
| `POST /mcp` | JSON-RPC envelope | The full MCP tool surface (mazemaker_recall, mazemaker_stats, mazemaker_browse, mazemaker_dream_stats, mazemaker_think, mazemaker_graph, mazemaker_remember, ...) |

**The MCP call shape** (`POST /mcp` with a `tools/call` body):

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": <timestamp>,
  "params": { "name": "mazemaker_recall", "arguments": { "query": "dream engine", "limit": 8 } }
}
```

Response is `{jsonrpc, id, result: {content: [{type:"text", text: "<JSON-stringified>"}]}}` —
the tool result is **double-wrapped**: extract `result.content[0].text` and
`JSON.parse()` it to get the actual data. The text-stringification is
specific to wonderland's MCP adapter.

**Standard client pattern** (paste this, then build on top):

```js
const POD = { url: 'http://127.0.0.1:8765', online: false,
              health: null, stats: null, dream: null, embedding: null, browse: [] };

// Mock fallback so the HUD never reads "—" and the world stays walkable when
// the pod is offline. Keep these numbers close to the live values.
const MOCK = {
  memories: 208810, connections: 103859, dim: 1024,
  backend: 'HttpEmbeddingBackend',
  dream: { sessions: 23732, strengthened: 77_200_000, pruned: 21_100_000,
           bridges: 34_700_000, insights: 8_300_000 },
  embedding: { dim: 1024, backend: 'HttpEmbeddingBackend', model: 'bge-m3' },
  browse: [ /* a few recent memory records */ ],
};

async function podHealth() {
  try {
    const r = await fetch(`${POD.url}/health`, { cache: 'no-store' });
    if (!r.ok) throw new Error(r.status);
    POD.health = await r.json();
    POD.online = true;
    return true;
  } catch (e) { POD.online = false; return false; }
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
  if (!await podHealth()) {                       // mock-fallback path
    POD.stats = { memories: MOCK.memories, connections: MOCK.connections,
                  embedding_dim: MOCK.dim };
    POD.dream = MOCK.dream; POD.embedding = MOCK.embedding; POD.browse = MOCK.browse;
    return false;
  }
  // parallel fetch — Promise.allSettled so a single failure doesn't block the rest
  const [emb, stats, dream, browse] = await Promise.allSettled([
    fetch(`${POD.url}/config/embedding`).then(r => r.json()),
    mcpCall('mazemaker_stats'),
    mcpCall('mazemaker_dream_stats'),
    mcpCall('mazemaker_browse', { limit: 25 }),
  ]);
  if (emb.status==='fulfilled')    POD.embedding = emb.value;
  if (stats.status==='fulfilled')  POD.stats     = stats.value;
  if (dream.status==='fulfilled')  POD.dream     = dream.value;
  if (browse.status==='fulfilled') POD.browse    = browse.value || [];
  return true;
}

// Fire-and-forget so the page paints the splash without waiting for the pod.
podInit().then(ok => {
  console.info(ok ? '%c[pod] connected ' + POD.url : '%c[pod] offline — mock fallback', 'color:#10b981;font-weight:bold');
});
```

**HUD wiring** — `paintHudFromPod()` reads `POD.stats` / `POD.dream` and
fills DOM spans. Call it:
1. Once at module load (shows "connecting…" with whatever POD has, even empty)
2. After `podInit()` resolves (repaints with live data)
3. On a 5-second polling interval so values keep flowing in

```js
function fmtN(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n/1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return n.toLocaleString('en-US');
  return String(n);
}

function paintHudFromPod() {
  // memories / edges — fall back to MOCK so the HUD always shows numbers
  if (POD.stats) {
    document.getElementById('hud-mem').textContent   = fmtN(POD.stats.memories);
    document.getElementById('hud-edges').textContent = fmtN(POD.stats.connections);
    if (POD.stats.embedding_dim)
      document.getElementById('hud-dim').textContent  = POD.stats.embedding_dim;
  } else {
    document.getElementById('hud-mem').textContent   = fmtN(MOCK.memories);
    document.getElementById('hud-edges').textContent = fmtN(MOCK.connections);
    document.getElementById('hud-dim').textContent   = MOCK.dim;
  }
  // dream engine — same pattern
  const d = POD.dream || MOCK.dream;
  document.getElementById('hud-sessions').textContent     = fmtN(d.sessions);
  document.getElementById('hud-strengthened').textContent = fmtN(d.strengthened);
  // ...
  // pod status pill: three states, three colors
  const pill = document.getElementById('hud-pod');
  if (POD.online)             { pill.textContent = 'connected';     pill.style.color = 'var(--ok)'; }
  else if (POD.health===false) { pill.textContent = 'offline · mock'; pill.style.color = 'var(--warn)'; }
  else                        { pill.textContent = 'connecting…';    pill.style.color = 'var(--text-mute)'; }
}
paintHudFromPod();   // immediate — never show "—" if a mock fallback exists

// Live poll: every 5s, refresh stats so the dashboard tracks ongoing ingest
setInterval(async () => {
  if (!POD.online) return;
  try { POD.stats = await mcpCall('mazemaker_stats'); paintHudFromPod(); } catch (e) {}
}, 5000);
```

**Live recall in the input handler** — debounced, request-tagged for out-of-order safety:

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
    if (req !== recallReqSeq) return;    // a newer query superseded this one
    POD.lastRecall = hits;
    POD.recallHistory.unshift({ q, hits, t: Date.now() });
    if (POD.recallHistory.length > 20) POD.recallHistory.pop();
    recallResults.innerHTML = hits.length
      ? hits.map(h => `<div class="hit"><span class="lbl">id=${h.id} · sim=${(h.similarity||0).toFixed(3)} · ${h.label||''}</span><span>${h.content||''}</span></div>`).join('')
      : '<div class="k">no hits · try: dream · recall · federation</div>';
  }, 180);  // 180ms debounce — don't fire on every keystroke
});
```

The `recallReqSeq` monotonic counter is the **debounce-of-debounce** — if
the user types "d", "dr", "dre" in rapid succession, the third call's
`recallReqSeq === 3`, and the first two `setTimeout` callbacks early-return
when their (slower) response lands. Without it, out-of-order responses
overwrite fresh ones. Same pattern works for any fire-and-forget query
where stale responses must not corrupt the UI.

**Why mock-fallback is non-negotiable**: the page should NEVER crash if
the pod is down. A `MOCK = { memories: 208810, ... }` object with a small
cached `browse[]` ensures the HUD shows real-looking numbers, the recall
returns substring-matched hits, and the user can still walk the world.
The mock is a development convenience, not a production target — the
live pod is the product. Treat any "real data only" code as a regression.

**Audit / verification pattern for a live-pod build**:
- Open DevTools console — expect `[pod] connected http://127.0.0.1:8765` in green
- HUD `#hud-pod` reads `connected` in green (or `offline · mock` in amber if the pod is down)
- HUD `#hud-mem` reads a number that matches `mazemaker_stats.memories` for the current pod
- Type into the recall input — after 180ms + network, hits appear with real IDs and similarity scores
- Test offline: stop the pod, reload — page still works, HUD shows mock numbers in amber

### 21. Custom GLSL ShaderMaterial for Particle/Edge Systems

When a scene needs thousands of particles with breathing, per-particle
salience sizing, phase-tinted color, and pulse-arc trajectories, doing
it on the CPU via per-instance matrix updates is wasteful and creates
GC pressure. A custom `ShaderMaterial` with vertex + fragment shaders
moves the breathing and color blending to the GPU — the CPU loop just
pushes 5 uniforms per frame.

**The full pattern** (5,000 nodes + 7,800 edges in ~80 lines of GLSL):

```js
// Per-vertex attributes — static after init
const positions  = new Float32Array(N * 3);
const aSalience  = new Float32Array(N);     // 0..1 — drives size + alpha
const aEnergy    = new Float32Array(N);     // 0..1 — drives breath frequency
const aColor     = new Float32Array(N * 3); // base color from label prefix

const geo = new THREE.BufferGeometry();
geo.setAttribute('position',  new THREE.BufferAttribute(positions, 3));
geo.setAttribute('aSalience', new THREE.BufferAttribute(aSalience, 1));
geo.setAttribute('aEnergy',   new THREE.BufferAttribute(aEnergy, 1));
geo.setAttribute('aColor',    new THREE.BufferAttribute(aColor, 3));

const mat = new THREE.ShaderMaterial({
  vertexShader: `
    attribute float aSalience;
    attribute float aEnergy;
    attribute vec3  aColor;
    uniform float uTime;
    uniform float uPhaseHue;     // 0..1 (HSL hue)
    uniform float uPhaseSpeed;
    uniform float uPodOnline;    // 0/1 — tint toward brand when live
    uniform float uPxRatio;      // device pixel ratio for point size
    varying vec3  vColor;
    varying float vAlpha;
    void main(){
      vec3 pos = position;
      float ph = aEnergy * 6.28318 + uTime * (0.35 + aEnergy*0.6) * uPhaseSpeed;
      float breath = 0.93 + 0.18 * sin(ph);                  // breathing
      pos *= breath;
      pos.y += sin(uTime * 0.27 + aEnergy * 3.14) * 0.07;    // gentle drift
      vec4 mv = modelViewMatrix * vec4(pos, 1.0);
      gl_Position = projectionMatrix * mv;
      gl_PointSize = (3.5 + aSalience * 14.0) * uPxRatio * (240.0 / max(-mv.z, 0.01)) * breath;
      // phase hue → RGB (HSL circle)
      vec3 hueCol = vec3(
        0.5 + 0.5*sin(uPhaseHue*6.28318),
        0.5 + 0.5*sin(uPhaseHue*6.28318 + 2.094),
        0.5 + 0.5*sin(uPhaseHue*6.28318 + 4.188));
      vec3 brand = vec3(0.545, 0.361, 0.965);                // #8b5cf6
      vColor = mix(aColor, mix(hueCol, brand, 0.6), uPodOnline * 0.65);
      vAlpha = 0.35 + aSalience * 0.55;
    }`,
  fragmentShader: `
    precision highp float;
    varying vec3  vColor;
    varying float vAlpha;
    void main(){
      vec2 d = gl_PointCoord - 0.5;
      float r = length(d);
      if (r > 0.5) discard;                                   // clip outside circle
      float a = smoothstep(0.5, 0.0, r);
      a = pow(a, 2.4);                                       // tight falloff
      gl_FragColor = vec4(vColor * (1.0 + a*0.5), a * vAlpha);
    }`,
  transparent: true, depthWrite: false,
  blending: THREE.AdditiveBlending,
  uniforms: { uTime: {value:0}, uPhaseHue:{value:0.78}, uPhaseSpeed:{value:1},
             uPodOnline:{value:0}, uPxRatio:{value:renderer.getPixelRatio()} },
});
const points = new THREE.Points(geo, mat);
```

**Edges with dashed flow** (fragment-shader-only effect — vertex shader is trivial):

```glsl
attribute float aType;  // 0..3 — similar/bridge/supersedes/derived
attribute vec2  uv;     // uv.x: 0 at src, 1 at dst
varying vec3  vColor;
varying float vType;
varying float vU;
void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
              vColor = color; vType = aType; vU = uv.x; }
```

```glsl
precision highp float;
varying vec3  vColor; varying float vType; varying float vU;
uniform float uTime; uniform float uPhaseSpeed; uniform float uPodOnline;
void main() {
  // type-weighted base alpha (supersedes=strongest, similar=weakest)
  float baseA = 0.06 + 0.05 * vType + 0.04 * uPodOnline;
  // dashed flow: a moving band of brighter pixel along the edge
  float band = fract(vU - uTime * 0.18 * uPhaseSpeed);
  float pulse = smoothstep(0.92, 1.0, band) * (1.0 - smoothstep(0.0, 0.08, band));
  vec3 col = vColor * (1.0 + pulse * 1.6);
  gl_FragColor = vec4(col, baseA + pulse * 0.35);
}
```

**The CPU animate() function** — was 30 lines iterating 5,000 nodes, now 4 lines:

```js
function animate(dt, cur) {
  const hsl = { h:0, s:0, l:0 };
  new THREE.Color(cur.hue).getHSL(hsl);
  points.material.uniforms.uTime.value       = elapsed;
  points.material.uniforms.uPhaseHue.value   = hsl.h;
  points.material.uniforms.uPhaseSpeed.value = cur.speed;
  points.material.uniforms.uPodOnline.value  = POD.online ? 1.0 : 0.0;
}
```

**Performance**: 5,000 nodes + 7,800 line segments + 30 CPU instructions per
frame ≈ 0.5ms GPU + 0.1ms CPU. Was 6,000+ matrix updates on CPU per frame
under the InstancedMesh approach. The 100×+ speedup is the whole point.

**Two non-obvious gotchas**:

1. **`attribute vec3 color` works without explicit declaration** when
   `ShaderMaterial({ vertexColors: true })` is set — Three.js auto-prepends
   the attribute. Use `vColor = color;` in the vertex shader directly.

2. **Pixel ratio matters for point size** — `gl_PointSize` is in physical
   pixels, so multiply by `renderer.getPixelRatio()`. Without it,
   particles look half-size on HiDPI displays (Retina, 4K monitors).

3. **DON'T name custom attributes after WebGL/Three.js built-ins** — `uv`,
   `position`, `normal`, `tangent`, `color`, `skinIndex`, `skinWeight` are
   all reserved (either auto-declared by ShaderChunks, or built into
   WebGL2). Declaring one of them as your own `attribute` causes a
   *duplicate-attribute* error at GLSL program link time. Three.js does
   NOT print this to `console.warn` — the program silently fails to link
   and you get `GL_INVALID_OPERATION` (0x502) on every `drawElements`
   call. Detection only works by polling `gl.getError()` in a loop after
   a few fresh frames. The fix: prefix all custom attributes with `a`
   (`aSalience`, `aEnergy`, `aColor`, `aType`, `aEdgeU`). This is the
   most common silent shader bug in raw `ShaderMaterial` work — see
   the "Pitfall: GLSL reserved attribute names" section below for the
   full debugging recipe.

**When to use ShaderMaterial vs. PointsMaterial / InstancedMesh**:
- `PointsMaterial` — single uniform size + color across all particles, no per-particle data
- `InstancedMesh` — per-instance position+rotation+scale+color, but ALL animation runs on CPU each frame
- `ShaderMaterial + Points` — per-vertex attributes (static), per-frame uniforms, GPU-driven animation. Use this when you have N > 1000 particles with continuous animation.

