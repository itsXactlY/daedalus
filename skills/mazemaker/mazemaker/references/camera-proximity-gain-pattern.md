# Camera-Proximity Gain Pattern

A reusable technique for camera-driven visual amplification: derive a single `[0..1]` gain factor from the camera's distance to a meaningful point in the scene, then apply it as a multiplier to multiple visual layers that should intensify as the camera approaches. Originally developed for `maze-crew-trailer.html` run #65 (2026-06-22).

## The Pattern (5 steps)

### 1. Pick the meaningful point + max radius

The "meaningful point" is the scene's emotional center — for the maze, it's the nucleus (world origin). The max radius is the distance beyond which the gain is zero.

```js
const PROXIMITY_MAX_R = 14;  // radius within which amplification peaks
```

Picking the radius: measure your camera path's distance-to-center at each keyframe. Set `PROXIMITY_MAX_R` to the threshold where you want the gain to start mattering. For the trailer, frames 3-6 (~5s-9s of the 20s loop) had `r=6-10`, so `PROXIMITY_MAX_R=14` means `prox>0` only for that ~4-second window — calm on distant keyframes, dramatic on interior keyframes.

### 2. Module-scope the raw distance (for debug/observability)

```js
let _camDist = 0;  // current distance to scene center
```

Module-scope means DevTools can inspect it during a live session, and it follows the same pattern as the trailer's `_phaseKick` (also per-frame derived state at module scope).

### 3. Compute the gain as a local const (recomputed every frame)

Right after `camera.position.set(...)`:

```js
_camDist = Math.hypot(camP[0], camP[1], camP[2]);
const prox = 1 - Math.min(_camDist / PROXIMITY_MAX_R, 1);
```

**Why `const` and not module-scope?** The value is derived from other state (`_camDist`) — it doesn't need its own storage. Local const makes the temporal scope obvious (one frame). Module-scope would imply cross-frame persistence, which is misleading.

**Why `Math.hypot` not `length()`?** Use the raw spline position `camP[0..2]`, NOT `camera.position` after any post-processing (e.g. camera tremor adds noise that would corrupt the gain curve). The trailer learned this the hard way: tremor amplitude is sub-pixel but would still perturb the distance metric.

### 4. Apply the gain to multiple visual layers

The trailer touched 4 heartbeat-driven layers:

```js
// Camera tremor: 1.0× → 1.8× at deepest point
const tremorGain = 1 + prox * 0.8;
camera.position.x += Math.sin(elapsed * 23.7 + 1.2) * beat * 0.10 * tremorGain;
camera.position.y += Math.sin(elapsed * 31.3 + 4.7) * beat * 0.10 * tremorGain;
camera.position.z += Math.sin(elapsed * 17.1 + 7.9) * beat * 0.10 * tremorGain;

// Fog density pulse: 1.0× → 2.25× at deepest point
scene.fog.density = _baseFog + beat * (0.0024 + prox * 0.0030);

// Vignette alpha pulse: 1.0× → 2.0× at deepest point
const _vA = 0.42 + beat * (0.18 + prox * 0.18);

// FOV breath: 1.0× → 2.2× at deepest point
camera.fov = 58 + beat * (1.5 + prox * 1.8) + _phaseKick * 4.0;
```

**Magnitudes tuned subtle but felt:** at the deepest moment (r=6.4, prox=0.54), the layers amplify by 1.43-1.67×. Not enough to overwhelm other layers, enough to create a felt intensification. The 20s loop develops an emergent dramatic arc: calm establishing shot → building tension → dramatic peak (frames 3-6) → gradual return to calm.

### 5. Visual diff: zero on boot, dramatic in the deep window

Because the camera starts far from the meaningful point (frame 0 at r=70 for the trailer), `prox=0` on the first frame — all 4 layers start at their baseline amplitudes. The amplification only emerges as the camera approaches, then naturally recedes. No choreographed trigger needed; the camera path is the choreography.

## When to Use

- **Fixed camera path with intimate moments** (cinematic trailers, flythroughs, scripted camera moves)
- **Multiple visual layers that should feel "felt-ly amplified" together** rather than independently animated
- **You want an emergent dramatic arc** without adding event triggers or timeline markers

