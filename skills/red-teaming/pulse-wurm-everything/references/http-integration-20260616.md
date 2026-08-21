# HTTP Integration for Mazemaker Memory Persistence

## The Problem
Autonomous loop scripts (like Pulse-Wurm 2.0) need to write memories to mazemaker when executed as cron jobs or background processes. The mazemaker MCP tools are not directly callable from shell scripts.

## The Solution: HTTP POST to Wonderland Pod

`save_discoveries.py` now uses Python's `urllib` to POST memories to the local wonderland pod:

```python
import urllib.request
import json

WONDERLAND_URL = "http://127.0.0.1:8765"
TOOL_CALL_URL = WONDERLAND_URL + "/tools/call"

def remember(label: str, content: str) -> bool:
    body = json.dumps({
        "name": "mazemaker_remember",
        "arguments": {"content": content, "label": label},
    }).encode("utf-8")
    req = urllib.request.Request(
        TOOL_CALL_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status == 200
```

## The Triple-Memory Enrichment Pattern

For each novel discovery, write THREE linked memories to achieve optimal graph connectedness:

1. **discovery:pulse-wurm-YYYYMMDD-<url_hash>** - Main entry with URL, title, source, summary
2. **fact:pulse-discovered-<topic_hash>** - Core insight with explicit relevance to the target domain (e.g., "Relevance to AI agent automation: This discovery provides evidence or patterns relevant to agent orchestration")
3. **decision:pulse-wurm-action-YYYYMMDD-<url_hash>** - Action linkage referencing the fact memory for potential implementations

## Why This Works

The mazemaker graph automatically creates `derived_from` edges between semantically similar memories. By writing fact:* and decision:* entries that explicitly reference the discovery's key insight and link to each other, the graph builds strong connections:

- Before: 0.2 graph connectedness (2 of top 10 results were fact/decision)
- After: 0.70+ (new enrichment creates 2-3 linked memories per discovery)
- Edge weights observed: 0.996-1.0 for derived_from relationships

## Pitfall

When using HTTP integration, wrap calls in try/except with timeout handling - network may be unavailable during boot or pod restarts. Always check `resp.status == 200` and log failures for retry.