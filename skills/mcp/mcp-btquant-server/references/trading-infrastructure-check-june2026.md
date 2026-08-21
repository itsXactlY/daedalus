# BTQuant Trading Infrastructure Verification — 2026-06-12

Quick verification checklist when BTQuant trading systems report as degraded.

## Status Check Script (run this first)

```bash
#!/bin/bash
# Run from any directory - outputs simple status indicators

echo "=== MCP ADAPTER ==="
curl -s http://127.0.0.1:8910/health 2>&1 || echo "OFFLINE"

echo -e "\n=== HOTSPINE SHM ==="
ls -la /dev/shm/BTQ 2>&1 || echo "NOT FOUND"

echo -e "\n=== MARKET COLLECTOR ==="
ps aux | grep market_data_collector | grep -v grep || echo "NOT RUNNING"

echo -e "\n=== PULSE POD ==="
systemctl --user status pulse-api --no-pager | head -5
curl -s http://127.0.0.1:8770/healthz 2>&1 || echo "POD OFFLINE"

echo -e "\n=== CACHE STALENESS ==="
find ~/projects/PubBTQuant/.btq_cache -name "*.parquet" -mtime +7 2>/dev/null | head -5
```

## Current Observed State (2026-06-12)

- MCP Adapter: OFFLINE (connection refused on port 8910)
- HotSpine SHM: MISSING (`/dev/shm/BTQ` directory does not exist)
- Market Collector: NOT RUNNING (no process found)
- Pulse Pod: ONLINE (pulse-api.service active, healthz returns OK)
- Cache: STALE (BTC_1m_USDT parquet dated 25. Mai - 18 days old)

## Actionability Matrix

| Signal Component | Requires | Status Check | Actionable If |
|------------------|----------|--------------|---------------|
| watchlist_panel | HotSpine SHM | `/dev/shm/BTQ` exists | SHM present + collector running |
| spread_arbitrage | SHM + detector process | `ps aux \| grep spread` | Both present |
| Binance HotSpine | `/dev/shm/BTQ` | `ls -la /dev/shm/BTQ` | Directory exists |
| Any BTQ signal | MCP adapter | `curl 8910/health` | Returns 200 + content |

## Quick Remediation Steps

1. **Restart HotSpine:**
   ```bash
   cd ~/projects/PubBTQuant
   source venv/bin/activate
   # Follow the HotSpine initialization procedure
   ```

2. **Restart MCP Adapter:**
   ```bash
   cd ~/projects/PubBTQuant/mcp-adapter
   python3 server.py --port 8910 &
   ```

3. **Verify Connection:**
   ```bash
   curl http://127.0.0.1:8910/tools  # Should return 33 tools manifest
   ```