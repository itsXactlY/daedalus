# Audit-Verification Worked Example — mazemaker-pro, 2026-08-07

Three parallel audit streams (HOCH/RUNTER/INTEGRATION) produced 90 issues. The parent
verified every CRITICAL + top HIGHs against source before shipping. Result: 3/3 CRITICALs
refuted, the buried HIGH confirmed as top fix, one live deployment confirmed a 4th.

## Refuted claims (worker severity was wrong)

1. **"CRITICAL: FTS5 MATCH injection"** (memory_client.py:1088/1139)
   Worker claim: `_sanitize_fts_query` doesn't escape FTS5 metacharacters, so user queries
   can inject boolean logic.
   Reality: the sanitizer FIRST runs `re.findall(r"[A-Za-z0-9_][A-Za-z0-9_/\-]{1,}")` —
   every FTS5 metachar (`" * + ^ ~ ( ) :`) is stripped before the query is built, and each
   token is wrapped in double quotes, inside which FTS5 treats all operators as literal.
   `-` is allowed in tokens but literal inside a quoted phrase. No vector.
   Verdict: WIDERLEGT (LOW, cosmetic).

2. **"CRITICAL: Postgres tsquery injection"** (postgres_store.py:1796/1837)
   Same pattern: `_sanitize_tsquery_terms` uses the same token regex — tsquery operators
   (`& | ! <-> :`) never survive it; `-` is NOT a tsquery operator (it's part of the lexeme,
   unlike FTS5). Entity path builds `(<-> phrase)` purely from regex tokens.
   Verdict: WIDERLEGT (LOW).

3. **"CRITICAL: NUL-byte truncation bypass"** (mazemaker.py:480 vs cpp_bridge.py:191)
   Worker claim: remember() bypasses the cpp_bridge NUL checks, so content silently
   truncates at the C boundary.
   Reality: the NUL checks sit exactly on the only `c_char_p` path (cpp_bridge is an
   OPTIONAL engine, loaded only with use_cpp=True); the active path is SQLiteStore.store
   which stores NUL intact (SQLite TEXT is binary-safe).
   Verdict: NOT CONFIRMED as active bug (LOW, defense-in-depth wish).

## Confirmed claims

4. **HIGH → top fix: canonicalization sweep swaps directed edges**
   (memory_client.py:343-347) `UPDATE connections SET source_id=target_id, target_id=source_id
   WHERE source_id > target_id` runs at EVERY store init with NO edge_type filter. The table
   has an edge_type column; supersedes/causal/derived_from edges with source>target get their
   direction inverted. Ingest usually writes source=older id, so most supersedes are safe —
   but legacy/import data is at risk. Fix: restrict to `edge_type IN ('similar','bridge')`.

5. **HIGH confirmed via deployment**: a parallel Claude Code session committed a fix to
   `gpu_recall.py` whose description matched audit finding H13 (GPU tensor/ID misalignment:
   "arming a misaligned tensor returns the WRONG memory for every recall, which reads as poor
   retrieval quality rather than as a bug"). The two new guards (ragged corpus refuses to arm,
   id/vector count mismatch refuses) were exactly the audit's proposed fix. This is the payoff
   case: the audit caught a silent-wrongness bug before it fired.

## Verification protocol that caught these

1. Read the actual code lines for every CRITICAL and top 2-3 HIGHs.
2. Look for PRE-FILTERS upstream of the claimed bug (regexes, sanitizers, quoting) — the
   classic false-positive is "injection" on a query that was already token-filtered or
   phrase-quoted. Both injection claims died on this.
3. Check REACHABILITY: optional .so absent? server not running? feature flag off? → downgrade
   to "latent" with evidence.
4. Check the surrounding data model: the NUL claim died on "which path actually uses c_char_p".
5. Record verdicts in the report (WIDERLEGT / BESTÄTIGT / latent) — keep raw worker reports
   as files, but the consolidated report carries verified severities.
6. Cross-check against live deployments: a fix commit that matches an audit finding verbatim
   is the strongest possible validation signal.

## Cost note

Verification took ~10 minutes of read_file/search on 5-6 code locations for 3 streams of work.
That is cheap insurance against shipping a report full of phantom CRITICALs — the "CRITICAL
injection" claims would have triggered urgent, unnecessary security work.
