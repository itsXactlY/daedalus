# Maze Crew Trailer — Session Detail

**Created:** 2026-05-27

## Context
`maze-crew-trailer.html` — 20-second cinematic camera flythrough of a cognition cluster.
CatmullRom camera spline, no controls, no HUD, pure visuals. Loops seamlessly with fade.

**File:** `/home/alca/projects/mazemaker-architect/public/maze-crew-trailer.html`

## Architecture

### Seamless Loop with Fade
```
LOOP_DURATION = 20s
FADE_DURATION = 0.9s
```
At `elapsed >= LOOP_DURATION - FADE_DURATION`, triggers fade-to-black, resets `TOTAL_TIME` and `_camTimeAccum` to 0, waits `FADE_DURATION`, then fades back in. The camera spline is designed so keyframe 11 (last visible) and keyframe 0 (first after fade) are close in position — avoiding a visible jump.

### Camera Spline
12 keyframes stored as `[camX, camY, camZ, lookX, lookY, lookZ]`. Manual CatmullRom sampler (`sampleSpline`) with wrapping indices for seamless loop. Keyframe 11 is NOT identical to keyframe 0 — avoids zero-length spline segment that would cause camera stalling.

### Speed Curve Integration
5 speed multipliers matching `PHASE_HUES`: `[0.70, 1.30, 0.60, 1.40, 1.00]` (avg = 1.0 for loop sync). Integrated via `window._camTimeAccum += dt * speed / LOOP_DURATION`. Reset to 0 at each fade. The average speed of exactly 1.0 ensures the camera completes exactly one spline loop per `LOOP_DURATION` seconds of visible playback.

### Phase Hue Interpolation
Shortest-path hue interpolation handles wrap-around (e.g., 0.55→0.78). Fog color and clear color lerp toward phase hue each frame using `1 - Math.exp(-3 * dt)`.

## Run — Cinematic Vignette + Film Grain

**Priority enhancement:** Added two post-processing overlay layers for cinematic, organic film-stock feel.

### Vignette
```css
#vignette {
  position: fixed; inset: 0; pointer-events: none; z-index: 4;
  background: radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.55) 100%);
}
```
Radial gradient darkens edges to 55% black. Draws the eye inward, gives footage a biological-tissue-under-microscope quality. Zero runtime cost (pure CSS).

### Film Grain
Animated noise texture on a 128×128 canvas, updated at 20Hz (every 50ms), stretched to fullscreen with `mix-blend-mode: overlay` at 3.5% opacity.

```js
const _grainSize = 128;

function initGrain() {
  const gc = document.getElementById('grain');
  gc.width = gc.height = _grainSize;
  _grainCtx = gc.getContext('2d', { willReadFrequently: true });
  _grainImgData = _grainCtx.createImageData(_grainSize, _grainSize);
  _grainCtx.imageSmoothingEnabled = false;
}

function updateGrain(dt) {
  _grainTimer += dt;
  if (_grainTimer < 0.05) return;  // throttle to ~20 Hz
  _grainTimer = 0;
  const data = _grainImgData.data;
  for (let i = 0; i < data.length; i += 4) {
    const v = Math.random() * 255 | 0;
    data[i] = v; data[i+1] = v; data[i+2] = v; data[i+3] = 204;
  }
  _grainCtx.putImageData(_grainImgData, 0, 0);
}
```

**Performance:** 128x128 = 16,384 pixels x 4 bytes = 64KB per update, at 20Hz = ~1.3MB/s memory bandwidth. Negligible. The `willReadFrequently: true` context hint optimizes for `putImageData` over `getImageData`.

**Design rationale:** The grain makes the trailer look like it was shot on film rather than rendered — critical for the "screen-recordable 7-second clip" goal. At 3.5% opacity with overlay blend, it adds texture without obscuring detail.

## Trailer-Specific Patterns

