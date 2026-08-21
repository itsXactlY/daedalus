# DECIDE Phase — 2026-06-23 06:15 UTC Cycle Post-Mortem

The 2026-06-23 06:15 UTC cycle is a documented FAILURE MODE for the
cross-day re-find guard. The cycle ran cleanly, scored candidates
correctly using the documented scoring framework, and wrote 3 decisions
that all passed the 2h dedup — but **failed to apply the cross-day
re-find guard that was added to the skill the same morning (05:45 UTC)**.

The cycle wrote `decision:rank-20260623-0615-critical-1-bofa-stablecoin-35pct-us-bank-deposit-drain-ceo-warning-2026`
(memory id 826729) as a CRITICAL #1, which is a **duplicate of
`decision:rank-20260622-2335-important-1-bofa-ceo-stablecoin-35-percent-deposit-drain-2026`**
(memory id 826578) written 6h45m earlier on 2026-06-22 23:35 UTC.

This post-mortem captures the failure mode so future cycles can avoid
repeating it.

## The cycle's three decisions

| Rank | Priority | Discovery | Memory ID | Status |
|---|---|---|---|---|
| #1 | CRITICAL | 826570 BofA CEO stablecoin 35% deposit drain | 826729 | **RE-FIND of 826578** |
| #2 | IMPORTANT | 826713 Masa Son dismisses orbital AI compute | 826730 | Companion to 826714 (already ranked 05:45Z) — should have been referenced not ranked |
| #3 | CRITICAL | 826493 Microsoft Crypto Clipper USB stealer | 826731 | Legit (not ranked in any prior cycle) |

