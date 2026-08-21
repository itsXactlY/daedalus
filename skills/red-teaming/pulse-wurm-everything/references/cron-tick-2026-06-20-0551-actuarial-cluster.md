# Pulse-Wurm 2.0 Tick 2026-06-20 ~05:51 UTC — Actuarial Cluster Discovery

Session-specific addendum for the cron tick that surfaced the **insurance/actuarial-for-autonomous-AI-agents** cluster. Read this alongside `cron-tick-playbook.md` and `cron-tick-2026-06-20-patterns.md`.

## What Yielded

**3 mazemaker saves** (ids 824667 / 824668 / 824669) — all in the same emerging cluster:

| ID | arXiv | Title | Angle |
|---|---|---|---|
| 824667 | 2605.25632 | Insuring Every Action: An Authority Frontier Framework for Runtime Actuarial Control of Autonomous AI Agents | Permission-boundary / authority-frontier primitive |
| 824668 | 2605.26508 | Foundations of a Time-Consistent Counterfactual Actuarial Runtime for Autonomous AI Agents | Temporal consistency for multi-step premium |
| 824669 | 2606.16326 | Gaming-Resistant Insurance Contracts for Autonomous AI Agents: Strategy-Proof Toll Mechanism Design | Strategy-proofness / game-theoretic toll mechanism |

**Cluster anchor (already saved prior tick)**: 2606.16465 Trace-Economic Underwriting (referenced in `cron-tick-2026-06-20-patterns.md` Pattern 3). Plus the older 2606.03777 Control Boundary to Insurance Claim via CER Framework (mazemaker id 822436 from 2026-06-19 ~07:15 tick).

**Cluster as of this tick**: **4 papers in ~30 days**. Per the cluster-growth heuristic in the playbook, still in "save-worthy" range because each paper has a methodologically distinct angle (authority frontier / time-consistency / strategy-proofness / trace-economics).

## Pattern: arxiv-ID-Anchored Reformulation (Tier 3)

The conventional concrete-reformulation pattern (playbook + `cron-tick-2026-06-20-patterns.md` Pattern 2) covers tier-1 academic phrasing → tier-2 concrete phrasing. This tick escalated to **tier-3 arxiv-ID-anchored** reformulation and it worked where tier 2 had failed.

**Sequence**:
1. Initial pulse_search deep on the 3 script seeds with their original phrasings: 0 novel.
2. Re-searched the **DoS seed** with tier-2 reformulation ("LLM agent reasoning budget exhaustion test-time-compute denial wallet attack 2026"): 13 candidates, ALL noise (Reddit relationship drama, tickertick consumer electronics, ft.com Big Tech stoking unrest).
3. Examined the *first* DoS search output and found one low-score (0.013) but on-topic candidate: arxiv 2605.25632 "Insuring Every Action: An Authority Frontier Framework for Runtime Actuarial Control of Autonomous AI Agents".
4. **Tier-3**: Re-ran pulse_search deep with `topic="arxiv 2605.25632 Insuring Every Action Authority Frontier Runtime Actuarial"`. Result: 4 candidates, all 4 in the actuarial cluster (2605.25632 anchor + 2605.26508 + 2606.16326 + 2606.16465).

**Why tier-3 works when tier-2 fails**:
- Query planner classifies `intent: person_research` (treating the arxiv ID as a person/entity identifier, not a topic)
- This triggers the openalex sub-source to be included in the fan-out
- The literal arxiv ID is a high-confidence token — openalex ranking rewards exact-ID matches with top scores
- The ID anchors the result to the *cluster around that paper*, not just the paper itself

**Trigger to escalate to tier-3**:
- Tier-2 returned 1+ on-topic paper with low score (0.01-0.03)
- Conventional phrasing misroutes to noise clusters (NBA/weddings/Ti metallurgy)
- 2-3 prior tier-1/tier-2 attempts on the same seed already returned 0 on-topic

**Don't use tier-3 first-line**: It requires a confirmed paper as the cluster anchor. Use it after tier-1/2 surface one promising URL.

## Pattern: Pre-Save Duplicate Check via discovery_topics

When a candidate surfaces that *might* be already-saved, the `visited_urls` cross-check alone is insufficient. Papers can be saved as `/abs/<id>` while the search returns `/pdf/<id>` (or vice versa), and `parse_pulse_search.py` normalization catches this for `visited_urls` but not for the `discovery_topics` audit log.

**Real case**: arxiv 2606.16465 surfaced in the tier-3 search (URL form `/pdf/2606.16465`). `parse_pulse_search.py` normalization would have flagged it as visited (the URL `https://arxiv.org/abs/2606.16465` was in `visited_urls`). But BEFORE running the helper, I cross-referenced `discovery_topics` for "2606.16465" and found the entry from the 2026-06-20 ~03:45 UTC tick: "Trace-Economic Underwriting 2606.16465 (insurance/economics novel domain)". Confirmed already saved.

**Recommended pre-save cross-check pattern** (add this to mazemaker_remember workflow):