## When NOT to Use

- **Free-orbit cameras** (user-controlled): proximity would be unstable, jump around as the user moves
- **Single-layer effects**: just animate the one layer directly, no need for a factor
- **Non-heartbeat-driven effects**: the technique pairs well with rhythmic base animations (heartbeat, breathing, oscillation) — without a base, there's nothing to amplify

## Pattern Variations

**Distance-squared gain** (sharper falloff):
```js
const prox = 1 - Math.min((_camDist / PROXIMITY_MAX_R) ** 2, 1);
```
Use when you want a sharper "all-or-nothing" transition. The trailer used linear because the camera path enters the proximity zone gradually.

**Asymmetric gain** (amplify only above baseline):
```js
const tremorGain = 1 + prox * 0.8;  // additive gain
// vs multiplicative
const tremorGain = 1 + prox * 0.5 * (someBaseline - 1);
```
Use when the layer already has a meaningful baseline and you want to scale the deviation from baseline, not the absolute value.

**Multi-zone proximity** (multiple meaningful points):
```js
const proxA = 1 - Math.min(distToA / MAX_R, 1);
const proxB = 1 - Math.min(distToB / MAX_R, 1);
const combinedProx = Math.max(proxA, proxB);  // nearest zone wins
```
Use when the scene has multiple focal points and the camera passes near each in turn. The trailer's single-center model doesn't need this, but a tour through multiple regions would.

## Pitfalls

- **Don't use `camera.position` post-tremor**: any per-frame position noise corrupts the gain. Use the spline position or another noise-free source.
- **Don't use `length()` if the camera might be at non-origin lookAt targets**: a camera looking at (0, 0, 0) but positioned at (5, 0, 0) has length 5 from origin but the *visual distance* to the subject depends on the lookAt point. Choose the meaningful-point distance carefully.
- **Don't forget the boot frame**: `prox=0` on frame 0 is the desired behavior (no amplification at distance), but verify in DevTools that the first frame doesn't accidentally read `_camDist=NaN` from a yet-uninitialized state.
- **Don't apply to all layers**: only layers that should intensify with proximity. Static layers (region hulls, starfield drift) should remain constant.

## Worked Example (trailer run #65)

Frame distances from origin in the trailer's 12-keyframe CatmullRom spline:
| Frame | Time | Position | Distance | prox |
|-------|------|----------|----------|------|
| 0 | 0.0s | (0, 28, 65) | 70.7 | 0.00 |
| 1 | 1.5s | (12, 18, 42) | 47.3 | 0.00 |
| 2 | 3.3s | (18, 10, 20) | 28.7 | 0.00 |
| 3 | 5.0s | (4, 4, 8) | 9.8 | 0.30 |
| 4 | 6.8s | (-4, -3, -4) | 6.4 | 0.54 |
| 5 | 8.5s | (0, -8, 2) | 8.2 | 0.41 |
| 6 | 10.3s | (8, -12, -8) | 16.5 | 0.00 |
| 7-11 | 12-19s | various | 25-64 | 0.00 |

So the gain was non-zero only for the 5.0-9.0s window (frames 3-5), peaking at frame 4. Outside that window, all 4 layers ran at baseline. Inside it, they amplified by 1.43-1.67× at peak proximity. The 20s loop developed an emergent dramatic arc without any timeline triggers.

## Code Organization Tip

**Module-scope the raw value, local-const the derived value.** This is a useful pattern for any per-frame derived state:

```js
// Module scope: the raw measurement, observable in DevTools
let _camDist = 0;

// Inside animate(), right after camera.position.set:
_camDist = Math.hypot(camP[0], camP[1], camP[2]);
const prox = 1 - Math.min(_camDist / PROXIMITY_MAX_R, 1);  // derived value, local-scope
```

Why both? `_camDist` at module scope = debuggability (can `console.log(_camDist)` from anywhere, can write to a debug overlay). `prox` as local const = clarity of temporal scope (recomputed every frame, no cross-frame persistence implied). The trailer's `_phaseKick` and `_lastPhaseIdx` follow the same dual pattern.
