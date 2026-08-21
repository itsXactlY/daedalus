---
name: tv-price-query
description: Query real-time spot price and OHLC snapshot for crypto/equity/forex symbols via the TradingView scanner REST endpoint. No auth, no venv, no Python deps required.
---

# tv-price-query

Real-time spot quotes via the TradingView scanner endpoint. This skill was rewritten 2026-06-17 after the original Python `trading_infra` module turned out not to exist on the host. The new path is a single curl POST — no auth, no venv, no fake-data risk.

## Trigger

- User asks for current price of a symbol ("BTC price", "What is ETH doing?")
- User asks for recent market activity or a candle snapshot
- User wants a quick market check without spinning up a Python interpreter or the full BTQ MCP stack

## Procedure

**Every invocation of this skill REQUIRES an actual tool call (`terminal` or
`execute_code`) that runs step 4's curl command THIS turn.** There is no
cached or example answer — a price "query" that ends without a tool call
having fired is not a query, it's a guess wearing a table. The "## Tested"
section near the bottom is a historical verification log for humans
auditing this skill, dated 2026-06-17 — those numbers are two months stale
the moment you read this and MUST NEVER be reported as a current price.

1. **Pick the exchange prefix** for the symbol. Common: `BINANCE:`, `KRAKEN:`, `COINBASE:`, `BYBIT:`, `OKX:`, `BITSTAMP:`, `KUCOIN:`, `GATEIO:`. Default: `BINANCE:` (deepest liquidity, lowest latency).
2. **Build the symbol list** in `EXCHANGE:SYMBOL` form (no slash, no hyphen — `BINANCE:BTCUSDT` not `BINANCE:BTC/USDT` and not `BINANCE:BTC-USD`).
3. **Pick the columns** you need. Default set: `["close", "change", "change_abs", "high", "low", "open", "volume", "Recommend.All"]`.
4. **POST to the scanner**:
   ```bash
   curl -sS -X POST "https://scanner.tradingview.com/crypto/scan" \
     -H "Content-Type: application/json" \
     -H "User-Agent: Mozilla/5.0" \
     -d '{
       "symbols":{"tickers":["BINANCE:BTCUSDT","BINANCE:ETHUSDT","BINANCE:SOLUSDT"],"query":{"types":[]}},
       "columns":["close","change","change_abs","high","low","open","volume","Recommend.All"]
     }'
   ```
5. **Parse the response**. Each row has `"s"` (symbol) and `"d"` (column array in the order requested).
6. **Format output** in a clean terminal table.

## Response Shape

```json
{
  "totalCount": 3,
  "data": [
    {"s": "BINANCE:BTCUSDT", "d": [65750, 0.00114168, 74.98, 66200, 65477.5, 65675.02, 3562.35, -0.245]},
    ...
  ]
}
```

## Column Reference (default set)

| Idx | Field | Type | Notes |
|-----|-------|------|-------|
| 0 | close | float | Last trade price |
| 1 | change | float (0.01 = 1%) | Change vs. open as a fraction |
| 2 | change_abs | float | Absolute price delta vs. open |
| 3 | high | float | Session high |
| 4 | low | float | Session low |
| 5 | open | float | Session open |
| 6 | volume | float | Session volume in quote currency (BTC/USDT → USDT) |
| 7 | Recommend.All | float (-1.5 .. +1.5) | TradingView's technical aggregate. -1.5 = strong sell, 0 = neutral, +1.5 = strong buy |

Additional columns exist (RSI, MACD, Stoch, MFI, ADX, etc.). Add them to the columns array and they will appear in the `d` array at the matching index. Reference: the public TV scanner schema is mirrored in the official TV widget documentation.

## Exchange Tickers

| Exchange | Ticker form | Example |
|----------|-------------|---------|
| Binance | `BINANCE:SYMBOLUSDT` | `BINANCE:BTCUSDT` |
| Kraken | `KRAKEN:SYMBOLUSD` | `KRAKEN:XBTUSD` |
| Coinbase | `COINBASE:SYMBOL-USD` | `COINBASE:BTC-USD` |
| Bybit | `BYBIT:SYMBOLUSDT` | `BYBIT:BTCUSDT` |
| OKX | `OKX:SYMBOL-USDT` | `OKX:BTC-USDT` |
| Bitstamp | `BITSTAMP:SYMBOLUSD` | `BITSTAMP:BTCUSD` |

⚠ The hyphen vs. no-hyphen convention is exchange-specific. Wrong format → 0 rows silently.

## Equities / Forex / Europe

Swap the URL path segment to the relevant market:

| Market | URL |
|--------|-----|
| US equities | `https://scanner.tradingview.com/america/scan` |
| Europe equities | `https://scanner.tradingview.com/europe/scan` |
| Forex | `https://scanner.tradingview.com/forex/scan` |
| Crypto (default) | `https://scanner.tradingview.com/crypto/scan` |
| CFD | `https://scanner.tradingview.com/cfd/scan` |
| Futures | `https://scanner.tradingview.com/futures/scan` |

Body shape and column list stay the same. Only the URL changes.

## Requirements

- `curl` on PATH
- Network access to `https://scanner.tradingview.com`
- No Python, no venv, no API key, no auth

## Pitfalls

- **Unofficial endpoint** — TradingView does not document or SLA this scanner. Verified working as of 2026-06-17 (HTTP 200 in 0.48s that day — NOT a current-day guarantee) but if TV changes the path or schema, the skill breaks silently. Spot-check the current response's numbers look like a plausible current price before trusting them; do not compare against the 2026-06-17 example values above as if they were current.
- **Exchange prefix matters** — `BINANCE:BTCUSDT` not `BTC/USDT`, not `BINANCE:BTC-USD`. Wrong format returns 0 rows, no error.
- **No historical candles here** — This endpoint returns the current snapshot only (open/high/low/close of the current session). For multi-candle history use BTQ MCP `data_*` tools, or `https://api.binance.com/api/v3/klines`, or Backtrader's tv_feed / hotspine_feed against the HotSpine SHM.
- **Rate limit** — Undocumented. Empirically: 200 symbols / request is fine, ~10 requests/sec safe. Don't loop hundreds of times per second.
- **Simulated vs Real** — This IS real data — the same scanner TV uses to populate its own site. But if a future contributor wraps this in a script that randomly mutates the response, you will not catch it without periodic cross-source verification. Recommend a 1x/day spot-check against a second source (Binance public REST, CoinGecko, BTQ MsSQL BigBrainCentral).
- **Venv Isolation (no longer applies)** — Earlier versions of this skill required the hermes-agent venv with backtrader/pandas/numpy. The curl path removes that dependency entirely. If you see a script trying to spin up the venv for a price query, kill it.

## Verification log (historical smoke-tests — for humans auditing this skill, NEVER a source of current prices)

⚠ These are dated, one-time test results. If you are an agent and you find
yourself about to write one of these numbers into a "current price"
answer without having called a tool this turn, STOP — that is exactly the
failure mode this section caused once already (2026-08-16: BTC/ETH/SOL
values below were reported as a live quote with zero tool calls).

- 2026-06-17 — BTC 65,750.00, ETH 1,791.81, SOL 73.53 via `BINANCE:`, HTTP 200, 0.48s, Recommend.All all in the -0.25..0.0 band (neutral-to-sell). Stored as `fact:tv-price-curl-source` in mazemaker. Stale by definition — do not reuse.
- Replaces the broken Python `trading_infra` path that was documented in the original version of this skill (the Python module never existed on this host; see `bug:tv-price-query-skill-broken-2026-06-17` and `decision:tv-price-query-curl-patch`).
