---
name: webgl-simd-typed-arrays
description: WebGL/SIMD typed arrays — Float32Array to GPU buffer mapping, vectorized operations via fragment compute patterns
category: devops
version: 1.0
tags: [webgl, simd, typed-arrays, float32array, gpu-mapping]
priority: medium
---

# WebGL/SIMD Typed Arrays

## Purpose

Map JavaScript typed arrays (Float32Array, Float16Array) directly to GPU buffers for vectorized operations. This is the foundation of all WebGPU/WebGL compute — without proper buffer mapping, you cannot efficiently transfer data between JS and GPU.

## Buffer Mapping Pattern

```javascript
// Step 1: Create typed array in JS
const dataSize = 1024 * 4; // 1024 floats × 4 bytes each
const gpuBuffer = new Float32Array(dataSize);

// Fill with data
for (let i = 0; i < 1024; i++) {
    gpuBuffer[i] = Math.sin(i * 0.01) * 100.0f;
}

// Step 2: Create GPU buffer with correct usage flags
const gpuDeviceBuffer = device.createBuffer({
    size: dataSize,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

// Step 3: Upload to GPU
device.queue.writeBuffer(gpuDeviceBuffer, 0, gpuBuffer.buffer);

// Step 4: Bind in shader
const bindGroup = device.createBindGroup({
    entries: [
        { binding: 0, resource: gpuDeviceBuffer },
    ],
});
```

## Shader Binding (WGSL)

```wgsl
@compute @workgroup_size(256, 1, 1)
fn main(
    @global const input: array<f32>,   // Bound from JS Float32Array
    @global var output: array<f32>     // Bound from JS Float32Array
) {
    let gid = @builtin(global_invocation_id);
    
    // Boundary check
    if (gid.x >= N) { return; }
    
    // Vectorized operation — SIMD pattern
    output[gid.x] = input[gid.x] * 2.0f + 1.0f;
}
```

## Float16Array for Memory Efficiency

```javascript
// Use Float16Array to halve memory bandwidth (half precision)
const halfDataSize = 1024 * 2; // 1024 floats × 2 bytes each
const gpuBuffer16 = device.createBuffer({
    size: halfDataSize,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

device.queue.writeBuffer(gpuBuffer16, 0, new Float16Array(halfDataSize).buffer);
```

**When to use Float16:**
- Neural network weights (precision loss is acceptable)
- Particle positions (position data doesn't need full precision)
- Normal vectors (direction data needs only 2 significant digits)

**When NOT to use Float16:**
- Accumulated sums (precision loss compounds)
- Physics simulations (small errors compound over time)
- Color data (visible banding in gradients)

## Fragment Compute Pattern (WebGL Fallback)

If WebGPU is not available, use fragment shaders for compute:

```javascript
// WebGL fragment shader compute pattern
const vertexShaderSource = `
    attribute vec2 a_position;
    void main() {
        gl_Position = vec4(a_position, 0.0, 1.0);
    }
`;

const fragmentShaderSource = `
    precision mediump float;
    uniform float u_data[${N}];
    uniform int u_count;
    
    void main() {
        int idx = gl_FragCoord.x + gl_FragCoord.y * ${W};
        if (idx >= u_count) return;
        
        vec4 color = vec4(u_data[idx] * 2.0, 0.0, 0.0, 1.0);
        gl_FragColor = color;
    }
`;
```

## GPGPU.js Pattern (Zero Shader Knowledge)

GPGPU.js allows GPU compute without writing shaders:

```javascript
// GPGPU.js — run JS on GPU with zero shader knowledge
const gpuProcess = new GPU.Process({
    // No shader code needed!
    textureSize: [W, H],
});

gpuProcess.addFunction(
    function() {
        var sum = 0;
        for (var i = 0; i < N; i++) {
            sum += this.data[i];
        }
        return sum;
    },
    {
        settings: {
            context: 'true',
            singlePrecision: true,
        },
        parameters: {
            width: W,
            height: H,
        },
    },
);

const gpuCompute = gpuProcess.compile();
gpuCompute.texture(dataTexture);
```

## Pitfalls

1. **Buffer alignment**: GPU buffers must be aligned to 16 bytes. If your data size isn't a multiple of 16, pad it:
   ```javascript
   const paddedSize = Math.ceil(dataSize / 16) * 16;
   const gpuBuffer = device.createBuffer({ size: paddedSize });
   ```

2. **Float32Array.byteLength**: A Float32Array of N elements has `N × 4` bytes. Make sure your GPU buffer size matches exactly.

3. **writeBuffer requires ArrayBuffer**: `device.queue.writeBuffer(buffer, offset, array.buffer)` — use `.buffer` to get the underlying ArrayBuffer.

4. **WebGL fallback limitations**: Fragment compute is limited by texture dimensions (typically 2048×2048) and cannot write to arbitrary memory locations. Use WebGPU for general-purpose compute.

## References

- GPGPU.js: Run JavaScript on Your GPU With Zero Shader Knowledge — https://dev.to/thatscalaguy/gpgpujs-run-javascript-on-your-gpu-with-zero-shader-knowledge-569n
- W3C WGSL Spec — https://www.w3.org/TR/2025/CRD-WGSL-20250603/

## Verification

To verify typed array mapping:
1. Create a Float32Array with known values
2. Upload to GPU buffer via `writeBuffer`
3. Dispatch a compute shader that returns the values unchanged
4. Read back output buffer and compare — should be identical
