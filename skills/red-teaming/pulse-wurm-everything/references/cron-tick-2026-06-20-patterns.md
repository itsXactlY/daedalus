# Pulse-Wurm 2.0 Tick 2026-06-20 ~02:55 UTC — Three New Patterns

This addendum captures patterns surfaced in the 2026-06-20 cron tick that were not covered by the existing playbook. Read this in addition to `cron-tick-playbook.md` when running a tick.

## Pattern 1: Script Saturation Bump is MCP-Blind

**Problem**: `pulse_tick.py` increments `saturation[seed] += len(discoveries)` based on **GitHub-channel discoveries only**. When MCP pulse_search deep yields 5+ novel on a seed but the GitHub channel returns 0, the script sets `saturation[seed] = 0` even though the agent will call `mazemaker_remember` for the MCP discoveries.

**Consequence**: The next tick's saturation-sort re-picks that seed (still at sat 0) and burns a tick on a fully-exhausted-for-its-phrasing seed.

**Workaround**: After MCP yields novel, manually bump the seed's saturation by the MCP count:

```python
# If MCP surfaced N genuinely novel discoveries on seed X (and the script found 0):
saturation[seed] = saturation.get(seed, 0) + N
```

This pushes the seed out of the next-tick pool and rotates in unsaturated seeds. Without this bump, the next 6-hour tick re-processes the same seed and gets 0 novel again — a wasted tick that increments `consecutive_empty` and risks triggering premature rotation.

**Real case**: ADK Arena seed processed. Script GitHub found 0. MCP pulse_search deep on the same seed yielded 5 novel (Watts/Debts 2606.10702, Arena Fixed-Model 10.1145/3786335.3813233, Do Agents Need Semantic Metadata? 2605.28787, Minimal Oversight 2606.15563, OpenAI biorisk early warning). Without manual bump, ADK Arena would have stayed at sat 0 and the next tick would re-pick it. Bumped to sat 5, ADK Arena correctly deprioritized for next tick.

**Related pattern**: Inverse of the "saturation-out behavior on successful yield" section in the playbook. The script handles GitHub yields + MCP zero. The agent must handle MCP yields + GitHub zero.

## Pattern 2: Seed Phrasing vs. Topic Saturation — Retire Phrasings, Not Topics

**Problem**: A seed's exact wording can saturate while the underlying topic is still productive. The rotation threshold (`consecutive_empty >= 3`) triggers a hard-coded fresh pool, but individual seed phrasings can saturate independently of the topic's overall productivity.

**Symptom**: Seed "AGENTSERVESIM (mazemaker 824431, seed=agent inference substrate KV cache cross-turn opti, 2026-06-20)" was added to the pool at saturation 0, anchored on the saved AGENTSERVESIM paper (mazemaker id 824431). The MCP openalex sub-channel on this exact phrasing returned 20 candidates — **all 20 dropped by the Ollama filter as off-topic** (Ti metallurgy cond-mat.mtrl-sci, Tied Links math.GT, MultiQG-TI text-to-SQL, etc.). 0/20 kept.

**Yet the underlying topic** ("agent inference substrate KV cache cross-turn optimization") has been highly productive under different phrasings in prior ticks: decision memory 822479 documents 4 papers in the cluster (Model-Native Computing 2606.00288, Leyline 2606.01065, Stateful Inference 2605.26289, Evoflux 2606.12674) plus Fail-Closed KV 2606.01387 (id 824436), with saturation 13 for the underlying seed.

**Diagnosis**: The openalex sub-channel's query embedding for the specific "AGENTSERVESIM" phrase routes to cond-mat.mtrl-sci / math.GT noise. The "agent inference substrate" phrasing routes to actual 2026 agentic-AI research. The query-planner heuristic over-indexes on the abstract-academic-anchor pattern when given a paper name.

**Rotation pattern when this happens**:

1. **Don't retire the topic** — saturation-out the seed with the saturated phrasing, but keep the productive follow-on phrasing in the queue or add it.
2. **Mark the saturated phrasing as exhausted** by bumping its saturation to a high value (e.g. 8-10) so the saturation-sort skips it.
3. **Add a fresh-angle phrasing for the same topic** with a new seed name (e.g. "agentic cross-turn KV cache reuse contract conformance vLLM 2026") that routes to the productive sub-channel.

**How to detect phrasing saturation vs. topic saturation**:
- Phrasing saturation: pulse_search on the exact seed text returns 0/40 kept, all noise of a consistent type (Ti metallurgy, Tied Links, etc.)
- Topic saturation: pulse_search on the same topic under a different phrasing also returns 0/40
- If only the original phrasing returns 0 but alternative phrasings still yield novel → phrasing saturation, not topic saturation

