# DECIDE Phase — Post-Saturation Recovery & Low-Saturation Patterns

Reference notes from the 2026-06-22 18:30 UTC DECIDE cycle, the first
cycle AFTER the 40+-decision saturation peak (17:30 UTC). Captures the
saturation-wave pattern, the 3-IMPORTANT/0-NICE_TO_KNOW pick mix in
low-saturation cycles, the FRESH-DIRECTION-tag dominance as a novelty
signal, and the max_similarity=0.785 cross-axis coverage case.

## Saturation-wave pattern — the cycle is NOT monotonically saturated

**The arc of 2026-06-22:**
- 14:30 UTC: 9 prior decisions in 2h (light saturation)
- 15:46 UTC: 21 prior decisions in 2h (moderate saturation)
- 16:15 UTC: 24 prior decisions in 2h (heavy saturation)
- 16:30 UTC: 30 prior decisions in 2h (heavy saturation)
- 17:00 UTC: 33+ prior decisions in 2h (heavy saturation)
- 17:30 UTC: 40+ prior decisions in 2h (EXTREME saturation peak)
- **18:30 UTC: 6 prior decisions in 2h (POST-SATURATION RECOVERY)**

**Why the recovery:** The 14:30 → 17:30 saturation peak was driven by
the Fable 5 / Glasswing / Anthropic US-gov escalation cluster emerging
across 9 cycles in 3 hours, generating 3 decisions per cycle = 27
decisions in 3h. As the cluster completed (after the 17:00 cycle added
all 7 narrative arcs + Mythos pivot + Anthropic IPO), the production
rate dropped back to 3 decisions/cycle (one per cycle per cron), so
the 2h window only contained 6 decisions from 16:30 onwards.

**The 18:30 cycle's data:**
- Pool: 50 discoveries returned by `mazemaker_browse(label_prefix='discovery:', limit=50)`
- After content-extracted ID dedup against 6 prior decisions: 37 unprocessed
- After companion-finding / sub-finding filter: 4-5 genuinely novel candidates
- 3 picks written, all IMPORTANT, all FRESH-DIRECTION domain-tagged

**Operational rule for post-saturation cycles:**

1. **Recalibrate scoring** — the 1-IMPORTANT + 2-NICE_TO_KNOW pattern
   from heavy-saturation cycles does NOT apply when 2h window drops
   back below ~10 decisions. Low-saturation cycles can have 3 IMPORTANT
   picks if the candidates justify it.
2. **Trust FRESH-DIRECTION as novelty signal** — in heavy saturation,
   the novel candidates are CRITICAL/IMPORTANT axis-completion (Fable 5
   multi-axis, Stargate infrastructure-axis, Big Tech AI competitive
   landscape). In low saturation, the novel candidates are FRESH-DIRECTION
   corpus-anchors for under-covered domains (energy, hardware, climate,
   finance). Both are valid IMPORTANT — the difference is whether the
   corpus has been EXTENDED (low-saturation case) or COMPLETED
   (heavy-saturation case).
3. **Higher recall query budget is OK** — in heavy saturation, you'd
   run 1-2 topic-recalls per candidate to confirm coverage. In low
   saturation, you can run 4-6 topic-recalls (one per candidate) without
   exhausting context, because the 2h window is small enough that the
   content-extracted ID set is fast to build.

## 3-IMPORTANT / 0-NICE_TO_KNOW pick mix (new pattern)

**The 18:30 cycle's picks:**

| Rank | Discovery | Topic | Connectedness | Max-Sim | Novelty | Priority |
|------|-----------|-------|---------------|---------|---------|----------|
| 1 | 826471 | AI capex unwind thesis 2027-2028 | 9/10 | 0.548 | 0.452 | IMPORTANT |
| 2 | 826479 | DRAM/HBM doubling Q1 2026 (memory wall) | 9/10 | 0.616 | 0.384 | IMPORTANT |
| 3 | 826470 | Nature 2026-06-21 article on AI degrading skills | 10/10 | 0.652 | 0.348 | IMPORTANT |

**Why all IMPORTANT (not 1 + 2 NICE_TO_KNOW as in heavy saturation):**

1. **Each pick completed a different cluster axis that was previously empty:**
   - 826471 → long-cycle structural framing (cycle-thesis anchor) for
     AI capex / energy / finance 2027-2028 horizon. Existing decisions
     covered per-deal PPAs (Microsoft-Chevron 2.7GW, TMI restart) but
     no single decision framed the SYSTEMIC 2027-2028 unwind.
   - 826479 → hardware/supply-side bottleneck anchor. Existing decisions
     covered demand-side (capex, PPAs, talent, IPOs) but no single
     decision framed the FAB-CAPACITY bottleneck.
   - 826470 → primary-source validation (Nature as highest-prestige
     general-science venue) for the AI-cognitive-impact cluster.

