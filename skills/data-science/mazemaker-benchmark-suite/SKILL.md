---
name: mazemaker-benchmark-suite
description: Complete benchmark suite for Mazemaker Adapter — retrieval, dream, GPU, scalability, graph, concurrent, conflict, MSSQL, agentic. All synthetic data, no external downloads.
tags: []
---

# Mazemaker Benchmark Suite — Development Guide

## DO NOT INVOKE FROM A RECALL / DREAM PATH

Each suite spawns:
- its own SQLite DB at a tempfile location (locks contend with live `~/.mazemaker/data/memory.db` if you're sloppy)
- its own embedding model load on GPU (~1.5 GB BGE-M3 on top of the live stack)

This is a **development guide for the suite itself**, not a tool to answer recall questions. To answer memory queries use `mazemaker_recall` via MCP. To force a consolidation cycle use `mazemaker_dream(phase='all')` via MCP. Run this suite ONLY when explicitly debugging benchmark code.

Before invoking, set `EMBED_CLIENT_ONLY=1` in the environment if the live mazemaker stack is up — otherwise the suite spawns a redundant model copy. Or stop `mazemaker-mcp.service` + the host `dream_worker` first if you need the GPU exclusively.

## Overview
Complete benchmark suite at `~/projects/mazemaker/benchmarks/neural_memory_benchmark/`.

Directory structure:
```
neural_memory_benchmark/
  __init__.py
  config.py          # All tunable knobs
  dataset.py         # 6 synthetic generators + QueryGenerator + MasterDataset
  benchmark.py       # Main orchestrator (NeuralMemoryBenchmark class + main())
  report.py          # ASCII + JSON report generator
  runner.py          # CLI entry point
  suites/
    retrieval.py     # Recall quality, latency, throughput
    dream.py         # NREM/REM/Insight phases
    gpu.py           # GPU vs CPU, batch throughput
    scalability.py    # 1K → 500K memory scaling
    graph.py         # BFS vs PPR vs HNSW traversal
    concurrent.py     # WAL stress, multi-threaded r/w
    conflict.py       # Supersession, salience decay, poison resistance
    mssql.py         # Sync bridge throughput
    agentic.py       # End-to-end agent workflow simulation
```

## Running
```bash
cd ~/projects/mazemaker
PYTHONPATH=. python3 benchmarks/neural_memory_benchmark/runner.py --dry-run  # smoke test
PYTHONPATH=. python3 benchmarks/neural_memory_benchmark/runner.py --suite retrieval
PYTHONPATH=. python3 benchmarks/neural_memory_benchmark/runner.py             # all suites
PYTHONPATH=. python3 benchmarks/neural_memory_benchmark/report.py              # generate report
```

Or as module:
```bash
cd ~/projects/mazemaker/benchmarks
python3 -m neural_memory_benchmark.runner --dry-run
```

## Known bugs and fixes

### Generator `__init__` signature inconsistency
`EpisodicGenerator(count=N)` and `TemporalGenerator(count=N)` accept `count`.
`FactualGenerator` and `ConversationalGenerator` do NOT — they generate endlessly.
`GraphGenerator(count=N)` and `AdversarialGenerator(count=N)` accept `count`.

In `MasterDataset.generate()`, instantiate without `count=` for factual/conversational:
```python
generators = {
    "episodic": EpisodicGenerator(seed=seed, count=episodic),
    "factual": FactualGenerator(seed=seed + 1),         # NO count=
    "temporal": TemporalGenerator(seed=seed + 2, count=temporal),
    "conversational": ConversationalGenerator(seed=seed + 3),  # NO count=
    "graph": GraphGenerator(seed=seed + 4, count=graph),
    "adversarial": AdversarialGenerator(seed=seed + 5, count=adversarial),
}
```

### Import style
This project uses absolute imports from the package root. When running as `benchmark.py` directly:
```python
# WRONG:
from .config import BenchmarkConfig

# CORRECT:
from neural_memory_benchmark.config import BenchmarkConfig
```
Also ensure `sys.path` has both `python/` (for memory_client) and the package root.

### `generate_scales` generator bug
`generate_scales()` had `count=factual` and `count=conversational` in `MasterDataset.__init__`, which don't accept those args. Fixed by removing those kwargs.

## Key design decisions
- All data is synthetic — no external downloads required
- Each suite gets its own temp DB (`tempfile.NamedTemporaryFile`) to avoid cross-contamination
- Suites use `sys.path.insert(0, str(SRC_ROOT / "python"))` for imports
- Results go to `~/.mazemaker/benchmark/results/`
- Report generator uses ANSI colors (green/yellow/red) for score visualization
