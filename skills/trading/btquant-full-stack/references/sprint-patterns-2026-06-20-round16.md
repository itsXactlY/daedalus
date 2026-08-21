# Sprint patterns — round 16 (2026-06-21)

Sprints **#249 – #252** (4 sprints, 0 widgets, 4 new ✓ tests,
PICK+SHIP held across 4+ mid-chain WEITER! triggers).

## What got built

| Sprint | Family | Struct | Methods |
|--------|--------|--------|---------|
| #249 | monthly bulk | (carry `MonthlyFillCount`) | 2 × `allSegment*` mirrors |
| #250 | monthly calendar | `AvgDailyPnLByMonth` | per-symbol, per-tag (12-element mean daily P&L grid) |
| #251 | monthly bulk | (carry `AvgDailyPnLByMonth`) | 2 × `allSegment*` mirrors |
| #252 | monthly calendar | `MonthlyWinLossCount` | per-symbol, per-tag (12-element W/L count grid) |

`AvgDailyPnLByMonth` is the seasonal counterpart to
`monthlyPnLSeriesBySymbol` (#240): instead of chronological
P&L per month, it's a 12-element grid of mean daily P&L
per month-of-year. Uses `std::map<std::string, double>[12]`
keyed by `YYYY-MM-DD` per month bucket — same key collision
pitfall as round 13.

`MonthlyWinLossCount` is the simpler sibling: 12-element
`winsByMonth[12]` + `lossesByMonth[12]` + `totalFills`. No
sorting needed, no bucket aggregation, just `tm.tm_mon` →
`winsByMonth[mo]++` / `lossesByMonth[mo]++`.

## Already-exists detection (re-reinforced)

Sprint #252 first attempt **duplicated the existing
`rollingWinRateByTag`** (defined at line 1899 since
round 6 / #181). Compile failed with German error:
"kann nicht überladen werden" (cannot be overloaded).
The fix: **grep the hpp BEFORE writing any method
declaration**, not just before writing any field access.

The grep recipe (now expanded from the field-name pitfall
catalogue):

```bash
grep -n "<methodName>" src/data/trade_journal.hpp
```

If a hit exists, do NOT redeclare. Reuse the existing
method, or pick a different name. Sprint #252 recovered by
swapping `rollingWinRateBySymbol/ByTag` (already existed)
for `monthlyWinLossBySymbol/ByTag` (new) and committed
cleanly.

This is a stronger version of the round 8 lesson ("grep
the hpp for the method name BEFORE adding the
declaration") — round 8 covered `sharpeTrendBySymbol`,
round 16 covered `rollingWinRateBySymbol/ByTag`. The
pattern is: **any time you add a per-symbol variant of a
method, grep for both the per-symbol AND the per-tag AND
the bulk variants**.

## PICK+SHIP held (again)

The session was punctuated by 4+ "FRAG NICHT IMMER SO
BEHINDERT: WEITER!" triggers. Each time the agent emitted
any narrative recap, the user fired WEITER. Final rule
re-confirmed: **between commits, ZERO chat output, the
mcp__mazemaker__mazemaker_remember call IS the artifact**.

## Round 16 recap

- **252 commits** on `0.0.2` (+4 from round 15)
- **937 ✓ across 237 cases** at end of round 16
  (was 933 ✓ across 233 at end of round 15)
- TradeJournal surface: **334+ methods** + 70+ derived
  analytics structs (was 326+ / 65+ at end of round 15).
  Round 16 added 2 new structs (`AvgDailyPnLByMonth`,
  `MonthlyWinLossCount`) and 8 new methods.
- **57 templated `build*<Pred/Iter>()` helpers** (was 55).
  56th (`AvgDailyPnLByMonth`), 57th (`MonthlyWinLossCount`).
- 0 failures across all 937 tests in 237 cases.
- **Round 16 alone: 4 sprints, 4 commits, 0 widgets, 4 new
  ✓ tests.** Cadence: ~2 minutes per commit including the
  mcp save.
- **20+ distinct derived analytics families** now follow
  the canonical 4-pattern (per-symbol / per-tag / bulk
  all-segments / bulk by-tag).

## Stale-pitfall watch

No new field-name pitfalls surfaced this round. The
`std::array` / `<array>` include pitfall (round 13) was
correctly handled — `AvgDailyPnLByMonth` and
`MonthlyWinLossCount` both compile cleanly because
`#include <array>` is already in the top-of-file block
after round 13 fix.

The "already-exists" pitfall is now its own catalogue
entry: round 8 was `sharpeTrendBySymbol`, round 12 was
`allSymbolRiskOfRuin`, round 16 was `rollingWinRateBySymbol/ByTag`.
The pattern is consistent: **always grep for the method
name across ALL of hpp AND cpp before declaring**.
