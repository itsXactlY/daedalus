---
title: WebGPU/Canvas2D Capability Checklist
description: Detailed checklist for verifying WebGPU/Canvas2D fallback implementations
---

# WebGPU/Canvas2D Capability Checklist

Use this checklist when verifying implementations that use the 3-tier ladder:
**WebGPU → WebGL2 → Canvas2D**

## Pre-Verification Setup

- [ ] Target URL accessible via HTTP server
- [ ] Hermes browser tools available
- [ ] Worktree has `assets/webgpu-boot.js` (or equivalent boot ladder)
- [ ] Worktree has `assets/glyph.js` (or equivalent deterministic renderer)
- [ ] Worktree has self-test suites (`glyph-det-test.js`, `gpu-graph-selftest.js`)

## Phase 1: API Availability

### `navigator.gpu`

```javascript
// In browser console
typeof navigator.gpu // "object" = true, "undefined" = false
```

- [ ] `navigator.gpu` → `true` (API namespace present)
- [ ] If `false`: Document browser/environment limitation

### `navigator.gpu.requestAdapter()`

```javascript
// In browser console
navigator.gpu.requestAdapter().then(a => console.log(a))
```

- [ ] Returns adapter object → WebGPU available
- [ ] Returns `null` → No GPU adapter (software rasterizer / no driver / headless)
- [ ] Hangs/times out → Missing timeout guard in boot code

**Expected in CI/headless:** `null` (no GPU driver)

### `navigator.gpu.getPreferredCanvasFormat()`

```javascript
// Only valid if adapter exists
navigator.gpu.getPreferredCanvasFormat()
```

- [ ] Returns format string (e.g., `"bgra8unorm"`)
- [ ] Throws if called without adapter

## Phase 2: Boot Ladder Verification

### `window.__webgpuBoot.backend()`

```javascript
window.__webgpuBoot.backend() // "webgpu" | "webgl2" | "canvas2d"
```

- [ ] Returns `"webgpu"` → Full WebGPU path active
- [ ] Returns `"webgl2"` → WebGPU failed, WebGL2 active
- [ ] Returns `"canvas2d"` → Both GPU tiers failed, 2D fallback active

### `window.__webgpuBoot.isPrimary()`

```javascript
window.__webgpuBoot.isPrimary() // true | false
```

- [ ] `true` → Primary backend is the active one
- [ ] `false` → Fallback backend active

### `window.__webgpuBoot.device()`

```javascript
window.__webgpuBoot.device() // GPUDevice | null
```

- [ ] Returns device if WebGPU active
- [ ] Returns `null` if fallback active

### Console Boot Logs (Critical Evidence)

Check `browser_console()` for:

- [ ] `[WebGPUBoot] WebGPU failed, trying WebGL2: requestAdapter returned null`
- [ ] `[WebGPUBoot] WebGL2 failed: WebGL2 context unavailable`
- [ ] `[WebGPUBoot] GPU tiers unavailable — 2D canvas fallback active`

**All three present** = clean demotion through all tiers.

## Phase 3: DOM & Canvas State

### `document.body.className`

```javascript
document.body.className
```

Expected patterns:
- `"canvas2d-fallback intro-done"` (2D fallback + intro complete)
- `"webgpu-active intro-done"` (WebGPU + intro complete)
- `"webgl2-active intro-done"` (WebGL2 + intro complete)

- [ ] Contains tier indicator (`canvas2d-fallback` | `webgpu-active` | `webgl2-active`)
- [ ] Contains `intro-done` (intro engine completed)

### `document.documentElement.className`

```javascript
document.documentElement.className
```

- [ ] Contains `intro-done`

### Canvas Inventory (Non-Zero Pixel Count)

For each canvas, sample 64×64 region via `getImageData`:

| Canvas | Expected (canvas2d fallback) | Expected (WebGPU) | Pass Criteria |
|--------|------------------------------|-------------------|---------------|
| `#stage2d` | **>0 (e.g., 648)** | 0 | Lit gradient in 2D mode |
| `#webgpuStage` | 0 | **>0** | GPU canvas active |
| `#intro-canvas` | 0 or >0 | >0 | Intro phase dependent |
| Glyph canvas (no id) | 0 (pre-glyph) or >0 | >0 | Glyph phase dependent |

