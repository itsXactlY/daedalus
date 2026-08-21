# Multi-phase audit-fix-reaudit campaigns — case study notes

This file documents patterns observed across multiple phases of a
single large audit-fix campaign on `jrwl-messenger` (2026-06-17
through 2026-06-19). The campaign followed the arc:

1. **Audit phase** — dispatch many subagent deep-dives against a
   codebase to produce a comprehensive findings list.
2. **Fix phase** — fix the findings in priority order, commit each.
3. **Re-audit phase** — dispatch fresh subagents to verify the fixes
   and surface regressions / new issues.
4. **Multi-cycle fix** — repeat fix + re-audit until the project is
   in a stable state.

These phases don't map cleanly onto the 600s subagent budget. Use
this file as a reference when planning similar campaigns.

---

## Audit phase (jrwl-messenger 2026-06-18, 13 subagents)

**Pattern:** dispatch 5 batches × 3 parallel subagents = 15 subagents
in ~30 min, each focused on a narrow file:line scope. Each subagent
writes a report file to disk.

**What worked:**
- Narrow focus per subagent (e.g. "audit gateway.py for race
  conditions") produces better reports than open-ended tasks
- Parallel dispatch (3 at a time) maximizes throughput without
  overloading the platform
- Asking each subagent to write a report file (not just return
  text) preserves the audit even if the user navigates away

**What didn't work:**
- Two subagents timed out at 600s on broader scopes (e.g.
  "audit the entire HTTP API surface")
- The orchestrator pattern (3-stage pipeline with reviewer +
  auditor) had a 100% timeout rate during the FIRST audit run.
  The leaf subagents did finish but the synthesis was lost.

**Specific subagent patterns that worked:**
- One subagent = one report file
- Each report includes: severity histogram, top critical findings,
  per-file:line list, recommended fix order
- Reports cross-reference each other so a future reader can follow
  the trail (e.g. "see also: AUDIT_FINAL_SYNTHESIS.md")

---

## Fix phase (jrwl-messenger 2026-06-18, 14 surgical commits)

**Pattern:** ordered by severity. Phase 0 (blockers) first, then
Phase 1 (trust model), Phase 2 (crypto), Phase 3 (federation),
Phase 4 (cleanup).

**Workload split between subagents and main session:**

| Task type | Who did it | Why |
|---|---|---|
| Small focused fix in a single section | Subagent | Surgical, fast, well-scoped |
| Test writing using existing patterns | Subagent | Clear template to follow |
| Multi-section edit in 3000+ line gateway.py | Main session | Subagents timeout on monolith reads |
| Cross-file refactor (5+ files) | Main session | Subagents timeout on scope |
| Live runtime verification (test runner) | Main session | Need build state in context |

**Critical workflow rules learned:**

1. **The `validate_http_session` audit found dead code; the
   re-audit found that the dead-code fix existed but wasn't called.**
   The fix for "CRIT-1" was a one-line edit to call the existing
   function from each handler. This pattern (dead code → call it)
   is the cheapest and highest-value fix; look for it first.
2. **Pre-existing bugs get exposed when writing tests.** See the
   "Tests surface pre-existing bugs" pattern in SKILL.md.
3. **The X3DH endpoint was broken (`verify_signed_prekey` was
   called but never imported).** This was caught by an E2E test
   that exercised the actual HTTP flow. Without that test, the
   bug would have persisted forever. **Tests that exercise the
   real production code path find real bugs.**
4. **`hasattr()` fallback in test assertions is a footgun.** See
   the "P0 silently broken test" pattern in SKILL.md. The
   fallback made the test pass on any state mutation, hiding the
   fact that the production code wasn't actually being tested.

**Subagent success rate by task type (jrwl-messenger 2026-06-18):**

| Task type | Success rate | Notes |
|---|---|---|
| Single-section fix in small file | 100% | Subagents excel at these |
| Test writing using existing pattern | 100% | Clear template to follow |
| Multi-section fix in 3000+ LOC monolith | 30% | Most timed out |
| 3-stage orchestrator pipeline | 33% | 1/3 in main session, 2/3 timed out |

**Concrete workload split that worked:**

- Phase 0 (3 fixes): 2 subagents (one for gateway.py, one for ui.html) + 1 main-session fallback after timeout
- Phase 1-4: 100% main session (gateway.py multi-section edits)
- Phase 5 (9 backlog items): 5 subagents + 4 main session for surgical
- Phase 6 (4 v1.0 tasks): orchestrators (4/5 timed out, partial work landed)
- Phase 7 (3 crews): orchestrators (3/3 timed out, partial work landed)

---

## Re-audit phase (jrwl-messenger 2026-06-19)

**Pattern:** dispatch fresh subagents with different focus than the
original audit. They verify the fixes AND look for new issues
introduced by the fixes.

**Critical finding from re-audit (jrwl-messenger Phase 6 verification):**

> Ratchet_encrypt / ratchet_decrypt were imported at gateway.py:241-242
> but **NEVER CALLED** in live gateway. All 9 live message-send /
> receive call sites use legacy `encrypt_message`. The Double Ratchet
> implementation was correct (after Phase 2 fixes) but DORMANT —
> only protecting the test suite, not production traffic.

**Lesson:** code-correct fixes that don't wire into the live path
provide false reassurance. **Verification must include a real
call-graph trace**, not just "did the test pass".

**Verification recipe:**

1. After every fix phase, dispatch ONE subagent with the explicit
   task: *"verify the fix actually runs in production. Trace the
   call graph from the public API surface (HTTP endpoint / WS message)
   through to the function that was changed. Report any places where
   the fix is bypassed."*
2. The subagent should be REQUIRED to grep for call sites of the
   changed function and check whether they're reachable from the
   live code paths.
3. If a subagent reports "all tests pass" but the function isn't
   called in production, that's a CRITICAL finding, not a
   PASS.

---

## Multi-phase campaign — what I'd do differently next time

**Plan the subagent-vs-main split upfront.** Don't discover at the
600s timeout that the task was too big for a subagent.

**Recipe for planning:**

1. List every fix.
2. For each fix, count:
   - How many files does it touch?
   - How many sections per file (non-adjacent = separate)?
   - How many lines to read for context?
   - Does it require knowing prior state (cumulative)?
3. If a fix requires reading > 2000 LOC of context, OR touching
   > 2 non-adjacent sections in a 3000+ LOC file: MAIN SESSION.
4. Otherwise: subagent.

**Build a test scaffolding FIRST.** The audit often finds bugs that
are best exposed by tests, not by reading code. Write a few smoke
tests that exercise the full HTTP/WS path early. They'll surface
pre-existing bugs (like the X3DH import bug) before they waste
fix-phase cycles.

**Use a fixed commit-message format per phase.** E.g.

```
fix: Phase N / <item-name>

[CRITICAL/HIGH/etc.] tag if applicable

<Bug summary>

<Fix details>

<Verification: tests pass, file:line>

Co-Authored-By: ...
```

This makes the git log searchable and tells the next person what
each commit does without reading the diff.

**Save the audit findings as memory at the START of the fix
campaign, not at the end.** The audit reports are large (300K+ in
the jrwl case). `mcp__mazemaker__mazemaker_remember` can fail with
"unreachable" or "internal error" — if it fails, retry later or
fall back to `memory` tool (which can also fail with "drift") or
disk file + commit. Have a backup plan before you start saving.

---

## Pre-existing bugs found during this campaign (by layer)

These are specific bugs from jrwl-messenger that future campaigns
might see in similar codebases:

- **Auth helper defined, never called.** Common anti-pattern:
  someone adds `def validate_session_token` and never calls it
  from any handler. Look for `def ` definitions and grep for the
  function name in the request handlers.
- **Imported-but-not-used → function called but NameError.** Less
  common but happens. Look for any function called in production
  paths that isn't in the file-level `from X import` block.
- **Wrong arg order in cache lookups.** Functions like
  `get_shared_secret(a, b)` use the args as a dict key. If callers
  pass `(b, a)`, it's a cache miss. Test that hits the cache hit
  path will catch this.
- **Endpoint that "succeeds" but doesn't persist.** Endpoints
  that return 200 OK but skip the actual save (often because of a
  try/except that swallows the exception). Test for actual state
  change, not just HTTP status.

---

## Test count as campaign health metric

The test count went up monotonically across the jrwl-messenger
campaign (Phase 0-7):

```
baseline (audit start): 397 passed, 7 failed (pre-existing)
+Phase 0: 395 passed, 2 failed (removed 7 dead tests)
+Phase 2: 398 passed, 2 failed (added 4 sender_key tests)
+Phase 5: 398 passed, 2 failed (added 3 H8 concurrency tests)
+Phase 6 v1.0-prep: 405 passed, 2 failed (added 7 ratchet/E2E tests)
+Phase 7 partial: 414 passed, 2 failed (added 3 WS ratchet tests, 6 X3DH tests)
```

The 2 "pre-existing" failures stayed at 2 throughout (the same two
tests that were broken before the audit started). That's a good
signal — the campaign didn't introduce regressions. Track this
metric after every commit to catch accidental regressions.

---

## When to STOP the campaign

The campaign is "done enough" when:

1. All CRITICAL and HIGH findings from the original audit are
   fixed or explicitly documented as "out of scope".
2. The re-audit (or the verification subagent) reports no NEW
   CRITICAL findings.
3. The test count is monotonically increasing.
4. The user says "ship it" or equivalent.

Don't keep finding new things to fix. There are always more.
The campaign ends when the highest-priority items are addressed
and the verification is clean. Anything beyond that should go
to a Phase-N+1 backlog, not the current campaign.