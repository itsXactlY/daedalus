# Cross-File Parity Matrix

Current state of every cross-file family-rule audit. Updated as of run #31 (2026-06-23) — cognitive thought-sparks row is now bio ✓ #29 + dream ✓ #30 + trailer ✓ #31 (full 3/3 parity); trailer's heartbeat channel count moves from 7 to 8.

## Family Rules (5)

1. **All overlay DOM refs cached at module scope + resolved in init()** — no `getElementById` / `querySelector` in animate() bodies.
2. **All per-frame `THREE.Color` / `THREE.Vector3` scratch values hoisted to module scope and mutated in place**.
3. **Resilient animate catch with consecutive-error tracking** (threshold 30 ≈ 0.5s @ 60fps).
4. **No CSS `transition:` on per-frame-driven properties** (JS is authoritative at 60fps).
5. **Per-frame change-detection gates on hot-path DOM writes** — width %, color HSL, opacity, box-shadow, filter.

## Per-File Compliance

| File    | Rule 1 (DOM cache) | Rule 2 (scratch hoist) | Rule 3 (try/catch) | Rule 4 (no CSS transition) | Rule 5 (change-detect gates) |
|---------|:-:|:-:|:-:|:-:|:-:|
| bio     | ✓ #11, #14 | ✓ | ✓ | ✓ | ✓ `_vignetteLast`, `_phaseFillLastW`, `_heartbeatLast`, `_hPhaseLast` #23 |
| dream   | ✓ #3, #4, #7 | ✓ | ✓ | ✓ #12 | ✓ `_vignetteLast` #N+26, `_phaseFillLastW` #16, `_heartbeatLast` #15 |
| trailer | ✓ #1 | ✓ | ✓ | ✓ #13 | ✓ `_vignetteLast`, `_phaseFillLastW`, `_phaseFillLastH`, `_heartbeatLast`, `_chrLastOpR3`, `_chrLastPx` |

