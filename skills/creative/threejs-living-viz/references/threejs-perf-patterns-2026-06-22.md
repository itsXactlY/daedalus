# Three.js Performance Patterns

Distilled from the Pandora's Box build at `/home/alca/projects/mazemaker-v2-stack/frontend/website/architect/pandoras-box.html` on 2026-06-22. The user's complaint was "1fps trash lol wow" — the build was originally a 100K-char Three.js scene with 12 monitor chambers, a 5000-node neural pool, 7800 edges, pulse particles, and full post-processing. After this pass it was substantially faster (the headless test reported 55fps without GPU; user's real browser should hit 60 locked).

## When the user complains about frame rate

Audit the build in this order. Each item below is independent and reversible; pick the ones that match the bottleneck you find in DevTools → Performance.

### 1. Cap pixelRatio at 1.0 for content scenes

```js
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.0));  // 1.0 for content
```

On a HiDPI display at 2×, `setPixelRatio(1.75)` means 1.75² = 3.06× more fragments than 1.0. Every full-screen pass (UnrealBloom, RGBShift, FXAA, custom ShaderPass) is multiplied by this — capping pixelRatio is the single biggest fragment-shader win. Use 1.5+ only for high-fidelity product hero scenes; for content / dashboard / 3D-explorable scenes, 1.0 is the right default.

### 2. Audit the post-process chain

```js
// BEFORE: 3 fullscreen passes (3× fragment cost)
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new UnrealBloomPass(...));
composer.addPass(new ShaderPass(RGBShiftShader));  // ← barely visible, full cost

// AFTER: 2 passes, half the cost
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new UnrealBloomPass(...));
```

Every post-process pass runs its fragment shader on every pixel of the screen. An RGBShift pass that nudges R and B channels by 12px every frame is often invisible after the tone-down — and it's a fullscreen fragment pass. Delete any pass whose visual contribution is below its cost. If you need the effect, gate it on a phase change and run zero-cost the rest of the time.

### 3. Hoist per-frame allocations out of animation hot path

```js
// BAD: GC pressure every frame
function animate(){
  const c = new THREE.Color(cur.hue);          // ~60 allocs/sec
  const dummy = new THREE.Object3D();          // ~60 allocs/sec
  group.children.find(c => c.userData.foo);    // O(n) per frame
}

// GOOD: module-scope scratch + cached lookups
const _c = new THREE.Color();
const _dummy = new THREE.Object3D();
const _cache = {};
function init(){ _cache.foo = scene.children.find(c => c.userData.foo); }
function animate(){
  _c.setHex(cur.hue);                          // mutate, no alloc
  _dummy.position.set(x, y, z);                // mutate, no alloc
  useFoo(_cache.foo);                          // O(1) lookup
}
```

The `find` cache only needs to be re-built when the scene tree changes (rarely). See `SKILL.md` Section 11 for the full pattern.

### 4. Gate scene animations on player position

If the world is a hub-and-spoke (multiple rooms, only one visible at a time), don't animate rooms the player can't see:

```js
// In the render loop:
if (currentRoomId === 'NEURAL_POOL'){
  updatePulseParticles();   // 80 setMatrixAt/frame
} else if (currentRoomId === 'VAULT'){
  updateVaultOrbs();         // 3 setMatrixAt/frame
} else if (currentRoomId === 'ATOMIZER'){
  updateFactParticles();     // 80 setMatrixAt/frame
}
// HUB: none of the above runs
```

For the Pandora's Box, this dropped 176 matrix updates/frame when the player was in the HUB. For hub-and-spoke scenes, the savings scale with the number of specialty rooms.

### 5. Reduce particle counts when they don't carry meaning

The "feel alive" instinct pushes 200+ particles per system. Before shipping, ask: does the user actually notice 200 vs 80 in a 16:9 frame at 60fps? Often 80 reads identical to 200, and 60% of the matrix-upload work disappears.

| System | Pandora's Box before | after | Visible difference |
|---|---|---|---|
| Neural pool pulse particles | 220 | 80 | none — too small to count |
| Phase chamber drifting | 80 × 4 rooms | 24 × 4 | none — they blend into the orb |
| Atomizer fact particles | 200 | 80 | none — radial pattern reads the same |

### 6. Pitfall: GLSL reserved attribute names in raw `ShaderMaterial`

In raw `THREE.ShaderMaterial` (not `onBeforeCompile` or `MeshStandardMaterial`-derived), the WebGL/Three.js runtime will silently fail to link the program if you name a custom attribute the same as a built-in slot. Symptom: `gl.getError()` returns `0x502 INVALID_OPERATION` every frame, and Three.js does NOT log it to `console.warn`.

```glsl
// BAD — 'uv' is a WebGL/Three.js built-in slot
attribute vec2 uv;
varying float vU;
void main(){ vU = uv.x; }

// GOOD — prefix all custom attributes with 'a'
attribute vec2 aEdgeU;
varying float vU;
void main(){ vU = aEdgeU.x; }
```

Reserved attribute names to AVOID in raw `ShaderMaterial`:
- `position` (built-in, declare in shader if used)
- `normal` (built-in)
- `uv` / `uv2` (built-in)
- `tangent` (built-in)
- `color` (built-in, but NOT auto-declared in raw `ShaderMaterial` even with `vertexColors: true` — you must declare `attribute vec3 color;` explicitly)
- `skinIndex` / `skinWeight` (skinned mesh)

**Safe naming convention**: prefix every custom attribute with `a` (`aSalience`, `aEnergy`, `aColor`, `aType`, `aEdgeU`; don't use `aPosition` because of `position` — use `aOffset` etc.).

**How to detect this bug**:
- Poll `gl.getError()` in a loop after 2-3 fresh rAF frames. If you see `0x502` every frame, it's a shader link issue.
- To get the actual `getShaderInfoLog` / `getProgramInfoLog`, monkey-patch `gl.compileShader` and `gl.linkProgram` BEFORE the page renders (inject via `document.write` at the top of the HTML, or a service worker). Once the page is loaded you can't reach the programs Three.js cached them in.
- Clear all pending errors first: drain via `while (gl.getError() !== gl.NO_ERROR) {}` before counting — leftover errors from the previous page state will give false positives.

**Why this isn't documented well**: Three.js's raw `ShaderMaterial` docs mention "use built-in attributes if you need them" but don't enumerate the reserved-name list, and the failure is silent (no `console.warn`, just `INVALID_OPERATION` on the first `drawArrays` against the unlinked program). The matrix mostly covers raw `ShaderMaterial`; `MeshStandardMaterial` + `onBeforeCompile` is more forgiving because the chunks auto-declare.

### 7. When removing a central data object, rewrite every downstream consumer

Symmetric refactor pitfall. Removed a top-level `CORPUS` constant → two consumers broke: a `const X = CORPUS.foo` at module init (TDZ-free if it's `const` not `let`), and an animate function that did `setMatrixAt` on an `InstancedMesh` that no longer exists. After a large refactor:

1. `grep` for the deleted identifier in the entire file
2. For every consumer, check the *contract* — does it call methods that no longer exist on the new data structure?
3. For each animation function, retarget it to the new contract (e.g. if rendering moved from `InstancedMesh` to `Points` + `ShaderMaterial`, the animation becomes uniform-pushes not matrix-updates)
4. Verify with: `node --check` on the extracted module body, then load in browser, then read HUD numbers — empty strings mean the data flow is broken

The 4-step verification catches the bug at the right granularity: a fresh load test catches "module crashed early", an empty-HUD test catches "module ran but data flow is unwired", a stale-GL-error test catches "rendered but the shader link failed".

## Headless-browser verification caveat

The Browserbase headless browser used for verification cached aggressively during this build. Symptoms: `requestAnimationFrame` runs at 60Hz but the page's `loop` function never gets invoked; HUD values stay at HTML defaults (`—`, `0,0,0`); no console errors. Solutions tried: query-param cache-bust, F5 reload, hard reload, different port. None worked. The only reliable test was to trust the file (curl-confirm the new content was being served) and let the user verify in their real browser. When a similar cache-stick happens, do not chase it in headless — confirm the served bytes match, then report to the user and let them test.
