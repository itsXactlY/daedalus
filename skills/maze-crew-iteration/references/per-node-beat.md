# Per-Node Heartbeat-Driven Size + Lightness

The pattern that makes a node cloud read as **800 living cells** instead of a uniform tissue. Each node swells + brightens on the cardiac peak with a per-node phase offset, so the wave visibly travels through the cloud. Direct match for "the maze as a CHARACTER — mood, heartbeat, emotional tonality" at the cellular scale.

**Status across files:** bio ✓ #N+18, dream ✓ #24, trailer ⬜ n/a (trailer has no per-node cloud — only camera spline + chroma layers).

## When To Use This Pattern

When you have:
- An `InstancedMesh` of N nodes (`memoryNodes`, `tissueGroups[].nodes`, etc.) where each node has a stable `id` and at least one 0..1 field (`energy`, `activation`, etc.) you can use for jitter
- A heartbeat envelope already computed in the animate function (`pulse`, `beat`, `hbPhase`, etc.) — typically from the `Math.pow(max(0, sin(hbPhase)), 12)` family
- The per-node size / lightness currently driven by other slow rhythms (`breathFactor`, `energyBoost`, `actGlow`) but **NOT** by the heartbeat envelope itself

Without this pattern, the node cloud "breathes" via slow phase rhythms but does NOT visibly throb on each cardiac peak — the cellular scale of the heartbeat is invisible.

## The Formula (mirror exactly across files)

```js
const phaseOff = n.id * 0.37 + n.energy * 1.5;
const beatContrib = Math.pow(Math.max(0, Math.sin(hbPhase + phaseOff)), 4);
const sz = n.baseSize * (1 + existingSlowTerms + actGlow + beatContrib * <sizeMult>) * <breathFactor>;
const lightness = <baseLightness> + <existingTerms> + beatContrib * <lightMult>;
```

Where:
- `n.id` is a stable per-node integer (0..N-1), set at node build time
- `n.energy` is a 0..1 field set at node build time (use `Math.random()` if no natural source)
- `hbPhase` is the per-frame heartbeat phase angle (radians), already hoisted to function scope
- The `^4` exponent produces a broad, sustained pulse; the `^12` envelope is reserved for sharp flash channels (shell, halo, screen-edge)
- `0.37` and `1.5` constants are tuned for organic ripple density — see math section below

## Phase Offset Math

The phase offset creates wavefront density across the cloud:

```
wavefrontCount = N * 0.37 / (2 * PI)  →  wavefrontWidth = N / wavefrontCount
```

| N (nodes) | Wavefronts at any time | Each wavefront width | Visual character |
|---|---|---|---|
| 200 (one tissue group in bio) | ~12 | ~17 nodes | clear distinct ripples |
| 800 (dream cloud) | ~47 | ~17 nodes | fine-grained organic ripple |
| 1500 (large maze cloud) | ~88 | ~17 nodes | dense high-frequency turbulence |

The constant `0.37` is tuned so each wavefront spans ~17 nodes — wide enough to read as a band, narrow enough that the wave's propagation is visible (not a uniform throb).

`n.energy * 1.5` adds a 0..1.5 radian jitter (~0..0.24 cycles) so nodes with similar IDs don't all peak on the same exact wavefront — gives the ripple a slightly noisy edge instead of razor-sharp bands.

## Magnitude Tuning (the "competing signal" rule)

**The default magnitude from bio is `0.45` for size + `0.30` for lightness.** Don't copy these verbatim to a new file — tune against the **strongest competing signal already in the per-node formula**.

**Rule:** the new heartbeat magnitude should be **3-5x smaller than the dominant existing per-node signal**, so the heartbeat reads as a layered second rhythm rather than competing for primary attention.

| Destination file | Dominant existing signal | bio magnitude | tune to |
|---|---|---|---|
| bio (single tissue group) | `n.fired * 0.6` (peaks 0.6) | 0.45/0.30 | 0.45/0.30 ✓ — fired peaks at 0.6, so 0.45 is comparable, not competing |
| dream (memory cloud) | `actGlow * 1.0` (peaks 1.0) | 0.45/0.30 | **0.20/0.13** — actGlow is 2x bio's fired, so heartbeat halved to avoid washout |
| (hypothetical) future file with strong dominant | `actGlow * 2.0` | 0.45/0.30 | 0.10/0.07 — even smaller, just a subtle heartbeat layer |

Document the relative magnitude ratio in the rationale comment:

```js
// Magnitude 0.20/0.13 vs bio's 0.45/0.30 — tuned to coexist with dream's
// dominant actGlow (peaks 1.0 vs bio's fired peaks 0.6). 0.45 here would
// double the activation signal at peak and wash out the per-node firing
// rhythm.
```

## Exponent Choice: ^4 vs ^6 vs ^12

| Exponent | Envelope character | Use for |
|---|---|---|
| ^12 | Sharp spike (~5% of cycle is meaningful) | Shell halo, screen-edge bloom, EKG trace — flash channels that should "punch" |
| ^6 | Medium spike (~25% of cycle is meaningful) | Consciousness core, brand text-shadow, brain-shell heartPunch — felt swell channels |
| **^4** | Broad pulse (~50% of cycle is meaningful) | **Per-node beat — sustained swell, reads as "breathing" not "flashing"** |

