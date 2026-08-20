---
name: wgsl-compute-shader-patterns
description: WGSL compute shader patterns — workgroup sizing, builtin functions, memory models, and common pitfalls
category: devops
version: 1.0
tags: [wgsl, compute-shaders, builtin-functions, memory-model]
priority: high
---

# WGSL Compute Shader Patterns

## Purpose

Best practices for writing WGSL compute shaders. Covers workgroup sizing, builtin function usage, memory model semantics, and common pitfalls.

## Workgroup Sizing Rules

### Rule 1: Dimensions must divide data evenly
```wgsl
// BAD — 1000 elements / 32 threads = 31 remainder
@workgroup_size(32, 1, 1)
fn main() {
    let gid = @builtin(global_invocation_id);
    if (gid.x >= N) return; // Wasted thread cycles
}

// GOOD — boundary check handles remainder
@workgroup_size(32, 1, 1)
fn main() {
    let gid = @builtin(global_invocation_id);
    if (gid.x >= N) return; // Correct but inefficient for last workgroup
}
```

### Rule 2: Workgroup size limit is 256×256×256 total threads
- Maximum per dimension: 256
- Maximum total threads: 256 × 256 × 256 = 16,777,216
- Practical limit: Most GPUs cap at 256 threads per workgroup

### Rule 3: Thread coalescing matters
```wgsl
// GOOD — contiguous memory access pattern
@workgroup_size(256, 1, 1)
fn main() {
    let gid = @builtin(global_invocation_id);
    // Each thread accesses consecutive elements
    output[gid.x] = input[gid.x] * 2.0f;
}

// BAD — strided access pattern (cache misses)
@workgroup_size(16, 16, 1)
fn main() {
    let gid = @builtin(global_invocation_id);
    // Threads access elements with stride = workgroup size
    output[gid.y * N + gid.x] = input[gid.y * N + gid.x]; // Strided access
}
```

## Builtin Function Reference

| Builtin | Meaning | Example |
|---------|---------|---------|
| `@builtin(global_invocation_id)` | Thread ID in grid | `let gid = @builtin(global_invocation_id);` |
| `@builtin(workgroup_id)` | Workgroup ID in grid | `let wgid = @builtin(workgroup_id);` |
| `@builtin(local_invocation_id)` | Thread ID within workgroup | `let lid = @builtin(local_invocation_id);` |
| `@builtin(num_workgroups)` | Total workgroups in grid | `let totalWGs = @builtin(num_workgroups);` |
| `@builtin(workgroup_uniform_id)` | Workgroup uniform ID | `let uid = @builtin(workgroup_uniform_id);` |

## Memory Model Semantics

### Global Memory (shader storage)
```wgsl
@global const input: array<f32>    // Read-only, cached by GPU
@global var output: array<f32>     // Read-write, write-optimized
```

### Uniform Memory (constant data)
```wgsl
@uniform constant config: MyConfig  // Immutable per dispatch, < 64KB
```

### Workgroup Memory (shared between threads in workgroup)
```wgsl
@workgroup var shared_data: array<f32, 16>; // Shared memory within workgroup
```

## Common Patterns

### Pattern 1: Parallel reduction (sum all elements)
```wgsl
@compute @workgroup_size(256, 1, 1)
fn main(
    @global const input: array<f32>,
    @global var output: array<f32>
) {
    let gid = @builtin(global_invocation_id);
    
    // Partial sum within workgroup
    var partial_sum: f32 = 0.0f;
    for (let i = 0u; i < N; i += 256u) {
        if (gid.x + i < N) {
            partial_sum += input[gid.x + i];
        }
    }
    
    // Reduce across workgroups (requires multiple passes)
    output[0] = partial_sum;
}
```

### Pattern 2: Matrix transpose
```wgsl
@compute @workgroup_size(16, 16, 1)
fn main(
    @global const input: array<f32>,
    @global var output: array<f32>
) {
    let gid = @builtin(global_invocation_id);
    let local = @builtin(local_invocation_id);
    
    // Transpose within workgroup tile
    for (let row = 0u; row < 16u; row++) {
        for (let col = 0u; col < 16u; col++) {
            output[(local.y * 16 + local.x) * N + (row * 16 + col)] = 
                input[(row * 16 + col) * N + (local.y * 16 + local.x)];
        }
    }
}
```

### Pattern 3: Atomic operations (counting, incrementing)
```wgsl
@compute @workgroup_size(256, 1, 1)
fn main(
    @global const input: array<f32>,
    @global var output: array<f32>
) {
    let gid = @builtin(global_invocation_id);
    
    // Atomic add to shared counter
    let counter = @subgroup_function_atomic_add(&output[0], 1u);
}
```

## Pitfalls

1. **No implicit synchronization**: Workgroups execute independently. If you need thread-level synchronization, use `@subgroup_function_*` builtins explicitly.

2. **Memory model is volatile**: GPU memory can be reordered by the compiler. Use `@subgroup_function_barrier()` for explicit barriers.

3. **Workgroup uniform limits**: Maximum 64KB per dispatch for uniform buffers. For larger data, use storage buffers.

4. **Builtin function types**: All builtins return u32 (unsigned int). If you need f32, cast explicitly: `let gid_f32 = @builtin(global_invocation_id) as f32;`

## References

- W3C WGSL Spec CRD — https://www.w3.org/TR/2025/CRD-WGSL-20250603/
- WebGPU Compute Shader Basics — https://webgpufundamentals.org/webgpu/lessons/webgpu-compute-shaders.html

## Verification

To verify WGSL patterns are correct:
1. Write a simple identity shader (output = input)
2. Dispatch with known workgroup sizes
3. Read back output buffer and compare against input — should be identical
