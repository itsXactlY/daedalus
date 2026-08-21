# MCP Adapter Architecture — BTQuant

Created: 2026-05-25
Location: `/home/alca/projects/PubBTQuant/mcp-adapter/`
Port: 8910
Tools: 33

## Transport

HTTP+SSE mode (default):
```bash
python3 /home/alca/projects/PubBTQuant/mcp-adapter/server.py --port 8910
# → http://0.0.0.0:8910/mcp   (JSON-RPC POST)
# → http://0.0.0.0:8910/sse   (SSE endpoint)
# → http://0.0.0.0:8910/health (status + tool count)
# → http://0.0.0.0:8910/tools  (tool manifest)
```

Stdio mode (for Hermes plugin transport: stdio):
```bash
python3 /home/alca/projects/PubBTQuant/mcp-adapter/server.py --stdio
```

## Architecture

The server uses a flat module structure — no package name dependency:

```
mcp-adapter/
├── server.py          # Starlette ASGI app, MCP protocol handlers
├── registry.py        # Shared TOOLS dict + register_tool decorator
├── tools/             # Tool modules, each imports from registry
│   ├── project.py     # 5 tools
│   ├── build.py       # 4 tools  
│   ├── test.py        # 3 tools
│   ├── backtest.py    # 4 tools
│   ├── agency.py      # 6 tools
│   ├── neural.py      # 4 tools
│   ├── data.py        # 7 tools
│   └── exchange.py    # 2 tools
├── demo_backtest.py   # standalone SMA crossover demo
└── scripts/
    ├── run.sh         # ./scripts/run.sh [--port 8910]
    └── install.sh     # pip install deps
```

### Import Chain

```
server.py → from registry import TOOLS, register_tool
server.py → _load_tools() → __import__("tools.project") 
tools/project.py → from registry import register_tool → @register_tool decorator fires → TOOLS dict populated
```

Key insight: `_load_tools()` must run BEFORE uvicorn takes over (at module import time, not just in `main()`). This is why the call sits at module level, not in `main()`.

## Tool Registration Pattern

Each tool module follows this exact pattern:

```python
from registry import register_tool

@register_tool(
    "tool_name",
    "Description shown to AI agent.",
    {"type": "object", "properties": {"param": ...}, "required": []},
)
def my_tool(args: dict) -> dict:
    # do work
    return {"result": ...}
```

- Tool name: lowercase_with_underscores, 40 chars max
- Description: 1 sentence, 70 chars max in manifest
- Input schema: standard JSON Schema
- Return: dict (will be JSON-serialized with `default=str`)

## Adding New Tools

1. Create `tools/your_module.py` with the pattern above
2. Add module name to `mods` list in `server.py:_load_tools()`
3. Restart server

## Known Issues

- Subprocess tools (backtest, test, build) run system Python3. If missing pip packages cause failures, install with `pip install --break-system-packages <pkg>`
- Backtest tool uses BTQuant's internal `get_crypto_data()` which has ~7 optional deps. For reliable standalone backtests, use `demo_backtest.py` (pure pip backtrader + ccxt)
- MCP client plugin may show "not connected" in Hermes session even though HTTP calls to port 8910 work fine — session-init issue, not server problem. Direct HTTP calls via execute_code are a reliable fallback.

## Hermes Config Entry

```yaml
  btquant:
    description: "BTQuant HFT framework — 33 tools: build, test, backtest, neural, agency, data, exchange"
    enabled: true
    transport: http
    url: http://127.0.0.1:8910/mcp
```

## 33 Tools Quick Reference

| Tool | Category | Returns |
|------|----------|---------|
| project_info | project | root, branch, size, file counts, dirs |
| project_git_status | project | branch, dirty files, log |
| project_cmakelists | project | all CMakeLists.txt paths |
| project_file_tree | project | directory tree at depth |
| build_list_targets | build | 3 projects + their make targets |
| build_run | build | cmake + make output |
| build_clean_all | build | removed build dirs |
| build_check_compiler | build | g++/gcc/clang++/cmake/make versions |
| test_list | test | all 10 available suites |
| test_run | test | suite output + exit code |
| test_lint | test | flake8 results |
| backtest_list_strategies | backtest | 17 strategies with descriptions |
| backtest_list_indicators | backtest | indicator catalogue |
| backtest_run_simple | backtest | SMA/MACD_ADX backtest on BTC |
| backtest_strategy_source | backtest | full source code of a strategy |
| agency_status | agency | config, process, log, DB |
| agency_start | agency | background process start |
| agency_stop | agency | kill agency process |
| agency_logs | agency | last N log lines |
| agency_strategies | agency | generated strategy files |
| neural_status | neural | pipeline files, config, models |
| neural_run_feature_selection | neural | feature selection output |
| neural_run_walk_forward | neural | walk-forward output |
| neural_pipeline_config | neural | full config.yaml values |
| data_hotspine_status | data | SHM files, libhotspine_reader.so |
| data_hotspine_run_test | data | basic/comprehensive/core/integration |
| data_mssql_status | data | DB connection, table count |
| data_mock_producer | data | mock market data generator |
| data_ccapi_process | data | is market_data_collector running? |
| data_detector_process | data | is manipulation_monitor running? |
| data_dashboard_process | data | is quantstats dashboard running? |
| exchange_status | exchange | stores, brokers, feeds, API keys |
| exchange_not_connected | exchange | missing perp DEX list with reasons |