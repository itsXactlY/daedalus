# Three.js + WebGL Gotchas from Real Production Builds

Hard-won lessons from the pandoras-box.html build (2026-06-22, ~106KB single-file
Three.js experience with 5,000-node Points + 7,800-edge LineSegments + 27 walkable
chambers + live pod integration). Each gotcha cost a debugging round — capture
them so future builds don't repeat the same mistakes.

---

## 1. Raw `ShaderMaterial` reserved attribute names → silent link failure

**Symptom:** `gl.getError()` returns `0x502` (GL_INVALID_OPERATION) every frame.
Three.js does NOT print anything to `console.warn`. The shader program fails
to link silently, the GPU renders blank/black for that draw call, and the
rest of the scene still works — so it's easy to miss.

**Root cause:** Raw `ShaderMaterial` lets you write any GLSL you want, including
re-declaring attributes that are auto-injected by WebGL/Three.js. Naming
collision with a built-in → duplicate-attribute error at link time → program
not linked → drawArrays on unlinked program → INVALID_OPERATION.

**Built-in attribute names to AVOID in raw `ShaderMaterial` declarations:**
`position`, `normal`, `uv`, `uv2`, `tangent`, `color`, `skinIndex`, `skinWeight`.
Even though `vertexColors: true` is set, Three.js does NOT auto-inject
`attribute vec3 color;` for raw `ShaderMaterial` (only ShaderChunks like
`MeshBasicMaterial` get this — declare it yourself if you need it).

**Convention:** prefix all custom attributes with `a`:
`aSalience`, `aEnergy`, `aColor`, `aType`, `aEdgeU`, `aSpeed`, `aPhase`.
Build-in names that you DO need (e.g. `color` for vertexColors) → declare
explicitly in the vertex shader.

**Detection:** when you see GL error 0x502, monkey-patch
`gl.compileShader` and `gl.linkProgram` BEFORE the page renders (inject
via document.write or service worker — too late to instrument after the
module has already run). Look for `COMPILE_STATUS` / `LINK_STATUS` returning
false. Always consume stale errors first, then check fresh ones over 2
frames — false positives from earlier broken pages linger in the error queue.

```js
// Hook BEFORE the page renders
const _gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
const _origLink = _gl.linkProgram.bind(_gl);
_gl.linkProgram = function(prog){
  _origLink(prog);
  if (!_gl.getProgramParameter(prog, _gl.LINK_STATUS)){
    console.error('link fail:', _gl.getProgramInfoLog(prog));
  }
};
```

---

## 2. TDZ (Temporal Dead Zone) cascade in large file refactors

**Symptom:** `ReferenceError: Cannot access '<name>' before initialization`
at some line deep in the file. The page silently fails — HUD stays at HTML
defaults, the loop never starts, console shows zero errors beyond the one
ReferenceError.

**Why it kept happening in pandoras-box.html (3 separate TDZ bugs in one file):**
a single 2,400-line single-file Three.js experience with module-scoped
let bindings, where refactors that move declarations leave stale references
in `addRoom({...})` push calls, `setPhase()` closures, `pushInception()` calls,
etc. — the moves are too granular to mentally trace.

**Pattern that always wins:**

```js
// BAD: push references a name declared 7 lines later
PHASE_ROOMS.push({ phase, group, orb, pmesh });   // pmesh is TDZ here
const pmesh = new THREE.InstancedMesh(...);

// GOOD-A: push AFTER the name exists
const pmesh = new THREE.InstancedMesh(...);
PHASE_ROOMS.push({ phase, group, orb, pmesh });

// GOOD-B: declare-empty-then-assign-later (works even if order is reshuffled)
let pmesh = null;
PHASE_ROOMS.push({ phase, group, orb, pmesh });
// ... later ...
pmesh = new THREE.InstancedMesh(...);
```

**Test rig after ANY large refactor:**
1. `python3 -c "import re; open('f.html').read()..."` extract module body
2. `node --check /tmp/extracted.mjs` — catches syntax, NOT runtime
3. Open in browser with a smoke-test at the bottom of the file:
   `setTimeout(() => console.info('LOOP_ALIVE'), 200)` — if you don't see it,
   the module crashed
4. Check the browser console for any uncaught errors (window.error +
   unhandledrejection handlers)
5. Check the actual DOM: if any `<b id="hud-X">` is still at its HTML default
   value 2 seconds after load, the JS that updates it never ran

---

## 3. Post-processing audit — every pass costs fullscreen fragment work

**Pattern that earned the cut:** in pandoras-box.html, the `RGBShift` ShaderPass
contributed ~zero visible effect after the tone-down but cost a fullscreen
fragment shader every frame. Drop it. Half the post-process chain, same
visible result, real perf gain.

**Audit checklist before shipping:**
- For every pass in `composer.addPass(new ...)`:
  - Does it materially change the image? (If the toggle would be invisible,
    drop the pass.)
  - What's the cost? UnrealBloom is heavy (multi-mip downsample + upsample).
    ShaderPass is one fullscreen quad. RenderPass is a no-op overhead.
  - Is it conditional? A kick on phase change can be a uniform, not a
    permanent pass.

**Reasonable default for an "editorial dark" 3D page:**
- `RenderPass` (required)
- `UnrealBloomPass` with strength 0.10–0.25, threshold 0.20–0.30 (only
  really bright things bloom; the rest of the scene stays clean)
- NO RGBShift / NO FilmPass / NO custom ShaderPass unless visibly
  contributing