The per-node beat uses ^4 (not the file's default ^12) because per-node phase offsets need a broad envelope to read as traveling waves. With ^12, the per-node peaks would be so brief that the eye couldn't see the wave traveling; with ^4, each node's pulse has a clear ~50% of the beat cycle where it's meaningfully larger — and the per-node phase offset has time to translate that into visible wavefront propagation.

## Per-Phase Heart Rate → Wave Appearance

The wave traverses at the per-phase heart rate (`cur.breathRate` in dream, `currentPulseSpeed` in bio, `HB_RATE` in trailer). With 800 nodes at ~47 wavefronts:

| Phase | Heart rate | Period | Wavefronts/sec | Visual character |
|---|---|---|---|---|
| AWAKE | 1.0 Hz | 1.11s | ~42 | mid-tempo ripple — calm steady |
| NREM | 0.25 Hz | 4.0s | ~12 | slow deep breathing — meditative |
| REM | 1.6 Hz | 0.625s | ~75 | rapid turbulent ripple — matches chaos=0.7 |
| INSIGHT | 1.0 Hz | 1.11s | ~42 | mid-tempo — the "aha" cohering |

The phase-rate-driven wave speed gives each phase a distinct visual rhythm for the same heartbeat code — REM shows fast turbulent ripples, NREM shows slow breathing waves, all from the same formula.

## Implementation Recipe

1. **Confirm the heartbeat envelope is hoisted to function scope.** You need `hbPhase` (or equivalent) available in the per-node loop. If it's inside a `if (ekgEl) { ... }` block, make sure the per-node loop is OUTSIDE that block but still in the same function (the existing pattern in dream.html has `pulse` + `hbPhase` declared at the top of the animate function body and updated conditionally inside the heartbeat block).

2. **Confirm `n.id` and `n.energy` exist.** `id` should be set to the loop index at node build time. `energy` should be a 0..1 field — use `Math.random()` if no natural source exists.

3. **Identify the dominant existing per-node signal.** Find the largest existing term in the size formula (typically `actGlow`, `n.fired`, or `energyBoost`). The new heartbeat magnitude should be 3-5x smaller.

4. **Add the 2 new const lines + 1 size term + 1 lightness term.** Mirror bio's exact formula; only the magnitude multipliers change.

5. **No new module-scope state, no new DOM refs, no new allocations.** The pattern is pure arithmetic in the existing per-node loop.

## Verification Recipe

```python
# 1. Extract module script and node --check
m = re.search(r'<script type="module">(.*?)</script>', html, re.DOTALL)
with open('/tmp/extracted.js', 'w') as out: out.write(m.group(1))
# Then: node --check /tmp/extracted.js (expect SYNTAX_OK exit 0)

# 2. Symbol audit — expect exactly:
#    phaseOff: 2 (1 decl + 1 use in Math.sin)
#    beatContrib: 3 (1 decl + 1 use in size + 1 use in lightness)
#    hbPhase (or beatPhase): +1 from before (the new Math.sin reference)

# 3. Antipattern grep in the NEW runtime block only:
#    new Float32Array: 0, new THREE.Color: 0, getElementById: 0
#    (the new block is pure arithmetic, zero allocations)

# 4. TDZ check — the new block's variables (phaseOff, beatContrib) must
#    be declared BEFORE any use within the same block. Use of hbPhase
#    and t must point to variables declared EARLIER in the function.
#    Note: nested `for (let i = ...)` declarations in OTHER blocks do
#    NOT shadow the outer `i` — block-scoping means they're separate
#    variables. (See pitfall in main SKILL.md.)
```

## Cross-File Pitfall: The "Copy Verbatim" Trap

The visual-pattern-invariants.md "Firing Rings" / "Pulse Arc Threads" / etc. sections say **"copy the constants verbatim"** when backporting. This rule holds for SHAPE (geometry, lifetime, color space) but NOT for MAGNITUDE when the destination file has a stronger competing signal.

**Always tune magnitude against the dominant existing channel in the destination file.** A 0.45 heartbeat boost in a file whose dominant per-node signal is 0.6 (bio) is fine; the same 0.45 in a file whose dominant signal is 1.0 (dream) would wash out the activation signal.

The "copy verbatim" rule applies to:
- Geometry (Shape: `RingGeometry(0.4, 0.5, 32)`)
- Lifetime (Duration: `RING_LIFE = 0.8`)
- Color space (Saturation: `0.85`)
- Material mode (Blending: `THREE.AdditiveBlending`)

The "tune to destination" rule applies to:
- Magnitude multipliers (how loud this channel is relative to others)
- Phase offset step (depends on N, the node count)
- Per-phase amplitude mappings (use the destination file's local `PHASE_DEFS` scalar)

## Why This Pattern Beats "Uniform Throb"

If you skip the per-node phase offset (`phaseOff` constant at 0) and apply the heartbeat uniformly to all nodes:

```js
// BAD: all nodes pulse in lockstep — uniform throb, no wave
const beatContrib = Math.pow(Math.max(0, Math.sin(hbPhase)), 4);
```

The brain reads as a single solid object that grows +20% on each beat. Looks mechanical, like a balloon inflating. No wave, no cellular character.

With the phase offset, each node is at a different phase, so the wave is visible — the brain reads as 800 living cells firing in a coordinated ripple. This is the difference between "alive as a body" and "alive as a brain."

## See Also

- `references/heartbeat-driven-emission.md` — single-pulse heartbeat sync (complement: this file is per-node, that file is per-emission)
- `references/visual-pattern-invariants.md` — per-node breath + wobble family rules (this pattern is the heartbeat-driven cousin)
- `references/cross-file-parity-matrix.md` — current state of this row across files