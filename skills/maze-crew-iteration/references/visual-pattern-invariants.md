# Visual Pattern Invariants — Cross-File Knob Catalog

Quick-reference for the proven numeric values used by the per-file visual
elements in the maze-crew family. When backporting a visual pattern from one
file to another, copy the constants here verbatim — they were tuned on the
live files and changing them changes the visual character.

## Firing Rings (per-pulse source-side ignition wavefront)

Implemented in bio (run #14+#18), dream (run #10), trailer (run #19). Closes
the cognitive-event triplet: source ignition → in-flight arc → destination
arrival.

| Knob | Value | Notes |
|---|---|---|
| `FIRING_RING_CAP` | `48` | Fixed pool; FIFO overflow at cap |
| `RING_LIFE` | `0.8` seconds | Lifetime; splice at `t >= RING_LIFE` |
| Scale growth | `1 → 4` units linear | Tissue-local reach; NOT organism-wide (that's heart waves' job) |
| Saturation | `0.85` | Source palette reads vivid, not white |
| Lightness fade | `0.55 * (1 - rp)` linear | Brightest at ignition (rp=0), invisible at rp=1 |
| Hue source | `e.src.hue` (the source neuron's region palette) | Matches pulse head + arc thread color |
| Geometry | `RingGeometry(0.4, 0.5, 32)` | Inner radius 0.4, outer 0.5, 32 segments |
| Geometry rotation | `rotateX(-Math.PI / 2)` | Lay flat in XZ plane (perpendicular to worldUp) |
| Material | `MeshBasicMaterial({color: 0xffffff, transparent: true, opacity: 1, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false})` | Additive + DoubleSide for visibility from any angle |
| InstancedMesh guard | `count = Math.max(ringCount, 1)` | Some GPU drivers choke on count=0 draw |
| Unused slot parking | Position `(0, -1000, 0)` scale `0` | Same pattern as heartWaveMesh / pulseMesh family |
| `frustumCulled` | `false` | Off-screen slots must not be culled |

**Spawn point:** Inside `emitPulse()` (or its per-phase equivalents in dream),
right after `edgeBrightness[ei] = 1.0` / `edgeFlashHue[ei] = dst.hue`, push:

```js
if (firingRings.length < FIRING_RING_CAP) {
  firingRings.push({ x: e.src.x, y: e.src.y, z: e.src.z, t: 0, hue: e.src.hue });
}
```

**Update point:** In `animate()`, between the arrival-flashes block and any
`startFadeLoop` / heartbeat-div block. Wrap in `if (firingRingMesh)` for
defensive partial-init safety. Reverse-iterate-and-splice for safe removal.

## Pulse Arc Threads (per-pulse in-flight line)

Implemented in all 3 files. Visualizes the path a thought travels along.

| Knob | Value | Notes |
|---|---|---|
| `ARC_CAP` | matches `PULSE_CAP` | 1:1 in-flight slots |
| Geometry | `CylinderGeometry(0.030, 0.030, 1, 6, 1, true)` | Thin, 6 sides, open-ended |
| Default axis | `Y` (cylinder default) | Re-oriented per pulse via `_dummy.quaternion.setFromUnitVectors(_arcUp, _arcDir)` |
| Hoisted scratch | `const _arcUp = new THREE.Vector3(0, 1, 0)` | Reused for every pulse; module scope |
| Orientation | `_dummy.quaternion.setFromUnitVectors(_arcUp, _arcDir)` where `_arcDir = (dx/len, dy/len, dz/len)` | Rodrigues for small-angle axis-angle |
| Scale | `(1, len, 1)` — len = pulse src→dst distance | Cylinder length matches edge length |
| Position | `((sx+tx)*0.5, (sy+ty)*0.5, (sz+tz)*0.5)` | Midpoint of the edge |
| Hue blend | `hue + (dstHue - hue) * (dying > 0 ? 1 : t)` | Lerp src→dst hue over the in-flight lifetime |
| Saturation | `0.85` | Matches firing-ring saturation family |
| Lightness | `0.45 * alpha` where alpha = `Math.sin(p.t * Math.PI) * 0.55 + 0.30` | Bell envelope, alpha 0.30→0.85→0.30 over lifetime |

## Pulse Arrival Flashes (per-pulse destination explosion)

Implemented in all 3 files. Visualizes the "thought landing."

| Knob | Value | Notes |
|---|---|---|
| `FLASH_CAP` | `32` (bio, dream) — trailer matches | Fixed pool; soft cap |
| Geometry | `SphereGeometry(0.55, 10, 8)` | Small bright sphere |
| Material | `MeshBasicMaterial({color: 0xffffff, transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false})` | Additive |
| Lifetime | `~0.36s` (trailer: `f.life += dt * 2.8`) | Bell envelope via sin(πt) |
| Scale growth | `0.4 → 1.6` linear over lifetime | 4× expansion |
| Color | `setHSL(hue, 0.95, 0.55 + bell * 0.35)` | Saturation 0.95 — punchier than ring; lightness bell-modulated for the burst peak |
| InstancedMesh guard | `count = Math.max(fCount, 1)` | Same as firing rings |
| Unused slot parking | Position `(0, -9999, 0)` scale `0` | Same family pattern |

**Spawn point:** In animate, when a pulse completes its in-flight (t reaches 1),
the arrival flash is pushed — typically at the pulse's update loop's
"complete" branch. NOT in `emitPulse()` (which only spawns the source-side).

## Heart Waves (brain-wide energy radiation on beat peak)

Implemented in all 3 files. Distinct from firing rings (local) and arrival
flashes (per-pulse) — these are organism-wide broadcasts.

| Knob | Value | Notes |
|---|---|---|
| Spawn threshold | `beat > 0.7` (bio/dream), `beat > 0.7` (trailer) | The spiky Math.pow(sin, 6) envelope's peak |
| Debounce | `0.4s` (`_lastBeatSpawn`) | One fire per beat max |
| `HEART_WAVE_CAP` | varies — 32 (trailer), 48 (bio), 64 (dream) | Tune to per-file peak emission rate |
| Geometry | Wireframe `IcosahedronGeometry(15, 1)` (bio), or per-file variant | Wireframe + additive = camera can pass through |
| Material | `LineBasicMaterial` (wireframe) or `MeshBasicMaterial` | Additive |
| Lifetime | ~2.5s (`t += dt * 0.40`) | Wave blooms and dissipates |
| Radius growth | `2 → 45` linear (covers full maze + distant structures at r=55-80) | |
| Opacity envelope | `Math.sin(w.t * Math.PI)` — 0 → peak → 0 | Bell curve, not linear |
| Rotation | Per-wave random spin axis + rate, baked at spawn | Smooth continuous spin survives camera flythrough |
| Hue | Spawn-time `phaseHue(elapsed)` — older waves keep their birth color | Visual timeline of pulses |
| Brightness modulation | `bell * 0.55` | Peak mid-life |

## Cognitive Thought-Sparks (additive particle pool from brain center)

Implemented in all 3 files (bio #29, dream #30, trailer #31). Visualizes the brain "thinking out loud" — additive point particles emitted from the brain center on each heartbeat peak, flying outward into the cosmos with phase-tinted hue. Distinct from heart waves (which are radial icosahedron shells) and firing rings (which are per-pulse ignition wavefronts at the source neuron) — sparks are diffuse particles released from the brain center itself.

| Knob | Value | Notes |
|---|---|---|
| `SPARK_CAP` | `40` | Fixed pool; round-robin slot reuse via `_sparkNextIdx` |
| `SPARK_LIFE` | `1.5` seconds | Each spark fades in then out |
| `SPARK_SPEED_MIN` | `1.8` units/sec | Minimum outward velocity |
| `SPARK_SPEED_MAX` | `4.5` units/sec | Maximum outward velocity |
| Position jitter | `(rand-0.5) * 0.3` on each axis (bio, dream) or `(rand-0.5) * 0.4` (trailer) | Trailer uses larger spread to compensate for slower heart rate |
| Velocity formula | `sin(phi)*cos(theta)*speed, sin(phi)*sin(theta)*speed, cos(phi)*speed` | `theta = random * 2π`, `phi = acos(2*r-1)` for area-weighted pole correction |
| Spawn threshold | `beat > 0.6` (using `Math.pow(Math.max(0, Math.sin(beatPhase)), 6)`) | Fires on ~13.6% of cycle (when sin > 0.908) |
| Spawn debounce | `0.35s` | One fire per beat max (matches heart-wave debounce × 0.875 = 1 fire/beat) |
| Lifetime decay | `life -= dt / SPARK_LIFE` | Linear 1 → 0 over 1.5s |
| Brightness bell | `Math.sin(life * Math.PI)` | 0 → peak (life=0.5) → 0 over lifetime |
| Color formula | `setHSL(_sparkHue[i], 0.85, 0.6); multiplyScalar(bell * 1.5)` | Saturation 0.85 (matches firing rings), lightness 0.6, magnitude 1.5× for additive headroom |
| Geometry | `BufferGeometry` + 2 `BufferAttribute`s (`position`, `color`, both `DynamicDrawUsage`) | Per-frame uploads |
| Material | `PointsMaterial({size: 0.18, vertexColors: true, transparent: true, opacity: 1.0, blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true})` | Additive; per-vertex color encodes brightness via additive blending |
| Park sentinel | `_sparkPos[i*3+1] = -9999` (below scene + camera.far=300) | All slots parked at boot; only written when transitioning live → parked |
| anyChanged gate | Set when at least one spark changed state; guards `attribute.needsUpdate = true` | Typical NREM/quiet frame has 0-1 changes; REM has 1-3 |
| Birth hue source | bio: `currentBeatHue` (module-scope); dream: `cur.hue` (module-scope); trailer: `hue` passed as parameter (local to animate) | Locked at spawn — phase can shift mid-flight without re-tinting existing sparks |

**Cross-file adaptations (the deltas):**

1. **Birth-hue source** (file-specific): bio and dream have the hue state at module scope (read directly from `currentBeatHue` / `cur.hue`). Trailer's `hue` is a `const` inside `animate()`, so `updateSparks()` accepts `birthHue` as a parameter — passed at call site as `updateSparks(dt, hue)`. **Audit before porting:** grep the destination file for the hue variable at module scope. If only inside `animate()`, switch the reader to a parameter (see SKILL.md pitfall 6a).

2. **Y-origin tracking** (file-specific): bio and trailer don't need it (consciousness core / nucleus is fixed at origin). **Dream DOES need it** because `cur.bgY` drifts vertically with phase (NREM -2.7 → INSIGHT +2.6, scaled by *2.5 → -6.75 to +6.5 world units). Dream emits from `(rand-0.5)*0.4, brainShell.position.y + (rand-0.5)*0.4, (rand-0.5)*0.4` — y-axis anchored to brain shell's current vertical position. Without tracking, REM sparks bloom from y=-1 while brain sits at y=-6.75 → visually disconnected.

3. **Position jitter spread** (file-specific): 0.3u (bio/dream) vs 0.4u (trailer). Trailer's slower heart rate (rph 0.5-0.8 Hz) means sparks fire less frequently; the larger spread ensures simultaneous sparks at trailer's peak rate still visibly separate. At 0.3u + 0.8 sparks/sec, sparks would tend to overlap.

**Per-phase spark rate sanity check** (always include in the log entry for future verification):

| File | Heart rate range | Spark rate | Visible overlap | Pool saturation |
|---|---|---|---|---|
| bio | 0.25-1.6 Hz (4 phases) | 0.25-1.6/sec | 0.4-2.4 sparks | 25-160s |
| dream | 0.25-1.6 Hz (4 phases) | 0.25-1.6/sec | 0.4-2.4 sparks | 25-160s |
| trailer | 0.5-0.8 Hz (rph modulated) | 0.5-0.8/sec | 0.75-1.2 sparks | 50-80s |

**Spawn point:** In `animate()`, immediately after the heart-wave spawn block (line ~2313 in trailer, ~1896 in bio). Same `beat > 0.6` threshold as heart-waves (threshold 0.7 with 0.4s debounce) but with 0.1 offset (spark fires slightly earlier — thought emerges before wave blooms, matching bio #18's two-stage heartbeat-emit/wave ordering).

**Update point:** In `animate()`, right after the heart-wave update loop. Two-phase per call:
1. EMISSION: `Math.pow(Math.max(0, Math.sin(beatPhase)), 6) > 0.6 && (now - _lastSparkSpawn) > 0.35` → spawn into round-robin slot
2. UPDATE: for each of the 40 slots, integrate `pos += vel*dt`, decay `life -= dt/SPARK_LIFE`, recompute bell brightness, write vertex color. Expired sparks park at sentinel y=-9999.

**Cross-file parity state:** bio ✓ #29 + dream ✓ #30 + trailer ✓ #31 — full 3/3 parity.

## Per-Node Breath + Positional Wobble

Implemented in all 3 files. Each node breathes at its own rate/phase.

| Knob | Value | Notes |
|---|---|---|
| Breath amplitude | `±6%` scale (`1 + sin(...) * 0.06`) | Subtle organic swell |
| Breath rate | Per-node `breathRate` (default 0.5 Hz) + per-node `breathPhase` | Independent per node |
| Wobble amplitude | `0.03` units in a ~30-unit scene | Sub-1px at outer keyframes |
| Wobble frequencies | 0.25 / 0.28 / 0.22 rad/s on X / Y / Z axes | Incommensurate — no visible period |
| Wobble phases | Per-node `wobblePhaseX/Y/Z` — init in buildNodes via `Math.random() * 2π` | Independent per axis |
| Fired swell | `n.fired * 0.6` size boost | Decays toward 0 over ~1s (multiplier 0.96/frame) |
| Fired brightness | `setHSL(n.hue, 0.55 + n.fired*0.30, 0.30 + n.fired*0.55 + n.energy*0.18)` | Saturation + lightness spike; clamp at (0.85, 1.0) for white peak |
| Energy boost | `+0.18` lightness from `n.energy` | Persistent energy boost (not transient like fired) |

## Per-Region Hull Scale + Activation Echo

| Knob | Value | Notes |
|---|---|---|
| Hull breathing | Per-region `hullBreathRate` + `hullBreathPhase` | Like per-node breath, but for the entire tissue cluster |
| Activation echo | Hull scale briefly swells when a pulse arrives in that region | Drives `regionHulls[r].activation` |
| Echo decay | ~3-4s (slower than per-node fired at ~1s) | Regional vs local timescale |

## Phase Progress Bar (HUD overlay)

| Knob | Value | Notes |
|---|---|---|
| Width update | `(camT or phaseProgress * 100).toFixed(1) + '%'` | 1 decimal — gates ~250 writes/loop not 1200 |
| Color update | `phaseHue(elapsed)` resolved to HSL string, written to `--phase-color` CSS var | 0.005 hue precision = ~1.8° HSL = imperceptible change |
| Change-detection gates | `_phaseFillLastW` (width), `_phaseFillLastH` (color) | Init `''` and `-1` to force first frame |
| CSS transition | **NONE** on `width` — JS authoritative at 60fps | `transition: background 0.3s ease` IS allowed on the color (slow chromatic shift) |

## Chromatic Aberration Overlay (chr-ab, on phase transitions)

Implemented in all 3 files.

| Knob | Value | Notes |
|---|---|---|
| Trigger | On phase-segment boundary (every 4s on the 5-segment loop) | Smoothstep-driven opacity envelope, ~9 writes/sec across 0.32s zone |
| Opacity peak | ~0.3 | Subtle — JS-driven, not CSS-transition |
| Channels | Red + Blue (cyan offset, opposite signs) | mix-blend-mode: screen, additive compositing |
| Hue shift on channel tint | Warm (R) / cool (B) ±N° from `phaseHue(elapsed)` | `triggerChrPhaseTint(phaseIdx)` writes `--ch-r-tint` / `--ch-b-tint` CSS vars |
| CSS transition | **NONE** on `opacity` — JS authoritative | `transition: opacity 0.15s` is an antipattern (lags per-frame JS by 150ms) |
| Change-detection gate | `_chrLastOpR3` (opacity) + `_chrLastPx` (transform px) | 3-decimal precision |

## Heartbeat (EKG div + screen-edge pulse)

| Knob | Value | Notes |
|---|---|---|
| Heart rate (rph) baseline | `0.5` (AWAKE / INSIGHT), mod `+0.3 * sin(elapsed * 2π/LOOP_DURATION)` (trailer) | Period exactly = LOOP_DURATION → clean wrap, no rph discontinuity |
| Beat envelope | `Math.pow(Math.max(0, Math.sin(beatPhase)), 6)` | Spiky; near-zero most of the time, sharp peak at beat |
| Heart-wave debounce | `_lastBeatSpawn = elapsed` after `beat > 0.7`; threshold 0.4s | One wave per beat max |
| Heartbeat-emit debounce (bio #18) | `_lastHeartbeatEmit = elapsed` after `_hbBeat > 0.6`; threshold 0.35s | Threshold offset 0.1 below heart-wave → thought emerges before wave blooms |
| CSS transition | **NONE** on `box-shadow`, `border-color`, `opacity` | JS authoritative at 60fps |
| Change-detection gate | `_heartbeatLast` — pipe-separated key of 7 quantized values (blur px, spread px, RGBA alpha, border alpha, 8-bit RGB) | Skips ~95% of frames between beats |

## Camera Tremor + FOV Breath + Fog Density (proximity-coupled)

| Knob | Value | Notes |
|---|---|---|
| Tremor frequency | 23.7 / 31.3 / 17.1 rad/s on X / Y / Z | Incommensurate — no visible repeat period |
| Tremor amplitude | `0.10` units * `(1 + prox * 0.8)` | Doubles at nucleus; ~1px wobble on outer keyframes |
| FOV breath | `58 + beat * (1.5 + prox * 1.8) + _phaseKick * 4.0` | Subtle at outer keyframes, dramatic at nucleus |
| Fog density | `_baseFog + beat * (0.0024 + prox * 0.0030)` | _baseFog = 0.011; peak density 0.0164 at nucleus |
| Vignette alpha | Follows same beat + prox envelope | _vignetteLast gate quantizes to skip ~95% of frames |

## Phase Transition Thought Burst (bio, run #20)

On every phase change (auto-tick, manual override, WS push — all three paths flow through `notePhaseTransition()`), fire a brief burst of 3-6 cascade pulses spread across a ~400ms window so the cognitive mode shift visibly produces thoughts. Each burst pulse flows through the existing `emitPulse()` pipeline (firing ring at source, inter-region thread if cross-region, axon arc filament, trail afterimages, arrival flash on completion, region activation echo, possible cascade follow-up) — so the burst reads as a coordinated thought storm rather than a separate visual element. Distinct from the chromatic aberration (which is purely a retinal flash) by being cognitive content.

| Knob | Value | Notes |
|---|---|---|
| `PHASE_BURST_DUR` | `0.40` seconds | Total burst lifetime cap; matches `triggerPhaseFlash()`'s 260ms + a 140ms tail |
| `PHASE_BURST_INTERVAL` | `0.07` seconds | Spacing between successive burst pulses (4 frames at 60fps) |
| Per-phase amplitude | `Math.round(3 + emitRate * 4)` | NREM 0.08→3, AWAKE 0.30→4, INSIGHT 0.20→4, REM 0.70→6 |
| State struct | `{ active: false, t: 0, fired: 0, total: 4 }` | Single mutable object reused across all transitions (no per-transition allocation, no per-frame GC) |
| Reset semantics | Always reset `active/t/fired` in `notePhaseTransition()` | Re-arm on back-to-back transitions (auto-tick + WS push in same frame) |
| WHILE loop bound | `Math.min(total, floor(t / INTERVAL))` | Stutter-frame safe: at most `total - fired` pulses per frame |
| Disarm conditions | `fired >= total` OR `t >= PHASE_BURST_DUR` | Normal completion OR safety-net dur cap |

**Per-phase amplitude table:**
| Phase | emitRate | Burst size | Duration | Character |
|---|---|---|---|---|
| NREM | 0.08 | 3 pulses | 210ms | quiet whisper — even the gearshift is sleepy |
| AWAKE | 0.30 | 4 pulses | 280ms | mid-flurry — conscious thought |
| INSIGHT | 0.20 | 4 pulses | 280ms | mid-flurry — the "aha" crystallizes |
| REM | 0.70 | 6 pulses | 420ms | active burst — gearshift is itself a dream event |

**Hook points.** Arm fires in `notePhaseTransition()` (single hook covers all 3 transition paths). Fire block lives in `animate()` after the heartbeat-emit block, BEFORE the pulse loop so burst pulses are processed in the same frame they're emitted (no 1-frame lag).

**OFF-cycle cost.** The animate-loop fire block is wrapped in `if (_phaseBurstState.active)` — common case between transitions (~99.4% of frames in the 66s loop) costs one comparison + one false branch. Zero allocations, zero DOM lookups on OFF frames.

**Cross-file parity state:** bio ✓ #20, dream ✓ #21 (backport complete — see "Dream Adaptation" below for the chaos-field amplitude mapping), trailer ⬜ (out-of-scope-by-design — 20s loop is single-segment, not state-machine; no phase transitions to burst on).

**Visual delta.** Before: phase transition fires chromatic pop (260ms), FOV kick (4° lens widen → settle), #h-phase pill swap, color lerps. Viewer sees a state change WITHOUT a thought. After: same chromatic pop + FOV kick + pill swap + color lerps, AND 3-6 cascade pulses spread across 210-420ms firing rings at their sources, traveling along axons, crossing between regions via inter-thread bridges, exploding in arrival flashes, accumulating region activation echoes. The viewer sees a state change WITH thoughts — "the brain just had a thought flurry that wrapped across regions because the mode shifted."

**Pulse-count delta:** +17 pulses per 66s cycle (~0.26 extra pulses/sec averaged). Visual density bump is +6% at peak burst; the *coordinated-thought-storm* character is the real win — burst pulses fire in 70ms intervals vs random emit's 33ms average, so they visibly bunch as a "flurry" rather than blending into the background.

### Dream Adaptation (dream, run #21)

When backporting the burst to dream, the **formula shape is copied verbatim** but the **amplitude scalar** is remapped to dream's local vocabulary. Bio's `PHASE_DEFS[phase].emitRate` (a 0..1 cognitive-emission scalar) doesn't exist in dream — dream's `PHASE_DEFS` uses `chaos` (a 0..1 cognitive-turbulence scalar) for the analogous concept. The mapping `Math.round(3 + chaos * 4)` produces an equivalent per-phase distribution:

| Phase | bio emitRate | burst | dream chaos | dream burst | Duration |
|---|---|---|---|---|---|
| NREM | 0.08 | 3 | 0.10 | 3 | 210ms |
| AWAKE | 0.30 | 4 | 0.00 | 3 | 210ms |
| INSIGHT | 0.20 | 4 | 0.20 | 4 | 280ms |
| REM | 0.70 | 6 | 0.70 | 6 | 420ms |

The AWAKE/NREM swap (bio: NREM=3 / AWAKE=4; dream: AWAKE=3 / NREM=3) is acceptable — both ends are in the "quiet whisper" band (3 pulses ≤ 280ms), the burst character is preserved, and `chaos` thematically maps dream's "dream-state turbulence" more cleanly than bio's emission-rate baseline. INSIGHT and REM match exactly.

**Implementation deltas vs bio** (all mechanical, no creative difference):
- Arm hook is in `onPhaseTransition(from, to)` (dream's name) not `notePhaseTransition()`.
- Burst fires `spawnThoughtPulse()` (dream's name, the existing per-beat pulse-emit function — same pipeline).
- Fire block placed AFTER `updateFiringRings(dt)` (dream has firing rings from run #10) and BEFORE the inter-region threads block — same "before pulse iteration so burst pulses processed same frame" requirement as bio.
- Defensive null-guard `if (_bDef)` matches the catch-block pattern at showInitError.

**Principle (extracted for future backports):** when backporting a bio pattern with a bio-specific scalar (`emitRate`, `hullBreathRate`, `wobblePhaseX`), DON'T force-fit the scalar — find the destination file's local analogue in its own `PHASE_DEFS` (or equivalent per-state config) and substitute. The formula shape carries the visual character; the scalar carries the per-state amplitude. If the destination file lacks any 0..1 cognitive-activity scalar at all, fall back to using `cur.speed` (always present in all three files) — though the visual distribution will be coarser.

**Cross-file parity state now:** dream ✓ #21. The "Phase Transition Thought Burst" feature row is closed in bio + dream. Trailer stays ⬜ as out-of-scope-by-design (cinematic loops have no phase-transition events).

## Phase-Keyed HUD Motion (Compound-Sine Biological Realism)

Implemented in dream (run #22) — adds rapid eye movement to the HUD awareness eye. The pattern is reusable for any small HUD element that needs to feel ALIVE across multiple phase states (AWAKE/NREM/REM/INSIGHT) rather than mechanically oscillating.

**The core insight:** single sines read as mechanical oscillation. Compound sines (dominant high-frequency + secondary lower-frequency, with IRRATIONAL frequency ratio) read as biological motion because the frequencies never beat back into a clean repeating pattern. Same principle as the per-node wobble in the Three.js scene (3 incommensurate frequencies on X/Y/Z), but applied to a single DOM element via CSS variables + per-frame JS writes.

**The transform composition:** when a CSS element needs BOTH a slow-driven component (smooth lerped state) AND a rapid per-frame component (saccades, drift), compose them in one transform string:

```css
.orb {
  transform: translateX(var(--eye-x, 0px)) scaleY(var(--eye-open, 1));
  transition: background 1s ease, box-shadow 1s ease;  /* NO transform transition */
}
```

**The transform transition rule (extension of pitfall #4):** drop `transition: transform` entirely from any element whose transform is JS-driven at 60fps with at least one rapid component. CSS transitions on transforms would (a) lag the JS-lerped smooth component by 50-100ms, and (b) smooth out the rapid component (defeating the point). The JS lerp itself (`factor = 1 - exp(-k*dt)` with k≈1.8 for smooth, k≈5 for snappy) already produces smooth visible motion; a CSS transition adds nothing but lag.

| Knob | REM | NREM | INSIGHT | AWAKE | Notes |
|---|---|---|---|---|---|
| Dominant frequency | 11.0 Hz | 0.6 Hz | 1.5 Hz | 0 (static) | The character-carrying component |
| Secondary frequency | 3.7 Hz | — | — | — | Adds jitter; only needed for "rapid" reads |
| Amplitude (px) | ±9 (compound) | ±3 | ±2 | 0 | Compound = sum of two sin·amp products |
| Magnitude rationale | "rapid" needs full traverse in ~0.6s | "barely perceptible drift" | "gentle gaze wandering" | "focused on a point" | Magnitude + frequency together read as motion character |

**Visibility-gating analysis (when motion is visible):** if the element has an overlay state (closed lid covering the orb), the motion is invisible when the overlay is fully closed, partially visible during mid-close, and fully visible when open. Don't add an explicit `if (overlayState === 'open')` gate — the natural overlay opacity handles it, AND the mid-close partial visibility is the DESIRED effect (viewer sees "the eye is closing but the eye underneath is moving" — exactly the REM signature). The visibility-gating analysis is a planning step, not a runtime gate.

**Magnitude-vs-viewport bounding:** bound amplitude by `floor((elementWidth - childWidth) / 2)` so the child's edges stay within the parent's `overflow:hidden` clip region. For 26px-wide eye + 7px-wide orb, max safe amplitude is ±9px (left edge max = -12.5px, parent half-width = 13px, still visible). Don't exceed this — overflow clipping looks like the element disappears at the edge, which reads as a bug not a feature.

**JS-side write pattern:**

```js
// Module-scope (near other cached DOM refs):
let _xxxEl = null;  // cached in init()

// In animate-loop hot path or lerpState():
if (_xxxEl) {
  const t = clock.getElapsedTime();  // module-scope clock, set in init()
  let motionX = 0;
  switch (currentState) {
    case 'STATE_A':  motionX = Math.sin(t * FREQ_A) * AMP_A; break;
    case 'STATE_B':  motionX = Math.sin(t * FREQ_B) * AMP_B; break;
    // ...
  }
  _xxxEl.style.setProperty('--motion-x', motionX.toFixed(2) + 'px');
}
```

**Defensive gating.** The `if (clock)` and `if (_xxxEl)` guards are cold-path safety — `clock` is set in init() and the DOM ref is cached in init(), so the guards should never fail in practice but cost ~1ns/frame in the hot path. Add them anyway; the alternative (a runtime crash on init order edge cases) is worse than the gate cost.

**Cross-file parity state:** dream ✓ #22. Bio and trailer don't have an awareness-eye element (they have other HUD elements — bio has the full-width EKG corner, trailer has the brand label + chromatic split). The pattern is reusable if those files ever add a similar small-character HUD element.

**Real-world source (rationale).** Real REM (Rapid Eye Movement) sleep is defined in sleep neuroscience by the eyes darting back-and-forth under closed lids at 1-2 Hz — it's literally where the name comes from. Without this motion, the dream visualization's "REM" phase looks identical to "NREM" or "INSIGHT" except for color — the most iconic feature of the most distinctive sleep state was invisible. Direct match for "Dream phases must feel like a brain sleeping/dreaming/awakening."

## Cross-File Pitfalls When Backporting Visual Patterns

1. **The `const beat` temporal-dead-zone trap.** `beat` (or any per-frame
   derived value) must be computed at the TOP of the animate body before any
   consumer sees it. If you add a new consumer mid-body and reference a
   variable declared later in the same frame, you get a silent ReferenceError
   that the try/catch swallows. Symptom: the new consumer never runs. Fix:
   hoist derived values to the top, or recompute locally at each consumer
   (the established pattern for `beat` is local recomputation at 5 sites).

2. **Change-detection gates lose precision on cheap values.** When you add a
   new per-frame DOM write, use `.toFixed(N)` precision tuned to the
   perceptible threshold — too coarse = visual stutter every gate-cycle, too
   fine = gate never fires = wasted work. Rule of thumb: 1 decimal on width
   % (0.4% resolution, ~250 fires/loop), 3 decimals on opacity (0.001 ≈
   imperceptible), 3 decimals on hue (1.8° HSL ≈ imperceptible).

3. **InstancedMesh `count = 0` draw glitch.** Some GPU drivers silently fail
   on `drawElementsInstanced` with `instanceCount = 0`. Always guard with
   `count = Math.max(activeCount, 1)` — when no instances are active, the
   unused slots parked at (0, -1000, 0) scale 0 are invisible but the draw
   still completes.

4. **CSS transition on per-frame-driven properties.** If the JS writes the
   canonical value at 60fps and the CSS has `transition: <prop>` on the same
   element, the browser smooths the JS write with a transition window
   (50-150ms lag) — visible as a smear on the per-frame rhythm. Rule:
   per-frame-driven properties get NO CSS transition. Slow-drift properties
   (color of a phase bar that changes every 4s) CAN have a transition
   because the JS only writes on the change event.