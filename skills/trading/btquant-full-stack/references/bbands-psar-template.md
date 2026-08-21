---
name: bbands-psar-template
version: "1.0"
description: "BBands + PSAR strategy template for BTQuant BaseStrategy - canonical pattern after user correction to use BaseStrategy-native instead of Jackrabbit harness"
author: Hermes
---

# BBands + PSAR Strategy Template

User correction (2026-06-11): "that was the WHOLE GOAL, to use OBVIOUSLY whole basestrategy!"

This template provides the correct BaseStrategy-native pattern. NEVER default to Jackrabbit harness.

## Canonical Pattern (32 lines)

```python
from .base import BaseStrategy, bt

class BBands_PSAR(BaseStrategy):
    params = (('period', 20), ('bb_mult', 2.0), ('psar_af', 0.02), ('psar_afmax', 0.2),)

    def __init__(self):
        super().__init__()
        self.bb = bt.indicators.BollingerBands(self.data.close, period=self.p.period, devfactor=self.p.bb_mult)
        self.psar = bt.indicators.ParabolicSAR(af=self.p.psar_af, afmax=self.p.psar_afmax)

    def buy_or_short_condition(self):
        # LONG entry: close ≤ lower_band AND PSAR < close (bullish trend confirming)
        if self.data.close[0] <= self.bb.bot[0] and self.psar.psar[0] < self.data.close[0]:
            self.create_order(action='BUY')
            return True
        # SHORT entry: close ≥ upper_band AND PSAR > close (bearish trend confirming)
        if self.data.close[0] >= self.bb.top[0] and self.psar.psar[0] > self.data.close[0]:
            self.create_order(action='SELL')
            return True
        return False

    def sell_or_cover_condition(self):
        if not self.in_position:
            return False
        # Exit LONG: close ≥ upper_band OR PSAR ≥ close (bearish reversal)
        if self.buy_executed and (self.data.close[0] >= self.bb.top[0] or self.psar.psar[0] >= self.data.close[0]):
            self.create_order(action='SELL')
            return True
        # Exit SHORT: close ≤ lower_band OR PSAR ≤ close (bullish reversal)
        if self.short_executed and (self.data.close[0] <= self.bb.bot[0] or self.psar.psar[0] <= self.data.close[0]):
            self.create_order(action='BUY')
            return True
        return False
```

## Indicator Access Patterns

| Indicator | Line Access |
|-----------|-------------|
| BollingerBands | `.top[0]`, `.bot[0]`, `.mid[0]` |
| ParabolicSAR | `.psar[0]` |
| SMA | `.sma[0]` |
| RSI | `.rsi[0]` |