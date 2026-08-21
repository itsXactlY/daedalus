# Phase Transition Thought Burst (Bio #20)

## The Pattern

On every phase change, fire a brief burst of 3-6 cascade pulses spread across a ~400ms window so the cognitive mode shift visibly produces thoughts. The transition had already been firing a chromatic pop (retina), FOV kick (camera), and color lerps (palette) — but no new pulses were emitted. The brain reorganized itself into a new sleep stage without visibly *thinking* about it. With this pattern, every phase change lands as a felt cognitive event: chromatic flash + thought flurry → tissue reacts (activation echoes + arrival flashes + cascade follow-ups).

## Implementation — Two-Hook Arming Pattern

When the trigger event (phase transition) has multiple paths (auto-tick, manual override, WS push), split the work into a **single arm hook** (in the common event handler) and a **fire block** (in the render loop):

```js
// ─── Module scope ────────────────────────────────────────────────
let _phaseBurstState = { active: false, t: 0, fired: 0, total: 4 };
const PHASE_BURST_DUR = 0.40;       // seconds — total burst lifetime cap
const PHASE_BURST_INTERVAL = 0.07;  // seconds between successive burst pulses

// ─── Arm hook: notePhaseTransition() — covers ALL 3 trigger paths ──
function notePhaseTransition() {
  // ... existing cycle counter + _phaseKick = 1.0 ...
  const _bDef = PHASE_DEFS[currentPhase];
  if (_bDef) {
    _phaseBurstState.active = true;
    _phaseBurstState.t = 0;
    _phaseBurstState.fired = 0;
    _phaseBurstState.total = Math.round(3 + _bDef.emitRate * 4);
  }
}

// ─── Fire block: animate(), after heartbeat-emit, before pulse loop ──
if (_phaseBurstState.active) {
  _phaseBurstState.t += dt;
  const _burstTarget = Math.min(
    _phaseBurstState.total,
    Math.floor(_phaseBurstState.t / PHASE_BURST_INTERVAL)
  );
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

## Why Two Hooks (Arm + Fire)

The single arm hook covers all transition paths in one place:
- **Auto-tick**: `updatePhase()` → `notePhaseTransition()` (every ~14-22s when phase ends)
- **Manual override**: `window.manualPhase()` → `notePhaseTransition()` (user presses Space)
- **WS push**: `tryConnectWS.onmessage` → `notePhaseTransition()` (external phase event)

Putting the fire block in `notePhaseTransition()` directly would force all 3 paths to call `emitPulse()` synchronously — that creates a single-frame traffic jam of overlapping pulses, vs a readable cognitive flurry spread across 4 frames. Splitting into arm + fire preserves the single-source-of-truth emit pipeline while keeping all 3 transition paths covered.

The fire block lives BEFORE `ensurePulseMesh()` / `ensureAxonArcMesh()` / the pulse loop in `animate()`, so burst pulses are pushed to `allPulses` before the loop iterates — they get processed in the same frame they're emitted (no 1-frame lag).

## Per-Phase Amplitude Analysis

`Math.round(3 + emitRate * 4)` produces 3-6 pulses per transition, scaled by the destination phase's emitRate:

| Phase  | emitRate | Burst size | Duration | Character |
|--------|----------|------------|----------|-----------|
| NREM   | 0.08     | 3 pulses   | 210ms    | quiet whisper — even the gearshift is sleepy |
| AWAKE  | 0.30     | 4 pulses   | 280ms    | mid-flurry — conscious thought |
| INSIGHT| 0.20     | 4 pulses   | 280ms    | mid-flurry — the "aha" crystallizes |
| REM    | 0.70     | 6 pulses   | 420ms    | active burst — gearshift is itself a dream event |

`Math.round` snaps to integers so the burst fires exactly N pulses, never a fractional count. At 60fps:
- 70ms burst interval = 4 frames between pulses — each pulse has time to fire its own firing ring before the next one's ignition lands.
- 3-6 pulses in 210-420ms = 1-3 pulses in-flight simultaneously at peak (well under PULSE_CAP = 2250).

## Duration Tuning

`PHASE_BURST_DUR = 0.40s` matches `triggerPhaseFlash()`'s 260ms setTimeout + a 140ms tail:
- 0.26s: chromatic flash visible
- 0.26-0.40s: chromatic flash fading, last burst pulse's arrival flash still visible

Long enough to feel "thought flurry", short enough that the burst doesn't bleed into the new phase's first beat cycle (NREM's slow heartbeat period is 3.3s, so 0.40s is 12% of the next NREM beat — visually distinct from the next beat peak).

## WHILE Loop Safety

`_burstTarget = Math.min(total, floor(t / INTERVAL))` is the stutter-frame safety net:
- 60fps frame (dt≈0.0167s): target advances by 0.24 slots/frame → loop fires 1 pulse per 4 frames.
- 100ms stutter frame (dt=0.1s, can happen on tab-switch): target jumps by 1.4 slots → loop fires 1-2 pulses to catch up, never more (bounded by `Math.min(total, ...)`).
- 1000ms hang: dur cap kicks in at 0.4s, burst disarms with whatever subset of pulses fired.

Zero risk of unbounded emitPulse() loop, even on a hung render thread.

## Reset Semantics

`notePhaseTransition()` always resets `active/t/fired` (never just appends). Back-to-back transitions (auto-tick + WS push in the same frame, or rapid manual cycling) re-arm the burst from scratch. Matches `_phaseKick = 1.0` precedent.

## Pulse-Count Delta

Per phase: NREM +3 (3-pulse burst on NREM transitions), AWAKE +4, INSIGHT +4, REM +6. Per 66-second cycle (4 transitions): +17 pulses per cycle, ~0.26 extra pulses/sec averaged.

Visual density bump is +6% at peak burst, but the *coordinated-thought-storm* character is the real win — burst pulses fire in 70ms intervals vs random emit's 33ms average, so they visibly bunch as a "flurry" rather than blending into the random background.

## OFF-Cycle Cost

The animate-loop fire block is wrapped in `if (_phaseBurstState.active)`. Common case between transitions (~99.4% of frames in the 66s loop): one comparison + one false branch. Zero allocations, zero DOM lookups.

## Visual Delta

**Before:** Phase transition fires chromatic pop (260ms), FOV kick (4° lens widen → settle), #h-phase pill text/color swap, color lerps. Viewer sees a state change without a thought — "the brain changed color, but didn't think about it."

**After:** Same chromatic pop + FOV kick + pill swap + color lerps, AND 3-6 cascade pulses spread across 210-420ms firing rings at their sources, traveling along axons, crossing between regions via inter-thread bridges, exploding in arrival flashes at their destinations, accumulating region activation echoes. The viewer sees a state change WITH thoughts — "the brain just had a thought flurry that wrapped across regions because the mode shifted."

## Implementation Correctness Checklist

- [x] `_phaseBurstState` is a single mutable object literal reused across all transitions — zero per-transition allocation, zero per-frame GC.
- [x] `emitPulse()` is the existing shared pulse-pipeline entry point — same one used by regular random emit + heartbeat-driven emit. Each burst pulse goes through the full chain: firing ring, inter-region thread, axon arc, trail, arrival flash, region echo, cascade. No new pulse-emission code path.
- [x] Animate-loop block wrapped in `if (_phaseBurstState.active)` so OFF-cycle cost is one comparison + false branch.
- [x] Fire block placed BEFORE `ensurePulseMesh()` / `ensureAxonArcMesh()` / pulse loop — burst pulses pushed to `allPulses` before loop iterates (no 1-frame lag).
- [x] WHILE loop bounded by `Math.min(total, ...)` — stutter-frame safe.
- [x] Defensive null-guard `if (_bDef)` matches catch-block oracle pattern.

## When to Apply This Pattern

Add phase-transition-thought-burst to any file when:
- The file has a segmented loop with discrete boundaries (state machine OR hue segments OR speed segments)
- Boundaries currently fire chromatic/visual flash but no new pulse/spawn emission
- The boundary has a single common detection site (function OR inline detector) that covers all paths
- The user-vision principle "the maze as a CHARACTER — mood, heartbeat, emotional tonality" applies

The pattern works for ANY segmented loop where boundaries are detected at a single site — not just multi-state machines. Trailer (#22) proves this: 5 hue-segment boundaries on a continuous 20s loop with no state machine still benefit from the burst. The arm hook can be inline (trailer's `if (_phaseIdx !== _lastPhaseIdx)` block) rather than a function call (bio's `notePhaseTransition()` / dream's `onPhaseTransition()`).

### Destination-Amplitude Mapping (File-Agnostic Formula)

The amplitude formula `Math.round(3 + scalar * 4)` is file-agnostic. Each file supplies its own per-segment cognitive-energy scalar — this is the key generalization from the cross-file parity trilogy:

| File | Scalar | Source | Range | Per-transition counts |
|------|--------|--------|-------|------------------------|
| bio | `emitRate` | `PHASE_DEFS[phase].emitRate` | 0..1 | NREM 3 / AWAKE 4 / INSIGHT 4 / REM 6 |
| dream | `chaos` | `PHASE_DEFS[phase].chaos` | 0..1 | NREM 3 / AWAKE 3 / INSIGHT 4 / REM 6 |
| trailer | `_speeds[i]` | module-scope `const _speeds = [0.70, 1.30, 0.60, 1.40, 1.00]` | 0.6..1.4 | wrap 6 / seg1 8 / seg2 5 / seg3 9 / seg4 7 |

All three produce 3-9 pulses per transition, fired at the same `PHASE_BURST_INTERVAL = 0.07s`, completing in the same `PHASE_BURST_DUR = 0.40s`. The visual character is preserved cross-file because the timing knobs are identical — only the amplitude-per-boundary varies based on each file's local scalar.

### Trailer Adaptation (Run #22)

Trailer's boundary detection is inline (not a function call), so the arm block goes directly after `_lastPhaseIdx = _phaseIdx;` and `triggerChrPhaseTint(_phaseIdx);`:

```js
// In animate(), inside the existing phase-boundary detector:
if (_phaseIdx !== _lastPhaseIdx) {
  _phaseKick = 1.0;
  _lastPhaseIdx = _phaseIdx;
  triggerChrPhaseTint(_phaseIdx);
  // ── Phase-transition thought burst arm (trailer pattern) ──
  const _destSpeed = _speeds[_phaseIdx % _phaseCount];
  _phaseBurstState.active = true;
  _phaseBurstState.t = 0;
  _phaseBurstState.fired = 0;
  _phaseBurstState.total = Math.round(3 + _destSpeed * 4);
}
```

The fire block uses `emitPulse()` (trailer's existing pulse-emit function) instead of `spawnThoughtPulse()` (dream) — same shared-pipeline reuse principle, just different function name.

### Pulse-Count Delta Cross-File

| File | Pulses per loop | Loops per minute | Pulses/sec averaged |
|------|-----------------|------------------|---------------------|
| bio | 17 | ~0.9 (66s loop) | +0.26/sec (+6% density) |
| dream | 16-17 | ~0.7 (82s loop) | +0.20/sec (+5-7% density) |
| trailer | 35 | 3.0 (20s loop) | +1.75/sec (+5.8% density) |

Trailer has more pulses per loop but shorter loops (20s vs 66-82s), so per-second density is similar across all three. The *coordinated-thought-storm* character (70ms interval vs random emit's 33ms average) is what unifies the visual feel cross-file.

## Don't Confuse With

- **Chromatic aberration on phase transition** (existing) — purely a retinal flash via the #phase-flash overlay. Distinct from cognitive content.
- **Heart wave on beat peak** — brain-wide energy radiation, not a thought propagation. Same spiky envelope family, different visual channel.
- **Heartbeat-driven emission burst** (bio #18) — emits ONE pulse per heartbeat peak. Different trigger (heartbeat vs phase transition), different rhythm (steady cadence vs bursty event).
- **Insight wave on INSIGHT entry** — radial wave from origin, distinct visual element. Composes with phase-burst (both fire on INSIGHT transition).