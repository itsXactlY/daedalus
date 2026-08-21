---
name: threejs-living-viz
category: creative
description: "Build immersive 3D visualizations of graph/memory data that feel alive — dream phases, mood systems, particle edge flows, Web Audio drones, cinematic camera scripting. Three.js + Canvas2D for dashboard panels. **STOP — read 'Doom-clone anti-pattern' in SKILL.md before triggering this skill; 3D walkable worlds are almost never what the user wants when they say 'explore' or 'walkable'.**"
triggers:
- User asks to 'make the maze look alive', 'build a cinematic trailer', 'create a 24/7 livestreams' of graph data
 - Building immersive Three.js experiences with life-like qualities (breathing nodes, dreaming phases, mood shifts)
 - Adding Web Audio atmosphere to a Three.js scene
 - Creating **or reconstructing** a timed cinematic flythrough (**trailer rebuild** from neural memory)
 - **Reconstructing deleted Three.js trailers from neural memory**
 - Integrating a 3D visualization into a dashboard panel
 - **Building a walkable 3D world** (first-person, hub-and-spoke, every corner reachable — see Section 19)
 - **Navigable data experiences** (PointerLockControls + chambers + door raycasting + canvas minimap)
 - **Visualizing a real corpus as a walkable space** (bake live stats, label prefixes, room descriptions into scene geometry/textures)
 - **Connecting a 3D experience to the live mazemaker pod** (wonderland at 127.0.0.1:8765 via /mcp JSON-RPC — see Section 20)
 - **Building GLSL ShaderMaterial systems** for thousands of particles with per-vertex attributes + uniform-driven animation (Section 21)
 - **Building 3D for mazemaker.online** (use the site-aligned design tokens, not the cinematic defaults — see "When Building 3D for mazemaker.online" pitfall)
---


# Three.js Living Visualization

Build immersive 3D visualizations where data feels alive — breathing, dreaming, moody, with audio atmosphere.

## Core Stack

- **Three.js** from CDN via importmap (`cdn.jsdelivr.net/npm/three@0.170.0/`)
- **EffectComposer** + **RenderPass** + **UnrealBloomPass** + **RGBShiftShader** from `three/addons/`
- **OrbitControls** for interactive scenes
- **Web Audio API** for ambient drone
- **Canvas2D** for dashboard panel integrations (lighter weight, clean lifecycle)

## Visual Layers (in order of build)

### 1. Background
- Starfield: 4000-8000 points, radius 15-300, radial distribution, `PointsMaterial({color:0x442266, size:0.12, blending:AdditiveBlending})`
- Nebula: 2000-3000 points, colored `0xBF00FF→0x1a0a2e`, opacity 0.06-0.15, slow rotation

### 2. Nodes
- `Points` with `PointsMaterial({map: glowTexture, vertexColors: true, sizeAttenuation: true, blending: AdditiveBlending})`
- Glow texture: 64px canvas with radial gradient (white center → violet edge → transparent)
- Size = `0.08 + salience * 0.5` (sized by salience/importance)
- Color = constellation color lerped toward white by salience
- Breathing: `size * (0.85 + sin(time * frequency) * 0.15)` — frequency varies by phase

### 3. Edges — Two Layers
**Layer A: Glow lines** (background, subtle)
- `LineSegments` with `LineDashedMaterial`
- **Dash offset animation** creates flowing plasma wave: `lineDashedMaterial.dashOffset = -elapsed * speed * 0.25`
- Vertex colors from edge type (bridge=cyan, causal=orange, support=mint, supersedes=red)
- Opacity 0.04-0.08, `blending: AdditiveBlending`

**Layer B: Particle streams** (foreground, dynamic)
- Each top edge emits 3-12 particles that lerp from source to target node
- `Points` with small size (0.08-0.12), same glow texture
- Speed multiplied by dream phase speed (0.3 NREM, 2.5 REM)
- Particles wrap around (when progress > 1, reset to 0)

### 4. Constellation Clustering
- Group nodes by label prefix: `skill:`, `decision:`, `bug:`, `fact:`, `invariant:`, `ops:`, `build:`, `user:`, `archive:`
- Each cluster gets a center position (spherical distribution around origin)
- Each cluster has its own color palette (violet, orange, red, mint, cyan, etc.)
- Cluster assignment: nearest cluster center to node position
- **Floating labels**: `Sprite` with canvas texture showing cluster name above cluster center

### 5. Dream Phase State Machine
```
AWAKE → NREM → REM → INSIGHT → (repeat)
```

| Phase | Duration | Bloom | Speed | Node Color | Feel |
|-------|----------|-------|-------|------------|------|
| AWAKE | 16s | 0.55 | 1.0 | #BF00FF | steady violet |
| NREM | 24s | 0.22 | 0.3 | #6a0dad | deep slow breathing |
| REM | 14s | 1.0 | 2.8 | #FF69B4 | chaotic bright rapid |
| INSIGHT | 18s | 0.75 | 0.7 | #00FA9A | green crystallization burst |

Each phase shift triggers: color transition, bloom ramp, RGB shift (0.008→0 over 1.5s), node breath frequency change, edge speed change, heartbeat rate change.

