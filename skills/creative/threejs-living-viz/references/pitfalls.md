# Three.js Living Viz — Pitfall Catalogue

Full pitfall section (Edge Color Decay through Import Map), formerly inline
in SKILL.md. Load with `skill_view(file_path='references/pitfalls.md')`.

---

### Edge Color Decay
NEVER multiply color array values frame-over-frame without resetting. `colors[i] *= 0.95` each frame compounds and edges vanish in <2 seconds. Either:
- Store original colors separately and lerp toward them
- Or don't modify colors at all each frame — set once at build time

### Camera Distance
For cinematic trailers that fill a 21:9 frame with a graph spread of ~8 units:
- **BAD**: z=30 → graph is a tiny blob in the corner
- **GOOD**: z=6-8 with FOV 70-75 → graph fills the frame
- Test on the widest aspect ratio the piece will be viewed at

### Font Brightness
Text on dark backgrounds needs aggressive brightness:
- **BAD**: `rgba(191,0,255,0.3)` → invisible on dark background
- **GOOD**: `rgba(235,215,255,1)` with `text-shadow` (triple glow: 60px, 120px, 200px)
- Test every text element against the brightest part of the scene

### Text Positioning (Cinematic)
- **BAD**: text dead center → covers the graph
- **GOOD**: oracle text at `bottom: 22%, left: 6%` (lower-third, left-aligned like film subtitles)
- CTA at `bottom: 18%`, centered

### Three.js Lifecycle in Dashboards
- When mounting Three.js in a dashboard panel that gets swapped out:
  - Create a `destroy()` method that disposes geometry, materials, textures
  - Store active instance in a module-level variable
  - Call `destroy()` before the panel container's innerHTML is replaced
- For simpler lifecycle: use Canvas2D instead of Three.js for dashboard panels

### Z-Index Discipline for HUD-Scoped Visual Effects

When the visualization has a HUD layer (`z-index: 10` — brand text, stats, phase pill, oracle, heartbeat, controls) and you want chromatic/filter effects (RGB split, hue-rotate, contrast flash) to affect **only the canvas area** without distorting the HUD, **NEVER use `document.body.style.filter`**. Body-level filters apply to the entire viewport including the HUD — every text element visibly distorts during the flash.

**Correct pattern — use a positioned DOM overlay at z-index BETWEEN the canvas and the HUD:**

```css
#rgb-split {
  position: fixed; inset: 0; pointer-events: none;
  z-index: 6;        /* BELOW HUD (z-index: 10), ABOVE canvas (default 0) */
  opacity: 0;
}
#rgb-split .ch { position: absolute; inset: 0;
  mix-blend-mode: screen; will-change: transform, opacity; }
#rgb-split .ch-r { background: linear-gradient(135deg, rgba(200,40,40,0.13), transparent 55%); }
#rgb-split .ch-b { background: linear-gradient(135deg, transparent 40%, rgba(40,40,200,0.13)); }
```

```html
<div id="rgb-split"><div class="ch ch-r"></div><div class="ch ch-g"></div><div class="ch ch-b"></div></div>
```

```js
// Trigger on phase transition — channels split then snap back
function triggerRGBSplit(tint) {
  const overlay = document.getElementById('rgb-split');
  if (!overlay) return;
  // ...reset state, fade in overlay, double-rAF to split channels
  r.style.transform = 'translateX(-12px)';
  b.style.transform = 'translateX(12px)';
  // ...fade out after ~120ms
}
```

**Why this works:**
- z-index 6 < HUD z-index 10 → channels appear on canvas only
- `mix-blend-mode: screen` produces the additive chromatic separation (R + B offset looks like color fringing in vision science)
- `pointer-events: none` doesn't block HUD interaction
- `opacity` on the parent overlay fades the effect cleanly

**The bug pattern (DO NOT do this):**
```js
// ❌ Distorts EVERYTHING: HUD text, controls, oracle quote
document.body.style.filter = 'hue-rotate(30deg) saturate(2) contrast(1.4)';
setTimeout(() => { document.body.style.filter = ''; }, 400);
```

