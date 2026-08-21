---
name: webgpu-webgl-fallback-cascade
description: Implement a three-tier GPU rendering fallback cascade (WebGPU → WebGL → Canvas2D) for browser-based particle systems and compute shaders. Use when building WebGPU applications that need to work across browsers without WebGPU support (Firefox, older Chrome).
category: devops

---

# WebGPU/WebGL/Canvas2D Fallback Cascade

## When to Use

Building a WebGPU application (particle system, compute shader, render loop) and you need it to work in browsers that don't have WebGPU enabled yet — Firefox (even with flags off), older Chrome versions, Safari. The cascade: WebGPU → WebGL → Canvas2D ensures maximum compatibility.

## Architecture

```
Browser loads page
    │
    ├─ Try WebGPU? ─── YES → Use WebGPU compute shaders (WGSL)
    │                        Best performance, full feature set
    │
    ├─ NO → Try WebGL? ─── YES → Use WebGL fragment/vertex shaders
    │                         GPU-accelerated, spiral/labyrinth patterns
    │                         Soft additive blending, scroll-driven effects
    │
    └─ NO → Canvas2D fallback
                       CPU-rendered particles (ctx.arc)
                       Simple drift animation, lowest quality
```

## Steps

### 1. Create the WebGL fallback renderer

Build a GPU-accelerated WebGL renderer as `js/webgl-fallback.js`. Key components:

- **Vertex + fragment shaders** — GPU computes particle positions and colors per frame
- **Spiral initialization** — Particles spawn in a spiral pattern (not random)
- **Scroll-driven dissolution** — As user scrolls, particles spread outward from center
- **Soft additive blending** — Fragment shader uses `vec4(1.0)` to blend particles softly
- **Buffer management** — Float32Array particle data → GPU vertex buffer each frame

```javascript
// js/webgl-fallback.js — Minimal structure
export class WebGLFallback {
    constructor(canvas) {
        this.canvas = canvas;
        this.gl = null;
        this.program = null;
        this.positionLocation = -1;
        this.colorLocation = -1;
        this.sizeLocation = -1;
        this.vertexBuffer = null;
        this.particles = new Float32Array(6000); // 1000 particles × 6 values (x, y, r, g, b, size)
        this.running = false;
    }

    init() {
        const gl = this.canvas.getContext('webgl');
        if (!gl) return false;

        // Compile vertex + fragment shaders from strings
        const vs = this.compileShader(gl, 'VERTEX', `...`);
        const fs = this.compileShader(gl, 'FRAGMENT', `...`);

        // Link program, get attribute locations
        this.program = gl.createProgram();
        gl.attachShader(this.program, vs);
        gl.attachShader(this.program, fs);
        gl.linkProgram(this.program);

        this.gl = gl;
        this.positionLocation = gl.getAttribLocation(this.program, 'aPosition');
        this.colorLocation = gl.getAttribLocation(this.program, 'aColor');
        this.sizeLocation = gl.getAttribLocation(this.program, 'aSize');

        // Enable blending for soft particle rendering
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE); // Additive blending

        return true;
    }

    render(time) {
        const gl = this.gl;
        gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        gl.clearColor(0.05, 0.05, 0.1, 1.0);
        gl.clear(gl.COLOR_BUFFER_BIT);

        // Update particle positions (simple drift + spiral decay)
        this.updateParticles(time);

        // Upload to GPU buffer
        const data = new Float32Array(this.particles);
        if (!this.vertexBuffer) {
            this.vertexBuffer = gl.createBuffer();
        }
        gl.bindBuffer(gl.ARRAY_BUFFER, this.vertexBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);

        // Bind attributes and draw
        gl.useProgram(this.program);
        gl.enableVertexAttribArray(this.positionLocation);
        gl.enableVertexAttribArray(this.colorLocation);
        gl.enableVertexAttribArray(this.sizeLocation);
        gl.vertexAttribPointer(this.positionLocation, 2, gl.FLOAT, false, 24, 0);
        gl.vertexAttribPointer(this.colorLocation, 3, gl.FLOAT, false, 24, 8);
        gl.vertexAttribPointer(this.sizeLocation, 1, gl.FLOAT, false, 24, 20);

        gl.drawArrays(gl.POINTS, 0, this.particles.length / 6);
    }

    updateParticles(time) {
        for (let i = 0; i < 1000; i++) {
            const idx = i * 6;
            // Spiral decay with scroll influence
            this.particles[idx] += Math.sin(time * 0.5 + i * 0.01) * 0.001;
            this.particles[idx + 1] += Math.cos(time * 0.3 + i * 0.015) * 0.001;
        }
    }

    destroy() {
        if (this.vertexBuffer) this.vertexBuffer.delete();
        if (this.program) {
            this.gl.deleteProgram(this.program);
        }
    }

    compileShader(gl, type, source) {
        const shader = gl.createShader(gl[type === 'VERTEX' ? gl.VERTEX_SHADER : gl.FRAGMENT_SHADER]);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            console.warn('Shader compile failed:', gl.getShaderInfoLog(shader));
            gl.deleteShader(shader);
            return null;
        }
        return shader;
    }
}
```

### 2. Wire the cascade into the render loop

In your main system file (e.g., `js/labyrinth-system.js`), add WebGL fallback detection:

