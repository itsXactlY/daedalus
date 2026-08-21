# Heartbeat-Driven Emission Burst (Bio #18)

## The Pattern

The heartbeat is a `Math.pow(Math.max(0, Math.sin(beatPhase)), 6)` envelope that peaks briefly per cycle. The `beat` variable is computed locally in `updateHeartbeat()` but is also recomputed locally in 3-4 other call sites (consciousness core, halo, camera tremor, heart wave spawn) using the same formula. **Do not hoist `beat` to module scope** — recompute at each consumer site for consistency with the existing pattern.

## Implementation

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

## Threshold Tuning

- Heart-wave spawn threshold: 0.7 (line 1896 in bio)
- Heartbeat-emit threshold: 0.6

The 0.1 offset means heartbeat-emit fires slightly earlier than the wave — thought visibly emerges just before the wave blooms out, and the wave visibly accompanies the propagating thought instead of leading it. Brain signal flow reads as: **beat peak → thought emerges → wave accompanies → cascade through tissue.**

## Debounce Pairing

- Heart-wave debounce: 0.4s (`_lastBeatSpawn`)
- Heartbeat-emit debounce: 0.35s (`_lastHeartbeatEmit`)

The 0.05s offset is small enough that both fire on the same beat but different enough that they don't quite collide on the same frame. At all four phases (AWAKE/NREM/REM/INSIGHT) both debounces allow exactly 1 fire per beat.

### Per-Phase Firing Analysis

| Phase  | Heart rate | Period | Heartbeat-emit (0.35s debounce) | Heart-wave (0.4s debounce) |
|--------|------------|--------|--------------------------------|-----------------------------|
| AWAKE  | 1.0 Hz     | 1.0s   | Every beat                     | Every beat                  |
| NREM   | 0.3 Hz     | 3.3s   | Every beat                     | Every beat                  |
| REM    | 1.6 Hz     | 0.625s | Every beat                     | Every beat                  |
| INSIGHT| 1.0 Hz     | 1.0s   | Every beat                     | Every beat                  |

The two channels stay coupled on the same beat, reinforcing the brain-as-character reading.

## Pulse-Count Delta

| Phase  | Before (emit-rate only) | After (+ heartbeat-emit) | Delta |
|--------|------------------------|--------------------------|-------|
| AWAKE  | 18/sec                 | 19/sec                   | +5.6% |
| NREM   | 4.8/sec                | 5.1/sec                  | +6.3% |
| REM    | 42/sec                 | 43.6/sec                 | +3.8% |
| INSIGHT| 12/sec                 | 13/sec                   | +8.3% |

Modest density bump across the board, but the *rhythm* change is the real win. Now there's a clear pulse-train pattern visible on each beat instead of a Poisson noise. On a 7-second screen-recordable clip, the viewer's eye sees pulses emanating in sync with the EKG trace and consciousness core throb.

## Visual Delta

**Before:** Stochastic pulse emission, decoupled from heartbeat. The brain has a strong cardiac rhythm with no cognitive rhythm — the heart beats, but the mind doesn't visibly think.

**After:** Stochastic + heartbeat-synced pulse emission, with each beat visibly triggering a thought. The brain now has a clear cognitive rhythm — synchronized to its cardiac rhythm — that wasn't visible before.

## Implementation Correctness Checklist

- [x] `emitPulse()` already does all the heavy lifting (random edge pick, source neuron fire, firing ring spawn, edge brightness, inter-thread bridges if cross-region). The heartbeat-emit just calls the same function — reuses the entire pulse pipeline.
- [x] Local `_hbBeat` recomputation matches the formula at L1622 (updateHeartbeat), L1993 (consciousness core), L2000 (halo), L2033 (camera tremor).
- [x] `_hbElapsed` uses `clock.getElapsedTime()` — same clock as the heart-wave debounce.
- [x] `_lastHeartbeatEmit` is module-scope, init = 0 (epoch start), debounce check works correctly on first beat peak after 0.35s elapsed.

## When to Apply This Pattern

Add heartbeat-driven emission to any file when:
- The file has a `beat` envelope (Math.pow(sin, 6) or similar) driving multiple visual channels
- Pulse/spawn emission is currently purely stochastic and decoupled from the heartbeat
- The file's "deferred-fix queue" footer is empty (means audit gaps are closed; ready for fresh feature work)
- The user-vision principle "the maze as a CHARACTER — mood, heartbeat, emotional tonality" applies

For dream (NREM/REM/Insight cycle): heartbeat-driven emission could be REM-only (active dreaming) — gate the emit block on `currentPhase === 'REM'`. For trailer (20s loop): probably N/A — trailer uses camera-path-driven emission, not heartbeat.

## Don't Confuse With

- **Stochastic emission only** — current behavior pre-#18. Random per-frame based on `currentEmitRate * dt * 60`.
- **Heart wave spawn** — visual icosahedron shell radiating outward, NOT a thought propagation. Same beat threshold family, different visual channel.
- **Camera-path-driven emission** — trailer's pattern. Not heartbeat-coupled.

## Companion Patterns

- **`references/heartbeat-emission-particle-pool.md`** — the round-robin GPU pool pattern (bio #29, dream #30) for emitting NEW additive particles on each beat peak. Pairs with this pattern: heart-wave + heartbeat-emit + sparks all fire on the same beat clock with slightly different debounces (0.4s / 0.35s / 0.35s). See that file's "Multi-Channel Beat Emission Cascade" section for the coexistence math and ordering principle (spark → activation pulse → thought pulse → heart-wave, in deterministic order).
- **`references/visual-pattern-invariants.md`** — magnitudes for firing rings, pulse arcs, etc.