---

## 4. Brand-aligned single-accent palette: hue variation reads as rainbow

**Symptom:** even after switching CSS to brand violet `#8b5cf6`, the 3D scene
still has phosphor-green doorways, cyan hermes bridge, mint observation
deck, red federation vault, pink phase REM, amber phase DECISION — the
screenshot looks like a "rainbow circus" because every room uses its own
"distinguishing color".

**Fix pattern (paste-ready):**

```js
// BAD: distinguish elements by hue
const labelColors = {
  'fact:':    0xa78bfa, 'decision:': 0xc4b5fd, 'bug:': 0xfca5a5,
  'invariant:': 0x67e8f9, 'ops:':       0x9ca3af, 'user:': 0x6ee7b7,
  'signal:':    0xf9a8d4, 'skill:':     0x8b5cf6, 'commit:': 0xfdba74,
  'reference:': 0x78716c, 'feedback:': 0xc4b5fd, 'auto:': 0xededf2,
  'derived:':   0x7c3aed,
};

// GOOD: distinguish by LIGHTNESS, keep HUE constant on the brand
const labelColors = {
  'fact:':      0xb9a4fa,  // ~75% lightness
  'decision:':  0xa78bfa,  // ~70%
  'bug:':       0x8b5cf6,  // brand
  'invariant:': 0xc4b5fd,  // ~80%
  'ops:':       0x6d4ec9,  // ~55%
  'user:':      0x9778fa,  // ~68%
  'signal:':    0x7c5fd9,  // ~60%
  'skill:':     0xa78bfa,  // brand-hi
  'commit:':    0x8b5cf6,  // brand
  'reference:': 0x5e3da3,  // ~45% (muted)
  'feedback:':  0xb9a4fa,
  'auto:':      0xededf2,  // bone-white (slight pop)
  'derived:':   0x9778fa,
};
```

**Same for doorway glow plates** — instead of 14 different colors for 14
doorways, just use one (the brand) and let the LABEL TEXT distinguish
destinations. The hub-and-spoke layout already groups them visually; the
color-coding is redundant and adds noise.

**EXCEPTION to preserve:** state-machine colors (AWAKE/NREM/REM/INSIGHT
phase hues, status ok/warn/err). These are part of the design language,
not decoration. The dream-phase state machine has 4 distinct chambers that
need to be visually identifiable from across the hub.

---

## 5. Bulk sed cleanup — the `, { ` trap

**Anti-pattern:** `sed -e 's/, { color:0xXXXXXX/, {/g'` produces
`doorway(..., {, w:2.0, h:3.0 })` — an empty object literal, which is a
SyntaxError in strict mode (which `<script type="module">` enforces).

**Two-step pattern when normalizing opts objects:**

```bash
# Step 1: strip the color arg, leaving the comma before the { dangling
sed -i 's/doorway(\([^,]*\), { color:0x[0-9a-fA-F]\+/doorway(\1, {/g' file.html
# Step 2: clean up the empty {, { pattern
sed -i 's/doorway(\([^,]*\), {, /doorway(\1, { /g' file.html
# Step 3 (optional): if no other args, drop the {} entirely
sed -i 's/doorway(\([^,]*\), { })/doorway(\1)/g' file.html
```

ALWAYS run `node --check` after bulk sed passes that touch syntax. Multi-step
sed is faster than per-call patches but needs verification.

---

## 6. BrowserBase headless caching: use port change + cache-bust

**Symptom:** BrowserBase headless browser keeps showing the OLD HTML even
after `browser_navigate(url?cacheBust=...)`. Position element shows the
HTML default value, loop never starts — but the served file is the new one
(curls the new bytes), and `node --check` passes. User opens in real
browser → fresh load → works.

**Workaround for headless testing:**
1. Start server on a different port (9017 → 9022)
2. `?cacheBust=22.06.07.50` (timestamp-stamped query)
3. Even that sometimes fails — fall back to: trust the file-on-disk check
   (curl the served bytes, diff against the file) + `node --check` for
   syntax + ask the user to do a real-browser test

**Real-browser hard-reload reminder:** when telling the user "test the
new version", suggest `Ctrl+Shift+R` (or Cmd+Shift+R on Mac) to bypass
service workers and browser cache.

---

## 7. Per-frame allocation hot path

The cinematic-html-trailer skill has a good "declare all `let` state at the
TOP of the script" warning. For Three.js specifically, the equivalent rule
is: **never `new THREE.Color()`, `new THREE.Object3D()`, `new Vector3()`,
or `new Float32Array()` inside a function called from the render loop.**

```js
// BAD
function animate(){
  const c = new THREE.Color(cur.hue);
  const dummy = new THREE.Object3D();
  // ... 5000 iterations using dummy and c
}

// GOOD — module-scope scratch
const _phaseColor = new THREE.Color();
const _pulseDummy = new THREE.Object3D();
const _hslScratch = { h:0, s:0, l:0 };
function animate(){
  _phaseColor.setHex(cur.hue);
  _phaseColor.getHSL(_hslScratch);
  _pulseDummy.position.set(x, y, z);
  // ... iterations
}
```

Other gotchas to grep for in the loop:
- `array.find()` over a scene graph — cache the result at build time
- `instanceMatrix.needsUpdate = true` on a mesh that's outside the camera
  frustum — cull it instead
- Animation work that runs every frame regardless of player position —
  gate it: `if (currentRoomId === 'X') animateX();`