**Critical:** `#stage2d` must have >0 pixels in canvas2d mode — proves paint-first boot works.

### JS Errors (`browser_console().js_errors`)

- [ ] `[]` — **Zero uncaught exceptions** (Gate D requirement)
- [ ] No `ReferenceError: createCanvas is not defined`
- [ ] No unhandled promise rejections

## Phase 4: Engine Loading Verification

### `MazeIntro`

```javascript
typeof window.MazeIntro // "object"
```

- [ ] Loaded as `"object"`
- [ ] Seed logged: `maze seed {hex} ({visit}::{date})`

### `MazeGlyph`

```javascript
typeof window.MazeGlyph // "object"
```

- [ ] Loaded as `"object"`
- [ ] Has `renderGlyph`, `computePathFingerprint`, `deriveGlyphParams`, `fnv1a32`, `mulberry32`

### `MazeGPUGraph`

```javascript
typeof window.MazeGPUGraph // "object"
```

- [ ] Loaded as `"object"`
- [ ] **Stays inert** when backend ≠ `"webgpu"` (correct behavior)
- [ ] Console: `[MazeGPUGraph] decision: backend="canvas2d" — GPU particle graph inert`

## Phase 5: Self-Test Execution

### Glyph Determinism Test (`glyph-det-test.js`)

```bash
cd assets && node glyph-det-test.js
```

- [ ] Test 1: Determinism — same path & time → same output: PASS
- [ ] Test 2: Differentiation — different paths → different output: PASS
- [ ] Test 3: Reduced-motion path deterministic: PASS
- [ ] Test 4: Empty path graceful rendering: PASS
- [ ] **All 6 assertions PASS, exit code 0**

### GPU Graph Selftest (`gpu-graph-selftest.js`)

```bash
cd assets && node gpu-graph-selftest.js
```

- [ ] Compute shader bindings verified (4 bindings)
- [ ] Render shader bindings verified (2 bindings)
- [ ] Buffer sizes aligned to 16 bytes
- [ ] Struct strides correct (Particle=24, Node=16, Uniform=64)
- [ ] Workgroup size = 64, Particle count = 8192, Dispatch = 128
- [ ] **All 29 assertions PASS, exit code 0**

## Phase 6: Gate Verification

### Gate D: 0 Inline Styles + Clean JS

- [ ] `grep -n 'style=' index.html` → Only dc-runtime template styles (framework mechanism)
- [ ] No hand-authored inline styles in source
- [ ] All JS files pass `node --check`
- [ ] `js_errors` = `[]`

### Gate F: User Walkthrough / Gänsehaut-Trigger

- [ ] Page loads with visible content (not black screen)
- [ ] Header HUD, command input, radial gradient all render
- [ ] Intro engine completes (`intro-done` class)
- [ ] `MazeGlyph` loaded and ready
- [ ] `MazeGPUGraph` correctly inert when backend ≠ webgpu
- [ ] Zero JS errors throughout
- [ ] Manual walkthrough: Opening → Final-loop works smoothly
- [ ] Worlds gallery & film smooth on target GPU (RTX 4060 Ti class)

## Common Failure Patterns & Fixes

| Symptom | Check | Fix |
|---------|-------|-----|
| Black screen, all canvases 0px | `js_errors` has ReferenceError | Wrap each tier in try/catch; ensure boot ladder doesn't unwind |
| `requestAdapter` hangs | No timeout in boot | Add `Promise.race([requestAdapter(), timeout(5000)])` |
| `#intro-canvas` 0px but intro done | React renders 2nd canvas | Intro IIFE runs before DC renders; ensure single canvas ownership |
| Glyph canvas 0px | Intro not at GLYPH phase | Verify `progress` reaches 1.0; check `MazeGlyph.renderGlyph` called |
| `MazeGPUGraph` tries to run on canvas2d | Guard missing | Check `window.__webgpuBoot.backend() === "webgpu"` before mount |

## Quick Command Reference

```bash
# Static checks
node --check assets/*.js support.js
grep -o 'src="media/[^"]*"' index.html | sed 's/src="//;s/"//' | xargs -I{} test -f {}

# Self-tests
cd assets && node glyph-det-test.js
cd assets && node gpu-graph-selftest.js

# Inline script check
# Extract inline <script> to /tmp/inline.js && node --check /tmp/inline.js
```

---

*Generated from implementation-verification skill verification session*