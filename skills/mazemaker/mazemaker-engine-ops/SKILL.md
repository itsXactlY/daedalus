---
name: mazemaker-engine-ops
description: "Maintain the Mazemaker stack — OOM, config, deploy."
version: 1.0.0
triggers:
  - mazemaker oom
  - mazemaker worker memory
  - mazemaker compute.toml
  - mazemaker engine-sha preflight
  - mazemaker build deploy
  - mazemaker dream cycle repair
---

# Mazemaker Engine Ops — Maintenance Playbook

Class-level knowledge for operating and repairing the Mazemaker
neural-memory stack (Pro pod: systemd user units + podman quadlets +
pgvector + dream-worker + embedding-worker + mcp). Big-corpus scale is
~215k memories x 1024d. The stack's historical disease is SILENT
degradation: components that crash quietly or become no-ops while the
cycle "runs".

## The one root cause to hunt first: whole-corpus Python-float materialisation

`store.get_all()` on 215k x 1024d turns 0.88 GB of raw blobs into
7-9 GB of Python objects (28 B/float + list pointers) and the allocator
does NOT return that memory to the OS — the worker keeps a 10-13 GB RSS
"steady state" that is NOT a leak and NOT per-cycle growth. It killed the
worker via systemd-oomd (memory pressure >80 % in the user slice,
OOMScoreAdjust=500 makes the worker the first victim) three times a day.
Symptoms: RSS jumps to ~10 GB within minutes of the first cycle, stays
flat, oomd kills during IDLE after DAE, never inside a phase.

Kill it with chunking: stream embedding blobs in keyset chunks
(`WHERE id > ? ORDER BY id LIMIT 4096`), decode with
`np.frombuffer(payload, dtype=np.float32)` (SQLite blobs are native LE;
pgvector wire is BE + 4-byte header, needs byte-swap on device). Never
`struct.unpack` the whole corpus into float lists. Verify bit-exact
against `get()` on a small corpus; add a regression test that fails if
the streaming path disappears.

## Config surfaces: compute.toml is RENDERED, not edited

`~/.mazemaker/compute.toml` is re-rendered by the license-client from the
JWT compute claim — hand-edited keys silently vanish. Policy defaults
belong in `python/compute_config.py` `DEFAULTS` (the file IS read), and
the rendered file only overrides when present. `present(section, key)`
distinguishes "key in the file" from "default applies" — use it before
overriding constructor args so explicit callers (tests, benches) are
never shadowed.

## The NameError class (config-gate regressions)

Moving a policy knob into compute.toml (e.g. commit 02fda91) tends to
add `_cc_get("dream", key)` calls to phases whose import line only binds
`_cc_flag`. Result: the phase crashes at the first read — logged as
"phase error" and the CYCLE CONTINUES, so the phase silently becomes a
no-op while stats keep printing. After any compute_config wiring change,
run a whole-file AST scan: every `_cc_*` name used inside a function must
be bound in that function's scope or at module level. Also grep the live
journal for "phase error"/"NameError" — a worker journal from production
is the fastest way to catch the class you just introduced.

## Build/deploy chain: the fingerprint must be a pure function of the repo

- `engine-sha.sh` must hash ONLY git-tracked files (`git ls-files`) of the
  BUILD source (Pro pod: `~/projects/mazemaker-pro/python`, NOT the free
  repo — a wrong default silently hashes the wrong, unchanged tree and the
  fingerprint looks "constant").
- Bash pipeline trap: a `while read` loop as a pipeline stage under
  `set -euo pipefail` exits 1 when the last read fails, pipefail aborts
  the rest of the pipeline, and the downstream `sha256sum` hashes EMPTY
  input — a constant, meaningless fingerprint. Prefer plain
  `grep -vE` filters + `xargs -d '\n'`; no test -f loops.
- Content-sensitivity test before trusting a hash: touch a tracked file,
  hash must change, revert must restore.
- Preflight is fail-closed now: image label == live-tree hash == expected
  or mcp refuses to start. Deploy the new preflight/engine-sha binaries
  TOGETHER with the image rebuild that stamps the matching label — never
  one without the other (a mid-build commit changes the tree hash and the
  fail-closed preflight blocks the next start).
