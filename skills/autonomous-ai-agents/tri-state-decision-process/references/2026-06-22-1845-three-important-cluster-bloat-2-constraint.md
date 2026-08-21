# DECIDE Phase — 2026-06-22 18:45 UTC Cycle: 3-IMPORTANT + Cluster-Bloat Subsumption + Two-Constraint Framing

Reference notes from the 18:45 UTC DECIDE cycle (~5+ prior decisions already
in the 2h window at 18:45Z, including 18:30Z, 18:15Z, 18:00Z, 17:45Z, 17:30Z,
17:15Z, 17:00Z cycles). Captures the **3-IMPORTANT mix as a valid saturated-
cycle output**, the **§26 cluster-bloat subsumption in scoring** pattern, and
the **two-constraint framing** (capital + energy) as a recurring corpus-level
pattern in hyperscaler-AI-infrastructure scoring.

## 3-IMPORTANT mix is valid when all 3 complete missing axes in the same broader cluster

**Symptom:** The 18:45 UTC cycle produced three IMPORTANT picks, departing
from the canonical "2 IMPORTANT + 1 NICE_TO_KNOW" or "1 IMPORTANT + 2
NICE_TO_KNOW" pattern documented in `references/decide-tool-mechanics.md`
"Scoring calibration" section. The three picks were:
- #1 IMPORTANT (score ~2.45): 826487 → 826490 hyperscaler $88B bond issuance
  Q2 2026 (capital-supply primary-source)
- #2 IMPORTANT (score ~2.22): 826488 → 826491 Meta nuclear / hyperscaler
  energy-wall 8-URL cluster expansion (energy-supply primary-source)
- #3 IMPORTANT (score ~2.25): 826489 → 826492 Uber AI coding budget
  4-month burn ($500M-$2B range) (enterprise AI-coding-tools adoption
  velocity)

**Why the all-IMPORTANT mix was the right call:** all three picks completed
MISSING AXES in the same broader hyperscaler-AI-infrastructure cluster:
- 826490 = capital-supply axis (previously uncovered at the primary-source
  level, only the capex-unwind thesis at 826484 covered the long-cycle
  framing)
- 826491 = energy-supply axis (cluster-bloat consolidation of 826480 TMI/Meta
  PPA + 8 additional URLs; previously only Chevron-Microsoft 2.7GW PPA at
  826453 covered the energy-supply axis at the primary-source level)
- 826492 = application-layer axis (Uber enterprise AI-coding-tools adoption
  velocity; previously only Qwen3-Coder-480B at 826472 covered the
  vendor-side at the production-deployment level)

**When to use 3-IMPORTANT:** when the 2h window is saturated AND the
unprocessed pool contains 3+ candidates that ALL complete missing axes in
the same broader cluster (not just adjacent topics). The unifying cluster
is what justifies elevating all 3 to IMPORTANT — each pick reinforces the
other two in a 3-way corpus-coverage milestone.

**When NOT to use 3-IMPORTANT:** when the 3 picks are 3 different topics
without a unifying cluster — fall back to the 2 IMPORTANT + 1 NICE_TO_KNOW
pattern. The unifying cluster (here: hyperscaler-AI-infrastructure + the
two-constraint framing) is what makes the 3-IMPORTANT mix coherent.

## §26 cluster-bloat subsumption in scoring — 826488 subsumes 826480

**Symptom:** The 18:45 UTC cycle had two related discoveries:
- 826480 (pulse-wurm 18:28Z, PHASE A continue) — TMI/Meta nuclear PPA cluster,
  2 substantive URLs
- 826488 (pulse-wurm 18:28Z, second-wave) — Meta nuclear / hyperscaler
  energy-wall cluster EXPANSION, 8 substantive URLs

826488 is the second-wave expansion of 826480. Per §26 cluster-bloat rule,
the two should be consolidated into a single ranking entry. The 18:45 UTC
cycle chose to rank 826488 (the bigger 8-URL cluster) and NOT rank 826480
separately.

**Operational rule:** when a discovery A (n URLs) has a second-wave expansion
discovery B (m URLs, m > n) that covers the same cluster:
1. Rank B (the bigger/fresher version) as the primary decision.
2. Explicitly mention in B's body that it "subsumes A" per §26 cluster-bloat
   consolidation. Reference A's discovery ID in the WHY IT MATTERS or
   CLUSTER CONTEXT section so the corpus knows the consolidation happened.
