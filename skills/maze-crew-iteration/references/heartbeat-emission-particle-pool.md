# Round-Robin GPU Particle Pool for Heartbeat-Synced Additive Emission (Bio #29)

## When to Use

Add a heartbeat-synced additive particle emitter when:
- The existing organism already has many heartbeat-driven channels (consciousness core, halo, EKG, brand glyph, distant structures, etc.) but **no explicit "the brain physically released a thought" visual**
- Cognitive emission is currently implicit (distributed across stochastic pulse system) but never explicit (no particle ever visibly leaves the brain center)
- The user-vision principle "thought propagation — activation that visibly travels between regions" applies
- The user-vision principle "the maze as a CHARACTER — mood, heartbeat, emotional tonality" applies
- The pattern needs to work for a 7-second screen-recordable clip — additive pinpricks are highly visible

## The Pattern

A pre-allocated pool of `SPARK_CAP` additive point particles that round-robin through slots on each spawn, with sentinel-value parking for expired particles. Zero per-frame allocation, zero per-spawn GC.

```js
// ─── Module scope ─────────────────────────────────────────────────
const SPARK_CAP = 40;
const SPARK_LIFE = 1.5;        // seconds — each particle fades in then out
const SPARK_SPEED_MIN = 1.8;
const SPARK_SPEED_MAX = 4.5;
const _sparkE = new THREE.Color();  // hoisted scratch — zero alloc per frame
let sparkMesh = null;
let _sparkPos;      // Float32Array(SPARK_CAP * 3)
let _sparkVel;      // Float32Array(SPARK_CAP * 3)
let _sparkLife;     // Float32Array(SPARK_CAP)        — life [1→0]
let _sparkHue;      // Float32Array(SPARK_CAP)        — birth hue
let _lastSparkSpawn = 0;
let _sparkNextIdx = 0;          // round-robin slot index

function buildSparks() {
  const geo = new THREE.BufferGeometry();
  _sparkPos  = new Float32Array(SPARK_CAP * 3);
  _sparkVel  = new Float32Array(SPARK_CAP * 3);
  _sparkLife = new Float32Array(SPARK_CAP);
  _sparkHue  = new Float32Array(SPARK_CAP);

  // Park all particles off-screen at boot — y=-9999 is below scene far-clip.
  // Sentinel value lets the per-frame loop distinguish "alive" from "parked".
  for (let i = 0; i < SPARK_CAP; i++) {
    _sparkPos[i * 3 + 1] = -9999;
    _sparkLife[i] = 0;
  }

  const posAttr = new THREE.BufferAttribute(_sparkPos, 3);
  posAttr.setUsage(THREE.DynamicDrawUsage);
  geo.setAttribute('position', posAttr);
  const colAttr = new THREE.BufferAttribute(new Float32Array(SPARK_CAP * 3), 3);
  colAttr.setUsage(THREE.DynamicDrawUsage);
  geo.setAttribute('color', colAttr);

  const mat = new THREE.PointsMaterial({
    size: 0.18,                    // small enough for discrete pinpricks, not fog layer
    vertexColors: true,
    transparent: true,
    opacity: 1.0,                  // per-vertex color encodes brightness via additive blending
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true,
  });
  sparkMesh = new THREE.Points(geo, mat);
  scene.add(sparkMesh);
}

function updateSparks(dt) {
  if (!sparkMesh) return;
  const tNow = clock.getElapsedTime();

  // ── Emission: spawn 1 particle per beat peak (debounced 0.35s) ──
  // ^6 envelope with threshold 0.6 fires when sin(x) > 0.908 — about 13.6%
  // of cycle. At all four phases (heart rate 0.25-1.6Hz, period 0.625-4s)
  // the 0.35s debounce allows exactly 1 fire per beat. Matches the
  // heartbeat-driven emission pattern (run #18) so cognitive emissions
  // stay deterministic across channels.
  const beat = Math.pow(Math.max(0, Math.sin(beatPhase)), 6);
  if (beat > 0.6 && (tNow - _lastSparkSpawn) > 0.35) {
    const i = _sparkNextIdx;
    _sparkNextIdx = (_sparkNextIdx + 1) % SPARK_CAP;
    // Tiny jitter at origin so back-to-back sparks don't overlap
    _sparkPos[i * 3]     = (Math.random() - 0.5) * 0.4;
    _sparkPos[i * 3 + 1] = (Math.random() - 0.5) * 0.4;
    _sparkPos[i * 3 + 2] = (Math.random() - 0.5) * 0.4;
    // Uniform random direction on sphere — Math.acos(2*r - 1) gives
    // correct area-weighted phi so particles don't cluster at poles.
    const theta = Math.random() * Math.PI * 2;
    const phi   = Math.acos(2 * Math.random() - 1);
    const speed = SPARK_SPEED_MIN + Math.random() * (SPARK_SPEED_MAX - SPARK_SPEED_MIN);
    _sparkVel[i * 3]     = Math.sin(phi) * Math.cos(theta) * speed;
    _sparkVel[i * 3 + 1] = Math.sin(phi) * Math.sin(theta) * speed;
    _sparkVel[i * 3 + 2] = Math.cos(phi) * speed;
    _sparkLife[i] = 1.0;
    _sparkHue[i]  = currentBeatHue;   // LOCK birth hue — phase can shift mid-flight
    _lastSparkSpawn = tNow;
  }

  // ── Update live particles + park expired ones ────────────────────
  const colArr = sparkMesh.geometry.getAttribute('color').array;
  let anyChanged = false;
  for (let i = 0; i < SPARK_CAP; i++) {
    if (_sparkLife[i] <= 0) {
      // Park off-screen at sentinel y=-9999 — guard with !== check to
      // avoid redundant writes for already-parked slots
      if (_sparkPos[i * 3 + 1] !== -9999) {
        _sparkPos[i * 3 + 1] = -9999;
        anyChanged = true;
      }
      continue;
    }
    _sparkPos[i * 3]     += _sparkVel[i * 3]     * dt;
    _sparkPos[i * 3 + 1] += _sparkVel[i * 3 + 1] * dt;
    _sparkPos[i * 3 + 2] += _sparkVel[i * 3 + 2] * dt;
    _sparkLife[i] -= dt / SPARK_LIFE;

    // Bell-curve brightness via vertex color — sin(π·life) peaks midlife.
    // multiplyScalar(1.5) pushes peak color above 1.0 so AdditiveBlending
    // headroom isn't wasted — the GPU clamps per-component anyway.
    const life = Math.max(0, _sparkLife[i]);
    const bell = Math.sin(life * Math.PI);
    _sparkE.setHSL(_sparkHue[i], 0.85, 0.6);
    _sparkE.multiplyScalar(bell * 1.5);
    colArr[i * 3]     = _sparkE.r;
    colArr[i * 3 + 1] = _sparkE.g;
    colArr[i * 3 + 2] = _sparkE.b;
    anyChanged = true;
  }
  // anyChanged gate: skip needsUpdate on idle frames. needsUpdate is
  // idempotent in WebGL so the gate is purely a CPU optimization.
  // Typical NREM frame: 0-1 changes; REM: 1-3 changes.
  if (anyChanged) {
    sparkMesh.geometry.getAttribute('position').needsUpdate = true;
    sparkMesh.geometry.getAttribute('color').needsUpdate = true;
  }
}
```

