# DECIDE Phase — Cron Config Conflicts & 2026-06-22 Saturation Learnings

Reference notes from the 2026-06-22 16:15 UTC DECIDE cycle, expanded with
the 16:30 UTC cycle learnings, the 17:30 UTC cycle extreme-saturation
data point, the 21:48 UTC cycle pair-into-narrative pattern at 50+
saturation, the 23:35 UTC cycle novel-axis-with-cluster-bridging
pattern, the 2026-06-23 00:15 UTC cycle single-rank NICE_TO_KNOW at
high saturation, and the 2026-06-23 03:15 UTC cycle post-CRITICAL
companion-finding completion cycle. Captures the meta-pattern of
cron-job system-prompt-vs-skill disagreement, the saturated-window
pattern at 14+ prior decisions per 2h, the connectedness-counting
workflow, and the timeout-retry operational note.

(See the older sections below for the historical pattern documentation.)

## Companion-finding completion cycle (NEW — 2026-06-23 03:15 cycle)

At extreme saturation with a recent CRITICAL event, the unranked pool
may consist almost entirely of companion findings to the CRITICAL
cluster. The cycle's picks are then the highest-scoring companion
findings rather than novel axes (which have already been exhausted by
prior cycles covering the same CRITICAL storyline). This is a sub-pattern
of the 50+ saturation case but with stricter structure.

**Symptom:** 2h window has 5+ prior decisions, including 1+ CRITICAL
rank from a recent cycle (1-3h ago) that opened a major storyline.
Pool has 20-40 discoveries, of which 25-30 are either directly covered
by recent CRITICAL decisions OR companion findings to the CRITICAL
cluster. After content-extracted ID dedup, only 2-5 candidates remain,
all of which are companion findings to the CRITICAL cluster.

**Worked example from 2026-06-23 03:15 UTC cycle (post-CRITICAL saturation):**

