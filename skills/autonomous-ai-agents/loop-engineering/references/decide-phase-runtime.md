# DECIDE Phase Runtime — Tri-State Cadence Loop

Runtime workflow for the **DECIDE phase** cron job (60-min cadence). Captured from the 2026-06-22 15:15Z tick. This is the *runtime* guide; the *deployment* details (job IDs, model assignments, schedules) live in `references/tri-state-deployment.md`.

## Job metadata (verify against current crontab)

- **Script:** `python3 ~/.hermes/loops/tri-state/decide_rank.py`
- **Returns:** JSON envelope with `{phase, timestamp, cadence, type: 'decision_request', instructions, priority_buckets, scoring}` — the `instructions` field is the canonical prompt for the agent.
- **Output labels:** `decision:rank-<YYYYMMDD-HHMM>-<priority>-<rank>-<slug>` (priority ∈ {critical, important, nice_to_know})
- **Output memory count:** 3 per tick (top 3 by score)

## The 7-step runtime workflow

### Step 1 — Read the script envelope
```bash
python3 ~/.hermes/loops/tri-state/decide_rank.py
```
The envelope's `instructions` field tells the agent exactly what to do. Trust it. The downstream ACT phase (6AM daily) reads the decision:rank-* labels and acts on them.

### Step 2 — Find recent discoveries: use `mazemaker_browse`, NOT `mazemaker_recall`

**Pitfall:** Semantic `mazemaker_recall(query='discovery:pulse-tick-*', limit=50)` returns mostly `decision:*` items (previous DECIDE phase outputs), because recall is embedding-based and the most-recently-written items dominate. This is a recurring failure mode that wastes tokens on a 600KB-plus result file full of irrelevant past decisions.

**Right way:** `mazemaker_browse(label_prefix='discovery:', limit=100)` — this uses SQL `LIKE` on the label column and returns chronologically-ordered discovery entries. `limit=100` covers a full 24h window in the current 4×/day Pulse-Wurm cadence.

```python
mcp__mazemaker__mazemaker_browse(label_prefix="discovery:", limit=100)
```

### Step 3 — Filter metadata items

Discovery:* labels include operational metadata, not just substantive findings. Exclude these patterns before scoring:

- `*_tick` and `*_tick-summary` — pulse-wurm tick summaries (e.g. `discovery:pulse-wurm-20260622_0554_tick`)
- `CONTEXT:` prefix in content — pulse_search "CONTEXT:" lines that record a search without a finding
- Items with `<500` characters of content — usually procedural notes, not findings

For the 2026-06-22 15:15Z tick: 100 browse items → ~70 substantive, 30 metadata. Skipping metadata cuts scoring work by 30%.

### Step 4 — Pre-screening: skip topics already covered in the last 2 hours

The task says "Skip items already written as decision:rank-* in the last 2 hours to avoid duplicates." Implementation:

```python
# Parse HHMM from recent decision:rank-YYYYMMDD-HHMM-* labels
now_hhmm = 1515  # current UTC
cutoff = now_hhmm - 200  # 1315 in this case; if negative, subtract 2400
for m in decisions_from_last_2h:
    slug_keywords = extract_keywords(m['label'])
    if any(kw in candidate_label.lower() for kw in slug_keywords):
        skip_candidate
```

Keyword-match on slug components is sufficient — full topic semantic dedup is unnecessary because each DECIDE run is small (3 items) and topic overlap is rare. The 2026-06-22 15:15Z tick had zero 2h-overlaps with 4 prior decisions; no skips needed.

### Step 5 — Score candidates: novelty is the discriminator, not connectedness count

**Pitfall:** "Connectedness = count of `fact:*` or `decision:*` labels in top-10 of `mazemaker_recall`" is not informative. Every candidate scores ~10/10 because recent DECIDE writes dominate the top-10 of any recall query. All 4 candidates I checked in the 2026-06-22 15:15Z tick scored 9-10/10 on connectedness — useless for ranking.

**Right metric:** **Novelty = 1 − max similarity to closest existing memory, excluding self-match.** Discriminator results from the 2026-06-22 15:15Z tick:

| Candidate topic | Max sim (excl. self) | Novelty |
|------------------|---------------------|---------|
| California SB-1047 chatbot-toy ban | 0.4794 | 0.5206 |
| Anthropic US-gov escalation timeline | 0.5099 | 0.4901 |
| Lean 4 mathematical finance | 0.5226 | 0.4774 |
| Apple Swift in kernel | 0.5602 | 0.4398 |