## Pattern 3: Anchor-Paper Seeds Can Still Yield Productive Follow-On Clusters

**Problem**: A seed whose name is a previously-saved paper (e.g. "ADK Arena: Evaluating Agent Development Kits via LLM-as-a-Developer" with the ADK Arena paper already saved as mazemaker id 822442) might look exhausted on first inspection, but the MCP openalex + rss sub-channels can surface a productive follow-on cluster around the anchor paper.

**Why this happens**: The seed's literal anchor paper is saved, but the broader research cluster around it keeps growing. The MCP sub-channels index on the paper's topic (ADK evaluation, agent framework comparison), not on the paper itself, so they surface:
- **Competitor benchmarks** (different group, same evaluation problem)
- **Sister methodology papers** (same DOI prefix, complementary angle)
- **Governance pairs** (the same problem space but on the policy/oversight axis)
- **Distinct vendor axes** (OpenAI biorisk frontier vs. agent governance cluster — different axis entirely, surfaced because the openalex co-citation graph links them)

**Real case**: ADK Arena seed at saturation 0, anchor paper 2606.05548 already in mazemaker. MCP pulse_search deep on this seed yielded 5 genuinely novel discoveries:
1. arxiv 2606.10702 "Watts and Debts of Agentic Frameworks" — direct competitor empirical study
2. DOI 10.1145/3786335.3813233 "Arena: Benchmarking AI Agent Frameworks Under Fixed-Model Conditions" — sister methodology (same DOI prefix as Malice in Agentland / Securing the Agent cluster)
3. arxiv 2605.28787 "Do Agents Need Semantic Metadata?" — ADK-relevant comparative study
4. arxiv 2606.15563 "Minimal Oversight: Uncertainty-Aware Governance for Delegated AI Systems" — governance axis pair
5. openai.com/index/building-an-early-warning-system-for-llm-aided-biological-threat-creation — OpenAI biorisk frontier (distinct from agent governance cluster)

**Rule**: Don't auto-retire a seed just because the literal anchor paper is in `visited_urls`. Check the openalex + rss sub-channels for follow-on cluster extensions before retiring. If the sub-channels also return all noise, THEN retire.

## Pattern 4: Hard-Coded Rotation Pool Sits in the Saturated Cluster — 2026-06-20 ~04:01 UTC

**Problem**: When `consecutive_empty >= 3` triggers, `pulse_tick.py` rotates `next_seeds` to a hard-coded pool:

```python
seeds = ["MCP security best practices", "LLM agent sandboxing",
         "AI model watermarking", "Autonomous agent red teaming",
         "Secure AI code generation"]
```

As of 2026-06-20, **4 of these 5 seeds point into the agent-security cluster — the single most-saturated topic space** (40+ discoveries/decisions in mazemaker in the last 48h). The hard-coded pool rotates the loop right back into the saturated cluster.

**State file evidence (2026-06-20 04:01 UTC)**:
- `"MCP security best practices 2026"` saturation = 4 (multiple prior ticks)
- `"LLM agent sandboxing 2026"` saturation = 5
- `"Autonomous agent red teaming 2026"` saturation = 4
- `"Secure AI code generation 2026"` saturation = 3
- `"AI model watermarking"` — NOT in state at all (the one fresh seed)

The rotation pool uses `"MCP security best practices"` without the `"2026"` suffix, so it would be a NEW seed (saturation 0) — but the openalex sub-channel routes "MCP security best practices" to the same dense cluster as `"MCP security best practices 2026"`. Phrasing differs, saturation sort treats as new, but topic is identical.

**Implication**: If rotation triggers at consecutive_empty=3, the next 1-2 ticks will saturate against the same cluster and trigger rotation again, looping on the hard-coded pool. The saturation-sort re-pick loop bug (covered in `cron-tick-playbook.md`) compounds this — the just-failed seeds re-enter next_seeds at sat 1-2, ahead of the rotated seeds.

**Pre-emptive workaround** (when consecutive_empty is 2 and rotation is imminent):

1. Bump the about-to-rotate hard-coded seeds to saturation 8+ BEFORE the script runs, so the saturation-sort skips them:
   ```python
   hard_coded = ["MCP security best practices", "LLM agent sandboxing",
                 "AI model watermarking", "Autonomous agent red teaming",
                 "Secure AI code generation"]
   for s in hard_coded:
       state["saturation_scores"][s] = max(state["saturation_scores"].get(s, 0), 8)
   ```

