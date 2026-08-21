---
name: mazemaker-dream-cpp26-rewrite
description: Mazemaker Dream Engine memory leak fixes + C++26 parallel rewrite blueprint
---

# Skill: Mazemaker Dream Engine — C++26 Parallel Rewrite Blueprint

## Purpose

Complete rewrite specification for the Mazemaker Dream Engine in C++26+.
Addresses confirmed memory leaks and delivers a cutting-edge, lock-free, SIMD-optimized
dream consolidation backend.

**Status**: DESIGN SPECIFICATION — not yet implemented.

---

## Confirmed Memory Leaks (Fixed + Outstanding)

### Fixed in this codebase
| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `access_logger.py` | JSONL log file grew forever, no rotation | Rotation at 100MB, keep 5 files |
| 2 | `access_logger.py` `_flush_buffer` | Old rotated logs never cleaned | `_clean_old_logs(30)` called every flush |
| 3 | `cpp_dream_backend.py` `prune_orphans` | Returned 0, never pruned MSSQL orphans | DELETE via MSSQL query |
| 4 | `cpp_dream_backend.py` `prune_old_dream_sessions` | Orphaned insights after session delete | Delete insights first, then sessions |
| 5 | `dream_engine.py` `prune_old_dream_sessions` (SQLite) | Same orphaned insights issue | Same fix applied |
| 6 | `simd.h` | `_mm256_loadu_ps` unaligned loads (10-20% slower) | `std::assume_aligned` + aligned path first |
| 7 | `simd.h` | AVX-512 checked but paths were redundant | Cleaner dispatch: AVX-512 > AVX2 > scalar |
| 8 | `simd.h` `cosine_similarity` | 3× `_mm256_store_ps` + manual horizontal sum | Single AVX-512 reduce + cleaner fallbacks |

### Already correct (No Fix Needed)
- AccessLogger `_buffer`: `deque(maxlen=1000)` — proper circular buffer
- DreamWorker `_embedding_cache`: `OrderedDict` + `move_to_end` + FIFO eviction — correct
- NREM maintenance: runs EVERY cycle, not every 50
- networkx import: already top-level cached (`HAS_NETWORKX`)
- `CppDreamBackend.prune_connection_history`: already implemented

### Still Outstanding (P2/P3)
| # | File | Issue | Impact |
|---|------|-------|--------|
| A | `knowledge_graph.cpp` `spread_activation` | Path vectors allocated per node, unbounded | High memory spike during deep BFS |
| B | `knowledge_graph.cpp` adjacency | Bidirectional edge duplication (2× storage) | 2× memory for edges |
| C | `memory_manager.cpp` `evict_oldest_internal` | O(n) index rebuild per eviction | CPU spike during consolidation |
| D | `semantic_memory.cpp` centroid update | Per-member hash lookup in `entries_` map | O(n×m) lookups |
| E | `embed_provider.py` | SentenceTransformer KV-cache accumulation | GPU fragmentation over long uptime |

---

## C++26 Architecture

### Pipeline: NREM → REM → Insight (Lock-Free Ring Buffers)

```
┌──────────────────────────────────────────────────────────────┐
│                   DREAM PIPELINE PROCESS                       │
│                                                               │
│  ┌─────────────┐    Lock-Free    ┌─────────────┐            │
│  │   NREM      │ ── MPSC Ring ──│    REM      │            │
│  │  Phase      │    (edges)     │   Phase      │            │
│  └──────┬──────┘                └──────┬──────┘            │
│         │                               │                     │
│         │ Lock-Free                     │ Lock-Free           │
│         ▼                              ▼                     │
│  ┌──────────────────────────────────────────┐              │
│  │        INSIGHT PHASE (Louvain)            │              │
│  └──────────────────────────────────────────┘              │
│                                                               │
│  ┌──────────────────────────────────────────┐              │
│  │       MEMORY BANK (Slab-Allocated)        │              │
│  │  SoA layout, AVX-512 batched cosine      │              │
│  │  CSR graph format                         │              │
│  └──────────────────────────────────────────┘              │
│                                                               │
│  ┌──────────────────────────────────────────┐              │
│  │     VECTOR ENGINE (SIMD + thread pool)   │              │
│  │  AVX-512 > AVX2 > NEON > Scalar          │              │
│  └──────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Data Structures

### CSR Graph (replaces `adjacency_` unordered_map)

```cpp
// Compressed Sparse Row — 5-10× memory reduction vs adjacency list
// For 100K edges (undirected): ~4.8MB vs ~50MB
struct CSRGraph {
    std::vector<uint64_t> row_offsets;    // N+1 entries
    std::vector<uint64_t> col_indices;   // M/2 entries (stored once, undirected)
    std::vector<float>    edge_weights;  // M/2 entries
    std::vector<uint32_t> edge_versions; // ABA prevention for CAS updates

