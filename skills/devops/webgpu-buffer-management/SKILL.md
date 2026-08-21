---
name: webgpu-buffer-management
description: WebGPU buffer management — storage buffers, uniform buffers, staging buffers, and correct usage flags for compute pipelines
category: devops
version: 1.0
tags: [webgpu, buffers, gpu-memory, compute-pipelines]
priority: high
---

# WebGPU Buffer Management

## Purpose

Correct buffer creation, binding, and lifecycle management in WebGPU compute pipelines. Covers storage buffers, uniform buffers, staging buffers, and usage flags.

## Buffer Usage Flags

| Flag | Meaning | When to Use |
|------|---------|-------------|
| `STORAGE` | Read/write from shader | Compute output, GPU-only data |
| `COPY_SRC` | Source for copy operations | Staging buffer → device buffer upload |
| `COPY_DST` | Destination for copy operations | Receiving data from CPU |
| `UNIFORM` | Constant data in shader | Configuration, small arrays (< 64KB) |
| `INDEX` | Index buffer for rendering | Not used in compute |
| `VERTEX` | Vertex attribute buffer | Not used in compute |

## Storage Buffer Pattern (GPU Read/Write)

```javascript
// Create storage buffer for compute shader read/write
const bufferSize = 1024 * 4; // 1024 floats × 4 bytes
const storageBuffer = device.createBuffer({
    size: bufferSize,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

// Bind in shader
@global const input: array<f32>   // @group(0) @binding(0)
@global var output: array<f32>    // @group(0) @binding(1)
```

## Uniform Buffer Pattern (Constant Data)

```javascript
// Uniform buffers are immutable per dispatch — great for config data
const configData = new Uint8Array([
    0x01, 0x00, 0x00, 0x00, // workgroupX = 1
    0x00, 0x00, 0x00, 0x00, // workgroupY = 0
    0x00, 0x00, 0x00, 0x00, // workgroupZ = 0
]);

const uniformBuffer = device.createBuffer({
    size: configData.length,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
});

device.queue.writeBuffer(uniformBuffer, 0, configData);

// Bind in shader
@uniform constant config: MyConfig  // @group(0) @binding(1)
```

## Staging Buffer Pattern (CPU → GPU Upload)

```javascript
// Step 1: Create staging buffer (CPU writable)
const stagingBuffer = device.createBuffer({
    size: dataSize,
    usage: GPUBufferUsage.COPY_SRC,
});

// Step 2: Write CPU data to staging buffer
stagingBuffer.writeFrom(cpuData); // cpuData is ArrayBuffer or TypedArray

// Step 3: Create destination buffer (GPU storage)
const gpuBuffer = device.createBuffer({
    size: dataSize,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

// Step 4: Copy staging → GPU buffer in command encoder
const encoder = device.createCommandEncoder();
encoder.copyBufferToBuffer(stagingBuffer, 0, gpuBuffer, 0);
device.queue.submit([encoder.finish()]);
```

## Bind Group Pattern

```javascript
// Create bind group to link buffers to shader bindings
const bindGroup = device.createBindGroup({
    label: 'compute-bind-group',
    layout: pipeline.getBindGroupLayout(0),
    entries: [
        { binding: 0, resource: inputBuffer },     // @group(0) @binding(0)
        { binding: 1, resource: outputBuffer },    // @group(0) @binding(1)
        { binding: 2, resource: configBuffer },    // @group(0) @binding(2)
    ],
});

// Use in compute pass
const pass = encoder.beginComputePass();
pass.setPipeline(computePipeline);
pass.setBindGroup(0, bindGroup); // Only ONE bind group per dispatch
pass.dispatchWorkgroups(workgroupX, workgroupY, workgroupZ);
pass.end();
```

## Pitfalls

1. **Single bind group per dispatch**: WebGPU allows only one bind group per dispatch call. If you need multiple buffers, combine them into a single buffer or use multiple bind groups with separate pipelines.

2. **Buffer alignment**: Buffers must be 16-byte aligned. If your data size isn't a multiple of 16, pad it:
   ```javascript
   const paddedSize = Math.ceil(dataSize / 16) * 16;
   ```

3. **Usage flags are additive**: You can combine flags with `|` (bitwise OR). A buffer with `STORAGE | COPY_DST` can be both written by the shader and copied from CPU.

4. **Uniform buffer size limit**: WebGPU uniform buffers are limited to 64KB per dispatch. For larger data, use storage buffers.

5. **Staging buffer lifecycle**: Staging buffers are temporary — create them, copy to GPU, then discard. Don't keep staging buffers around; they waste memory.

## References

- MDN: GPUBufferUsage documentation — https://developer.mozilla.org/en-US/docs/Web/API/GPUBufferUsage
- WebGPU Fundamentals: Buffer Management — https://webgpufundamentals.org/webgpu/lessons/webgpu-buffers.html

## Verification

To verify buffer management is correct:
1. Create a simple compute shader that reads from input buffer and writes to output buffer
2. Upload data via staging buffer pattern
3. Dispatch compute and read back output — should match expected values