- The whole chain to keep in sync: image label (built) == live tree hash
  (committed, clean tree) == `installed.image_tag` == `desired.image_tag`.
  `installed`/`desired` are stamp files under `~/.mazemaker/`; `desired`
  is overwritten by the update server.

## GPU is a contract on the Pro pod

CPU degradation must never happen silently. `MM_RECALL_GPU_STRICT=1` (in
both production quadlets) makes the GPU arm raise when CUDA is missing and
refuses the whole-corpus CPU brute-force fallback (7 GB / 75 s get_all
scan) with a clear message; `MM_ALLOW_CPU_RECALL=1` is the explicit opt-in
for dev/tests. Non-strict environments keep the WARN path. The misleading
"GPU recall ARMED ... on cpu" INFO line is the historical lie — check the
device string before celebrating "ARMED".

## Dream-cycle repair patterns

- NREM was a silent no-op for weeks (NameError class above): verify by
  journal ("NREM phase error") — a healthy NREM logs strengthen/weaken/
  prune numbers, not just "decay scaled".
- Bridge insights are deterministic per source node: cache the last
  written content per node (lives across cycles) instead of re-inserting
  ~29k rows/cycle (95 % duplicates, flush 240 s). The first cycle after a
  cache-clear writes everything once — that is expected.
- `dream_insights` had no retention: add `prune_old_insights(keep_days)`
  to both backends, wire into periodic maintenance, default in
  compute_config DEFAULTS (not the volatile rendered toml).