**Notes:**
- bio: 4/4 parity on the gate types it shares with the other files. `_phaseFillLastH` is n/a (bio's phase-fill is gradient not HSL hue loop), `_chrLastOpR3`/`_chrLastPx` are n/a (bio has no per-frame chromatic aberration overlay — its `#phase-flash` is a 260ms one-shot, not a sustained per-frame channel). The new `_hPhaseLast` is bio-only — dream/trailer don't have a phase pill element, so it doesn't enter the shared matrix.
- dream: 3/3 on the gate types it shares with bio (vignette, phaseFill W, heartbeat). Same n/a as bio on `_phaseFillLastH` / `_chrLast*`.
- trailer: 6/6 full coverage, including the per-frame chromatic aberration gates that the other two files don't have.

## Heartbeat Channel Inventory (Bio)

Channels that follow the heartbeat in bio (post run #23):

| Channel | Location | Beat formula |
|---------|----------|--------------|
| Consciousness core scale + brightness | animate L1992-2005 | `Math.pow(Math.max(0, Math.sin(beatPhase)), 6)` |
| Consciousness halo scale + opacity | animate L1999-2005 | Same |
| Camera FOV breath | animate L1427+ | Same |
| Camera position tremor | animate L2033-2038 | Same |
| EKG trace + marker dot | updateHeartbeat L1710-1744 | Same |
| Heart waves | animate L1896-1901 | Same (threshold 0.7) |
| Brand glyph scale + text-shadow blur | updateHeartbeat L1645+ | Same |
| Screen-edge heartbeat glow | heartbeat div box-shadow | Same |
| Per-node beat-driven size + lightness | per-node loop L2056-2067 | `Math.pow(Math.max(0, Math.sin(beatPhase + phaseOff)), 4)` (different exponent) |
| Per-region local beat swell | hull scale L2092-2095 | `Math.pow(Math.max(0, Math.sin(beatPhase + tg._heartbeatPhaseOff)), 6)` (per-region offset) |
| Pulse emission (#18) | animate emit block | Same as heart-wave, threshold 0.6 |
| Brand glyph rotation duration (#21) | updateHeartbeat `--brand-spin-dur` | Driven by `currentPulseSpeed`, not `beat` |
| **Phase pill box-shadow glow (#23)** | updateHeartbeat `_hPhaseEl.style.boxShadow` | `Math.pow(Math.max(0, Math.sin(beatPhase)), 6)` — peak 7px blur / 0.45 alpha, gated by `_hPhaseLast` |

**12 heartbeat-driven channels** as of run #23. When adding a NEW channel, pick a threshold in the 0.5-0.7 range to ensure it fires only on beat peaks, and a debounce that matches the existing rate of the channel it's coupled with (typically 0.3-0.5s).

## Cross-File Per-File Feature Comparison

| Feature                                  | bio  | dream | trailer |
|------------------------------------------|:----:|:-----:|:-------:|
| Heartbeat-driven visual channels         | 15   | 14    | 8       |
| Heart wave / radial bloom on beat        | ✓    | ✓     | ✓       |
| Per-pulse firing ring at source          | ✓    | ✓ (#10) | ✓     |
| Inter-region synapse threads             | ✓    | ✓     | ✓       |
| Arrival flash at pulse destination       | ✓    | ✓     | ✓       |
| Neural cascade (chain pulses)            | ✓    | ✗     | ✗       |
| Recognition ping (close-up camera event) | ✗    | ✗     | ✓       |
| Heartbeat-driven pulse emission          | ✓ #18 | ✓ #27 | ✓ #25 |
| Cognitive thought-sparks                 | ✓ #29 | ✓ #30 | ✓ #31 |
| Phase-transition thought burst           | ✓ #20 | ✓ #21 | ✓ #22 |
| Phase pill heartbeat pulse               | ✓ #23 | n/a   | n/a     |
| Per-node beat-driven size + lightness    | ✓ #N+18 | ✓ #24 | n/a |
| Consciousness core / nucleus             | ✓    | ✗     | ✓       |
| EKG HUD with phase-colored trace         | ✓    | ✓     | ✗       |
| Phase progress bar                       | ✓    | ✓     | ✓       |
| Chromatic aberration on phase transition | ✓    | ✓     | ✓       |
| Distant fog-of-war structures            | ✓    | ✓     | ✓       |
| Cosmic motes (midground haze)            | ✓    | ✓     | ✓       |
| Starfield background                     | ✓    | ✓     | ✓       |
| Camera spline / flythrough               | ✗ (orbit) | ✗ (orbit) | ✓ |
| Auto-rotation when idle                  | ✓    | ✗     | ✗       |
| WebSocket live phase push                | ✗    | ✓     | ✗       |
| Try/catch with consecutive-error counter | ✓    | ✓     | ✓       |

## Multi-System File Audit (Dream #27 lesson)

When a file has multiple parallel cognitive-emission subsystems (not just one `emitPulse()` like bio + trailer), audit each subsystem individually for heartbeat-coupling before claiming cross-file parity. Dream has THREE:

1. **`heartWaves`** (radial shells via `heartWaves.push(...)` inside the heartbeat block at L2964-2978) — heartbeat-driven pre-existing.
2. **`thoughtPulses`** (inter-region nearest-neighbor via `spawnThoughtPulse()` in the same heartbeat block) — heartbeat-driven pre-existing.
3. **`activationPulses`** (main pulse mesh, traveling bright dots via stochastic `Math.random() < pulseRate` + four phase-distinct branch arms at L3443-3541) — heartbeat-driven only since run #27.

Recipe to find candidate subsystems:

```bash
grep -nE '\.push\(\{|emitPulse|spawnPulse|push.*\{.*src|activationPulses|thoughtPulses|heartWaves' public/maze-crew-<file>.html
# Then for each subsystem: is it gated by `pulse > X && (t - _lastX) > Y` or purely stochastic (`Math.random()`)?
```

If any subsystem is purely stochastic, it's a candidate for the heartbeat-emit pattern (with its own debounce var). Run this audit before claiming cross-file parity for any heartbeat-driven emission row.

## Audit Commands

```bash
# Check for getElementById in animate() bodies (should be 0)
grep -nE 'getElementById|querySelector' public/maze-crew-*.html

# Check for new Color/Vector3 in animate() bodies (should be 0)
grep -nE 'new THREE\.Color\(|new THREE\.Vector3\(' public/maze-crew-*.html

# Check for CSS transition on per-frame-driven properties (should be 0)
grep -nE 'transition.*opacity|transition.*width|transition.*box-shadow|transition.*filter' public/maze-crew-*.html

# Check change-detection gate coverage
grep -nE '_vignetteLast|_phaseFillLast|_heartbeatLast|_hPhaseLast|_chrLast' public/maze-crew-*.html

# Find every pulse-emission subsystem (multi-system audit)
grep -nE '\.push\(\{|emitPulse|spawnPulse|push.*\{.*src|activationPulses|thoughtPulses|heartWaves' public/maze-crew-*.html
```

When any of these return non-zero, that's a candidate for the next run.