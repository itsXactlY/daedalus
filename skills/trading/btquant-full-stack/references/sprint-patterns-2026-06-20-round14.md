# Sprint patterns — round 14 (sprints #239-#244)

6 sprints in this round. 0 widgets added. 6 new ✓ tests
(#225-#230). 0 failures.

## What shipped

Sprint #239 — `allSegmentDoWTradeCount` /
`allSegmentDoWTradeCountByTag` bulk mirror of #238
(per-segment DoW trade count).

Sprint #240 — `monthlyPnLSeriesBySymbol` /
`monthlyPnLSeriesByTag` — new derived analytics:
vector<MonthlyPnLEntry> with {month YYYY-MM,
realized, tradeCount}. Distinct from `monthlyReturns`
(which returns year×month matrix). Useful for "show
me BTC monthly P&L" line chart.

Sprint #241 — `bestWorstDayBySymbol` /
`bestWorstDayByTag` — new derived analytics:
BestWorstDay struct with {segment, bestDate,
bestRealized, worstDate, worstRealized, activeDays}.
Distinct from `topTradeDays/worstTradeDays` (lists).
BestWorstDay returns the SINGLE best/worst with date.

Sprint #242 — `allSegmentBestWorstDay` /
`allSegmentBestWorstDayByTag` — bulk mirror of #241
sorted DESC by bestRealized.

Sprint #243 — `winLossAvgBySymbol` / `winLossAvgByTag`
— new derived analytics: WinLossAvg struct with
{segment, avgWin, avgLoss (absolute), winRatio,
nWins, nLosses}. Distinct from `expectancyBySymbol`
(combines win rate + R). WinLossAvg is the simpler
"average win, average loss" without win rate.
Formula: `avgWin = sumW / nW`, `avgLoss = |sumL| / nL`,
`winRatio = avgWin / avgLoss`.

Sprint #244 — `allSegmentWinLossAvg` /
`allSegmentWinLossAvgByTag` — bulk mirror of #243
sorted DESC by winRatio.

## New pitfall catalogue entries

None this round — the catalogue was complete at end
of round 13.

## Cadence

~2 minutes per commit including the mcp save.
6 commits across the round. PICK+SHIP held across
3 mid-chain WEITER! triggers (sprint #238 → #239,
#240, #242 → #243).

## Cumulative stats through sprint #244

- **244 commits** on `0.0.2`
- **32 widgets** (unchanged since round 7)
- **929 ✓ across 229 cases** (from 923 ✓ across 223
  at end of round 13)
- TradeJournal surface: **316+ methods** + 60+ derived
  analytics structs (from 304+ methods / 56+ structs
  at end of round 13). Round 14 added 12 new methods
  (6 derived methods × 2 variants per-sym/per-tag +
  6 bulk methods = 12).
- 4 new derived analytics structs in round 14:
  `DoWTradeCount` (round 13 carry), `MonthlyPnLEntry`,
  `BestWorstDay`, `WinLossAvg`.
- **52 templated `build*<Pred/Iter>()` helpers**
  (from 49 at end of round 13). 50th (monthly P&L),
  51st (best/worst day), 52nd (win/loss avg) added
  in round 14.
- 0 failures across all 929 tests in 229 cases.
- **16 distinct derived analytics families** now
  follow the canonical 4-pattern (per-symbol /
  per-tag / bulk all-segments / bulk by-tag):
  1. risk-adjusted return (Sharpe/Sortino/Calmar/Omega/Kelly)
  2. drawdown analysis (recoveries/durations/depths/streaks)
  3. session analysis (sessions/top/worst)
  4. distribution analysis (PnL/WR/intervals/vol)
  5. concentration (HHI/contributions/retention)
  6. correlation (symbol-symbol/all-symbol/all-tag)
  7. leaderboard
  8. temporal (best-DoW/best-hour/hourly-WR/hourly-P&L)
  9. day-of-week
  10. day-stats (best/worst day)
  11. win-loss (avg win/loss)
  12. trend (sharpeTrend)
  13. risk (PoR/RR/expectancy)
  14. operational
  15. edge (composite score)
  16. volatility (ratio)

## Pattern reinforcement

The "four-pattern" coverage (per-symbol / per-tag /
bulk all-segments / bulk by-tag) is now the established
default. Every new derived analytics struct gets all
four method shapes unless the operator has a reason
otherwise. This is the 16th family to ship the full
quad.

The `localtime_r` TZ-fragility lesson from round 13
held — no new hardcoded bucket indices this round.
The hour-of-day P&L tests (#222) use scan-for-bucket
semantics.
