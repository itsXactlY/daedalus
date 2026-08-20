---
name: webgl-fragment-compute-patterns
description: WebGL fragment compute patterns — using fragment shaders for general-purpose GPU compute when WebGPU is unavailable
category: devops
version: 1.0
tags: [webgl, fragment-shaders, gpu-compute, fallback]
priority: medium
---

# WebGL Fragment Compute Patterns

## Purpose

When WebGPU is not available (older browsers, mobile), use WebGL fragment shaders for general-purpose GPU compute. This is a fallback pattern — WebGPU should be preferred when possible.

## Fragment Shader Compute Pattern

```javascript
// Create framebuffer for compute output
const framebuffer = gl.createFramebuffer();
gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);

// Attach render target texture
const texture = gl.createTexture();
gl.bindTexture(gl.TEXTURE_2D, texture);
gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, W, H, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture);

// Create framebuffer attachment for compute output
const renderbuffer = gl.createRenderbuffer();
gl.bindRenderbuffer(gl.RENDERBUFFER, renderbuffer);
gl.renderbufferStorage(gl.RENDERBUFFER, gl.RGBA4, W, H);
gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.RENDERBUFFER, renderbuffer);

// Set up framebuffer for compute pass
gl.viewport(0, 0, W, H);
gl.clear(gl.COLOR_BUFFER_BIT);
```

## Fragment Shader Compute Code

```glsl
precision mediump float;

uniform float u_data[${N}];    // Input data (1D array)
uniform int u_count;            // Data count

void main() {
    // Calculate thread ID from fragment coordinates
    vec2 uv = gl_FragCoord.xy;
    int idx = int(uv.x + uv.y * ${W});
    
    if (idx >= u_count) return;
    
    // Compute logic — same as any GPU compute
    float result = u_data[idx] * 2.0 + 1.0;
    
    // Output to fragment color (RGBA format)
    gl_FragColor = vec4(result, 0.0, 0.0, 1.0);
}
```

## Vertex Shader Setup

```glsl
attribute vec2 a_position;

void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
```

## JavaScript Orchestration

```javascript
// Step 1: Create shader program
const vertexShader = gl.createShader(gl.VERTEX_SHADER);
gl.shaderSource(vertexShader, vertexShaderSource);
gl.compileShader(vertexShader);

const fragmentShader = gl.createShader(gl.FRAGMENT_SHADER);
gl.shaderSource(fragmentShader, fragmentShaderSource);
gl.compileShader(fragmentShader);

const program = gl.createProgram();
gl.attachShader(program, vertexShader);
gl.attachShader(program, fragmentShader);
gl.linkProgram(program);

// Step 2: Create buffer for vertex positions (full-screen quad)
const quadBuffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, quadBuffer);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1, -1,  // bottom-left
    1, -1,   // bottom-right
    -1, 1,   // top-left
    1, 1     // top-right
]), gl.STATIC_DRAW);

// Step 3: Draw framebuffer for compute pass
gl.useProgram(program);
gl.viewport(0, 0, W, H);
gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

// Step 4: Read back result (RGBA format)
const pixels = new Uint8Array(W * H * 4);
gl.readPixels(pixels, gl.RGBA, gl.UNSIGNED_BYTE);
```

## Pitfalls

1. **Texture size limits**: WebGL textures are typically limited to 2048×2048. For larger datasets, split into multiple passes.

2. **No random access**: Fragment shaders cannot read from arbitrary memory locations — only the texture bound to the framebuffer. Use uniform arrays or texture buffers for input data.

3. **Precision limitations**: WebGL uses `mediump` (16-bit) by default. For full precision, use `highp` — but this may be slower on some GPUs.

4. **No compute shaders**: WebGL doesn't have compute shaders. You must use fragment shaders as a workaround — this means every "compute" operation renders a full-screen quad.

5. **Framebuffer overhead**: Creating and binding framebuffers is expensive. Minimize framebuffer creation by reusing the same framebuffer across multiple compute passes.

## References

- GPGPU.js: Run JavaScript on Your GPU With Zero Shader Knowledge — https://dev.to/thatscalaguy/gpgpujs-run-javascript-on-your-gpu-with-zero-shader-knowledge-569n
- WebGL Fundamentals: Fragment Compute Patterns — https://webgl2fundamentals.com/webgl/fragment-compute.html

## Verification

To verify fragment compute is working:
1. Create a simple identity shader (output = input)
2. Render to framebuffer with known data
3. Read back pixels and compare against input — should be identical
