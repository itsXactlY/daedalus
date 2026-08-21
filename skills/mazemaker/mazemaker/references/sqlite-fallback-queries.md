# SQLite Fallback Queries for Dream Stats

When MCP endpoint at `http://127.0.0.1:8765/mcp` is unreachable during dream dispatch, use direct SQLite queries against `~/.mazemaker/data/memory.db`.

## State File Field Clarification

```json
{
  "last_total_insights": 10109720,  // Main insights counter used by pre-run script
  "last_total": 7575615            // Fallback used by dream_disp.py when MCP fails
}
```

The pre-run script tracks `last_total_insights`. When MCP is down, fall back to SQLite counts and compare against `last_total_insights` field.

## Core Queries (SQLite 3)

```sql
-- Total insight count
SELECT COUNT(*) FROM dream_insights;

-- Bridge insights (dominant pathway type)
SELECT COUNT(*) FROM dream_insights WHERE insight_type = 'bridge';

-- Cluster insights (pattern recognition type)
SELECT COUNT(*) FROM dream_insights WHERE insight_type = 'cluster';

-- Sessions processed
SELECT COUNT(*) FROM dream_sessions;

-- Graph connections
SELECT COUNT(*) FROM connections;

-- Total memories
SELECT COUNT(*) FROM memories;
```

## Growth Threshold Check

```python
import sqlite3
from pathlib import Path
import json

state = json.loads(STATE_PATH.read_text())
last = state.get('last_total_insights', 0)
growth = total_insights - last  # Compare against last_total_insights, not last_total
threshold_met = growth >= 1000
```

## Palace Process Detection

When verifying Palace status without MCP, check for Wonderland wrapper processes:

```bash
ps aux | grep "hermes gateway\|wonderland\|pasta" | grep -v grep
```

The `pasta` process with `8765` in command indicates Wonderland proxy is routing MCP traffic.