### Pulse Trail Rings (Thought Propagation Visibility)
Each pulse gets a billboarded `RingGeometry` that faces the camera, creating a visible "wake" behind the traveling activation. Scale follows `(0.15 + sin(t * PI) * 0.55) * (1 - t)` — grows then shrinks as the pulse ages. This makes thought propagation readable as directional motion rather than just blinking dots.

### Chromatic Aberration on Phase Transitions
At each of the 5 phase boundaries, RGB channels split inversely proportional to a smoothstep of time-into-segment. First 8% of each segment triggers the effect. CSS `transform: translateX(±px)` on `.ch-r` and `.ch-b` divs.

### Edge Shimmer (Heartbeat)
Edge line opacity lerps toward `0.08 + beat * 0.12` each frame, tying the neural network's visual intensity to the cardiac rhythm.

### Distant Structures Slow Drift
`distantGroup.rotation.y += dt * 0.018` — continuous slow rotation. Per-structure opacity pulses with heartbeat via `userData.baseOp` storage pattern.

## Run #19 (2026-06-20) — Hull Spheres Pulse with Heartbeat + Shift Hue with Phase

**The miss:** The 8 region hull glow spheres (`BackSide MeshPhongMaterial`, opacity 0.12) were completely static. Every other scene element already breathed — edges shimmered with the beat, distant structures drifted and pulsed, fog shifted hue — but the maze's organ envelopes sat frozen.

**The fix — three patches:**

1. Module-level state:
```js
let _hullE = new THREE.Color();
let regionHulls = [];
```

2. In `buildNodes()`, push each hull into the tracking array at creation:
```js
const hull = new THREE.Mesh(hullGeo, hullMat);
hull.position.copy(center);
scene.add(hull);
regionHulls.push({
  mesh: hull, mat: hullMat,
  hue: reg.hue,
  pulsePhase: ri * 0.42,     // per-region offset → organs beat out of phase
  baseOpacity: 0.12,
});
```

3. In animate loop, after the edge-shimmer block:
```js
if (regionHulls.length) {
  const hullK = 1 - Math.exp(-2.5 * dt);
  for (let i = 0; i < regionHulls.length; i++) {
    const h = regionHulls[i];
    const swell = 1 + beat * 0.05 + Math.sin(elapsed * 0.32 + h.pulsePhase) * 0.015;
    h.mesh.scale.setScalar(swell);
    _hullE.setHSL(hue, 0.55, 0.04 + beat * 0.06);
    h.mat.emissive.lerp(_hullE, hullK);
    const targetOp = h.baseOpacity + beat * 0.08;
    h.mat.opacity += (targetOp - h.mat.opacity) * 0.12;
  }
}
```

**Why the per-region offset matters:** Without `pulsePhase = ri * 0.42`, all 8 hulls swell and contract in perfect lockstep. The scene looks like a single mechanical pump. With the offset, each organ swells on its own rhythm — the maze reads as a colony of independently living structures.

**Reusing the global `beat`:** The same `beat = pow(sin(beatPhase), 6)` value that drives the DOM heartbeat div and the edge shimmer now also drives hull scale and opacity. The maze as a whole beats as one organism.

## Pitfalls

### Camera Spline Keyframe 0 != Keyframe N-1
The last keyframe must NOT be identical to the first. CatmullRom uses wrapping indices, so identical positions create a zero-length segment -> camera stalls. Instead, make keyframe N-1 a natural continuation of the arc that approaches (but doesn't match) keyframe 0.

### Speed Curve Average Must Be 1.0
If the average speed multiplier != 1.0, the camera will drift relative to the loop duration over multiple cycles. Verify: `speeds.reduce((a,b)=>a+b) / speeds.length === 1.0`.

### Clock Reset on Fade
`clock.stop(); clock.elapsedTime = 0; clock.running = true` prevents a huge `getDelta()` spike after the fade. Without this, the first frame after fade would have `dt ~= FADE_DURATION` causing a visible hitch.

## File Location
`/home/alca/projects/mazemaker-architect/public/maze-crew-trailer.html`