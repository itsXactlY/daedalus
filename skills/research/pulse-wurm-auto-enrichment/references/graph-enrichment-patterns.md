# Graph Enrichment Patterns for Pulse-Wurm

## Problem Statement

Pulse-Wurm 2.0 (memory ID 744962) operates efficiently but has low graph linkage:
- Only 20% of recall results are fact:* or decision:* entries
- Goal: Increase to 70%+ fact/decision ratio

## Triple-Memory Linkage Pattern

Each discovery should spawn three linked memories:

```
discovery:pulse-wurm-YYYYMMDD_<hash>     (salience: 0.4)
        ↓ derived_from
fact:pulse-discovered-<topic_hash>        (salience: 0.6)  
        ↓ derived_from
decision:pulse-wurm-action-YYYYMMDD_<hash> (salience: 0.5)
```

## Fact Extraction Heuristics

### Content-Based Patterns

| Pattern | Fact Label Template | Example |
|---------|---------------------|---------|
| autonomous agent | `fact:pulse-discovered-autonomous-<hash>` | "Autonomous agent workflow identified" |
| security vuln | `fact:pulse-discovered-security-<hash>` | "Security consideration: .env loading" |
| framework/tool | `fact:pulse-discovered-framework-<hash>` | "Implementation framework: Fable |
| research paper | `fact:pulse-discovered-research-<hash>` | "Research finding: MAS-Algorithm papers" |

### Key Extraction Rules

1. Extract the core insight (what was discovered)
2. Link to source domain/topic explicitly
3. Include actionable context ("Why it matters")
4. Set salience 0.6 (high importance for knowledge retention)

## Decision Generation Patterns

### Default Template

```
Action: Evaluate integrating '{topic}' into Hermes workflows.

Why it matters: Pulse-Wurm identified this as novel and relevant.

Suggested next steps:
- [topic-specific action based on URL domain/content]
- Research compatibility with existing infrastructure  
- Document for future implementation

Source discovery ID: {memory_id}
```

### Domain-Specific Actions

| Source/Topic | Decision Action |
|--------------|-----------------|
| github.com | Clone and analyze repository |
| arxiv.org | Read and summarize for knowledge base |
| security topic | Add to security review checklist |
| framework/tool | Evaluate for integration into workflows |
| autonomous agent | Test with mazemaker dream cycles |

## Edge Weight Calibration

### Derived_From Weights

| Source → Target | Weight | Rationale |
|-----------------|--------|-----------|
| discovery → fact | 1.0 | Direct source of insight |
| fact → decision | 0.99 | Strong causal relationship |
| discovery → decision | 0.75 | Weaker direct relationship |

These weights ensure:
- Fact entries surface in recall when querying discovery topics
- Decisions surface in graph traversal from facts
- Graph clustering groups related discoveries and their actions

## Integration with pulse-wurm-2 Tick

Modify pulse_tick.py to call enrichment:

```python
# After storing discoveries, call:
from skills.research.pulse-wurm-auto-enrichment.scripts.enrich_discoveries import enrich_all

enrich_all(discovered_findings)
```

Or use wrapper script:
```bash
python3 ~/.hermes/skills/research/pulse-wurm-auto-enrichment/scripts/enrich_discoveries.py --from-state
```