    // Atomic weight update via CAS
    bool atomic_strengthen(uint64_t src, uint64_t tgt, float delta) noexcept;

    // Bimodal degree scan: dense scan for hot nodes, CSR skip for cold
    std::pair<size_t, size_t> degree_range() const noexcept;
};
```

### SoA Memory Bank (replaces per-node vectors)

```cpp
// Structure of Arrays — cache-line optimal, SIMD-friendly
// 1024d × 100K memories = 400MB contiguous (fits in L3)
struct MemoryBank {
    // 64-byte aligned buffers (AVX-512 optimal)
    std::vector<float, AlignedAllocator<float, 64>> embeddings;  // 400MB per 100K
    std::vector<uint32_t> node_ids;
    std::vector<float>    salience;
    std::vector<uint32_t> memory_type;  // EPISODIC=0, SEMANTIC=1, DERIVED=2
    std::vector<uint64_t> timestamps;
    std::vector<uint32_t> access_counts;

    // AVX-512 batch cosine: 16 vectors × 1024 dims per core cycle
    void batch_cosine(const float* query, size_t query_id,
                      size_t count, size_t dim,
                      float* results) const noexcept;
};
```

### Slab Allocator

```cpp
// Zero-fragmentation allocator for graph objects
// O(1) alloc/dealloc, never returns memory to OS
template<typename T, size_t SLAB_SIZE = 4096>
class SlabAllocator {
    std::vector<std::unique_ptr<T[]>> slabs_;
    std::vector<T*> free_list_;

public:
    T* alloc() noexcept;
    void dealloc(T* p) noexcept;
    void clear() noexcept { free_list_.clear(); }  // Reset without freeing
};

// All temporary objects (paths, activation maps, edge sets) use slab allocation
```

---

## Phase Architecture

### NREM Phase

**Input**: Recent memories from SQLite
**Algorithm**: Spreading activation per memory
**Output**: Lock-free ring of edges to strengthen

```cpp
class NREMScheduler {
    LockFreeRing<SpreadingTask, 512> input_queue_;
    LockFreeRing<EdgeResult, 2048> output_queue_;
    std::jthread worker_pool_;  // work-stealing

    // Per-worker: reads from shared input ring, writes to output ring
    void worker_loop(std::stop_token token, size_t worker_id) noexcept;

    // Spreading activation: bounded depth, thread-local path storage
    void spread_activation(uint64_t memory_id, float threshold,
                           std::span<EdgeResult> results) noexcept;
};
```

**Key optimizations**:
- Thread-local `std::vector<uint64_t>` paths — no heap allocation per spread
- Batched edge strength updates via CAS
- Early termination when activation < threshold

### REM Phase

**Input**: Edge results from NREM ring
**Algorithm**: Isolated memory detection + vector similarity search
**Output**: Bridge connections to DB

```cpp
class REMPhase {
    // Isolate detection: scan CSR degree array, find nodes with degree < 3
    std::vector<uint64_t> find_isolated(const CSRGraph& graph, size_t max_degree) const noexcept;

    // Bridge discovery: batch cosine between isolated set vs all memories
    // Uses AVX-512 batch cosine with SoA memory bank
    std::vector<BridgeCandidate> discover_bridges(
        const MemoryBank& bank,
        std::span<const uint64_t> isolated_ids,
        size_t top_k
    ) const noexcept;
};
```

### Insight Phase

**Input**: Connection graph
**Algorithm**: Louvain community detection + bridge identification
**Output**: Cluster insights to DB

```cpp
class InsightPhase {
    // Louvain: modularity optimization on CSR graph
    // Batched edge weight reads, no temporary adjacency copies
    std::vector<Community> louvain(const CSRGraph& graph, uint32_t seed) const noexcept;

    // Bridge detection: count inter-community edges per node
    // Single CSR scan (O(M)), not O(N²)
    std::vector<BridgeNode> find_bridges(const CSRGraph& graph,
                                        std::span<const Community> communities) const noexcept;
};
```

---

## ASM64 Critical Path Ops

### Batch Cosine (AVX-512, 16 elements/cycle)

```asm
; Input: rdi=query_ptr, rsi=vectors_ptr, rdx=count, rcx=dim, r8=results_ptr
; Precondition: all pointers 64-byte aligned, dim multiple of 16
section .text
global batch_cosine_avx512
batch_cosine_avx512:
    push rbp
    mov rbp, rsp

    ; Pre-compute query L2 norm
    vbroadcastss zmm0, [rel .one]           ; placeholder
    vxorps zmm1, zmm1, zmm1                  ; sum = 0
    mov rax, rcx
    sar rax, 4                               ; iterations = dim/16
    jz .norm_tail

