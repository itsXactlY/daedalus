---
id: vwap-hidden-divergence-strategy
name: vwap-hidden-divergence-strategy
title: VWAP Hidden Divergence Swing Trading Strategy
description: TradingView Pine Script strategy detecting hidden VWAP divergences for swing long/short entries
author: alca
version: 1.0
tags: [trading, vwap, divergence, swing, pine-script]
---

# VWAP Hidden Divergence Swing Strategy

Builds a TradingView strategy from VWAP hidden divergences. Integrates Cheatcode ZERO and Cheatcode A concepts.

## Signal Logic

Hidden divergences are trend-continuation signals:

| Signal | Price Action | VWAP Action | Entry |
|--------|-------------|-------------|-------|
| H Bull | Higher Low (HL) | Lower Low (LL) | LONG |
| H Bear | Lower High (LH) | Higher High (HH) | SHORT |

### Hidden Divergence Explained

Hidden divergences occur during trending markets and signal continuation:

- **Hidden Bullish**: Price makes a higher low while VWAP makes a lower low. Indicates bulls are stronger than apparent.
- **Hidden Bearish**: Price makes a lower high while VWAP makes a higher high. Indicates bears are stronger than apparent.

## Key Components

### VWAP Oscillator
- Uses Volume Weighted Average Price (VWAP) as the divergence oscillator
- Optional EMA smoothing for cleaner signals

### Pivot Detection
- `ta.pivothigh()` and `ta.pivotlow()` on VWAP for oscillator pivots
- Separate price pivots (wicks or bodies) for price action comparison
- Configurable lookback range (min/max bars between pivots)

### Risk Management
- ATR-based stop loss (2x ATR default)
- Reward-to-risk ratio (2.5x default)
- Optional trailing stop

## Files Created

- `/home/alca/projects/vwap-divergence-swing/strategy_vwap_hidden_divergence_strategy.pine` - Main strategy file

## Usage

Copy the `.pine` file into TradingView Pine Editor. Default settings work on 1W timeframe as shown in the reference chart.

## Parameters

```pinescript
lookback_right = 3    // Pivot Lookback Right
lookback_left = 5     // Pivot Lookback Left  
max_lookback = 60     // Max bars between pivots
min_lookback = 5      // Min bars between pivots
vwap_smooth = 3       // EMA smoothing period
atr_sl_mult = 2.0     // Stop loss ATR multiplier
rr_ratio = 2.5        // Take profit reward:risk
```

## Implementation Notes

1. Pivot logic uses `ta.valuewhen()` to compare current vs. previous pivot values
2. Hidden bullish: oscillator pivot low is LOWER than previous, price pivot low is HIGHER
3. Hidden bearish: oscillator pivot high is HIGHER than previous, price pivot high is LOWER
4. Signals trigger on `plotshape()` for visual confirmation and `strategy.entry()` for execution