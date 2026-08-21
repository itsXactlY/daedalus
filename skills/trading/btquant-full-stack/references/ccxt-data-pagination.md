# CCXT Datenabruf — Pagination & Benchmarking

## Das Problem

`exchange.fetch_ohlcv(symbol, timeframe, since, limit=N)` ignoriert `limit` wenn `limit > 1000`. Binance gibt maximal 1000 Candles pro Call zurück. Für Backtests über Monate/Jahre auf 1m sind 1000 Candles (~16h) nutzlos.

## Lösung: Pagination

```python
import time as _time
exchange = ccxt.binance({"enableRateLimit": True})
since = exchange.parse8601("2025-01-01T00:00:00Z")
all_candles = []

for i in range(800):  # bis zu 800.000 Candles
    chunk = exchange.fetch_ohlcv("BTC/USDT", "1m", since=since, limit=1000)
    if not chunk:
        break
    all_candles.extend(chunk)
    since = chunk[-1][0] + 60000  # nächste Minute
    _time.sleep(0.22)  # Rate Limit: ~4.5 calls/sec
```

## Performance

| Daten | Pages | Delay | Gesamtzeit |
|-------|-------|-------|------------|
| 35.000 Candles (25d 1m) | 35 | 0.25s | ~9s |
| 734.000 Candles (17mo 1m) | 734 | 0.22s | ~160s |
| 100.000 Candles (70d 1m) | 100 | 0.3s | ~30s |

## BTQuant Cache-System

BTQuant's `PolarsDataLoader` in `utils/backtest.py` cached geholte Daten als Parquet-Dateien:

```python
cache_dir = "/home/alca/projects/PubBTQuant/.btq_cache/"
# Dateiname: {Symbol}_{Interval}_{Collateral}_{md5hash}.parquet
# Hash basiert auf: f"{symbol}|{interval}|{collateral}|{ranges_str}"
```

Manuelles Befüllen:
```python
# Column-Namen müssen exakt sein:
# TimestampStart (Mikrosekunden!), Open, High, Low, Close, Volume
```
