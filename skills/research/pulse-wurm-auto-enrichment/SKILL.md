---
name: pulse-wurm-auto-enrichment
description: "Automatically enriches Pulse-Wurm discoveries with linked fact:* and decision:* entries after each pulse-wurm-2 tick to improve graph connectedness."
type: "skill"
category: "research"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [pulse, enrichment, knowledge-graph, automation, fact-decision-linkage]
    related_skills: [pulse-wurm-everything, mazemaker]
---

# Pulse-Wurm Auto-Enrichment Skill

## Overview

Automatically enriches Pulse-Wurm discoveries with linked fact:* and decision:* entries after each pulse-wurm-2 tick. This skill addresses the graph linkage problem identified in Discovery Memory ID 744962, where Pulse-Wurm 2.0 operates efficiently (15 URLs visited, 1 discovery topic seeded, 0 empty ticks) but has low graph linkage (only 2 of top 10 recall results are fact:* or decision:*).

The enrichment process creates a triple-memory structure for each discovery:
1. **discovery:** pulse-wurm-YYYYMMDD_<hash> — main entry with URL/title/summary
2. **fact:** pulse-discovered-<topic_hash> — core insight linked to the discovery
3. **decision:** pulse-wurm-action-YYYYMMDD_<hash> — action linkage for potential implementations

## When to Use

- Pulse-Wurm 2.0 tick completes and needs automatic knowledge graph enrichment
- You want to improve graph connectedness scores from 0.2 to 0.70+
- Discovery outputs need structured fact/decision linkage for downstream consumption
- Running as part of the pulse-wurm-2 cron job post-processing

### Don't use for:
- Manual discovery curation (use mazemaker_remember directly)
- Pulse-Wurm Everything reconnaissance (uses different workflow)
- Non-pulse related memory creation

## Trigger Conditions

This skill should run automatically after each pulse-wurm-2 tick with the following triggers:

```yaml
triggers:
  - source: cron.job.completed
    job_name: pulse-wurm-2
    condition: discovery_writes > 0
  - source: mazemaker.recall
    query: "discovery:pulse-wurm-2026*"
    condition: no_linked_fact_or_decision
  - source: pulse.output
    field: novels_found
    condition: value > 0
```

## Implementation Steps

### Step 1: Discovery Detection

Detect novel discoveries from the latest pulse-wurm-2 tick using mazemaker_recall:

```python
from mcp_mazemaker import mazemaker_recall

# Find recent pulse-wurm discoveries
discoveries = mazemaker_recall(
    query="discovery:pulse-wurm-*",
    limit=20,
    label_prefix="discovery:pulse-wurm"
)
```

### Step 2: Fact Extraction

For each discovery, extract key insights and create fact:* entries:

```python
def extract_facts(discovery_content: str, topic: str) -> list[str]:
    """Extract 1-3 core facts from a discovery."""
    facts = []
    
    # Pattern-based extraction for common discovery types
    if "autonomous" in discovery_content.lower():
        facts.append(f"Autonomous agent pattern: {topic}")
    if "framework" in discovery_content.lower():
        facts.append(f"Implementation framework identified: {topic}")
    if "security" in discovery_content.lower() or "vulnerability" in discovery_content.lower():
        facts.append(f"Security consideration: {topic}")
    
    return facts
```

### Step 3: Decision Generation

Generate actionable decisions based on discovery patterns:

```python
def generate_decisions(topic: str, source_url: str) -> list[str]:
    """Generate actionable decisions from a discovery."""
    decisions = []
    
    # Common decision patterns
    decisions.append(f"Evaluate {topic} for integration into autonomous agent workflows")
    decisions.append(f"Research {topic} implementation with existing MCP infrastructure")
    
    if "github" in source_url or "repo" in source_url:
        decisions.append(f"Clone and analyze repository for {topic}")
    
    return decisions
```

### Step 4: Memory Persistence

Write linked memories using mazemaker_remember:

```python
from mcp_mazemaker import mazemaker_remember

# Write triple for each discovery
def enrich_discovery(topic: str, url: str, summary: str, discovery_id: int):
    # (a) Main discovery - already written by pulse-wurm-2
    
    # (b) Fact entry
    fact_label = f"fact:pulse-discovered-{hash_topic(topic)}"
    mazemaker_remember(
        content=f"{summary}\\n\\nSource: {url}\\n\\nThis insight emerged from Pulse-Wurm reconnaissance on {topic}.",
        label=fact_label,
        salience=0.6
    )
    
    # (c) Decision entry
    decision_label = f"decision:pulse-wurm-action-{timestamp}-{hash_hex}"
    mazemaker_remember(
        content=f"Evaluate integrating {topic} into Hermes workflows.\\n\\nJustification: {summary}\\n\\nSource URL for analysis: {url}",
        label=decision_label,
        salience=0.5
    )
```

### Step 5: Graph Edge Formation

The enrichment process automatically creates derived_from edges through the label-based linkage. Verify edges formed:

```python
from mcp_mazemaker import mazemaker_browse

# Check for fact/decision linkage
fact_decision_ratio = count_fact_decision_links() / total_discoveries
target_ratio = 0.70  # 70%+ fact/decision connectedness
```

## Salience and Label Patterns

### Salience Values

| Memory Type | Salience | Rationale |
|-------------|----------|-----------|
| discovery:* | 0.4 | Default for pulse discoveries |
| fact:* | 0.6 | Higher - core knowledge to preserve |
| decision:* | 0.5 | Medium - actionable but secondary |

### Label Format

