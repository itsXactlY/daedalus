# Pulse-Wurm Saturation Prioritization Pattern
*2026-06-17 Implementation*

## Core Mechanism

Topics are scored by number of discoveries they've yielded. The system actively avoids re-exploring high-saturation topics.

## Saturation Scoring Algorithm

```python
# After each tick, update scores
if topic_has_results:
    saturation_scores[topic] += 1

# Sort seeds by saturation for next tick
next_seeds = sorted(all_seeds, key=lambda s: saturation_scores.get(s, 0))
```

## Observed Saturation Distribution

| Topic | Score |
|-------|-------|
| AI agent loop engineering automation systems | 63 |
| MCP protocol ecosystem updates | 61 |
| Codex CLI orchestration workflows | 56 |
| AI agent self-improvement techniques | 42 |
| MCP security vulnerability analysis | 36 |
| Claude Code MCP integration | 5 |
| VLLM inference optimization | 5 |

## Key Insight

Seeds with 0-10 saturation are HIGH priority for exploration.
Seeds with 30+ saturation are DE-prioritized.

## Implementation Notes

1. **State Persistence**: Saturation scores are stored in `pulse_state.json` across sessions
2. **Reset Condition**: `consecutive_empty` counter resets when any seed yields results
3. **Fresh Seed Rotation**: When `consecutive_empty >= 3`, rotate to entirely new topics
4. **URL Deduplication**: All discovered URLs are tracked to prevent re-processing

## Debugging Saturation

If a topic seems under-explored despite high saturation:
- Check if the saturation score was incorrectly incremented
- Verify URL deduplication isn't blocking valid new results
- Consider temporal decay (reduce scores by 10% per week)