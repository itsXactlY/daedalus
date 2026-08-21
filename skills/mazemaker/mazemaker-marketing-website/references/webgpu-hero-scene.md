# WebGPU hero scene — implementation reference (commit 524018e)

From-scratch full-viewport GPU scene for the Mazemaker landing. Read the
"WebGPU rebuild" section of SKILL.md first for the operator context; this file
has the concrete code shape.

## Structure

```
<canvas id="gpuScene" aria-hidden="true"></canvas>   <!-- fixed inset:0, z-0, pointer-events none -->
...
<script src="assets/pod.js"></script>               <!-- engine FIRST -->
<script> /* scene + composer, plain IIFEs, no modules */ </script>
```

Scene boots in an IIFE: `resize()` first (dpr capped at 2), then
`if (prefers-reduced-motion) { statGpu="static"; return; }` (NO simulation at
all), then `initWebGPU().then(ok => ok || initCPU()).catch(initCPU)`.

## WebGPU path (primary)

```js
if (!navigator.gpu) return false;
const adapter = await navigator.gpu.requestAdapter();   // null in headless
const device  = await adapter.requestDevice();
const fmt = navigator.gpu.getPreferredCanvasFormat();
const ctx = canvas.getContext("webgpu");               // null if unsupported
ctx.configure({ device, format: fmt, alphaMode: "premultiplied" });
```

- Uniform buffer: `Float32Array([W, H, time, mouseX, mouseY, 0])`, usage
  `UNIFORM | COPY_DST`, rewritten every frame via `device.queue.writeBuffer`.
- Storage buffers: `pos` (Float32Array N*2) + `vel`, usage
  `STORAGE | COPY_DST` (pos also `COPY_SRC` for readback if needed).
- BindGroupLayout: binding 0 uniform (COMPUTE|VERTEX), 1 pos
  read-only-storage (COMPUTE|VERTEX), 2 vel storage (COMPUTE only).
- Compute pipeline: `@compute @workgroup_size(64)`, guard
  `if (i >= arrayLength(&pos)) return;`, integrate: pull toward breathing
  centre (`cx = W*0.5 + sin(t*0.5 + i*0.01)*W*0.06`), mouse repulsion
  (`if (d2 < 40000 && d2 > 1) v += d/d2 * 30`), damp `*0.985`, wrap edges.
  `dispatchWorkgroups(Math.ceil(N/64))`.
- Render pipeline: `@vertex` builds an instanced quad — `vi/6u` = particle,
  `vi%6u` = corner; 6 verts per particle, `draw(N*6, 1, 0, 0)`.
  `@fragment` returns `vec4(color, 0.5)`; color = amber→green mix by
  `f32((i * 2654435761u) % 100u)/100.0`. Fragment target blend:
  src-alpha / one-minus-src-alpha on both color and alpha.
- Render pass: `clearValue {r:0,g:0,b:0,a:0}`, loadOp clear, storeOp store on
  `ctx.getCurrentTexture().createView()`.

## CPU fallback (headless / no GPU)

`canvas.getContext("2d")`, ~220 particles, same centre-pull + damp + wrap
integration, `fillStyle rgba(232,165,94,0.5)`, `arc(r=1.4)` per particle.
Set `statGpu="canvas2d"`, badge "running locally · canvas2d".

## Honesty / disclosure

- Stats strip has `<b id="statGpu">—</b>renderer` — always set it:
  `webgpu` | `canvas2d` | `static` (reduced-motion). Never claim GPU that isn't
  running.
- Badge: `running locally · webgpu` / `· canvas2d`.

## Verification limits

Headless Chromium has no GPU adapter — `requestAdapter()` returns null, so only
the canvas-2d path is browser-testable there. Verify animation by comparing two
`getImageData` snapshots ~400ms apart (frames differ = animating). The WGSL path
is structurally checkable (markers: `requestAdapter`, `createShaderModule`,
`dispatchWorkgroups`) but real execution needs the operator's GPU machine.
