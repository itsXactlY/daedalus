---
title: Common Failure Patterns
description: Known failure modes and fixes for WebGPU/Canvas2D gated implementations
---

# Common Failure Patterns & Fixes

This document captures known failure modes encountered during gate verification of WebGPU/Canvas2D fallback implementations, with verified fixes.

---

## 1. Black Screen / Zero Pixels on All Canvases

### Symptom
- `browser_vision` shows black/empty page
- All canvases report 0 non-zero pixels
- `js_errors` shows `ReferenceError: createCanvas is not defined`

### Root Cause
The boot ladder (`webgpu-boot.js`) attempts WebGPU → WebGL2 → Canvas2D, but an exception in one tier isn't caught, causing the entire boot to unwind before reaching the 2D fallback.

### Evidence
```
[WebGPUBoot] WebGPU failed, trying WebGL2: requestAdapter returned null
ReferenceError: createCanvas is not defined
    at paint2D (webgpu-boot.js:87)
    at boot (webgpu-boot.js:156)
```

### Fix
Wrap **each tier attempt** in its own try/catch block, ensuring the ladder continues to the next tier:

```javascript
async function boot() {
  // Tier 1: WebGPU
  try {
    const adapter = await navigator.gpu.requestAdapter();
    if (adapter) {
      const device = await adapter.requestDevice();
      // ... setup WebGPU
      return { backend: 'webgpu', device };
    }
  } catch (e) {
    console.warn('[WebGPUBoot] WebGPU failed, trying WebGL2:', e.message);
  }

  // Tier 2: WebGL2
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2', { ... });
    if (gl) {
      // ... setup WebGL2
      return { backend: 'webgl2', gl };
    }
  } catch (e) {
    console.error('[WebGPUBoot] WebGL2 failed:', e.message);
  }

  // Tier 3: Canvas2D (MUST NOT THROW)
  try {
    const canvas = document.getElementById('stage2d') || createCanvas2D();
    const ctx = canvas.getContext('2d', { alpha: true, desynchronized: true });
    paint2D(ctx, canvas.width, canvas.height); // Safe paint
    return { backend: 'canvas2d', ctx };
  } catch (e) {
    console.error('[WebGPUBoot] 2D canvas failed:', e.message);
    throw e; // Last resort - no fallback left
  }
}
```

### Verification
- `js_errors` = `[]`
- `#stage2d` has >0 non-zero pixels
- Console shows all three boot log lines

---

## 2. `requestAdapter()` Hangs / No Timeout

### Symptom
- Page load hangs indefinitely
- No console output from WebGPU tier
- Browser tab becomes unresponsive

### Root Cause
`navigator.gpu.requestAdapter()` can hang on some headless/CI environments without a timeout guard.

### Fix
Add a timeout promise race:

```javascript
const ADAPTER_TIMEOUT = 5000; // 5 seconds

const adapter = await Promise.race([
  navigator.gpu.requestAdapter({ powerPreference: 'high-performance' }),
  new Promise((_, reject) =>
    setTimeout(() => reject(new Error('requestAdapter timeout')), ADAPTER_TIMEOUT)
  )
]).catch(() => null); // null = treat as unavailable
```

### Verification
- Page loads within timeout period
- Console shows `[WebGPUBoot] WebGPU failed, trying WebGL2: requestAdapter returned null` (or timeout message)

---

## 3. `#intro-canvas` Shows 0 Pixels Despite Intro Complete

### Symptom
- `document.body.className` contains `intro-done`
- `typeof window.MazeIntro === "object"`
- `#intro-canvas` non-zero pixel count = 0
- `MazeIntro` seed logged in console

### Root Cause
The intro IIFE (in `intro.js`) creates its own canvas and calls `resize()` on it. Separately, the dc-runtime React component renders a `<canvas id="intro-canvas">` from the template. The IIFE's canvas gets the drawing; the React canvas remains at default 300×150 with no drawing operations.

### Fix Options

**Option A: Single Canvas Ownership (Recommended)**
Have the IIFE use the React-rendered canvas:
```javascript
// In intro.js IIFE
const canvas = document.getElementById('intro-canvas');
if (canvas) {
  // Use existing canvas instead of creating new one
  const ctx = canvas.getContext('2d', { ... });
  // ... render to this canvas
}
```

**Option B: Hide React Canvas**
```css
/* In style.css */
#intro-canvas { display: none; }
```
And let IIFE create its own canvas (current behavior, but documented).

### Verification
- Single canvas with drawing operations
- Non-zero pixel count on the active intro canvas

---

## 4. Glyph Canvas Shows 0 Pixels

### Symptom
- `typeof window.MazeGlyph === "object"` (loaded)
- Glyph canvas exists (288×72, no id)
- Non-zero pixel count = 0
- Intro phase not reached GLYPH state

