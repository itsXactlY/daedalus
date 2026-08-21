---
name: mazemaker-stack-ops
description: Operate and debug the mazemaker-pro production stack.
category: devops
version: 1.0.0
tags: [mazemaker, stack, pgvector, dream, afe, quadlet, preflight, oomd, bake]
---

# Mazemaker Pro Stack Operations

Class-level guide for operating and debugging the production Mazemaker stack
(`~/projects/mazemaker-pro` engine + `~/projects/mazemaker-v2-stack/backend`
deployment, PG-backend, podman quadlets, systemd user units). Every pitfall
below was hit and fixed for real in 2026-08-07; references hold the detail.

## The five stack facts that explain most "nothing works" reports

1. **The SQLite DB is a 0-byte shell since the PG migration** —
   `ls -la ~/.mazemaker/data/memory.db` → 0 bytes. The corpus lives in
   Postgres, but some engine paths still read SQLite. Symptom: phases report
   "0 sources" while `SELECT count(*) FROM memories` in PG shows 200k+.
   AFE sources must be PG-first (dream_engine `_phase_afe` prefers
   `self._memory._postgres_store` when it has the streamer). After any backend
   migration, verify WHICH store each phase actually reads.
2. **compute.toml is RENDERED by the license-client from the JWT claim** —
   hand-edited keys get overwritten. Durable policy defaults belong in
   `compute_config.py` DEFAULTS (they win when the toml lacks the key).
3. **status=137 in the idle phase (not mid-cycle) = systemd-oomd** — Memory
   Pressure >80% in the user slice for >20s kills the largest consumer
   (OOMScoreAdjust=500 marks the dream-worker). Check `systemctl --user show
   -p MemoryHigh,MemoryMax` for every unit and SUM them — the sum must stay
   below RAM or oomd kills someone on any spike. Kernel/cgroup limits are NOT
   the usual killer.
4. **get_all() = Python-float explosion** — 215k×1024 materialises 7–9 GB
   (28 B/float + pointers vs 0.88 GB raw). Hot paths: HNSW rebuild, GPU-arm
   fallback, DAE-CPU. Fix pattern: stream blob bytes via
   `iter_for_gpu_arm` → `np.frombuffer`; endian tag `"le"` (SQLite native) vs
   `"be"` (pgvector wire, flip on GPU). Verify bit-exact against `get()`.
5. **Deploy chain must line up** — image `org.mazemaker.engine_sha` LABEL ==
   live-tree hash == preflight expected. A commit landing DURING a build makes
   the label stale → the fail-closed preflight blocks the next start. Rebuild
   with the final tree; a 20-min rebuild is cheaper than a blocked pod.

## Silent-death classes (check these first when a phase "produces nothing")

- **compute_config import class**: `from compute_config import flag as _cc_flag,
  warn_ignored_env` without `get` → any `_cc_get(...)` in the same function
  raises NameError (NREM + _phase_synthesis died this way, masked by early
  compute.toml gates). Guard: whole-file AST scan — every `_cc_*` use must be
  bound in its function scope. Run after any compute_config wiring change.
- **engine-sha fingerprint traps**: hash `git ls-files` NOT `find .` (untracked
  files poison the working-tree hash); `set -euo pipefail` + `while read` in a
  pipeline silently kills the downstream hash → CONSTANT fingerprint (always
  test content sensitivity: edit a file → hash must move); default ENGINE_SRC
  must be the PRO tree, not the free repo.
- **Silent CPU degradation**: `MM_RECALL_GPU_STRICT=1` (production quadlets)
  turns a missing CUDA into a hard RuntimeError and refuses the whole-corpus
  brute-force scan; `MM_ALLOW_CPU_RECALL=1` is the explicit opt-in for dev and
  bulk bakes where the GPU recall tensor is not needed (arm on CPU, embedding
  stays on the GPU HTTP worker).

## Verification techniques that catch real bugs (ad-hoc, not just suites)

- Mock HTTP server capturing the real outgoing request (method/path/headers/
  body) — proves auth headers, temperature, penalties actually leave the code;
  test both modes (cloud key vs local no-key) and diff the bodies.
- Fake torch via `sys.modules` (`types.ModuleType` with
  `cuda.is_available=lambda: False`) exercises GPU code paths on hosts without
  torch — through the REAL code, not a copy of its logic.
- Fake self via `types.SimpleNamespace` + unbound method call behaviour-tests
  large methods (`DreamEngine._phase_afe(fake)`) without the full object graph.
- Verify agent/worker claims against the code: a three-CRITICAL audit report
  shrank to zero after reading the actual sanitizers (token-regex + quoting
  blocked the claimed injection). Numbers over narrative.

## Deterministic extraction bakes (no invented facts)

- `MAZEMAKER_AFE_LLM_REASONING=0` (plain instruct path, no deep-think system
  prompt) + `MAZEMAKER_AFE_LLM_TEMP=0.0` (deterministic). The auto-detection
  keys on "hermes" in the model name; the env forces it regardless.
- Cloud APIs (deepseek/openai) reject llama.cpp-native `repeat_penalty` with
  HTTP 400 — drop it in API-key mode, keep frequency/presence penalties.
- Parallel bakes: engine-native `MAZEMAKER_AFE_WORKER_ID/N_WORKERS` sharding +
  `meta('afe_processed_ids')` idempotency = no duplicate work across workers
  and restarts. Watch VRAM: N workers × GPU-arm tensor can exceed the card;
  MM_ALLOW_CPU_RECALL for the arm if the bake does not need it.

## Operator workflow preferences (2026-08-07)

- Code audits are READ-ONLY: no test execution, no builds, no starts.
- Fix lists are worked point by point: audit → fix → verify → next, with a
  proof (log line, measurement, behaviour test) for every fix.
- No new tripwires: think about deploy timing (builds vs commits), deployed-vs-
  repo drift, and label/hash chains before changing anything.
- Perf claims need numbers: measure RSS/VRAM/latency before and after.

## References

- `references/2026-08-stack-fix-round.md` — the full fix round: commits,
  exact commands, diagnose-first checklists, measured numbers.