```
discovery:pulse-wurm-YYYYMMDD_<6char_hash>
fact:pulse-discovered-<topic_slug>-<topic_hash>
decision:pulse-wurm-action-YYYYMMDD_<6char_hash>
```

Example:
```
discovery:pulse-wurm-20260617-9cc0b5
fact:pulse-discovered-autonomous-agents-9cc0b5
decision:pulse-wurm-action-20260617-9cc0b5
```

## Example Usage

### Basic Enrichment Function

```python
#!/usr/bin/env python3
"""Auto-enrichment for Pulse-Wurm discoveries."""
import re
import json
import hashlib
from mcp_mazemaker import mazemaker_remember, mazemaker_recall

def hash_topic(topic: str) -> str:
    """Create short hash from topic string."""
    return hashlib.md5(topic.encode()).hexdigest()[:6]

def create_discovery_memory(topic: str, url: str, summary: str, source_seed: str) -> str:
    """Create a discovery memory with mazemaker-style format."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    date_str = datetime.now().strftime('%Y%m%d')
    label = f"discovery:pulse-wurm-{date_str}_{url_hash}"
    
    content = f"""# {label}

**Topic**: {topic}
**URL**: {url}
**Summary**: {summary}
**Source Seed**: {source_seed}
**Key Findings**: [Extract key insights here]
**Discovered**: {datetime.now().isoformat()}

## Related
- See also: fact:pulse-discovered-{topic.replace(' ', '-').lower()}, decision:pulse-wurm-action-{date_str}_{url_hash}
"""
    mazemaker_remember(content=content, label=label, salience=0.4)
    return label
```

def enrich_pulse_discoveries():
    """Find and enrich unlinked pulse discoveries."""
    # Get discoveries from last 24 hours
    discoveries = mazemaker_recall(
        query="discovery:pulse-wurm-*",
        limit=10,
        label_prefix="discovery:pulse-wurm"
    )
    
    enriched_count = 0
    for d in discoveries.get("result", []):
        memory_id = d.get("id")
        content = d.get("content", "")
        
        # Extract topic from discovery content
        topic_match = re.search(r"Topic:\s*(.+?)(?:\n|$)", content)
        if not topic_match:
            continue
            
        topic = topic_match.group(1).strip()
        
        # Check if already enriched
        linked = mazemaker_recall(query=f"derived_from:{memory_id}")
        if linked.get("total", 0) > 0:
            continue
        
        # Create fact entry
        fact_label = f"fact:pulse-discovered-{hash_topic(topic)}"
        mazemaker_remember(
            content=f"Pulse-Wurm discovered {topic}. Key insight extracted for knowledge graph integration.",
            label=fact_label,
            salience=0.6
        )
        
        # Create decision entry
        decision_label = f"decision:pulse-wurm-action-{d.get('created_at', '')[:8]}"
        mazemaker_remember(
            content=f"Action: Evaluate {topic} for implementation in Hermes workflows. Source discovery ID: {memory_id}",
            label=decision_label,
            salience=0.5
        )
        
        enriched_count += 1
    
    return {"enriched": enriched_count}

# Run enrichment
result = enrich_pulse_discoveries()
print(f"Enriched {result['enriched']} discoveries")
```

### Cron Integration

Add to pulse-wurm-2 cron job:

```bash
# After pulse_tick.py completes, run enrichment
python3 ~/.hermes/skills/research/pulse-wurm-auto-enrichment/enrich_discoveries.py
```

The pulse-wurm-2 cron job should invoke this skill by modifying its prompt:

```yaml
cron_job:
  name: pulse-wurm-2
  schedule: "15 */6 * * *"
  post_process:
    - skill: pulse-wurm-auto-enrichment
      trigger: on_discovery_write
      action: enrich_all_recent
```

## Verification Checklist

After each tick:

- [ ] Discovery memories created (label: `discovery:pulse-wurm-*`)
- [ ] Fact memories created for each discovery (label: `fact:pulse-discovered-*`)
- [ ] Decision memories created for each discovery (label: `decision:pulse-wurm-action-*`)
- [ ] Derived_from edges formed between discovery → fact → decision
- [ ] Graph connectedness ratio improved (target: 70%+ fact/decision linkage)
- [ ] State file updated with enriched topic counts

## Common Pitfalls

1. **Missing linkage**: If facts/decisions aren't linked, verify derived_from edges are being stored by checking mazemaker_browse for related_skills patterns.

2. **Low salience**: Using salience < 0.4 may cause facts to decay too quickly during dream cycles.

3. **Duplicate topics**: The hash_topic function ensures unique labels; without it, duplicate discoveries will overwrite.

4. **Enrichment timing**: Running enrichment before discovery write completes causes missing memory IDs. Always enrich after pulse tick confirms writes.

5. **Topic extraction failure**: If Topic: pattern doesn't match discovery content, extraction fails. Add fallback via URL domain parsing.

## Reference Files

- `references/graph-enrichment-patterns.md` — Detailed fact/decision extraction patterns
- `references/edge-weight-calibration.md` — Derived_from edge weight tuning for optimal graph connectivity
- `references/implementation-reference-20260617.md` — Working implementation from actual tick
- `references/pulse-wurm2-implementation-20260617.md` — Working pattern from pulse-wurm-everything skill
- `scripts/enrich_discoveries.py` — Runnable script for post-tick enrichment

## Metrics to Track

| Metric | Target | Current | Measurement |
|--------|--------|---------|-------------|
| Fact/decision ratio | 0.70+ | ~0.20 | recall label distribution |
| Graph edges per discovery | 2+ | ~0 | mazemaker_think depth-2 |
| Salience retention | 0.5+ avg | 0.4 | mazemaker_health scores |