**Audit rule for the maze-crew loop:** When reviewing any maze-crew-*.html for visual-effect bugs, `grep -n 'body\.style\.filter\|document\.body\.style\.filter'` — if it appears near a phase transition, it's the same bug. Fix: route through a z-index-6 overlay.

Real examples: `maze-crew-bio.html` run #20 (added `#phase-flash` overlay), `maze-crew-dream.html` run #21 (had `#rgb-split` overlay already wired; just removed leftover `body.style.filter` hacks in `onPhaseTransition()` and `window.manualPhase()`). The trailer file uses a different pattern (CSS filter targeted at the canvas element only, not body) so was unaffected.

### InstancedMesh Per-Instance Transform API

The method is **`mesh.setMatrixAt(i, matrix)`**, NOT `setInstanceMatrix`. The latter doesn't exist on `InstancedMesh` and has been broken since Three.js r126. Calling it silently throws inside try/catch blocks (visualization appears to work but pulses/nodes never render) and crashes hard outside try/catch.

Historical bug surfaced in `maze-crew-bio.html` iteration log #17 — 4 broken calls broke pulse visibility for weeks before being caught. When working with `InstancedMesh`:
- **Write**: `mesh.setMatrixAt(i, matrix)` (correct)
- **Read**:  `mesh.getMatrixAt(i, matrix)` (correct, available since r126)
- Both require `mesh.instanceMatrix.needsUpdate = true` after the loop

Quick lint check: `rg "setInstanceMatrix" path/` should return zero hits in any current Three.js code.

### Heartbeat Shadow CSS String Allocation

DOM heartbeat indicators often use `box-shadow` with a color derived from phase hue. The naive form:
```js
hbEl.style.boxShadow = `0 0 ${4 + pulse * 16}px ${_color.setHSL(cur.hue, 0.6, 0.5).getStyle()}`;
```
allocates **two strings per frame** — `.getStyle()` formats an `rgb(...)` string internally, and the template literal allocates a second full shadow string. At 60 fps, that's 120 string allocations/sec just for a 4-pixel pulse dot.

**Fix — Hue-stamped CSS cache:** Rebuild the color string only when the slowly-changing scalar (phase hue, blend factor) drifts beyond a small epsilon (e.g., 0.002). The dynamic spread/blur part of the box-shadow still concatenates per-frame, but the expensive color formatting runs a handful of times per second during phase transitions, never on idle frames.

```js
// Module scope:
let _beatCssColor = 'rgb(128,128,128)';
let _beatHueStamped = -999;
// In animate:
if (Math.abs(cur.hue - _beatHueStamped) > 0.002) {
  _color.setHSL(cur.hue, 0.6, 0.5);
  _beatCssColor = 'rgb(' + ((_color.r*255)|0) + ',' + ((_color.g*255)|0) + ',' + ((_color.b*255)|0) + ')';
  _beatHueStamped = cur.hue;
}
hbEl.style.boxShadow = '0 0 ' + (4 + pulse * 16) + 'px ' + _beatCssColor;
```

**Applies anywhere** the CSS color derives from a visually-continuous scalar (lerped state machines, smooth time blends). Does NOT apply for discontinuous changes (phase swaps, user-triggered events) where every change should rebuild.

**Cross-File Audit Rule:** When fixing an allocation in one maze-crew file, `grep -n '\.getStyle()\|new THREE.Color()\|new Float32Array' public/maze-crew-*.html` for the SAME anti-pattern in the OTHER files. Fixing bio.html but leaving the same pattern in dream.html is a half-fix. See `references/maze-crew-dream.md` Run #19 for the discovery and fix.

### Anchored Effects Must Follow Moving Parents

**The bug class:** any visual effect that radiates from or anchors to a "core" position (coherence ring, heart-wave mesh, halo, shockwave, particle emitter, bloom center) was likely initialized with a hardcoded `position.set(0, -1, 0)` or similar one-time value. If the parent object (brain shell, central node cluster, scene origin) later moves — e.g. driven by `cur.bgY` for a phase cycle, or by user-controlled camera parallax — the effect stays pinned to the original coordinates and the visual disconnects from its semantic source.

