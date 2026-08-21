# BTQuant Hourly Macro Pulse Feed Signals

## Signal Format
Reddit-sourced signals arrive in this format:
```
**{rank}. {title}** `reddit` (score)
   Assets: {asset_category} | Vol: {volume}
   BTQ: {component}
```

## Detection Pipeline
1. **Pulse Source**: Reddit posts filtered through C++ manipulation detectors
2. **Score**: Relevance score (0.02 = low-moderate relevance)
3. **Assets**: Categories - crypto market-wide, monitoring
4. **Volume**: neutral, MEDIUM-HIGH
5. **BTQ Component**: Where signal applies
   - `watchlist_panel` - general market monitoring
   - `Binance HotSpine /dev/shm/BTQ` - spread_arbitrage detector specifically

## Current Arbitrage Detector Status
- **SpreadArbitrageDetector** configured with:
  - min_profit_bps: 10 (configurable, default 10)
  - maker_fee_bps: 10
  - taker_fee_bps: 20
- **Data requirement**: Best bid/ask across 2+ exchanges (binance, coinbase, kraken, okx, bybit, gate)
- **Trigger**: `arbitrage.set_min_profit_bps()` threshold crossed

## Activation Requirements
HotSpine shared memory must be active at `/dev/shm/BTQ` for live signals. Check with:
```bash
ls -la /dev/shm/BTQ  # Should show shared memory segments
ps aux | grep market_data_collector  # Should show running collector
```

## Pulse HTTP Endpoint Details
- **URL:** `http://127.0.0.1:8770/search`
- **Request:** `{"topic": "financial markets trending macro geopolitics crypto equities bonds", "n": 10, "llm_filter": false}`
- **Response:** Contains `ranked_candidates` array with `final_score`, `title`, `source`, `url`, `snippet`
- **Score Thresholds:** ~0.02 = low relevance, ~0.3 = moderate, >= 0.5 = action-worthy
- **Freshness Decay:** Scores penalize older content (freshness field 0-96 days)

## Discord Delivery Configuration
- **Job ID:** `433006b417a1` (enabled, runs hourly at minute 0)
- **Channel:** `1497265474981855253`
- **Script:** `btquant-macro-discord.py` formats pulse output for Discord posting

## HotSpine Shared Memory Offline Status
**Critical:** `/dev/shm/BTQ` does NOT exist - HotSpine data feed is offline.
- Check: `ls -la /dev/shm/BTQ` (currently returns MISSING)
- Impact: Cannot receive live Binance orderbook data, spread arbitrage detector inactive
- Signal mapping still works but references inactive components
- Required for: `Binance HotSpine`, `spread_arbitrage detector`, `whale_frontrun detector`, `liquidity_imbalance detector`

## When HotSpine Offline
If `/dev/shm/BTQ` missing:
1. Pulse signals still valid for trend awareness
2. Skip all BTQ component references in analysis  
3. Use alternative: check `.btq_cache/*.parquet` for last-known market data
4. Alert: "HotSpine SHM offline - live signals unavailable"

## Score Interpretation Patterns (2026-06-11)

### Score Ranges Observed
- **0.01-0.02:** Low relevance - informational only, not action-worthy
- **0.03-0.05:** Moderate relevance - worth noting for context
- **>= 0.3:** Action-worthy - requires immediate attention
- **>= 0.5:** High priority - execute trading logic

### This Run Analysis
All 40 candidates scored 0.01-0.02 (low relevance). No action-worthy opportunities found. Key observations:
- China bond market post hit 4.8M views before deletion (highest attention metric)
- Polymarket prediction "Will X start a crypto trading platform" scored 0.016 but was stale (2023-12-31)
- Tickertick sources showed ticker-tagged articles (MSFT/TSLA/AAPL) but low direct crypto relevance

### Classification for Cron Reports
- **Signal Category:** "trend-aware" when all scores < 0.03
- **Signal Category:** "monitor" when scores 0.03-0.2 and HotSpine offline
- **Signal Category:** "execute" when scores >= 0.3 AND HotSpine live

## Notable Events Flagged by Pulse
- High-impact Reddit posts (viral content) may indicate regime shifts
- Posts deleted by mods still get scored before deletion
- FOMC-related signals require attention for macro volatility plays
- Polymarket stale dates (2023-2024) should be filtered out for real-time trading signals