### 5.1 Phase as Master Control — Drive Everything From One Scalar

The phase state machine is not just a cycle. It is a **single scalar** that should drive every time-varying property in the scene so the world reads as ONE organism, not a stack of independent timers. The minimum set of properties to bind to the phase:

```js
// In the render loop, after phaseIdx has been updated:
const cur = PHASES[phaseIdx];     // { hue, bloom, speed, ... }
bloom.strength = cur.bloom;                       // post-processing
NEURAL_EDGES.material.opacity = 0.10 + cur.bloom * 0.18;   // edge visibility
heartbeatRate = cur.speed;                        // DOM heartbeat CSS
cameraFar.fogDensity = lerp(fogDensity, 0.04 - cur.speed * 0.015, 0.04);  // REM is clearer
moodLabel.textContent = MOODS[phaseIdx % MOODS.length];   // display layer
// On phase transition, kick the post-FX:
if (phaseJustChanged) {
  rgbShift.uniforms.amount.value = 0.012;        // chromatic split
  setTimeout(() => { rgbShift.uniforms.amount.value = 0; }, 200);
}
```

The pattern: when phase changes, EVERYTHING changes coherently. If bloom changes but edge opacity doesn't, the world looks "off". The fix is always to bind to the phase scalar — never to independent clocks.

**Common audit misses** (run this 4-property check on every visualization):
- Bloom changes but fog density stays fixed → world feels static
- Heartbeat changes but particle speed doesn't → particles ignore the phase
- Phase pill color updates but monitor/edge color doesn't → UI lies about the scene state
- AWAKE state is identical visually to NREM except for color → wasted state

**Real example**: the Pandora's Box 4 phase chambers (AWAKE/NREM/REM/INSIGHT). Each chamber has its own orb, particles, ceiling tint, floor opacity — all driven from `PHASE_DEFS[p]`. Pressing P to advance the phase changes bloom, edge opacity, fog, particle speed, and orb emissive intensity in lockstep. The phase scalar is the only source of truth.

### 6. Mood System
8 emotional states: `tranquil, inquisitive, turbulent, serene, emerging, ancient, feverish, still`
- Changes on phase transition + periodically (~20s)
- Subtly shifts node colors toward mood color (15% blend every 15 frames)
- Displayed in HUD as a changing label with color

### 7. Web Audio Ambient Drone
- Single `OscillatorNode` connected to `BiquadFilterNode` → `GainNode` → destination
- Frequency changes by phase: NREM=28Hz, AWAKE=55Hz, INSIGHT=85Hz, REM=130Hz
- Wave type: triangle for REM (brighter), sine for everything else
- Audio context initialized on FIRST user gesture (click/keydown) — browser policy
- Optionally: short `pulseAudio()` pings on REM/Insight transitions (oscillator + gain ramp)

### 8. Cinematic Trailer (Timed Camera Flythrough)
- Define keyframes array: `{t, act, camera:[x,y,z], target:[x,y,z], bloom, bg, oracle}`
- Interpolate between keyframes with ease-in-out quad easing
- 4 acts: BIRTH (fade in) → GROWTH (edges flood) → DREAM (phase cycle) → REVELATION (pull back)
- Camera at z=6-8 (close!) for 21:9 cinematic framing
- FOV 70-75 for wide aspect ratio
- **Oracle text**: lower-third, left-aligned (not center), ~15px
- **CTA**: bottom 18%, centered, for call to action
- Total duration: ~30 seconds

### 9. Dashboard Panel Integration (Canvas2D)
- When integrating into an existing dashboard with panel switching, use Canvas2D not Three.js
- Self-contained class with `enter(body)` and `destroy()` lifecycle
- Store active instance in a module-level tracker for cleanup
- Nodes as circles with radial gradients, edges as stroked lines, particles as dots
- Dream phase state machine with same phase definitions but 2D rendering

### 10. Biological Tissue Aesthetic (Nodes as Living Cells)

An alternative to the particle-cloud approach: render nodes as organic tissue using `InstancedMesh` with `SphereGeometry`, grouped into translucent membrane envelopes.

**Instanced Mesh Nodes:**
```js
const nodeGeo = new THREE.SphereGeometry(1, 8, 6);
const nodeMat = new THREE.MeshPhongMaterial({
  color: regionColor, emissive: regionEmissive,
  transparent: true, opacity: 0.85,
});
const mesh = new THREE.InstancedMesh(nodeGeo, nodeMat, count);
mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
// Per node: set scale, position via dummy.updateMatrix()
// Per node color: mesh.setColorAt(i, color);
```

**Tissue Membrane Hull:**
```js
const hullGeo = new THREE.SphereGeometry(radius + 1.5, 16, 12);
const hullMat = new THREE.MeshPhongMaterial({
  color: regionHueColor, emissive: regionHueDark,
  transparent: true, opacity: 0.15,
  side: THREE.BackSide, depthWrite: false,
});
```
- Compute center as average of node positions in the region
- Radius = max distance from center to any node + padding
- `BackSide` rendering gives a soft glow envelope, not a solid shell

**Driving hull spheres with the heartbeat + phase hue:**

