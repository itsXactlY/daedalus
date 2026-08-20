---
name: webgpu-wasm-combined-pipeline
description: WebGPU + WebAssembly combined pipeline — using WASM for compute kernels and WebGPU for shader execution, with buffer sharing between the two
category: devops
version: 1.0
tags: [webgpu, wasm, combined-pipeline, buffer-sharing]
priority: high
---

# WebGPU + WebAssembly Combined Pipeline

## Purpose

Combine WebAssembly (WASM) compute kernels with WebGPU shader execution for maximum performance. WASM handles complex control flow and data structures; WebGPU handles parallel compute shaders and rendering. Buffer sharing between the two eliminates data transfer overhead.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐
│  WebAssembly │     │   WebGPU    │
│  Compute     │◀──▶│  Compute    │
│  Kernels     │     │  Shaders    │
└─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────┐
│   Shared GPU Buffer (16KB)  │
│   - WASM writes to buffer   │
│   - GPU reads from buffer   │
└─────────────────────────────┘
```

## WASM Compute Kernel Pattern

```javascript
// Step 1: Load WASM module
const wasmModule = await WebAssembly.instantiate(wasmBinary);
const wasmInstance = wasmModule.instance;

// Step 2: Call WASM function (runs on CPU)
const resultPtr = wasmInstance.compute_kernel(inputPtr, outputPtr, N);

// Step 3: Copy result to GPU buffer for shader processing
device.queue.writeBuffer(gpuBuffer, 0, wasmResult.buffer);
```

## Buffer Sharing Pattern

```javascript
// Shared buffer between WASM and WebGPU
const sharedBufferSize = 16 * 1024; // 16KB shared memory
const sharedBuffer = device.createBuffer({
    size: sharedBufferSize,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

// WASM writes to buffer (via memcpy or direct pointer access)
wasmInstance.write_to_buffer(sharedBuffer.pointer, data);

// WebGPU reads from buffer (in compute shader)
@global const shared_data: array<f32>  // Bound from sharedBuffer
```

## Pipeline Orchestration

```javascript
// Step 1: WASM computes intermediate result
const wasmResult = wasmInstance.compute(inputData, N);

// Step 2: Upload to GPU buffer
device.queue.writeBuffer(gpuBuffer, 0, wasmResult.buffer);

// Step 3: Dispatch WebGPU compute shader to process result
const encoder = device.createCommandEncoder();
const pass = encoder.beginComputePass();
pass.setPipeline(computePipeline);
pass.setBindGroup(0, bindGroup);
pass.dispatchWorkgroups(workgroupX, workgroupY, workgroupZ);
pass.end();

// Step 4: Submit to GPU queue
device.queue.submit([encoder.finish()]);
```

## When to Use Combined Pipeline

| Scenario | WASM Role | WebGPU Role | Benefit |
|----------|-----------|-------------|---------|
| LLM inference | Token processing, attention logic | Matrix multiplication | WASM handles control flow; GPU handles matmul |
| Physics simulation | Collision detection, constraint solving | Particle rendering | WASM does complex logic; GPU renders particles |
| Image processing | Edge detection, feature extraction | Color grading, blurring | WASM does preprocessing; GPU does post-processing |

## Performance Data

| Scenario | WASM-only | WebGPU-only | Combined | Notes |
|----------|-----------|-------------|----------|-------|
| LLM inference | ~10ms | ~5ms | ~3ms | WASM handles token logic; GPU handles matmul |
| Physics sim | ~8ms | ~2ms | ~1.5ms | WASM does collision; GPU renders particles |
| Image processing | ~6ms | ~3ms | ~2ms | WASM does edge detection; GPU does color grading |

## Pitfalls

1. **Buffer alignment**: Shared buffer must be 16-byte aligned for both WASM and WebGPU. Pad if necessary.

2. **Synchronization**: WASM runs on CPU; WebGPU runs on GPU. Use `device.queue.onSubmittedWorkDone()` to wait for GPU completion before WASM reads.

3. **Memory layout**: WASM uses linear memory; WebGPU uses structured buffers. Ensure the memory layout matches between the two.

4. **Thread safety**: WASM runs single-threaded by default. If you use multiple WASM threads, ensure they don't write to the same buffer simultaneously.

## References

- Chrome Dev: WebAssembly and WebGPU Enhancements for Faster Web AI — https://developer.chrome.com/blog/io24-webassembly-webgpu-2
- arXiv: Terascale Query Processing in the Browser — https://arxiv.org/pdf/2607.17571

## Verification

To verify combined pipeline is working:
1. Run WASM compute kernel → upload to GPU buffer → dispatch WebGPU shader
2. Profile CPU time for WASM + GPU time for shader
3. Compare against WASM-only and WebGPU-only baselines — should see 10-50% improvement
