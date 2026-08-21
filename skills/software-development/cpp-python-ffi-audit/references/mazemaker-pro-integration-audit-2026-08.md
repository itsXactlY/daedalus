# Mazemaker-pro — Integration Stream Audit Findings (2026-08-07)

Project: `/home/alca/projects/mazemaker-pro` (Python memory engine + optional C++ `libmazemaker.so`).
Audit mode: READ-ONLY, static analysis. Nothing built/run. Report was in German (parent-specified format).
Purpose of this file: cross-reference before re-auditing or fixing — avoid duplicate findings, verify fixes.

Note: on the audited host there was NO `build/` dir and NO `fast_ops*.so` — the C++ path was not even
built; all Python fallback tests pass while the entire C++ layer is untested in practice.

## CRITICAL (7)
1. `src/core/c_api.cpp:136-151, 185-201` — `out.embedding` points into local `mem_results` vector → dangling on return; header contract "valid until next call" broken.
2. `src/core/c_api.cpp:31-52, 65-80, 104-152, 177-201` — no try/catch around adapter calls; `HopfieldLayer::store/retrieve` (`src/memory/hopfield.cpp:27-30, 115-117`) throws `std::invalid_argument` on dim mismatch → exception over `extern "C"` → std::terminate → whole Python process SIGABRT. Python-side `except: pass` (memory_client.py:1910-1914, 2210-2214, 2886-2897) is useless against this. `cpp_bridge.py:196-213` never validates `len(embedding)` vs adapter dim.
3. `src/core/memory_adapter.cpp:110, 174-179, 286, 292-293, 303` + `src/core/c_api.cpp:224` — ±1 ID-offset: graph node IDs and memory IDs both start at 1 and run in sync, but code assumes `memory_id+1` → self-loops in store() auto-edges, think() starts at wrong node, returned IDs off by one. `mazemaker_add_edge` passes IDs through WITHOUT offset (memory_adapter.cpp:478) — internally inconsistent.
4. `tools/dashboard/live_server.py:1406-1413, 1371-1381, 1431` — unauthenticated `/ws/terminal` spawns `$SHELL` (pty) on default `0.0.0.0:8443`; unauthenticated `/api/restart` (systemctl); no Origin checks on `/ws/stream`.
5. `tools/dashboard/live_server.py:1279`, `tools/dashboard/generate.py:277` — `json.dumps(current_data)` inlined into `<script>` without `</` escaping → stored XSS via memory labels (user data).
6. `tools/dashboard/generate.py:301-310` — `--serve` mode: `SimpleHTTPRequestHandler` + `os.chdir(output dir)` on `0.0.0.0` → whole directory (default `~/`) exposed, directory listing, no auth.
7. `tools/production_upgrade.py:298-321` — dedup rebuild `CREATE TABLE connections_dedup AS SELECT MIN(id), source_id, target_id, MAX(weight), edge_type, MIN(created_at)` drops ALL other columns (event_time, valid_from/to, last_activated, activation_count, reason, changed_at, dream_session_id) → bi-temporal typed-edge data silently destroyed; new UNIQUE index also forbids legitimate bi-temporal duplicates.

## HIGH (6)
8. `python/memory_client.py:2885-2904` — C++-retrieve path is the FIRST candidate source in `_semantic_candidates`; it only searches the in-memory C++ copy (10k capacity) → recall blindness on 193k corpora; `_cpp_id_map.get(cpp_id, cpp_id)` can emit phantom IDs; `return out` skips the full Python scan.
9. `src/graph/knowledge_graph.cpp:554-563` — `prune_weak_edges` removes only one direction → asymmetric graph (dangling reverse edges; traversal behaves direction-dependent).
10. `sync.sh:20-26` — copies a file list that misses `_lib_finder.py`/`lstm_knn_bridge.py`/`config.py` (→ ModuleNotFoundError in plugin, silent C++ deactivation) and lists non-existent `mssql_store.py`/`dream_mssql_store.py`.
11. `tests/test_suite.py:131-137, 263-264` — runs against the PRODUCTION DB (`~/.mazemaker/engine/memory.db`) and writes into it (`Mazemaker()` without db_path).
12. `scripts/import_mazemaker_runtime.py:34, 203-208`, `scripts/import_beam_to_pg.py:41` — `DROP SCHEMA ... CASCADE` without dry-run/confirm; DSN rewritten via `str.replace("dbname=mazemaker", ...)` silently fails on variant DSNs → could drop schema in the WRONG (production) database; the two scripts share `conv_N` schemas destructively (one drops whole schema, other only `memories` → orphan connections).
13. `src/core/c_api.cpp:506-550` + `src/memory/knn.cpp:156-164` — `nm_knn_search` never validates caller `embed_dim` vs engine `embed_dim_` → OOB read in `std::copy`; `MemoryCandidate.embedding` is a raw pointer into the Python ctypes buffer.