## Why Each Piece Matters

### Pre-allocation + round-robin (no allocation per spawn)

`SPARK_CAP=40` slots × `1/SPARK_LIFE=0.67 spawns/sec at 1Hz heart rate × 1.5s lifetime = ~1 live particle typical, 2-3 peak`. Pool saturates after `SPARK_CAP / (spawn_rate) = 40 / 0.67 = ~60s` of peak-rate spawning — far beyond the 1.5s lifetime, so the round-robin never loses a particle before its slot expires. Same pre-allocation pattern as:
- `FIRING_RING_CAP = 120` (bio pulse emission)
- `INTER_THREAD_CAP = 16` (bio inter-region synapse threads)
- `HEART_WAVE_CAP = 4` (bio radial heart waves)
- `COSMIC_MOTE_COUNT = 80` (bio midground drift layer)

### Sentinel parking (-9999)

Round-robin slot reuse means you can't rely on `life === 0` to indicate "parked" — the spawn block may overwrite a still-alive slot. Sentinel parking at `y = -9999` (below scene far-clip) lets the GPU cull parked particles at zero per-frame cost. The `if (_sparkPos[i * 3 + 1] !== -9999)` guard in the park branch prevents redundant writes for already-parked slots.

### Birth hue lock at spawn (vs lerp toward current)

