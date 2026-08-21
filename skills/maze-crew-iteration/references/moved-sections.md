# maze-crew-iteration — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Specific Techniques

### Heartbeat-driven emission burst (bio, run #18)

The heartbeat is a `Math.pow(Math.max(0, Math.sin(beatPhase)), 6)` envelope that peaks briefly per cycle. The `beat` variable is computed locally in `updateHeartbeat()` but is also recomputed locally in 3-4 other call sites (consciousness core, halo, camera tremor, heart wave spawn) using the same formula. The pattern:

```js
// Module scope (near other _lastBeat debounce vars)
let _lastHeartbeatEmit = 0; // debounce for heartbeat-driven pulse emission

// In animate(), after the existing random-emit block:
const _hbBeat = Math.pow(Math.max(0, Math.sin(beatPhase)), 6);
const _hbElapsed = clock.getElapsedTime();
if (_hbBeat > 0.6 && (_hbElapsed - _lastHeartbeatEmit) > 0.35) {
  emitPulse();
  _lastHeartbeatEmit = _hbElapsed;
}
```

**Threshold tuning.** Heart-wave spawn threshold is 0.7; heartbeat-emit threshold is 0.6. The 0.1 offset means heartbeat-emit fires slightly earlier than the wave — thought visibly emerges just before the wave blooms, so the wave accompanies the propagating thought instead of leading it. Brain signal flow: beat peak → thought emerges → wave accompanies → cascade through tissue.

**Debounce pairing.** Heart-wave debounce is 0.4s (`_lastBeatSpawn`); heartbeat-emit debounce is 0.35s. The 0.05s offset is small enough that both fire on the same beat but different enough that they don't quite collide on the same frame. At all four phases (AWAKE/NREM/REM/INSIGHT) both debounces allow exactly 1 fire per beat.

**Visual delta.** Before: stochastic pulse emission, decoupled from heartbeat. After: stochastic + heartbeat-synced pulse emission, each beat visibly triggering a thought. The brain has a clear cognitive rhythm synchronized to its cardiac rhythm. On a 7-second screen-recordable clip, the viewer's eye sees pulses emanating in sync with the EKG trace and consciousness core throb.

**Pulse-count delta:** AWAKE +5.6%, NREM +6.3%, REM +3.8%, INSIGHT +8.3% (modest density bump, but the *rhythm* change is the real win).

**Cross-file parity state:** bio ✓ #18, dream ✓ #27, trailer ✓ #25. Full 3/3 parity after dream #27 backport.

### Heartbeat-driven pulse emission — Dream Adaptation (multi-system files, run #27)

Dream's architecture is structurally different from bio + trailer, and the heartbeat-driven emission pattern has to be adapted accordingly. Bio + trailer have ONE pulse-emission subsystem (a single `emitPulse()` function that creates the activation pulse + firing ring + axon arc through one entry point). Dream has THREE separate pulse subsystems, each with its own emission path:

