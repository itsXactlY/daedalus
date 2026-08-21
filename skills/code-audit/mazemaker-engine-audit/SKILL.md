---
name: mazemaker-engine-audit
description: Use when auditing the mazemaker-pro memory engine.
category: code-audit
---

# Mazemaker Engine Audit

Auditing / thesis verification / degradation analysis for the **mazemaker-pro** semantic-memory engine. Covers the fallback-inventory method, config-surface liveness checks, git archaeology for introduction commits, and benchmark-condition truth.

> ⚠️ Repo: `/home/alca/projects/mazemaker-pro` (memory engine). Do NOT confuse with `/home/alca/projects/mazemaker` (stickman-video project — skill `mazemaker-autonomous-loop`).

## Engine map (python/)

| File | Role |
|---|---|
| `memory_client.py` (~5300 L) | `SQLiteStore` + `NeuralMemory`/`Mazemaker` hot path: recall pipeline, RRF channel fusion, ColBERT/DAE channel scoring, GPU init (3-tier: remote→local cache→auto-build), HNSW (hnswlib, ef hardcoded 64) |
| `embed_provider.py` | Shared UNIX-socket embed server (one model per pod), `SharedEmbedClient`, `RemoteGpuRecallClient`, GPU-first policy with `MAZEMAKER_DEVICE_STRICT` |
| `gpu_recall.py` | `GpuRecallEngine`: tensor cosine search, `load_from_store` for PG. Device selection at lines ~110-113 is **silent** |
| `dream_engine.py` | `DreamEngine` phases (nrem/rem/insight/**supersedes**/afe/synthesis/**dae**) + `DreamBackend` base class whose defaults degrade silently |
| `postgres_store.py` | PG backend; per-connection `SET hnsw.ef_search` via `MM_HNSW_EF_SEARCH` (default 500, since 3215f95 2026-05-21) |
| `dream_postgres_store.py` | PG dream backend: 3-slice `sample_for_dream`, `add_supersedes_batch`, `get_memory_vectors` (pgvector parse fixed a354383 2026-07-10) |
| `dae.py` / `colbert_helper.py` | DAE compute + ColBERT late-interaction. `channel_status()`: DAE recall channel **intentionally unwired** |
| `compute_config.py` | Reads compute.toml — **ONLY `[dream]` and `[afe]` have consumers** |
| `config.py` | Plugin config from `~/.hermes/config.yaml` `memory.neural.*` (NOT compute.toml!) |
| `license.py` | `has_feature("colbert"/"dae"/"postgres"/...)` JWT gates |

## Config surfaces — live vs dead (THE big trap)

Three separate config worlds; only the first two do anything:

1. **compute.toml** (`/root/.mazemaker/compute.toml` or `~/.mazemaker/`, written by license-client from JWT): `[dream]` + `[afe]` keys LIVE via `compute_config.py` (since 02fda91 2026-08-07). **`[compute]`, `[recall]`, `[recall_advanced]` (mode, rerank, colbert_weight, dae_weight, candidates_n, multi_query), `[embeddings]`, `[storage]`, `[resources]`, `[mcp_tools]`, `[vault]` are DEAD — read by no code.** An operator's web-console settings there silently do nothing.
2. **`~/.hermes/config.yaml` → `memory.neural.*`** → `config.py get_config()` → `Memory(...)` constructor (retrieval_mode, rerank, channel_weights, rrf_k, …). If no `neural:` section exists, defaults apply: **retrieval_mode="semantic", rerank=False** — regardless of what compute.toml says.
3. **Env vars**: `MM_COLBERT_ENABLED` (blob write + WARN if no Pro), `MM_HNSW_EF_SEARCH` (PG only), `EMBED_CLIENT_ONLY` (thin client, refuses local ARM), `MAZEMAKER_DEVICE_STRICT`, `MAZEMAKER_SUPERSEDES_CURATED_ONLY`, `MM_DB_BACKEND` (WARN if postgres without Pro). Env vars that used to steer policy are now ignored with one-time `warn_ignored_env()` — grep `compute_config.py` for the LEGACY list before trusting an env var.

## Audit methodology (verified workflow)

1. **Fallback inventory**: grep `if not self._<feature>`, `if <x> is None`, `except` across the 6 core files; classify EVERY fallback by log level — `debug`/silent do NOT count as a Meldung.
2. **Silence hides in return-paths, not naked excepts**: 205 excepts had only 2 literal `pass`; the real silent modes are `return {}`/`return []` (ColBERT/DAE scorers, RemoteGpuRecallClient on socket death, `_get_reranker` fail-closed) and **misleading wording** ("GPU recall ARMED ... on cpu" = INFO; `pairs_checked 17000, found 0` reads as "nothing found" when the writer was dead).
3. **Config liveness**: for every config key, grep the key/section name across the repo and check which sections the config module actually handles. Dead knob = operator believes X, engine does Y.
4. **Auto-promote + fail-closed paths**: rerank auto-True for advanced/skynet (`memory_client.py:3857-3861`) but silently skipped if CrossEncoder won't load; channel weight > 0 but channel inert when data absent (ColBERT needs blobs written by `MM_COLBERT_ENABLED=1`; DAE needs `enable_dae`/`dae_weight` per-call because default weight is 0.0 on ALL presets).
5. **Git archaeology**: `git log --format='%h %ad %s' --date=short -S '<distinctive string>' -- python/` finds introduction commits per behavior. Check whether a "fix" commit created a NEW silent mode (supersedes curated-only gate after the 515k-edge firehose, eab7a9f 2026-08-06).
6. **Benchmark conditions**: parse result JSONs' `config` dict (e.g. `benchmarks/external/results/inception_bench_loop-iter95-*.json`); distinguish harness types (LongMemEval-S = ephemeral per-question vs LongMemEval-oracle = full-corpus); compare against deployed compute.toml + config.yaml. Published numbers usually were NOT measured under normal-operation config.
7. **Historical vs current**: code comments "MEASURED/Audited 2026-08-0X" mark recent fixes — verify current code state before claiming a mode is broken (e.g. PG 3-slice `sample_for_dream` is FIXED since afec238 2026-05-07; GPU-init is loud since 2026-08-05).
8. **Exhaustive function-coverage (found the untested production core)**: run all suites IN-PROCESS via `runpy.run_path(suite, run_name='__main__')` under a `sys.settrace` that counts executed function names per module (trap `'call'` events only; return an inner fn that stops tracing at `'return'` to cut overhead). Then AST-inventory every `def`/method and diff defined-vs-executed. On the suites this found **postgres_store 66/66 and dream_postgres_store 37/37 ZERO suite coverage** — the production core had no tests at all. Write targeted behaviour tests (valid input → result; bad input → clean error) for each uncovered function. NOTE: the settrace overhead makes perf-tests fail spuriously — ignore perf assertions in the traced run.
9. **Test must prove the EFFECT, not just "no crash"**: a fix that stops a TypeError is only half-proven if the new kwarg doesn't observably change behaviour. For `mode=` I first proved "no TypeError" but all modes returned the same hits — the user correctly rejected that. Prove the effect by inspecting result internals (`channel_scores` keys: semantic → only `semantic`; advanced/hybrid → `bm25, entity, ppr, recency, semantic`).


## Known silent-degradation map (verified 2026-08-07)

6+ modes, full detail (file:line, trigger, log level, since-commit) in `references/silent-degradation-map.md`. Headline: GPU→CPU silent device selection + misleading "ARMED on cpu" INFO; ColBERT channel inert without blobs (silent `{}`); DAE recall channel structurally OFF (weight 0, unwired); supersedes gate curated-only → never fires on autosave corpus; compute.toml recall knobs dead; SQLite HNSW ef=64 hardcoded; `_semantic_candidates` silent cascade to 75s brute-force.

## Cycle time: the "seconds-era" vs current minutes (verified 2026-08-08)

The docs/readme-rewrite branch documents the golden era: **end-to-end dream cycle ~38 s on a 193k/~1M-edge corpus** (NREM ~16 s sparse-PPR-on-CUDA + REM ~12 s batched, one matmul + one transaction + Insight ~2 s). The full stack-integration audit on the real 215k corpus found the cycle now takes MINUTES, and **the architecture is NOT regressed** — every golden-era primitive is still present (think_ids fast-path, `_invalidate_gpu_ppr_adjacency`, `recall_batch` one-matmul, `add_connections_batch` one-transaction, `add_one` appends, no-silent-fallback via `MM_RECALL_GPU_STRICT`). The time gap is NOT missing architecture; it is:

- **`get_all(True)` vector materialisation**: the cycle path can still call `store.get_all()` WITH embeddings, building 215k×1024 Python floats (7-9 GB) in RAM *even when the GPU tensor is armed* (duplicate load). This is a cycle-time driver AND the worker RAM-bloat. The lazy fix (`94cdc80`) made `_load_from_store` use `include_embeddings=not armed`, but OTHER `get_all(True)` sites in the cycle path still materialise.
- **PG-vs-SQLite backend cost**: the 38 s era ran on SQLite (one file, bulk UPDATEs near-free). The PG migration (01.05.) moved the ~214k weaken/strengthen edge-UPDATEs + audit-row inserts onto PG transaction/WAL costs — seconds became minutes.
- Maintenance sweeps (`prune_connection_history` over a 18.2M-row table) are **NOT** the bottleneck *provided* the `changed_at` index is used (EXPLAIN shows Index Scan, cost ~0.6) — check the plan before blaming the prune.
- Returning to seconds means: kill every `get_all(True)` in the armed-worker cycle path, batch the edge-UPDATEs into fewer/larger transactions, and keep DAE/ColBERT/Synthesis out of the cycle.

## Free/Pro table boundary (do NOT leak Pro tables into SQLite)

`SQLiteStore` is the FREE stack — it gets only the tables it needs. **NEVER add a Pro feature's table to the SQLite schema** (e.g. `memory_dae_embeddings` is PG-only, created by `ensure_dae_schema`). The table's ABSENCE in a fresh SQLite DB is the intended no-leak guard — a bare Pro-gated call crashing there is correct, not a bug to "fix". The build asserts free↔pro module separation (`PRO_MODULES` no-leak guard in build-all-locked.sh). I added the DAE table to the SQLite schema once and had to revert (35d7d4c).


## Benchmark truth (published numbers vs normal operation)

- **R@5 0.8426 / R@10 0.9000** (LongMemEval-oracle champion iter100): `recall_mode=skynet, rerank=True, colbert=True, dae=True, dream=False`, PG, 25 964 sessions, p50 1.7 s. **Not reproducible in normal operation** (prod runs hybrid/advanced, DAE channel off, colbert partial).
- **LongMemEval-S R@5 0.9787 / R@1 0.8574**: hybrid + ColBERT@1.5, ephemeral harness.
- **skynet R@5 0.9000** (anchor-paraphrase): channel defaults semantic 1.0/bm25 0.9/entity 1.0/temporal 0.35/ppr 0.55/salience 0.25, p50 340 ms.
- **lean R@5 0.60 > skynet 0.42** on real prose (n=200).
- EverMemBench: no numbers in repo (external; source of the PG normaliser bug, 2026-07-03).
- dream_worker CLI defaults: `--retrieval-mode hybrid`, `--think-engine ppr`, `--max-memories 2000`, `--max-isolated 800`.

## Pitfalls

- Bare-except counting is a weak signal; count silent return-paths instead.
- `DreamBackend` base-class defaults degrade silently by design (`sample_for_dream`→recent-only, `get_memory_vectors`→`{}` → supersedes no-ops). Any new backend that doesn't override inherits silence.
- Community/Lite installs: `has_feature()` AND-gates mean `MM_COLBERT_ENABLED=1` without Pro → one WARN then stays hybrid (published R@5 0.96, no ColBERT bonus).
- The plugin `Memory` is built from `config.py` (config.yaml), the dream_worker from CLI args + env — two code paths can run different retrieval modes in the same pod.
- READ-ONLY audits: don't patch; deliver the map with commit refs.
- **"GPU recall init skipped … CPU/numpy" in EVERY host-side test is host-only** (host python lacks torch). The production container has torch+CUDA (`GPU recall arm: streamed 215k vectors onto cuda`) + `MM_RECALL_GPU_STRICT=1`. Don't chase it as a production bug; make the test an honest SkipTest (like the torch absent → skip pattern), not a red suite.
- **Schema/adapter col-count mismatch class**: `get_all(include_embeddings=False)` must SELECT exactly the columns its no-vector unpack expects (7) — the old query always SELECTed all 9 (embedding+vector_dim) and passed the row to a 7-col unpack → `ValueError: too many values to unpack`. Any SELECT/unpack pair must stay in lockstep.
- **recall_advanced "Internal tool execution error"** = the tool schema advertised a kwarg (`mode`) the engine method lacked → TypeError. Cross-check the MCP tool schema (`mcp_schemas.py`) against the engine method signature; a tool that throws is a real bug independent of quality.
- **Supersedes paging**: demoting a superseded row by −0.5 is NOT enough to keep it out of the top-k — with few hits it still pages. Drop superseded rows whose successor is present in the result set (the elevated successor replaces them). Traversal applies in recall, not just curated lookup.
- **ColBERT env gate must cover BOTH paths (a512c36)**: `MM_COLBERT_ENABLED=0` gated only the token WRITE path (`_colbert_write_enabled`) — the READ channel weight came from the retrieval-mode presets (advanced/hybrid → 0.5, skynet → 1.2) and the compute.toml overlay (colbert_weight=1.5). Result: embed_colbert HTTP calls kept firing every ~1 s in the cycle despite env=0 (a real cycle-time sink, measured 2026-08-08 05:25). Fix: the env wins LAST (force colbert channel weight 0.0 after every preset/overlay when env is not 1/true/yes/on); the no-env default is now OFF (was 0.5-preset). General lesson: an operator gate that only switches one of two paths is a lying knob — audit ALL consumers of a feature, not just the obvious one.
- **compute.toml is RENDERED by license-client from the JWT claim** — hand-editing a key there is volatile (overwritten on next render). The stable off-switch for a Pro policy is an env var set in the quadlet (e.g. `MAZEMAKER_DAE_ENABLED=0`), and the `DEFAULTS` dict must match the shipped policy (e.g. `stage_s_enabled` default was True, letting Synthesis run on any fresh/no-toml container — fixed to False).
- Duplicate test-function names silently shadow one another (two `def test_31()` → the second wins, the first never runs). A regression guard that "passes" while never executing is worthless — check for name collisions.


## References
- `references/silent-degradation-map.md` — full degradation map with file:line, trigger, log level, since-commit + dead-knob inventory (session 2026-08-07, THESE B).
- `references/audit-2026-08-08-cycle-and-integration.md` — cycle-time root causes (get_all(True) materialisation, PG-vs-SQLite cost), the fixes (get_all(False), stage_s default, recall_advanced mode, supersedes paging, dream_stats pool leak), the function-coverage gap numbers, and the Free/Pro table-boundary lesson.
- `references/colbert-gate-und-stack-integration.md` — ColBERT env gate must cover BOTH paths (a512c36, the lying-knob lesson), the PG-container-test licence trap (silent SQLite fallback), the exhaustive PG-store verification results (75/75), and the operator preference for host-side behaviour tests over container chains.