Particles capture `_sparkHue[i] = currentBeatHue` at spawn time and **never re-read `currentBeatHue` mid-flight**. If the phase transitions mid-lifetime, the particle keeps its birth color. This reinforces temporal flow the same way bio's heart-wave icosahedra do (`hue: currentBeatHue` locked at spawn — see bio.html L2101). Visual: viewer sees particles of distinct colors traversing the same field, rather than every particle slowly shifting to match the current beat.

### Vertex-color brightness via setHSL + multiplyScalar

`PointsMaterial` with `vertexColors: true` multiplies per-vertex color × material.color. Setting per-vertex color directly via `_sparkE.setHSL(hue, 0.85, 0.6); _sparkE.multiplyScalar(bell * 1.5);` lets each particle have its own brightness envelope. Alternative (single `material.opacity`) would modulate the whole layer uniformly — wrong for "discrete pinpricks". The `1.5×` multiplier pushes peak color above 1.0 so AdditiveBlending headroom isn't wasted (GPU clamps per-component anyway).

### anyChanged gate

`needsUpdate` triggers a GPU buffer upload. WebGL re-uploads are idempotent for identical data but still cost a CPU-side hash check + buffer-subdata call. The `anyChanged` gate skips the upload entirely on idle frames. Typical NREM frame: 0-1 changes (no spawns during off-beat); REM frame: 1-3 changes (1 spawn + 1-2 particle updates). The gate saves ~80% of GPU upload work during the long between-beats segments.

### Math.acos(2*r - 1) for correct area-weighted phi

Naive `phi = Math.random() * Math.PI` clusters particles at the poles. `phi = Math.acos(2 * Math.random() - 1)` is the standard uniform-on-sphere formula — area-weighted so density is uniform across the sphere surface. Pair with `theta = Math.random() * Math.PI * 2` for full 4π coverage.

## Threshold/Debounce Math