### Root Cause
`MazeGlyph.renderGlyph()` is only called when intro reaches the GLYPH phase (progress ≥ threshold). If intro stalls or doesn't progress to that phase, glyph never renders.

### Fix
Verify intro progression:
```javascript
// In intro.js - check phase progression
if (stateProgress >= GLYPH_PHASE_THRESHOLD && window.MazeGlyph) {
  MazeGlyph.renderGlyph(ctx, width, height, cursorPath, stateProgress, time);
}
```

Check console for: `maze seed {hex} ({visit}::{date})` — confirms intro ran.

### Verification
- `browser_console` shows intro seed log
- `document.body.className` contains `intro-done`
- Glyph canvas non-zero > 0 after GLYPH phase

---

## 5. `MazeGPUGraph` Attempts to Run on Non-WebGPU Backend

### Symptom
- `window.__webgpuBoot.backend()` returns `"canvas2d"`
- `MazeGPUGraph` still tries to create WebGPU resources
- Errors in console about `device.createBuffer` on null

### Root Cause
Missing guard in `MazeGPUGraph` mount/initialization to check active backend.

### Fix
Add backend check before GPU resource creation:

```javascript
// In gpu-graph.js mount() or init()
if (window.__webgpuBoot?.backend() !== 'webgpu') {
  console.log('[MazeGPUGraph] decision: backend="canvas2d" — GPU particle graph inert');
  return { inert: true }; // Graceful no-op
}

// Proceed with WebGPU setup only if backend === 'webgpu'
```

### Verification
- Console shows: `[MazeGPUGraph] decision: backend="canvas2d" — GPU particle graph inert (0 canvases added, no adapter requested)`
- No WebGPU errors in console
- `typeof window.MazeGPUGraph === "object"` (still loaded, just inert)

---

## 6. Inline Script Syntax Errors (Gate D Fail)

### Symptom
- `node --check` on extracted inline script fails
- Gate D: "JS syntax clean" fails

### Common Causes
1. Template literal interpolation issues in dc-runtime scripts
2. Missing semicolons in IIFE
3. `const`/`let` in non-strict mode (though all should be strict)

### Fix
- Extract inline script to temp file: `cat > /tmp/inline.js << 'EOF' ... EOF`
- Run `node --check /tmp/inline.js`
- Fix syntax errors in source template (`index.html` or dc component)

### Verification
- All inline scripts pass `node --check`

---

## 7. Media Asset 404 (Gate D Fail)

### Symptom
- `test -f media/{asset}.webp` fails
- HTTP 404 for asset
- `browser_vision` shows broken image placeholders

### Root Cause
Asset referenced in `index.html` but not copied to worktree `media/` directory.

### Fix
```bash
# Verify all referenced assets
grep -o 'src="media/[^"]*"' index.html | sed 's/src="//;s/"//' | sort -u | xargs -I{} test -f {} || echo "MISSING: {}"

# Copy from source if available
cp /path/to/source/media/{asset}.webp media/
```

### Verification
- All `test -f` checks pass
- HTTP 200 for all asset endpoints

---

## 8. Self-Test Failures

### Glyph Determinism Test Fails

| Failure | Cause | Fix |
|---------|-------|-----|
| `MazeGlyph not loaded` | `glyph.js` not loaded before test | Ensure `require('./glyph.js')` runs before accessing `window.MazeGlyph` |
| Fingerprint not stable | `Math.random()` used instead of `mulberry32` | Replace all RNG with seeded `mulberry32` |
| Commands differ | `performance.now()` or `Date.now()` in render | Use injected `time` parameter only |

### GPU Graph Selftest Fails

| Failure | Cause | Fix |
|---------|-------|-----|
| Binding count mismatch | WGSL `@binding` decorators don't match JS layout | Align `@group(0) @binding(N)` with `bindGroupLayout` entries |
| Buffer size not multiple of 16 | Struct padding incorrect | Add explicit padding fields to match `std140`/`std430` layout |
| Workgroup size mismatch | `WORKGROUP_SIZE` constant differs | Sync constant between JS and WGSL |

---

## Quick Reference: Failure → Check → Fix

| Failure | First Check | Likely Fix |
|---------|-------------|------------|
| Black screen | `js_errors` | Try/catch each boot tier |
| Hang on load | Network tab / console | `requestAdapter` timeout |
| Intro canvas 0px | `intro-done` class present? | Single canvas ownership |
| Glyph canvas 0px | Intro seed logged? | Verify GLYPH phase reached |
| GPU graph errors | `backend()` value | Add backend guard |
| Gate D fail | `node --check` output | Fix syntax in source |
| Asset 404 | `test -f` output | Copy asset to media/ |
| Self-test fail | Test output assertions | Fix RNG/binding/layout |

---

*Generated from implementation-verification skill verification session*