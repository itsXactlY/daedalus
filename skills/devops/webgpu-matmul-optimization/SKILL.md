---
name: webgpu-matmul-optimization
description: WebGPU matrix multiplication optimization — workgroup tiling, shared memory emulation, achieving 1+ TFLOP throughput on consumer GPUs
category: devops
version: 1.0
tags: [webgpu, matmul, sgemm, gpu-optimization, tflops]
priority: high
---

# WebGPU Matrix Multipilation Optimization

## Purpose

Achieve maximum throughput for matrix multiplication (GEMM/SGEMM) on WebGPU compute shaders. The key technique is workgroup-level tiling with shared memory emulation via uniform buffers, reducing global memory bandwidth pressure by 10-50x compared to naive matmul.

## Naive vs Optimized Pattern

### Naive (unoptimized)
```wgsl
@compute @workgroup_size(32, 32, 1)
fn main(
    @global const a: array<f32>,
    @global const b: array<f32>,
    @global const c: array<f32>
) {
    let row = @builtin(workgroup_id_y);
    let col = @builtin(workgroup_id_x);
    let idx = @builtin(global_invocation_id);
    
    var sum = 0.0f;
    for (let k = 0u; k < K; k++) {
        sum += a[row * K + k] * b[k * N + col];
    }
    c[idx.y * N + idx.x] = sum;
}
```

This reads every element from global memory. For a 1024×1024 matmul, each thread reads 1024 elements from A and 1024 from B → 2048 global memory accesses per thread. With 32×32 workgroups = 32768 threads → ~67 million global loads.

### Optimized (tiling + shared memory emulation)
```wgsl
@compute @workgroup_size(16, 16, 1)
fn main(
    @global const a: array<f32>,
    @global const b: array<f32>,
    @global const c: array<f32>,
    @uniform constant tile_a: array<f32>,  // shared memory emulation
    @uniform constant tile_b: array<f32>   // shared memory emulation
) {
    let row = @builtin(workgroup_id_y);
    let col = @builtin(workgroup_id_x);
    
    var sum = 0.0f;
    
    // Tiled matmul loop
    for (let tile_k = 0u; tile_k < K; tile_k += TILE_SIZE) {
        // Load tile into shared memory (emulated via uniform buffer)
        let local_row = @builtin(local_invocation_id_y);
        let local_col = @builtin(local_invocation_id_x);
        
        // Tile A load — row of workgroup, all columns
        tile_a[local_row * TILE_SIZE + local_col] = 
            a[row * K + tile_k + local_col];
        
        // Tile B load — column of workgroup, all rows
        tile_b[local_row * TILE_SIZE + local_col] = 
            b[(tile_k + local_row) * N + col];
        
        // Sync (uniform buffer acts as barrier)
        var dummy: u32 = 1u;
        let old = atomicAdd(&dummy, 0u);
        
        // Compute partial sum using tile data
        for (let k = 0u; k < TILE_SIZE; k++) {
            sum += tile_a[local_row * TILE_SIZE + k] * 
                   tile_b[k * TILE_SIZE + local_col];
        }
    }
    
    c[row * N + col] = sum;
}
```

## Workgroup Tiling Strategy

| Tile Size | Workgroup | Best For | Notes |
|-----------|-----------|----------|-------|
| 8×8 | 8×8 | Small matrices | Minimal shared memory pressure |
| 16×16 | 16×16 | Medium matrices (512-2048) | Sweet spot for most GPUs |
| 32×32 | 32×32 | Large matrices (2048+) | Requires careful register management |

## Cross-Vendor Optimization

### NVIDIA
- Favors larger workgroups (32×32 or 64×1)
- Excellent warp-level primitives — use `@builtin(nv_warp_id)` for intra-warp communication
- Register pressure is less of a concern; can use more shared memory

### Apple/Metal
- Prefers smaller tiles (8×8 or 16×16)
- Strong L1 cache; uniform buffer emulation works well
- Avoid excessive loop unrolling — Metal compiler handles it better

### Intel
- Requires explicit cache hints via `@builtin(cache_hint)`
- Smaller workgroups (16×16) perform best
- Register pressure is severe; keep tile sizes small

## Performance Targets

| Matrix Size | Workgroup | Expected TFLOP | Notes |
|-------------|-----------|----------------|-------|
| 256×256 | 16×16 | ~0.5 TFLOP | Warmup + overhead dominates |
| 512×512 | 16×16 | ~1.0 TFLOP | Sweet spot for consumer GPUs |
| 1024×1024 | 32×32 | ~1.5 TFLOP | Register pressure increases |
| 2048×2048 | 32×32 | ~2.0 TFLOP | Bandwidth-bound; consider A64X format |

## Pitfalls

1. **Uniform buffer limits**: WebGPU has a 64KB uniform buffer limit per dispatch. For large tiles, split into multiple uniform buffers or use storage buffers.

2. **Register pressure**: Each thread holds `TILE_SIZE` values in registers. For 32×32 tiles with f32 data, that's 1024 × 4 bytes = 4KB per thread — exceeds register limits on most GPUs. Use smaller tiles or split the accumulation loop.

3. **Workgroup size must divide matrix dimensions**: If your matrix is 1000×1000 and you use 16×16 workgroups, the last tile won't align. Add a boundary check:
   ```wgsl
   if (local_row >= N || local_col >= K) { return; }
   ```

4. **Loop unrolling**: Don't manually unroll — the WGSL compiler handles it better. Instead, use `@builtin(workgroup_uniform_id)` to partition the loop across workgroups.

## References

- Nuss & Bolts: Optimizing a WebGPU Matmul Kernel for 1TFLOP+ Performance — https://www.nuss-and-bolts.com/p/optimizing-a-webgpu-matmul-kernel
- Ahmed5720/Fast-WebGPU-SGEMM — https://github.com/Ahmed5720/Fast-WebGPU-SGEMM
- ggml-webgpu PR #22241 (llama.cpp matmul tuning) — https://github.com/ggml-org/llama.cpp/pull/22241

## Verification

To verify optimization is working:
1. Profile GPU compute time before and after tiling — expect 5-20x reduction
2. Check register usage in browser dev tools — should be < 64 regs per thread
3. Compare against CPU matmul — WebGPU should be 10-50x faster for matrices > 512×512
