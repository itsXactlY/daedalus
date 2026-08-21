---
name: multi-agent-code-orchestration
description: |
  Coordinate multiple AI coding sub-agents to do milestone-scale software work. Two
  patterns under one class: (A) plan execution via delegate_task subagents with 2-stage
  review (per-task), and (B) a 3-coder + 1-auditor + 1-reviewer crew for milestone-sized
  workstreams in 2 waves (exceeds the 3-concurrent dispatch cap). Use when the user asks
  for a 'crew', 'team', '3 coder + auditor + reviewer', or any multi-agent code effort.
---

# Multi-Agent Code Orchestration

Class-level skill for splitting coding work across sub-agents. Both patterns delegate to
isolated `delegate_task` workers; they differ in scale and review shape. The original
narrow skills `subagent-driven-development` (pattern A) and
`multi-agent-crew-orchestration` (pattern B) are absorbed below; support lives under
`references/<source>/`.

## Pattern A — Plan execution via subagents (absorbed from `subagent-driven-development`)

Execute a written plan by dispatching one `delegate_task` subagent per task, each with a
**2-stage review** (implement, then self-review / fix). Best for plans with many discrete
tasks that fit under the 3-concurrent dispatch cap.

Discipline:
- **Context-budget** — don't drown a subagent in the whole repo; give it the task +
  the files it touches. Support: `references/subagent-driven-development/context-budget-discipline.md`.
- **Gates taxonomy** — what counts as done at each gate. Support:
  `references/subagent-driven-development/gates-taxonomy.md`.
- **Audit-fix campaigns** — patterns for sweeping fix passes. Support:
  `references/subagent-driven-development/audit-fix-campaign-patterns.md`.

## Pattern B — Milestone crew (absorbed from `multi-agent-crew-orchestration`)

For milestone-sized work that exceeds the 3-concurrent cap: a **3-coder + 1-auditor +
1-reviewer** crew in **2 waves** — wave 1 parallel implementation, wave 2 parallel review,
then parent does post-timeout verification on disk and self-fills gaps, with
BLOCKER-fix-before-merge.

Support (under `references/multi-agent-crew-orchestration/`): `test-fixture-patterns.md`,
`phase-8-round-4-5-addendum.md`, `round-6-7-8-stability-data.md`,
`bug-patterns-from-real-rounds.md`. Template:
`templates/multi-agent-crew-orchestration/node-test-driver.template.js`.

## Choosing

- Plan of many small tasks, under concurrency cap → Pattern A.
- Milestone / "build me a team" / over the cap → Pattern B.

## See also

- `software-development/agent-delivery-integrity` — don't let a crew report "done" with
  empty shells.
- `autonomous-ai-agents/loop-engineering` — for recurring autonomous loops.
