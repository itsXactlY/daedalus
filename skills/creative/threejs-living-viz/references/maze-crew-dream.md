# Maze Crew Loop — Session Detail

**Created:** 2026-05-25

## Context
Autonomous cron-driven iteration loop that improves three Three.js visualization files in rotation:
1. `maze-crew-bio.html` — biological organism view (nodes as tissue, traveling activation pulses)
2. `maze-crew-dream.html` — dream engine (NREM/REM/Insight phase cycling as brain sleeping/awakening)
3. `maze-crew-trailer.html` — cinematic 20s camera flythrough

Rotation: bio → dream → trailer → bio → ...

Iteration log: `public/maze-crew-ITERATION-LOG.md`

## Run #2 — Orbit Control API Symmetry Fix

**Iteration Performed**
**Priority fix:** Orbit control API symmetry bug — `orbitCtrl.phi` and `orbitCtrl.radius` were plain properties while `theta` had a getter/setter pair, causing stale camera matrix whenever those properties were set outside the constructor.

**Change:**
- All three orbitCtrl properties (`theta`, `phi`, `radius`) now have symmetric getter/setter pairs.
- `resetCam()` simplified — works purely through property setters, no explicit `updateCam()` workaround needed.
- `radius` setter includes auto-clamp (`Math.max(8, Math.min(120, v))`) consistent with `updateCam()` body.

**Root cause:** Setters were added to `theta` during a prior refactor but not to `phi`/`radius`. Any code that set `orbitCtrl.phi` directly (future features, another developer) would silently skip the camera matrix update. The camera would self-correct on the next drag/scroll event — making the bug look non-deterministic.

**OrbitCtrl API Symmetry Pattern:**
```js
orbitCtrl = { updateCam,
  get theta() { return theta; set theta(v) { theta = v; updateCam(); } },
  get phi()   { return phi;   set phi(v)   { phi = v;   updateCam(); } },
  get radius(){ return radius; set radius(v){ radius = clamp(v); updateCam(); } }
};
```
All three properties handle camera invalidation transparently. No call site needs to remember `updateCam()`.

## Run #4 — Distant Fog-of-War Structures

**Priority enhancement:** 10 wireframe shapes at 40–80 units. Mix of Icosahedron, TorusKnot, Dodecahedron, Cone. Phase-aware rotation + opacity lerp.

## Run #13 — Bridge Line Alpha Fade

**Priority fix:** REM bridge lines now fade with `bc.setHSL(b.hue, 0.8, 0.5 * alpha)` instead of hardcoded lightness. Lines emerge organically, peak at midpoint, fade out.

## Run #14 — GC Pressure Fix

**Priority fix:** Hoisted `_dummy`, `_color`, `_vec3` to module scope instead of per-frame allocation in the 800-node update loop.

## Run #16 — Vignette Opacity Fix (Dead Computed Value)

**Priority fix:** `targetVig` computed per frame but never assigned to DOM. One line added: `vigEl.style.opacity = targetVig`. CSS `transition: opacity 2s` handles crossfade.

## Run #17 — INSIGHT Coherence Wave

**Priority enhancement:** Added expanding coherence wave ring on INSIGHT phase transition. Previously INSIGHT lacked a distinctive visual signature.

**What was built:**

`RingGeometry(0.1, 0.5, 64)` with teal additive material, expanding center→radius 22 over ~0.8s:

```js
let coherenceRing = null;

function ensureCoherenceRing() {
  if (!coherenceRing) {
    const geo = new THREE.RingGeometry(0.1, 0.5, 64);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x40e8b0, transparent: true, opacity: 0,
      side: THREE.DoubleSide, depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    coherenceRing = new THREE.Mesh(geo, mat);
    coherenceRing.position.y = -1;
    scene.add(coherenceRing);
  }
}

function triggerCoherenceWave() {
  ensureCoherenceRing();
  coherenceRing.userData = { t: 0, active: true };
}

function updateCoherenceRing(dt) {
  if (!coherenceRing || !coherenceRing.userData.active) return;
  const ud = coherenceRing.userData;
  ud.t += dt * 1.2;
  if (ud.t >= 1) { coherenceRing.userData.active = false; coherenceRing.material.opacity = 0; return; }
  coherenceRing.scale.setScalar(ud.t * 22);
  coherenceRing.material.opacity = Math.sin(ud.t * Math.PI) * 0.6;
  coherenceRing.material.color.setHSL(0.38 + ud.t * 0.08, 0.7 - ud.t * 0.3, 0.3 + ud.t * 0.35);
}
```

**One-Shot Expanding Ring Pattern** (reusable):
1. Flat `RingGeometry` + `scale.setScalar(progress * maxRadius)` — cheaper than rebuilding geometry
2. Bell-curve opacity: `Math.sin(progress * Math.PI)` for natural fade-in/fade-out
3. Hue shift during expansion adds narrative (teal→white = crystallization)
4. `depthWrite: false` + `AdditiveBlending` — additive phenomena, not solid objects
5. Deactivate when done (`active = false; opacity = 0`) to skip per-frame updates
6. Trigger by setting `userData = { t: 0, active: true }` — resets cleanly even mid-animation

