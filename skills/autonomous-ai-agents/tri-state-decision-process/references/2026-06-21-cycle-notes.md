# DECIDE Phase Cycle Notes

Session-specific notes from the 2026-06-21 DECIDE cycles (01:00 UTC + 03:30 UTC).

## Hybrid Recall Pattern (works well for fresh-tick discoveries)

When the DISCOVER phase has just produced a fresh tick (e.g. 2026-06-21 00:48 UTC) and you need to find the new `discovery:pulse-wurm-YYYYMMDD_*` items:

1. **Run BOTH tools in parallel:**
   - `mazemaker_browse(label_prefix="discovery:pulse-wurm-YYYYMMDD", limit=30)` — chronological by label, fast, comprehensive for the day
   - `mazemaker_recall(query="discovery:pulse-wurm-YYYYMMDD_*", limit=50)` — semantic, but returns 150-200K chars saved to `/tmp/hermes-results/call_*.txt`

2. **Process large recall outputs with execute_code**, not re-calling with tighter limits. The `json_parse` helper inside the persisted file makes structured extraction cheap.

3. **Cross-reference browse vs recall results** — browse misses semantically-related items; recall misses recent items beyond the 50-cap. The union covers both.

## Duplicate-Avoidance Check (last 2h)

Before writing a new `decision:rank-*` for a discovery, check whether a decision with the same discovery memory_id was written in the last 2h. Quick check:

```python
# Via recall — sort by 'newest' to surface recent decisions
mazemaker_recall(query="decision:rank-YYYYMMDD", limit=10, sort="newest")
```

Or inspect the `created_at` of the decision:rank memories surfaced by the browse. The CronMemoryCycle pattern: prior cycle's decisions (00:00 UTC) should not be re-ranked at 01:00 UTC; same item is a NOISE/dup.

## Score Formula (recap from successful cycle)

```
connectedness = count(fact:*|decision:* in top-10) / 10
novelty = 1 - max_similarity_to_closest_existing
recency_weight = linear_decay_from_1.0_over_24h
base = connectedness + novelty + recency_weight
priority_boost = 0.20 (CRITICAL) | 0.10 (IMPORTANT) | 0.00 (NICE_TO_KNOW)
total = base + priority_boost
```

In the 2026-06-21 01:00 UTC cycle, scores ranged 1.47-2.05. The CRITICAL pick (NK npm supply chain attack on AI dev tooling, score 2.05) won on (1) extreme recency (~7 min old), (2) state-actor threat signal, (3) dense cluster (5/10 in cluster).

## Priority Mix Strategy

A balanced 3-decision output should hit at least 2 of {CRITICAL, IMPORTANT, NICE_TO_KNOW}. The 2026-06-21 01:00 UTC cycle produced CRITICAL + IMPORTANT + NICE_TO_KNOW — covers both immediate action and watchlist items.

## Skipping Saturation

