# Saturation Decay — Rolling-Window Cycle Dynamics (NEW — 2026-06-23 00:30 cycle)

**The pattern:** at very high saturation, the 2h-window decision count can oscillate
substantially between adjacent 15-min cycles. The 00:15Z cycle (case 4: 1 viable
pick) was followed by the 00:30Z cycle (3 viable picks), because the 2h rolling
window had moved past the densest portion of the 2026-06-22 second-wave coverage.

## Worked example: 00:15Z → 00:30Z oscillation

**00:15Z cycle (2026-06-23):**
- 2h window: 22:15Z 2026-06-22 to 00:15Z 2026-06-23
- Prior decisions in window: 14+ (22:46Z Meta keylogger + Pew + Kunal Shah,
  23:35Z BofA + Zig + Education, 00:00Z Uber + 2 others)
- Viable candidates (connectedness > 0.5 AND novelty > 0.4): 1
- Output: 1 NICE_TO_KNOW (826590 Apple UK iCloud, id 826602)

**00:30Z cycle (2026-06-23):**
- 2h window: 22:30Z 2026-06-22 to 00:30Z 2026-06-23
- Prior decisions in window: 14+ (22:46Z, 23:35Z, 00:00Z, 00:15Z cycles)
- Viable candidates: 3
  - 826487 hyperscaler $88B Q2 2026 bond issuance (IMPORTANT)
  - 826502 NVIDIA Cosmos / GR00T humanoid frontier deployment 2026 (IMPORTANT)
  - 826470 Nature 2026-06-21 AI skills degradation empirical study (NICE_TO_KNOW)
- Output: 3 decisions (ids 826608, 826609, 826610)

**What changed in 15 minutes:** the 22:15Z-22:30Z boundary of the rolling 2h window.
At 00:15Z, the 2h window included 22:15-22:30Z (a quiet period with 0-1 decisions
from prior cycles). At 00:30Z, the 22:15-22:30Z slice fell OUT of the window, but
the candidates that were blocked by the 22:15-22:30Z slice (which were the
2026-06-22 second-wave discoveries like 826487, 826502, 826470) were still
uncovered — the 22:46Z / 23:35Z / 00:00Z cycles had been busy with 2026-06-23
tick-38/39 discoveries (apple-uk, education, mythos, bofa, etc.), not the older
2026-06-22 second-wave material.

**The general rule:** at 14+ decisions/2h with 1 viable pick (case 4), the very
next cycle (15-30 min later) may find 3 viable picks because (a) the 2h window
has rolled forward, and (b) the next-decision-tier candidates (those that were
blocked by the 1-pick tier in the previous cycle) become available. The oscillation
between "1 pick" and "3 picks" at high saturation is normal.

## Cross-cluster macro synthesis (NEW — 2026-06-23 00:30 cycle)

When the cycle's 3 picks span 2+ different topic clusters, the cycle report
should note the **cross-cluster macro synthesis** that emerges from the picks.
This is distinct from the "pair-into-narrative" pattern (which is about
constructing the picks themselves); the macro synthesis is about the
operator-facing report.

**Worked example from 00:30Z cycle:**

The 3 picks covered 3 distinct clusters:
- 826487 → financial-system × capital-structure × hyperscaler AI capex
- 826502 → robotics × frontier-models × deployment maturity
- 826470 → AI-ethics × primary-source × skill degradation

The cycle report noted the **2026-Q2 macro picture** that emerges:
"AI infrastructure is (a) debt-financed, (b) energy-constrained, (c) reaching
frontier-deployment maturity in humanoids, (d) triggering primary-source
Nature meta-findings on skill degradation."

**Operational rule for cycle reports:**

1. If the cycle's picks span 2+ distinct clusters, the report should include
   a 1-3 sentence "macro synthesis" note that names the cross-cluster pattern.
2. The synthesis should be specific (name the 4-5 components of the pattern),
   not generic ("the AI industry is changing fast").
3. The synthesis should reference existing decisions that the picks pair with
   (e.g., "pairs with 826480 TMI/Meta nuclear PPA + 826484 capex unwind thesis").