## MEDIUM (10)
14. `python/_lib_finder.py:18-45` — `exists()` check only; corrupt/wrong-arch .so → raw OSError outside memory_client's guarded init; `_louvain_get_lib` (cpp_bridge.py:375) bypasses the `shared_cdll` cache.
15. `python/cpp_bridge.py:170-174` — `initialize(dim, hopfield_capacity, episodic_capacity)` silently ignores the capacity args (C API cannot set them); `dim` not stored → no length validation possible.
16. `src/core/memory_adapter.cpp:33` + `src/memory/memory_manager.cpp:340, 363-364` — TWO Hopfield instances (adapter + manager, different capacities, diverge on eviction); `hopfield_.top_k()` result computed and discarded (dead code).
17. `src/core/memory_adapter.cpp:474-479` — `edge_type` parameter `(void)`-discarded; all edges become `Similar`.
18. `src/core/memory_adapter.cpp:383-386` — `episodic_count`/`semantic_count` hardcoded 0 in stats.
19. `include/mazemaker/simd.h:613-629` + `src/simd/simd_engine.cpp:68-71` + `CMakeLists.txt:41-43, 95` — claimed runtime dispatch doesn't exist (compile-time only) → `-march=native` builds SIGILL on other CPUs; `HAS_AVX2`/`HAS_AVX512` CMake vars are dead; `install(DIRECTORY include/neural ...)` points at non-existent dir (real dir: `include/mazemaker`).
20. `python/fast_ops.pyx:24-37, 42-75, 294-331` — `boundscheck(False)` cosine kernels with no `a.shape[0]==b.shape[0]` guard → OOB read; `hash_embed` (line 128) repeats a 32-byte SHA256 pattern for dim>32 → only 32 independent dims; `temporal_decay` no clamp on future timestamps (score > 1).
21. `python/dream_engine.hpp` (1501 lines, NOT built by anything) — unconditional `#include <immintrin.h>` (ARM build breaks); VP-Tree `build()` stores `indices[mid]` as pivot but partitions around random `pivot_idx` (line 374-413) → inconsistent tree, false negatives; `bfs_with_similarity` ignores query/sim args; PPR damping nullified by normalization (286-323); `CSRGraph::build` no `dst < n` check → OOB write.
22. `src/memory/memory_manager.cpp:47-52, 172-177`, `src/memory/hopfield.cpp:270-276` — pointer-return APIs (read/get_pattern) release locks before caller uses pointer → UAF race with evict/remove/merge; latent (C API disables threads, c_api.cpp:40-42).
23. `src/memory/memory_manager.cpp:24-26`, `src/memory/hopfield.cpp:33-35`, `hopfield.h:92`, `memory.h:72` — capacity 0 → infinite eviction loop + `occupancy()` div-by-zero.
26. `migrate.sh:90, 152-166, 620, 661` — `cp -a` backup of WAL DB (inconsistent snapshot, self-documented in production_upgrade.py:81-99), destructive DELETEs without dry-run.
28. `python/test_integration.py:138`, `python/test_suite.py:413`, `tests/test_upside_down.py:805` — C++ symbol tests use legacy path `~/projects/mazemaker-adapter/build/...` (not `<repo>/build`); upside-down sync test requires non-existent `cpp_dream_backend.py` → suite is red.

## LOW (5)
24. `src/memory/vsa.cpp:69-82` — `shift % n` with n==0 → SIGFPE.
25. `src/core/memory_adapter.cpp:292-293` — `start_id + 1` wraps to 0 at UINT64_MAX (`think(-1)` via ctypes).
27. `tools/dashboard/live_server.py:244-267` — node query loads ALL rows before Python-side `[:NODE_LIMIT]`.
29. `src/graph/knowledge_graph.cpp:71-75` — `add_edge` silently returns false for missing nodes; batch API reports only "0 added" — masks ID bugs.
30. `src/core/c_api.cpp:530-531` — timestamps: C-API converts seconds→µs but clients sending µs produce `temporal_decay > 1`; NaN/negative `static_cast<uint64_t>` UB.

## Test-gap highlights (for re-audit streams)
- No test runs the C++ path (`use_cpp=False` everywhere in tests/test_upside_down.py).
- Missing-lib fallback untested (importing the wrapper module ≠ loading the .so).
- No dim-mismatch crash test; no phantom-ID test with C++ enabled; no prune_weak_edges asymmetry test.
- c_api.cpp not covered by any C++ test (CMake test list: test_vector_ops, test_hopfield, test_graph only).
- AVX2/AVX-512 kernels never executed (portable build flags).
- postgres_store.py, dream_postgres_store.py, gpu_recall.py, embed-server.py: no tests.
- production_upgrade.py, live_server.py, generate.py, migrate.sh, sync.sh, import scripts: zero automated tests.
