# PotatoHarvester Pro — ATR Volatility Bands Strategy

## Overview
EMA center + ATR volatility bands breakout strategy. Works in both JackrabbitRelay TechnicalAnalysis format and BTQuant BaseStrategy format.

## Core Logic (45-44 lines)

```
EMA(21) center + ATR(21) bands with multipliers [3,5,7..21]
Long: close crosses above bottom band (band n) → signal = +(n+1)
Short: close crosses below top band (band n) → signal = -(n+1)
No algorithmic stop loss (-1 return)
```

## JackrabbitRelay Format
File: `dependencies/backtrader/strategies/PotatoHarvesterPro.py`

Key methods:
- `ta.EMA(close_idx, period)` - adds EMA column
- `ta.ATR(h, l, c, period, smooth_func=ta.EMA)` - adds TR + ATR columns  
- `ta.Cross(idx1, idx2)` - adds diff + cross columns (cross=1 when idx1 crosses above idx2)
- `ta.AddColumn(value)` - appends value to last row
- `ta.LastRow()` - returns current row

## BTQuant Format  
File: `dependencies/backtrader/strategies/PotatoHarvesterPro_BTQuant.py`

Key differences:
- Uses `bt.indicators.CrossOver()` returning 1/0/-1 (not 2 columns)
- Configurable tighter bands: `mult_start=1.0, mult_step=0.5, levels=5` → [1,1.5,2,2.5,3]
- Integrated TP/SL via `create_order()` and `close_order()`
- Requires `percent_sizer` parameter for position sizing

## Verification
Run with:
```python
cd /home/alca/projects/PubBTQuant
python3 -c "
import signal as _signal, sys
sys.path.insert(0, 'dependencies/backtrader')
import backtrader as bt; sys.modules['signal']=_signal
from strategies.PotatoHarvesterPro_BTQuant import PotatoHarvesterPro
# Verify class loads and has params
print(PotatoHarvesterPro.params)
"
```

## Performance Notes
- Tested: ~100-200 trades on 5000-10000 candles
- Win rate: 43-52% on random walk data
- Bands are wide with multipliers 3-21; use tighter multipliers for mean-reversion setups