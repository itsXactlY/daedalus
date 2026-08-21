# BTQuant Cron Report Template (2026-06-12)

Used for hourly pulse monitoring and system status reporting.

## Critical Status Block
Always check these 3 components first:
- `/dev/shm/BTQ` exists? → HotSpine SHM active
- `ps aux | grep market_data_collector` shows process? → Collector running
- `curl -s http://127.0.0.1:8910/health` returns 200? → MCP adapter listening

If ANY is missing: Signals referencing associated components are non-actionable.

## Pulse Sources Priority
When pulse-search returns candidate pools:
1. **reddit** - Most often has actionable trading posts
2. **tickertick** - Market data feeds, but bias to legacy tickers
3. **polymarket** - Event prediction markets (watch date freshness)
4. **arxiv/sem_scholar** - Research, rarely actionable for live trading
5. **github** - Code repos, may have strategy implementations

## Signal Actionability Thresholds (pulse-pro)
- Score ≥ 0.10: HIGH relevance
- Score 0.04-0.10: MEDIUM relevance (check context)
- Score < 0.04: LOW relevance (often noise)

When score is low AND referenced component offline: Mark as non-actionable.

## Offline Components Matrix
| Component | SHM Path | Process | Pulse References |
|-----------|----------|---------|------------------|
| HotSpine | `/dev/shm/BTQ` | market_data_collector | watchlist_panel feeds |
| MCP Adapter | n/a | mcp-adapter/server.py | 33 trading tools |
| Detectors | SHM + process | 5 detectors | spread_arbitrage, whale_frontrun, etc. |

## Cache Staleness Check
Parquet files in `.btq_cache/`:
```bash
find .btq_cache -name "*.parquet" -mtime +7  # Files older than 7 days = stale
```

Stale cache + no SHM = COMPLETELY offline for trading.