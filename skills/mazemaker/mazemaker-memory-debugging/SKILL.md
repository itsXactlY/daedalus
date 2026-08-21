---
name: mazemaker-memory-debugging
category: devops
description: "Debug mazemaker memory engine: OOM, dream phases, synthesis."
---

# Mazemaker Memory-Engine Debugging

Use when hunting OOMs, slow phases, or silent zero-outputs in the mazemaker semantic-memory engine (`~/projects/mazemaker-pro/python/`: memory_client.py, dream_engine.py, postgres_store.py, dae.py, synthesis.py, gpu_recall.py, dream_postgres_store.py, colbert_helper.py). Companion to the user-owned `mazemaker-dream-engine` skill (which covers HOW to run the cycle; this one covers HOW to debug it).

## The golden RAM constant (read this first)

One 1024-d float32 embedding:
- 4 KB as SQLite blob / numpy array / pgvector wire bytes
- **~37 KB as Python `list[float]`** (1024 × (28 B float + 8 B pointer) + list overhead)

⇒ Any `fetchall()` of the memories table that unpacks embeddings to Python lists blows up **8–9 GB at 215k rows**. This exact pattern caused the measured 12.3–12.9 GB kernel-OOM kills (documented in-code at postgres_store.py:1007-1016 and gpu_recall.py:176-182, 275-276). Whenever a mazemaker process dies with status=137 / ~12-13 GB host RAM, look for a get_all()-funnel first.

## Debugging procedure (systematic, READ-ONLY)

1. **Find the funnel**: grep for `get_all()` call sites and any `fetchall()` on `memories`/`connections` without LIMIT. Known get_all() funnel points (SQLiteStore.get_all memory_client.py:532-556, PostgresStore.get_all postgres_store.py:969-993); line numbers verified 2026-08-07 @ HEAD b415570:
   - `_ensure_hnsw` (memory_client.py:2102; `mems = self.store.get_all()` at **:2130 — UNCONDITIONAL, even the "incremental" add path materializes the whole corpus first**, then np.asarray + hnswlib ≈ 9–12 GB peak). Fires from `_semantic_candidates` (:3022) and auto-connect (:2580) whenever GPU recall is unarmed/failed. THE strongest mid-cycle OOM candidate. git blame: line 2130 untouched since 717589b (2026-04-30) — no 2026-08-07 fix touched this path.
   - `GpuRecallEngine.load_from_store` fallback (gpu_recall.py:260) — SQLite store has no `iter_for_gpu_arm` (PG has it: postgres_store.py:1009, streaming 16 MB/chunk — the canonical fix). Introduced 1e0d590 (2026-05-18); SQLite fallback still does get_all.
   - DAE CPU/remote path (dae.py:671) — fires when `gpu._emb_tensor` is absent (RemoteGpuRecallClient, embed_provider.py:642, has no tensor attrs). Introduced 6046063c (2026-05-21).
   - `_load_from_store` (memory_client.py:1902) — `get_all(include_embeddings=not _armed)` at :1927: healed when GPU armed (94cdc80), still 7–8 GB transient + retained when not.
   - `_semantic_candidates` brute force (:3048); search_bm25/search_entity FTS fallbacks (:1114/:1157 — FALLBACK_SCAN_CAP=10k bounds the SCAN loop, NOT the get_all() materialization, which already happened); afe_facts fallback (:4838).
   - NOT a funnel: `_find_conflicts` (memory_client.py:2656) is DEAD CODE (never called) — remember() conflict detection uses indexed `find_by_label`. Don't chase it.
