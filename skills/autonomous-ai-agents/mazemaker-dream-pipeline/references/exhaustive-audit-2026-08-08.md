# Exhaustive every-function audit — 2026-08-08

The operator demanded "ALLES testen, jede einzelne Funktion" — suites alone
proved insufficient. This is the proven workflow + the findings.

## Coverage measurement (no pytest/coverage needed)

pip is blocked on this host (PEP 668, externally-managed). `coverage` is not
installed — build a settrace-based function-level inventory instead:

```python
called = {}  # (module, fnname) -> count
def trace(frame, event, arg):
    if event == 'call':
        mod = os.path.basename(frame.f_code.co_filename).replace('.py', '')
        if mod in TARGETS:
            called[(mod, frame.f_code.co_name)] = called.get((mod, frame.f_code.co_name), 0) + 1
        def ret(frame2, event2, arg2):      # stop line-tracing inside (perf)
            return None if event2 == 'return' else ret
        return ret
    return None
sys.settrace(trace)
for suite in ('python/test_suite.py', 'tests/test_suite.py', 'tests/test_upside_down.py'):
    try: runpy.run_path(suite, run_name='__main__')
    except SystemExit: pass
sys.settrace(None)
```

Diff against an AST inventory (`ast.walk` for FunctionDef/AsyncFunctionDef per
module). Result: 416 defs, 182 executed — 234 gaps. Distribution that matters:
**postgres_store 66/66 + dream_postgres_store 37/37 = ZERO suite coverage**
(the production backend), afe 10/10, dream_worker 5/5, mcp_schemas 2/2,
config 2/2, plus ~52 memory_client paths (mcp-tool/PPR/reranker) and ~24
dream_engine backend methods.

Note: trace overhead makes perf assertions fail (35 s instead of < 2 s) and
`wal_checkpoint failed` logs appear — both are instrumentation artefacts, not
findings. The suites are green without the tracer.

## PG behaviour tests must run INSIDE the pod network

The pgvector container exposes no host ports (`/dev/tcp/localhost/5432` fails;
`PortMappings` empty). Host-side python cannot reach PG. Run the test script
in a throwaway container on the SAME pod, secret as env:

```bash
POD=$(podman inspect systemd-mazemaker-pgvector --format '{{.Pod}}')
podman run --rm --pod "$POD" --user 0 \
  --secret mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD \
  -v /tmp/audit-exhaustive-pg.py:/audit.py:ro \
  -v /home/alca/projects/mazemaker-pro/python:/app/core:ro \
  -e PYTHONPATH=/app/core \
  localhost/mazemaker-v2-mcp:gpu python3 /audit.py
```

- DSN: `postgresql://mazemaker:<pw>@localhost:5432/mazemaker_test` (in-pod
  localhost works). POSTGRES_PASSWORD is NOT in the container env — the
  secret must be injected as `MM_POSTGRES_PASSWORD`.
- Create the throwaway DB once: `CREATE DATABASE mazemaker_test`. NEVER point
  the audit at the production `mazemaker` DB.
- Result: 75/75 PG-store functions passed with 0 findings after fixing the
  TEST's signature guesses.

## Test-script mistakes that masquerade as findings

Nearly every "finding" in the first run was the test guessing a signature:
`search_temporal(query, ...)` needs the query; `weighted_edges()` takes no
limit; `recent_semantic_pool(limit)` has no `pool`; `remember_batch` takes
`list[dict]` not tuples; `prune_memories_by_label_prefix(prefix, older_than_ts)`
needs a ts; `stream_missing_colbert(batch_size, start_after_id)`; 
`upsert_dae_vectors` rows are 6-tuples; `add_bridges_batch(bridges,
dream_session_id=...)` — bridges FIRST; `get_memory_metadata([ids])` takes a
list; `get_connections()` on the dream store takes NO args.
Rule: **read the actual `def` signature before writing the call.** And use
two EXISTING ids for FK-constrained edge writes — `mid+1` as target violates
`connections_target_id_fkey`.

## The Free/Pro-Grenze false positive

The audit flagged "SQLite has no memory_dae_embeddings table" as a bug; I
added the CREATE to the SQLite schema (419c882) and pushed. Operator
correction: **SQLite ist FREE VERSION ONLY — sie bekommt NUR die Tabellen die
nötig sind, aber NIEMALS die Funktionen eines Pro-Stacks.** Reverted
(35d7d4c). A missing Pro table in SQLite is the no-leak guard working; Pro
paths are `has_feature()`-gated. Lesson: know which tier a store belongs to
BEFORE treating a missing table as a defect.

## Test-suite honesty repairs (python/test_suite.py)

- `test_11` sentence_transformers singleton: skip guard checked only the
  model dir + import; the backend died at INSTANTIATION ("No module named
  'torch'"). Put the constructor call inside the try; skip on torch absent.
- `test_30` cpp bridge: bridge raises at `MazemakerCpp()` (lazy .so load,
  RuntimeError), not at import — the constructor belongs inside the try.
- hermes plugin tests: hard-imported `plugins.memory.neural` from stale
  paths; now skip when the plugin dir is absent.
- **Shadowing**: two `def test_31()` existed — the second (hermes files)
  shadowed the streaming-arm regression test, which NEVER ran. Renamed to
  `test_hermes_files`. Check for duplicate test function names after adding
  tests; a missing test in the output is a shadowing symptom.
- The `@_testcase` wrapper swallows SkipTest (logs SKIP) — when verifying a
  skip, assert on the suite RUN output, not on a direct call expecting a
  raise.

## engine-sha.sh constant-hash bug (related)

`set -euo pipefail` + `xargs -I{} sh -c '... printf "%s\0"'` produced a
CONSTANT fingerprint: dash's printf ignores `\0` (NUL separation vanishes),
and the while-loop's final `read` exits 1 → pipefail marks the pipeline
failed → set -e kills the rest → sha256sum hashes empty stdin → constant
text-hash. Fix: plain `grep -vE "$EXCLUDE_RE"` + `xargs -d '\n' sha256sum`.
Also: the script's DEFAULT source pointed at the FREE repo
(`~/projects/mazemaker/python`) — a bare call hashed the wrong tree and the
fingerprint "never changed" despite pro-tree edits. Default is now
`~/projects/mazemaker-pro/python`. Verify content-sensitivity by editing a
tracked file (hash must move) and reverting (hash must return).