**Real example (maze-crew-dream.html Run #30):** the brain shell moves with phase:
- REM: `targetShellY = -1 + (-5) * 2.5 = -13.5`
- NREM: `targetShellY = -1 + (-2) * 2.5 = -6`
- INSIGHT: `targetShellY = -1 + (3) * 2.5 = +6.5`

But the **coherence ring** (INSIGHT entry burst) was created with `coherenceRing.position.y = -1` and never updated, so on INSIGHT entry the "aha!" ring bloomed **7.5 units above** the brain. Worse, the **heart-wave mesh** (fires on every heartbeat peak) was also pinned at y=-1, so during REM (brain at y=-13.5) every heart wave radiated from "thin air" 12.5 units above the brain. Caught only when reviewing screen recordings of REM and INSIGHT phases.

**The fix — sync child position to parent every frame, at the top of the child's update function:**

```js
// Inside updateCoherenceRing(dt), BEFORE the early-return for inactive state
if (brainShell) coherenceRing.position.y = brainShell.position.y;

// Same pattern for heart-wave mesh — sync at the top of the if (heartWaveMesh) block
if (heartWaveMesh) {
  if (brainShell) heartWaveMesh.position.y = brainShell.position.y;
  // ...rest of wave spawn/update logic
}
```

**Why this is cheap and safe:**
- The brain-shell position is already lerped at 0.03 per frame → no jitter on the child
- One float read + one float write per frame per anchored effect — negligible CPU
- No new allocations, no new state, no GC pressure
- Guards `if (parentMesh)` ensure no crash if parent is destroyed/rebuilt during scene reinit

**Detection — audit grep for any new anchored effect:**

```bash
# Find every position.set call in the file, then check whether the position is updated in animate loop:
grep -n 'position\.set\|\.position\.y =' public/maze-crew-*.html
```

For each `position.set` that is NOT inside the animate loop body, ask: "Does this object's parent move? Does the parent's position depend on a phase/state scalar that I lerp?" If yes, add a sync line in the update function.

**Applies to:**
- Coherence rings / shockwaves / one-shot bursts
- Heart-wave meshes / radial pulse emitters
- Halo envelopes around moving nodes
- Particle emitter origins
- Any "follows the camera target but offset" effect whose target moves

**Does NOT apply to:**
- Static scene props (starfield, distant fog structures — at the periphery, never expected to follow the brain)
- HUD elements (DOM, not Three.js)
- Object that IS the moving parent itself (e.g. brain shell — its position is the thing being driven)

**Cross-file audit rule:** when adding a new anchored effect in one maze-crew file, grep the OTHER two for the same pattern (`grep -n 'position.set.*0.*-1' public/maze-crew-*.html`) and verify each instance has a parent-sync line. Same pattern as the heartbeat `getStyle()` cross-file audit from Run #20.

### Trailer Camera Spline Pitfalls
- **Keyframe 0 ≠ Keyframe N-1**: Last keyframe must NOT equal first in a looping CatmullRom spline — identical positions create a zero-length segment and the camera stalls. Make the last keyframe a natural approach toward (but not matching) keyframe 0.
- **Speed curve average = 1.0**: If average speed multiplier ≠ 1.0, camera drifts relative to loop duration. Verify: `speeds.reduce((a,b)=>a+b) / speeds.length === 1.0`.
- **Clock reset on fade**: Reset `clock.stop(); clock.elapsedTime = 0; clock.running = true` at loop restart. Otherwise `getDelta()` returns the entire fade duration as `dt`, causing a visible frame hitch.

### GC Pressure from Per-Frame Allocations in Animation Loops

**CRITICAL:** Never allocate `new Float32Array`, `new Vector3`, `new Object3D`, or any heap object inside a hot animation loop that runs 60×/sec. Each allocation triggers garbage collection, causing periodic frame hitches visible as stutter.

**Common allocation sites to grep for in any maze-crew-*.html:**
- `new THREE.Color()` in color lerp chains
- `new Float32Array()` in pulse/trail spawners
- `new Vector3()` in position math
- `\.getStyle()` calls (formatting allocates strings)
- Template literals inside the animate loop that interpolate per-frame dynamic values

**The Pattern — Object Pool for Trail Buffers:**

When each traveling pulse/particle needs a working buffer (e.g., circular trail buffer), pre-allocate a pool at init time and borrow/return:

```js
// At init: pre-allocate pool
const POOL_SIZE = 150;  // > max concurrent objects
const pool = Array.from({ length: POOL_SIZE }, () =>
  new Float32Array(TRAIL_MAX * TRAIL_STRIDE)
);
let poolIdx = 0;

function borrowBuf() {
  const buf = pool[poolIdx];
  poolIdx = (poolIdx + 1) % POOL_SIZE;
  return buf;
}

// In spawn site: zero allocation
activationPulses.push({
  // ... other fields ...
  trailBuf: borrowBuf(),  // was: new Float32Array(TRAIL_MAX * TRAIL_STRIDE)
  trailLen: 0, trailWrite: 0,
});
```

**Pool sizing rule:** `POOL_SIZE` must exceed the maximum number of concurrently alive objects. If mesh capacity is 120, pool of 150 guarantees recycled buffers are always from completed objects. Linear allocation with wrap is safe because the oldest reclaimed buffer was from a pulse that died ≥1 frame ago.

**Also hoist to module scope:** `_dummy`, `_color`, `_vec3` — any object used per-frame in the animate loop must be allocated once at module level, not inside the loop body.

**Detection:** If the visualization stutters every ~2-3 seconds, profile for GC pauses. Common culprits: `new Float32Array` in pulse spawners, `new Vector3()` in position calculations, `new THREE.Color()` in color lerp chains.

### Port 8765 Conflict on Systems Running wonderland / passt / uvicorn
On machines running the mazemaker pod (wonderland on 127.0.0.1:8765), passt
(libvirt user-mode networking), or any uvicorn service, the default
`python3 -m http.server 8765` returns 404 (uvicorn answers, but routes
are /api/* — not /index.html). Verify with `ss -tlnp | grep :8765` first;
if `passt.avx2` or `python3 (uvicorn)` owns it, pick a different port.
The Pandora's Box build settled on **9017** (free in the 9000-9099 range
on this machine). Other safe options: 8080, 8766, 9000, 9100.

```bash
ss -tlnp | grep -E ':87|:90'         # check what's bound
cd <project> && python3 -m http.server 9017
```

### Headless Browsers Don't Render WebGL
Browserbase / Chrome headless / Playwright in CI frequently lack a GPU
context. `document.querySelector('canvas').getContext('webgl2')` returns
null. The Three.js canvas attaches to the body and the DOM structure is
verifiable, but the scene does not paint. **Validation strategy:**
- Assert the canvas exists at expected dimensions: `c.width === 1280 && c.height === 633`
- Assert the module executed: probe a side-effect of the build (e.g.
  `document.getElementById('phase-pill').textContent === 'AWAKE'`)
- Assert zero console errors
- For real visual verification, run the page in a normal Chrome/Firefox
  with GPU and use `?time=X` URL-param seek (cinematic-html-trailer
  pattern) or screenshot at a known time

**Do NOT** conclude "the build is broken" from a black headless screenshot.
**Do** verify DOM structure + module-execution side-effects.

### Vision Models Misread Numbers in Screenshots
When verifying via a vision model (browser_vision or vision_analyze),
the model can hallucinate or misread specific numbers — e.g. reporting
"edges 183,859" when the HUD shows "edges 103,859". The model sees a
dark HUD on a dark background and guesses. **Always cross-check
numeric claims against the source HTML/CSS** (`grep -E '[0-9,]+' <file>`)
or against `document.getElementById('hud-edges').textContent` via
browser_console. Treat vision as a layout/visual check, not a data check.

### Web Audio Browser Policy
- Browsers block audio context creation until user gesture
- Create AudioContext on first click/keydown event listener
- Remove listener after initialization to avoid re-initializing

### Import Map
Always use exact version `three@0.170.0` — other versions may break the addon imports:
```json
{"imports":{
  "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
}}
```

