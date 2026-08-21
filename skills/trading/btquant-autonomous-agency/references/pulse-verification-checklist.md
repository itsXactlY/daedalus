# Pulse Feed Verification Checklist (2026-06-11)

## Quick Verification Commands

```bash
# 1. Pulse HTTP health check
curl -s http://127.0.0.1:8770/ | jq -r '.status'

# 2. Pulse search endpoint test
curl -s -X POST http://127.0.0.1:8770/search \
  -H 'Content-Type: application/json' \
  -d '{"topic": "financial markets", "n": 3, "llm_filter": false}' | jq '.ranked_candidates[0]'

# 3. Discord delivery job status
hermes cron list | grep 433006b417a1
# Expected: job_id=433006b417a1 enabled=true schedule="0 * * * *"

# 4. Format script test
python3 ~/.hermes/scripts/btquant-macro-discord.py | head -10
```

## Verification Results (Session Id: 686957)

| Check | Status | Notes |
|-------|--------|-------|
| Pulse health | ✅ OK | HTTP 200, ts: 1781150507 |
| Pulse search | ✅ OK | Returns ranked_candidates array |
| Discord job | ✅ Active | Hourly schedule confirmed |
| HotSpine SHM | ❌ Offline | /dev/shm/BTQ missing |
| Market collector | ❌ Offline | No process running |
| Cache | ✅ Exists | .btq_cache/ has stale parquet |

## Troubleshooting When HotSpine Offline

When pulse returns signals but `/dev/shm/BTQ` missing:

1. **Check cache staleness**: `ls -la .btq_cache/*.parquet` timestamps
2. **Signal validity**: Pulse trends still actionable for market awareness, but BTQ component signals (Binance HotSpine, spread_arbitrage) require live feed
3. **Restart collector** (if needed): Build `market_data_collector` from ccapi project and start
4. **Alert wording**: "HotSpine SHM offline — live signals from cache only"