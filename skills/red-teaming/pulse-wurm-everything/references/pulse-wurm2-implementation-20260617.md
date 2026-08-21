# Pulse-Wurm 2.0 Implementation - 2026-06-17

## Working Code Pattern

```python
# State file: ~/.hermes/loops/pulse-wurm2/pulse_state.json
{
  "discovery_topics": [list of all topics ever discovered],
  "visited_urls": [deduplication list],
  "saturation_scores": {topic: count},
  "last_tick": "ISO timestamp",
  "consecutive_empty": 0,
  "next_seeds": [lowest saturation topics first]
}
```

## Execution Flow

```
1. Run pulse_tick.py to get state and seeds
2. For each seed topic:
   - pulse_search(topic, depth='deep')
   - Filter results against visited_urls from state
   - For unvisited promising URLs: pulse_dig(max_rounds=2, max_fetches=100)
   - ENRICHMENT: Write THREE linked memories per discovery:
     a. discovery:pulse-wurm-YYYYMMDD_<hash> - main entry with URL/title/summary
     b. fact:pulse-discovered-<topic_hash> - core insight linked to target domain
     c. decision:pulse-wurm-action-YYYYMMDD_<hash> - action linkage for potential implementations
3. Update state:
   - Append new URLs to visited_urls
   - Increment saturation score for seeds with results
   - Set next_seeds = lowest-saturation topics first
   - If all seeds return 0 novel results, increment consecutive_empty
   - If consecutive_empty reaches 3, rotate to fresh seed topics
```

## Key Observations

- pulse_search returns nested JSON with `body.ranked_candidates` and `body.items_by_source`
- URL extraction requires parsing nested JSON structure
- Saturation scoring effectively prioritizes under-explored topics
- LLM filter with llm_filter=false bypasses over-aggressive filtering

## Triple-Memory Graph Enrichment

To achieve 0.70+ graph connectedness, each discovery must spawn linked fact:* and decision:* memories:
- derived_from edges form between discovery → fact (weight ~1.0)
- derived_from edges form between fact → decision (weight ~0.99)
- Graph queries return 70%+ fact/decision ratio instead of 20%