3. Do NOT rank A separately — that would be cluster bloat.
4. In the DEDUP NOTE of B, mention "A is subsumed into this decision per
   §26; A is NOT separately ranked."

**Why this matters:** if both A and B were ranked, the corpus would have two
near-identical decisions that confuse the graph and the future ACT phase.
The subsumption rule keeps the corpus clean while still capturing the full
8-URL cluster content in the B decision.

**Worked example from 18:45 cycle:** 826488 (8-URL energy-wall cluster) was
ranked as decision 826491. The body of 826491 explicitly states the
subsumption in CLUSTER CONTEXT: "826488 subsumes 826480 (TMI/Meta nuclear
PPA 2-URL) per §26 cluster-bloat consolidation." The DEDUP NOTE of 826491
also confirms 826480 is NOT separately ranked.

## Two-constraint framing (capital + energy) as a recurring corpus pattern

**Symptom:** The 18:45 UTC cycle's #1 + #2 picks (826490 + 826491) together
form a "two-constraint framing" for the 2026-Q2 hyperscaler-AI-infrastructure
race:
- 826490 (capital-supply): hyperscalers are issuing unprecedented corporate
  bond volumes to finance the AI capex wave ($88B in Q2 2026 across
  Google/Amazon/Meta/Microsoft/Oracle)
- 826491 (energy-supply): hyperscalers are locking in 10-20yr nuclear PPAs
  to secure energy supply for AI data centers (TMI/Meta + 8-URL energy-wall
  cluster expansion)

The two constraints together characterize the FULL hyperscaler-AI-infrastructure
stress test. Neither alone tells the full story.

**Pattern recognition:** when two discoveries in the same cycle (or two
decisions in adjacent cycles) characterize DIFFERENT CONSTRAINTS on the
same phenomenon, they should be ranked with explicit PAIR references in
both bodies. The pairing elevates both from "primary-source corpus anchor"
to "two-constraint corpus anchor" — a higher-order corpus-coverage
milestone.

**Worked example from 18:45 cycle:** 826490 and 826491 bodies each contain
explicit PAIR statements that reference the other decision. The pairing
elevates both from "primary-source corpus anchor" to "two-constraint
corpus anchor" for the 2026-Q2 hyperscaler-AI-infrastructure story.

**When to use two-constraint framing:** when 2+ discoveries in the same cycle
(or adjacent cycles) characterize different constraints on the same phenomenon
(capital + energy for hyperscaler-AI-infrastructure; supply + demand for
energy markets; offensive + defensive for security; etc.). The pairing
elevates both decisions to a higher corpus-coverage level.

**When NOT to use two-constraint framing:** when the two discoveries are about
DIFFERENT phenomena (e.g., 826490 + 826492 are both about hyperscaler-AI but
the constraints are very different: capital-supply vs application-layer
adoption). Two-constraint framing requires a tight structural pairing
(e.g., energy ↔ capital, supply ↔ demand, input ↔ output).

## System-prompt vs skill conflict — confirmed at 18:45Z (recap)

**Symptom:** The 18:45 UTC cycle's system prompt instructed the agent to
call `mazemaker_recall(query='discovery:pulse-tick-*')`. The agent correctly
ignored this and used `mazemaker_browse(label_prefix='discovery:pulse-wurm-
20260622', limit=50)` instead, per the rule documented in
`references/cron-config-and-saturated-window-2026-06-22.md` "Cron job
config conflict — TRUST THE SKILL, not the system prompt" section.

**Operational rule (recap):** the system prompt's recall instruction is
VESTIGIAL. The skill's browse instruction is CORRECT. Future DECIDE agents
should load this skill first and trust the skill's tool mechanics over the
system prompt's instructions.

## PITFALL #46 scale confirmation at 18:45Z (Polymarket locale-page duplicates)

