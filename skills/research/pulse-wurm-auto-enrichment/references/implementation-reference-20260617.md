# Pulse-Wurm 2.0 Implementation Reference

## Working Discovery Pattern

The following pattern was successfully used in the 2026-06-17 tick:

### 1. State Loading and URL Tracking

```python
import json

with open('/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json') as f:
    state = json.load(f)

visited_urls = set(state.get('visited_urls', []))
```

### 2. Discovery Memory Format

Each discovery is written as a markdown file with this structure:

```markdown
# discovery:pulse-wurm-YYYYMMDD_<hash>

**Topic**: <topic>
**URL**: <url>
**Summary**: <summary>
**Source Seed**: <seed>
**Key Findings**: <findings>
**Discovered**: <timestamp>

## Related
- See also: fact:pulse-discovered-<topic>, decision:pulse-wurm-action-YYYYMMDD_<hash>
```

### 3. Fact Memory Pattern

```markdown
# fact:pulse-discovered-<topic-slug>

**Core Insight**: <insight>

**Key Discoveries**:
1. **<repo>**: <description>
2. **<repo>**: <description>

**Implications**:
- <implication 1>
- <implication 2>

**Related Discovery**: [[discovery:pulse-wurm-YYYYMMDD_<hash>]]
```

### 4. Decision Memory Pattern

```markdown
# decision:pulse-wurm-action-YYYYMMDD

**Action Items from Pulse-Wurm Discovery**

## Immediate Actions
1. **Evaluate <topic>** - <reason>
2. **Review <framework>** - <reason>

## Integration Opportunities
- <opportunity 1>
- <opportunity 2>

## Security Considerations
- <consideration 1>
- <consideration 2>

**Next Review**: <timestamp>
```

## Actual Discoveries from 2026-06-17

| Topic | URL | Summary |
|-------|-----|---------|
| Autonomous AI coding agents | https://github.com/RalphD-Ger/hermes-system-agent | NVIDIA Jetson deployment with Claude Opus integration |
| Autonomous AI coding agents | https://github.com/ThalesGnimavo/casp | 200-line Coding-Agent State Protocol |
| Autonomous AI coding agents | https://github.com/ajadi/forge | 36-agent pipeline architecture |
| Autonomous AI coding agents | https://github.com/air-gapped/skills | 40+ Claude Code plugins |
| ControlFlowMonitor agents | https://github.com/pensarai/apex | Autonomous security testing |
| VLLM framework vulnerabilities | https://github.com/ibondarenko1/llm-serving-security | CVE matrix and hardening guides |

## State Update Pattern

```python
# Update saturation scores
for topic in topics:
    saturation_scores[topic] = saturation_scores.get(topic, 0) + 1

# Sort by saturation for next seeds
sorted_topics = sorted(saturation_scores.items(), key=lambda x: x[1])
next_seeds = [t[0] for t in sorted_topics[:5]]

# Update state
state.update({
    'visited_urls': list(visited_urls),
    'saturation_scores': saturation_scores,
    'discovery_topics': discovery_topics,
    'last_tick': datetime.now().isoformat(),
    'consecutive_empty': 0,
    'next_seeds': next_seeds
})
```