2. **Check GPU-arm state** (arm tiers in memory_client.py:~1560-1811): remote-via-socket → np.load cache (~2–3 GB) → build_gpu_cache auto-build (~2.5–3 GB) → load_from_store (8–9 GB). Cache fingerprint = cached rows vs COUNT(*); a growing DB makes the cache stale every start.
3. **Check the recall fallback chain** (memory_client.py:2880-2923): store.search_semantic (PG) → GPU → `_ensure_hnsw()` → get_all. One GPU failure inside REM's `recall_batch` (dream_engine.py:2158-2166) falls into per-query recall → HNSW → the 12–14 GB spike. This is why the OOM lands mid-cycle (~20–28 min), not at startup.
4. **Time the phases** against the crash: full cycle on 215k/708k ≈ 25–45 min; REM ~20–28 min; DAE runs on cycle 1 (`cycle_index==0` passes the cadence gate, dream_engine.py:2885-2888) at ~25–28 min. Correlate before blaming a phase.
5. **Bounded-by-design things** (don't chase these): `get_connections()` full-table dicts = 200–400 MB; ColBERT is per-ID via worker (`/embed_colbert`); insight `insight_rows` buffer ≤ ~16k small tuples.

## Steady state vs spike — decide FIRST

Not every OOM is the mid-cycle get_all() spike. The 2026-08-07 dream-worker kills were **steady state from startup**, not spikes:

- **Steady-state signature**: identical peak every run (12.4/12.5/12.6/12.8 GB), reached during `Mazemaker.__init__`, still high 30+ min after cycle end (oomd measured 12.5 GB "current" while the worker was idle in its sleep loop). Cause: `_load_from_store()` materialising the corpus as Python objects — RssAnon 10.4 GB inside __init__ AFTER the GPU arm completed (commit 94cdc80 message). 215k × (embedding `list[float]` 5.7–7.3 GB + content str 10–25 KB → 2.2–5.4 GB + connections 0.2–0.4 GB) ≈ 9–13 GB, **never evicted** (no eviction path in memory_client.py).
- **Spike signature**: mid-cycle (~20–28 min), drops back after the phase. Funnels: `_ensure_hnsw` (:2130), gpu_recall load_from_store fallback (:260), DAE (dae.py:671).
- Discriminator: systemd logs "Consumed ... X memory peak" after a kill; compare with `journalctl -u systemd-oomd` "Current Memory Usage" vs when the cycle ended. Also `_gpu_ppr_adj` rebuild churn (200–400 MB) is noise, not the 12 GB.

**IMAGE-STALENESS TRAP (check before blaming source)**: the deployed container image may predate the fix commit. Compare:
```bash
podman image inspect localhost/<img>:<tag> --format '{{.Created}}'   # UTC
git log --format='%h %ad %s' --date=format:'%Y-%m-%d %H:%M' -5
```
2026-08-07: fix commit 94cdc80 (21:12 UTC) landed ~47 min AFTER the image build (20:25 UTC) → every run that day used pre-fix full-load code while source already looked fixed. A run log showing NEW-code strings ("streamed ... no host-side float conversion") does NOT prove the whole image is current.

**Residual post-94cdc80**: `GpuRecallEngine._contents/_labels/_ids` still holds 215k content strings (≈ 2–5.5 GB at 10–25 KB avg) — the engine needs them to render recall results and serve the recall socket. Next optimization target if the residual matters: fetch content per-result from PG instead of retaining it.

## oomd kill mechanics (host overcommit)

systemd-oomd kills the largest/designated cgroup when a PARENT slice exceeds pressure — not when a unit hits its own limit. Evidence (2026-08-07, dream-worker killed 3× at 12.5–12.6 GB with a 16G limit it never touched):

- `journalctl -u systemd-oomd`: "Marked ... for killing due to memory pressure for /user.slice/user-1000.slice/user@1000.service/app.slice being 83.52% > 80.00% for > 20s with reclaim activity" + "Current Memory Usage: 12.5G" + the unit's own "Memory Pressure Limit: 0.00%" (ManagedOOMMemoryPressure unset — the 80% comes from the parent slice's default; drop-in sets DefaultMemoryPressureLimit=80%, DefaultMemoryPressureDurationSec=20s).
- Victim selection: OOMScoreAdjust (dream-worker **500** = explicit "sacrifice first", all other units 200) + anon dominance (12.5G anon, Pgscan 1.76M) vs pgvector whose 9G High is mostly shared_buffers + page cache (reclaimable → low pressure contribution).
- Thrash amplifier: unit `MemoryHigh=12G` with container `--memory-swap=16g == memory` (NO swap): 12.5G anon exceeds High → continuous reclaim with no swap escape → drives the parent slice over 80 %.
- Arithmetic: sum of MemoryHigh across CONCURRENTLY-running units must stay under RAM − desktop (~4–11 GB observed). 2026-08-07: High sum 31.2 GiB (33.5 GB), Max sum 39.5 GiB (42.4 GB) on 31 GiB host → structurally overcommitted. The operator's budget comment lives in `mazemaker-pgvector.container` [Service] — read it before changing any limit. Per-unit: `systemctl --user show <unit>.service -p MemoryHigh -p MemoryMax -p OOMScoreAdjust`.
- **Limits correction alone is NOT sufficient**: 12.5G anon inside an 8G-High cgroup = reclaim thrash, kill only later. Structural fix (don't hold the corpus as Python objects) + sum correction together.

## Host-level swap deadlock (NOT an engine bug)

2026-08-10 desk: pod felt deadlocked (dream-worker cycles 3x slower, every embed call stalling), but `pg_stat_activity` was clean (0 lock waits) and no engine OOM. Root cause was HOST-level: `vm.swappiness=133` (runtime-set, NO /etc/sysctl.d entry — leftover tuning experiment) made the kernel evict HOT pod services to swap even with 14 GB free RAM. embedding-worker (865582): 1.78 GB VmSwap / 151 MB RSS (~92 % paged out); MCP/NMM server (883756): 1.42 GB; 5x claude + 3x node "2.1.22x" also swapped. Total swapout since boot 229M pages (~900 GB); pswpout active at 2.4 MB/s.

Vicious cycle: every dream-worker embed request hit page faults → cycles 3x slower → more pressure. Looks like a mazemaker bug but is NOT — the engine is the victim, not the cause.

Diagnostic sequence (READ-ONLY, in order):
1. **Rule out DB lock first**: `SELECT * FROM pg_stat_activity WHERE state='active'` + lock-wait check. Clean → not PG.
2. **Check swap churn**: `vmstat 1 30` (active pswpout) + `grep pswp /proc/vmstat` (totals since boot).
3. **Per-process swap**: `grep VmSwap /proc/[0-9]*/status | sort -k2 -n` (or awk), correlate with `ps -o pid,rss,cmd`. VmSwap ≈ RSS means a hot process is paged out.
4. **Find the rogue runtime sysctl**: `sysctl vm.swappiness` vs `grep -r swappiness /etc/sysctl.d/` — mismatch = runtime-set, no persistence (e.g. `sysctl -w` experiment from a past session).
5. **Fix persistently**: `sysctl -w vm.swappiness=10` + write `/etc/sysctl.d/99-swappiness.conf`. Normal swap usage is fine; the anomaly is eviction of hot services while RAM is free.

## PG retention + config quirks (2026-08-10 plan findings)

- PG16.13 container gets ALL settings via `postgres -c` args (shared_buffers=3GB, effective_cache_size=7GB, ...) — **ALTER SYSTEM would be lost**; change args in the container unit, not in SQL.
- `autovacuum_count=0` on ALL tables (insert-dominant, few dead tuples) — don't expect autovacuum to manage growth.
- **NO retention code in v2-pod** (0 grep hits) → `connection_history` (16M rows / 2.16 GB) + `dream_insights` (14.3M rows / 2.36 GB) grow unbounded. Retention (>90d DELETE + VACUUM FULL, then daily cron + monthly partitioning) + effective_cache_size 7→16GB + parallel workers 2→8 are the open work (plan:resource-stabilization-2026-08-10).

## Synthesis "30 clusters → 0 proposals"

Check `clusters_synthesised` in the stats to localize:
- 0 → anchors died before the LLM: NREM prunes `derived:cluster` memories at a **5-min TTL** (dream_engine.py:1859) but Synthesis queries a **3600-s window** (dream_engine.py:3427, 3434-3443) → `continue` at 3477-3478.
- >0 but proposals=0 → AFE-member gate (`label LIKE '%::afe::%'` + `min_facts=3`, dream_engine.py:3491/3428) or the LLM chain (synthesis.py): missing model → `ollama run` CLI pull → 60 s timeout → `[]`; no `[...]` in output → `[]` (line 256); items without `evidence_indices` dropped (line 274); `min_evidence=2` (line 354); `min_confidence=0.5` (line 383).

## Insight-flush slowness

RAM-safe buffer; the time sink is write amplification: per-edge `connection_history` rows (24k/cycle → 3M/day; fixed to 1 summary row via `MAZEMAKER_DREAM_HISTORY_PER_EDGE=0`), dream_insights explosion, SQLite WAL growth, PG FK violation in the derived-cluster prune.

## Verification tips

- The engine's own code comments carry measured numbers (12.3 GB, 18.2M history rows, 9.1M rows/day) — read the comments before re-measuring.
- For RAM math: count rows × 37 KB for Python-float embeddings, × 4 KB for np/blob, × ~250–300 B for small connection dicts. Exact on 215,132 rows × 1024-d: 32 B/elem = 7.05 GB, 36 B/elem = 7.93 GB; numpy float32 copy 0.88 GB; hnswlib data+links ≈ 0.97 GB; chunked 4096-row page = 16.8 MB raw bytes.
- **Commit map for get_all paths** (verified 2026-08-07, mazemaker-pro):
  - `_ensure_hnsw` get_all :2130 — introduced 717589b (2026-04-30, V3.1 squash), **never fixed** (blame still 717589b at HEAD b415570).
  - gpu_recall `load_from_store` :260 — introduced 1e0d590 (2026-05-18); PG arm fixed by a906fe7 (06:40, streaming; 12.3 GB documented) → 38a0efc (10:31, on-device decode; measured 1.07 GB) → 52e8e15 (10:52, recall/embed decouple); SQLite arm fallback still get_all.
  - `_load_from_store` :1927 — fixed by 94cdc80 (21:12, include_embeddings flag; 12.9 GB → 1.43 GB).
  - DAE CPU path dae.py:671 — introduced 6046063c (2026-05-21), never fixed.
  - The hash "1f1beb1" cited for the GPU-native decode does NOT exist in either repo — the commit is **38a0efc**. Cross-check any cited hash with `git rev-list --all | grep <hash>` before trusting it.
- **"Is path X still broken?" audit**: `git blame -L <line> -- <file>` on the get_all line answers in one shot (blame showing 717589b = untouched by all fixes); verify pre-fix state with `git show <fix>^:<file>`.
- **Chunking infra (K3)**: `fetchmany` has ZERO occurrences in mazemaker-pro/python. SQLite has NO paged vector stream: no `iter_for_gpu_arm`, no `search_semantic`, no `count_all` (PG has all three: postgres_store.py:1009/896/1084). Only float-free SQLite corpus paths: np.load gpu_cache (stale-prone via fingerprint) and build_gpu_cache (fetchall of raw blobs, ~2.5–3 GB, not chunked). A keyset-pagination fix à la PG would take 12.9 GB → ~2–3 GB host peak.

## References

- `references/dream-worker-oom-2026-08-07.md` — full candidate ranking with file:line, RAM math, synthesis filter chain, phase timings from bench logs.
- `references/dream-worker-steady-state-2026-08-07.md` — THESE-E-Verifikation: Steady-State vs Spike, Image-Staleness-Timeline (Image 20:25 UTC vs Fix 21:12 UTC), RAM-Halte-Karte, oomd-Kill-Beweiskette (Slice 83–87% > 80%, OOMScoreAdjust 500), Limits-Arithmetik (High 31.2 GiB / Max 39.5 GiB vs 31 GiB), post-Fix-Residual (Engine-_contents).
- `references/getall-funnel-verification-2026-08-07.md` — THESE-A-Audit: Call-Site-Inventar (heiß/kalt, beide Repos), RAM-Rechnung je Pfad, Git-Einführung der get_all-Pfade (717589b/1e0d590/6046063c/a906fe7/38a0efc/52e8e15/94cdc80), Chunking-Infrastruktur-Audit (fetchmany=0).