**Design rationale:** INSIGHT = communities synchronizing. The expanding ring visualizes coherence radiating outward through the brain shell — the "aha moment" of the dream cycle. Teal→white hue shift reinforces the "crystallization" metaphor.

## Run #18 — Trail Buffer Pool (GC Stutter Fix)

**Priority fix:** Per-pulse `new Float32Array(DREAM_TRAIL_MAX * DREAM_TRAIL_STRIDE)` allocations in the animation loop — one per spawned pulse across 5 spawn sites. During REM phase (up to 12 pulses/frame at 60fps) this caused 720+ heap allocations/sec, triggering GC pauses and visible frame hitches.

**Change:** Pre-allocated a pool of 150 `Float32Array(80)` trail buffers at init time. Added `borrowTrailBuf()` that linearly cycles through the pool with wrap-around. Pool size (150) > max concurrent pulses (120 mesh slots), so recycled buffers are always from pulses that completed ≥1 frame ago.

```js
const TRAIL_POOL_SIZE = 150;
const trailPool = Array.from({ length: TRAIL_POOL_SIZE }, () =>
  new Float32Array(DREAM_TRAIL_MAX * DREAM_TRAIL_STRIDE)
);
let trailPoolIdx = 0;
function borrowTrailBuf() {
  const buf = trailPool[trailPoolIdx];
  trailPoolIdx = (trailPoolIdx + 1) % TRAIL_POOL_SIZE;
  return buf;
}
```

**5 allocation sites replaced** with `borrowTrailBuf()`:
- Ambient baseline pulse spawner
- NREM consolidation wave spawner
- REM chaotic burst spawner
- INSIGHT coherent burst spawner
- Default phase spawner

**Result:** Zero GC pressure from trail buffers during playback. Smooth 60fps even during dense REM bursts.

**Generalizable Pattern — Object Pool for Animation Loop Buffers:**
When each spawned entity needs a working buffer (trail, history, scratch space):
1. Pre-allocate pool at init: `Array.from({ length: POOL_SIZE }, () => new BufferType(...))`
2. `POOL_SIZE` must exceed max concurrent entities
3. Linear allocation with wrap is safe (oldest reclaimed buffer is always from a dead entity)
4. Never use `new BufferType(...)` inside the animate loop body

## Run #19 — Heartbeat Shadow getStyle() + Template-Literal Allocation

**Priority fix:** `hbEl.style.boxShadow = \`0 0 ${4+pulse*16}px ${_color.setHSL(cur.hue, 0.6, 0.5).getStyle()}\`` allocated **two strings per frame** (60 fps × 2 = 120/sec) just for the heartbeat glow color. Same anti-pattern that Run #1 fixed in `maze-crew-bio.html` — when iterating across files in the maze-crew loop, the priority check must explicitly audit the OTHER files for the same anti-pattern. Fixing bio.html but not dream.html leaves a half-fix; the loop should treat recurring allocation patterns as cross-cutting.

**Detection signal:** `grep -n '\.getStyle()' public/maze-crew-*.html` during the priority check. If it appears in the animate loop, that's an unfixed allocation site.

**Change:** Hoisted `_beatCssColor` + `_beatHueStamped` to module scope. Color string rebuilds only when `cur.hue` drifts > 0.002 (smoothly-lerped phase hue → fires a handful of times/sec during transitions, never on idle frames).

```js
// Module-scope (near _dummy, _color):
let _beatCssColor = 'rgb(128,128,128)';
let _beatHueStamped = -999;

// In animate loop (replaces the original boxShadow template literal):
if (Math.abs(cur.hue - _beatHueStamped) > 0.002) {
  _color.setHSL(cur.hue, 0.6, 0.5);
  _beatCssColor = 'rgb(' + ((_color.r*255)|0) + ',' + ((_color.g*255)|0) + ',' + ((_color.b*255)|0) + ')';
  _beatHueStamped = cur.hue;
}
hbEl.style.boxShadow = '0 0 ' + (4 + pulse * 16) + 'px ' + _beatCssColor;
```

**Result:**
- `Color.getStyle()` calls: 60/sec → ~5/sec (only on phase-hue drift)
- Template-literal allocations: 60/sec → 1/sec (the spread concat, since `pulse` is per-frame dynamic — unavoidable; was 2, now 1)

**Generalizable Pattern — Hue-Stamped CSS Cache:**
When a CSS string contains a color that derives from a slowly-changing scalar (phase hue, time-of-day, blend factor), rebuild the cached string only when the scalar drifts beyond a small epsilon. Avoids both `Color.getStyle()` formatting overhead AND the per-frame template-literal allocation, while preserving identical visuals.