```python
arxiv_id = "2606.16465"
already_saved = any(arxiv_id in str(t) for t in state["discovery_topics"])
# OR check the visited_urls with both URL forms:
already_visited = (
    f"https://arxiv.org/abs/{arxiv_id}" in visited_urls or
    f"https://arxiv.org/pdf/{arxiv_id}" in visited_urls
)
if already_saved or already_visited:
    # Mark visited only, do NOT save to mazemaker
    pass
```

**Why this matters**: The tier-3 reformulation specifically returns papers in the cluster of the anchor — most are likely already-saved. Without the cross-check, you'd save 1 anchor + 3 duplicates = 4 mazemaker slots wasted on the same cluster. With it: 1 anchor + 0 saves (already done) + N genuinely novel angles.

## Pattern: Cluster-Saturation Diagnostic via discovery_topics

The `discovery_topics` audit log is the ground truth for cluster state, more reliable than `saturation_scores` (which can drift under concurrent ticks — see playbook "Concurrent Cron Execution").

**Cluster-saturation diagnostic procedure**:
1. For a topic that surfaced from a seed, grep `discovery_topics` for the topic name or arxiv ID prefix.
2. Count the unique arxiv IDs / DOIs in the matching entries.
3. Map each ID to its date-stamped tick.
4. The cluster's growth rate (papers per 30 days) determines if new entries are novel or cluster-bloat.

**Applied to the actuarial cluster (this tick)**:
- 2606.16465 saved 2026-06-20 ~03:45 UTC
- 2606.03777 saved 2026-06-19 ~07:15 UTC
- 2605.25632, 2605.26508, 2606.16326 saved 2026-06-20 ~05:51 UTC (this tick)
- **Growth rate**: 5 papers in ~36 hours. By cluster-growth heuristics (4 papers in <30 days = still save-worthy), this is right at the threshold but each paper has a distinct methodology.

## State Changes This Tick

```json
{
  "visited_urls": "2478 -> 2542 (+64)",
  "consecutive_empty": "1 -> 0 (3 saves)",
  "next_seeds": [
    "LLM agent insurance actuarial runtime underwriting 2026",
    "agent OS architecture microkernel substrate LLM inference 2026",
    "LLM agent reasoning budget exhaustion test-time-compute DoS 2026",
    "A Query Engine for the Agents (arxiv 2605.27785, saved id 824408)"
  ],
  "saturation_scores_updated": {
    "LLM agent DoS rate-limit cost amplification guardrail bypass 2026": "+1 (surfaced 2605.25632 anchor)",
    "agent skill supply chain SBOM provenance verification ClawHub follow-on 2026": "+1",
    "A Query Engine for the Agents (arxiv 2605.27785, saved id 824408)": "+1"
  }
}
```

## Next-Tick Recommendations

1. **Lead with the actuarial seed** (`LLM agent insurance actuarial runtime underwriting 2026`) — it now has 4 papers in cluster, may surface 1-2 more from the same DOI prefix or author network.
2. **Use tier-3 reformulation first** if the actuarial seed returns 0 — anchor on `arxiv 2606.16326 Gaming-Resistant Insurance Contracts`.
3. **Watch for cluster-saturation** — if the actuarial cluster reaches 6+ papers in 30 days, mark it mature and don't save follow-on incremental papers.
4. **The "A Query Engine for the Agents (arxiv 2605.27785)" seed** has been retried 3+ times across recent ticks with 0 yield. **Recommend retiring** the seed by bumping its saturation to 8+ so the saturation-sort skips it. Pattern 5 in `cron-tick-2026-06-20-patterns.md` already documented that arxiv-ID seeds misroute to noise — this is additional confirmation.

## Tick Report (delivered to cron destination)

```
## Pulse-Wurm 2.0 Tick Report — 2026-06-20 05:51 UTC

**3 novel discoveries saved** (mazemaker ids 824667–824669). State updated.

### Script tick
The 3 script seeds via GitHub channel returned 0. pulse_tick.py reported consecutive_empty: 1.

### MCP channel — tier-3 reformulation yielded
Conventional phrasing of the 3 script seeds saturated via tier-2. Re-querying the DoS seed
with arxiv-ID-anchored topic ("arxiv 2605.25632 Insuring Every Action") opened the actuarial
cluster and surfaced 4 papers (3 genuinely novel, 1 already saved). Saved:
- 824667: arxiv 2605.25632 Insuring Every Action (authority frontier)
- 824668: arxiv 2605.26508 Time-Consistent Counterfactual Actuarial Runtime
- 824669: arxiv 2606.16326 Gaming-Resistant Insurance Contracts (strategy-proof)

### State updates
- visited_urls: 2478 -> 2542 (+64)
- consecutive_empty: 1 -> 0
- next_seeds: rotated actuarial cluster to #1 priority
- Saturation bumped on 3 processed seeds

### Patterns confirmed
- arxiv-ID-anchored reformulation (tier 3) outperforms abstract phrasing for cluster extension
- Pre-save cross-check via discovery_topics caught 2606.16465 duplicate before mazemaker save
- Openalex sub-channel remains the productive channel; reddit/tickertick/github noise
```