2. Add 5 fresh-angle seeds from LEAST-SATURATED clusters that are NOT in the agent-security family. From `state["saturation_scores"]` at 2026-06-20 04:01 UTC:
   - `AI GPU supply chain 2026 HBM3E packaging constraints` (sat 9)
   - `model native computing architecture LLM agent OS inference substrate 2026` (sat 9)
   - `EU AI Act enforcement August 2026 deadline compliance gap` (sat 13)
   - `EU AI Act Article 50 transparency AI agent identity disclosure` (sat 4)
   - `Linux kernel eBPF AI inference accelerator patches 2026` (sat 10)

3. Lower consecutive_empty back to 0-1 so rotation doesn't trigger.

**Root fix** (for a future pulse_tick.py revision): the hard-coded rotation pool should be a parameter (env var, config file, or state field `rotation_pool`) rather than a code constant. The operator updates the pool manually when the cluster landscape shifts. As of 2026-06-20 the pool has not been updated since 2026-06-17 — the cluster landscape has shifted substantially since then.

**Diagnostic check before rotation**: Before consecutive_empty hits 3, check `state["saturation_scores"]` for the 5 about-to-rotate hard-coded seeds. If 4 of 5 are already at saturation 3+, rotation into this pool is wasteful — pre-empt the rotation with the bump-and-redirect pattern above.

## Pattern 5: Specific arxiv-ID Seeds Return Near-Zero Candidates — 2026-06-20 ~04:01 UTC

**Observation**: A seed of the form `"<arxiv paper title> arxiv <id>"` (e.g. "A Query Engine for the Agents arxiv 2605.27785") returned only **2 ranked_candidates** in pulse_search deep — both Reddit posts, both low-relevance.

**Why this matters**: The saturation-sort treats these as fresh seeds (sat 0), so they re-enter the next-tick pool and burn ticks producing near-zero signal.

**Compare**: Topic-descriptive seeds (e.g. "agent inference substrate KV cache cross-turn optimization") routed to openalex and yielded 6-10 candidates per tick — the productive pattern. The arxiv-ID seeds route to noise because:
- The LLM-filter sees the paper name as an "abstract-academic-anchor" pattern and routes to unrelated academic content
- The query planner treats arxiv IDs as identifiers, not topics
- The matched papers in openalex don't have the exact ID, so they don't surface

**Rule for seed design**: Avoid including literal arxiv IDs in seed text unless the seed is explicitly meant to find follow-on work to a specific paper. Even then, prefer `"<topic> follow-on <author/lab> 2026"` over `"<paper title> arxiv <id>"`. The openalex sub-channel is more productive with topic + author phrasing.

**Confirmed same-tick data** (2026-06-20 04:01 UTC pulse_search deep, depth='default', llm_filter=true):
- Seed "A Query Engine for the Agents arxiv 2605.27785" → 2 ranked_candidates, 0 productive
- Seed "autonomous web navigation theory human browsing behavior agent 2026" → 6 ranked_candidates, 0 productive (saturated topic)
- Seed "detection-in-depth offensive cyber agents defense primitive 2026" → 10 ranked_candidates, all cluster-bloat

**Pattern interaction**: Pattern 2 above (Seed Phrasing vs. Topic Saturation) covers the general case. This is a specific instance — arxiv-ID seeds are a "phrasing saturation" subtype where the literal ID anchor causes the LLM filter to misroute.

## Pattern 6: arxiv-ID-Anchored Reformulation (Tier 3) — When Tier 2 Fails (2026-06-20 ~05:51 UTC)

The "Concrete reformulations yield, abstract academic phrasing fails" pattern in the playbook is tier-2 (topic-descriptive reformulation). When tier 2 still fails, escalate to tier 3 — anchor the topic on a confirmed arxiv ID.

**Tier progression**:
- **Tier 1** (academic phrasing): `"LLM agent DoS rate-limit cost amplification guardrail bypass 2026"` — fails (intent=person_research, routes to reddit noise)
- **Tier 2** (concrete reformulation): `"LLM agent reasoning budget exhaustion test-time-compute denial wallet attack 2026"` — fails on the same seeds (still routes to reddit/tickertick noise)
- **Tier 3** (arxiv-ID anchored): `"arxiv 2605.25632 Insuring Every Action Authority Frontier Runtime Actuarial"` — works, returns 4 cluster papers

**Why tier 3 works**:
- The query planner treats the arxiv ID as an entity identifier → routes to openalex sub-source
- The literal ID is a high-confidence token → top scores for exact-ID matches
- The ID anchors the result to the *cluster around that paper*, surfacing adjacent papers that share the same author network / DOI prefix / citation graph