```javascript
import { WebGLFallback } from './webgl-fallback.js';

export class LabyrinthSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.webgpuDevice = null;
        this.webglFallback = null;  // ← New field
        this.running = false;
    }

    async init() {
        // Try WebGPU first (best performance)
        if (await this.initWebGPU()) {
            console.log('[Labyrinth] WebGPU initialized');
            return true;
        }

        // Fallback to WebGL (still GPU-accelerated, better than Canvas2D)
        const gl = this.canvas.getContext('webgl');
        if (gl) {
            this.webglFallback = new WebGLFallback(this.canvas);
            if (this.webglFallback.init()) {
                console.log('[Labyrinth] WebGL fallback active');
                return true;
            }
        }

        // Last resort: Canvas2D (CPU-rendered, simple particles)
        console.warn('[Labyrinth] Falling back to Canvas2D');
        this.canvas2d = this.canvas.getContext('2d');
        return false;
    }

    animate(now) {
        if (!this.running) return;

        if (this.webglFallback) {
            // WebGL path — GPU-accelerated particles
            this.webglFallback.render(now);
        } else if (this.canvas2d) {
            // Canvas2D path — CPU particles
            this.canvas2d.clearRect(0, 0, this.canvas.width, this.canvas.height);
            // ... existing Canvas2D particle logic ...
        }

        requestAnimationFrame((t) => this.animate(t));
    }

    destroy() {
        this.running = false;
        if (this.webglFallback) {
            this.webglFallback.destroy();
        }
        if (this.canvas2d) {
            // Canvas2D cleanup — nothing special needed
        }
    }
}
```

### 3. Verify the cascade works

```bash
# Syntax check all JS files
for f in js/*.js app.js; do node --check "$f" && echo "OK $f"; done

# Start dev server and test in browser
cd ~/v3 && python3 -m http.server 8081 &
# Open in Firefox (no WebGPU flags) → should see WebGL fallback active
# Open in Chrome with WebGPU disabled → should also hit WebGL or Canvas2D
```

## Pitfalls

- **WebGL context loss** — If the GPU driver crashes, `webgl` context may be lost. Add a `contextlost` event listener and attempt to restore.
- **Shader compilation errors** — WebGL shaders fail silently if syntax is wrong. Always check `gl.getShaderInfoLog()` after compile.
- **Additive blending requires premultiplied alpha** — If particles look washed out, use `gl.blendFunc(gl.ONE, gl.ONE)` instead of additive.
- **Canvas2D performance** — CPU-rendered particles at 60fps with 1000+ particles can cause jank. Limit particle count or reduce animation complexity for Canvas2D path.
- **Destroy cleanup** — Always call `destroy()` on WebGL context, program, and buffers to avoid memory leaks (especially important if the render system is recreated).
- **Float32Array alignment** — Vertex attribute pointers must match buffer layout exactly. If positions are 2 floats (8 bytes), colors start at offset 8, sizes at offset 20 for RGBA + size layout.
- **WebGL2 `gl_PointSize` is mandatory** — Modern browsers default to WebGL2 when you call `canvas.getContext('webgl')`. In WebGL2 the old WebGL1 method `gl.pointSize()` does NOT exist — calling it throws `TypeError: gl.pointSize is not a function`. You MUST set point size per-vertex in the vertex shader via `gl_PointSize = yourValue;`. If your shader computes a varying for size, assign it to `gl_PointSize` before `gl.drawArrays(gl.POINTS, ...)`.
- **WebGPU adapter strategies must use valid enums** — The WebGPU spec only accepts `'low-power'`, `'high-performance'`, or no preference. Using `'max-performance'` (or any other value) throws a TypeError on `requestAdapter()`. Only use the three valid options in your retry strategies.
- **Silence per-try console logging during fallback** — When WebGPU isn't available (Firefox, older Chrome), each failed adapter request logs a warning. If you have 5+ retry strategies that all fail, the console gets spammed with 5+ warnings before falling back to WebGL. Suppress intermediate try logs and only emit ONE final fallback message.

## Verification Checklist

- [ ] WebGPU path works in Chrome with WebGPU enabled
- [ ] WebGL fallback activates in Firefox without WebGPU flags
- [ ] Canvas2D fallback activates when both WebGPU and WebGL fail
- [ ] `destroy()` called on page unload prevents memory leaks
- [ ] All particle systems render correctly across all three paths
- [ ] No shader compilation errors in console

## Example: Shader Sources for WebGL Fallback

```javascript
// Vertex shader — transforms particle positions to clip space
const VERTEX_SHADER = `
    attribute vec2 aPosition;
    attribute float aSize;
    varying float vAlpha;
    void main() {
        gl_Position = vec4(aPosition * 2.0 - 1.0, 0.0, 1.0);
        gl_PointSize = aSize * gl_PointSize;
        vAlpha = 1.0;
    }
`;

// Fragment shader — soft glowing circle per particle
const FRAGMENT_SHADER = `
    precision mediump float;
    varying vec4 vColor;
    void main() {
        vec2 coord = gl_PointCoord - vec2(0.5);
        float dist = length(coord);
        if (dist > 0.5) discard;
        float alpha = 1.0 - dist * 2.0;
        gl_FragColor = vec4(vColor.rgb, alpha);
    }
`;
```

## Why This Cascade Matters

WebGPU is still experimental in many browsers. Firefox ships WebGPU behind flags only. Safari support is limited. The WebGL fallback ensures your GPU-accelerated rendering works even when WebGPU isn't available — giving you a **smooth experience across all browsers** without the jarring quality drop of CPU-only Canvas2D.
