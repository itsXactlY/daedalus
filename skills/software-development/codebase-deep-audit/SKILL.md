---
name: codebase-deep-audit
description: "Audit codebases with crews — verify claims, git timelines."
version: 1.0.0
triggers:
  - deep audit of a codebase
  - audit crew
  - when did this start degrading
  - verify subagent findings
  - inception audit
---

# Codebase Deep Audit — Crew Method with Verification

Class-level workflow for full, deep, read-only audits of large codebases
(100k+ LOC, multiple repos, production stack) using parallel subagent crews.

## Core Principle

Subagent reports are SELF-REPORTS, not verified facts. Free/low-cost models
hallucinate completions, invent line numbers, and overstate severity. The
parent's job is to VERIFY before the findings become a report the user acts on.

## Workflow

1. **Recon first**: file inventory + line counts + process/service map +
   VRAM/RAM numbers if a live stack is involved. Hand the crew hard facts,
   not guesses (PID→service mapping, exact versions, exact log lines).
2. **Dispatch parallel streams** (max_concurrent_children), one concern
   domain each: engine kernel, pipeline/cycles, deployment chain,
   cross-repo divergence. Give every worker: absolute paths, known findings
   to deepen (not rediscover), and a strict output format
   (Datei:Zeile | Severity | Bug | Fix | Einfuehrungs-Commit).
3. **Inception nesting**: if children should spawn grandchildren, set
   `role="orchestrator"` EXPLICITLY. Default leaf children have NO
   delegate_task tool — they will quietly do the work inline and report
   "kein Spawn-Tool verfuegbar". Orchestrators need full context for their
   children (they share nothing).
4. **Verify every CRITICAL/HIGH against the code** (see Pitfalls for the
   canonical miss). Verify commit claims with `git cat-file -t <hash>`.
5. **Synthesize with a Verification section**: confirmed / disproved /
   severity-changed, plus the priority-ordered fix list.
6. **Git-history timeline** for "when did it start degrading": per confirmed
   defect, `git log -S'<symbol>'` + `git blame` → table
   `date -> commit -> what broke silently`. This surfaces the classic
   self-inflicted regression: a config-gate commit that started calling an
   accessor it never imported (NameError class), a "perf" commit that moved
   a whole-corpus load into a hot path, etc.
7. **Read full subagent summaries**: batch results are truncated to
   head+tail; the middle lives in
   `~/.daedalus/cache/delegation/subagent-summary-*.txt`. Always read the
   complete files before consolidating.

## Pitfalls

- **Sanitizer blindness**: workers claim injection ("raw query!") while a
  tokenizing regex two lines above already strips the metacharacters. In a
  real audit, all three worker-CRITICALs (FTS5-injection, tsquery-injection,
  NUL-truncation) were disproved by sanitizers the worker never read; the
  actual HIGH (a canonicalization sweep swapping directed edges without an
  edge_type filter) was the one the worker had downgraded.
- **Phantom commits**: a session transcript may cite a commit that exists in
  no repo (another worktree, local-only). Verify, then cite the real hash.
- **Free-model workers**: "Now I have a comprehensive view... let me compile
  the report" followed by nothing = failed run. 600 s timeouts with 0 summary
  = failed run. Re-dispatch on a pinned reliable model; do not accept the
  gap. Check `~/.daedalus/config.yaml` `delegation:` — if it pins a free
  model, EVERY delegate_task (not just loops) rolls the dice. Pin
  `delegation.model`/`delegation.provider` to a reliable model
  (e.g. deepseek-v4-flash / deepseek).
- **Truncated summaries**: the consolidated batch message trims each
  worker's output. The full text is on disk — read it before acting on the
  fragments.
- **read-only discipline**: audits of production stacks run while other
  agents may be building/deploying — never restart, never start, never
  write. State the read-only rule in every worker's context.

## Related

Overlaps with the user-owned `parallel-code-audit-crew` skill; if that gets
curator-adopted, merge this workflow into it. `persistent-crew-loop` carries
the loop-supervision variant of the free-model/delegation lessons.