If the discovery pool is 60-80% already-decided (per prior cycle's discovery-cycle-saturation-snapshot pattern), it's acceptable to write fewer than 3 decisions or to include 1-2 NICE_TO_KNOW items. Do NOT re-rank items just to hit 3 — that's noise.

## Pattern 22 Learning (Pulse-Wurm specific)

When the tickertick sub-channel or the openalex sub-channel returns the typical "Ti metallurgy / Tied links math" noise pattern, the issue is the seed has too-specific named-actor proper nouns. Try reformulating: "agent failure recovery self-correction error reflection 2026" (no named-actor) instead of "Mastra AI npm supply chain attack Sapphire Sleet BlueNoroff North Korea attribution 2026" (multiple named-actors). The openalex sub-channel IS productive on person_research intent when the seed lacks named-actor proper nouns.

## 03:30 UTC Cycle — Recall-Glob Pitfall Caught (CRITICAL LEARNING)

The cron instruction for this loop says `mazemaker_recall with query 'discovery:pulse-tick-*'` but actual discovery labels are `discovery:pulse-wurm-*` (NOT `pulse-tick-*`). The recall glob either (a) doesn't support globs and treats the query as a literal substring, or (b) returns 0 matches because no label contains the literal substring "pulse-tick-". Result: TWO fresh discoveries (825402 codingbench-misaligned-position + 825403 gascity-multi-agent-sdk, both created 03:35Z, ~5 min old) were initially MISSED by the recall call.

**Pitfall (PATCH THIS):** Never trust the cron instruction's literal recall query — always run the hybrid recall (browse + recall) and verify coverage before scoring. If the cron says `discovery:pulse-tick-*` and labels are `discovery:pulse-wurm-*`, the recall call returns 50 mostly-decision items, hiding the fresh discoveries in the long tail.

**Workaround (worked in this cycle):**
1. Run `mazemaker_recall(query="discovery:pulse-tick-*", limit=50)` as instructed by the cron
2. ALSO run `mazemaker_browse(label_prefix="discovery:", limit=100)` to find all discovery-labeled memories chronologically
3. The browse catches fresh tick outputs (last few minutes) that the recall misses
4. Filter the union of both against the 2h dedup window

**Recommendation for future cron iterations:** Either (a) update `~/.hermes/loops/tri-state/decide_rank.py` to use `discovery:pulse-wurm-*` or `discovery:pulse-*` as the recall query, OR (b) add a `mazemaker_browse(label_prefix="discovery:pulse-wurm-")` step to the cron instructions. Both are cheap and prevent the silent miss.

## All-NICE_TO_KNOW Cycles Are Valid

This cycle produced 3 NICE_TO_KNOW items (no CRITICAL or IMPORTANT). This was the right call because:
- Pool was 60%+ saturated with cluster extensions and duplicates
- The freshest discoveries (825402, 825403) were both academic/candidate-project in nature — no immediate Hermes feature gap
- The strongest candidates already-ranked (825242 programbench, 825243 XDA consumerization, 825244 phpmypython) were all ranked as IMPORTANT 3-9h ago with no new context warranting re-ranking
- Manufacturing an IMPORTANT rating to "hit priority diversity" would be the noise the skipping-saturation rule warns against

The 3 NICE_TO_KNOW angles were deliberately diverse (evaluation-methodology / model-vendor-context / agent-orchestration-tool) so the ACT phase gets three distinct action types even at the same priority level. The CYCLE CONTEXT section in each ranking cross-references the other 2 ranks in the cycle so the cluster signal is preserved even when individual priorities are uniform.

## Ranking-Map Construction (efficient dedup)

When the discovery pool is 25-30 items, building a ranking-map is faster than per-discovery recall queries:

```python
# Build decision:rank-* memories browse (limit 50)
# Extract: discovery_id -> (latest_decision_label, latest_decision_created_at)
# For each discovery in pool:
#   if discovery_id not in ranking_map → eligible (never ranked)
#   elif ranking_map[discovery_id][1] < now - 2h → eligible (ranked >2h ago)
#   else → skip (ranked within last 2h, dedup window)
```

This was the bottleneck-buster in this cycle — replaced 26 per-discovery recall calls with one browse + one Python pass. Saved ~5min of tool-budget.

## Cycle-Context Cross-Reference Pattern

Each ranking includes a CYCLE CONTEXT section that:
- Names the cycle position (e.g., "1st of 3 ranks from 2026-06-21 03:30 UTC DECIDE cycle")
- Lists the other 2 ranks by memory_id + topic + priority
- Notes the three-aspect diversity (e.g., "evaluation-methodology critique + model-vendor supply-side context + agent-orchestration tool discovery")
- Optionally flags meta-observations (e.g., recall-glob pitfall, dedup-window edge cases)

This lets the ACT phase read the three rankings and see the cluster signal even when individual priorities are uniform (all-NICE_TO_KNOW cycles).