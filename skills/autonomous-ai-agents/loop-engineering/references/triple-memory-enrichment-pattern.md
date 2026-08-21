# Triple-Memory Enrichment Pattern
**Date:** 2026-06-17
**Purpose:** Convert discoveries into connected graph memory for better retrieval and reasoning

## Pattern Structure

Each discovery spawns three linked memory entries:

### 1. Discovery Entry (`discovery:pulse-wurm-YYYYMMDD_<hash>`)
- **salience:** 0.4
- **content:** Full discovery details (topic, URL, summary, source_seed, findings, authors, publication date)

### 2. Fact Entry (`fact:pulse-discovered-<topic-slug>`)
- **salience:** 0.3
- **content:** Core insight, key metrics, significance, relationship to discovery
- **related_to:** discovery label

### 3. Decision Entry (`decision:pulse-wurm-action-YYYYMMDD_<hash>`)
- **salience:** 0.4
- **content:** Potential actions, priority, rationale
- **discovery_ref:** discovery label

## Example from ScientistOne Discovery

```
discovery:pulse-wurm-20260617_scientistone
  → fact:pulse-discovered-scientistone-coe
  → decision:pulse-wurm-action-20260617_scientistone
```

## Benefits

1. **Redundancy:** Multiple paths to the same insight
2. **Context:** Facts provide distilled knowledge; decisions provide actionability
3. **Graph Growth:** 3 nodes + 2 edges per discovery increases graph connectivity
4. **Retrieval:** Can find insights via discovery, fact, or decision labels

## Implementation

When saving discoveries:
1. Generate timestamp hash for uniqueness
2. Write discovery first
3. Write fact linking to discovery
4. Write decision linking to discovery
5. Update state file with new visited URLs