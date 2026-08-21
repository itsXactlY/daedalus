---
name: webgpu-dispatch-overhead-reduction
description: WebGPU dispatch overhead reduction — measuring, characterizing, and eliminating CPU-GPU synchronization costs for LLM inference and batched compute
category: devops
version: 1.0
tags: [webgpu, dispatch-overhead, cpu-gpu-sync, llm-inference]
priority: high
---

# WebGPU Dispatch Overhead Reduction

## Purpose

WebGPU has significant CPU-GPU synchronization overhead per dispatch call. For LLM inference (32+ layers) and batched compute (100+ kernels), this overhead dominates actual GPU compute time. This skill documents measurement techniques and reduction strategies.

## The Problem

Each `dispatchWorkgroups()` call requires:
1. CPU command buffer submission
2. GPU driver validation
3. Command queue serialization
4. GPU scheduler scheduling

Total overhead per dispatch: ~50-200μs depending on GPU vendor.

For a 7B parameter LLM with 32 layers, each requiring one dispatch → 32 × 100μs = 3.2ms of pure overhead. On a fast GPU where compute takes 10ms total, that's 32% overhead.

## Measurement Technique

```javascript
// Measure dispatch overhead empirically
const N = 100; // Number of dispatches to test
const timings = [];

for (let i = 0; i < N; i++) {
    const start = performance.now();
    
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginComputePass();
    pass.setPipeline(computePipeline);
    pass.setBindGroup(0, bindGroup);
    pass.dispatchWorkgroups(1, 1, 1);
    pass.end();
    
    device.queue.submit([encoder.finish()]);
    
    // Wait for completion
    const end = performance.now();
    timings.push(end - start);
}

const avgOverhead = timings.reduce((a, b) => a + b, 0) / N;
console.log(`Average dispatch overhead: ${avgOverhead.toFixed(2)}ms`);
```

## Reduction Strategies

### Strategy 1: Indirect Dispatch (Best for batched kernels)

```javascript
// Batch 100 dispatches into 1 indirect call
const indirectBuffer = device.createBuffer({
    size: 100 * 12, // 12 bytes per dispatch command
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

const encoder = device.createCommandEncoder();
const pass = encoder.beginComputePass();
pass.setPipeline(computePipeline);
pass.setBindGroup(0, bindGroup);
pass.dispatchWorkgroupsIndirect(indirectBuffer, 0, 100); // One call!
pass.end();
```

**Reduction**: 100 dispatches → 1 indirect call. Overhead: 100 × 100μs → ~50μs = **99.5% reduction**.

### Strategy 2: Command Buffer Batching (Best for mixed workloads)

```javascript
// Batch multiple different pipelines into one command buffer
const encoder = device.createCommandEncoder();

// Pipeline A — compute shader
const passA = encoder.beginComputePass();
passA.setPipeline(computePipelineA);
passA.dispatchWorkgroups(10, 10, 1);
passA.end();

// Pipeline B — render pass
const renderPass = encoder.beginRenderPass({ ... });
renderPass.setPipeline(renderPipelineB);
renderPass.draw(...);
renderPass.end();

// Pipeline C — compute shader
const passC = encoder.beginComputePass();
passC.setPipeline(computePipelineC);
passC.dispatchWorkgroups(5, 5, 1);
passC.end();

device.queue.submit([encoder.finish()]); // One submit!
```

**Reduction**: Multiple dispatches across different pipelines batched into single GPU submission. Overhead: N × 50μs → ~50μs = **~(N-1)/N reduction**.

### Strategy 3: Workgroup Size Optimization (Best for small kernels)

```wgsl
// Instead of dispatching 100 workgroups of size 1×1×1:
// pass.dispatchWorkgroups(100, 1, 1);

// Dispatch 1 workgroup of size 100×1×1:
pass.dispatchWorkgroups(1, 1, 1); // One call, 100 threads inside
```

**Reduction**: Reduces dispatch count from N to 1. Overhead: N × 50μs → ~50μs = **~(N-1)/N reduction**.

## Vendor-Specific Overhead Data

| Vendor | Dispatch Overhead | Best Reduction Strategy | Notes |
|--------|-------------------|------------------------|-------|
| NVIDIA | ~50μs | Indirect dispatch | Excellent for large batches |
| AMD | ~80μs | Command buffer batching | Less efficient indirect dispatch |
| Intel | ~120μs | Workgroup size optimization | Highest overhead — batch aggressively |
| Apple | ~30μs | Any strategy | Lowest overhead — less critical |

## LLM Inference Pattern

```javascript
// Layer-by-layer inference with indirect dispatch
const layerCount = 32; // For a 7B model
const indirectBuffer = device.createBuffer({
    size: layerCount * 12,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

// Fill indirect buffer with per-layer dispatch commands
for (let layer = 0; layer < layerCount; layer++) {
    const offset = layer * 12;
    // Set workgroup dimensions for this layer's compute
    indirectBuffer.setUint32(offset + 0, workgroupX[layer], true);
    indirectBuffer.setUint32(offset + 4, workgroupY[layer], true);
    indirectBuffer.setUint32(offset + 8, 1, true); // Z = 1
}

// Single dispatch call for all layers!
pass.dispatchWorkgroupsIndirect(indirectBuffer, 0, layerCount);
```

## Pitfalls

1. **Indirect buffer size**: Must be exactly `count × 12` bytes. If you miscalculate, the GPU will execute undefined behavior.

2. **Command buffer lifetime**: The indirect buffer must remain valid until the command encoder finishes. Do not write to it while the GPU is executing.

3. **Vendor differences**: Intel has the highest dispatch overhead (~120μs) — indirect dispatch is most critical here. Apple has the lowest (~30μs) — less critical but still beneficial.

4. **Workgroup size limits**: If you batch 100 workgroups into one indirect call, the GPU scheduler may struggle with thread coalescing. Test across vendors.

## References

- arXiv: Measuring and Reducing WebGPU Dispatch Overhead for LLM Inference — https://arxiv.org/html/2608.08730v1
- arXiv: Characterizing WebGPU Dispatch Overhead for LLM Inference Across Four GPU Vendors — https://arxiv.org/html/2604.02344

## Verification

To verify overhead reduction:
1. Measure dispatch time before and after indirect dispatch
2. Compare against CPU matmul baseline — WebGPU should be 10-50x faster
3. Profile GPU utilization — should see higher occupancy with indirect dispatch
