# Skipped Re-Rank Horizons (don't re-rank already-decided items)

The 2-hour dedup window in [canonical-workflow.md](canonical-workflow.md) Step 2 catches items decided in the immediately preceding cycle. But broader "already-decided" windows matter too. Confirmed across multiple cycles (2026-06-21 03:30Z, 04:02Z).

## Three re-rank horizons

| Horizon | Window | Action |
|---|---|---|
| Hard dedup | 0-2h | Always skip — same item is noise |
| Soft saturation | 2-9h | Skip IF the new context offers no new angle AND the existing decision is recent (within the same day) |
| Already-clustered | 9h+ | Skip IF the discovery is a re-discovery of an already-ranked paper / cluster member (look up the topic, not the discovery_id) |

## Re-discovery anti-pattern

A NEW discovery_id pointing to the SAME paper/cluster that was already ranked 16-36h ago is NOT a fresh signal. Examples confirmed:
- 824853 (full-duplex omni-modal cluster) → already ranked as 824908 ~16h ago (decision:rank-20260620-nice_to_know-2-realtime-fullduplex-omni-modal-cluster)
- 824984 (ClawHub Security Signals paper) → already ranked as 822501 ~36h ago (decision:rank-20260619-important-clawhub-security-signals), as the discovery_id 822439 backing that decision

Re-deciding such items creates duplicate decision:rank-* memories that the ACT phase will then have to de-duplicate. Don't do it.

## Soft saturation (2-9h, same-day)

If a discovery was decided 3-9h ago in a prior cycle and the new context offers no new angle, skip it even though it passes the 2h hard dedup. Examples confirmed (2026-06-21 04:02Z cycle):
- 825242 (ProgramBench) → decided as 825260 ~4h ago (decision:rank-20260620-important-1-programbench-hard-ceiling-2350). No new context → skip.
- 825243 (XDA Claude Code consumerization) → decided ~4h ago. No new context → skip.
- 825244 (phpmypython Claude binary patch) → decided ~4h ago. No new context → skip.

The decision labels from earlier cycles are visible in the browse output of `decision:rank-*` so this check is cheap. Don't manufacture a re-rank just to hit the 3-decision output quota.

## When re-ranking IS appropriate

Re-rank an item only if:
- The original decision has a substantive error (wrong priority, wrong cluster context) — but this should be SUPERSEDED via the dream_supersedes phase, not re-decided.
- New context emerged that meaningfully changes the priority (e.g. an item previously NICE_TO_KNOW now has an active security incident attached) — in this case re-rank with a new label that explicitly references the original.

Default: don't re-rank. The 2h hard dedup + soft saturation + already-clustered rules cover 95% of cases.

## Operational signal

If the eligible pool after dedup is < 3 items AND no genuine fresh discoveries are available, write fewer than 3 decisions and explain in the cycle-log line. This is normal during discovery saturation periods (60-80% of pool already decided is common).