**Trigger to escalate to tier 3**:
- Tier 1/2 returned 1+ on-topic paper with low score (0.01-0.03) → that's the cluster anchor
- Conventional phrasing misroutes to noise clusters (NBA, weddings, Ti metallurgy)
- 2-3 prior attempts on the same seed returned 0 on-topic yield

**Don't abuse tier 3**: Requires a confirmed anchor paper first. Not a first-line search.

**Real case**: 2026-06-20 ~05:51 tick surfaced 3 saves (824667/824668/824669) in the actuarial-for-autonomous-agents cluster via tier-3 anchor on 2605.25632.

## Pattern 7: Pre-Save Duplicate Check via discovery_topics (2026-06-20 ~05:51 UTC)

`visited_urls` cross-check alone misses papers saved in a different URL form (`/abs/` vs `/pdf/`) or saved under a slight title variation. The `discovery_topics` audit log is the ground-truth secondary check.

**When to apply**: Before saving any candidate that surfaced from a tier-3 (arxiv-ID-anchored) reformulation, since tier-3 specifically returns papers in the cluster of the anchor — most are already-saved.

**Cross-check recipe**:

```python
arxiv_id = "2606.16465"
# Check both URL forms in visited_urls
abs_form = f"https://arxiv.org/abs/{arxiv_id}" in visited_urls
pdf_form = f"https://arxiv.org/pdf/{arxiv_id}" in visited_urls
# Check discovery_topics for the ID (audit log)
saved_before = any(arxiv_id in str(t) for t in state["discovery_topics"])
if abs_form or pdf_form or saved_before:
    # Already saved — mark visited only, do NOT call mazemaker_remember
    pass
```

**Real case (2026-06-20 ~05:51)**: arxiv 2606.16465 Trace-Economic Underwriting surfaced via tier-3. `parse_pulse_search.py` normalization flagged it as visited (the abs form was in visited_urls), and the discovery_topics grep confirmed it was saved 2 hours earlier (2026-06-20 ~03:45 tick). Saved 1 mazemaker slot for a genuinely novel paper in the same cluster.

## Pattern 8: Cluster-Growth Heuristic — Save Threshold Tied to Cluster Size (2026-06-20 ~05:51 UTC)

Refines the cluster-bloat discipline (save only when paper adds a new angle) with quantitative cluster-size thresholds:

| Cluster size | Cluster age | Action |
|---|---|---|
| 0-1 papers | n/a | Save freely — first paper defines the cluster |
| 2-3 papers | <30 days | Save new angles only; benchmark-heavy candidates visited-only |
| 4-5 papers | <30 days | Save only if angle is methodologically distinct |
| 6+ papers | <30 days | Cluster-bloat risk: save at most 1/tick regardless of yield |
| 4+ papers | 30-90 days | Mature: save only if new methodology |

**Cluster-saturation diagnostic** (use when in doubt):

```python
# Grep discovery_topics for cluster's anchor terms
cluster_terms = ["actuarial", "insurance", "2606.16465", "2605.25632"]
matching_entries = [t for t in state["discovery_topics"] if any(c in str(t) for c in cluster_terms)]
# Count unique arxiv IDs in matching entries
import re
arxiv_ids = set()
for entry in matching_entries:
    arxiv_ids.update(re.findall(r"\d{4}\.\d{4,5}", str(entry)))
print(f"Cluster: {len(matching_entries)} entries, {len(arxiv_ids)} unique papers")
```

**Don't auto-retire**: The actuarial cluster reached 4 papers in 36 hours (this tick) and all 4 are still save-worthy because each introduces a distinct angle (authority frontier / time-consistency / strategy-proofness / trace-economics). Density alone is not the signal — methodology diversity is.

## Tick Report Format (delivered as response, not file)

The 6-hour cron tick delivers its report as the agent's final response (not as a `pulse_wurm_tick_YYYYMMDD_HHMM.md` file). The "When the Operator Asks" section of the playbook references per-tick report files, but those are written by 4x/hour or manual ad-hoc ticks, not the 6-hour cron. The cron response itself is the durable tick record.

**Implication**: The tick report should be self-contained:
- Tabular seed-processing summary (before/after saturation, novel count)
- List of mazemaker IDs saved
- Cluster bloat discipline application (which URLs marked visited only)
- State changes summary
- Next-tick recommendations (which seeds to retire, which to add)

This is what gets delivered automatically to the cron destination, so the operator's downstream consumers (e.g. rank-and-decide cycles, hermes-kanban workers) see it as the canonical tick artifact.