Static hull envelopes look like plastic bubbles. To make the maze's organs feel *alive*, the hulls themselves must respond to the heartbeat and the current phase hue. This requires three steps:

```js
// 1) At init: track hulls in a module-level array (NOT in scene.children,
//   which you'd have to filter by type every frame)
let regionHulls = [];

// 2) In buildNodes(), per region:
const hull = new THREE.Mesh(hullGeo, hullMat);
hull.position.copy(center);
scene.add(hull);
regionHulls.push({
  mesh: hull, mat: hullMat,
  hue: reg.hue,
  pulsePhase: ri * 0.42,    // ← KEY: per-region offset so organs beat out of phase
  baseOpacity: 0.12,
});

// 3) In animate loop, after computing the heartbeat `beat`:
const _hullE = new THREE.Color();  // hoist — never allocate inside the loop
if (regionHulls.length) {
  const hullK = 1 - Math.exp(-2.5 * dt);
  for (let i = 0; i < regionHulls.length; i++) {
    const h = regionHulls[i];
    // Scale: heartbeat swell + slow per-region undulation
    const swell = 1 + beat * 0.05 + Math.sin(elapsed * 0.32 + h.pulsePhase) * 0.015;
    h.mesh.scale.setScalar(swell);
    // Emissive lerps toward phase hue, brightness rides the beat
    _hullE.setHSL(phaseHue, 0.55, 0.04 + beat * 0.06);
    h.mat.emissive.lerp(_hullE, hullK);
    // Opacity rises on the beat
    const targetOp = h.baseOpacity + beat * 0.08;
    h.mat.opacity += (targetOp - h.mat.opacity) * 0.12;
  }
}
```

Three things make this work:
- **`pulsePhase = regionIndex * 0.42`** — without per-region offsets, all hulls pulse in lockstep and the scene looks like a single mechanical object. Random offsets from `Math.random()` also work but deterministic per-index offsets make the relationship between region and phase readable.
- **`1 - Math.exp(-k * dt)`** — frame-rate-independent lerp factor (here `k=2.5` for ~0.4s response time). Same form as the fog-color lerp in the cinematic trailer.
- **Reuse the global `beat` value** — if you already compute `beat = pow(sin(beatPhase), 6)` for the DOM heartbeat indicator, drive hull scale/opacity from the same value. The maze as a whole beats as one organism.

### Gaussian Node Distribution
Use Box-Muller transform for organic clustering instead of uniform random:
```js
function gaussian() {
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}
// Position: center + gaussian() * spread
```

### 11. Traveling Activation Pulses
- See `references/pulse-glow-aura.md` for the full glow aura layering pattern

Distinct from continuous particle streams: discrete "pulse" events that travel along edges as glowing spheres, triggered at phase-dependent rates.

**Pulse Data Structure:**
```js
{ sx, sy, sz, tx, ty, tz, t: 0, speed: 0.5, hue: 0.78, life: 1.0 }
```

**Eased Arc Trajectory:**
```js
const e = p.t < 0.5 ? 2 * p.t * p.t : 1 - Math.pow(-2 * p.t + 2, 2) / 2;
const x = p.sx + (p.tx - p.sx) * e;
const y = p.sy + (p.ty - p.sy) * e + Math.sin(p.t * Math.PI) * 0.8;
const z = p.sz + (p.tz - p.sz) * e;
```
- Ease-in-out quadratic for natural acceleration/deceleration
- Sine arc adds vertical lift (synaptic jump feel)
- Scale pulses with `Math.sin(p.t * Math.PI)` for bloom-at-peak effect

**Instanced Pulse Rendering:**
- Single `InstancedMesh(SphereGeometry(0.12, 6, 4), MeshBasicMaterial)` with capacity ~200
- Update only active pulses each frame; hide unused instances by scaling to 0 or moving far away
- Use `instanceColor` to tint pulses by source region hue

**Glow Aura Layering (no post-processing needed):**
Layer a second InstancedMesh at the same positions with larger geometry + lower opacity + tinted color. Read back transforms from the primary mesh via `getMatrixAt()`/`getColorAt()` instead of duplicating position math:

```js
// Setup
const GLOW_GEO = new THREE.SphereGeometry(1.8, 8, 5);      // 3× larger
const GLOW_MAT = new THREE.MeshBasicMaterial({
  color: 0x8855ff, transparent: true, opacity: 0.18,
  blending: THREE.AdditiveBlending, depthWrite: false,
});

// Build: create glow mesh with same capacity as primary
pulseGlowMesh = new THREE.InstancedMesh(GLOW_GEO, GLOW_MAT, 180);
scene.add(pulseGlowMesh);

// Animate: after primary mesh is written, clone + modify
for (let i = 0; i < cap; i++) {
  if (i < activeCount) {
    pulseMesh.getMatrixAt(i, dummy.matrix);        // clone position/rotation
    dummy.scale.setScalar(dummy.scale.x * 2.6);     // scale up for glow
    dummy.updateMatrix();
    pulseGlowMesh.setMatrixAt(i, dummy.matrix);     // ← setMatrixAt, NOT setInstanceMatrix
                                                    //   (the latter doesn't exist on InstancedMesh)

    pulseMesh.getColorAt(i, color);
    color.lerp(_violetColor, 0.35);                 // tint toward violet
    pulseGlowMesh.setColorAt(i, color);
  } else {
    dummy.position.set(0, -9999, 0);               // hide unused
    dummy.scale.setScalar(0);
    dummy.updateMatrix();
    pulseGlowMesh.setMatrixAt(i, dummy.matrix);
  }
}
```
- Core pulse (small, bright): single-pass rendering
- Glow aura (large, soft): readback + scale + tint
- No post-processing pipeline needed
- See `references/pulse-glow-aura.md` for full breakdown + variations

