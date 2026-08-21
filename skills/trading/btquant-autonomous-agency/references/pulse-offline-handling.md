# Pulse Verification When HotSpine Offline

## Observed Behavior (2026-06-11)

When `/dev/shm/BTQ` is missing, the following applies:

### Pulse HTTP Endpoint
- Root endpoint `http://127.0.0.1:8770/` returns `{"detail":"Not Found"}`
- MCP tools still work via `mcp-pulse_pulse_*` functions
- Use MCP tools directly rather than raw HTTP calls

### Cache Handling
- Cache file `.btq_cache/BTC_1m_USDT_2ee8fdb96a31.parquet` exists
- File format: Apache Parquet (PAR1 header)
- No Python parquet readers installed on system (pandas, pyarrow, fastparquet all missing)
- Cache age: Use `stat` command to check modification timestamp
- Cache stale warning: Data older than 7 days should be treated as reference-only

### Status Check Pattern
```bash
# Check SHM existence
ls -la /dev/shm/BTQ 2>&1 | grep -q "cannot access" && echo "OFFLINE" || echo "LIVE"

# Check cache staleness
find .btq_cache -name "*.parquet" -mtime +7 -exec stat {} \;
```

### MCP Tool Output Parsing (Double-Escaped JSON)
When MCP pulse tools return large outputs, they're often written to temp files as double-escaped JSON:
```python
import json
# Read and decode double-escaped format
with open(temp_file, 'r') as f:
    raw = f.read()
data = json.loads(raw)           # First decode: {"result": "{...}"}
parsed = json.loads(data['result'])  # Second decode: actual content
candidates = parsed.get('body', {}).get('ranked_candidates', [])
```

### Reporting Template for Offline State
When HotSpine is offline but pulse signals are detected:
1. Flag SHM offline in infrastructure status
2. Note cache staleness with modification date
3. Report signals as "valid but execution blocked"
4. Provide restart commands for `market_data_collector`