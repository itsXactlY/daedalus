# Cycle-Time Measurements 2026-08-08 — real 215k, pod + GPU + real policy

All measurements below ran in the pod container (same pod as pgvector) with
`--device nvidia.com/gpu=all`, the QUADLET envs (`MM_COLBERT_ENABLED=0`,
`MAZEMAKER_DAE_ENABLED=0`, `EMBED_BACKEND=http`, `EMBED_CLIENT_ONLY=1`,
`MM_RECALL_GPU_STRICT=1`, `MM_EMBEDDING_WORKER_URL`), licence mounts
(`license.jwt` + `jwt.v1.pub.ed25519`), the RENDERED `compute.toml`, the PG
secret, and the engine source mounted read-only
(`-v ~/projects/mazemaker-pro/python:/app/core:ro`) so the FIXES run, not the
stale image. Run commands: `podman run --rm --pod <pgvector-pod> --user 0
--device nvidia.com/gpu=all --secret mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD
-v <script>:/audit.py:ro -v <python>:/app/core:ro ... localhost/mazemaker-v2-mcp:gpu python3 /audit.py`.
Never write test memories into the production DB.

## The journey (all on the real 215.5k corpus)

| Config | Cycle time | Insights/cycle | Notes |
|---|---|---|---|
| stale code (embed_colbert flood + DAE running) | ~36 min | 29-30k | the "hours" era; embed_colbert HTTP calls every ~1s during the cycle |
| DAE off (env-name fix 5396678) | 525.9s | 30k | DAE had written 215,651 rows — the full-corpus compute was ~450s of it |
| DAE off + MM_INSIGHT_BRIDGES=0 (9e63ff6) | 178.0s / 169.8s (cycle 2) | **50** | bridge rows cut — 47k bridges still DETECTED, only the duplicate rows stop |
| + REM budget 400 (0e64ed3) | ~100s expected | 50 | REM GPU embedding halved |

Reference points: with DAE properly skipped the cycle was 72.3s in the run
where REM found almost no bridges (graph state dependent — REM is the
variable part). NREM is consistently ~10s.

## Phase timing (pod-phase-timing, run_cycle(phases=[...]))

```
nrem       :  10.4s  {'processed': 2000}
supersedes :   0.6s
rem        : 128.0s  {'bridges': 1583}   ← the bottleneck
```

## REM drill-down (pod-rem-timing)

```
sample_isolated_for_dream(800):   0.5s
recall_batch(800, k=10):        152.4s   ← the whole REM cost
Kandidaten-Bewertung (6417):      0.00s
```

The 152.4s is the batched GPU embedding of the 800 sample queries. The
queries were already truncated to 200 chars (`queries = [m["content"][:200]
for m in kept]`) — so it is per-sequence GPU latency through the embedding
worker's batch processing, not text length. The semantic bridge search
scales linearly with sample count; the discovery rate does not (the same
bridges are found over cycles). Fix 0e64ed3: `max_isolated` now reads
compute.toml `[dream].max_isolated`, default 800→400.

## Bridge-insight flood: why no dedup signature survived

- v1 (content = count only): cycle2 still 12,050 insights.
- v2 (count + top-3 community IDs): cycle2 still 30,424 — Louvain re-labels
  every run, any id-based signature wobbles.
- v3 (count + top-3 community SIZES — robust against renumbering, verified
  in the drift matrix): cycle2 STILL 28,562 — the Louvain STRUCTURE itself
  reorganises under NREM/REM edge-weight changes (communities grow/shrink/
  split), so size-based signatures wobble too.

The rows are redundant text duplicates of the edges REM already wrote
(dream_insights at 14M rows). `MM_INSIGHT_BRIDGES=0` (9e63ff6, default ON
for compat) skips minting them: insights 30k→50 per cycle, cycle 417s→178s.
The bridge DETECTION (47k bridges found) is untouched — only the duplicate
rows stop.

## Env-name mismatch (the "knob does nothing" class, 5396678)

The quadlet sets `MAZEMAKER_DAE_ENABLED=0`; `_phase_dae` read only the
legacy `MM_DAE_ENABLED` (empty → "1"). The two names never met → the
full-corpus DAE compute ran (215,651 rows written, ~450s/cycle). Fix: the
gate reads BOTH names. Lesson: grep the deployed knob's name against the
code's `os.environ.get(...)` calls — a renamed env in the quadlet while the
code kept the old name survives every unit test of the gate logic.

## ColBERT read-path gate (a512c36)

`MM_COLBERT_ENABLED=0` gated only token WRITES; the READ channel weight came
from retrieval-mode presets (0.5 advanced/hybrid) + compute.toml overlay
(1.5), so embed_colbert HTTP calls kept firing every ~1s during the cycle
despite env=0. Fix: the env wins LAST — after every preset/overlay force
the colbert channel weight to 0.0 unless env is explicitly on. Side effect
(intended): with no env the channel is now OFF by default.
