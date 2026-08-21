---
name: mazemaker-benchmark-debugging
category: data-science
description: How to debug the mazemaker benchmark suite when it fails or regresses.
version: 2.0.0
priority: low
---

# Mazemaker Benchmark Debugging

The benchmark suite lives at `~/projects/mazemaker/benchmarks/neural_memory_benchmark/`. Its API is the engine's own `Mazemaker` class — see `~/projects/mazemaker/python/memory_client.py` for the canonical interface (recall, remember, think, dream).

## Hard rules — read before invoking anything

1. **Do not run benchmarks from a recall / dream path.** Each suite spawns its own SQLite DB at a `tempfile.NamedTemporaryFile` location AND its own embedding model. Running while the live mazemaker stack is up doubles VRAM and locks the WAL. Stop `mazemaker-mcp.service` and the host `dream_worker` first if you need the GPU exclusively.
2. **Set `EMBED_CLIENT_ONLY=1`** before invoking any benchmark that touches the live memory.db — otherwise it spawns a redundant BGE-M3 model copy. Set it `0` only if intentionally measuring cold-load.
3. **Refuse to invoke scripts from a `recall:` skill follow-through.** This skill is for explicit debugging only, never an automatic side effect of answering a memory query.

## Diagnostic workflow

When a benchmark suite fails:

1. Read the actual error from the suite's stdout/stderr. The skill cannot reproduce it without a live trace.
2. Confirm `~/projects/mazemaker/python/` is on `PYTHONPATH` (the runner inserts it from the package root; if invoked from elsewhere, imports fail).
3. Confirm the test DB path is writable and not collision-prone with another suite running concurrently.
4. For embedding-throughput regressions: compare against `mazemaker_stats()` — backend mismatches (sentence-transformers vs fastembed) explain most cliffs.
5. For recall-latency regressions: compare against the live `mazemaker_recall` against the same query — the live engine is the ground truth, not the suite.

## What this skill is NOT

- Not a substitute for `mazemaker_recall` to answer memory questions.
- Not a runner for ad-hoc memory tests; use `mazemaker_dream(phase='all')` then `mazemaker_recall(...)` via MCP for that.
- Not a place for fictional class definitions. The historical version of this skill listed a `NeuralMemoryBenchmark` interface (embed_batch / search / k-recall) that did not match the engine. Replaced.

## See also

- `mazemaker-benchmark-suite` — invocation reference for the real benchmark suite.
- `mazemaker-first` — recall protocol (the right path for memory questions, not benchmarks).
- `mazemaker-dream-engine` — MCP-tool dream interface.
