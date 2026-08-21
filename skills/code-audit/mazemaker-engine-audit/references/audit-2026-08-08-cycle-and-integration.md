# Audit 2026-08-08 — cycle time, full-stack integration, coverage gaps

Session detail behind the "Cycle time" and "function-coverage" sections of the
SKILL.md. All findings verified against the live stack on this box.

## Cycle-time root causes (real 215k corpus, full-stack integration test)

- Golden era (docs/readme-rewrite branch): "end-to-end cycle time ~38s on a
  193k-memory / ~1M-edge corpus" — NREM ~16s sparse-PPR-on-CUDA, REM ~12s
  batched (one matmul + one transaction), Insight ~2s.
- Current full cycle on 215k with DAE/ColBERT/Synthesis OFF: still MINUTES.
  Live NREM was >18 min, CPU 70%, no phase-progress log.
- Active PG query during the hang: `SELECT id, label, content, embedding,
  vector_dim, ... FROM memories` = `store.get_all()` WITH embeddings — the
  7-9 GB Python-float materialisation, duplicated even though the GPU tensor
  is armed. `_load_from_store` is lazy (`include_embeddings=not armed`, 94cdc80)
  but OTHER `get_all(True)` sites in the cycle path still materialise.
- Golden-era architecture is PRESENT, not regressed (verified grep):
  `think_ids` fast-path, `_invalidate_gpu_ppr_adjacency`, `recall_batch`
  one-matmul, `add_connections_batch` one-transaction, `add_one` appends,
  `MM_RECALL_GPU_STRICT` no-silent-fallback.
- `prune_connection_history` over an 18.2M-row table is fast IF the
  `changed_at` index is used: `EXPLAIN DELETE ... WHERE changed_at < cutoff`
  → Index Scan cost ~0.57. Blame the edge-UPDATEs + get_all, not the prune.

## Fixes from this session (all verified behaviourally)

- `postgres_store.get_all(include_embeddings=False)` crashed:
  `SELECT` always returned 9 columns (embedding+vector_dim) but the no-vector
  unpack expected 7 → `ValueError: too many values to unpack`. Fixed: select
  exactly the 7 columns in the False branch. (Same col/unpack lockstep class
  applies to any adapter.)
- `compute_config.DEFAULTS[dream].stage_s_enabled` was `True` — without a
  rendered compute.toml (fresh container / test harness) Synthesis ran even
  though policy is off. Default now False (matches shipped policy).
- `recall_advanced` TypeError: `mcp_schemas.py` advertised `mode`, but
  `Memory.recall` had no `mode` param → every call raised, surfaced as
  "Internal tool execution error" by the MCP wrapper. Fixed: `mode` param
  feeds the hybrid-default and the rerank-default.
- Supersedes paging: superseded rows were demoted −0.5 but stayed in top-k.
  Fixed: drop a superseded result when its successor is present in the result
  set. Verified: recall with traversal → only newer id; without → old stays.
- Connection-pool leak (other session, related): `dream_stats()` created
  `DreamPostgresStore()` (new `ConnectionPool(min_size=1,max_size=8)`) per call
  and never closed it → 100/100 idle connections, "too many clients already".
  Fixed with a cached backend (`_dream_stats_backend`).

## Function-coverage numbers (the production core had zero suite coverage)

Ran all 3 suites in-process via `runpy.run_path` under `sys.settrace`
(counting `'call'` events). 13 core modules, 416 defs, only 182 executed,
234 not executed by the suites:

- postgres_store: 66/66 NOT executed
- dream_postgres_store: 37/37 NOT executed
- afe: 10/10 NOT executed (module level)
- dream_worker: 5/5, mcp_schemas: 2/2, config: 2/2 NOT executed
- memory_client: 52 gaps (MCP-tool paths, PPR-GPU, reranker)
- embed_provider: 30 gaps (socket-server internals), gpu_recall: 8

The PG backends — the PRODUCTION core — had zero suite coverage. Targeted
behaviour tests for the uncovered PG functions (75/75) + the rest (65/65)
all passed against a throwaway `mazemaker_test` DB after fixing the
get_all(False) bug. Pattern: run the PG-targeted tests INSIDE the pod
container (`podman run --pod <pgpod> --secret mazemaker_pg_password,
type=env,target=MM_POSTGRES_PASSWORD -v <repo>/python:/app/core:ro`) because
PG is pod-internal (no host port exposed), and mount the Pro licence
(`-v ~/.mazemaker/license.jwt` + `MAZEMAKER_LICENSE_PATH`) or `has_feature`
falls back to SQLite and the PG path silently isn't exercised.

## Free/Pro boundary lesson

SQLite is the FREE stack. Never add a Pro feature's table to the SQLite
schema. I added `memory_dae_embeddings` (PG-only, created by
`ensure_dae_schema`) to the SQLite schema as a "fix" for a bare-call crash —
reverted (35d7d4c) because the table's absence IS the no-leak guard. The
build asserts module separation (PRO_MODULES no-leak guard in
build-all-locked.sh). A Pro-gated call crashing on a fresh SQLite DB is
correct behaviour, not a bug.