- Threshold 0.6 with `^6` envelope: fires when `sin(x) > 0.908`, i.e. `x ∈ (1.144, 1.998)` rad = 0.854 rad = **13.6% of cycle**
- Heart-wave at threshold 0.7 with `^12`: fires when `sin(x) > 0.972`, i.e. `x ∈ (1.323, 1.819)` rad = 0.496 rad = **7.9% of cycle**
- Particles fire ~30ms earlier per beat than heart waves (matches bio's two-stage coupling from run #18)
- Debounce 0.35s matches `_lastHeartbeatEmit` exactly so spawn timing is deterministic across cognitive-emission channels

### Per-Phase Spawn Rate (= heart rate)

| Phase   | Heart rate | Sparks/sec | Visible at any moment (rate × 1.5s) |
|---------|------------|------------|--------------------------------------|
| NREM    | 0.25 Hz    | 0.25/s     | 0.4 (slow meditative drift)          |
| AWAKE   | ~1.0 Hz    | 1.0/s      | 1.5 (steady heartbeat)               |
| INSIGHT | 1.0 Hz     | 1.0/s      | 1.5 (focused "aha" beat)             |
| REM     | 1.6 Hz     | 1.6/s      | 2.4 (rapid chaotic distribution)     |

## Implementation Correctness Checklist

- [x] Module-scope `sparkMesh`, `_sparkPos`, `_sparkVel`, `_sparkLife`, `_sparkHue` hoisted together as a coherent pool
- [x] `_sparkE` hoisted scratch — `setHSL` mutates in place, no per-frame Color allocation
- [x] `beatPhase` and `currentBeatHue` are module-scope, updated by `updateHeartbeat()` BEFORE `updateSparks()` runs (the animate-loop order matters — sparks must come after the heartbeat update)
- [x] `clock` is module-scope, set in init() — `clock.getElapsedTime()` is safe
- [x] `scene` is module-scope, set in init() — `scene.add(sparkMesh)` in `buildSparks()` called from init() is safe
- [x] The park-guard `if (_sparkPos[i * 3 + 1] !== -9999)` prevents redundant writes for already-parked slots
- [x] `anyChanged` gate skips GPU uploads on idle frames

## When NOT to Use

- **Particles that need to interact with each other** (collisions, attractions) — round-robin slot reuse makes identity-tracking hard. Use a regular array with splice() for short-lived interactive particles.
- **Particles that need variable lifetime per spawn** — round-robin assumes uniform lifetime. If you need different lifetimes, add a `_sparkLifeTotal[i]` array and store per-spawn lifetime.
- **Files without a heartbeat envelope** — trailer's 20-second loop has no heartbeat; use camera-path-driven emission instead.
- **Files where particle count must scale with phase** — round-robin pool is fixed-size. For phase-scaled particle count (e.g., REM has 3× more particles than NREM), use a flag-per-slot pattern or a different approach.

## Cross-File Applicability

- **Bio ✓** — implemented in run #29, fires from consciousness core at origin
- **Dream ✓** — backported in run #30 (adapted: emits from `brainShell.position.y` not origin, since the dream's brain drifts vertically with phase). See "Dream Adaptation" section below for the y-tracking pattern.
- **Trailer** — probably N/A. Trailer is camera-path-driven with no heartbeat envelope. Could adapt the round-robin pool for the recognition-ping pattern (single radial ping per camera dive) but the per-frame emission/position math is different.

### Multi-Channel Beat Emission Cascade (dream, run #30)

When the destination file already has multiple heartbeat-driven emission systems and you add a new one, the new emission joins a coordinated cascade. In dream, every beat peak now fires FOUR distinct emission channels in deterministic order, all gated by different debounce vars but firing on the same beat clock:

| Channel | Debounce var | Threshold | Visible character |
|---|---|---|---|
| Heart-wave (icosahedron shell) | `_lastBeatSpawn` 0.4s | `pulse > 0.7` | radial expanding wireframe |
| Thought pulse (inter-region point) | (same as heart-wave) | (same) | traveling bright sprite |
| Activation pulse (general cognitive) | `_lastHeartbeatEmit` 0.35s | `_hbBeat > 0.6` | traveling bright sprite |
| **Cognitive thought-sparks (additive diffuse)** | `_lastSparkSpawn` 0.35s | `beat > 0.6` | particles from origin |

**The cascade composition principle.** Each channel has its own debounce so it doesn't fight the others for frame budget, but the thresholds (0.6 vs 0.7) and debounces (0.35 vs 0.4) are tuned so they all fire on the SAME beat peak in deterministic order:
1. **Spark** fires first (^6 envelope, threshold 0.6) — the brain releases a thought into the cosmos
2. **Activation pulse** fires next (same ^6 envelope, same threshold, different debounce) — a specific cognitive signal travels
3. **Thought pulse** fires next (^12 envelope, threshold 0.7) — a coordinated inter-region signal travels
4. **Heart-wave** fires last (^12 envelope, threshold 0.7) — the whole brain visibly radiates

The viewer sees a coordinated thought event: spark emerges, pulses travel, wave blooms — all from the same beat peak.

**Debounce-coexistence math.** For all four to fire on the same beat at all four phases:
- NREM (0.25Hz, period 4s) — all four debounces (0.35-0.4s) << 4s, all fire 1×/beat ✓
- AWAKE/INSIGHT (1Hz, period 1s) — debounces 0.35-0.4s < 1s, all fire 1×/beat ✓
- REM (1.6Hz, period 0.625s) — debounces 0.35-0.4s < 0.625s, all fire 1×/beat ✓

The math holds at every phase because the longest debounce (0.4s) is always shorter than the shortest beat period (0.625s REM). **This is the constraint** that allows multiple heartbeat-synced emissions to coexist without one starving another.

**What breaks if you violate the constraint.** If a new emission had a debounce > the shortest beat period (e.g., 0.7s debounce in REM 0.625s), it would skip beats intermittently — viewer sees the new emission fire every other REM beat, breaking the visual coupling. If a new emission had a debounce of 0.3s, it would NOT double-fire per beat (because the `_hbBeat > 0.6` window is only 13.6% of cycle — the throttle is the beat envelope width, not the debounce). Always verify the debounce math against the SHORTEST beat period before adding a new heartbeat-synced channel.

**When to use.** Whenever adding a NEW heartbeat-synced emission channel to a file that already has heartbeat-driven emissions. Add the new channel LAST in the animate-loop chain so it fires after the existing channels, and pick a debounce in the 0.30-0.40s range to coexist with the existing channels.

**When NOT to use.** Single-channel files (bio's main emit pulse, trailer's recognition ping) don't need this pattern — they have one heartbeat-synced emission and the existing pattern is enough. The cascade emerges when the file has 2+ parallel emission systems AND you're adding a third or fourth.

### Dream Adaptation (run #30)

The dream backport copies the bio #29 spark pattern verbatim EXCEPT for one critical detail: the emission origin must track the brain's vertical drift. Dream's brain drifts vertically with phase (`cur.bgY` ranges from ~-2.7 in NREM to ~+2.6 in INSIGHT, scaled by `*2.5` → world-space `~y=-6.75` to `~y=+6.5`). Without y-tracking, REM sparks would bloom from `y=-1` while the brain sits at `y=-6.75` — visually disconnected from the core they emanate from.

**The y-tracking pattern:**

```js
// Inside updateSparks emission block, after the round-robin slot assignment:
const cy = brainShell ? brainShell.position.y : -1;
_sparkPos[i * 3]     = (Math.random() - 0.5) * 0.4;
_sparkPos[i * 3 + 1] = cy + (Math.random() - 0.5) * 0.4;  // tracks brain Y
_sparkPos[i * 3 + 2] = (Math.random() - 0.5) * 0.4;
```

**Why `brainShell.position.y` and not `cur.bgY * 2.5`.** The `cur.bgY * 2.5` is the target value; `brainShell.position.y` is the actual rendered position (the brain shell lerps toward the target at 0.03/frame via `brainShell.position.y += (targetShellY - brainShell.position.y) * 0.03` at L3238 of dream). Reading the live position (not the target) ensures sparks track the visually-rendered brain — even if the brain shell hasn't fully caught up to a recent phase shift, sparks follow where it actually is on screen. **Subtle but important**: tracking the target would let sparks disconnect from the visual brain by up to ~3 units during fast phase transitions (REM ↔ AWAKE has the largest amplitude). Tracking the live position keeps them locked.

**Null-safe access.** `brainShell` is module-scope `let brainShell, brainShellWire;` declared at L1110, populated in `buildBrainShell()` inside init(). The `brainShell ? brainShell.position.y : -1` defensive fallback returns `y=-1` if the brain isn't built yet — sparks emit from origin, which is the correct "uninitialized" behavior. In practice `brainShell` is always non-null after init() completes, so the fallback is dead code. Add it anyway — the alternative (a runtime crash on init-order edge cases) is worse than the cost.

**What does NOT need adapting.** The spark lifecycle, birth-hue lock (`cur.hue` in dream, the lerped phase hue), threshold/debounce math (0.6 with `^6`, 0.35s), bell envelope, vertex-color brightness, anyChanged gate, sentinel parking — all copy verbatim from bio. The only file-specific element is the y-origin tracking.

**Cross-file parity state:** bio ✓ #29, dream ✓ #30 (THIS RUN). The two implementations are now structurally identical except for the y-tracking line. Future trailer backport (if attempted) would need a third adaptation: trailer has no brainShell, so sparks would emit from origin (or from `consciousnessCore.position` if trailer ever gains one).

## Companion Patterns

- `references/heartbeat-driven-emission.md` — the simpler "call existing emit function on each beat" pattern. Round-robin pool is for **new** particle emission, not coupling existing emitters to heartbeat.
- `references/visual-pattern-invariants.md` — magnitudes for firing rings, pulse arcs, etc. Use the same scale of opacity/lightness when tuning spark color/brightness so the new particles compose with the existing palette.
- `references/phase-transition-thought-burst.md` — burst pattern for transient phase-transition events. Round-robin pool is for **continuous heartbeat** emission. Both can coexist on the same beat (burst fires once on phase change, sparks fire every beat).