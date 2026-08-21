---
name: mcp-btquant-server
category: mcp
description: MCP server for BTQuant trading framework - operational status, tools, startup
tags: [mcp, btquant, trading, server]
---

# BTQuant MCP Server

## Status Verification (as of 2026-06-12)

### How to Check Current Status
```bash
# Check MCP adapter port
curl -s http://127.0.0.1:8910/health 2>&1 || echo "MCP ADAPTER OFFLINE"

# Check HotSpine SHM (critical for trading signals)
ls -la /dev/shm/BTQ 2>&1 || echo "SHM NOT FOUND"

# Check market_data_collector process
ps aux | grep market_data_collector | grep -v grep || echo "NO COLLECTOR"

# Check pulse pod (trading data source)
systemctl --user status pulse-api
curl -s http://127.0.0.1:8770/healthz
```

### Known Offline State (2026-06-12)
- **MCP Adapter (8910):** OFFLINE — curl returns connection refused
- **HotSpine SHM:** MISSING — `/dev/shm/BTQ` does not exist
- **Market Collector:** NOT RUNNING
- **Cache Staleness:** BTC parquet files stale (>7 days old)
- **Pulse Pod:** ONLINE on port 8770, but trading infrastructure disconnected

### When Offline: Signal Actionability Check
If MCP adapter or HotSpine is offline, ALL trading signals referencing these components are NON-ACTIONABLE. Check before reporting trading opportunities.

## Startup

```bash
cd ~/projects/PubBTQuant/mcp-adapter
python3 server.py --port 8910
# Verify: curl http://127.0.0.1:8910/health
```

## Tool Categories (33 total)

| Category | Count | Tools |
|----------|-------|-------|
| project | 4 | project_info, project_git_status, project_cmakelists, project_file_tree |
| build | 4 | build_list_targets, build_run, build_clean_all, build_check_compiler |
| test | 3 | test_list, test_run, test_lint |
| backtest | 4 | backtest_list_strategies, backtest_list_indicators, backtest_run_simple, backtest_strategy_source |
| agency | 5 | agency_status, agency_start, agency_stop, agency_logs, agency_strategies |
| neural | 4 | neural_status, neural_run_feature_selection, neural_run_walk_forward, neural_pipeline_config |
| data | 6 | data_hotspine_status, data_hotspine_run_test, data_mssql_status, data_ccapi_process, data_detector_process, data_mock_producer |
| exchange | 2 | exchange_status, exchange_not_connected |

## Hermes Integration

Config already exists in `~/.hermes/config.yaml` under `mcp_servers.btquant`. No manual setup needed.

## Common Issues

- **Server not responding:** Check with `curl http://127.0.0.1:8910/health`
- **Dependencies missing:** Usually pre-installed (starlette, uvicorn, sse-starlette)

## Trigger

- User asks about BTQuant MCP status
- Need to verify BTQuant tools availability
- Checking trading infrastructure connectivity