1. **`heartWaves`** (radial wave shells) — emitted via `heartWaves.push(...)` inside the existing `if (pulse > 0.7 && (t - _lastBeatSpawn) > 0.4)` heartbeat block at L2964-2978. Already heartbeat-driven (pre-existing, run #28 era).
2. **`thoughtPulses`** (inter-region nearest-neighbor thoughts) — emitted via `spawnThoughtPulse()` inside the same heartbeat block. Already heartbeat-driven (pre-existing, run #21 era).
3. **`activationPulses`** (main activation-pulse mesh, traveling bright dots between random memory nodes) — emitted via stochastic `Math.random() < pulseRate` + four phase-distinct branch arms at L3443-3541. Was NOT heartbeat-driven until run #27.

The dream #27 fix added heartbeat-emit ONLY to subsystem #3, the only one that was missing it. The threshold (0.6 with `^6` envelope) is slightly lower than the existing heartbeat block's 0.7 with `^12` so the activation pulse fires ~30ms before the heart-wave (matching bio's two-stage coupling: thought → wave). Debounce 0.35s vs the existing 0.4s so both fire on the same beat in deterministic order.

**Lesson for future cross-file backports.** When the destination file has multiple parallel cognitive-emission subsystems, audit each one individually for heartbeat-coupling. A blanket "the file has heartbeat-driven emission" claim is incomplete until every pulse-emitting subsystem is gated. Recipe:

```bash
# Find every pulse-emission subsystem in the file
grep -nE '\.push\(\{|emitPulse|spawnPulse|push.*\{.*src|activationPulses|thoughtPulses|heartWaves' public/maze-crew-<file>.html
# For each, check whether it's gated by `pulse > X && (t - _lastX) > Y` or purely stochastic (`Math.random()`)
```

If any subsystem is purely stochastic, it's a candidate for the heartbeat-emit pattern (with its own debounce var). The audit-cmd above is the parity-matrix maintenance routine — run it on each file before claiming cross-file parity is closed.

**Cross-file parity state:** the heartbeat-driven emission row of the matrix is now bio ✓ #18 + dream ✓ #27 + trailer ✓ #25 — full 3/3 parity. The multi-system adaptation is documented here so future backports know to inspect each subsystem, not just the main one.

On every phase change, fire a brief burst of 3-6 cascade pulses spread across a ~400ms window so the cognitive mode shift visibly produces thoughts (chromatic pop was retina-only; this adds cognitive content). Each burst pulse flows through the standard `emitPulse()` pipeline so the burst reads as a coordinated thought storm, not a separate visual element. Distinct from chromatic aberration (retinal flash) by being cognitive content.

**The pattern.** When a trigger event has multiple paths (auto-tick + manual override + WS push for phase transitions), split the work into:
- **Single arm hook** in the common event handler — sets `active = true`, resets counters, scales amplitude by destination state
- **Fire block** in the render loop — checks `active`, emits content over the scheduled window, disarms when done

```js
// Module scope
let _phaseBurstState = { active: false, t: 0, fired: 0, total: 4 };
const PHASE_BURST_DUR = 0.40;       // seconds — total burst lifetime
const PHASE_BURST_INTERVAL = 0.07;  // seconds between successive burst pulses

// In notePhaseTransition() (covers all 3 transition paths in one hook):
const _bDef = PHASE_DEFS[currentPhase];
if (_bDef) {
  _phaseBurstState.active = true;
  _phaseBurstState.t = 0;
  _phaseBurstState.fired = 0;
  _phaseBurstState.total = Math.round(3 + _bDef.emitRate * 4);
}

// In animate(), after heartbeat-emit, before pulse loop:
if (_phaseBurstState.active) {
  _phaseBurstState.t += dt;
  const _burstTarget = Math.min(_phaseBurstState.total,
                                Math.floor(_phaseBurstState.t / PHASE_BURST_INTERVAL));
  while (_phaseBurstState.fired < _burstTarget) {
    emitPulse();
    _phaseBurstState.fired++;
  }
  if (_phaseBurstState.fired >= _phaseBurstState.total
      || _phaseBurstState.t >= PHASE_BURST_DUR) {
    _phaseBurstState.active = false;
  }
}
```

**Per-phase amplitude** (via `Math.round(3 + emitRate * 4)`):
| Phase | emitRate | Burst | Duration | Character |
|---|---|---|---|---|
| NREM | 0.08 | 3 | 210ms | quiet whisper |
| AWAKE | 0.30 | 4 | 280ms | mid-flurry |
| INSIGHT | 0.20 | 4 | 280ms | mid-flurry |
| REM | 0.70 | 6 | 420ms | active burst |

**Threshold tuning.** `PHASE_BURST_DUR = 0.40s` matches `triggerPhaseFlash()`'s 260ms + 140ms tail so the burst extends through the visible chromatic flash. `PHASE_BURST_INTERVAL = 0.07s` is short enough that burst pulses overlap as they travel (a 70ms-spaced pulse is still mid-flight when the next one fires its source firing ring), but long enough to read as a series of distinct events. At 60fps = 4 frames between pulses.

**WHILE loop safety.** `_burstTarget = Math.min(total, floor(t / INTERVAL))` — at most `total - fired` pulses per frame, even on a 100ms stutter frame. Stutter-frame safe by construction.

**Cross-file parity:** bio ✓ #20, dream ✓ #21, trailer ✓ #22 (all three now have the feature). The destination-amplitude formula `Math.round(3 + scalar * 4)` is file-agnostic — each file uses its own per-segment cognitive-energy scalar (bio = `emitRate`, dream = `chaos`, trailer = `_speeds[_phaseIdx % _phaseCount]`), yielding 3-9 pulses per transition. Same `PHASE_BURST_DUR` / `PHASE_BURST_INTERVAL` knobs across all three files for timing parity. The trailer backport proves the pattern generalizes to ANY segmented loop, not just state-machine phase cycles — see `references/phase-transition-thought-burst.md` "Trailer Adaptation" section for the per-segment-speed analysis.

**Pulse-count delta:** +17 pulses per 66s cycle (~0.26 extra pulses/sec averaged). Visual density bump +6% at peak burst; the *coordinated-thought-storm* character is the real win — burst pulses fire in 70ms intervals vs random emit's 33ms average, so they visibly bunch as a "flurry" rather than blending into the background.

### Phase-keyed HUD motion with compound-sine biological realism (dream, run #22)

When a small HUD element (eye, indicator, status icon) needs to feel ALIVE across multiple phase states (AWAKE/NREM/REM/INSIGHT) rather than mechanically oscillating, give each phase its own MOTION CHARACTER — not just a different speed but a different frequency band AND amplitude. For the REM rapid eye movement:

```js
// Module-scope: clock already exists, eyeEl cached in init().
if (eyeEl) {
  const t = clock.getElapsedTime();
  let eyeX = 0;
  switch (currentPhase) {
    case 'REM':     eyeX = Math.sin(t * 11.0) * 6.0 + Math.sin(t * 3.7) * 3.0; break; // ±9px rapid saccades
    case 'NREM':    eyeX = Math.sin(t *  0.6) * 3.0;                               break; // ±3px slow drift
    case 'INSIGHT': eyeX = Math.sin(t *  1.5) * 2.0;                               break; // ±2px gentle wander
    case 'AWAKE':   eyeX = 0;                                                      break; // focused center
  }
  eyeEl.style.setProperty('--eye-x', eyeX.toFixed(2) + 'px');
}
```

```css
.orb {
  /* Compose slow-driven scale with rapid-driven translate; */
  /* DO NOT transition transform — would smooth out the rapid component. */
  transform: translateX(var(--eye-x, 0px)) scaleY(var(--eye-open, 1));
  transition: background 1s ease, box-shadow 1s ease;  /* NO transform */
}
```

**Three rules that make this pattern work:**

1. **Compound sines (dominant + secondary with irrational ratio)** read as biological motion. Single sines read as mechanical oscillation. Ratio 11.0/3.7 ≈ 2.97 never beats back into a clean repeating pattern, so the motion never shows a visible period. Same principle as the per-node wobble in the Three.js scene (3 incommensurate frequencies on X/Y/Z).

2. **Frequency bands differentiate phases more clearly than amplitudes alone.** REM at 11Hz reads "rapid" even at ±1px. AWAKE at 0Hz (static) reads "focused." NREM at 0.6Hz reads "drifting." INSIGHT at 1.5Hz reads "wandering." Tuning amplitude is secondary; tuning frequency is primary.

3. **Drop `transition: transform` from any element with rapid per-frame motion.** The established pitfall in this skill (CSS-transition-lag on per-frame-driven properties) has a subtle extension: CSS transitions on transforms would ALSO smooth out rapid components, defeating the purpose. JS-lerped values already produce smooth visible motion — no transition needed.

**Magnitude tuning:** bound amplitude by `floor((elementWidth - childWidth) / 2)` so the child's edges stay within the parent's `overflow:hidden` clip region. For 26px-wide eye + 7px-wide orb, max safe amplitude is ±9px. Don't exceed — overflow clipping reads as a bug.

**Visibility-gating analysis (planning step, not runtime gate):** if the element has an overlay state (closed lid covering the orb), the motion is naturally invisible when the overlay is fully closed and partially visible during mid-close. The mid-close partial visibility IS the desired effect (viewer sees "the eye is closing but the eye underneath is moving" — exactly the REM signature). Don't add explicit `if (overlayOpen)` gates — the natural overlay opacity handles it.

**Defensive gating.** `if (clock)` and `if (eyeEl)` guards are cold-path safety — `clock` is set in init() and the DOM ref is cached in init(), so the guards should never fail in practice. Add them anyway; alternative (a runtime crash on init order edge cases) is worse than the ~1ns/frame gate cost.

**Full implementation + magnitude tuning rationale + verification:** see `references/run-history.md` Run #22 and `references/visual-pattern-invariants.md` "Phase-Keyed HUD Motion" section.

**Cross-file parity state:** dream ✓ #22. Bio and trailer don't have an awareness-eye element (they have other HUD elements — bio's full-width EKG corner, trailer's brand label + chromatic split). Pattern is reusable if those files ever add a similar small-character HUD element.

### Phase-aware CSS animation timing via CSS variable interpolation (bio, run #21)

When an existing CSS `@keyframes` animation should speed up or slow down with the organism's state (pulseSpeed, phase, camera proximity, etc.), drive its `animation-duration` from a CSS custom property written by JS each frame. This keeps the animation declarative (still CSS, no per-frame `transform` writes) while making its timing phase-aware.

**The pattern.** Define a `@keyframes` animation as normal, but reference a CSS variable for the duration:

```css
#hud .brand-glyph {
  animation: brandSpin var(--brand-spin-dur, 16s) linear infinite;
}
@keyframes brandSpin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
```

Write the variable from JS each frame (no per-frame `transform: rotate(...)` calls, no animation RESTART on speed change):

```js
// In updateHeartbeat() right after the existing --brand-glyph-scale write:
document.documentElement.style.setProperty(
  '--brand-spin-dur',
  (16 / Math.max(currentPulseSpeed, 0.1)).toFixed(2) + 's'
);
```

**Browser interpolation behavior (the non-obvious part).** When `animation-duration` is bound to a CSS variable and that variable's value changes, modern browsers (Chrome 84+, Firefox 75+, Safari 14+) **interpolate the playback rate smoothly** — the animation continues from its current angle at the new rate, NO restart. The earlier mental model "changing duration restarts the animation" is wrong for the variable-binding case. Verified behavior on bio #21: the `⌬` glyph smoothly accelerated from 16s → 5.7s on AWAKE→REM without snapping to rotation 0. The DOM `Animation` API exposes this — `animation.playbackRate` updates to match the new duration, and `currentTime` is preserved.

**Why this beats JS-driven rotation.** Naïve alternative: `element.style.transform = 'rotate(' + (t * speed) + 'deg)'` every frame. Costs a layout flush per frame and competes with any other transform on the same element (the brand-glyph-pulse wrapper already does `transform: scale(...)` for heartbeat). The CSS-animation approach is GPU-composited, composes cleanly with sibling transform pipelines (the wrapper transform applies first, then the inner rotation), and a change-detection gate on the setProperty write skips identical values.

**Magnitude choice: write `animation-duration` not `animation-delay`.** A common mistake is to try `animation-delay: -${speedOffset}s` to fast-forward. This works but couples the rate to time-since-page-load rather than current state — every reload starts at the same place. With `animation-duration`, the speed reflects the *current* state immediately.

**Floor against division-by-zero.** Always wrap the speed divisor with `Math.max(speed, 0.1)` — a 0-duration animation is invalid CSS and freezes the element. Only matters during init edge cases, but the floor is essentially free.

**Cross-file parity state:** bio ✓ #21. Dream and trailer have no rotating brand glyph. Bio-only feature — not a cross-file parity issue.

**Full implementation + verification:** see `references/phase-aware-css-animation.md`. Worked example from bio #21 with the per-phase rotation table and the browser-support verification recipe.

### Cognitive thought-sparks — cross-file additive particle pool (bio #29, dream #30, trailer #31)

When the brain "thinks out loud" — visibly releasing additive point particles from its center into the cosmos on each heartbeat peak — every organism-family visualization needs the same particle-pool subsystem. Three files, three adaptations. The construction is identical (BufferGeometry + DynamicDrawUsage + PointsMaterial + AdditiveBlending); the only file-specific deltas are the **birth-hue source** and the **y-origin tracking**.

**The shared pattern.** Per heartbeat peak (`Math.pow(Math.max(0, Math.sin(beatPhase)), 6) > 0.6` with 0.35s debounce — fires when `sin(x) > 0.908`, ~13.6% of cycle), spawn ONE spark into the next round-robin slot of a 40-slot Float32Array pool. Velocity uses `Math.acos(2r-1)` for correct area-weighted phi (sparks don't cluster at poles). Lifetime 1.5s with bell-curve brightness via `Math.sin(life * Math.PI)`, vertex color magnitude 1.5× for additive headroom. anyChanged gate on `needsUpdate` — typical frame has 0-1 changes. **Identical across bio + dream + trailer** — copy the constants verbatim, copy the velocity formula verbatim.

**Birth-hue source adaptation (file-specific).**

- **bio**: `currentBeatHue` is a module-scope state variable maintained by `lerpPhaseColors()` each frame. `updateSparks()` reads it directly from module scope. Cleanest pattern.
- **dream**: `cur.hue` is the per-phase hue lerped by `lerpState()` each frame and stored on the `cur` object. Module-scope access via `cur.hue`. Same shape as bio.
- **trailer**: `hue` is a **`const` declared inside the animate() function** at the phase-fog block. It's NOT module-scope. `updateSparks()` is declared at module scope, so a free reference to `hue` inside `updateSparks` would throw `ReferenceError` (free variables resolve through the lexical declaration scope, not the call scope). **Fix: pass `hue` as a parameter** — `updateSparks(dt, birthHue)` called as `updateSparks(dt, hue)`. Mirrors trailer's existing pattern for inter-region thread bridges (`t.dstHue` carried in the data record, not read from outer scope).

**Cross-file lesson:** when porting a module-scope-state reader between files, audit whether the state variable is actually module-scope in the destination. If it's local to the call function, switch the reader to a parameter — don't promote the variable to module scope (that's a bigger change than the feature itself).

**Y-origin tracking adaptation (file-specific).**

- **bio**: no y-tracking needed (consciousness core is fixed at origin).
- **dream**: `cur.bgY` ranges from -2.7 (NREM) to +2.6 (INSIGHT), scaled by `*2.5` → -6.75 to +6.5 world units. Without tracking, REM sparks would bloom from y=-1 while the brain sits at y=-6.75 — visually disconnected. **Fix:** sparks emit from `(rand-0.5)*0.4, brainShell.position.y + (rand-0.5)*0.4, (rand-0.5)*0.4` — y-axis anchored to the brain shell's current vertical position.
- **trailer**: no y-tracking needed (nucleus is fixed at origin). Symmetric jitter on all three axes.

**Origin-spread tuning.** bio uses 0.3u spread; trailer uses 0.4u spread. Rationale: trailer's heart rate is slower (rph 0.5-0.8 Hz vs bio's pulseSpeed range 0.3-1.0), so sparks fire less frequently. The larger spread ensures simultaneous sparks at trailer's peak rate still visibly separate as distinct particles. With 0.3u spread at 0.8 sparks/sec, sparks would tend to overlap.

**Per-phase spark rate sanity check.** Always run this math in the log entry so future runs can verify. Formula: `sparkRate = heartRate × 1.0` (the 0.35s debounce allows exactly 1 fire per beat at all heart rates ≥ 0.35 Hz). Visible-at-any-moment = `sparkRate × 1.5s lifetime`. Pool saturation = `SPARK_CAP / sparkRate` seconds.

| File | Heart rate range | Spark rate | Visible overlap | Pool saturation |
|---|---|---|---|---|
| bio | 0.25-1.6 Hz | 0.25-1.6/sec | 0.4-2.4 sparks | 25-160s (≥16s lifetime) |
| dream | 0.25-1.6 Hz (4 phases) | 0.25-1.6/sec | 0.4-2.4 sparks | 25-160s |
| trailer | 0.5-0.8 Hz (rph modulated) | 0.5-0.8/sec | 0.75-1.2 sparks | 50-80s |

**Cross-file parity state:** bio ✓ #29 + dream ✓ #30 + trailer ✓ #31 — full 3/3 parity as of run #31 (2026-06-23). Bio is the canonical reference implementation; dream and trailer are both straight ports with the file-specific adaptations documented above.

### Boot fade-in via CSS transition + JS opacity write (trailer, run #28)

When a file has a "loading overlay" that fades out to reveal the canvas (or any wrapper overlay that obscures the rendered content until init() completes), the boot transition can read as a hard cut if the canvas underneath snaps to opacity 1 the moment the overlay starts fading. Add a parallel canvas opacity transition that fades FROM black during the same window the overlay fades OUT to black — viewer sees the loading text dissolve over an emerging brain instead of "loading overlay dissolves, revealing a pre-existing maze."

**The pattern.** Three coordinated changes:

```css
/* Extend the existing transition shorthand — DO NOT replace it. */
#c {
  /* Existing transition for loop-seam chromatic desaturation preserved */
  transition: filter 0.7s ease, opacity 0.8s ease;
  opacity: 0;  /* Initial state — JS writes opacity: '1' after init */
}
```

```js
// In init(), AFTER _canvasEl = document.getElementById('c'); (line ~653 in trailer):
if (_canvasEl) _canvasEl.style.opacity = '1';
document.getElementById('loading').classList.add('gone');
```

**Why extend the existing `transition:` shorthand rather than replace it.** The `#c` rule already had `transition: filter 0.7s ease` for `startFadeLoop`'s chromatic desaturation on loop seams. Replacing it would lose that capability. Adding `, opacity 0.8s ease` appends a new property to the same shorthand — both transitions are tracked independently by the browser, run in parallel, and don't interfere.

**Why `opacity: 0` in the CSS rather than setting it from JS first.** CSS initial state is set BEFORE the first paint, so the canvas is invisible from t=0 (the loading overlay covers it anyway, but this is the correct first-frame paint even if the overlay somehow failed to render). JS then writes `opacity: '1'` AFTER init completes; the CSS transition kicks in because the computed value changed.

**Why the duration mismatch (loading 0.6s vs canvas 0.8s).** Both fades start on the same paint frame (because init() is synchronous — see pitfall 1d "synchronous-init() CSS-transition batching"). At t=0.6s the loading text is fully gone but the canvas is only at 75% opacity (still 25% to go). The 200ms extra means the canvas finishes appearing AFTER the overlay is gone — viewer sees the brain visibly emerging from black during the last 200ms, not arriving pre-lit. If both were 0.6s, they'd finish simultaneously and the dissolve would feel truncated. If both were 1.0s, the boot would feel sluggish.

**Why NO `display: none` between them.** Keeping the canvas in the layout (just transparent) means the WebGL renderer runs from t=0, even during the fade. The canvas is fully rendered but invisible. By the time the opacity reaches 1.0, the maze is already mid-animation (a frame or two into the active scene). If you used `display: none` + `display: block`, the renderer might not initialize at all (some browsers defer WebGL canvas init until visible), causing a flash of black right after the reveal.

**The ordering trap (see pitfall 1d for full detail).** The natural placement for the opacity write is right next to `loading.classList.add('gone')` because they're conceptually paired (both fire when the scene is "ready"). But `_canvasEl` is often resolved LATER in init() than the loading-class-add line — the family rule says "resolve overlay refs in init(), use cached pointers elsewhere," which doesn't dictate the order between cache resolutions. **Use site MUST be AFTER the resolution site in source order, or the defensive `if (_canvasEl)` guard silently swallows the operation and the canvas stays at opacity 0 forever.**

**Synchronous init() CSS-transition batching.** Both `loading.classList.add('gone')` and `_canvasEl.style.opacity = '1'` happen during init()'s synchronous execution. The browser batches the style invalidations and starts BOTH CSS transitions on the next paint frame, not on per-mutation boundaries. So even if the source-order distance is 50+ lines (as in trailer — opacity write at L668 vs loading-class-add at L617), both transitions begin together. This is the property that makes the cross-fade work; if init() were async or used `requestAnimationFrame` between the mutations, the transitions would shift and the cross-fade would become a sequential fade.

**Visual delta.** Before: hard cut from black-with-text to black-with-maze as the loading overlay starts dissolving. After: loading text dissolves over an emerging brain; at t=0.6s the loading text is fully gone but canvas is at 75% opacity; the brain visibly "swims up out of the dark" during the 200ms gap before full opacity.

**Cross-file parity state:** trailer-only. Bio and dream don't have a separate loading overlay (they're persistent visualizations with no boot reveal needed). Trailer is the only file with a fade-to-black loop seam (`#fade` overlay), so it's also the only file with a complementary fade-from-black boot. No cross-file parity gap created or closed.

**When to use:** any file with a loading overlay that fades out to reveal a WebGL canvas / image / content area. The "loading text → maze" handoff is the most cinematic opportunity in any boot sequence.

**When NOT to use:** if the loading overlay fades INSTANTLY (no transition) and the canvas appears via some other mechanism (e.g., replacing the overlay with a `<canvas>` element via DOM swap). The pattern only applies when there's a real opacity transition to cross-fade against.

### Per-node heartbeat-driven size + lightness (bio #N+18, dream #24)

When a node cloud (`memoryNodes`, `tissueGroups[].nodes`, etc.) is already driven by SLOW rhythms (`breathFactor`, `energyBoost`, `actGlow`, `n.fired`) but the per-node size/lightness does NOT respond to the heartbeat envelope, the cloud reads as a uniform tissue that doesn't throb at the cellular scale. Add a per-node phase offset to the heartbeat so each node peaks at a different moment, creating visible wavefronts that travel through the cloud on each cardiac cycle.

**The formula** (mirror verbatim across files):

```js
const phaseOff = n.id * 0.37 + n.energy * 1.5;
const beatContrib = Math.pow(Math.max(0, Math.sin(hbPhase + phaseOff)), 4);
const sz = n.baseSize * (1 + existingSlowTerms + beatContrib * <sizeMult>) * breathFactor;
const lightness = <base> + <existingTerms> + beatContrib * <lightMult>;
```

**Phase-offset math.** With N nodes at multiplier 0.37: `wavefrontCount ≈ N * 0.37 / (2π)`. For 800 nodes → ~47 wavefronts visible at any time, ~17 nodes wide. For 200 nodes → ~12 wavefronts. The 0.37 constant is tuned so each wavefront spans ~17 nodes — wide enough to read as a band, narrow enough to make wave propagation visible.

**The `^4` exponent is intentional.** The file's default heartbeat envelope is `^12` (sharp spike, ~5% of cycle is meaningful) — perfect for shell/halo/screen-edge flash channels. The per-node beat uses `^4` (broader pulse, ~50% of cycle is meaningful) because per-node phase offsets need a sustained envelope to read as traveling waves. With `^12`, the per-node peaks would be so brief that the eye couldn't see the wave traveling; with `^4`, each node's pulse has a clear ~50% of the beat cycle where it's meaningfully larger, giving the per-node phase offset time to translate that into visible wavefront propagation.

**The magnitude-vs-competing-signal rule.** Don't copy bio's 0.45/0.30 verbatim to a new file — tune against the **dominant existing per-node signal** already in the size/lightness formula. Rule of thumb: new heartbeat magnitude should be **3-5x smaller than the dominant existing term** so it reads as a layered second rhythm rather than competing for primary attention. Bio's dominant is `n.fired` (peaks 0.6) → heartbeat 0.45 is comparable. Dream's dominant is `actGlow` (peaks 1.0) → heartbeat 0.20 (about half bio's). Document the ratio in the rationale comment.

**Implementation cost:** zero new module-scope state, zero new DOM refs, zero new allocations. 2 const decls + 1 size term + 1 lightness term per node. Pure arithmetic — Math.pow is native, no `new`. Works in any per-node loop where `n.id` (or equivalent index), `n.energy` (or equivalent 0..1 field), and the heartbeat phase angle are already available.

**Why this beats a uniform throb.** Without per-node phase offset (offset = 0 constant), all nodes peak in lockstep on each beat — the brain reads as a single object that grows +20% on each beat, like a balloon inflating. With the phase offset, ~47 wavefronts visibly travel through the cloud at the heart rate, so the brain reads as 800 living cells firing in a coordinated ripple. The difference is "alive as a body" vs "alive as a brain."

**Per-phase heart rate drives wave appearance.** The wave advances at the per-phase heart rate (`cur.breathRate` in dream, `currentPulseSpeed` in bio). REM (1.6Hz) shows rapid turbulent ripples, NREM (0.25Hz) shows slow breathing waves, AWAKE/INSIGHT (1.0Hz) show mid-tempo — all from the same formula. The phase-rate-driven wave speed gives each phase a distinct visual rhythm for the same heartbeat code.

**Cross-file parity state:** bio ✓ #N+18, dream ✓ #24, trailer ⬜ n/a (no per-node cloud). Full implementation + verification recipe + magnitude-vs-competing-signal analysis + the copy-verbatim-vs-tune-to-destination distinction: see `references/per-node-beat.md`.

### Threshold/debounce analysis pattern

For any spawn rate controlled by heartbeat, compute per-phase expectations:

```text
- AWAKE (heart rate ~1.0 Hz, period ~1.0s): heartbeat-emit fires every ~1.0s
- NREM (heart rate ~0.3 Hz, period ~3.3s): both debounces allow 1 fire per beat
- REM (heart rate ~1.6 Hz, period ~0.625s): both debounces allow every beat
- INSIGHT (heart rate ~1.0 Hz, period ~1.0s): both debounces allow every beat
```

Show this in the log so future runs can verify the math.

## Pitfalls (from the run history)

1. **The `const beat` temporal dead zone** (trailer #N+5, pre-fix) — referencing `beat` before its declaration. Always recompute `beat` locally at each consumer site; don't hoist to module scope.
1a. **TDZ from a `const` declared in a SIBLING block** (bio #23, caught at syntax-check) — when an earlier code path declares `const _foo = …` inside an `if (cond) { … }` block and a NEW block in the same function tries to reference `_foo` BEFORE that declaration's source line, it throws `ReferenceError: Cannot access '_foo' before initialization` even though the variable *exists* in source. Block-scoped `const`/`let` are subject to TDZ at every access site — order of access within the function matters, not order of lexical declaration across blocks. Symptom: `node --check` exits 0 (the parser is happy because the variable IS declared somewhere in the function scope), but the runtime throws on the first animate frame and the try/catch swallows it → "feature added but visually nothing happens." Fix options: (a) **derive locally** — compute the value in your own block via a fresh `setHSL` / `Math.round` call (zero alloc if you reuse a hoisted scratch like `_beatColor`); (b) **hoist the source** — move the `const _foo = …` to the top of the function so all sibling blocks see it; (c) **drop the `const`** — make it a module-scope `let` (loses block-scoping but visible everywhere). Option (a) is preferred when the scratch is reused, since it adds no new module-scope state and keeps the change small. **Verification catch recipe:** before committing the patch, search for any name your new block references that is also `const`/`let` declared later in the same function: `grep -nE '(const|let) (\\b'$(echo $names | tr ' ' '\\|')'\\b)' <file> | awk -F: '$1 > <my_line>'` — any hit is a TDZ risk.

1b. **TDZ audit false-positive from nested for-loop `let i = …` declarations** (dream #24, false alarm) — the recipe above (and any naive grep for `(const|let) i\b` after the new block's line) flags every nested `for (let i = 0; …)` in the file as a TDZ risk for the outer `i`. This is wrong because **block-scoping keeps them separate**: a `let i` inside a nested `for (...)` block has its own scope and does NOT shadow the outer `i`. The audit must distinguish between (a) sibling-block declarations that share the same function scope (real TDZ risk per pitfall 1a), and (b) nested-block declarations that are isolated by their own block scope (false positive). Practical filter: skip any `let i` that appears as part of a `for (let i = …)` expression — those are guaranteed block-scoped and cannot cause TDZ on the outer `i`. The same filter applies to any `let` declared in a `for (... ; ... ; ...)` head, in a `{ … }` block that opens immediately after the `for`, or as a function parameter (parameters are function-scoped but already declared before the body). Only flag declarations that share the function scope with the new block. **Verification of the filter:** after applying it, run the patch and confirm the existing for-loop's `i` still iterates correctly (the iteration count should be unchanged from before). If iteration breaks, the filter is wrong — the for-loop is sharing scope (rare; usually means a manually-written `for` without proper block delimiters).

1c. **Naive regex-based balance check fails on template literal `${...}` substitutions** (run #25, 2026-06-23) — the established verification recipe is "strip strings + comments with regex, then count `{ } ( ) [ ]`." This is broken for the maze-crew files because they use template literals with `${expr}` substitutions extensively (e.g. `` `rgba(${r},${g},${b},${a})` ``, `` `0 0 ${blur}px ${spread}px ${...}` ``, `` `M${x1} ${y1} L${x2} ${y2}` ``). The regex strip treats the whole template literal as an opaque string, so it doesn't count braces INSIDE the substituted expression — but it DOES count the `${`'s opening `{` (if the regex catches it) and never counts the matching `}`. Result: false-positive imbalances of +2 to +30 braces on a file that `node --check` confirms is syntactically valid. **Symptom:** `grep -cE '\\{' | grep -cE '\\}'` (or the equivalent Python regex-strip-then-count recipe) reports a non-zero delta on a file where `node --check` exits 0. **Fix:** use the state-machine checker at `scripts/balance_check.py` — it properly tracks state (`code` / `squote` / `dquote` / `tpl` / `tpl_expr` / `line_comment` / `block_comment` / `regex`) and recurses into template literal `${...}` substitutions. Reports `{` / `(` / `[` deltas with 0/0/0 = valid. Also reports a "noise" count of characters consumed inside `tpl_expr` (these don't affect validity; the noise metric is for diagnosis if a real imbalance ever appears — large noise on a file with 0/0/0 means the file is fine, the deltas are from deep template-literal nesting). **Discovered on trailer #25:** the naive recipe reported `Braces: 77/75 (delta +2)` and `Parens: 363/362 (delta +1)` on the 143,476-char module; the state-machine script reported `0/0/0`; `node --check` exited 0. All three agreed once the correct tool was used. **When NOT to use the script:** if you've already extracted a JS-only file (no HTML) and the file is < 1000 lines, the naive regex is fine — the script's only real win is on files with heavy template-literal use. **Companion to pitfall 1b:** both are about naive verification recipes giving false signals. The lesson is the same: build a proper structural checker, don't lean on a regex.

1d. **Defensive `if (_cachedRef)` guards hide use-before-resolve bugs on cached DOM refs** (run #28, trailer.html — caught mid-run, NOT a real-world bug shipped to production). The defensive null-guards that the family rule mandates (`if (_chrR) _chrR.style.transform = ...`, `if (_hudEl) _hudEl.style.opacity = ...`, etc.) are ESSENTIAL for safe runs — but they have a sharp edge: **when the new use site is placed BEFORE the cache resolution in init()'s source order, the guard returns false and the operation is silently skipped**. There is NO runtime error, NO `node --check` failure, NO `try/catch` trip — the canvas/widget just stays at its initial state forever.

The classic failure pattern: when adding a new feature that needs to write to a cached DOM ref (`_canvasEl`, `_heartbeatEl`, `_chrAb`, `_vignetteEl`, `_diagEl`, etc.), the natural instinct is to put the new write NEAR the existing feature's writes (e.g., near the `loading.classList.add('gone')` call for boot-related changes). But that natural placement is often EARLIER in init() than where the ref was originally resolved. The guard makes the bug invisible.

**Real example from trailer #28 (this run):** The boot fade-in was initially placed at the Ready block right next to `loading.classList.add('gone')` (around L617). `_canvasEl = document.getElementById('c')` is resolved much later, at L653. Initial code:
```js
// At Ready block (L617-628), BEFORE _canvasEl is resolved at L653:
if (_canvasEl) _canvasEl.style.opacity = '1';  // guard returns false → silently skipped
document.getElementById('loading').classList.add('gone');
```
The `if (_canvasEl)` guard correctly evaluates to false (the ref hasn't been resolved yet at L617), so the opacity write is skipped. The canvas stays at CSS `opacity: 0` (set in the new CSS rule) for the entire page lifetime. Loading text fades out, viewer sees a permanently black screen. No errors, no warnings, no console output.

**Why `node --check` doesn't catch it.** The code is syntactically valid — `_canvasEl` is declared at module scope (line ~378), so the reference resolves at parse time. The runtime issue is value-nullness, not symbol-resolution. `node --check` only does syntax checking, not runtime value checking.

**Why the try/catch doesn't catch it.** There's no exception thrown. The guard returns false and execution continues normally. The animate loop runs fine, just rendering against an invisible canvas.

**Detection recipe (apply BEFORE committing any patch that adds a new use of an existing cached DOM ref):**
1. List every cached DOM ref the new feature writes to (e.g., `_canvasEl`, `_heartbeatEl`).
2. For each ref, find the line where it's RESOLVED in init() (the line `_xxxEl = document.getElementById('xxx');`).
3. For each ref, find the line where the NEW code USES it.
4. **Use line must be AFTER resolve line** in source order. If use line < resolve line, the guard will silently swallow the operation.

**Fix options, ranked:**
- **(a) Move the new code AFTER the resolution site.** Simplest, lowest-risk. The use site being adjacent to the resolve site (and not adjacent to the conceptually-related existing code) is a small cost.
- **(b) Move the resolution site EARLIER** in init() (e.g., resolve all overlay refs at the top of init(), before any consumer). Larger change but cleaner — resolves the family-rule invariant that "overlay refs are resolved in init() before they're used" without per-feature ordering games.
- **(c) Skip the guard for THIS use site** (no `if (_xxxEl)`). Unsafe — if init() is called before DOM ready, the property write throws. Don't do this.

**The synchronous-init() CSS-transition batching insight (bonus lesson from the same run).** Once the ordering bug is fixed by moving the opacity write to AFTER `_canvasEl` resolution, the next question is: will the two CSS transitions (`#loading` opacity 0.6s fade + `#c` opacity 0.8s fade) start at the same moment? Yes — because init() runs SYNCHRONOUSLY top-to-bottom. Both DOM mutations (`loading.classList.add('gone')` at L617 + `canvas.style.opacity = '1'` at L668 after the fix) are committed during the same synchronous JS execution cycle. The browser processes style invalidations based on the COMPUTED values after the JS execution finishes — not per-mutation. So both transitions start together on the next paint. If init() were async (used `requestAnimationFrame` between the two mutations), the timing would shift and the cross-fade would become a sequential fade. **Lesson:** in init(), batch all boot-time DOM mutations together for synchronized transitions.
2. **CSS `transition: opacity 2s` on `#vignette`** (dream #12) — lagged the per-frame opacity write by 2s. Strip the transition, let JS be authoritative.
3. **CSS `transition: filter 0.7s ease` on `canvas`** (trailer #13) — generic selector, also matched `#grain` which shouldn't transition. Split into `#c, #grain { display: block; ... }` + `#c { transition: filter 0.7s ease }`.
4. **Dead `NODE_COUNT = 900` const** (trailer #17) — declared but never referenced. REGIONS[].count sum is the single source of truth. Remove or replace with a comment explaining why.
5. **`getElementById` in animate-adjacent paths** (bio #11/#14, dream #3/#4/#7, trailer #1) — all overlay refs must be cached. Audit all files with `grep -nE 'getElementById' public/maze-crew-*.html` and check each call site is init() or a one-shot handler.
6. **Empty .maze-crew-iter.log rotation state when files were just created** — fall back to mtime-based rotation: `ls -la public/maze-crew-*.html`, pick the oldest mtime as the "next" file.
6a. **Module-scope-state reader ported to a file where the variable is local to the call function** (run #31, trailer #31) — bio's `updateSparks()` reads `currentBeatHue` from module scope (set by `lerpPhaseColors()` each frame); trailer's equivalent state is `hue`, but `hue` is a `const` declared INSIDE `animate()`. If `updateSparks()` is declared at module scope and references `hue` directly, it throws `ReferenceError: hue is not defined` on first animate frame (free variables resolve through LEXICAL declaration scope, not call scope — `hue` is declared inside `animate`, not at module scope). Symptom: `node --check` exits 0, but the animate catch handler increments `_frameErrCount` past 30 and the diagnostic surface "⟡ signal degrading — refresh to restore" appears within 0.5s of boot. Detection: before porting any module-scope-state reader, grep for the variable name at module scope in the destination file. If only found inside `animate()`, switch the reader to a parameter: `updateSparks(dt, birthHue)` called as `updateSparks(dt, hue)`. Fix options, ranked: (a) **switch to parameter** — cleanest, smallest blast radius; (b) **promote the variable to module scope** with `let hue;` at top + `hue = phaseHue(elapsed);` in animate — bigger change, affects every consumer; (c) **make updateSparks an inline block in animate** — loses reusability. Option (a) is the established pattern in trailer's inter-region thread bridges (`t.dstHue` carried in the data record). **When NOT to apply this:** when the destination variable IS module-scope (bio's `currentBeatHue`, dream's `cur.hue`) — direct reference works fine. The audit is destination-specific.