The 06:15 cycle thus produced 1 duplicate (826729), 1 redundant companion
(826730 — 826713 was already noted as a companion to 826714 in the
05:45 cycle's decision body), and 1 legitimate pick (826731).

## What the cycle did correctly

- Used `mazemaker_browse(label_prefix='discovery:')` for the discovery
  pool (correct — not `mazemaker_recall` per the system-prompt
  anti-pattern documented in `cron-config-and-saturated-window.md`)
- Parsed 50 discoveries from the 225KB file-dump via `execute_code`
  with double `json.loads` (correct — see "Handling large recall
  outputs" in `decide-tool-mechanics.md`)
- Built `already_ranked_ids` from the 2h window via regex extraction
  of `Discovery Memory ID: NNN` patterns from prior decision content
  (correct)
- Computed composite scores using connectedness + novelty + recency
  (correct framework)
- Used priority-weighted scoring (CRITICAL=1.5, IMPORTANT=1.0,
  NICE_TO_KNOW=0.4) — this is a DEVIATION from the skill's calibrated
  additive boost (+0.50/+0.25/+0.00) and may have skewed the ranking
  in ways that the additive-boost framework would not
- All 3 `mazemaker_remember` calls succeeded on first attempt
  (bodies were 1500-1800 words, well within the embedding round-trip
  budget; the 1700-word timeout case from 05:00Z was transient)

## What the cycle did WRONG — the cross-day re-find guard

The cross-day re-find guard was added to the skill at 2026-06-23
05:45 UTC. It explicitly documents the BofA case as the worked
example:

> 826570 (discovery:pulse-wurm-20260623_bofa35) created today 03:XX UTC,
> re-surfacing the BofA CEO 35% stablecoin drain story.
> 826578 (decision:rank-20260622-2335-important-1-bofa-ceo-stablecoin-35-percent-deposit-drain-2026)
> was written YESTERDAY 23:35 UTC, more than 6h before the 05:45 cycle.

The 06:15 cycle was THE NEXT CYCLE AFTER 05:45. It had 14 unranked
candidates, including 826570. The cycle ran the 2h dedup (which
correctly excluded the 11 discoveries in the 2h window) and then
proceeded to score the remaining 14 candidates — but never ran the
cross-day re-find check.

The cycle's recall for "BofA stablecoin deposit drain" returned
10 results, ALL with `fact:*` or `decision:*` labels (hence
`connectedness=1.00`). The cycle interpreted this as strong graph
integration and used it as a positive signal for scoring. But the
cycle did NOT inspect what those 10 results WERE — specifically,
it did not check whether the top-1 result was a `decision:rank-*`
covering the same BofA event.

The cycle's pre-existing `already_ranked_ids` set only captured
discoveries from the 2h window. 826578 was 6h45m old, so 826570
correctly passed the 2h dedup. The cross-day re-find guard was the
MISSING STEP between dedup and scoring.

## Why the guard was missed

The 06:15 cycle's working memory had the cross-day re-find guard
rule available (the skill is in the available skills list and the
05:45 cycle had added the section the same morning), but the cycle
did not invoke the rule. The most likely reasons:

1. **Recall-and-count workflow bias:** the cycle's existing workflow
   was to recall a topic, parse for fact+decision count, compute
   connectedness, and use that for scoring. The cycle did not have
   a separate "is the top-1 a prior decision on the same event?"
   step in the workflow.
2. **High connectedness misread as positive signal:** `conn=1.00`
   looked like the BofA topic was a STRONG candidate. The cycle did
   not realize that high connectedness can also indicate a cross-day
   re-find (the corpus has 10+ prior decisions/facts on the topic
   because yesterday's cycle ALREADY covered it).
3. **2h dedup confidence bias:** the cycle trusted that the 2h
   dedup was sufficient. The cross-day re-find guard was treated
   as an optional extra check, not a mandatory one.
4. **The 826570 → 826578 connection is non-obvious from the
   discovery label alone:** the discovery label is
   `discovery:pulse-wurm-20260623_bofa35` and the prior decision
   label is `decision:rank-20260622-2335-important-1-bofa-ceo-stablecoin-35-percent-deposit-drain-2026`.
   The shared token is "bofa" + "stablecoin" — only visible via
   recall + content inspection.

## The correct cross-day re-find check

The 06:15 cycle should have done this between the 2h dedup and
the scoring step:

```python
# 1. 2h dedup (done)
already_ranked = {826506, 826550, 826590, 826644, 826645, 826651,
                  826665, 826667, 826687, 826706, 826714}
unranked = [d for d in candidates if d['id'] not in already_ranked]

# 2. CROSS-DAY RE-FIND CHECK (MISSED in 06:15 cycle)
refind_ids = set()
for c in unranked:
    topic = extract_topic(c)  # from content body's TOPIC: line
    recalled = mazemaker_recall(query=topic, limit=5)
    for r in recalled[:3]:
        if r['label'].startswith('decision:rank-'):
            # Prior decision exists on this topic — check if it
            # specifically covers THIS discovery
            prior = mazemaker_get(memory_id=r['id'])
            if str(c['id']) in prior['content']:
                # Cross-day re-find confirmed
                refind_ids.add(c['id'])
                break

# 3. Score only non-refind candidates (CORRECT step)
fresh_for_scoring = [c for c in unranked if c['id'] not in refind_ids]
```

## Detection heuristic — when connectedness is suspiciously high

The 06:15 cycle's 826570 had `conn=1.00` AND `top_sim=0.68`. Both
heuristic thresholds for cross-day re-find were exceeded:

- `conn=1.00` (10/10 fact+decision in top-10) AND `top_sim >= 0.6` →
  near-certain cross-day re-find signal
- `conn >= 0.9` AND `top_sim >= 0.55` → probable cross-day re-find signal
- `conn < 0.7` OR `top_sim < 0.5` → fresh-candidate signal

If the cycle had applied this heuristic, 826570 would have been
flagged for explicit cross-day re-find verification. The guard
would have caught it.

## Operational rules going forward

1. **The cross-day re-find guard is MANDATORY, not optional.**
   It must run after 2h dedup and before scoring. There is no
   exception for "obvious" candidates — the BofA case shows that
   high-conn high-sim candidates are EXACTLY where re-finds hide.

2. **The heuristic pre-check (`conn >= 0.9` AND `top_sim >= 0.55`)
   is a hard trigger for explicit cross-day re-find verification.**
   Don't just note it and move on — run the guard.

3. **Companion findings to already-ranked discoveries should be
   referenced, not re-ranked.** The 06:15 cycle ranked 826713 (Masa
   Son) as a standalone decision when the 05:45 cycle's
   `decision:rank-20260623-0545-important-1-sophia-space-apex-orbital-compute-infrastructure-2026`
   already noted 826713 as a "complementary companion finding" in
   its body. The 826713 discovery should not have been re-ranked —
   the prior cycle's triage decision should have been respected
   per the "paired but unranked" rule documented in
   `decide-tool-mechanics.md`.

4. **Priority-weighted scoring (multiplicative) deviates from the
   skill's calibrated additive-boost framework.** The 06:15 cycle
   used `priority_weight * connectedness + novelty + recency` with
   weights CRITICAL=1.5, IMPORTANT=1.0, NICE_TO_KNOW=0.4. The
   skill's calibrated framework is
   `connectedness + novelty + recency + boost` with
   CRITICAL=+0.50, IMPORTANT=+0.25, NICE_TO_KNOW=+0.00. The two
   approaches can produce different rankings for the same input —
   particularly when high-priority candidates have moderate
   connectedness. Future cycles should use the additive-boost
   framework unless explicitly calibrated otherwise.

5. **The `already_ranked_ids` set should be expanded beyond the 2h
   window for cross-day re-find purposes.** The 2h window catches
   same-cycle re-rankings; the cross-day guard catches multi-day
   re-rankings. Both are needed for full coverage.

## Specific cycle outcome (what should have been written)

If the 06:15 cycle had applied the cross-day re-find guard, the
output would have been:

| Rank | Priority | Discovery | Memory ID | Status |
|---|---|---|---|---|
| #1 | CRITICAL | 826493 Microsoft Crypto Clipper | NEW (id 826731) | Legit — security threat, no prior coverage |
| #2 | IMPORTANT | 826713 Masa Son orbital compute dismissal | NOT WRITTEN | Already covered as companion to 826714 in 05:45 cycle's decision body |
| #3 | NICE_TO_KNOW | 826502 NVIDIA Cosmos / GR00T humanoid | NEW | 10.7h old, conn 1.00, novelty 0.52 — second-best legitimate pick |

(826570 BofA would have been filtered out as a cross-day re-find
of 826578.)

## Memory addressable in future cycles

- 826729 = the duplicate decision:rank-* written in this cycle (BofA)
- 826730 = the companion-finding decision:rank-* (Masa Son)
- 826731 = the legitimate decision:rank-* (Crypto Clipper)
- 826578 = the prior BofA decision that should have been detected
  as the cross-day re-find target

Future cycles should be aware that 826729 is a known duplicate of
826578 — if ACT phase queries for the BofA finding, it should act
on 826578 (the older, original) and treat 826729 as a no-op duplicate.