2. **Each pick had specific actionability for the ACT phase:**
   - 826471 → suggested action: `config_change` (long-cycle seed ring
     buffer) + `skill_update` (pulse-wurm tick-learnings cluster anchor)
   - 826479 → suggested action: `config_change` (hardware seed ring
     buffer) + `fact_save` (consumer-DRAM-price-doubling fact anchor)
   - 826470 → suggested action: `skill_update` (Nature primary-source
     weighting) + `fact_save` (Nature article as corpus anchor)

3. **Each pick had high cross-axis connectedness** (9-10 fact+decision
   memories in top-10) — confirming they were not noise but corpus
   bridges worth pinning.

**Operational rule:** In low-saturation cycles, the pick mix can
deviate from the 1-IMPORTANT + 2-NICE_TO_KNOW pattern. If all 3 candidates
have `connectedness > 0.7` AND clear ACT-phase actionability, write all
3 as IMPORTANT. Do NOT artificially downgrade to NICE_TO_KNOW to fit a
template. Conversely, if even 1 of 3 has low actionability, downgrade
that one to NICE_TO_KNOW.

## max_similarity=0.785 cross-axis coverage case (new threshold data)

**The 18:30 cycle's TMI/Meta nuclear PPA (826480) case:**

- Discovery: tick 23 1828 PHASE A CONTINUE — Microsoft TMI restart +
  Meta nuclear PPAs 2026 (r/technology 1fm8bga + r/wallstreetbets 1q860z1)
- Topic-recall with `mazemaker_recall_multi` angles on "Microsoft Three
  Mile Island Meta nuclear PPA 2026" returned:
  - Top-1 hit: `fact:microsoft-chevron-2_7gw-west-texas-ppa-2026-06-22`
    at similarity=0.564 (BUT: this is a related but DIFFERENT PPA story —
    Chevron gas in West Texas, not Meta nuclear)
  - Top-2 hit: `decision:rank-20260622-1815-nice_to_know-3-ai-aerosol-optical-depth...`
    at similarity=0.493 (topically adjacent)
  - Top-3 hit: `discovery:pulse-wurm-20260622_chevron-microsoft-west-texas-2gw-ppa`
    at similarity=0.589 (the original Chevron-Microsoft discovery)
- MAX similarity to closest non-self memory: 0.785 (computed by the
  recall-multi engine, considering all top-10 results, not just top-3)
- The 0.785 was the OVERALL max — likely against the existing
  `decision:rank-20260622-1700-important-2-chevron-microsoft-west-texas-2gw-20yr-ppa`
  (fact 826347) which has similar hyperscaler-PPA semantics even though
  it's a gas PPA, not a nuclear PPA

**Decision:** SKIP 826480 (label as NOISE).

**Why the high max_sim + cross-axis coverage still indicates "covered":**
- The energy-PPA cluster is already comprehensively covered
  (Chevron-Microsoft 2.7GW PPA, Stargate Michigan 1GW, Norway Stargate,
  TMI restart, xAI Memphis 3.5GW)
- Adding a 6th PPA story (Meta nuclear) doesn't add a new axis — it
  just adds a second-mover signal to the existing hyperscaler-PPA axis
- The novelty (0.215) was below the 0.4-0.5 threshold the skill
  recommends for IMPORTANT

**Operational rule for the max_similarity threshold:**

The skill's `references/decide-tool-mechanics.md` "Scoring calibration"
section says "topic-recall with similarity >= 0.5 = likely already covered".
The 18:30 cycle confirmed this threshold holds even at higher values
(0.785 = definitively covered) and at moderate values (0.616 DRAM
= moderately covered but still novel hardware-supply-side framing worth
ranking). The 0.4-0.5 band is the ambiguous zone where content-extracted
ID check is needed to confirm coverage; >= 0.5 = skip with confidence.

**Threshold table updated:**

| Max similarity | Action |
|---|---|
| < 0.4 | Definitely novel, rank highly |
| 0.4 - 0.5 | Ambiguous — content-extracted ID check needed |
| 0.5 - 0.6 | Likely covered, cross-check + verify axis-completion |
| 0.6 - 0.7 | Probably covered, only rank if axis-completion is unambiguous |
| >= 0.7 | Covered, skip |

## Why topic-recall still beats content-extracted ID check in low-saturation

