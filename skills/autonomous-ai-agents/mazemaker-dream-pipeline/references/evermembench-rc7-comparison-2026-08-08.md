# EverMemBench 1:1 vs RC7 — comparison recipe (2026-08-08)

Operator goal: "vergleichen wir 1:1 ggü. RC7 den bench" — the current engine
(all 2026-08-08 fixes) against the 1.0.0-RC7-era EverMemBench result, same
corpus, same questions, same metric.

## RC7-era facts (from mazemaker memories + pipeline scripts)

- Leaderboard position (published 2026-07-05, mazemaker.online hero):
  own harness, same protocol (gpt-4.1-mini + gpt-4.1-nano, PG corpus
  10,388 mems / 72,943 edges). 10-cat mean 46.4 vs EverMemOS leaderboard
  mean 44.6 (+2.2pp, without ever seeing their corpus). Budget answerer
  deepseek-v4-flash: 51.1 (52.6 pooled) — explicitly NOT leaderboard-
  comparable. k=30 fetch: 304/626 = 48.56% pooled / 46.78% mean.
  Five shipped engine fixes as receipts: tsquery phrases (0 errors instead
  of 145/626), pool-checkout, event-time API, supersedes no-op, REM-flood.
  (memory 955030, `fact:evermembench-leaderboard-46.4-vs-44.6-2026-07-05`)
- Canonical bench numbers (memory 841698, `fact:mazemaker-benchmark-numbers-canonical`):
  LongMemEval oracle R@5 0.8426 / R@10 0.9000 (500q, 25k haystack);
  hop-2 R@10 0.00→1.00; shuffled-edge negative control 1.00→0.27;
  post-dream synthesis 0.00→0.43; supersession 0.03→0.33; cross-session
  continuity 0.06→0.62; lean retrieval 0.60 vs skynet 0.42 R@5; gemma3:270m 18/20.

## RC7 engine configuration (from `benchmarks/external/run_pipeline.sh` + `dream_evermembench.py`)

- Pipeline stages: FLOOR (add+search+answer+evaluate) → DREAM
  (`dream_evermembench.py`, N_CYCLES=4) → COMPLETE (search+answer+evaluate).
- Answerer: qwen2.5:3b via ollama (local, `host.containers.internal:11434`).
- Judge: deepseek-v4-flash via NVIDIA NIM (`integrate.api.nvidia.com`, NVKEY).
- Engine knobs (dream_evermembench.py): `retrieval_mode="advanced"`,
  `use_hnsw="auto"`, `lazy_graph=True`, `think_engine="ppr"`, `rerank=True`,
  `retrieval_candidates=512`, `channel_weights={"colbert": 1.5, "dae": 1.0}`.
- CLI: `eval.cli --dataset dataset/004/dialogue.json --qa qa_004.json
  --system mazemaker --top-k 10 --user-id <stage>`; dataset 004 (626 QA).
- Local data present at `benchmarks/external/data/evermembench/`
  (dialogue_004.json, qa_004.json, QAR_1m.json).

## 1:1 comparison plan (the independent variable = engine internals only)

1. Reproduce the RC7 engine config EXACTLY (advanced, colbert 1.5 + dae 1.0,
   rerank, ppr, 512 candidates, 4 dream cycles) on the CURRENT code (all
   fixes: mode kwarg, supersedes paging, get_all fix, streaming, ...).
   NOTE: colbert/dae are policy-OFF in production envs now — for the bench
   the channels must be re-enabled (bench isolation, not production).
2. Same corpus (004, 10,388 mems / 72,943 edges in the isolated
   `evermembench` PG DB), same 626 questions, same top-k 10 / k=30 metrics.
3. Compare: RC7 numbers (46.4 mean / 48.56 pooled at k=30) vs current.

## Decision points for the operator before running

- Full LLM run (exact RC7 protocol): needs ollama up (qwen2.5:3b) + NVKEY.
- Retrieval-only variant (ANSWER-RECALL@k substring diagnostic, deterministic,
  no LLM): isolates retrieval changes without the LLM components. The
  evermembench.py harness itself flags that substring R@k is a DIAGNOSTIC,
  not a valid EverMemBench score (87% of GT answers are paraphrased) — a
  VERIFIED score needs the benchmark's own answer-generation + LLM judge.

## Execution learnings (2026-08-08, harness actually built & smoke-tested)

These are the real obstacles hit when assembling the isolated bench, all
durable and re-checkable:

- **`use_cpp=True` SIGSEGVs the mcp container (EXIT 139 / Segfault)** during
  `Mazemaker(...)` construction — the C++ bridge (`libneural_memory.so`)
  crashes at init inside the container image. Symptom: the ingest log ends
  right after the licence line with `EXIT=139` and the DB stays at 0 rows.
  Fix: `use_cpp=False` in ALL pod-container bench/audit scripts (the Python
  stores give the same retrieval semantics; the bench measures the engine,
  not the C++ accelerator). Isolate first with a 5-line construct+remember
  smoke before blaming the data.
- **`CREATE DATABASE evermembench` via `podman exec <POD>` fails** — `podman
  exec` takes a CONTAINER name, not the pod name; the "create" silently
  no-ops, then the ingest container opens a nonexistent DB and the count is
  0. Use the actual container: `podman exec systemd-mazemaker-pgvector psql
  -U mazemaker -c "CREATE DATABASE evermembench"`.
- **Ollama cloud models require a subscription**: `deepseek-v4-flash:cloud`
  → `{"error":"this model requires a subscription, upgrade for access..."}`.
  Don't route the judge through Ollama cloud — use the real deepseek API
  instead (key in `~/.hermes/config.yaml` `providers.deepseek.api_key`,
  base `https://api.deepseek.com/chat/completions`). Never print the key;
  pass it as an env and read it in the container.
- **deepseek-v4-flash judge API quirk**: at `max_tokens<=30` the model
  returns EMPTY content with `finish_reason: length` (it burns the token
  budget before emitting the verdict) — at `max_tokens≈60` it reliably
  returns `CORRECT`/`WRONG`. The name `deepseek-v4-flash` IS a valid API
  model (an API error message lists it alongside deepseek-v4-pro). Extract
  the verdict by substring (`startswith("CORRECT")`), not exact match.
- **Isolated DB proof for the operator**: state the DB, don't just claim it —
  grep the script's `MM_POSTGRES_DB` line + `SELECT count(*) FROM memories
  WHERE label LIKE 'bench004%'` on the LIVE DB (must be 0) shows the bench
  never touched production.

