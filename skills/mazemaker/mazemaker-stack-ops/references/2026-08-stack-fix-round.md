# 2026-08-07 — Stack Fix Round (detail)

Full context for the mazemaker-stack-ops skill. Everything here was measured on
the live Pro pod (RTX 4060 Ti 16 GB, 31 GB RAM, 215k corpus, PG-backend).

## Diagnose-first checklists

### AFE reports "0 sources" while the corpus is full
```bash
ls -la ~/.mazemaker/data/memory.db                      # 0 bytes = the shell
podman exec systemd-mazemaker-pgvector psql -U mazemaker -d mazemaker -tAc \
  "SELECT count(*) FROM memories WHERE length(content) >= 500 AND label LIKE 'auto:%'"
# 61k+ in PG, 0 sources from the phase -> store choice is wrong (SQLite-first)
```
Fix: `_phase_afe` picks `self._memory._postgres_store` when it has
`stream_long_memories_for_afe` (commit e9e9670). The phase was ALREADY written
PG-compatible (add_connections_batch/stream_long_memories_for_afe/meta exist on
both stores) — only the store SELECTION was stuck on SQLite.

### Dream-worker killed with status=137
```bash
journalctl --user -u mazemaker-dream-worker | grep -B5 'status=137'
# oomd lines: "Memory Pressure Limit", ".control markiert", "payload markiert"
systemctl --user show -p MemoryHigh,MemoryMax mazemaker-dream-worker
```
Killer = systemd-oomd (user-slice pressure >80% for >20s), NOT the kernel and
NOT the container cgroup. The kill comes in the IDLE phase after DAE, 6-14 min
after the last phase line, with RSS at the plateau. Fix both sides: engine RAM
(see get_all fix) and MemoryHigh sum < RAM (was 31.2G on 31G; lowered to 28.25G:
dream 12/16→10/14, pgvector 9/10→8/9, PodmanArgs --memory matched).

### Fingerprint looks constant
```bash
H0=$(bash .../engine-sha.sh); echo '# x' >> python/config.py
H1=$(bash .../engine-sha.sh); git checkout -- python/config.py
H2=$(bash .../engine-sha.sh)
[ "$H0" != "$H1" ] && [ "$H0" = "$H2" ] || echo "CONSTANT — pipeline broken"
```
Traps found: (1) `find .` hashed untracked files; (2) `set -euo pipefail` with
a `while read` filter loop — the loop exits 1 on EOF, pipefail kills the
pipeline, downstream sha256sum gets empty stdin → constant hash of the
empty-input text; (3) ENGINE_SRC defaulted to the FREE repo while the build
uses the PRO tree. Final pipeline: `git ls-files | LC_ALL=C sort | grep -vE
"$EXCLUDE_RE" | xargs -d '\n' sha256sum | sha256sum | awk '{print $1}'` with
the exclude list mirrored from sync-engine.sh. Deploy chain: image LABEL ==
live hash == preflight expected; a commit during a build = stale label =
fail-closed preflight blocks the pod. Fix: rebuild with the final tree.

### Phase dies silently with NameError
```bash
journalctl --user -u mazemaker-dream-worker | grep -i nameerror
```
compute_config imports must bind `get` as well as `flag`:
`from compute_config import flag as _cc_flag, get as _cc_get, warn_ignored_env`.
NREM and _phase_synthesis both imported only `flag` while reading `_cc_get`
(latent since 02fda91; masked because compute.toml gates returned before the
reads). Guard (whole-file AST scan, python):
```python
mod_binds = {a.asname or a.name for n in tree.body
             if isinstance(n, ast.ImportFrom) for a in n.names}
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        fn_binds = set(mod_binds)
        for n in ast.walk(node):
            if isinstance(n, ast.ImportFrom):
                fn_binds |= {a.asname or a.name for a in n.names}
        uses = {n.id for n in ast.walk(node)
                if isinstance(n, ast.Name) and n.id.startswith("_cc_")}
        missing = uses - fn_binds   # report
```

## Measured numbers (before → after)

