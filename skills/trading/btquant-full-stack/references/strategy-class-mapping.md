# BTQuant Strategy Class Mapping

Dateiname != Klassenname bei den meisten BTQuant-Strategien.
Nur 3 von 17 passen. Hier die vollständige Tabelle für korrekte Imports.

| Dateiname (.py) | Tatsächliche Klasse | Match? |
|-----------------|-------------------|--------|
| `Aligator_supertrend` | `AliG_STrend` | ❌ |
| `MACD_ADX` | `Enhanced_MACD_ADX4` | ❌ |
| `NearestNeighbors_RationalQuadraticKernel` | `NRK` | ❌ |
| `OrderChain` | `Order_Chain_Kioseff_Trading` | ❌ |
| `Order_Chain_Kioseff_Trading` | `Order_Chain_Kioseff_Trading` | ✅ |
| `QQE_Hullband_VolumeOsc` | `QQE_Example` | ❌ |
| `SMA_Cross_MESAdaptive_Prime` | `SMA_Cross_MESAdaptivePrime` | ❌ |
| `SMA_Cross_Simple` | `SMA_Cross_Simple` | ✅ |
| `ST_RSX_ASI` | `STrend_RSX_AccumulativeSwingIndex` | ❌ |
| `SineWeightZeroLagQQEVolMesaAdaptive` | `FastSineWeightZeroLagQQEVolMesaAdaptive` | ❌ |
| `StagedConvergenceStrategy` | `StagedConvergenceStrategy` | ✅ |
| `SuperTrend_Scalp` | `SuperSTrend_Scalp` | ❌ |
| `Vumanchu_A` | `VuManchCipher_A` | ❌ |
| `Vumanchu_B` | `VuManchCipher_B` | ❌ |
| `jrr_orders` | (keine BaseStrategy) | ❌ |
| `pancakeswap_dca_marketmaker` | `Pancakeswap_dca_mm` | ❌ |
| `pancakeswap_orders` | (keine BaseStrategy) | ❌ |

## Korrekter Import

```python
# FALSCH — ClassNotFound:
from strategies.SuperTrend_Scalp import SuperTrend_Scalp  # ❌

# RICHTIG:
from strategies.SuperTrend_Scalp import SuperSTrend_Scalp  # ✅
```

## Erkennungsmethode

```python
with open(f"dependencies/backtrader/strategies/{filename}.py") as f:
    for line in f:
        if line.strip().startswith("class ") and "BaseStrategy" in line:
            actual = line.split("(")[0].replace("class ","").strip()
            break
```