- A worker stuck in "deactivating" for minutes = it received SIGTERM and
  is finishing a phase; a second SIGTERM ("send again to exit
  immediately") forces the exit. StopTimeout ~150-180 s.
- systemd-oomd (not the kernel) is often the killer: check
  `systemctl --user status systemd-oomd` and the user-slice pressure
  (oomd.conf MemoryPressureLimit), and sum MemoryHigh across ALL units —
  an oversubscribed sum (> RAM) makes oomd kill the largest consumer no
  matter the per-unit caps.

## Dream-cycle time: seconds, not hours (measured 2026-08-08, real 215k)

Cycle time fell 36 min → ~70 s. The chain of drivers, in the order they
bite after each fix:

- **REM is the dominant cost once NREM is fixed**: the batched GPU
  embedding of the sample queries costs ~190 ms/query on the 4060 Ti
  (800 samples = 152 s, 400 = 76 s, 200 = 38 s). The bridge-search time
  scales LINEARLY with the sample budget, the discovery rate does not
  (the same bridges are re-found over cycles). Halve `max_isolated` to
  halve REM: default 800 → 400 → 200. Read it from compute.toml
  `[dream].max_isolated` with the default in compute_config DEFAULTS
  (rendered toml is volatile).
- **Insight bridge-INSIGHT rows are the next flood**: ~47k bridge nodes
  mint ~30k rows/cycle even with the content-dedup cache, because Louvain
  community LABELS drift every cycle (IDs renumber — a top-3-ID signature
  still fires; community SIZES are the stable structural signature, but
  the structure itself wobbles so even sizes fire). The rows are
  redundant — REM already wrote the edges, the text row adds nothing.
  `MM_INSIGHT_BRIDGES=0` stops minting them (keeps the cluster insights,
  ~50/cycle) and the dream_insights table stops growing (14.1M plateau).
  Env wins last, also against compute.toml.
- **Env-name mismatch class**: the quadlet sets `MAZEMAKER_DAE_ENABLED=0`
  but a phase read the legacy `MM_DAE_ENABLED` → the full-corpus DAE
  compute kept running (525 s cycles, 215k vectors written) despite the
  "off" policy. A gate reading a legacy `MM_*` name must ALSO read the
  current `MAZEMAKER_*` name; verify behaviourally with BOTH names set to
  0 and with neither, not by grep.
- NREM is ~10 s once the get_all materialisation is gone (see root-cause
  section). The 38 s-era numbers in the docs were on a ~193k corpus; the
  same config on 215k lands at ~70 s.

## Benchmark corpus ingest: brute force, never single remember() calls

Operator directive (2026-08-08): corpus ingest for benchmarks must NOT go
through per-memory `remember()` — each call makes its own HTTP embed
round-trip (~220 ms bge-GPU latency), so 10k memories = 30+ min of pure
latency. The correct pattern:

1. Bulk-INSERT the texts directly into the memories table (no remember
   path, no conflict detection, no graph edges).
2. Embed in ONE pass via the batched embedding path (`embed_batch` — the
   same GPU batch API the REM phase uses for its sample queries).
3. Fill the vector columns from the batch output.

Container pitfalls for bench/integration runs: `use_cpp=True` segfaults
(EXIT 139) inside the mcp container at engine init — construct Mazemaker
with `use_cpp=False`. Before building ANY bench tooling, recall mazemaker
first for the established method ("das ist so elendig voll mit ALLEM was
du zu wissen haben musst"). Bench DBs are always isolated (`MM_POSTGRES_DB`
= a separate database, never the live one; verify zero bench labels in
the live DB afterwards).

## One-off corpus bake: Stage C via cloud API (DeepSeek fallback)

When the local Stage C chain must catch up on the WHOLE corpus once
(operator directive 2026-08-07: "deepseek einmalig, damit der komplette
Korpus wieder zu echtem production state findet, dann übernimmt llama
wieder"), use the cloud transport instead of the local llama-server:

- `afe.py` `_stage_c_completion` speaks OpenAI-compatible HTTP. With
  `MAZEMAKER_AFE_API_KEY` set it adds `Authorization: Bearer` and DROPS
  the llama.cpp-native `repeat_penalty` (cloud endpoints reject it with
  HTTP 400) while keeping frequency/presence penalties. Without the key
  nothing changes for local llama/ollama. Verified against a mock HTTP
  server (header + body captured).
- **Determinism is a directive, not a preference**: the bake runs
  `MAZEMAKER_AFE_LLM_REASONING=0` (hard off, name-independent — the
  auto-detect only matches "hermes" anyway) and `MAZEMAKER_AFE_LLM_TEMP=0.0`.
  The temp-0 degeneration that hit the local 3B ("user is a user" loop)
  does not apply to a cloud model; the prompt's negative rules ("output []
  if none", never invent) stay in force. Verify the REQUEST, not the env:
  mock server must see temperature 0.0 and no system/deep-think message.
- **Parallel whole-corpus bake**: the engine phase supports worker sharding
  (`MAZEMAKER_AFE_WORKER_ID` / `MAZEMAKER_AFE_N_WORKERS`, id % N) and is
  idempotent (`meta('afe_processed_ids')`), so N parallel
  `podman run ... --phase afe --once` workers can drain 60k+ long sources
  without duplicates. Each worker loops `--phase afe --once` until the log
  says `AFE: 0 sources`. Do NOT point this at the bench baker
  (`bake_afe_stageC_api.py` writes to the mm10m_bench DB with a ::api::C
  namespace) when the goal is production facts.
- Full recipe (podman flags, env-file with key at 0600, loop): see
  `references/afe-deepseek-bake.md`.

## Verification discipline

Ad-hoc `hermes-verify-*` scripts under /tmp that exercise the REAL code
paths (fake-torch in sys.modules for CUDA branches, mock HTTP servers for
transport tests) beat text-grep checks; keep them small and targeted.
The repo test suites are standalone runners
(`PYTHONPATH=python python3 python/test_suite.py --tags ...`) — pytest is
NOT the canonical runner (the @_testcase wrappers confuse it).

Verify WITH THE POD ENV, never bare host python: the host has no torch,
so "GPU recall init skipped" there is a dev artifact, not a signal.
Integration/behaviour checks run as `podman run --pod $POD --user 0
--device nvidia.com/gpu=all` with the pg password via
`--secret mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD`,
the license + pubkey + compute.toml mounted, and the real quadlet envs
(MM_COLBERT_ENABLED, MAZEMAKER_DAE_ENABLED, EMBED_BACKEND=http,
EMBED_CLIENT_ONLY=1, MM_RECALL_GPU_STRICT=1). Point at a test DB with
`MM_POSTGRES_DB` unless the run is deliberately against production.

## Session detail

`references/session-2026-08-07-fix-run.md` — the full P1-P10 fix run
(commits, exact quadlet lines, worker journal evidence, benchmark
history reconstruction).
`references/evermembench-rc7-comparison.md` — EverMemBench-004 harness
facts (RC7 config, data shapes, qwen2.5:3b answerer collapse, deepseek
API quirks, deterministic ANSWER-RECALL@k isolation).
`references/afe-deepseek-bake.md` — whole-corpus Stage C cloud bake recipe.
