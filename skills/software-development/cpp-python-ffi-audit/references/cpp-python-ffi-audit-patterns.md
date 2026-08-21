# C++ ↔ Python FFI Audit — Recurring Bug Patterns

Condensed pattern bank from audits of ctypes/pybind hybrid projects (validated 2026-08 on mazemaker-pro).
Each pattern: symptom → root cause → quick check.

## 1. C++ exceptions crossing `extern "C"` → std::terminate
```cpp
// BAD: no try/catch in the C-API function
MAZEMAKER_API uint64_t mazemaker_store(...) {
    ...
    return adapter->store(embedding, ...);   // throws std::invalid_argument on dim mismatch
}
```
- Python `try/except` around the ctypes call CANNOT catch it → SIGABRT of the whole process.
- Check: every `MAZEMAKER_API` function has try/catch; wrapper validates lengths BEFORE the call.
- Grep: `std::invalid_argument`, `throw` inside classes reached from the C API.

## 2. Returned pointer into function-local vector
```cpp
auto mem_results = adapter->retrieve(cue, k);          // local
out.embedding = const_cast<float*>(r.embedding.data()); // dead on return
```
- Header contract "valid until next call" is fiction. Check ownership of every returned pointer.

## 3. ID-space offset drift between subsystems
- Two subsystems with independent counters (graph nodes `next_node_id_ = 1`, memory IDs `next_id_ = 1`).
- Code adds ±1 offsets assuming a relationship that doesn't exist (`sim_id + 1`, `node_id - 1`).
- Symptom: self-loops `(n,n)` in auto-edges, off-by-one IDs returned to Python, `add_edge` silently
  dropping edges because the target node doesn't exist.
- Check: simulate actual ID values for stores 1..3 by hand; verify `add_node`'s returned ID vs memory ID.

## 4. ctypes struct drift
- `c_size_t` vs `c_uint64`, missing padding after float fields, `char[256]` vs `c_char*256`.
- Check: `_fields_` in Python vs struct in header, field by field, including alignment.

## 5. Length/dim mismatch = OOB read in C++
```cpp
std::copy(candidates[i].embedding, candidates[i].embedding + embed_dim_, ...); // embed_dim_ != caller's embed_dim
```
- Every `dim`/`count`/`k` from the caller must be validated against the engine's internal dims.
- SIMD kernels (`cosine_similarity(a, b, n)`) read `n` floats with no length knowledge — nullptr or
  short buffers = crash/UB. Empty `vector::data()` is often nullptr; `n==0` guards are not enough.

## 6. Fallback that is never actually tested
- Test suites that do `import cpp_bridge` never load the .so — a corrupt/missing lib is undetected.
- `find_lib` with `if p.exists(): return str(p)` misses corrupt/wrong-arch files.
- Check: write a test that (a) renames the .so away, (b) truncates it, (c) loads it and calls one function.

## 7. Test suites that never exercise the native path
- `use_cpp=False` in every test = the whole C++ layer is untested (typical for "optional" accelerators).
- C++ unit tests built with `-march=x86-64` never run AVX2/AVX-512 kernels (compile-time dispatch).
- Check: count tests with the native flag on; run the suite both ways if allowed.

## 8. Compile-time SIMD dispatch → SIGILL on other CPUs
- `#if SIMD_HAS_AVX2 ... _mm256_...` with `-march=native` build → illegal instruction on older hosts.
- Comment claims "runtime dispatch lives in X" but X only prints CPU info. Verify the dispatch is real.

## 9. Boundary math
- `shift % n` with n==0 → SIGFPE; `while (size >= capacity)` with capacity 0 → infinite loop;
  `occupancy() = size/0` → inf; `uint64_t max + 1` → wrap to 0; `static_cast<int>(size_t)` overflow.
- Capacity-0 paths are usually unreachable via the C API but reachable via future config knobs.

## 10. Destructive tooling
- Table rebuild: `CREATE TABLE x_dedup AS SELECT col1, col2 ... FROM x` silently drops all unlisted
  columns (bi-temporal edge fields, audit fields) — check `PRAGMA table_info` before trusting.
- `DROP SCHEMA IF EXISTS ... CASCADE` without `--dry-run`/confirmation; DSN rewriting via
  `str.replace("dbname=x", ...)` fails silently on variant DSNs → runs against the WRONG database.
- File-copy backups (`cp`) of WAL-mode SQLite are inconsistent — use `sqlite3 .backup` /
  `Connection.backup()`.

## 11. Dashboard/network tooling security
- Unauthenticated WebSocket that spawns a shell (`pty.openpty()` + `SHELL`) on `0.0.0.0` = remote RCE.
- No Origin check on WS endpoints = Cross-Site WebSocket Hijacking (memory data leak).
- `json.dumps(user_data)` inlined into `<script>` without escaping `</` = stored XSS.
- `SimpleHTTPRequestHandler` after `os.chdir(output_dir)` serves the whole directory with listing.
- `subprocess.run(..., check=True)` on openssl without try/except = crash on missing binary.
