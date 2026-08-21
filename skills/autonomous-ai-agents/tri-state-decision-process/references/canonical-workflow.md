# Canonical DECIDE-Phase Workflow (4 steps)

The cron instruction emits a single `mazemaker_recall(query='discovery:pulse-tick-*')` call which is INSUFFICIENT on its own (see [recall-glob-pitfall.md](recall-glob-pitfall.md)). The canonical workflow below is what has produced correct coverage across multiple cycles (2026-06-21 01:00Z, 03:30Z, 04:02Z, 19:00Z). **Do NOT skip steps or run them out of order.**

## Step 1 — Hybrid recall (browse + recall, in parallel)

Run BOTH tools in parallel:
- `mazemaker_browse(label_prefix="discovery:", limit=100)` — chronological, catches fresh tick outputs (last few minutes to hours)
- `mazemaker_recall(query="discovery:pulse-tick-*", limit=50)` — semantic, returns 50 mostly-decision:* items from the long tail (matches the cron instruction verbatim)

Then union the discovery:* entries by id. The browse set is the source of truth for fresh tick outputs; the recall set catches semantically-related items the browse may miss.

This pattern was confirmed across 3+ cycles (2026-06-21 01:00Z, 03:30Z, 04:02Z). Skipping the browse step consistently misses fresh pulse-wurm tick outputs from the last few hours.

**Browse limit choice (added 2026-06-21 19:00 UTC cycle):** use `limit=100` when the pool is under-saturated; use `limit=50` when the pool is saturation-dense (i.e. when the 2h dedup window count is approaching the 10+ saturation threshold per `2026-06-21-cycle-notes-1430.md`). The 19:00 cycle confirmed that 50 is sufficient when 9+ recent decisions are already in the 2h window — the remaining candidates are corpus-coverage milestones that don't require exhaustive enumeration.

## Step 2 — Dedup against last 2h via ranking-map

Build a ranking-map in one browse, not N per-discovery recall queries:
- `mazemaker_browse(label_prefix="decision:rank-", limit=50)` — get latest 50 ranking decisions
- Extract `discovery_id → (decision_label, decision_created_at)` from each decision's content (regex on `Discovery Memory ID:\s*(\d+)`)
- Save to `/tmp/dedup_map.json` for the next step

For each discovery in the union pool, skip if `discovery_id ∈ dedup_decided_recent` (i.e. decision_created_at ≥ now - 2h). This single-pass approach replaces ~26 per-discovery recall calls with one browse + one Python pass (saves ~5min of tool budget).

### Dedup extension — side-findings get implicit coverage from parent decision ranking (added 2026-06-21 19:00 UTC cycle)

