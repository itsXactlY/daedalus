# BTQuant Known Issues & Fixes

## 1. fast_mssql C++ module incompatible with Python 3.14

The compiled `.so` files only work on Python 3.12/3.13. Python 3.14 needs the pyodbc shim.

**Fix:** Shim at `dependencies/backtrader/feeds/mssql/fast_mssql.py`. `dontcommit.py` is already patched.

## 2. Strategy class names ≠ filenames

- `SuperTrend_Scalp.py` → `SuperSTrend_Scalp`
- `Vumanchu_A.py` → `VuManchCipher_A`
- `Vumanchu_B.py` → `VuManchCipher_B`
- `Aligator_supertrend.py` → `AliG_STrend`
- `ST_RSX_ASI.py` → `STrend_RSX_AccumulativeSwingIndex`
- `QQE_Hullband_VolumeOsc.py` → `QQE_Example`
- `SineWeightZeroLagQQEVolMesaAdaptive.py` → `FastSineWeightZeroLagQQEVolMesaAdaptive`
- `NearestNeighbors_RationalQuadraticKernel.py` → `NRK`
- `SMA_Cross_MESAdaptive_Prime.py` → `SMA_Cross_MESAdaptivePrime`
- `MACD_ADX.py` → `Enhanced_MACD_ADX4`
- `OrderChain.py` → `Order_Chain_Kioseff_Trading`
- ✅ `SMA_Cross_Simple.py` → `SMA_Cross_Simple`
- ✅ `StagedConvergenceStrategy.py` → `StagedConvergenceStrategy`

## 3. Strategy init_cash override

Strategies have own `init_cash` param (default $1,000). Pass it to the constructor.

## 4. Circular import on backtrader.utils

BTQuant's `signal.py` shadows stdlib `signal`. Fix: save stdlib signal before importing.

## 5. Best SuperTrend_Scalp parameters (May 2025–May 2026 BTC/USDT)

- ADX≥20 · 50% Sizer · TP 2.0% · Trail 0.3% → +1.09% (25 days)
- Over 17 months: 11 trades, 90.91% WR, $282 P&L (+28.22% on $1K), but capital dropped -12.33% due to trail friction
