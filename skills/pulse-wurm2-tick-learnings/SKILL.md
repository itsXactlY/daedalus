---
name: pulse-wurm2-tick-learnings
description: Class-level learnings from running Pulse-Wurm 2.0 cron ticks. Pitfalls and patterns that every fresh tick should know — pulse_search response shape, cluster-bloat discipline, noise URL patterns, state.json write order, **pulse_search-as-hijack-bypass**, **pulse_dig EMPTY_SEED CONSISTENT**, **Polymarket hijack registry (16 surfaces, 12 classes — incl. NEW class #9 non-AI-entity+year #246, PITFALL #263 SpaceX Starship 18-locale hijack)**, **carry-over file schema + sibling-subagent write conflict (§32)**, **operator-override APPLY-don't-recommend (§23)**, , **single-datetime drift recovery (§25)**, **arxiv-noise flood hijack (§26)**, **high-yield seed pattern (§27)**, **deep-job processing as tick step 0 (§29)**, **person-research deep search fails on role/hiring topics (§31)**, **Anthropic safety-classifier prompt-framing artifacts — Fable 5 'fix this code' cluster (§33)**, **named-person + government-agency + named-AI-program triple-trigger hijack (§34, PITFALLS** #253/#254)**, **global election-influence triptych widening (§35)**, **PITFALL #253 deep-job 100% PM hijack at scale (4-trigger recipe)**, **legal domain §15a failure mode (#255)**, **cluster-bloat consolidation pattern (#256)**, **PM-settlement-as-verification (#257)**. Loaded by pulse-wurm2-stateful-tick.
---

# Pulse-Wurm 2.0 Tick Learnings

Distilled from 100+ ticks of the 6-hour pulse-wurm2 cron loop. These are the
**operational pitfalls and gotchas** that the umbrella
`pulse-wurm2-stateful-tick` SKILL.md assumes but does not enumerate. Patch the
references when a new pitfall surfaces; the umbrella SKILL.md rarely needs
editing.

## Learning index

The full learning bodies live in four references files, grouped by epoch.
Load the relevant one with `skill_view(file_path=...)` when a tick hits one of
these patterns:

- **`references/learnings-core.md`** — §1–§22: core operational shape
  (pulse_search response, PICKED_DOMAIN, EMPTY_SEED, cluster-bloat, noise
  URLs, Polymarket hijack bypass + registry, state.json write order).
- **`references/learnings-june-2026.md`** — §23–§33 + lettered follow-ups:
  the June 2026 deep-tick wave (operator-override, outage abort, drift
  recovery, PITFALL #244/#253, deep-job step-0, carry-over key naming).
- **`references/learnings-tick10.md`** — renumbered tick-10 duplicates:
  arxiv-noise flood + high-yield seed pattern.
- **`references/learnings-session-details.md`** — pointers to session-specific
  detail in other skills.

| § | Learning | Details |
|---|----------|---------|
| 1 | pulse_search response shape (MCP) | `references/learnings-core.md` |
| 2 | PICKED_DOMAIN extraction (mazemaker fresh-direction algorithm) | `references/learnings-core.md` |
| 3 | consecutive_empty double-bump | `references/learnings-core.md` |
| 4 | Python f-string backslash gotcha (via execute_code) | `references/learnings-core.md` |
| 5 | visited_urls cross-check is exact-string match | `references/learnings-core.md` |
| 6 | Tick report file naming | `references/learnings-core.md` |
| 7 | pulse_dig EMPTY_SEED blocker (NOW CONSISTENT, not intermittent) | `references/learnings-core.md` |
| 8 | Cluster-bloat discipline | `references/learnings-core.md` |
| 9 | Noise URL pattern recognition | `references/learnings-core.md` |
| 11 | pulse_tick.py runs in STUB mode — agent must make real MCP calls | `references/learnings-core.md` |
| 12 | terminal() heredoc pattern is BLOCKED | `references/learnings-core.md` |
| 13 | Large MCP results persist to /tmp/hermes-results/ | `references/learnings-core.md` |
| 14 | Fresh-direction can re-pick an already-tried SEED | `references/learnings-core.md` |
| 15 | Abstract-academic seeding pitfall (6-tick pattern as of 2026-06-22 13:11Z) | `references/learnings-core.md` |
| 15a | Concrete-reformulation ALSO fails for some non-AI/ML domains (NEW 2026-06-22 13:11Z) | `references/learnings-core.md` |
| 20 | pulse_search as Polymarket-hijack bypass (NEW 2026-06-22 tick 7) | `references/learnings-core.md` |
| 21 | Polymarket hijack surface registry (14 surfaces, growing) | `references/learnings-core.md` |
| 22 | Tick report carry-over: pulse-wurm-next-topics.json | `references/learnings-core.md` |
| 16 | Picker keyword-match counting is a known approximation | `references/learnings-core.md` |
| 17 | State.json write order | `references/learnings-core.md` |
| 18 | Tool-result triple-wrap for mazemaker browse | `references/learnings-core.md` |
| 19 | channel_stats.mcp_channel counter | `references/learnings-core.md` |
| 23 | Operator-override code pattern — APPLY, don't just recommend (NEW 2026-06-22 tick 1232) | `references/learnings-june-2026.md` |
| 24 | Pulse MCP full-outage clean-abort pattern (NEW 2026-06-22 tick 1232) | `references/learnings-june-2026.md` |
| 25 | Single-datetime drift recovery (NEW 2026-06-22 tick 1232) | `references/learnings-june-2026.md` |
| 26 | arxiv DOI + benchmark name = 100% Ti-substring noise (PITFALL #245) — NEW 2026-06-22 13:18Z | `references/learnings-june-2026.md` |
| 27 | Picker Counter() bug — 0-count domains get missed — NEW 2026-06-22 13:18Z | `references/learnings-june-2026.md` |
| 28 | Manual rotation at consecutive_empty=3 — script rotation code dead — NEW 2026-06-22 13:18Z | `references/learnings-june-2026.md` |
| 29 | Deep-job processing as tick step 0 (NEW 2026-06-22 13:34Z) | `references/learnings-june-2026.md` |
| 30 | Script auto-sort works correctly when next_seeds pool is healthy (NEW 2026-06-22 13:34Z) | `references/learnings-june-2026.md` |
| 31 | Person-research deep search fails on role/hiring topics — 9th hijack class (NEW 2026-06-22 13:5 | `references/learnings-june-2026.md` |
| 26b | PITFALL #244 LOW-SCALE MODE — sub-channel fully suppressed (NEW 2026-06-22 14:01Z) | `references/learnings-june-2026.md` |
| 27b | High-yield §27 cluster-saturation clarification (NEW 2026-06-22 14:01Z) | `references/learnings-june-2026.md` |
| 27c | 3-angle climate yield from single seed (NEW 2026-06-22 14:01Z) | `references/learnings-june-2026.md` |
| 27d | Clock-skew detection pattern (NEW 2026-06-22 14:01Z) | `references/learnings-june-2026.md` |
| 28b | Manual rotation §28 verified end-to-end (2026-06-22 14:01Z) | `references/learnings-june-2026.md` |
| 23a | Cluster-brother popping — extend §23 to include adjacent dead seeds (NEW 2026-06-22 14:36Z) | `references/learnings-june-2026.md` |
| 28c | PITFALL #253 — infrastructure-systems-design domain exhausted (NEW 2026-06-22 14:36Z) | `references/learnings-june-2026.md` |
| 26c | PITFALL #253 references and follow-up (NEW 2026-06-22 14:36Z) | `references/learnings-june-2026.md` |
| 32 | Carry-over file key naming — `in_flight_deep_jobs_at_tick_end` (NEW 2026-06-22 14:45Z) | `references/learnings-june-2026.md` |
| 33 | Nature as primary-source venue for AI-cognitive-impact (NEW 2026-06-22 18:30Z) | `references/learnings-june-2026.md` |
| — | See also: session-specific detail in references/ | `references/learnings-session-details.md` |
| 26 | Broad-benchmark-evaluation → arxiv-noise flood (NEW 2026-06-22 tick 10) | `references/learnings-tick10.md` |
| 27 | High-yield seed pattern — direct RSS canonical + Reddit cluster (NEW 2026-06-22 tick 10) | `references/learnings-tick10.md` |

## When to load what

- Normal tick startup → skim this index, load `learnings-core.md` only if a
  core pitfall pattern matches.
- Deep-job / tick-12xx+ behavior → load `learnings-june-2026.md`.
- arxiv flood or high-yield seed handling → load `learnings-tick10.md`.