- CYCLE TIMESTAMP: 2026-06-23 03:15 UTC
- 2H WINDOW: 01:15Z 2026-06-23 to 03:15Z 2026-06-23
- PRIOR DECISIONS IN WINDOW: 5 (826619 Anthropic Fable-5/Mythos-5 US-gov CRITICAL #1 of 3 at 01:00Z, 826622 Anthropic IPO IMPORTANT #2 at 01:00Z, 826623 hyperscaler $88B IMPORTANT #3 at 01:00Z, 826608 hyperscaler $88B re-rank at 00:30Z, 826602 Apple UK NICE_TO_KNOW #1 at 00:15Z)
- POOL: 30 discoveries from `mazemaker_browse(label_prefix='discovery:', limit=30)` (13 from 20260623, 17 from 20260622)
- UNRANKED CANDIDATES AFTER CONTENT-EXTRACTED DEDUP: 3

The 3 unranked candidates (all companion findings to the CRITICAL Anthropic Mythos cluster opened by 826619):

| Rank | Discovery | Companion Cluster | Novelty (1-max_sim) | Connectedness | Recency | Score | Pattern |
|---|---|---|---|---|---|---|---|
| #1 IMPORTANT | 826642 Trump × Anthropic Mythos truce meeting | Anthropic Mythos regulatory (826619) | 0.47 (vs iris-pod 0.532) | 1.0 (10/10 fact+decision) | 1.0 (2026-06-23) | ~2.57 | companion-finding + cluster-bridging (US-gov regulatory × Anthropic capital × Mythos-model roadmap) |
| #2 IMPORTANT | 826643 Anthropic Mythos successor emerges | Anthropic Mythos model-roadmap (826619+826622) | 0.45 (vs iris-pod 0.547) | 0.8 (8/10) | 1.0 | ~2.35 | companion-finding + cluster-bridging (model-roadmap × iteration-pace × US-gov policy) |
| #3 IMPORTANT | 826651 SpaceX Starship V3 wet-dress rehearsal | SpaceX frontier-hardware (826281+826195) | 0.31 (vs OpenAI-GPT-5.4-Cyber 0.686) | 0.7 (7/10) | 1.0 | ~2.11 | companion-finding + cluster-extension (frontier-spaceflight × SpaceX-IPO × Artemis-HLS) |

**The companion-finding completion cycle anatomy:**

(a) **CRITICAL event exhausts the major-axis pool.** The 826619 CRITICAL rank at 01:00Z (Anthropic Fable-5/Mythos-5 US-gov suspension) consumed the major Anthropic Mythos regulatory-axis. Subsequent 826622 + 826623 ranks (Anthropic IPO + hyperscaler $88B) consumed the capital-structure companion axes. The 03:15Z cycle found no unranked discoveries that weren't directly tied to the already-comprehensively-covered Anthropic Mythos + SpaceX clusters.

(b) **All 3 picks are companion findings** to dense clusters (Anthropic Mythos × 2, SpaceX × 1). This is a structural break from prior cycle patterns where at least 1 pick was a sparse-cluster anchor or novel-axis completion. The companion-finding completion cycle has 0 sparse-cluster candidates because the 30-discovery pool has been comprehensively covered by 50+ prior decisions over the last 18h.

(c) **All 3 picks rate IMPORTANT** (not the 1 IMPORTANT + 2 NICE_TO_KNOW pattern documented above). This is because each companion finding completes a multi-cluster narrative: 826642 completes the regulatory-truce axis (826619 → 826642 → 826622), 826643 completes the model-roadmap axis (826619 → 826643), 826651 completes the SpaceX three-axis emergence (826281 + 826195 + 826651). The IMPORTANT classification is justified by the cluster-completion function, not by standalone novel-axis substance.

(d) **Score profile is high across all 3 picks** (2.11-2.57) — typical for companion findings to dense clusters (the high graph_connectedness boost comes from the existing cluster density). Compare to the 17:30 cycle's picks (2.20, 2.07, 2.00) where sparse-cluster anchors had lower connectedness. The companion-finding completion cycle produces uniformly high scores because all candidates benefit from the underlying cluster density.

**Operational rule — new case 5 added to the saturation heuristic:**

5. **NEW (2026-06-23 03:15):** If the 2h window has 5+ prior decisions AND a
   recent (1-3h ago) CRITICAL event opened a major storyline, AND the
   unranked pool is exclusively companion findings to that storyline or
   its dense companion clusters → write 1-3 companion-finding completion
   ranks, ALL at the priority that matches the underlying cluster
   substance (typically IMPORTANT if the companion finding completes
   a regulatory/capital/iteration-pace axis; NICE_TO_KNOW if it
   completes only a niche corpus extension). Do NOT pad with
   sparse-cluster picks just to reach 3; do NOT downgrade companion
   findings to NICE_TO_KNOW just because they're companions — let
   the cluster-completion function drive the priority classification.
   The companion-finding completion cycle's value is in completing
   multi-cluster narratives, not in finding new axes.

**Why this differs from case 1-4:**
- Case 1-2 (moderate saturation): pool has both novel-axis and
  cluster-anchor candidates, prefer 1 IMPORTANT + 2 NICE_TO_KNOW
  for axis-completion + corpus-extension mix.
- Case 3 (extreme saturation, no novel axes): write 1 NICE_TO_KNOW
  "saturation reached" note.
- Case 4 (single-rank saturation): write 1 NICE_TO_KNOW for the 1
  viable corpus-anchor candidate.
- Case 5 (post-CRITICAL companion-finding completion): write 1-3
  companion-finding ranks at the priority that matches the
  cluster-completion function, NOT the typical 1 IMPORTANT + 2
  NICE_TO_KNOW mix. The cycle can produce 3 IMPORTANT ranks without
  padding or downgrading.

**Companion observation — all-IMPORTANT 3-rank output:** the 03:15Z
cycle was the first DECIDE cycle in recent memory to write 3 IMPORTANT
ranks in a single cycle. This is structurally different from the
"1 IMPORTANT + 2 NICE_TO_KNOW" norm. The cycle report to the operator
should explicitly state "3 IMPORTANT ranks, post-CRITICAL companion-
finding completion cycle" so the operator can verify the saturation
heuristic fired correctly. The all-IMPORTANT output is acceptable
when the companion findings all complete load-bearing cluster
narratives; it's NOT acceptable as a default cycle output when the
unranked pool is mixed.

**Timeout retry pattern (operational note):** during the 03:15Z cycle,
the first `mazemaker_remember` call for 826663 (Trump × Anthropic
truce, ~7.5KB content) timed out at 120s. The retry succeeded
immediately. The same content was stored on retry as id 826663.
This is consistent with MCP-server-side rate-limiting or
content-size throttling, not agent-side failure. If a
`mazemaker_remember` call times out at 120s, the immediate retry
with the SAME content typically succeeds — do not modify the content
or split it into multiple smaller writes (the engine will store the
content as a single decision:rank-* memory regardless of write
chunking). The timeout is operational noise, not a content issue.

**Signal:oracle-cluster memo as authoritative coverage map:** the 03:15Z
cycle confirmed that `signal:oracle-cluster-YYYY-MM-DD-X` memos
(observed: signal:oracle-cluster-2026-06-23-B id 826658) are
authoritative coverage maps for which discoveries have been
addressed in the current cycle cluster. The 03:15Z memo explicitly
listed 826642 + 826643 as NOT YET RANKED anchors for the day's
Mythos storyline, which validated the cycle's picks. Future cycles
should briefly check for a `signal:oracle-cluster-YYYY-MM-DD-X`
memo at the start of the cycle — if present, it acts as a pre-filter
for the unranked pool and can save 1-2 mazemaker_recall calls.

## Future cycle patterns to watch for (placeholders)

- **Sub-cluster-emergence cycle:** when a new sub-cluster emerges within
  a dense cluster (e.g., a new "Mythos successor" sub-thread within
  the Anthropic cluster), the cycle's picks may all be sub-cluster
  anchors. Pattern not yet observed at scale; document when seen.
- **Cross-cluster-divergence cycle:** when two dense clusters
  simultaneously have companion-finding completions, the cycle's
  picks may pair across clusters (e.g., 2 Anthropic + 1 SpaceX in
  the 03:15Z cycle). The 03:15Z cycle is a mild example; document
  when a 50/50 cross-cluster split is observed.
- **CRITICAL-walkback cycle:** when a prior CRITICAL rank is walked
  back by a subsequent CRITICAL or IMPORTANT rank (e.g., new evidence
  reverses the CRITICAL trigger), the walkback-cycle output is
  structurally different from typical. Not yet observed.

---

# Original 2026-06-22 reference content (preserved for historical context)

The sections below document the 2026-06-22 cycles that established the
foundation for the saturation heuristic. New sections should be added
ABOVE this divider.

## Cron job config conflict — TRUST THE SKILL, not the system prompt

**Symptom:** The DECIDE cron job's system prompt instructs the agent to call
`mazemaker_recall(query='discovery:pulse-tick-*')` to fetch the 24h
discovery pool. THIS INSTRUCTION IS WRONG. The actual data uses labels
formatted as `discovery:pulse-wurm-YYYYMMDD_*` (e.g.,
`discovery:pulse-wurm-20260622_1747-freshdir-robotics-pokemon-go-ai-military-drones`),
not `discovery:pulse-tick-*`. Recall returns mostly prior `decision:rank-*`
memories (sorted by embedding similarity — the decision graph is dense,
the discovery graph is sparse) and misses the fresh discoveries entirely.

**Broader pattern variants also fail:** the 17:30 UTC cycle confirmed that
even a broader query like `mazemaker_recall(query='discovery:*')` returns
mostly decisions/clusters, not fresh discoveries. The recall embedding
similarity always pulls the dense decision-graph ahead of the sparser
discovery rows, regardless of how broad the query term is. There is no
recall query that reliably returns fresh discoveries. The ONLY working
approach is `mazemaker_browse`.

**Correct tool:** `mazemaker_browse(label_prefix='discovery:')` for the full
pool, or `mazemaker_browse(label_prefix='discovery:pulse-wurm-YYYYMMDD')`
for today-only. (Already documented in PITFALL #N+1 in SKILL.md and in
`references/decide-tool-mechanics.md` — but agents that read the system
prompt first may not load this skill before trying the wrong tool.)

**Operational rule for future DECIDE agents:** When the system prompt and
this skill disagree about which tool to use for the discovery pool, ALWAYS
trust this skill. The system prompt instruction is a vestigial reference
to an earlier version of the loop; the skill has been the source of truth
since the recall-vs-browse distinction was identified.

**What to do if you accidentally tried recall first:** The result will
have a `recall` shape (top-level list of `{id, label, content, similarity, score}`
objects, not the browse `memories` shape). The top-1 result will almost
always be a recent `decision:rank-*` entry. If you see this, immediately
switch to `mazemaker_browse` and re-fetch. Do NOT try to "fix" the recall
by adjusting the query term — switch tools.

## Forward-projected discovery pattern

**Symptom:** A discovery's `created_at` (Unix timestamp in mazemaker) is
AFTER the cycle's `timestamp`. Example from 2026-06-22 16:15 UTC cycle:
discovery 826440 `discovery:pulse-wurm-20260622_18XX-phase-a-b-big-tech-ai-talent-investment-cluster`
had `created_at` = 1782144373 (~16:46 UTC), but the cycle timestamp was
20260622_1615 (16:15 UTC) — i.e., 31 min AFTER the cycle window opened.

**Why this happens:** The Pulse-Wurm 2.0 cron tick runs continuously and
writes new discoveries throughout the day. A DECIDE cycle that runs at
16:15 UTC may capture discoveries created between 16:15 UTC and the moment
the cycle's `mazemaker_browse` call executes (typically 16:18-16:20 UTC).
The chronological browse returns the most recent N regardless of cycle
timestamp.

**Operational rule:** Process these forward-projected discoveries
normally. Do NOT flag the `created_at > cycle_timestamp` mismatch as
"out-of-window" — it is normal. The dedup against the 2h decision window
still works (use the discovery's `created_at` to determine recency weight,
not the cycle timestamp). If a discovery is forward-projected, score its
recency weight as 1.00 based on its own `created_at`, not the cycle
timestamp.

## 40+-decision-per-2h saturation is the new upper bound (2026-06-22 17:30)

**The arc so far:** 14:30 cycle had 9 prior decisions in 2h. 15:46 had 21.
16:15 had 24. 16:30 had 30. 17:30 hit **40+ prior decisions in the 2h
window** (15:30-17:15Z, ~9 cycles × 3-4 decisions each, plus earlier cycles
that fell inside the rolling 2h window). This is the upper bound observed
so far.

**Key data from 17:30 cycle:** Pool of unranked discoveries from
`mazemaker_browse(label_prefix='discovery:', limit=80)`: 49 (after
grep-extracting the IDs from the file-dump). Of those 49, 16 were obvious
"fresh-looking" candidates that turned out to be already covered:
826421 (SpaceX-Cursor $60B), 826357 (Chevron-Microsoft 2.7GW PPA),
826353 (Huawei chip export), 826429 (Anthropic IPO pivot), 826407
(Fable 5/Mythos US-gov suspension), 826395 (Anthropic 50B/900B
TechCrunch NBC), 826409 (Lean 4 Coelho mathematical finance), 826368 +
826360 (Delaware/Hawaii Citizens United bypass), 826430 (Hansen Earth
energy imbalance doubling), 826440 (Big Tech AI talent cluster), 826456
(Earth energy imbalance cluster), 826447 (Dario Amodei Anthropic feud),
826457 (Steam AI disclosure), 826455 (AlphaFold-Nvidia-Eli Lilly), 826436
(Pokémon Go military drones), 826435 (Figure 02 laundry vintage). The
content-extracted `Discovery Memory ID:` regex confirmed each was
referenced in a prior decision's body.

**3 picks still found at 40+ decisions:**
- **#1 IMPORTANT** (score ~2.20): 826355 OpenAI First Proof submissions
  (openai.com/index/first-proof-submissions) — AI math capability
  primary-source, corpus anchor for the sparse AI × formal-verification
  × OpenAI-anchored sub-cluster. Graph 0.70, novelty 0.45, recency 0.85.
- **#2 NICE_TO_KNOW** (score ~2.07): 826396 Apple Swift in kernel
  (blog.calif.io) — Apple platform systems-programming milestone,
  cross-language systems programming advance. Graph 0.50, novelty 0.62,
  recency 0.95.
- **#3 NICE_TO_KNOW** (score ~2.00): 826449 APAC CFO AI playbook
  (dev.to) — 60% APAC finance leaders say AI-led automation is their top
  priority for 2026. First APAC finance × AI × 2026 frontier-deployment
  corpus anchor. Graph 0.30 (sparse), novelty 0.70, recency 1.00.

**Key pattern shift at 40+ decisions:** the IMPORTANT pick is no longer
a "novel axis completion" (the Fable 5 multi-axis, Stargate
infrastructure-axis, Big Tech AI competitive-landscape patterns are
already complete) — it's a **primary-source corpus anchor for a sparse
sub-cluster that had been under-covered**. The NICE_TO_KNOW picks are
niche corpus-extensions rather than novel axes. All three picks had
`graph_connectedness ≤ 0.70` — much lower than the typical 0.80+ for
axis-completion picks in earlier-saturated cycles (e.g., 826440 Big Tech
AI was 0.90, 826380 Stargate Michigan was 1.00, 826419 Anthropic US-gov
escalation was 1.00).

## Refined skip rule for extreme saturation

The "skip the cycle entirely" rule still applies, but the trigger
condition is narrower than "30+ decisions". It's specifically **"30+
decisions AND the unprocessed pool is dominated by companion findings
(no candidate with `graph_connectedness > 0.3` AND `novelty > 0.4`)"**.
At 40+ decisions with 3 picks still available (one with
`connectedness=0.70` and two with `connectedness=0.30-0.50`), the cycle
should NOT skip — it should write the 3 picks even though they're
lower-priority corpus anchors.

**Operational heuristic for extreme saturation (40+ decisions/2h):**

1. If pool has ≥ 5 candidates with `connectedness > 0.5` AND `novelty > 0.4` →
   1 IMPORTANT + 2 NICE_TO_KNOW pattern (similar to 14:00/15:46 cycles).
2. If pool has 1-4 candidates with `connectedness > 0.5` AND `novelty > 0.4` AND
   2-3 candidates with `connectedness > 0.3` AND `novelty > 0.5` → 1 IMPORTANT +
   2 NICE_TO_KNOW pattern (this is the 17:30 cycle pattern at 40+ decisions).
3. If pool has 0 candidates with `connectedness > 0.3` AND `novelty > 0.4` →
   write a single NICE_TO_KNOW "saturation reached, no novel candidates in 2h
   window" note.

The 17:30 cycle is a case-2 example. Future agents at extreme saturation
should expect niche corpus-anchor picks rather than novel axis-completion
picks. Do NOT inflate scores to make picks feel IMPORTANT — write them
as NICE_TO_KNOW corpus anchors with the lower graph_connectedness
honestly reflected in the score breakdown.

## 24-to-30-decision-per-2h saturation is the new normal

**Symptom:** The 2026-06-22 16:15 UTC cycle had **24 prior decisions in
the 14:15-16:00Z window** (1418Z, 1430Z, 1445Z, 1500Z, 1515Z, 1530Z,
1546Z, 1600Z — 8 cycles, 3 decisions each = 24). The pool of unprocessed
discoveries was 31/50 after dedup, but most were companion findings to
already-comprehensively-covered clusters (Fable 5/Glasswing, Stargate,
xAI Memphis, Chevron-Microsoft, Hawaii-Delaware, etc.).

The 2026-06-22 16:30 UTC cycle escalated this to **30 prior decisions in
the 14:30-16:15Z window** (added 1615Z cycle: 826441 big-tech-ai-talent,
826442 pokemon-go, 826443 figure02-laundry). At 30+ decisions, the
unprocessed pool is typically 2-5 genuinely novel candidates — the rest
are either companion findings or directly covered by 2-3 prior decisions
each.

**Operational rule:** This is the new normal. The skill's
"Saturated 2h window pattern" guidance (in `references/decide-tool-mechanics.md`)
already handles this — use content-extracted `Discovery Memory IDs?:` from
prior decisions to build the authoritative covered set, then look for
genuinely novel axes (not just topic slugs). The 2026-06-22 16:15 UTC
cycle's 3 picks (826440, 826436, 826435) and the 16:30 UTC cycle's 3 picks
(826353 Huawei, 826406 r/singularity-641, 826384 ecohealth) were all
genuinely novel axes that didn't share covered topic slugs with the 24-30
prior decisions.

**What to expect:** 1 IMPORTANT + 2 NICE_TO_KNOW is the typical mix
when the 2h window is saturated. The IMPORTANT pick should complete a
new axis (e.g., US-China AI/chip export-control race China-side mirror,
Big Tech AI competitive landscape, regulatory permitting, community
opposition), while the NICE_TO_KNOW picks fill niche corpus-coverage
gaps (e.g., community-deliberation vs engagement-signal, canonical
vintage milestone anchor, climate/bio-health corpus extension). Do NOT
pad with marginal picks just to reach 3 — the skill's instruction is to
write the TOP 3 highest-scoring items, not to write 3 items regardless
of quality.

## Content-extracted `Discovery Memory IDs?:` dedup — worked example

The skill's `references/decide-tool-mechanics.md` documents the
content-based dedup extraction (parse `Discovery Memory IDs?: NNN[, NNN]`
from each prior decision's content body) as more authoritative than
slug matching. The 2026-06-22 16:15 UTC cycle validated this at scale.

**Numbers (16:15 cycle):** 24 prior decisions in 2h window → 21 unique
discovery IDs extracted (some decisions reference 2+ discovery IDs).
Deduped pool: 50 discoveries returned by browse → 19 covered (in the
21-ID set) → 31 unprocessed. The 3 picked decisions (826440, 826436,
826435) all had zero references in any prior decision body — confirmed
novel.

**Numbers (16:30 cycle):** 30 prior decisions in 2h window → ~24 unique
discovery IDs extracted. Deduped pool: 50 discoveries → ~26 covered
(some via 2+ decisions) → ~24 unprocessed. Of those 24, only 3 (Huawei,
r/singularity-641, ecohealth) had top-1 recall similarity < 0.5 to the
nearest non-self memory. The other 21 unprocessed were either companion
findings to covered clusters or had recall similarity ≥ 0.6 indicating
near-duplicate coverage.

**Numbers (17:30 cycle):** 40+ prior decisions in 2h window → 40+ unique
discovery IDs extracted. Deduped pool: 80 discoveries (browse limit=80)
→ ~46 covered → 33 unprocessed (49 minus the 16 obvious covered ones
= 33). Of those 33, only 3 (OpenAI First Proof, Apple Swift kernel,
APAC CFO AI playbook) had `connectedness > 0.3` AND `novelty > 0.4`.
The other 30 unprocessed were either companion findings, niche references
with low connectedness, or had been cross-referenced in 2+ prior decisions
even without being the primary discovery.

**Operational rule:** Trust the content-extracted ID set over slug
matching. The slug fragments collide (multiple decisions can share
"glasswing" or "anthropic-us-gov") but the content-extracted IDs are
unique per discovery. Use slug matching for fast pre-filtering at very
large pool sizes, but always cross-check with content extraction before
writing a decision that risks duplicating a prior one.

## Connectedness-counting script

The `references/decide-tool-mechanics.md` "Companion cross-check:
topic-recall for novelty estimation" section describes the
connectedness-counting pattern in prose. The 2026-06-22 16:30 UTC cycle
(30 prior decisions in 2h, 50 discoveries in pool) validated a runnable
form of this pattern that future saturated cycles can use directly.

**Script:** `scripts/score_connectedness.py` — takes a list of
`/tmp/hermes-results/call_<hash>.txt` file-dumps (one per candidate
topic-recall) and produces per-candidate:
- `fact+decision` count in top-10 (= connectedness numerator)
- `discovery` count in top-10
- `other-typed` count (signal:/bug:/invariant:/ops:/user:)
- `noise` count (anything else)
- max similarity to closest non-self memory
- implied novelty (1 - max similarity)
- top-10 hits with id/label/similarity/kind for manual inspection

**Invocation pattern from `execute_code` (when running a DECIDE cycle):**

```python
import subprocess
result = subprocess.run(
    ["python3",
     "~/.hermes/skills/autonomous-ai-agents/tri-state-decision-process/scripts/score_connectedness.py",
     "/tmp/hermes-results/call_<huawei-hash>.txt",
     "/tmp/hermes-results/call_<r-singularity-hash>.txt",
     "/tmp/hermes-results/call_<ecohealth-hash>.txt"],
    capture_output=True, text=True
)
print(result.stdout)
```

**Output interpretation:**
- `connectedness >= 0.7` + `max_similarity < 0.5` = strong candidate
  (topical anchor with high graph density but novel framing)
- `connectedness >= 0.7` + `max_similarity >= 0.5` = likely already
  covered (read the closest non-self decision to verify it covers THIS
  discovery specifically)
- `connectedness < 0.3` = sparse cluster, novel axis (corpus-extension
  candidate, not redundant)

**Worked example from 2026-06-22 16:30 cycle:**

| Candidate | connectedness | max_sim | implied_novelty | interpretation |
|---|---|---|---|---|
| 826353 Huawei | 0.70 | 0.467 | 0.533 | Strong — China-side mirror of fable5-chinese-group-access |
| 826406 r/singularity-641 | 0.70 | 0.50 | 0.50 | Strong — fable5 community-deliberation axis completion |
| 826384 ecohealth | 0.30 | 0.30 | 0.70 | Weak connectedness, high novelty — climate/bio-health corpus extension |

**Worked example from 2026-06-22 17:30 cycle (40+ decisions):**

| Candidate | connectedness | max_sim | implied_novelty | interpretation |
|---|---|---|---|---|
| 826355 OpenAI First Proof | 0.70 | 0.55 | 0.45 | Strong — corpus anchor for sparse AI × formal-verification × OpenAI sub-cluster |
| 826396 Apple Swift kernel | 0.50 | 0.38 | 0.62 | Moderate — Apple platform systems-programming milestone |
| 826449 APAC CFO AI playbook | 0.30 | 0.30 | 0.70 | Weak connectedness, high novelty — first APAC finance × AI corpus anchor |

**Why this matters:** when the 2h window is saturated with 24-30 prior
decisions, a candidate with `connectedness < 0.3` but high novelty
(like 826384 or 826449) is still rankable as NICE_TO_KNOW for corpus
extension, but should NOT be ranked IMPORTANT even if the topic seems
substantive. The script output makes the connectedness signal visible
at a glance rather than buried in a 100KB file-dump.

**Companion pattern:** for each candidate, ALSO read the top-2
highest-similarity non-self memories via `mazemaker_get(memory_id=NNN)`
to verify the content actually covers the candidate (recall returns
topically-adjacent decisions that may not specifically cover THIS
discovery). This is the "cross-check" step documented in
`references/decide-tool-mechanics.md` "Content-based dedup extraction"
section. The script tells you WHICH decisions to cross-check; the
cross-check confirms whether they actually cover the candidate.

## Two-pass cross-check — the verification pattern for 30+-decision windows

When the 2h window has 30+ prior decisions, a single recall per candidate
is often insufficient to determine coverage. The 2026-06-22 16:30 UTC cycle
validated a two-pass cross-check pattern:

**Pass 1 (topic-recall):** `mazemaker_recall(query=<candidate topic>,
limit=10)`. The top-1 result is the closest non-self memory. If it's a
`decision:rank-*` with similarity >= 0.5, suspect coverage. Note its
memory ID for cross-check.

**Pass 2 (cross-check):** `mazemaker_get(memory_id=<top-1 hit from
pass 1>)`. Read the actual decision content. Look for the candidate's
discovery ID (in `Discovery Memory ID: NNN` or in PAIR/CYCLE CONTEXT
sections). If found, the candidate is covered — skip. If not found
BUT the topic is similar, the recall is returning a topically-adjacent
decision that doesn't specifically cover the candidate — the candidate
may still be novel.

**Worked example from 16:30 cycle:**
- 826258 iOS27-Siri-Extensions → topic-recall top-1 was decision 826262
  (09:45 IMPORTANT) at sim=0.669 → cross-check: 826262 explicitly
  references "Discovery Memory ID: 826258" → COVERED, skip
- 826355 OpenAI-First-Proof → topic-recall top-1 was decision 826373
  (13:45 IMPORTANT) at sim=0.669 → cross-check: 826373 explicitly
  references "Discovery Memory ID: 826355" → COVERED, skip
- 826360 Hawaii-Citizens-United → topic-recall top-1 was decision
  826400 (14:30 NICE_TO_KNOW Tom Moore primary-source) at sim=0.559 →
  cross-check: 826400 references "Discovery Memory ID: 826390"
  (tom-moore-corporate-power-reset, not 826360) BUT the PAIR section
  references 826360 as the "policy-event primary-source" → COVERED via
  umbrella (826374 at 13:45), skip
- 826312 EUROPA → topic-recall top-1 was decision 826323 (11:45
  NICE_TO_KNOW EUROPA) at sim=0.648 → cross-check: 826323 explicitly
  references "Discovery Memory ID: 826312" → COVERED, skip
- 826353 Huawei → topic-recall top-1 was decision 826398 (14:30
  IMPORTANT Mythos macOS crack) at sim=0.394 → cross-check: 826398
  does NOT reference 826353 (different topic: Mythos vs Huawei) →
  UNCOVERED, rank

**Worked example from 17:30 cycle (40+ decisions):**
- 826421 SpaceX-Cursor → content-extracted ID check found it referenced
  in decision 826382 (14:00 IMPORTANT-3 spacex-cursor-60b) → COVERED, skip
- 826357 Chevron-Microsoft → content-extracted ID check found it referenced
  in decision 826453 (17:00 IMPORTANT-2 chevron-microsoft-west-texas) →
  COVERED, skip
- 826353 Huawei → content-extracted ID check found it referenced in
  decisions 826398 (14:30), 826461 (17:00), 826392 (13:30) → COVERED, skip
- 826355 OpenAI-First-Proof → content-extracted ID check across ALL 40+
  prior decisions in 2h window → NO references found → UNCOVERED, rank
- 826396 Apple-Swift-Kernel → content-extracted ID check → NO references
  found → UNCOVERED, rank
- 826449 APAC-CFO-AI-Playbook → content-extracted ID check → NO references
  found → UNCOVERED, rank

**The pattern:** at 30+ decisions, content-extracted ID check across
ALL prior decisions in the 2h window is more reliable than topic-recall
+ cross-check. The reason: topic-recall on a niche topic like APAC finance
AI or Apple Swift kernel may not surface the right prior decision
(sparse topic, no similar coverage), while content-extracted ID check
deterministically confirms whether THIS specific discovery was ranked.
The 17:30 cycle used content-extracted ID check for all 49 candidates
and found the 3 picks deterministically.

**Operational rule:** at 30+ decisions/2h, prefer content-extracted ID
check over topic-recall. At < 30 decisions/2h, either approach works
(topic-recall is faster for small pools, content-extracted ID check is
faster for large pools once you have the 2h decision set built up).

## Pair-into-narrative rule at 50+ saturation (2026-06-22 21:48 cycle)

At 50+ prior decisions/2h, the per-cycle picks are forced into niche
corpus-anchor territory. To make the picks load-bearing instead of
disjoint trivia, the cycle's 3 ranks should **pair into coherent
multi-cluster narratives** with each other and with existing decisions.

**Worked example from 2026-06-22 21:48 UTC cycle (50+ decisions/2h):**

Picks made:
- #1 IMPORTANT (826479 / score ~2.52): DRAM memory wall × HBM AI scaling bottleneck 2026
- #2 IMPORTANT (826487 / score ~2.28): Hyperscaler $88B bond issuance Q2 2026
- #3 NICE_TO_KNOW (826502 / score ~2.37): NVIDIA Cosmos / GR00T humanoid foundation models

Cluster narratives formed by these picks:

(A) **2026-Q2 AI-INFRASTRUCTURE 4-CLUSTER STRUCTURAL STORY** — picks #1+#2 pair with two existing decisions to complete a 4-cluster corpus narrative:
- ENERGY SUPPLY (existing: 826480 TMI/Meta nuclear PPA + 826453 Chevron/Microsoft West Texas 2GW PPA)
- CAPITAL SUPPLY (pick #2: 826487 hyperscaler $88B bond issuance)
- MATERIAL SUPPLY (pick #1: 826479 DRAM memory wall × HBM)
- CYCLE UNWIND (existing: 826484 AI capex unwind thesis 2027-2028)

When the cycle's picks complete an existing 2-cluster story into a 4-cluster story, the picks become load-bearing anchors for the corpus, not just niche scores.

(B) **2026-Q2 HUMANOID DEPLOYMENT 4-ANCHOR CORPUS** — pick #3 pairs with three existing decisions to complete a 4-anchor humanoid narrative:
- FOUNDATION MODELS (pick #3: 826502 NVIDIA Cosmos / GR00T)
- HOME DOMESTIC (existing: 826443 figure-02-laundry-folding)
- CULTURAL NORMALIZATION (existing: 826516 unitree-spring-festival-gala)
- REAL FACTORY DEPLOYMENT (existing: 826503 figure-f03-bmw-spartanburg)

**Operational rule for extreme saturation (50+ decisions/2h):**

1. After scoring all candidates, group them by topic-cluster (energy, capital, material, cycle, humanoid, security, etc.)
2. Identify which existing 2h-window decisions already cover each cluster
3. For each cluster with 2+ existing decisions, look for a candidate that would COMPLETE the cluster to 3+ or 4+ anchors
4. Prefer candidates that pair into a multi-cluster narrative over candidates that stand alone, even if standalone candidates have slightly higher raw scores
5. Pick a 2-3 cluster mix per cycle (don't pick 3 from the same cluster; don't pick 3 from completely disjoint clusters)

**Why this matters:** at 50+ decisions/2h, the corpus has enough density that disjoint niche picks become hard to retrieve later (low recall signal, no cross-cluster reinforcement). Picks that pair into narratives get cross-referenced from existing cluster decisions, building the recall signal organically. This is the long-term corpus-value play over the short-term score-arbitrage play.

**Companion rule:** when picking IMPORTANT + NICE_TO_KNOW mixes at extreme saturation, the IMPORTANT picks should be the cluster-completing ones (high cross-cluster reinforcement) and the NICE_TO_KNOW picks should be the corpus-extension ones (sparse cluster anchors). This gives ACT-phase a clear priority signal: implement the cluster-completing IMPORTANTs first, treat the NICE_TO_KNOWs as corpus-build work.

## Single-rank NICE_TO_KNOW output at high saturation (2026-06-23 00:15 cycle)

**Symptom:** The 2h window has 14+ prior decisions (22:46Z, 23:35Z, 00:00Z cycles all
recently produced 3-rank outputs covering most of the 2026-06-22 discoveries). After
dedup, the unranked pool has exactly **1 candidate** with `connectedness > 0.5` AND
`novelty > 0.4`, and 0 fallback candidates at the `connectedness > 0.3` bar. The existing
case-1/case-2/case-3 rules don't explicitly cover this "1 viable pick only" scenario.

**Worked example from 2026-06-23 00:15 UTC cycle:**

- **CYCLE TIMESTAMP:** 2026-06-23 00:15 UTC
- **2H WINDOW:** 22:15Z 2026-06-22 to 00:15Z 2026-06-23
- **PRIOR DECISIONS IN WINDOW:** 14+ (22:46 Meta keylogger + Pew climate + Kunal Shah;
  23:35 BofA + Zig + Education; 00:00 Uber AI coding budget + 2 others)
- **POOL OF UNRANKED DISCOVERIES:** ~30 (from `mazemaker_browse(label_prefix='discovery:')`)
- **DEDUPED TO VIABLE CANDIDATES:** 1 (826590 Apple UK iCloud £3bn class action)
- **REJECTED CANDIDATES:** 826570 BofA, 826549 Meta keylogger, 826548 Kunal Shah,
  826550 Pew climate, 826574 Education, 826573 Anthropic Mythos, 826546 Zig, 826501
  Apple WWDC, 826489 Uber — all already ranked in 2h window

**The 1 viable candidate (826590 Apple UK iCloud £3bn):**

- Score: ~2.32 (connectedness 0.90 + novelty 0.42 + recency 1.00)
- Priority: NICE_TO_KNOW (legal corpus anchor, not blocking/24h-actionable)
- Connectedness 0.90 = 9/10 fact+decision labels in top-10 topic-recall (legal-AI
  cluster densely linked). Novelty 0.42 reflects that the UK-jurisdiction +
  Apple-anti-competitive angle is novel vs the US-side legal corpus (SB-1047
  chatbot-toys ban 826418, CA state legislation 826417/826418). Recency 1.00
  because the discovery was created in tick 39 (~02:30Z) just minutes before
  this 00:15Z cycle ran — a forward-projected discovery (see "Forward-projected
  discovery pattern" section above).

**Output:** 1 rank written (`decision:rank-20260623-0015-nice_to_know-1-apple-uk-icloud-3bn-class-action-green-light-legal-corpus`),
memory id 826602. CLUSTER CONTEXT documented as "RANK #1 of 1" with explicit note
that all 5 other 2026-06-23 tick-38 + tick-39 discoveries were either already covered
by recent decisions or did not surface as substantive novel findings.

**Why this is not "all-noise" (case 3):** there IS a viable pick with high graph
connectedness. Writing 0 ranks would discard a legitimate corpus-anchor finding.

**Why this is not 3-rank (case 1 or 2):** there are no 2nd or 3rd viable candidates.
Inflating the cycle output by adding 2 marginal picks would violate the "do not pad"
rule documented in the "Refined skip rule for extreme saturation" section above.

**Operational rule — case 4 added to the saturation heuristic:**

4. **If pool has 1 candidate with `connectedness > 0.5`**
   AND `novelty > 0.4` AND 0 fallback candidates at `connectedness > 0.3` AND
   `novelty > 0.5` → write 1-rank NICE_TO_KNOW with explicit "RANK #1 of 1"
   cluster context. Do NOT pad to 3 ranks; do NOT skip the cycle. The single
   pick is load-bearing as a corpus anchor.

**What to expect at this saturation level (14-20 decisions/2h with 1 viable pick):** the
1-rank output is typically a NICE_TO_KNOW corpus anchor for a sparse cluster that
previously had no primary source. The "Cluster Context: RANK #1 of 1" framing + the
explicit list of rejected candidates in the decision body makes it clear to the ACT
phase that this is a single-corpus-anchor cycle, not a partial 3-rank output. The
cycle report to the operator should explicitly state the saturation level ("14+ prior
decisions in 2h window, 1 viable pick remaining") so the operator can verify the
saturation heuristic fired correctly.

**Companion observation — forward-projected discoveries + tight 2h window:** the 00:15Z
cycle caught a forward-projected discovery (826590 created at tick 39 ~02:30Z but
the cycle timestamp was 00:15Z — the discovery was created AFTER the cycle
opened but before the cycle's `mazemaker_browse` call executed). The
forward-projected pattern is documented separately in the "Forward-projected
discovery pattern" section above, but the 00:15Z cycle validated that the
pattern holds even at high saturation — a fresh discovery created minutes
before the cycle can still be the 1 viable pick if it happens to be a high-
graph-connectedness corpus anchor.

## When to skip the cycle entirely (saturated saturation)

The 2026-06-22 16:15 UTC cycle did NOT trigger this rule, but it's worth
documenting: if the 2h window has 30+ prior decisions AND the unprocessed
pool is dominated by companion findings (zero novel axes), the cycle can
write a single NICE_TO_KNOW note saying "saturation reached, no novel
candidates in 2h window" and stop. The skill's `references/decide-tool-mechanics.md`
"Handling large recall outputs" section also covers this. Do NOT write
3 decisions with trivial variants just to fill the quota — that's the
"Läuft loop" anti-pattern. Do NOT skip the cycle silently — even a
1-line saturation note is better than no output (the cron job expects
activity).

**The 17:30 cycle (40+ decisions) did NOT trigger this rule** because
the pool had 3 candidates with `connectedness > 0.3` AND `novelty > 0.4`.
The threshold for "skip entirely" is "0 candidates with `connectedness > 0.3`
AND `novelty > 0.4`" — not just "30+ decisions in 2h". Future agents at
extreme saturation should run the 3-candidate check before skipping.

## Novel-axis-with-cluster-bridging at 50+ saturation (2026-06-22 23:35 cycle)

At 50+ decisions/2h, the pool is mostly niche corpus-anchor candidates
(sparse clusters, low cross-cluster reinforcement). The 23:35 UTC cycle
(52+ decisions in 21:35-23:35Z window) validated that **novel-axis-with-
cluster-bridging candidates are the rare high-value picks** at this
saturation level — they emerge rarely but are the most actionable when
they do.

**Pattern:** a candidate that simultaneously (a) introduces a new axis
not in the existing corpus, AND (b) has high graph connectedness to
multiple existing clusters (rather than to a single sparse cluster).
These candidates are rare because most discoveries are either novel-axes
(with low connectedness, since the cluster hasn't built up) OR
cluster-anchors (with high connectedness but no new axis). The
intersection — both new AND well-connected — is the extreme-saturation
sweet spot.

**Worked example from 2026-06-22 23:35 UTC cycle (52+ decisions/2h):**

| Rank | Discovery | Novelty (1-max_sim) | Connectedness | Recency | Score | Pattern |
|---|---|---|---|---|---|---|
| #1 IMPORTANT | 826570 BofA CEO stablecoin 35% deposit drain | 0.572 (vs yc-w26 sim 0.428) | 0.90 (9/10 fact+decision) | 1.00 (2026-06-23) | ~2.62 | novel-axis + cluster-bridging (financial-system × banking × US-deposit × stablecoin regulation) |
| #2 NICE_TO_KNOW | 826546 Zig Software Foundation 2026 | 0.499 (vs ai-capex-unwind sim 0.501) | 1.00 (10/10 fact+decision) | 0.95 | ~2.45 | cluster-anchor (programming × AI-policy, dense graph via recent decisions) |
| #3 NICE_TO_KNOW | 826574 Education × AI frontier 2026 | 0.550 (vs tom-moore sim 0.450) | 0.90 (9/10 fact+decision) | 1.00 | ~2.45 | novel-axis (first-ever education-domain fresh-direction success) |

**The BofA finding's novel-axis-with-cluster-bridging anatomy:**

(a) **Novel axis:** BofA CEO Brian Moynihan publicly stating a 35% US
bank-deposit drain number from stablecoin competitive threat. The
specific 35% number from a US bank CEO is not in the corpus — closest
entries are general banking-vs-stablecoin concerns without quantified
drain projections.

(b) **Cluster-bridging:** The finding's top-10 recall has 9/10 fact+decision
labels spanning multiple existing clusters — 826468 YC AI startups
(startups), 826417 SB-1047 (legal/regulation), 826564 Kunal Shah
(corporate-leadership), 826400 Tom Moore (corporate-power), 826530
iris-pod (operator-stack), 826280 US-DC opposition (infrastructure),
826488 meta-nuclear-energy-wall (energy), 826526 pitfall-46-glasswing
(operational). The candidate bridges the financial-system, banking,
US-deposit, and stablecoin-regulation clusters simultaneously.

(c) **Why it ranks IMPORTANT despite 52+ saturation:** The IMPORTANT
boost (+0.15) doesn't dominate the score; the candidate's base score
(0.90 + 0.572 + 1.00 = 2.47) is already the highest of the cycle. The
priority classification reflects the substance (financial-system
structural inflection with regulatory policy-relevance — Fed/Treasury/
FDIC + stablecoin-framework legislative debate). When the base score
is already this high, the priority classification just needs to match
the substance.

**Operational rule for 50-55+ saturation:**

1. Build the candidate pool (typically 5-15 candidates after dedup
   against 4h of prior decisions — at 50+ decisions/2h the relevant
   dedup window expands to 4h because adjacent cycles overlap so much
   that the 2h window misses prior coverage).
2. Score all candidates with `connectedness + novelty + recency`.
3. Look for the "novel-axis-with-cluster-bridging" pattern:
   - Novelty > 0.5 (genuinely not in corpus)
   - Connectedness > 0.8 (high graph density across MULTIPLE clusters,
     not just one)
   - Recency > 0.9 (very fresh)
   - These three together are the "high-value pick" signal.
4. If 1+ candidate has this pattern, rank it as IMPORTANT (or
   CRITICAL if security/privacy/labor angle) regardless of how
   many other corpus-extension picks exist.
5. Fill remaining 2 ranks with the highest-scoring cluster-anchor or
   novel-axis candidates (typical NICE_TO_KNOW).
6. If 0 candidates have this pattern, fall back to the
   "pair-into-narrative rule at 50+ saturation" from the previous
   section — pick 2-3 cluster-completing or cluster-extending picks
   that pair into 2-3 cluster narratives.

**What to expect at 50-55+ saturation:** typically 1 novel-axis-with-
cluster-bridging pick + 2 cluster-anchor or fresh-direction picks.
The cluster-anchor/fresh-direction picks should still have
`connectedness > 0.7` so they pass the cluster-completion filter; if
not, the pool is too saturated and the cycle should consider the
"all-noise cycle disposition" (skip the write, append log, output
[SILENT] or short report).

**Companion rule:** the "pair-into-narrative rule at 50+ saturation"
(previous section) and this "novel-axis-with-cluster-bridging" rule
are not contradictory. Pair-into-narrative is the fallback when
novel-axis-with-cluster-bridging is unavailable. The 23:35 cycle
successfully used pair-into-narrative AS A SECONDARY heuristic even
though the #1 pick was novel-axis-with-cluster-bridging — the
#2 + #3 picks (Zig + Education) were orthogonal corpus-extensions
without strong narrative pairing, but their scores (2.45 each) and
orthogonal-domain fit made them valid NICE_TO_KNOW anchors without
requiring narrative pairing.