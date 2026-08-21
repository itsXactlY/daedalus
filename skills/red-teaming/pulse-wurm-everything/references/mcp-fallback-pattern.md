## MCP Server Unreachable Backoff Pattern

When MCP calls fail with `TimeoutError` or `ClosedResourceError`:
- After 3 consecutive failures, server enters ~45-60s auto-retry cooldown
- During this window, direct REST API calls succeed (pod is still running)

## Direct REST API Access

Pulse pod exposes REST endpoints at `http://127.0.0.1:8770`:

```python
# Health check (no auth required)
curl http://127.0.0.1:8770/healthz

# License status (no auth required)  
curl http://127.0.0.1:8770/license

# Search endpoint (free)
POST /search with {"topic": "...", "depth": "...", "lookback_days": 90}

# Dig endpoint (license-gated)
POST /dig with {"topic": "...", "seed_report": {"candidates": [...]}}
```

## Fallback Strategy
1. Wait 60s after MCP failures (timeout backoff window)
2. Try direct REST API calls to confirm pod is running
3. If REST works, use REST for searches until MCP recovers
4. Resume normal MCP flow once backoff expires

## Session Results (2026-06-12)
- 14 topics researched across AI/ML, hardware, quantum, space, finance, security
- Key findings discovered via ArXiv, Reddit, RSS/OpenAI, Lobsters, Lemmy sources
- Dig operations successfully followed rabbit trails to discover related research papers