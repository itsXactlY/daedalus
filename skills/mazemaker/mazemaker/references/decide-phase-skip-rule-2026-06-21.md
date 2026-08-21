# DECIDE Phase Skip-Rule Worked Example (2026-06-21 08:15Z)

This is a concrete worked example of how the 2-hour skip rule interacts with the
3-rank-per-cycle limit, and why the recall-based discovery enumeration misses
items the browse-based enumeration catches.

## The 2h Skip Rule, Restated

> "Skip items already written as `decision:rank-*` in the last 2 hours to avoid
> duplicates."

The rule operates on the **DECISION memory's `created_at`**, not the discovery
memory's `created_at`. A discovery from 4h ago is still eligible if no decision
about it was written in the last 2h.

## Concrete Example: 2026-06-21 08:15Z Cycle

**Current UTC time**: 2026-06-21 08:15:57 (cron timestamp `20260621_081557`)

**Decision cycles in the prior 4h window**:

| Cycle time (UTC) | Decision IDs | Discoveries covered |
|-----------------|--------------|---------------------|
| 06:00 | 825446, 825447, (rank 2, 3) | 825426 hardware, 825436 legaltech, 825414 claudecodere |
| 07:15 | 825463, 825464, 825465 | 825456 pulse-tick 0609, 825425 history-recipe, 825408 space-recipe |
| 08:00 | 825474, 825473, 825472 | 825300 NK npm (CRITICAL), 825468 Chinese distillation (IMPORTANT), 825471 silent sabotage (CRITICAL) |

## Skip Rule Math (UTC)

A discovery is SKIPPED if any of these conditions hold:
1. A `decision:rank-*` memory was created in the last 2h UTC **AND** its content
   references the discovery's ID.
2. The discovery's label appears in the decision's content (cross-reference).

At 08:15:57 UTC, the 2h skip window covers 06:15:57 UTC → 08:15:57 UTC.

**Decisions in skip window** (created 06:15-08:15):
- 825463 (07:15), 825464 (07:15), 825465 (07:15) — INSIDE window
- 825474 (08:00), 825473 (08:00), 825472 (08:00 if exists) — INSIDE window
- 825446, 825447 (06:00) — OUTSIDE window by 15 min, eligible for re-ranking

In practice, 06:00 UTC decisions are eligible for re-ranking in theory but the
practical decision is: don't re-rank. The 06:00 cycle already produced
comprehensive decisions with full action-item lists. Re-ranking already-thoroughly
decided items is duplicate work that exceeds the marginal value of freshness.

## The 08:00 UTC Cycle's Gap

The 08:00 cycle chose three CRITICAL/IMPORTANT findings on the US-China AI
competition axis:
- 825471 (Anthropic silent sabotage, CRITICAL)
- 825468 (Chinese AI distillation, IMPORTANT)
- 825300 (NK npm supply chain, CRITICAL)

These three are SKIPPED at 08:15 (inside 2h window).

But the discovery pool at 07:55-08:06 UTC contained MORE findings that the 08:00
cycle did NOT include (3-rank limit):
- 825469 (Palantir Maven + Iran civilian casualties) — CRITICAL, MISSED
- 825470 (programming frontier) — IMPORTANT, MISSED
- 825475 (gaming crisis) — NICE_TO_KNOW, MISSED
- 825462 (Velune-CLI) — NICE_TO_KNOW, MISSED (created 07:17, also missed)

The 08:15 cycle (this one) ranked the missed CRITICAL (Palantir), the missed
IMPORTANT (programming frontier), and a NICE_TO_KNOW (Velune-CLI 825462).

## Why the Recall Query Missed the Gap

If the 08:15 cycle had used `mazemaker_recall(query="discovery:pulse-tick-*",
limit=50)` as the cron script's instructions suggested, the top 50 results
would have been saturated with prior `decision:rank-*` memories (semantically
related to the query) and would NOT have surfaced 825469/825470/825462/825475
as the fresh discoveries they are. The recall API ranks by similarity, not by
recency.

`mazemaker_browse(label_prefix="discovery:", limit=30)` returns the 30 most
recently-created memories in `created_at DESC` order. THIS is the right tool
for DECIDE phase enumeration.

The cron script `~/.hermes/loops/tri-state/decide_rank.py` STILL suggests the
broken recall pattern in its `instructions` field. The workflow in
`SKILL.md` section 8 supersedes those instructions.

## What Would Have Happened With the Bad Pattern

If the 08:15 cycle had used the recall-based pattern, the 4 fresh discoveries
(825469/825470/825462/825475) would have been at positions 5-50 in the recall
result, mixed with 46+ prior decisions and earlier discoveries. The DECIDE agent
would have manually scanned through them looking for the "decision memory ID"
pattern, found that the 08:00 cycle already covered 825471/825468/825300, and
might have concluded (incorrectly) that the 2h window's discoveries are all
covered. The 825469 Palantir-Maven-Iran CRITICAL finding would have been MISSED
for another 60 minutes until the 09:15 cycle.

## The Right Pattern (Verified 2026-06-21 08:15Z)

1. `mazemaker_browse(label_prefix="discovery:", limit=30)` → 30 most recent
2. Filter to 24h window by `created_at` UTC (epoch → UTC datetime comparison)
3. For each, check if a `decision:rank-*` from the last 2h references it
4. Score the survivors by (graph_connectedness + novelty + recency + priority_boost)
5. Write top 3 as `decision:rank-20260621-<priority>-<N>-<slug>`

The 08:15 cycle followed this pattern and correctly identified 825469, 825470,
825462 as the top 3 unranked items. They were written as decisions 825476,
825477, 825478.

## Timestamp Discipline

`created_at` is always UTC. Labels like `discovery:pulse-wurm-20260621_0609_tick`
look like local-time suffixes but are unreliable for skip math. Always:
- Convert `created_at` epoch seconds to UTC datetime.
- Compare against `datetime.now(tz=timezone.utc)`.
- Compute `age_hours = (now - created) / 3600`.
- Skip if `age_hours < 2` for the decision that referenced the discovery.

Doing the math in local time or on the label suffix can be off by hours,
causing either re-ranking or skipping the wrong items.