- Worker RSS after arm: 12.9 GB → 1.06 GB (gpu streaming arm + lazy graph,
  commits a906fe7/38a0efc/52e8e15/94cdc80).
- Worker RSS through the first full cycle: 10.4 GB @5min → 2.3–3.55 GB stable.
- GPU arm: 12.3 GB host RAM → 1.07 GB, 6.3 s, 0.82 GB VRAM, bit-identical
  cross-checked at 3 indexes.
- DAE compute: 193.7 s with get_all materialisation → 87.3 s streaming
  (215,261 vectors, no RAM explosion).
- NREM: silent NameError crash → real work (26k strengthened / 190k weakened /
  635 pruned per cycle).
- Stage B (spaCy): B=0 for months → B=4 facts in the first working cycle
  (root cause: AFE read sources from the 0-byte SQLite).
- Test suites: upside_down 171/171, test_suite 44/44 (first green since the
  PG migration; upside_down was red since 2026-05-01 because the [15] sync
  list demanded the deleted cpp_dream_backend.py).

## Key commits (mazemaker-pro unless noted)

- a906fe7/38a0efc/52e8e15 — streaming GPU arm, on-device decode, recall/embed
  decoupling (the "1f1beb1" hash from the other agent does not exist in any
  repo — always verify commit hashes you are told about).
- 94cdc80 — lazy graph, 12.9 → 1.43 GB (load_from_store embedding skip).
- b530abb — compute.toml [recall] wiring (present()-guarded; no DEFAULTS leak).
- b66fd5f/9b2747a — synthesis + NREM compute_config NameError fixes.
- 1c99921 — SQLite iter_for_gpu_arm/count_all + chunked HNSW + DAE streaming.
- abf738c — silent degradations warn (CPU-arm DEGRADED, rerank, remote recall).
- 1dfb868 — test repairs (sources list, isolated tmp DB, cleanup to tmp DB,
  streaming-arm regression test).
- 9e321d6/db432d8 — engine-sha git-based + PRO default; fail-closed preflight;
  CDI-strip in update; llm in off-list.
- 146a157 — bridge-insight dedup cache + prune_old_insights (both backends).
- 1c7849b/2b92a6d — free-repo port of the streaming fix + CI main-v2 trigger.
- e9e9670 — PG-first AFE sources (the 0-byte SQLite root cause).
- b0184d2 — Stage C cloud-API transport (Bearer, repeat_penalty dropped in
  key-mode).
- 9e85e3c/0d64272 — MM_RECALL_GPU_STRICT (hard CPU refusal) + quadlets.
- v2-stack: be2ae07 (limits), f276260/eb8267d (synthesis env cleanup).

## Bake recipe (one-off corpus-wide AFE A→B→C with deepseek-v4-flash)

- Env: MAZEMAKER_AFE_LLM_URL=https://api.deepseek.com/v1/chat/completions,
  MAZEMAKER_AFE_MODEL=deepseek-v4-flash, MAZEMAKER_AFE_API_KEY (0600 file),
  MAZEMAKER_AFE_LLM_FALLBACK=1, MAZEMAKER_AFE_LLM_REASONING=0,
  MAZEMAKER_AFE_LLM_TEMP=0.0, MAZEMAKER_AFE_SKIP_CHUNKS=1,
  MAZEMAKER_AFE_WORKER_ID/N_WORKERS for parallel sharding,
  MM_RECALL_GPU_STRICT=1 + MM_ALLOW_CPU_RECALL=1 (arm on CPU — 8 GPU arms
  would exceed VRAM; embedding stays on the GPU HTTP worker).
- Idempotency via meta('afe_processed_ids') — workers can loop
  `dream_worker --phase afe --once` until the phase reports "0 sources".
- The afe-window.service (local llama/DeepHermes, REASONING=1) is the
  template for the podman run flags (--pod mazemaker, secrets, mounts).
- Verification: mock HTTP server capturing request headers/body proves the
  transport (Bearer present, temperature 0.0, no repeat_penalty in cloud mode;
  repeat_penalty present in local mode).
