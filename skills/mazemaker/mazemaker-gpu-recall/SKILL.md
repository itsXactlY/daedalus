---
name: mazemaker-gpu-recall
category: devops
description: GPU-accelerated neural memory recall engine and database recovery procedures
triggers:
  - neural memory recall too slow
  - C++ bridge returning wrong results
  - GPU recall engine
  - Hopfield bias
  - embedding normalization mismatch
  - neural memory database recovery
---

# Mazemaker GPU Recall Engine + Database Recovery

## Problem Context

After a BTRFS snapshot restore, the Mazemaker system had multiple issues:
1. Two SQLite databases with different states (248MB bloated vs 55MB clean)
2. MSSQL contaminated with ~3000 benchmark memories (LongMemEval)
3. C++ bridge Hopfield network biased on benchmark data
4. Embedding normalization mismatch causing wrong recall

## Solution: GPU Recall Engine

Built gpu_recall.py using torch.matmul for CUDA cosine similarity.
8.8 MB VRAM for 2264 memories, ~100ms recall time.

## Pitfalls

### 1. C++ Hopfield Network Bias

Symptom: recall() always returns bench-math-363 with 0.967 similarity.
Root cause: Hopfield learns from stored data. Benchmark data dominates.
Fix: use_cpp=False in __init__.py. Use GPU or Python fallback.

### 2. Embedding Normalization Mismatch

Symptom: Wrong recall after L2-normalizing stored embeddings.
Root cause: Stored normalized (mag=1.0), query unnormalized (mag=28).
Fix: Keep both raw OR normalize both. For GPU, keep both raw.

### 3. FastEmbed vs sentence-transformers

FastEmbed: ONNX, no PyTorch conflict, ~50ms/emb. Use for CPU.
sentence-transformers: PyTorch CUDA, ~108 mem/s. Use for GPU batch.

### 4. SQLite = Source of Truth

SQLite is canonical. MSSQL is optional mirror.

## Database Recovery

1. Compare DBs: check freelist_count, connection_history bloat
2. Filter quality from MSSQL: skip DD*, turn-*, msg:*, person names
3. Import + VACUUM
4. Re-embed with GPU (sentence-transformers + CUDA)
5. Build GPU cache (~/.mazemaker/gpu_cache/)
6. MSSQL sync

## Performance

| Method | Time | Correct? |
|--------|------|----------|
| GPU (torch.matmul) | 100ms | Yes |
| Python loop | 500ms | Yes |
| C++ Bridge | 90ms | No (biased) |

## Config

embedding_backend: fastembed (NOT sentence-transformers for CPU)
use_cpp: false (Hopfield biased)