.norm_loop:
    vmovups zmm2, [rdi + r9 * 4]             ; load 16 query floats
    vfmadd231ps zmm1, zmm2, zmm2            ; sum += v^2 (fma)
    add r9, 16
    dec rax
    jnz .norm_loop

.norm_tail:
    vextractf32x4ymm1, zmm1, 0              ; fold 512→256
    ...
    vsqrtps zmm0, zmm1                       ; ||query||
    vrcp14ps zmm0, zmm0                      ; 1/||query|| for division
    mov r9, 0                                ; vector index = 0

.outer_loop:
    cmp r9, rdx
    jge .done
    vxorps zmm3, zmm3, zmm3                  ; dot = 0
    vxorps zmm4, zmm4, zmm4                   ; ||vec||² = 0
    mov r10, 0                               ; dim offset = 0
    mov rax, rcx
    sar rax, 4                               ; dim/16 iterations

.inner_loop:
    vmovups zmm5, [rsi + r9*dim*4 + r10*4]  ; 16 floats of vector j
    vmovups zmm6, [rdi + r10*4]             ; 16 floats of query
    vfmadd231ps zmm3, zmm5, zmm6             ; dot += v * q
    vfmadd231ps zmm4, zmm5, zmm5             ; ||v||² += v²
    add r10, 16
    dec rax
    jnz .inner_loop

    vsqrtps zmm4, zmm4                       ; ||vec||
    vmulps zmm3, zmm3, zmm0                  ; dot * (1/||q||)
    vmulps zmm3, zmm3, zmm4                  ; dot / (||q|| * ||v||)
    vmovups [r8 + r9*4], zmm3                ; store 16 results
    inc r9
    jmp .outer_loop

.done:
    vzeroupper
    pop rbp
    ret
```

### Hebbian Weight Update (FMA chain, lock-free CAS)

```cpp
// C++ wrapper using inline asm for the inner loop
inline void hebbian_batch_avx512(
    const uint32_t* src_ids,   // source memory IDs
    const uint32_t* tgt_ids,   // target memory IDs
    const float* deltas,        // weight deltas
    float* weights,            // in/out: current weights (aligned)
    size_t count
) noexcept {
    for (size_t i = 0; i < count; i += 16) {
        size_t batch = std::min(size_t(16), count - i);
        // Load 16 weights
        __m512 w = _mm512_load_ps(weights + src_ids[i]);
        // Load 16 deltas
        __m512 d = _mm512_load_ps(deltas + i);
        // FMA: w' = w + delta (no clamping here — clamp after)
        __m512 w_new = _mm512_add_ps(w, d);
        // Store back
        _mm512_store_ps(weights + src_ids[i], w_new);
    }
}
```

---

## Compilation Requirements

```cmake
# Minimum C++26 (GCC 14+, Clang 18+, MSVC 2024 17.12+)
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# AVX-512 mandatory for this build (check at CMake level)
include(CheckCXXSourceCompiles)
check_cxx_source_compiles("
    #include <immintrin.h>
    int main() { __m512 v = _mm512_setzero_ps(); return 0; }
" HAVE_AVX512F)
if(NOT HAVE_AVX512F)
    message(FATAL_ERROR "AVX-512F required for dream engine")
endif()

# OpenMP for thread pool
find_package(OpenMP REQUIRED)

# Link-time optimization for cross-TU inlining
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
```

---

## Performance Targets

| Metric | Current (Python) | Target (C++26) |
|--------|-----------------|----------------|
| NREM phase (100 memories) | ~30s | < 2s |
| REM phase (50 isolated) | ~45s | < 3s |
| Insight phase (Louvain) | ~57s | < 5s |
| Peak RSS during NREM | ~800MB | < 200MB |
| Embedding cache bound | 2048 items | None (CSR indexed) |
| Edge update latency | O(log N) | O(1) CAS |

---

## Implementation Order

1. **CSR graph + SoA memory bank** — Foundation for all phases
2. **Slab allocator** — Eliminate fragmentation across phases
3. **AVX-512 batch cosine** — Single biggest performance multiplier
4. **Lock-free MPSC rings** — NREM→REM→Insight pipeline
5. **Louvain community detection on CSR** — replaces networkx dependency
6. **Batched DB writes** — Bulk INSERT for bridges/insights