```js
let _cachedCss = 'rgb(255,255,255)';
let _lastStamped = -999;
// In render:
if (Math.abs(animatedScalar - _lastStamped) > 0.002) {
  _color.setHSL(animatedScalar, 0.6, 0.5);
  _cachedCss = 'rgb(' + ((_color.r*255)|0) + ',' + ((_color.g*255)|0) + ',' + ((_color.b*255)|0) + ')';
  _lastStamped = animatedScalar;
}
el.style.cssProperty = _cachedCss;  // or compose with other dynamic parts
```

Use this anywhere the hue/saturation/lightness changes are visually continuous (lerped state machines, smooth interpolations) — NOT for discontinuous changes (phase swaps, user-triggered events) where every change should rebuild.

## Run #20 — Cross-File Audit Lesson (Meta)

**Pattern reinforcement:** When a fix lands in one maze-crew file, the loop should `grep` the OTHER two files for the same anti-pattern before declaring the run done. This run discovered the same heartbeat allocation in dream.html that Run #1 had fixed in bio.html — purely by inspection. Without the cross-file audit step, dream.html would have carried the same allocation indefinitely.

**Concrete rule for future loop runs:**
1. Apply the fix to the rotated file
2. `grep -n '\.getStyle()\|new Float32Array\|new THREE.Color()' public/maze-crew-*.html` — if any OTHER file has the same pattern, log it as a follow-up
3. If the anti-pattern is well-established in the other files, do an emergency cross-file fix instead of a feature add this run

## Run #21 — Removed Redundant `body.style.filter` Hacks (HUD Distortion Bug)

**Priority fix:** Two leftover `document.body.style.filter = 'hue-rotate(...) saturate(...)'` calls distorted the entire viewport — including HUD brand text, memory/bridges/edges/communities stats, phase pill, oracle quote, and heartbeat — during every auto AND manual phase transition.

**Root cause:** The `triggerRGBSplit(tint)` function (using a `#rgb-split` overlay at z-index 6, BELOW the HUD at z-index 10) was already correctly wired. The body-filter hacks were redundant visual effects left over from before the overlay was built.

**Two callsites removed:**
1. `onPhaseTransition()` (line 762): `el.style.filter = 'hue-rotate(30deg) saturate(2) contrast(1.4) brightness(1.2)'` for 400ms
2. `window.manualPhase()` (line 1683): `el.style.filter = 'hue-rotate(60deg) saturate(2)'` for 400ms

**Cross-file audit discovered same bug in bio.html:** Run #20 (separate session) had already fixed bio.html by adding the `#phase-flash` overlay — that file had NO overlay previously, so a NEW overlay had to be created and wired via a `triggerPhaseFlash()` function. Dream.html was the inverse case: the overlay existed and was wired, but the body-filter hack was left in. Both fixes achieve the same correct end state — visual chromatic effects scoped to canvas, HUD stays crisp.

**Lesson — Z-Index Discipline for HUD-Scoped Effects:** (See main SKILL.md "Z-Index Discipline for HUD-Scoped Visual Effects" pitfall.) The rule: any chromatic/filter visual effect that should affect only the canvas MUST be implemented as a positioned DOM overlay at z-index BETWEEN canvas (0) and HUD (10), never via `document.body.style.filter`. The bio run #20 had to ADD the overlay; the dream run #21 just had to remove the redundant hack. Same bug, opposite fix shape.

**Audit command for future loop runs:** `grep -n 'body\.style\.filter\|document\.body\.style\.filter' public/maze-crew-*.html` — if any result sits near a phase transition or visual flash, route through a z-index-6 overlay instead.

## Techniques Reinforced

**Frame-Rate-Independent Lerp:**
`factor = 1 - Math.exp(-k * dt)` — identical visual speed at any framerate. `k=1.8` for smooth, `k=5` for snappy.

**Phase Lerped State Machine:**
Properties tracked in smoothed `cur` object. Each lerps toward phase target every frame. Avoids snapping on phase change.

**Dead Computed Values:**
Recurring pattern: value calculated but never assigned. Detection: search for `const target*` in animate loop, verify it flows into `.style`/`.material`/`.opacity`.

**Phase Transition Completeness Checklist:**
Every phase transition should have: (1) color/filter shift, (2) RGB split or equivalent visual disruption, (3) phase-unique visual burst (NREM=slow wave, REM=bridge burst, INSIGHT=coherence ring), (4) oracle text update, (5) HUD counter delta. Filter effects must be HUD-scoped (z-index discipline) — never `body.style.filter`.

**Object Pool for Animation Buffers:**
Never allocate heap objects in hot loops. Pre-allocate pools at init. Pool size > max concurrent entities. Linear wrap allocation is safe.

**Z-Index Discipline for HUD-Scoped Visual Effects:**
Chromatic/filter effects that should affect only the canvas area use a positioned DOM overlay at z-index BETWEEN canvas (0) and HUD (10). Never `document.body.style.filter` — it distorts HUD text. See main SKILL.md pitfall section.

## File Location
`/home/alca/projects/mazemaker-architect/public/maze-crew-dream.html`
