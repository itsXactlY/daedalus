## Pulse MCP Tool Argument Bug

**Date:** 2026-08-06
**Tool:** `mcp__pulse__pulse_search`
**Issue:** Tool drops the topic argument even when passed. All pulse operations affected.

**Reproduction:**
```
mcp__pulse__pulse_search({"topic": "test"})
```
Returns: "missing required argument(s): topic"

**Workaround:**
- Check MCP catalog for alternative tool names
- Try calling the pulse MCP script directly via terminal
- Use `mcp__pulse__pulse_diagnose` to check system health