### 12. Fog-of-War Distant Structures

Wireframe skeletal shapes at the periphery to suggest infinite extent. Place at 40-80 units (inside the fog boundary) for structures that fade in/out as the camera orbits.

**Shape Variety (mix of 4 geometries):**
```js
const shapeFactories = [
  () => new THREE.IcosahedronGeometry(2 + Math.random() * 4, 0),  // sharp faceted
  () => new THREE.TorusKnotGeometry(1.5 + Math.random() * 2, 0.6, 18, 8),  // twisted loops
  () => new THREE.DodecahedronGeometry(2 + Math.random() * 3),  // pentagonal
  () => new THREE.ConeGeometry(2 + Math.random() * 2, 3 + Math.random() * 3, 6),  // spires
];
```
- Mix prevents repetitive patterns — the periphery looks organically populated
- IcosahedronGeometry subdivision 0 (not 1) keeps wireframes sharp and low-poly

**Spherical Distribution (vertically squashed):**
```js
const theta = Math.random() * Math.PI * 2;
const phi = Math.acos(2 * Math.random() - 1);
const r = 40 + Math.random() * 40;
mesh.position.set(
  r * Math.sin(phi) * Math.cos(theta),
  r * Math.cos(phi) * 0.3,       // vertical squash — structures float more horizontally
  r * Math.sin(phi) * Math.sin(theta)
);
```
- Y multiplied by 0.3 keeps distant structures near the horizontal plane (like clouds or distant mountains)
- Avoids structures floating directly overhead or underfoot

**Per-Structure Rotation in Animate Loop:**
```js
for (const s of distantStructures) {
  const spd = s.userData.rotSpeed * (0.5 + cur.speed * 0.5);  // phase-aware speed
  s.rotation.x += s.userData.rotX * spd;
  s.rotation.y += s.userData.rotY * spd;
  s.rotation.z += s.userData.rotZ * spd;
  s.material.opacity += ((0.02 + cur.dreamOpacity * 0.06) - s.material.opacity) * 0.01;
}
```
- Each structure rotates on a random axis at its own speed — creates organic visual variety instead of uniform motion
- Speed scales with `cur.speed`: barely moves in NREM, drifts in REM

### 13. DOM Heartbeat Indicator

A DOM element (not 3D) that pulses in sync with the phase's pulse rate:
```js
// CSS: #beat { width:6px; height:6px; border-radius:50%; transition:opacity 0.15s,transform 0.15s }
beatPhase += dt * PHASE.pulseSpeed * 2.2;
const beat = Math.pow(Math.max(0, Math.sin(beatPhase)), 6);
// ^ power-of-6 for sharp spike rather than smooth sine
el.style.opacity = 0.15 + beat * 0.55;
el.style.transform = `scale(${1 + beat * 0.6})`;
el.style.boxShadow = `0 0 ${beat * 18}px rgba(155,107,255,${beat * 0.4})`;
```
- `pow(sin, 6)` creates a sharp cardiac spike rather than smooth oscillation
- Phase pulse speeds: NREM=0.3, AWAKE=0.8, INSIGHT=1.0, REM=2.8

### 14. One-Shot Expanding Ring (Coherence Wave / Shockwave)

For any "burst outward" visual — coherence wave, shockwave, birth pulse, insight crystallization:

```js
// Setup (once)
const ring = new THREE.Mesh(
  new THREE.RingGeometry(0.1, 0.5, 64),
  new THREE.MeshBasicMaterial({ color: 0x40e8b0, transparent: true, opacity: 0,
    side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending })
);
scene.add(ring);

// Trigger (on phase transition or event)
ring.userData = { t: 0, active: true };

// Animate (per frame)
function updateRing(dt) {
  if (!ring.userData.active) return;
  ring.userData.t += dt * speed;
  const p = ring.userData.t;
  if (p >= 1) { ring.userData.active = false; ring.material.opacity = 0; return; }
  ring.scale.setScalar(p * maxRadius);
  ring.material.opacity = Math.sin(p * Math.PI) * peakOpacity;
  ring.material.color.setHSL(hue + p * hueShift, sat - p * satDecay, lit + p * litRise);
}
```

- `scale.setScalar()` expands the flat ring — cheaper than rebuilding geometry
- `Math.sin(p * Math.PI)` gives natural bell-curve fade
- Hue shift during expansion adds narrative (teal→white = crystallization)
- `depthWrite: false` + `AdditiveBlending` — additive phenomena, not solid objects
- Deactivate when done (`active = false; opacity = 0`) to skip per-frame updates
- Trigger by setting `userData = { t: 0, active: true }` — resets cleanly even mid-animation
- See `references/maze-crew-dream.md` Run #17 for full INSIGHT coherence wave implementation

