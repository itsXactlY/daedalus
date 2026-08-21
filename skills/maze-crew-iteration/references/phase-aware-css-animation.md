---
name: phase-aware-css-animation
description: Reference for driving existing CSS @keyframes animations from per-frame JS state (phase, pulseSpeed, heartbeat, proximity) via CSS custom property interpolation. Worked example from bio #21 (phase-aware brand rotation). Covers the browser interpolation behavior, the wrong-way that DOES restart, and a verification recipe.
---

# Phase-Aware CSS Animation Timing via CSS Variable Interpolation

## The problem

You have a CSS animation that should respond to a per-frame state variable (currentPulseSpeed, beat, phase, camera proximity, etc.). Examples in the maze crew family:

- Brand glyph rotation that speeds up during REM, slows during NREM (bio #21)
- A loader spinner that pulses with the heartbeat
- A pulse-line indicator whose thickness tracks activity level
- A directional indicator that rotates faster when closer to a target

The naive options all have problems:

| Approach | Problem |
|---|---|
| Hardcode `animation: x 16s …` | Not state-aware |
| Per-frame `element.style.transform = 'rotate(' + angle + 'deg)'` | Layout flush per frame, competes with sibling transforms |
| Rewrite `element.style.animation = 'x ' + newDur + 's …'` | **Restarts the animation** to t=0 every frame |
| `animation-delay: -${offset}s` | Couples rate to time-since-page-load, not current state |

The right answer is binding `animation-duration` to a CSS variable and writing the variable from JS.

## The technique

```css
.element {
  animation: someKeyframes var(--x-dur, 16s) linear infinite;
}
@keyframes someKeyframes { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
```

```js
// In your per-frame update (e.g., updateHeartbeat()):
document.documentElement.style.setProperty(
  '--x-dur',
  (baseDuration / Math.max(currentPulseSpeed, 0.1)).toFixed(2) + 's'
);
```

**Two surgical changes** — CSS rule + 1 JS setProperty call. Zero new module-scope state, zero per-frame allocations.

## Why it works (the non-obvious browser behavior)

When `animation-duration` is bound to a CSS variable via `var()` and the variable's value changes at runtime, modern browsers **interpolate the playback rate smoothly without restarting the animation**:

- Chrome 84+ (July 2020)
- Firefox 75+ (April 2020)
- Safari 14+ (September 2020)

The DOM `Animation` API exposes this directly: `animation.playbackRate` updates to match the new duration, and `currentTime` is preserved. So an animation at 200° rotating at 16s/period that switches to 5.7s/period continues from 200° at the new rate — no snap, no flicker, no visible discontinuity.

The pitfall is doing it the WRONG way: rewriting the entire `animation` shorthand (`element.style.animation = '… ' + newDur + 's …'`) DOES restart because you're replacing the declaration, not editing a property. The `var()` binding is what makes the change *edit* a property rather than *replace* a declaration.

## Verification recipe

1. **Bind duration to var:** change `animation: x 16s linear infinite` to `animation: x var(--x-dur, 16s) linear infinite`.
2. **Add JS write:** `document.documentElement.style.setProperty('--x-dur', computedDur + 's')` in your per-frame update.
3. **Manual test:** open DevTools, find the element, and run `getComputedStyle(el).animationDuration` — verify it shows the current var's value (e.g., `5.71s`), not `16s`.
4. **Behavioral test:** change the var in DevTools (`document.documentElement.style.setProperty('--x-dur', '2s')`) and watch the animation smoothly speed up — the rotation angle should NOT snap to 0. If it does snap, you're in the WRONG-way pattern.
5. **Floor check:** verify `Math.max(speed, 0.1)` guards division-by-zero. Set the var to `0s` (without the floor) and confirm the animation freezes (which is bad UX but a valid edge case). With the floor, the minimum duration is `16 / 0.1 = 160s`, which is slow but not frozen.

## Worked example: bio #21 phase-aware brand rotation

**The gap.** Bio's `⌬` brand glyph had `animation: brandSpin 16s linear infinite` — a static rotation rate regardless of sleep stage. Every other visible rhythm (starfield, cosmic motes, distant structures, EKG rate, brain center heartPunch) already followed the lerped `currentPulseSpeed`. The brand glyph was the last static holdout.

**The fix.**
1. CSS line 45: `animation:brandSpin 16s linear infinite` → `animation:brandSpin var(--brand-spin-dur,16s) linear infinite`. Fallback `16s` preserves prior behavior on first-frame paint and for any browser that doesn't accept CSS variables in `animation-duration`.
2. JS write in `updateHeartbeat()` (right after the existing `--brand-glyph-scale` write): `document.documentElement.style.setProperty('--brand-spin-dur', (16 / Math.max(currentPulseSpeed, 0.1)).toFixed(2) + 's')`.

**Per-phase rotation periods** (driven by `PHASE_DEFS[p].pulseSpeed` × the lerped `currentPulseSpeed`):

| Phase    | pulseSpeed | Rotation period | Visual character |
|----------|-----------:|----------------:|------------------|
| AWAKE    | 1.0        | 16.00s          | baseline (unchanged) |
| NREM     | 0.3        | 53.33s          | slow meditative spin |
| REM      | 2.8        |  5.71s          | chaotic fast spin |
| INSIGHT  | 0.7        | 22.86s          | focused moderate spin |

**Visual delta.** On a 7-second clip, during REM the `⌬` glyph whirls ~1.2 full rotations (vs the static 0.44 it would have made before), during NREM it barely creeps forward (0.13 rotations vs 0.44). The brand label — always visible in the top-left corner — becomes a phase indicator you can read even when the central organism is off-screen.

**Verification result.**
- `node --check` on extracted module → SYNTAX_OK
- Code brace/paren/bracket balance: 0/0/0
- HTML body tag balance: div 12/12, canvas 2/2, span 10/10, button 3/3
- Symbol audit: `--brand-spin-dur` introduced exactly 1×; `currentPulseSpeed` count unchanged
- Antipattern grep: 0 new Float32Array, 0 getElementById, 0 querySelector, 0 setInstanceMatrix, 0 body.style.filter

**Size:** +22 lines (dominated by the 22-line rationale comment), +1,905 bytes.

## When to use this vs alternatives

**Use this technique when:**
- You have an existing CSS keyframe animation that should respond to per-frame state
- The element's transform should compose cleanly with sibling transforms (wrapper scale + inner rotation)
- You want GPU-composited animation (cheap on the hot path)
- The state variable changes smoothly (lerped), not in discrete steps

**Use JS-driven `transform: rotate(...)` per frame when:**
- You need angle-discrete control (snapping to specific angles, not continuous rotation)
- The element has no CSS animation today (would be a regression to ADD one just for this)
- You're already writing the transform for OTHER reasons (sibling pipeline exists)

**Use `@keyframes` with no var binding when:**
- The animation rate is truly constant (a 1s pulse indicator, an idle loader)
- You'd never want it state-aware

## Pitfalls

1. **Don't rewrite the whole `animation` shorthand.** `element.style.animation = 'brandSpin ' + dur + 's linear infinite'` restarts the animation. Use the var binding or change `animation-duration` directly via a separate property write (`element.style.animationDuration = dur + 's'`).

2. **Always provide a fallback in the var() call.** `var(--x-dur, 16s)` — without the fallback, browsers without CSS-variable support in `animation-duration` will fail to parse and the animation disappears entirely. The fallback ALSO helps during first-frame paint (before the JS write lands).

3. **Wrap divisors with `Math.max(value, 0.1)`.** A `0s` or `0.001s` duration is invalid CSS and freezes the element visually. The 0.1 floor is essentially free.

4. **Don't transition `animation-duration`.** It's transitionable in some browsers but the spec is fuzzy. JS writes the canonical value at 60fps; a CSS transition would lag by 50-150ms and smear the rhythm — same anti-pattern already documented for box-shadow/opacity/width in the family rules.

5. **Don't change the keyframes themselves.** The var binding is for DURATION only. Changing `@keyframes brandSpin { from { rotate(0) } to { rotate(360) } }` to use a variable angle defeats the GPU compositing benefit.

## When NOT to apply this audit

- Files with no CSS keyframe animations (pure JS transforms everywhere)
- Files where every element already reads a state variable (audit returns nothing)
- Cases where the rate change would be distracting rather than felt (e.g., a "PONG: 0" counter where variable speed would feel buggy)

## Cross-file applicability

Bio #21 is the first application. The pattern is reusable in:
- Dream's awareness eye (currently drives translateX via `--eye-x` var — could ADD a rotation animation with phase-aware speed for the eye's pupil if desired)
- Trailer's brand label (if a brand glyph is ever added)
- Any future maze-crew feature that needs state-aware CSS animation timing