4. If the picks are all from the same cluster, do NOT force a macro synthesis —
   report them as standalone picks.

**Why this matters:** the cycle report is the operator's primary visibility
into the corpus evolution. Cross-cluster synthesis notes turn 3 disjoint
picks into a 1-sentence corpus-level narrative, which is much more useful
for operator situational awareness than 3 separate "decision written" lines.

## Soft vs hard dedup for out-of-window NICE_TO_KNOWs (NEW — 2026-06-23 00:30 cycle)

**The tension:** the 2h dedup rule (per "Dedup against 2h decision window" in
`references/decide-tool-mechanics.md`) is a hard rule: skip items already written
as `decision:rank-*` in the last 2 hours. The literal rule allows re-ranking
items decided MORE than 2h ago.

**The practical issue:** some discoveries are ranked as NICE_TO_KNOW in earlier
cycles (e.g., 826524 vercel-cloudflare-workers-claude-code was ranked as
`decision:rank-20260622-2130-nice_to_know-3-vercel-cloudflare-workers-claude-code-cluster-bloat`
3h before the 00:30Z cycle). When the next cycle finds the same topic re-surfacing
as a fresh discovery (826524 again, or a near-duplicate), the literal 2h rule
allows re-ranking. But re-ranking a NICE_TO_KNOW already in the corpus creates
a duplicate decision entry with no new information.

**Worked example from 00:30Z cycle:**

The 00:30Z candidate pool included 826524 (vercel-cloudflare-workers-claude-code).
This discovery was already ranked at 21:30Z as NICE_TO_KNOW. The 00:30Z cycle was
at 00:30Z, which is 3h after the 21:30Z decision — outside the 2h dedup window.

The 00:30Z cycle chose to NOT re-rank 826524 because:
- The earlier decision already covers the same topic with the same score
- Re-ranking would create a duplicate decision entry
- The 3 slots are better spent on genuinely novel picks (826487, 826502, 826470)

**Operational rule (refined dedup):**

1. **Hard dedup:** skip items decided in the last 2h (the literal rule). No exceptions.
2. **Soft dedup:** for items decided 2-6h ago, prefer to skip if the prior decision
   was NICE_TO_KNOW AND the new candidate has the same or lower score than the
   prior decision. Re-rank only if the new candidate is substantially better
   (e.g., primary-source URL, higher engagement, novel framing).
3. **No dedup:** for items decided more than 6h ago, treat as fresh. The
   corpus context may have changed enough that a re-ranking is meaningful.
   Consider whether the re-ranking is updating the corpus understanding
   (e.g., the topic is now corpus-complete) or just adding noise.

**Companion principle:** the goal of the 2h dedup is to prevent the same
discovery from being ranked twice in consecutive cycles. The 2-6h soft
dedup extends the spirit of the rule to NICE_TO_KNOW re-rankings. The
6h+ no-dedup acknowledges that long-window re-rankings may be valuable
if the corpus context has evolved (e.g., new cluster-anchor picks make
an older NICE_TO_KNOW a NICE_TO_KNOW cluster-bridging pick).

## Implications for the saturation heuristic (case 1-4)

The existing case-1/case-2/case-3/case-4 saturation heuristic in
`references/cron-config-and-saturated-window-2026-06-22.md` is preserved.
The 00:30Z cycle validated that case 4 ("1 viable pick") can flip to case 1/2
("3 viable picks") in 15-30 minutes when the 2h rolling window moves past
the densest portion. The case-1/2/3/4 thresholds are still correct at
each cycle; the oscillation between cases is normal and not a sign of
incorrect scoring.

**Operational note for future DECIDE agents:** if a case-4 cycle produces
a single NICE_TO_KNOW, the NEXT cycle (15-30 min later) is likely to be
case-1 or case-2 with 3 picks. This is not a sign that the case-4 cycle
"missed" picks — it's the natural oscillation pattern. Do NOT try to
"backfill" the case-4 cycle by re-ranking the same candidate in the
case-1/2 cycle.