**Self-match signal:** When a candidate's `mazemaker_recall` returns the candidate itself at sim ≥ 0.7 in the top-10 (as happened for Apple Swift at 0.7169), that's the strongest possible novelty signal — no close existing memory at all. The novelty formula should exclude self-match from the max-similarity calculation:

```python
existing_sims = [m['similarity'] for m in recall[:10] if m['id'] != candidate_id]
novelty = 1.0 - max(existing_sims) if existing_sims else 1.0
```

### Step 6 — Parse the recall result via `execute_code` + `json.loads(file)`

The recall/browse result files are 100-600KB. Inline `skill_view` / `read_file` chokes on them; the tool result is truncated and dumped to `/tmp/hermes-results/call_<id>.txt`. Efficient pattern:

```python
import json
from hermes_tools import terminal
result = mcp__mazemaker__mazemaker_recall(query=..., limit=10)
# Tool returns untrusted_tool_result; persisted to file
path = '/tmp/hermes-results/call_<id>.txt'  # from tool result preview
with open(path) as f: raw = f.read()
data = json.loads(raw)         # {"result": "[{...}]"}
inner = json.loads(data['result'])  # list of {id, label, content, similarity, ...}
```

This pattern uses ~10 tool calls per tick instead of ~40 (no per-item get calls, no JSON re-parsing by hand).

### Step 7 — Write the top 3 as `mazemaker_remember` with structured content

The content template that future ACT-phase agents can act on:

```
DECISION (DECIDE phase <YYYYMMDD_HHMM> UTC, RANK #<n> of 3 — <PRIORITY>, <one-line title> — <one-line context>):

Discovery Memory ID: <id> (<label>) — <one-paragraph description of what was found + URL + salience>

WHY IT MATTERS (<PRIORITY> — <2-5 numbered reasons, each one factual and specific>):
(1) ...
(2) ...
(3) ...

SCORE BREAKDOWN:
- Connectedness (fact:* or decision:* count in top 10): N/10
- Novelty (1 - closest_existing_memory_similarity): 0.NNNN
- Recency: 1.0
- Composite: <sum>

SUGGESTED ACT-PHASE ACTION: <skill_update | code_fix | config_change | fact:anchor | etc.> — <one-line rationale>
```

Use the `decision:rank-<YYYYMMDD-HHMM>-<priority>-<rank>-<slug>` label. The HHMM is the actual write time, not the tick start.

## When no discoveries are worth ranking

If the substantive filter yields 0 items (rare — usually means a quiet 24h for Pulse-Wurm), write a single `decision:rank-<YYYYMMDD-HHMM>-noise-quiet-window-observed` decision with content "No substantive discoveries in the last 24h; saturation ratio <threshold>; recommend MEASURE-phase review of pulse-wurm seed rotation." This keeps the ACT phase from no-op'ing silently.

## When mazemaker MCP is unreachable during DECIDE

If `mazemaker_recall` returns "MCP server 'mazemaker' is unreachable" during the DECIDE phase:
1. Run `mcp__mazemaker__mazemaker_health` to confirm — sometimes it's a transient blip
2. If confirmed: fall back to **session_search** for recent DECIDE phase outputs (per the ACT-phase recovery pattern in `references/act-phase-recovery.md`)
3. Defer the DECIDE write until next tick — write a `signal:decide-deferred-<date>` noise-rank decision to record the skip
4. Do NOT call `mazemaker_remember` blindly — the write-side cooldown pattern from Pulse-Wurm applies (3 writes → 120s timeout per write)

## Verification

After a DECIDE tick:
1. `mazemaker_recall('decision:rank-20260622-1515', limit=5)` — confirm 3 new decisions landed
2. Spot-check one decision's content for completeness (Discovery ID, score breakdown, suggested action)
3. Confirm the labels follow the `decision:rank-YYYYMMDD-HHMM-<priority>-<rank>-<slug>` pattern — the rank field (1/2/3) and the priority field are both load-bearing for ACT phase

## Related

- `references/tri-state-deployment.md` — cron job IDs, model assignments, schedules
- `references/act-phase-recovery.md` — recovery patterns when mazemaker MCP is unreachable
- `references/pulse-wurm-2.0-tick-20260619-rotation-write-cooldown.md` — write-side cooldown pattern (applies to DECIDE writes too)
- `references/pulse-wurm-2.0-tick-20260621-year-token-resultset-pdf-dedup.md` — pre-save dedup pattern (similar in spirit to the 2h-skip check)
