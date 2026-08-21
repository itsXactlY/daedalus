# Decision Label Format and Slug Derivation

## Label Schema

DECIDE-phase decisions follow this exact label pattern:

```
decision:rank-YYYYMMDD-<priority>-<N>-<slug>
```

| Component | Format | Example | Notes |
|-----------|--------|---------|-------|
| `decision:rank-` | literal prefix | `decision:rank-` | Distinguishes from `decision:pulse-wurm-action-*` and `decision:fable-mythos-*` |
| `YYYYMMDD` | UTC date of the cycle | `20260621` | Use UTC date, not local. The cron script's `timestamp` field is UTC. |
| `<priority>` | one of: `critical`, `important`, `nice_to_know` | `critical` | Lowercase, underscore between words. |
| `<N>` | integer 1-3 | `1`, `2`, `3` | Rank within the 3-rank cycle. 1 = highest score. |
| `<slug>` | kebab-case short tag | `palantir-iran-civilian-casualties` | See slug rules below. |

## Slug Derivation Rules

The slug is the human-readable identifier for the discovery. Follow these rules:

1. **Lowercase, kebab-case** (lowercase letters and digits, hyphens between words).
2. **3-6 words** describing the discovery's core finding, not its mechanism.
3. **No dates or version numbers** — these go stale.
4. **No file paths or tool names** unless the discovery IS about that tool.
5. **Use the discovery's most newsworthy noun-phrase** — the entity, event, or finding that a human would search for later.

### Good Slugs

- `palantir-iran-civilian-casualties` (entity + event + outcome)
- `programming-frontier-2026-cluster` (cluster + domain + cluster-marker)
- `velune-cli-deliberative-committee` (tool + novel-pattern)
- `legaltech-mcp-second-wave-megathread-amplification-confirmed` (long but specific; cluster + pattern + confirmation)
- `gpt53codexspark-revisit` (entity + intent — `revisit` indicates this is a re-evaluation)

### Bad Slugs

- `discovery-825469` — useless, just the ID
- `2026-06-21-issue` — date in slug goes stale
- `bug` — too generic
- `palantir_palantir_iran_iran` — word repetition
- `palantir-maven-iran-civilian-casualties-palantir-maven-2026-06` — redundant date/entity repetition

## Content Schema (60-300 words)

The `content` field should follow this structure:

```markdown
DECISION (DECIDE phase YYYYMMDD_HHMM UTC, RANK #N of 3 — <PRIORITY>, <short-tag>):

Discovery Memory ID: <id> (<discovery label>) — <one-line summary of the finding>.

WHY IT MATTERS (<priority label> — <one-line why-it-matters>):
<2-4 paragraphs explaining why this finding matters operationally, what it changes
in the agent's threat model or research agenda, and how it relates to prior work
in the graph. Reference specific memory IDs and decision IDs as evidence.>

SCORE BREAKDOWN:
- Graph connectedness: <X.XX> (<N> of 10 topic-recall results are fact:*/decision:* — <list the key memory IDs>)
- Novelty: <X.XX> (1 - max similarity <Y.YY> to closest non-self memory <id> — <one-line reason>)
- Recency weight: <X.XX> (created YYYY-MM-DD HH:MM UTC, <age-min> old at this cycle — <inside/outside freshness window>)
- Base score: <sum>
- <PRIORITY> priority boost: <+0.XX> (<reason>)
- TOTAL SCORE: ~<final>

SUGGESTED ACTION TYPE: <type>. ACT PHASE ACTIONS:
(1) <action 1 with concrete steps and memory ID references>
(2) <action 2 with concrete steps and memory ID references>
(3) <action 3 with concrete steps and memory ID references>
<additional actions as needed>

CLUSTER CONTEXT:
<N>th of 3 ranks from YYYY-MM-DD HH:MM UTC DECIDE cycle. Pairs with rank #<X> (<id> — <one-line>) and rank #<Y> (<id> — <one-line>). Together: <one-line theme that connects the three>. <Optional: note if this is a gap-filler for a prior cycle's 3-rank limit.>

Label: decision:rank-YYYYMMDD-<priority>-<N>-<slug>
```

## Worked Example (Verified 2026-06-21 08:15Z)

```python
mazemaker_remember(
    content="""DECISION (DECIDE phase 20260621_0815 UTC, RANK #1 of 3 — CRITICAL, US military AI deployment → admitted civilian casualties, MISSED by 08:00 cycle):

Discovery Memory ID: 825469 (discovery:pulse-wurm-20260621-palantir-maven-iran-civilian-casualties) — Palantir Maven Pentagon adoption → 168+ children killed in Iran Minab school strike → Trump public defense ("war is nasty"). <... 200-300 words total ...>

SCORE BREAKDOWN:
- Graph connectedness: 0.50 ...
- Novelty: 0.34 ...
- Recency weight: 1.00 ...
- Base score: 0.50 + 0.34 + 1.00 = 1.84
- CRITICAL priority boost: +0.20 ...
- TOTAL SCORE: ~2.04

SUGGESTED ACTION TYPE: fact_memory + research_watchlist + skill_update. ACT PHASE ACTIONS:
(1) CREATE fact memory: palantir-maven-iran-civilian-casualties-2026-06 ...
<...>

Label: decision:rank-20260621-critical-1-palantir-iran-civilian-casualties""",
    label="decision:rank-20260621-critical-1-palantir-iran-civilian-casualties"
)
```

## When a Cycle Has < 3 Ranks

If the discovery pool produces fewer than 3 rankable items (e.g., 2 CRITICAL and
no IMPORTANT), do NOT pad with NICE_TO_KNOW just to fill 3 slots. Write only
the items that earn a rank. The 3-rank limit is a maximum, not a quota. A
2-rank cycle is fine.

Also: do NOT write 4+ decisions in one cycle. If 4 items are clearly above the
threshold, the 4th goes to the next cycle. The 3-rank limit is a HARD cap.
