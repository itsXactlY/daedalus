# Parallel Read-Only Audit — mazemaker-pro — 2026-08-07

Third application of the parallel-readonly-audit methodology. 3 streams (HOCH bottom-up persistence/retrieval,
RUNTER top-down API/engines, INTEGRATION C++/bridge/tooling), 90 findings, then a follow-up 3-stream READ-ONLY
deployment/OOM investigation. Engine: Python memory system on Podman/Quadlet stack, 215k-memory PG corpus.

## The 3 refuted CRITICALs (verification wins)

1. **FTS5 MATCH injection (memory_client.py:1088/1139) — REFUTED.**
   `_sanitize_fts_query` (428-446) tokenizes via `re.findall(r"[A-Za-z0-9_][A-Za-z0-9_/\-]{1,}")` then wraps
   every token in quotes. FTS5 metacharacters (`" * + ^ ~ ( ) :`) cannot survive the regex; inside a quoted
   FTS5 phrase all operators are literal. `-` IS an FTS5 operator but only outside quotes — inside the phrase
   it is literal. No injection vector, worst case a meaningless phrase like `"a-"`.

2. **Postgres tsquery injection (postgres_store.py:1796/1837) — REFUTED.**
   `_sanitize_tsquery_terms` (1751-1760) uses the same token regex; tsquery operators (`& | ! <-> <N> :`)
   are filtered. CRITICAL asymmetry the workers got wrong: `-` is an operator in FTS5 but NOT in tsquery
   (it is part of the lexeme). Entity path (1830-1834) builds `(<-> phrase)` only from regex tokens.

3. **NUL-byte truncation (cpp_bridge.py:191-194 vs mazemaker.py:480) — NOT a live bug.**
   The NUL checks sit exactly at the only c_char_p boundary (`MazemakerCpp` is optional, use_cpp=True).
   The active path is SQLiteStore.store (memory_client.py:469) which stores NUL intact in TEXT.
   Remains only as a defense-in-depth wish (central validator), severity LOW.

**Verified surviving HIGH:** Canonicalization sweep (memory_client.py:343-347) swaps ALL `source_id > target_id`
rows without an edge_type filter — directed edges (supersedes/causal) with source>target get inverted.
Fix: `AND edge_type IN ('similar','bridge')`.

## OOM / RAM-bloat diagnosis methodology (the 12.9 GB worker)

**Who killed it: systemd-oomd, not kernel, not cgroup.** journalctl signatures:
`".control marked (user@1000 90.18 %)"`, `"payload marked (app.slice 85.33 %)"`, `"Avg10 86.15"`,
`"with reclaim activity"`. oomd kills the LARGEST consumer under ambient memory pressure >80% for >20s —
the worker (OOMScoreAdjust=500) died at 12.9G under a 16G limit while the host slice sat at 85% pressure.
3 kills all came in the IDLE phase 6-14 min after the last phase log line — the phases themselves ran in seconds.

**Leak vs steady-state:** RssAnon showed two large anon regions (5741 + 5199 + 815 MB), growth 61 MB/75s.
That is load-time materialization held permanently, not a cycle leak. The kill clock follows the pressure,
not the workload.

**The classic Python killer: `get_all()` materialization.** 215k × 1024-dim:
- Python float objects: 1024 × (28 B float + 8 B list pointer + overhead) ≈ 8-9 GB
- + np.asarray copy (0.9 GB) + hnswlib internals (2.5-4 GB) → peak 12-14 GB
- Three live sites: HNSW full rebuild (memory_client.py:2069 from :2913-2917), GPU-arm fallback
  (gpu_recall.py:260), DAE bulk (dae.py:671). Raw bytes are only 880 MB — 10× that means Python objects.
- Fix pattern: chunked/streaming loads, iter cursors, wire-bytes-to-device decode
  (`torch.frombuffer(payload, dtype=torch.uint8).to(device).view(-1,4).flip(-1).contiguous().view(torch.float32)`
  for pgvector big-endian) instead of Python float lists.

**Bisect checkpoint recipe:**
- 1 phase per FRESH process (accumulated allocations confound)
- cgroup `memory.peak` / `memory.current`, not only /proc/self/status
- CP order: after import → after backend init → BEFORE GPU arm → AFTER GPU arm (dies here often) →
  after engine init → per phase → IDLE plateau: memory.peak every 30s for 15 min after last phase
- Object attribution at peaks: /proc/<pid>/smaps_rollup + tracemalloc snapshot
- Isolate the machine: close desktop, temporarily stop systemd-oomd, else the killer fires mid-measure

**Other verified findings:** Synthesis "30 clusters, 0 proposals" = Ollama never actually called (0 lines in
worker journal; the "HTTP 200" was only the /api/tags probe). Filter chain: TTL mismatch (NREM prunes
derived:cluster with 5-min TTL at dream_engine.py:1859-1861 vs Synthesis's 3600s window at :3427),
AFE min_facts=3, `ollama run` CLI-pull timeout on a non-existent default model (alibayram/smollm3),
parse gates (no `[...]`, missing evidence_indices, min_evidence=2, min_confidence=0.5).
Insight flush 95% = write amplification (connection_history 24k rows/cycle → 18.2M in 6 days), RAM-safe.

## Benchmark model-history reconstruction (which ollama model ran where)

Technique for "which model produced result X":
1. Git log: `git log --all --oneline --grep='ollama\|qwen\|bench' -i` — commit subjects carry model swaps
   (found: `ada2955 feat(afe): Stage C over HTTP, Bonsai-4B instead of DeepHermes`,
   `59b65d4 engine: synthesis Ollama transport — HTTP first, CLI fallback`).
2. Result artifacts: `grep '"gen_model"' results/*.json` (evermembench JSONs: 3× qwen2.5:3b),
   `run_arms_ollama.sh` in the archived upstream bench repo (`~/.archive/EverMemBench/`) documents the
   exact local models in its log lines.
3. `ollama list` — tags like `qwen2.5:3b-128k` (pulled 7 weeks ago, matching the bench window) vs
   `qwen2.5:3b` — timestamp of the pull correlates with the run window.
4. Distinguish retrieval numbers from LLM numbers: "R@5 0.9000" was skynet retrieval (BGE-M3 + HNSW +
   multi-signal, no LLM); the ssp-lift 0.2667→0.3333 was qwen2.5:3b in the parallel API baker; the
   "GOATED" AFE Stage C model was DeepHermes-3-Llama-3-3B-Preview (deep-think mode), NOT qwen.

## Deployment quick hits (Podman/Quadlet stack)

- Limits-sum arithmetic lies: 51.5G MemoryMax / 40.3G MemoryHigh summed on a 31G host — recompute after
  any limit change; the pgvector unit comment was stale.
- `OOMScoreAdjust=500` on a worker = "preferred oomd victim" — deliberate, but it means ambient host
  pressure kills the worker before anything else.
- A `dae-off.conf.disabled-20260806` rename silently RE-ENABLED an unwired feature that was the documented
  OOM amplifier — check .disabled drop-ins during audits.
- `ExecStartPost=try-restart` is robust (non-fatal, no-block) but not idempotent: worker crash-loop →
  mcp restart spiral with double GPU-arm spikes. Boot-race fix = `After=embedding-worker` on mcp, not a post hook.
- Missing `org.mazemaker.engine_sha` image label = preflight staleness gate silently dead (fail-open).
