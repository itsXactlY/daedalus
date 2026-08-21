# Triple-Memory Enrichment Pattern (June 16, 2026)

## The Problem
Pulse-Wurm 2.0 discoveries had low graph connectedness (0.2 ratio). When mazemaker_recall queried 'pulse-wurm2', only 2 of top 10 results were fact:* or decision:* labels.

## The Solution
Write THREE linked memories per discovery to ensure strong graph connectivity:

1. **discovery:pulse-wurm-YYYYMMDD-<hash>** (salience 0.4)
   - Main entry: topic, URL, source, summary
   
2. **fact:pulse-discovered-<topic_hash>** (salience 0.5)  
   - Core insight: explicit relevance to target domain (AI agent automation)
   - Key finding with 2-3 sentence summary
   
3. **decision:pulse-wurm-action-YYYYMMDD-<hash>** (salience 0.4)
   - Action linkage: suggested actions, priority, related seeds
   - Explicit graph linkage: "Graph linkage: Linked to fact:<topic_hash>"

## Implementation
Add to save_discoveries.py after URL extraction:

```python
for u in novel_urls:
    url = u['url']
    hash_val = url_hash(url)
    topic_h = topic_hash(url)
    
    # Three linked writes
    remember(f"discovery:pulse-wurm-{timestamp}-{hash_val}", disc_content)
    remember(f"fact:pulse-discovered-{topic_h}", fact_content)  
    remember(f"decision:pulse-wurm-action-{timestamp}-{hash_val}", decision_content)
```

## Results
- Graph edges: derived_from relationships with weights 0.996-1.0
- Connectedness ratio: 0.2 → 0.70+ (7 of 10 top results are now fact/decision)
- See memory ID 741036 for full verification details

## Related
- `references/http-integration-20260616.md` — HTTP POST implementation for mazemaker_remember from shell scripts