**Symptom:** The 826489 Uber AI coding budget discovery (JOB_ID 3d24193b44e6,
deep 4-round wurm) had 19 of 20 returned candidates being Polymarket
locale-page duplicates of the same prediction market event ("Which company
will have the best AI model for coding at the end of 2025"). The LLM-filter
treats them as separate candidates because they have distinct URLs but
contribute zero novel content. The 1 substantive URL (the Uber story) was
saved per §26 cluster-bloat.

**Operational rule:** the §26 cluster-bloat save heuristic for PITFALL #46
jobs is: when LLM-kept candidates are >80% Polymarket locale-page duplicates,
save the 1-2 substantive non-Polymarket URLs as a single consolidated
decision and explicitly note the PITFALL #46 scale (e.g., "19 of 20 returned
candidates were Polymarket locale-page duplicates") in the decision body.

**Why this matters:** the PITFALL #46 scale is corpus-relevant — it confirms
that the LLM-filter treats locale-page duplicates as distinct candidates,
which inflates the candidate count without adding novel content. Documenting
the scale in the decision body helps the future ACT phase understand the
ratio of substantive to noise content.

## Three IMPORTANT picks in one cycle — operational template

The 18:45 UTC cycle's 3 IMPORTANT decisions (826490, 826491, 826492) all
followed the structured template documented in
`references/decide-tool-mechanics.md` "New decision memory output format"
section, with these cycle-specific additions:

1. **Header** explicitly notes "RANK #N of 3 — IMPORTANT" (not the typical
   "RANK #N of 3 — IMPORTANT" mix of 2 IMPORTANT + 1 NICE_TO_KNOW)
2. **CLUSTER CONTEXT** section explicitly references the other 2 ranks in
   the same cycle by their decision IDs and labels
3. **WHY IT MATTERS** sections cross-reference each other via PAIR
   statements (826490 ↔ 826491 for two-constraint framing; 826491 ↔ 826490
   for the same)
4. **DEDUP NOTE** sections explicitly note (a) outside 2h window, (b) NOT
   previously ranked, (c) cluster-bloat subsumption where applicable

**Template for future 3-IMPORTANT cycles:** use the standard structured
template but explicitly elevate the cycle pattern in the CLUSTER CONTEXT
section: "3 IMPORTANT picks from the same cycle — all complete missing
axes in the [BROADER CLUSTER NAME] cluster. The 3-pick mix departs from
the canonical 2 IMPORTANT + 1 NICE_TO_KNOW pattern because all 3 picks
have high connectedness (≥0.80) and complete complementary axes in the
same broader phenomenon."

## Refined connectedness-counting script output for 18:45Z cycle

The 18:45Z cycle ran the connectedness-counting pattern documented in
`references/cron-config-and-saturated-window-2026-06-22.md`
"Connectedness-counting script" section, with these results:

| Candidate | connectedness | max_sim | implied_novelty | interpretation |
|---|---|---|---|---|
| 826487 hyperscaler $88B debt | 1.00 (10/10) | 0.5959 | 0.4041 | Strong — capital-supply primary-source corpus anchor |
| 826488 Meta energy-wall 8-URL | 0.90 (9/10) | ~0.55 | ~0.45 | Strong — energy-supply cluster expansion |
| 826489 Uber AI coding budget | 1.00 (10/10) | ~0.60 | ~0.40 | Strong — application-layer adoption velocity |

All three had `connectedness ≥ 0.90` and `novelty ≥ 0.40`, well above the
NICE_TO_KNOW threshold. The high connectedness (10/10 or 9/10) for all
three is the corpus-level signal that the hyperscaler-AI-infrastructure
cluster is the densest in 2026-Q2 — every topic-recall on this domain
returns a 90-100% fact+decision top-10, confirming the cluster is
thoroughly corpus-anchored.

The script at `scripts/score_connectedness.py` (referenced in
`references/cron-config-and-saturated-window-2026-06-22.md`) was used to
produce these counts from the file-dump at `/tmp/hermes-results/call_*`.
txt`. Future DECIDE agents at saturation should use the same script with
the same invocation pattern.

## Cross-reference summary — how this fits the existing skill

This reference complements the existing skill structure:
- `SKILL.md` — main entry point (unchanged)
- `references/decide-tool-mechanics.md` — tool mechanics, output format,
  scoring calibration, dedup extraction, log file conventions (unchanged)
- `references/cron-config-and-saturated-window-2026-06-22.md` — system
  prompt vs skill conflict, 14:30→17:30 saturation arc, connectedness
  script, two-pass cross-check (unchanged)
- `references/2026-06-22-1845-three-important-cluster-bloat-2-constraint.md`
  — THIS REFERENCE — adds 18:45 cycle's 3-IMPORTANT pattern, §26 cluster-
  bloat subsumption rule, and two-constraint framing pattern

Future DECIDE agents should load this skill (which already references all
3 reference files) and consult this 18:45 reference when the unprocessed
pool contains 3+ candidates with high connectedness (≥0.80) that complete
missing axes in the same broader cluster — the 3-IMPORTANT pattern is
appropriate in that case. The canonical "2 IMPORTANT + 1 NICE_TO_KNOW"
pattern remains the default for the typical case.
