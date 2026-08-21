# Sprint patterns — round 12 (sprints #229-#234)

**Date:** 2026-06-20
**Scope:** 6 sprints, all derived-stats primitives, 0 widgets added.

## What was built

Six sprints, all the journal-wide → per-symbol → per-tag → bulk
mirror pattern, three new derived struct families. Final state:
234 commits, 919 ✓ across 219 cases, 0 failures, 32 widgets
(unchanged), 296+ TradeJournal methods, 46+ templated
`build*<Pred/Iter>()` helpers.

| #   | Method(s)                            | Type                  | Struct              |
|-----|--------------------------------------|-----------------------|---------------------|
| 229 | edgeScoreBySymbol / ByTag            | per-segment primitive | EdgeScore           |
| 230 | allSegmentEdgeScore / ByTag          | bulk mirror           | EdgeScore           |
| 231 | timeBetweenFillsBySymbol / ByTag     | per-segment primitive | TimeBetweenFills    |
| 232 | allSegmentTimeBetweenFills / ByTag   | bulk mirror           | TimeBetweenFills    |
| 233 | volatilityRatioBySymbol / ByTag      | per-segment primitive | VolatilityRatio     |
| 234 | allSegmentVolatilityRatio / ByTag    | bulk mirror           | VolatilityRatio     |

## Composite EdgeScore formula

```cpp
double prod = max(W, 0) * max(R, 0) * max(E, 0) * max(K, 0);
double edge = pow(prod, 0.25);     // geometric mean
edge = edge / (edge + 1.0);         // sigmoid-style compress to 0..1
```

Combines four edge metrics (winRate, payoff, expectancy, kelly)
into a single 0..1 score. Geometric mean penalises any zero
component more harshly than arithmetic mean, which is what you
want — a segment with K=0 (negative Kelly) is dangerous even if
E is positive. The `x / (x+1)` compress keeps the score bounded
without hard-capping the underlying magnitudes.

Useful for the "all segments ranked by overall edge" panel —
one number per segment, sortable, comparable across symbols.

**DO NOT** use the raw `prod` directly — it can be huge (e.g.
W=0.6 * R=2 * E=20 * K=0.4 = 9.6) and isn't bounded. Always
compress.

## TimeBetweenFills semantics

`timeBetweenFillsBySymbol(symbol)` returns:
- `gapCount` — number of gaps (fills.size() - 1)
- `meanSec` — average gap in seconds
- `minSec` / `maxSec` — extremes

**CRITICAL pitfall (round 12 caught it):** you MUST sort the
timestamps before computing gaps. Fills arrive in append-order
but the journal can be loaded from JSONL where ordering is
NOT guaranteed. The previous `tradingFrequency` style methods
assumed sorted; this one explicitly sorts:

```cpp
std::sort(stamps.begin(), stamps.end());
```

The bug pattern: assuming `loadAll()` returns sorted timestamps.
It doesn't. Always sort before gap-difference math.

## VolatilityRatio formula

```cpp
ratio = dailyStddev / avgTradeSize
```

Combines two existing per-segment metrics: `DailyVolSeg.stddevDaily`
and `TradeSizeStatsSeg.meanSize`. The ratio is dimensionless —
"how many avg-trade-sizes of daily variation do I have?". >1.0
means daily stddev is bigger than a typical trade; <1.0 means
daily returns are smoother than trade sizes.

Useful for risk-sizing: a high ratio (e.g. 3.0) means the
trader's daily P&L varies a lot relative to typical trade size,
so position sizing should be more conservative. A low ratio
(0.5) means daily P&L is stable — they can size up.

**Pitfall (round 12):** `ratio = 0` when `avgTradeSize` is 0
(no fills), so the `if (avgTradeSize > 1e-9)` guard is
mandatory. Otherwise division by zero → NaN → garbage downstream.

## PICK+SHIP discipline — held across mid-chain WEITER!

The user fired `FRAG NICHT IMMER SO BEHINDERT: WEITER!` at
#225, #228, #230, #232, #234. Each time, the chain continued
without a mid-chain summary. The natural-next-step heuristic
from the SKILL.md PICK+SHIP rule kept firing correctly:

- After #228 (per-segment DD depth pct) → #229 was the
  edge-score composite (the "natural completion" of the
  edge-metric family alongside Kelly and R).
- After #229 → #230 was the all-segment bulk mirror.
- After #230 → #231 was a fresh primitive family
  (time-between-fills), not a mirror — the user typed WEITER
  before mirror #230 was done; we went mirror first, then
  primitive. The order doesn't matter as long as both happen
  in the chain.
- After #232 → #233 was a new primitive (vol-ratio), then
  #234 mirror.

The heuristic "the shape of unfinished work IS the roadmap"
held: every chain-end was either a per-segment primitive
awaiting its bulk mirror, or a bulk mirror awaiting a
per-segment primitive. Both directions are valid next steps.

## Cumulative stats update (through sprint #234)

- **234 commits** on `0.0.2` (from 228 at end of round 11)
- **32 widgets** (unchanged from round 7)
- **919 ✓ across 219 cases** (from 913 ✓ across 213 at end of round 11)
- TradeJournal surface: **296+ methods** (from 284+ at end of round 11)
- **46+ templated `build*<Pred/Iter>()` helpers** (from 43+)
  Round 12 added: 44th (edge score), 45th (time-between-fills),
  46th (vol-ratio). Three new derived structs: `EdgeScore`,
  `TimeBetweenFills`, `VolatilityRatio`.
- 6 sprints, 6 commits, 0 widgets, 6 new ✓ tests.
- 0 failures.

## What was NOT done in round 12 (and why)

- No widget wiring — all 6 sprints are data-layer. The
  widgets that consume per-symbol metrics can switch to the
  bulk mirror variants in a future round if needed.
- No PnL heatmap updates — the heatmap already uses
  weekday-hour data (#173-#174), no new primitive needed
  for round 12's analytics.
- No method consolidation — still pure additions. The
  method count is 296+ and growing; a future round should
  start grouping similar metrics into shared structs
  (e.g. `RiskMetrics` containing sharpe/sortino/calmar/kelly
  together) to reduce per-method overhead.
