---
name: cpp-python-ffi-audit
description: Audit C++/Python ctypes bridges for FFI safety bugs.
---

# C++ ↔ Python FFI Hybrid Audit

## When to Use
- User asks for a code audit / review of a project with a C++ core (`extern "C"` API) + Python wrapper (ctypes, cffi, pybind11) — e.g. "audit Stream X: C++-Ebene, Python↔C++-Bridge, Test-Abdeckung, Tooling"
- Any task where Python calls into a `.so`/`.dll` and you must find crashes, UB, contract drift, or dead fallback paths
- Verifying test coverage of a native-optional codebase ("does any test actually exercise the C++ path?")

## Core Method (READ-ONLY)
1. Read the C-API header and its implementation side by side — the header's OWNERSHIP CONTRACT is the spec; verify the code honors it.
2. Read the Python wrapper(s) and check every ctypes signature against the header (types, sizes, padding, ownership, NULL handling).
3. Trace one full round-trip (store → retrieve → think) by hand, including ID values — ID-offset bugs only show when you simulate actual values.
4. Grep the test suites for the native switch (`use_cpp=False` / `--no-cpp` / skip-if-no-lib). Count how many tests actually run the native path.
5. Check the fallback: what happens when the .so is missing, corrupt, wrong arch, or an old ABI version.
6. Audit tooling/scripts for destructive ops (DROP CASCADE, table rebuilds, DELETE without dry-run) and unauthenticated network endpoints.

## Checklist (verify each item)
- **Exception barrier**: every `extern "C"` function must wrap its body in try/catch. A C++ exception crossing the FFI boundary = `std::terminate` = SIGABRT of the whole Python process. Python `try/except` around the call does NOT catch it — `except: pass` guards are an illusion. Trigger classes: `std::invalid_argument` on dimension mismatch, `bad_alloc`, vector copies.
- **Dangling pointers**: returned `float*`/`struct*` must not point into function-local containers (`std::vector` local variable — dead on return). Header claims like "valid until next call" must actually hold.
- **ID-space drift**: two subsystems with own counters (graph node IDs, memory IDs) — check the ±1 offset conventions between layers (`store` auto-edges, `think` start node, `add_edge` pass-through). Symptom: self-loops `(n,n)`, off-by-one IDs in results, silently dropped edges.
- **ctypes struct layout**: padding/alignment (uint64 after floats), `char[N]` truncation via strncpy, `c_size_t` vs `c_uint64` mismatches.
- **Length validation**: every `dim`/`count`/`k` parameter checked against engine-internal dimensions; mismatch = OOB read in C++ (SIMD kernels read `dim` floats blindly).
- **Buffer lifetime**: `const float*` into Python ctypes arrays — must live for the whole call; C++ must not retain pointers past return.
- **Fallback reality**: test by actually loading the lib (CDLL + ABI smoke call), not by `import wrapper_module` (that never touches the .so). `find_lib` checking only `exists()` misses corrupt/wrong-arch files.
- **SIMD dispatch**: compile-time ISA (`-march=native`, `__AVX2__`) → SIGILL on other CPUs; runtime dispatch must be real. Also check `install(DIRECTORY ...)` paths match actual include dir names.
- **Boundary math**: `x % n` with n==0 (SIGFPE), `while (size >= capacity)` with capacity 0 (infinite loop), empty `vector::data()` = nullptr into memcpy-like kernels, `uint64_t + 1` wraparound on max values.
- **Error-code mapping**: C returns 0/-1 — Python must translate; silent `except: pass` hides real failures.
- **Tooling**: table rebuilds that SELECT only some columns lose the rest (bi-temporal/typed edges); DROP SCHEMA CASCADE without `--dry-run`/confirm; file-copy backups of WAL SQLite are inconsistent (use `Connection.backup()`); unauthenticated WebSocket shell endpoints; missing Origin checks (CSWSH); `json.dumps(...)` inlined into `<script>` without escaping `</` = stored XSS; `SimpleHTTPRequestHandler` serving the whole cwd.

## Output Format (German reports, keep code/file names English)
```
## <STREAM>-Audit
### ISSUE N: [Title]
**Datei**: path:line
**Severity**: CRITICAL/HIGH/MEDIUM/LOW
**Code**: ```...```
**Bug**: explanation
**Fix**: recommended fix
```
End with a severity-sorted summary + explicit test-gap list. If something cannot be verified without running code, say so explicitly — never guess.

## References
- `references/cpp-python-ffi-audit-patterns.md` — condensed bug-pattern bank with code snippets (recurring across FFI projects)
- `references/mazemaker-pro-integration-audit-2026-08.md` — full findings of the 2026-08 mazemaker-pro Integration stream (30 issues, exact file:line); cross-reference before re-auditing that project

## Pitfalls
- Do NOT build/run during a read-only audit — static analysis only; state that nothing was executed.
- Parallel audit streams of one project produce overlapping findings — check the integration stream's reference file first to avoid duplicate reports.
- C++ unit tests compiled with portable flags (`-march=x86-64`) never execute the AVX2/AVX-512 kernels — SIMD paths are usually untested even when "tests pass".
- `initialize(**kwargs)` wrappers that ignore their parameters (capacity etc.) are silent API lies — flag them.
