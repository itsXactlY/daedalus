# Parallel Read-Only Audit: hoch & runter — field lessons (2026-08-07, mazemaker-pro)

Lessons from a 3-stream parallel audit crew over /home/alca/projects/mazemaker-pro.
Belongs to the codebase-due-diligence class; applies to ANY large-codebase audit via delegate_task.

## 1. Audit = READ-ONLY (operator correction)

Audit request means: NO test runs, NO builds, NO service starts, NO file edits — not even
"running the project's own test suite as empirical evidence". The operator corrected exactly
this ("nein. nur code audit.") when a background test-suite run was started alongside the crew.
If empirical verification is wanted, it is asked for separately. Only exception: read-only
greps/reads to verify a finding.

## 2. Stream split along DATA-FLOW direction (hoch & runter)

Split parallel audit streams by data-flow direction, not concern domains. Strictly disjoint
file ownership per stream (list exact files + line counts in each worker's context).

| Stream | Direction | Files | Focus |
|--------|-----------|-------|-------|
| HOCH (bottom-up) | Persistence → Retrieval → Engines | stores, schema, migrations, retrieval/GPU/rerank | SQL injection, corruption recovery, concurrency, boundary, empty/NaN data |
| RUNTER (top-down) | API/Plugin surface → Engines → Store | entry points, schemas, config, license, engines, embed providers | contract violations, error paths, graceful degradation, None/garbage input, silent fallbacks |
| INTEGRATION (optional 3rd) | Cross-layer | C++/bridge, tests, tooling, scripts | memory safety, bridge contracts, test coverage gaps, idempotency |

"Upside-down" lens = the project's own edge-case philosophy. If the project has an
upside-down test suite (e.g. tests/test_upside_down.py), its docstring defines the lens:
"tests everything that SHOULDN'T work, edge cases, boundary conditions, corruption recovery,
and what if the user is drunk scenarios. If it passes here, it's production." Do NOT run the
suite during the audit.

Worker brief requirements (each worker):
- exact file list with line counts, full paths
- the lens (upside-down philosophy quote)
- output format: Datei:zeile, Severity (CRITICAL/HIGH/MEDIUM/LOW), Code snippet, Bug, Fix
- "report EVERY issue, even LOW"
- report language: operator's language (German here), code/file names English
- "READ-ONLY: change nothing, commit nothing, start nothing, build nothing"

## 3. Free-model subagent returns EMPTY report (status=completed, no summary)

Symptom: task marked completed, api_calls > 0, but the summary is only "Let me compile the
report" — the worker read files, then ran out of steam before writing the final answer. The
batch's "Full subagent output saved to: ..." hint is absent for that task.

Diagnosis: `tail -c 20000 ~/.hermes/cache/delegation/live/<delegation_id>/task-N.log`
shows what the worker actually did (read_file trace present = it worked, only the answer is
missing).

Recovery: re-dispatch ONLY that stream as a single delegate_task with the hard requirement
"YOUR FINAL ANSWER MUST BE THE COMPLETE REPORT" in BOTH goal and context — AND on a NON-free
model. Root cause of free-model crews: `delegation.model`/`delegation.provider` in
`~/.hermes/config.yaml` pin ALL delegate_task children globally; a free model there makes
every sub-agent a roulette (see persistent-crew-loop skill for the config fix: pin
deepseek-v4-flash/deepseek or delete the block). Re-dispatching on the SAME free model tends
to fail identically.

## 4. Cross-stream duplicates + report artifacts

Overlapping streams find the same bug twice (e.g. WAL checkpoint race reported by both HOCH
and RUNTER). Deduplicate in the consolidated report with a cross-reference map (H5 == R7)
instead of presenting duplicates as separate findings.

Artifacts (follow the project's audit convention, e.g. benchmarks/audit/):
- one raw report file per stream (copy of subagent summary)
- one consolidated file: scope, dedup map, severity table, prioritized fix order, open
  questions ("not judgeable" items the workers flagged)

## 5. VERIFY sub-agent CRITICALs — injection findings need the pre-filter check

Sub-agent line numbers and severities are SELF-REPORTS. In the 2026-08-07 audit, ALL THREE
reported CRITICALs were disproven by a 5-minute code check:

- "FTS5 MATCH injection" (memory_client.py:1088/1139) — WRONG: `_sanitize_fts_query`
  (line 428-446) tokenizes via `re.findall(r"[A-Za-z0-9_][A-Za-z0-9_/\-]{1,}")` FIRST, which
  strips every FTS5 metacharacter (`" * + ^ ~ ( ) :`); each token is then wrapped in double
  quotes, where FTS5 treats everything literally.
- "Postgres tsquery injection" (postgres_store.py:1796/1837) — WRONG: `_sanitize_tsquery_terms`
  (line 1751-1760) applies the same token regex; tsquery operators (`& | ! <-> :`) cannot
  survive it, and `-` is NOT an operator in tsquery (unlike FTS5).
- "NUL-byte truncation bypass" (mazemaker.py:480) — WRONG: the NUL checks sit exactly at the
  c_char_p boundary (cpp_bridge.py:191-194), which is the ONLY path that truncates; the active
  SQLite path stores NUL intact.

Pattern: LLM auditors see "user input reaches SQL string" and flag injection WITHOUT checking
for upstream sanitizers/allowlists/regexes. Rule: for EVERY injection/security finding, grep
the function that BUILDS the query, look for pre-filtering before the flagged line, and test
whether the metacharacters can actually survive the filter. Then downgrade or strike.

What SURVIVED verification (real top findings): connection canonicalization sweep
(memory_client.py:303-359) swaps ALL source_id>target_id rows without an edge_type filter,
inverting directed supersedes/causal edges (runs on every store init; fix: restrict to
'similar'/'bridge'); WAL checkpoint close-race (memory_client.py:1327-1335, join 2s without
lock); BM25 fallback loads the whole corpus before the 10k cap applies (1107-1123).

## Audit result (mazemaker-pro 2026-08-07, VERIFIED)

After verification: 0 CRITICAL (all three disproven, see §5), 12 HIGH (top: canonicalization
sweep, WAL checkpoint race, NaN/Inf embeddings unvalidated, license pubkey env bypass
license.py:364-382, GPU tensor/ID misalignment gpu_recall.py:186-257, migration setval
idempotency + FK pre-filter OOM, dream sampling silent fallback, divergent GPU wait policies),
16 MEDIUM, ~20 LOW. INTEGRATION stream (C++/bridge/tests/tooling) re-dispatched on
deepseek-v4-flash after the free-model empty-report failure. Full reports:
benchmarks/audit/upside-down-audit-2026-08-07.md (+ -hoch- / -runter- raw files).