When a parent discovery is ranked, its explicitly-listed sub-findings (in the decision's "PAIR with" or "cross-reference" section) are implicitly covered — do NOT separately rank them in subsequent cycles. This extends the 2h window: a sub-finding is considered "already decided" if its parent decision was written, regardless of when the sub-finding itself was created.

**Diagnostic shortcut:** when you see `discovery_id=N` listed in a parent decision's "PAIR with" / "cross-reference" section, treat it as already-decided for the rest of the day. The parent's ranking carries the sub-findings' coverage. Verified pattern from 2026-06-21 19:00 UTC cycle: 825700 (Milrem THeMIS Ukraine), 825687 (Merz Polymarket 100%), 825677 (Poland "shoot first" policy) were all sub-findings of 825694 (NATO eastern flank, ranked 17:16 UTC); all were correctly skipped at 19:00 UTC despite being fresh discoveries. See `references/2026-06-21-cycle-notes-1900.md` for full case study.

### Dedup extension — axis-complement ranking for partially-covered domains (added 2026-06-21 20:46 UTC cycle)

Counterpoint to the sub-finding implicit coverage rule: when a discovery is in a domain already partially covered by a prior decision, but introduces a NEW DIMENSION/AXIS, rank it as the axis-complement with explicit axis-complementarity documentation. Do NOT skip it as a sub-finding because the new axis represents orthogonal coverage, not redundancy.

**Distinguishing axis-complement from sub-finding:**
- **Sub-finding**: same topic, same axis (e.g., Milrem THeMIS Ukraine re-discovered under same NATO eastern flank axis) → SKIP per dedup extension rule.
- **Axis-complement**: same domain, different axis (e.g., operational axis vs scientific axis in space domain) → RANK as complement with explicit documentation.

**Diagnostic shortcut:** ask "does this discovery open a new dimension the prior decision didn't cover?" If yes → axis-complement (rank it). If no → sub-finding (skip per dedup rule).

Verified pattern from 2026-06-21 20:46 UTC cycle:
- **825744 (LEO orbital debris + Starcloud)** in space domain: prior coverage 825572 (deep-space-ai-anomaly-detection) covered the SCIENTIFIC axis. 825744 covers the OPERATIONAL + COMMERCIAL axis → RANKED as axis-complement, paired with 825572 in the decision's "PAIR with" section.
- **825743 (history-archaeology academic)** in history domain: prior coverage 825626 (history-archaeology-freshdir-cluster) covered the DISCOVERY axis. 825743 covers the ACADEMIC axis → RANKED as axis-complement, paired with 825626.

See `references/2026-06-21-cycle-notes-2046.md` for full case study.

## Step 3 — Score with the canonical formula

For each eligible (non-noise, non-dedup-skipped) discovery, compute:

```
connectedness = count(fact:*/decision:* in top-10 topic-recall) / 10
novelty        = 1 - max_similarity_to_closest_existing_memory (excluding self)
recency_weight = max(0, 1 - age_hours / 24)  # linear decay over 24h
base           = connectedness + novelty + recency_weight
priority_boost = 0.20 (CRITICAL) | 0.10 (IMPORTANT) | 0.00 (NICE_TO_KNOW)
TOTAL          = base + priority_boost
```

For topic-recall, use a query that captures the discovery's CORE TOPIC, not the discovery's full content. Use top-1 similarity from the recall results as the max-similarity proxy (or top-2 if top-1 is the discovery itself).

### Recency-weight clock-skew caveat (added 2026-06-22 00:30 UTC cycle)

**Discovery content "system UTC" timestamps are forward-dated by 5+ hours vs the actual `created_at` Unix epoch.** The pulse-wurm tick writer appears to log discoveries with a "next-run" or scheduled time in the body, not the actual wall-clock time. The discovery LABEL timestamps (e.g. `discovery:pulse-wurm-20260622_0130_freshdir-fable5-export-control` → 20260622_0130) and the `created_at` Unix epoch are synchronized and accurate. The body content's "system UTC" claim is unreliable.

When computing recency_weight, use ONE of:
1. The LABEL timestamp extracted via `(\d{8})_(\d{4})` regex (matches format #1 from `2026-06-21-cycle-notes-2145.md`)
2. The `created_at` Unix epoch from `mazemaker_get` for the discovery

**Do NOT use the body content's "system UTC" date strings** for recency_weight. The 2026-06-22 00:30 cycle caught this skew: discovery 825817 (label says 20260622_0021, body says "~00:21Z", actual created_at 1782087702 = 2026-06-22 05:41:42Z) — the body time was forward-dated by 5h20min. See `references/2026-06-22-cycle-notes-0030.md` for the full reproduction.

This skew means the recency_weight formula is correct when using label timestamps, but UNDERESTIMATES freshness by ~5 hours if the body content timestamp is naively trusted. For 00:30 cron, a "01:35Z" content time looks "1h05m old" (recent) when it's actually 5+ hours in the future of the cron — the discovery is genuinely from a later cycle, not a recent one.

### Connectedness quality — generic-fallback discount (added 2026-06-21 19:00 UTC cycle)

For niche topics with no specific graph nodes, `mazemaker_recall(topic, limit=10)` returns the broader corpus's decisions as fallback. Connectedness count may be high (e.g. 9/10 = 0.9 for AI SRE tools), but topical relevance of the matches is LOW — the matches are decisions about gaming, Anthropic, NATO, etc., not about the discovery's specific topic.

**Quality check:** when computing connectedness, qualitatively verify whether the top-10 recall matches are TOPICALLY related to the discovery. If 7+/10 are generic-fallback (not topic-related), discount connectedness by ~50%. Better workaround: query recall with a more specific query (longer phrase, more domain anchors) to bias the recall toward topic-specific results. If even a specific query returns generic-fallback matches, that's a signal of low graph presence and the effective connectedness should be capped at ~0.5. Verified limitation from 2026-06-21 19:00 UTC cycle: 825636 (AI SRE tools) had 9/10 generic-fallback matches, effective connectedness ~0.45 not 0.9.

Priority classification guidance:
- **CRITICAL** — security/data-loss/blocking; immediate action. Examples: active supply-chain attack with state-actor attribution, blocking infrastructure bug.
- **IMPORTANT** — feature gap / optimization; act within 24h. Examples: new attack primitive against Hermes-relevant surface, evaluation capability ceiling.
- **NICE_TO_KNOW** — research-stage / informational; store for reference. Examples: industry analysis, methodology papers, candidate projects.

## Step 4 — Persist top 3 with cluster cross-reference

Write the top 3 scoring discoveries via `mazemaker_remember` with label `decision:rank-<YYYYMMDD>-<priority>-<slug>` and content that includes:
1. Discovery Memory ID and one-line summary
2. Why it matters (priority bucket justification)
3. Full score breakdown (connectedness / novelty / recency / boost / total)
4. Suggested action type (skill_update / code_fix / config_change / research_watchlist / fact_memory)
5. Cluster cross-reference — name the other 2 decisions in this cycle by memory_id + topic + priority
6. Cycle context (which cycle, which pair-ranks, three-aspect diversity)

Priority mix strategy: aim for at least 2 of {CRITICAL, IMPORTANT, NICE_TO_KNOW} in a 3-decision output. If the pool is 60-80% already-decided (saturation), fewer than 3 is acceptable and all-NICE_TO_KNOW is valid (don't manufacture IMPORTANT to hit diversity).

### Step 4b — Process-milestone handling for deep-research jobs (added 2026-06-21 20:46 UTC cycle)

When a discovery represents a process milestone (deep-research job kicked off, content pending) rather than a content finding, apply a special-case pattern:

1. **Rank the process milestone NOW** as a NICE_TO_KNOW decision. Document the deep-job parameters: depth, wurm rounds, sources, fetches/round, growth metrics (e.g., "search phase 53 candidates, dig-1 60 new (113% growth), dig-2 26 new").
2. **DEFER fact_memory creation** to the next DECIDE cycle when content materializes from `pulse_research_result` / `pulse_research_status` / `pulse_research_start`.
3. **Add research_watchlist entries + pulse-wurm seeds NOW** so the topic gets continued coverage while the deep job runs.
4. **Decision "Action" section must explicitly say** "DEFERRED fact_memory creation — wait for next-tick poll of pulse_research_result".
5. **Pair with downstream signals** (IPO pipeline, related decisions) so the decision has cluster cross-references even without content materialization.

**Diagnostic shortcut:** when a discovery's content begins with "PHASE B FRESH-DIRECTION" or contains "Started pulse_research" or "pulse_research_start" or "job running in background", it is a process milestone — apply the defer-fact-memory pattern.

**Why this pattern matters:** without it, the agent would either (a) skip the discovery (missing the process milestone + corpus-coverage initiation) or (b) write a fact_memory based on the in-progress intermediate results (which would lock in stale rankings before the final LLM filter applies).

Verified pattern from 2026-06-21 20:46 UTC cycle: 825688 (startups-kickoff) was ranked as NICE_TO_KNOW with deferred fact_memory creation, paired with fact:anthropic-valuation-965b-2026-05 (824830) + decision:rank-20260620-nice_to_know-3-spacex-ai-cloud-pivot-thesis (824950) for the AI-capital-formation-arc pair. See `references/2026-06-21-cycle-notes-2046.md` for full case study.

## Logging

Append a one-line entry to `~/.hermes/logs/tri-state-decide.log` with ISO timestamp, decision IDs and priorities, scores, pool stats, and any skipped re-rank notes. The log is the audit trail the ACT phase reads to know what was decided this cycle.