### 16. Per-Instance Color Events (Flash on Activation)

When individual instances of an `InstancedMesh` need to respond to events (a neuron firing on pulse arrival, a region lighting up on phase transition, a particle "born" from a spawn), the per-instance COLOR must update for that instance. Naive approach — calling `setColorAt` on every instance every frame — is wasteful. Better: track state transitions, batch updates with a dirty flag.

```js
let nodeColorDirty = false;            // hoisted outside the per-instance loop

for (let i = 0; i < nodeData.length; i++) {
  const n = nodeData[i];
  const wasFired = n.fired > 0;        // state before decay
  if (n.fired > 0) { n.fired *= 0.96; if (n.fired < 0.005) n.fired = 0; }
  const isFired  = n.fired > 0;        // state after decay

  if (wasFired || isFired) {
    if (isFired) {
      // Brightness spike — saturation + lightness boost approaches white at peak
      _pCol.setHSL(n.hue, 0.55 + n.fired * 0.30, 0.30 + n.fired * 0.55 + n.energy * 0.18);
    } else {
      // Just decayed to zero — reset to baseline (matches build-time color)
      _pCol.setHSL(n.hue, 0.55, 0.30 + n.energy * 0.18);
    }
    nodeMesh.setColorAt(i, _pCol);
    nodeColorDirty = true;
  }
  // ... rest of per-node matrix update ...
}

if (nodeDirty)         nodeMesh.instanceMatrix.needsUpdate = true;
if (nodeColorDirty && nodeMesh.instanceColor) nodeMesh.instanceColor.needsUpdate = true;
```

**Key insights:**
- `wasFired || isFired` detects both "fired this frame" AND "just decayed to zero" — covers the entire event lifecycle with a single branch.
- Branch on `isFired` to choose fire-state color vs. baseline reset. Without the reset branch, fired nodes stay bright forever (common bug).
- One `needsUpdate` write per frame is cheap. Full-mesh color rewrite every frame wastes GPU bandwidth on idle instances.
- Typical arrival rate is a few/sec, so 0–2 nodes transition through fired state per frame. Cascade bursts may briefly spike to 5–10 transitions — still bounded.
- Cost is `O(transitions_this_frame)` `setColorAt` calls, not `O(total_instances)`. For 900 nodes with ~5 transitions/frame, that's ~0.5% of the work of a full rewrite.

**Per-instance color multiplies the diffuse term only.** For Phong/PBR materials with a separate `emissive` property (which is shared across all instances), the fire flash primarily brightens the diffuse response to lighting. For MeshBasicMaterial, the per-instance color is the entire visible color. For the strongest flash effect, also boost the material's `emissive` once-per-frame toward a hot color during fire-heavy periods.

**Cross-file audit rule:** When one maze-crew file gets per-instance event color updates, check the OTHER two for the same pattern. The fired state was identical across all three files (set in pulse arrival, decays at 0.96/frame) but the per-instance color was never updated in any of them until the trailer in Run #34. Fixing one file without checking the others leaves the visualization inconsistent — pulse arrival in one file reads as a flash, in another as a silent scale swell.

**Real example:** `maze-crew-trailer.html` Run #34 (per-neuron brightness flash on firing). All three maze-crew files have the same per-node `fired` state, so this pattern applies to bio and dream too — backport the per-instance color update to keep visual consistency.

### 17. Multi-Scale Cognitive Response Audit

The "maze as a character" principle requires that a single event (a thought arriving, a heartbeat peaking, a phase transition) produce feedback at multiple nested scales. If any scale is silent, the cognitive moment reads as incomplete or mechanical. When iterating on a cognitive visualization, audit each event for these response layers:

| Scale | What it represents | Example implementations |
|-------|-------------------|------------------------|
| **Per-element** | The receiving entity itself flashes/brightens | Per-instance `setColorAt` flash (Section 16), per-node `fired` size swell, per-spike particle burst |
| **Per-region** | The organ/cluster containing the entity responds | `regionHulls[].activation` echo (bio/trailer Run #30), `clusterAct[c]` accumulation (dream Run #31), regional hue shift |
| **Per-globe** | The whole brain-wide signal propagates | Heart-wave ripples from origin (Run #26, #27, #28), coherence ring on INSIGHT entry, brain shell swell with average activation |
| **Per-network** | Connections to other regions fire (cascade) | Neural cascade A→B→C, bridge-discovery pulses, edge shimmer tied to beat |

**The audit checklist** — pick an event (e.g., "a pulse arrives in region X") and verify all four scales fire visibly:

- [ ] **Per-element**: the destination node itself brightens, swells, or sparks
- [ ] **Per-region**: the destination organ's hull/halo brightens, swells, or shifts hue
- [ ] **Per-globe**: a brain-wide wave/ring radiates from the event
- [ ] **Per-network**: a follow-up signal fires to a connected neighbor (cascade), an edge brightens, or a bridge pulses

**Common audit misses** (real bugs caught by this checklist):
- Per-node `fired` only triggered size swell, not color flash (Run #34 — bio + dream still have this gap)
- Heartbeat drove edge shimmer and hull pulse, but not the starfield or the film grain overlay
- Pulse arrival spawned an arrival flash, but the destination region's hull stayed at baseline opacity
- Coherence ring on INSIGHT entry bloomed 7.5 units above the brain because it was pinned to a hardcoded position while the brain moved with phase (see "Anchored Effects Must Follow Moving Parents" pitfall)

**Why this matters for screen recordings:** On a 7-second clip, the viewer doesn't analyze the structure — they feel the cognitive moment. A nested multi-scale response reads as alive; a single-scale response reads as a tech demo. The trailer is the most screen-recorded of the three (cinematic flythrough), so it should have ALL scales firing visibly. The bio and dream files are interactive/long-form, so the per-globe scale is less critical but the per-element and per-region scales should still be on.

**Run cadence:** Apply this audit at the END of every major iteration (every 5–10 runs), not on every run. It surfaces gaps that the previous 5–10 incremental additions accumulated. See `references/maze-crew-trailer.md` Run #34 for the per-element scale gap that was caught in the trailer.

### 18. In-Browser ES Module Syntax Validation

In-browser ES module scripts in HTML (`<script type="module">`) cannot be linted with `node --check` directly — the script imports from `three` via importmap, and `node` doesn't resolve the importmap. Extract the script block first:

```bash
python3 -c "
import re
html = open('public/maze-crew-trailer.html').read()
m = re.search(r'<script type=\"module\">(.*?)</script>', html, re.DOTALL)
open('/tmp/check.mjs', 'w').write(m.group(1))
print(f'Extracted {len(m.group(1))} chars of JS')
"
node --check /tmp/check.mjs
```

**Catches:** missing braces / parens, `let`/`const` redeclarations, invalid `await` positions, destructuring errors, template literal mistakes, most ES module syntax errors. Returns exit 0 on success.

**Doesn't catch:** logic errors, Three.js API misuse (those need browser test), runtime exceptions from missing properties.

**Apply to ALL three maze-crew-*.html files in the same iteration cycle.** A change in one file's pattern (e.g., the `setInstanceMatrix` → `setMatrixAt` fix in Run #17) often indicates the same pattern exists in the other two files. Run the validation on each one after editing any of them. See `references/maze-crew-bio.md` for the Run #17 discovery (4 broken calls in bio + 2 in dream caused pulse visibility to be silently broken for weeks before being caught).


### 20. Live Pod Integration (Wonderland /mcp JSON-RPC)

Moved to `references/advanced-layers.md` — load with
`skill_view(file_path='references/advanced-layers.md')`.

### 21. Custom GLSL ShaderMaterial for Particle/Edge Systems

Moved to `references/advanced-layers.md` — load with
`skill_view(file_path='references/advanced-layers.md')`.

## New Section: Reconstructing Deleted Trailers

**Trigger:** User says "rebuild the trailer", "restore the deleted HTML/MP4", "extract from neural memory", "the assets are gone but I know the build spec lives in Mazemaker".

### Workflow

1. **Neural recall** — `mazemaker_recall("trailer-final.html", limit=5)`
   - Neural memory returns session transcripts, file snippets, build specs
   - Filter hits with `similarity ≥ 0.45` — treat them as context
   
2. **Asset census** —
   - What existed (HTML, MP4, VO WAV, mix JSON, firedragon configs)?
   - Which are recoverable from memory (HTML)? Which must be rebuilt from scratch (MP4 frames)?

3. **Pane reconstruction** —
   - Open `~/TRAILER_TASK.md` archetype (memory id=492343)
   - Extract beat timings, VO time markers, SFX cues
   
4. **HTML rebuild** —
   - Reproduce Three.js scene, post-processing pipeline, particle systems
   - Save assets to **persistent git-tracked workspace** (`~/mazemaker-trailer-rebuild/`)

5. **Video rebuild** —
   - Firedragon batch (`godlike-batch.sh`) for both 16×9 and 9×16
   - FFmpeg remix:
     ```bash
     ffmpeg -stream_loop 1 -i trailer4-final-16x9.mp4 -i vo/walk-through.wav \
     -codec:v libx264 -pix_fmt yuv420p -shortest \
     trailer4-final-16x9-mixed.mp4
     ```

6. **Artifact tracking** —
   - Write `TRAILER_SPEC.md` listing every asset, memory reference, hash checksum
   - Catalog MP4s with `mediautils probe trailer1-final-*.mp4` → log durations, loudness, resolution

### Pitfalls
- **Memory recall TTL**: Neural memory is definitive but file *content* can diverge from the memory text if files were edited post-storage. **Always cross-check recall with on-disk files** — treat recall as source of truth only when the file is missing.

- **Ephemeral state**: VO files, firedragon raw captures, ffmpeg intermediates land in `/tmp/` and disappear across reboots. **Forward `/tmp/mazemaker-*` assets into the persistent workspace** ASAP.

- **VO re-synthesis**: Use Chatterbox phoneme decoding + hertz remapping when reference audio is synthetic or lost (audio quality beats perfect timbre).

- **Capture reliability**: Firedragon 10% failure rate — **snapshot viewport screenshot** every 2 seconds if running headless (`/tmp/shot-{t}.png`) and drop frames with monochromatic noise.

### Trailer Beat Checklist
| Name | Duration Target | VO Lines | Beat Type |
|------|----------------|------------|-----------|
| trailer-final | 15 s | 3 | Solo helix bloom |
| trailer4-final | 22 s | 3 | **Fast terminal → recall → dream** |
| trailer7-final | 20 s | 3 | **Federation handshake** |

### Deliverables
| Deliverable | Where |
|-------------|------|
| `TRAILER_SPEC.md` | `~/mazemaker-trailer-rebuild/` |
| `trailer*-final.html` | `~/mazemaker-trailer-rebuild/` (mirrored into mazemaker-architect/public/) |
| MP4 masters (both aspects) | `~/mazemaker-trailer-rebuild/video/` |
| Git commit | `git add . && git commit -m "Trailer rebuild: <memory-run>, <date>"` |

### See Also
- `TRAILER_SPEC.md` — Master spec (session 20260523_011902)
- `references/mazemaker-trailer-rebuild.md` — Memory extraction detail + beat mapping



## Pitfall catalogue

Full pitfall section (Edge Color Decay, Z-Index Discipline, GC Pressure, Port
8765 Conflict, Headless WebGL, Import Map, …) moved to
`references/pitfalls.md` — load with
`skill_view(file_path='references/pitfalls.md')`.

## Verification
- [ ] Graph fills the frame at 21:9 aspect ratio
- [ ] All 4 dream phases cycle through (AWAKE → NREM → REM → INSIGHT)
- [ ] Edge dash offset animation flows (edges visibly travel)
- [ ] Particle streams move along edges continuously
- [ ] Mood indicator changes color every ~20s
- [ ] Web Audio drone shifts pitch on phase change (user gesture required)
- [ ] Trailer camera follows scripted path through all 4 acts
- [ ] Panel integrates cleanly with dashboard (no Three.js leaks when switching)
- [ ] No compounding color decay (edges don't vanish)
- [ ] All text readable against scene background
- [ ] Activation pulses visibly travel along edges with arc trajectories
- [ ] Pulse glow aura (layered InstancedMesh) visible as soft halo around traveling pulses
- [ ] Tissue membrane envelopes surround node clusters
- [ ] Hull spheres themselves pulse with the heartbeat and tint-shift with phase hue (not static — see Section 10)
- [ ] Distant structures visible at periphery (fog-of-war)
- [ ] Heartbeat indicator pulses at phase-appropriate rate
- [ ] Coherence wave expands outward on INSIGHT transition (one-shot ring)
- [ ] Per-neuron brightness flash fires on pulse arrival (per-instance color spike, see Section 16) — not just size swell
- [ ] Multi-scale cognitive response audit: per-element, per-region, per-globe, per-network all fire on the same event (Section 17)
- [ ] Phase transition chromatic effects (RGB split, hue flash) appear ONLY on canvas area — HUD text remains crisp (use z-index-6 overlay, not `body.style.filter`)
- [ ] Each phase has a unique visual burst: NREM=slow wave, REM=bridge burst, INSIGHT=coherence ring
- [ ] Trailer: vignette darkens edges, film grain adds organic texture (if trailer/recording context)
- [ ] Trailer: camera spline loops seamlessly without stutter at loop boundary

**Walkable 3D world (Section 19):**
- [ ] Splash overlay gates pointer-lock; click-to-enter works
- [ ] All chambers reachable from HUB without dead-ends (connectivity check)
- [ ] WASD + mouse-look + Space/CTRL work, no falling-through-floor glitch
- [ ] Door raycaster activates at < 4m; pressing E transitions to the target room
- [ ] Each room has a back-out path to HUB (or a connected corridor)
- [ ] Canvas minimap shows player position, facing arrow, and current-room highlight
- [ ] Inception queue logs the last 8 rooms entered with timestamps
- [ ] Camera.y clamped: never below 0.4, never above 40
- [ ] Ceiling exists at `y = CEIL_Y` in every chamber (no looking up at infinity)
- [ ] Real-data labels visible on monitors, archways, portals (not "Demo Room 1")
- [ ] All scene geometry stable across reloads (deterministic seed)
- [ ] DOM structure validated in headless (canvases attached, no console errors, module-executed side-effects present)
- [ ] **Phase as master control**: bloom, edge opacity, fog density, heartbeat rate, particle speed, monitor hue all bound to the same phase scalar — change one and the world should change coherently (Section 5.1)
- [ ] **IIFE block-scoped rooms**: room-local helper variables (positions, sizes, counts) stay inside their `{ }` block, not at module scope (Section 19.16)
- [ ] **Verify existing files unchanged**: when the user says "DO NOT TOUCH existing code", capture md5sum before AND after, diff must be empty (Section 19.17)

**Live pod integration (Section 20):**
- [ ] DevTools console shows `[pod] connected http://127.0.0.1:8765` in green
- [ ] HUD `#hud-pod` reads `connected` in green (or `offline · mock` in amber if pod is down)
- [ ] HUD `#hud-mem` / `#hud-edges` / `#hud-dim` are filled from `mazemaker_stats`, not from `MOCK`
- [ ] DREAM ENGINE panel numbers (sessions, strengthened, pruned, bridges, insights) are live from `mazemaker_dream_stats`
- [ ] Recall input triggers a real `mazemaker_recall` call after 180ms; hits show real IDs and similarity scores
- [ ] Rapid typing into recall does NOT show stale results (the `recallReqSeq` guard works)
- [ ] Test offline: stop the pod, reload — page still works, HUD shows mock numbers in amber
- [ ] `MOCK` fallback values are close to live values so the UI looks real even when the pod is offline

**GLSL ShaderMaterial systems (Section 21):**
- [ ] Particle count > 1000 AND has continuous animation (breathing, drift, phase-tint) → use `Points` + `ShaderMaterial`, not `InstancedMesh`
- [ ] Vertex attributes are static after init (`aSalience`, `aEnergy`, `aColor`); per-frame state goes through `uniforms`
- [ ] `uPxRatio` uniform is set from `renderer.getPixelRatio()` so HiDPI displays show correct point size
- [ ] `vertexColors: true` is set when using `attribute vec3 color` in the vertex shader
- [ ] animate() function is **rewritten** to push uniforms (not iterate per-instance) when swapping rendering paths
- [ ] `node --check` on extracted module body passes after the refactor


## Walkable 3D Worlds + Cinematic Overlays

§15 Cinematic Post-Processing Overlays and §19 Walkable 3D Worlds
(PointerLock + Chambers + Doors, 19.1–19.17) moved to
`references/walkable-3d.md` — load with
`skill_view(file_path='references/walkable-3d.md')`.

## Doom-clone anti-pattern (READ FIRST if user says "walkable", "explore", "every corner", "navigate")

**Hard rule:** When the user request contains evocative spatial language like "walkable", "explore", "every path", "every corner reachable", "navigate", "tour the system" — interpret it as a **UI metaphor FIRST**, not a literal first-person 3D world.

**Real failure pattern:** Asked for "explore mazemaker, every path walkable", I loaded this skill (triggers explicitly match "walkable 3D world" + "navigable data experiences") and built a 106KB Three.js FPS maze with PointerLockControls, custom GLSL shaders, 5000-node neural pool, 27 chambers, door raycasting. User: **"I WAS ASKING FOR A FUCKING UI, NOT AN DOGSHIT DOOM CLONE!"** The user wanted a 25KB editorial card-grid with modals and live data. The spatial metaphor was evocative language, not a literal requirement.

**Default to 2D interactive UI when ANY of these are true:**
- System has >10 nodes or >3 hierarchy levels (spatial layout doesn't help comprehension)
- User mentions "UI", "control surface", "dashboard", "panel", "view", "page" anywhere
- User wants to UNDERSTAND or OPERATE a system, not play a game

**Only escalate to 3D walkable when ALL of these are true:**
1. User explicitly asks for first-person / immersive / cinematic
2. System has <30 nodes
3. Brand identity explicitly calls for 3D
4. Performance budget allows

**If user pushes back with strong language on a 3D build:** the lesson is STRUCTURAL. They want a different class of solution. Stop patching the 3D and rebuild from scratch at the right abstraction level.

For the full failure case study (commands, file sizes, what was attempted, what finally worked), see `references/doom-clone-anti-pattern.md`.


## See Also

- `references/architecture.md` — dream-stream.html / maze-cosmos.html architecture (original 2026-05-21 build)
- `references/doom-clone-anti-pattern.md` — when "walkable" means UI, not FPS


- `references/maze-crew-bio.md` — maze-crew-bio.html session detail (2026-05-24): tissue nodes, activation pulses, fog-of-war, heartbeat DOM
- `references/maze-crew-dream.md` — maze-crew-dream.html session detail (2026-05-27): orbit fix, fog-of-war, bridge fade, GC fix, vignette fix, INSIGHT coherence wave, trail buffer pool
- `references/maze-crew-trailer.md` — maze-crew-trailer.html session detail (2026-05-27): CatmullRom camera spline, speed curve integration, vignette, film grain, trail rings, chromatic aberration
- `references/pulse-glow-aura.md` — InstancedMesh glow aura pattern: getMatrixAt/getColorAt readback, no post-processing needed
- `references/threejs-pitfalls-from-production.md` — hard-won gotchas from a real 106KB single-file Three.js build: raw ShaderMaterial reserved-attribute names, TDZ cascade patterns in large refactors, post-processing audit, brand-aligned single-accent palette rule, BrowserBase caching workaround, per-frame allocation hot-path fixes. Read this before shipping a 3D experience.
- `references/mazemaker-pod-integration.md` — Full wonderland /mcp client pattern with verification recipe


## Refactoring tips

Retarget-animate, central-data-object grep, design-token guidance moved to
`references/refactoring-tips.md` — load with
`skill_view(file_path='references/refactoring-tips.md')`.