In heavy saturation (30+ decisions/2h), content-extracted ID check is
faster because you've already built the 2h decision set. In low saturation
(6 decisions/2h like the 18:30 cycle), the 2h decision set is tiny and
the content-extracted ID check is fast regardless. The 18:30 cycle used
BOTH approaches and confirmed they're complementary:

1. **Content-extracted ID set** (fast pre-filter): built from 6 prior
   decision contents, identified 29 unique covered discovery IDs. Reduced
   pool from 50 to 37.
2. **Topic-recall per candidate** (scoring step): ran 4 `recall_multi`
   queries (one per top candidate) and computed connectedness + novelty
   from the top-10 results.

The hybrid pattern worked well. The 18:30 cycle's lesson: in low
saturation, run topic-recall on ALL surviving candidates (not just the
top 3) because the recall is cheap and the connectedness data informs
both the scoring AND the final priority classification (cluster axis
completion vs. niche corpus anchor).

## Cluster axis completion check (used in 18:30 cycle)

For each surviving candidate, after topic-recall, check the top-3 hits'
labels. If the candidate's top-3 hits all share a parent decision
cluster (e.g., 826440, 826441, 826442 all in the Big Tech AI talent
cluster), the candidate is likely a companion finding to that cluster
→ check if the companion finding ADDS a new axis or just repeats.

The 18:30 cycle's TMI/Meta nuclear (826480) check: top-1 hit was the
Chevron-Microsoft 2.7GW PPA decision. Both are hyperscaler-PPA stories.
The TMI/Meta nuclear adds "second-mover signal" but no NEW axis. → NOISE.

By contrast, the 18:30 cycle's DRAM/HBM (826479) check: top-3 hits were
Big Tech AI talent decision, Aurora Earth energy imbalance decision, and
a misc Anthropic decision. NONE of these were hardware-supply-side. The
DRAM finding adds a NEW axis (physical-material constraint) to the
existing demand-side AI-scaling cluster. → IMPORTANT.

**Operational rule for cluster axis completion:**

1. For each surviving candidate, run topic-recall and read the top-3
   hits' labels.
2. Identify the parent cluster (if any) — typically a high-engagement
   fact: or decision: memory with 3+ prior decisions referencing it.
3. Determine: does the candidate ADD a new axis (e.g., supply-side vs
   demand-side, primary-source vs commentary, regulatory vs technical)
   or just REPEAT an existing axis?
4. If NEW axis: rank. If REPEAT: skip (or NICE_TO_KNOW if it's a
   particularly canonical second-mover signal).

## FRESH-DIRECTION tag → IMPORTANT candidate pipeline (new 18:30 pattern)

In the 18:30 cycle, ALL 3 picks were tagged FRESH-DIRECTION in the
discovery content body. This is a SHIFT from heavy-saturation cycles
where FRESH-DIRECTION picks were usually NICE_TO_KNOW (corpus
extension) and CRITICAL/IMPORTANT picks were axis-completion discoveries.

**The 18:30 cycle's pattern:** FRESH-DIRECTION discoveries became
IMPORTANT when they:
1. Surfaced a primary-source with high engagement (Nature article, r/WSB
   383-upvote capex thesis, r/pcmasterrace 304-comment DRAM thread)
2. Framed a corpus-anchor that paired naturally with existing per-deal
   or per-story facts (e.g., DRAM doubling as the supply-side complement
   to Microsoft-Chevron gas PPA as a demand-side story)
3. Had ACT-phase actionability (config_change for seed ring buffer,
   skill_update for cluster anchor, fact_save for primary-source citation)

**Operational rule:** In low-saturation cycles, FRESH-DIRECTION
discoveries are FIRST-CLASS IMPORTANT candidates, not NICE_TO_KNOW
fillers. Treat them as primary candidates alongside CRITICAL/IMPORTANT
axis-completion findings.

## Cycle log entry for 18:30

```
2026-06-22T18:30Z cycle=decide timestamp=20260622_1830
pool=50 (browse limit=50, after dedup+filter=37, after companion-filter=4-5)
ranks=3 (3 IMPORTANT, 0 NICE_TO_KNOW)
ids written: 826484 (capex-unwind), 826485 (dram-hbm), 826486 (nature-ai-skills)
skipped: 826480 (TMI/Meta nuclear, max_sim=0.785, already covered by 826453 chevron-microsoft)
skipped: 826483, 826482, 826481 (fail-pattern discoveries, NOISE)
skipped: 826368-826449 cluster companions (already covered)
prior 2h decisions: 6 (low saturation, post-recovery from 17:30 peak of 40+)
saturation: LOW (cycle pattern = 3 IMPORTANT, 0 NICE_TO_KNOW)
pick mix: 3x FRESH-DIRECTION (energy, hardware, climate-cognitive)
```
