# GLSL Reserved Attribute Names in Raw ShaderMaterial — Full Debugging Recipe

**This is the most common silent shader bug in raw `THREE.ShaderMaterial` work.** It produces a `GL_INVALID_OPERATION` (0x502) on every `drawElements` call with no `console.warn`, no exception, no log message — the affected mesh just doesn't render and you only notice by polling `gl.getError()` manually.

## The bug class

Any custom `attribute` declared in a raw `ShaderMaterial` vertex shader that shares a name with a WebGL/Three.js built-in will fail to link. Three.js does NOT report this to `console.warn` because the failure happens inside the WebGL driver's program-link step, which Three.js treats as a silent error. The shader's program object exists but is invalid; subsequent `drawElements` calls on that program produce `INVALID_OPERATION`.

## Built-in names to avoid

| Name | Why it collides |
|------|-----------------|
| `position` | auto-declared by Three.js (and by WebGL2 implicitly for vertex shaders) |
| `normal` | auto-declared by Three.js when normals exist |
| `uv` | auto-declared by Three.js AND a built-in WebGL2 attribute slot |
| `uv2` | built-in for aoMap / lightMap |
| `tangent` | auto-declared when tangent attribute exists |
| `color` | auto-injected by Three.js IF `vertexColors: true` is set (your declaration is safe but redundant) |
| `skinIndex`, `skinWeight` | auto-declared when skinned mesh |

The most dangerous name is **`uv`** because it looks innocuous ("just a 2D coord") and is the most common custom-attribute name in user code. Three.js's auto-prepended declaration collides with your declaration → link error.

## Detection recipe (in DevTools console)

```js
// 1. Get the WebGL context from the Three.js canvas (the second one, after the minimap)
const c = document.querySelectorAll('canvas')[1];
const gl = c.getContext('webgl2') || c.getContext('webgl');

// 2. Drain all stale errors from previous page loads / accumulated frames
let drained = 0;
while (gl.getError() !== gl.NO_ERROR && drained < 100) drained++;

// 3. Wait 2-3 fresh frames
await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

// 4. Now collect only NEW errors
const fresh = [];
let e = gl.getError();
let n = 0;
while (e !== gl.NO_ERROR && n < 20) {
  fresh.push('0x' + e.toString(16));
  e = gl.getError();
  n++;
}
console.log('fresh GL errors:', fresh);
// 0x502 = INVALID_OPERATION   ← a custom shader is failing
// 0x501 = INVALID_VALUE
// 0x500 = INVALID_ENUM
// 0x502 every frame + nothing else = exactly the reserved-attribute bug
```

If you see `0x502` on every fresh-frame check, you have a shader-link failure. The next step is to identify which shader.

## Getting the actual GLSL info log

Three.js doesn't print it, so you have to monkey-patch BEFORE the page renders. Two options:

**Option A** — service worker intercept (heavy, only for full diagnostic mode)

**Option B** — inject via `document.write` before the module loads (simpler):

```js
// Before any other JS runs:
const origGet = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, ...rest) {
  const gl = origGet.call(this, type, ...rest);
  if ((type === 'webgl' || type === 'webgl2') && gl) {
    const origCompile = gl.compileShader.bind(gl);
    gl.compileShader = function(shader) {
      origCompile(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('SHADER COMPILE FAIL:', gl.getShaderInfoLog(shader));
      }
    };
    const origLink = gl.linkProgram.bind(gl);
    gl.linkProgram = function(prog) {
      origLink(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        console.error('PROGRAM LINK FAIL:', gl.getProgramInfoLog(prog));
      }
    };
  }
  return gl;
};
```

Then load the page — any shader failure is now loud with the actual GLSL error message.

## The fix

Prefix every custom attribute with `a` (or another unique prefix). Update three places:

1. The GLSL declaration
2. The `geometry.setAttribute` call
3. Every reference in the vertex shader body

```js
// BEFORE (silently broken)
edgeGeo.setAttribute('uv',     new THREE.BufferAttribute(uv, 2));   // collides
edgeGeo.setAttribute('aType',  new THREE.BufferAttribute(types, 1));
const edgeVert = `
  attribute vec2  uv;       // ← collision
  attribute float aType;
  varying float vU;
  void main() { ... vU = uv.x; }
`;

// AFTER (works)
edgeGeo.setAttribute('aEdgeU', new THREE.BufferAttribute(aEdgeU, 2));
edgeGeo.setAttribute('aType',   new THREE.BufferAttribute(types, 1));
const edgeVert = `
  attribute vec2  aEdgeU;    // ← no collision
  attribute float aType;
  varying float vU;
  void main() { ... vU = aEdgeU.x; }
`;
```

The naming convention `a<Name>` is the safest because no Three.js or WebGL built-in starts with `a`.

## Audit grep

Run on any new `ShaderMaterial` work, before the page loads:

```bash
rg -n 'attribute\s+\w+\s+\b(uv|position|normal|tangent|color|uv2|skinIndex|skinWeight)\b' path/
```

Any hit is a reserved-name collision waiting to happen. (Note: `attribute vec3 color` in a vertex shader using `vertexColors: true` is harmless because Three.js auto-declares it consistently, but it's redundant — drop your declaration.)

## Real example — Pandora's Box 2026-06-22

The edge shader in the central neural pool was meant to render 7,800 line segments with a per-edge 0-to-1 coordinate used for a "dashed flow" effect in the fragment shader. The author wrote:

```glsl
attribute vec2 uv;     // 0 at src end, 1 at dst end
varying float vU;
void main() { ... vU = uv.x; }
```

Three.js auto-prepended `attribute vec2 uv;` (because every Three.js vertex shader gets the standard set of built-ins). The link step saw two declarations of the same name in the same scope → program link failed silently → every frame's `drawElements` returned `GL_INVALID_OPERATION` (0x502). The neural pool and edges rendered as blank space with no console warning.

**Detection took 10 minutes of `gl.getError()` polling** because the symptom looks like a render-path bug, not a shader bug. The fact that Three.js doesn't print shader-info logs by default is a class-level footgun.

**Fix**: rename `uv` → `aEdgeU` in three places (declaration, geometry.setAttribute, vertex shader body). After the rename, `getError()` returned `NO_ERROR` on every fresh-frame check.

**Why this is hard to find with normal debugging**: there is no stack trace, no console message, no visible change in frame rate. The only signal is "this mesh doesn't render". The temptation is to suspect the geometry, the blending mode, the camera frustum, the depth test — anything except the shader. The audit grep is the fastest path: scan for `attribute` declarations and check each name against the built-in list.

## Related pitfall — `color` attribute without `vertexColors: true`

A common adjacent bug: writing `vColor = color;` in a vertex shader without setting `vertexColors: true` on the material. Result: `color` is undefined, GLSL defaults to `(0,0,0,1)`, all vertices render black. The fix is to set `vertexColors: true` on the `ShaderMaterial` (Three.js then auto-injects the attribute) OR to explicitly declare `attribute vec3 color;` in the vertex shader. The latter is more explicit and works without the `vertexColors` flag.

For raw `ShaderMaterial` work, the recommended pattern is to **always declare every attribute you use** — don't rely on Three.js auto-injection. The auto-injection is for ShaderChunks-based materials; for raw shaders, declare explicitly and you own the contract.
