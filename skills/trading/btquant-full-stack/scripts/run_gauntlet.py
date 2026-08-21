#!/usr/bin/env python3
"""
BTQuant Strategy Gauntlet — testet ALLE 11 verfügbaren Strategien, $100 Start, 35% Sizer.
BTC/USDT 1m, 01.05.2025 – 25.05.2026.

Usage:
    /usr/bin/python3 /home/alca/.hermes/skills/trading/btquant-full-stack/scripts/run_gauntlet.py
"""
import sys, os
sys.path.insert(0, "/home/alca/projects/PubBTQuant")
sys.path.insert(0, "/home/alca/projects/PubBTQuant/dependencies")
sys.path.insert(0, "/home/alca/projects/PubBTQuant/dependencies/backtrader")
sys.path.insert(0, "/home/alca/projects/PubBTQuant/dependencies/backtrader/feeds/mssql")
import signal as _signal
try:
    import backtrader as bt
except Exception:
    for k in list(sys.modules.keys()):
        if 'backtrader' in k: del sys.modules[k]
    sys.path = [p for p in sys.path if "/backtrader" not in p]
    sys.path.insert(0, "/home/alca/projects/PubBTQuant/dependencies/backtrader")
    sys.path.insert(0, "/home/alca/projects/PubBTQuant/dependencies/backtrader/feeds/mssql")
    import backtrader as bt
sys.modules['signal'] = _signal

from backtrader.feeds.pandafeed import PandasData
import ccxt, pandas as pd, time as _time

# Class Mapping
STRATS = [
    ("SMA_Cross_Simple", "SMA_Cross_Simple", {}),
    ("SuperTrend_Scalp", "SuperSTrend_Scalp", {"adx_period":13,"adxth":20,"st_fast":2,"st_fast_multiplier":3,"st_slow":6,"st_slow_multiplier":7,"take_profit":2,"trailing_stop_pct":0.4,"dca_deviation":1.5}),
    ("Vumanchu_A", "VuManchCipher_A", {"take_profit":3,"dca_deviation":4}),
    ("Vumanchu_B", "VuManchCipher_B", {"take_profit":3,"dca_deviation":4}),
    ("ST_RSX_ASI", "STrend_RSX_AccumulativeSwingIndex", {"take_profit":2,"trailing_stop_pct":0.5}),
    ("Aligator_supertrend", "AliG_STrend", {"take_profit":3}),
    ("QQE_Hullband_VolumeOsc", "QQE_Example", {"take_profit":3}),
    ("SineWeightZeroLagQQEVolMesaAdaptive", "FastSineWeightZeroLagQQEVolMesaAdaptive", {}),
    ("NearestNeighbors_RationalQuadraticKernel", "NRK", {"take_profit":3,"period":14}),
    ("SMA_Cross_MESAdaptive_Prime", "SMA_Cross_MESAdaptivePrime", {}),
    ("StagedConvergenceStrategy", "StagedConvergenceStrategy", {"take_profit":3}),
]

exchange = ccxt.binance()
since = exchange.parse8601("2026-05-01T00:00:00Z")
all_c = []
for i in range(35):
    chunk = exchange.fetch_ohlcv("BTC/USDT", "1m", since=since, limit=1000)
    if not chunk: break
    all_c.extend(chunk)
    since = chunk[-1][0] + 60000
    _time.sleep(0.25)

df = pd.DataFrame(all_c, columns=["timestamp","open","high","low","close","volume"])
df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
df.set_index("datetime", inplace=True)
df.sort_index(inplace=True)

results = []
for fname, cname, params in STRATS:
    mod = __import__(f"strategies.{fname}", fromlist=["_"])
    cls = getattr(mod, cname)
    p = {"percent_sizer": 0.35, "debug": False, "backtest": True}
    p.update(params)
    cerebro = bt.Cerebro()
    cerebro.addstrategy(cls, **p)
    cerebro.adddata(PandasData(dataname=df.copy()))
    cerebro.broker.setcash(100.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.run()
    end_val = cerebro.broker.getvalue()
    ret = (end_val / 100.0 - 1) * 100
    print(f"{'📈' if ret > 0 else '📉'} {fname:40s} ${end_val:>7.2f}  {ret:>+7.2f}%")
    results.append((fname, end_val, ret))

print("\n🏆 RANKING")
for i, (n, e, r) in enumerate(sorted(results, key=lambda x: -x[2]), 1):
    m = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
    print(f"  {i:2d}. {m} {n:40s} ${e:>7.2f}  {r:>+7.2f}%")
