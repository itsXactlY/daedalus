---
name: webgpu-compute-shader-basics
description: WebGPU compute shader fundamentals — WGSL structure, buffer binding, workgroup configuration, compute pass setup
category: devops
version: 1.0
tags: [webgpu, wgsl, compute-shaders, fundamentals]
priority: high
---

# WebGPU Compute Shader Basics

## Purpose

Foundational patterns for writing WebGPU compute shaders in WGSL. Covers buffer binding, workgroup sizing, compute pass structure, and common pitfalls.

## Compute Pass Structure

```javascript
// Step 1: Create compute pipeline
const pipeline = device.createComputePipeline({
    label: 'my-compute-pipeline',
    layout: 'auto',
    module: shaderModule,
    vertex: { source: '' },  // No vertex shader needed for compute
});

// Step 2: Create bind group (binds buffers to shader)
const bindGroup = device.createBindGroup({
    label: 'compute-bind-group',
    layout: pipeline.getBindGroupLayout(0),
    entries: [
        { binding: 0, resource: inputBuffer },   // @group(0) @binding(0)
        { binding: 1, resource: outputBuffer },  // @group(0) @binding(1)
    ],
});

// Step 3: Encode compute pass
const commandEncoder = device.createCommandEncoder();
const computePass = commandEncoder.beginComputePass();
computePass.setPipeline(pipeline);
computePass.setBindGroup(0, bindGroup);

// Dispatch workgroups
computePass.dispatchWorkgroups(workgroupX, workgroupY, workgroupZ);

computePass.end();

// Step 4: Submit to GPU queue
device.queue.submit([commandEncoder.finish()]);
```

## WGSL Compute Shader Template

```wgsl
@compute @workgroup_size(X, Y, Z)
fn main(
    @global const input: array<f32>,      // @group(0) @binding(0)
    @global var output: array<f32>        // @group(0) @binding(1)
) {
    let gid = @builtin(global_invocation_id);
    let wgid = @builtin(workgroup_id);
    let lid = @builtin(local_invocation_id);
    let localSize = @builtin(num_workgroups);
    
    // Boundary check
    if (gid.x >= N || gid.y >= M) { return; }
    
    // Compute logic
    let idx = gid.y * N + gid.x;
    output[idx] = input[idx] * 2.0f;
}
```

## Workgroup Sizing Patterns

| Pattern | When to Use | Example |
|---------|-------------|---------|
| `@workgroup_size(1, 1, 1)` | Single-threaded compute | Hash functions, atomic operations |
| `@workgroup_size(N, 1, 1)` | 1D data parallel | Array transforms, vector ops |
| `@workgroup_size(sqrt(N), sqrt(N), 1)` | 2D grid | Image processing, matrix ops |
| `@workgroup_size(8, 8, 1)` | Small tile compute | Matmul tiles, particle systems |

**Rule**: Workgroup dimensions should divide evenly into your data dimensions. If you have 1000 elements and use workgroups of size 32, the last workgroup will have 4 unused threads — add a boundary check.

## Buffer Binding Patterns

### Storage Buffers (read/write)
```wgsl
@global const input: array<f32>    // Read-only storage
@global var output: array<f32>     // Read-write storage
```

### Uniform Buffers (constant data)
```wgsl
@uniform constant config: MyConfig  // < 64KB, immutable per dispatch
```

### Storage Textures (for image-like data)
```wgsl
@texture_read_only input_tex: texture<32float>  // Read-only texture
@texture_storage rgba32float output_tex          // Write storage texture
```

## Pitfalls

1. **Workgroup size limit**: Maximum workgroup size is 256 × 256 × 256 on most GPUs. On Apple/Metal, the limit is 1024 total threads per workgroup.

2. **Buffer alignment**: Buffers must be aligned to 16 bytes (GPU buffer alignment). Use `createBuffer({ size: N * 4, usage: GPUBufferUsage.STORAGE })` where N is rounded up to multiples of 4.

3. **Dispatch dimensions**: `dispatchWorkgroups(x, y, z)` uses workgroup counts, not thread counts. A 16×16 workgroup with dispatch(8, 8, 1) produces 8 × 8 = 64 workgroups × 256 threads = 16384 total threads.

4. **No vertex shader needed**: Compute shaders don't need a vertex shader. Set `vertex: { source: '' }` in the pipeline creation to avoid errors.

5. **Shader module compilation**: WGSL is compiled at runtime by the browser. Check for compilation errors via `navigator.gpu.requestAdapter()` and `device.queue.onSubmittedWorkDone()`.

## References

- WebGPU Fundamentals: Compute Shader Basics — https://webgpufundamentals.org/webgpu/lessons/webgpu-compute-shaders.html
- Chrome Dev: Get Started with GPU Compute — https://developer.chrome.com/docs/capabilities/web-apis/gpu-compute
- W3C WGSL Spec CRD — https://www.w3.org/TR/2025/CRD-WGSL-20250603/

## Verification

To verify compute shaders are working:
1. Create a simple identity shader (output = input)
2. Dispatch with known workgroup sizes
3. Read back output buffer and compare against input — should be identical
