# Sprint patterns — round 11 (sprints #223-#228)

**Date:** 2026-06-20
**Scope:** 6 sprints, all derived-stats primitives, 0 widgets added.

## What was built

Six sprints, all of the journal-wide → per-symbol → per-tag → bulk
pattern, three new derived structs, two new per-segment pairs
plus their bulk mirror counterparts. Final state: 228 commits,
913 ✓ across 213 cases, 0 failures, 32 widgets (unchanged), 284+
TradeJournal methods, 43+ templated `build*<Pred/Iter>()` helpers.

| #   | Method(s)                                  | Type                  | Struct                  |
|-----|-------------------------------------------|-----------------------|-------------------------|
| 223 | kellyFractionBySymbol / ByTag             | per-segment primitive | KellyFraction           |
| 224 | allSegmentKellyFraction / ByTag           | bulk mirror           | KellyFraction           |
| 225 | fillsPerDayBySymbol / ByTag               | per-segment primitive | FillsPerDay             |
| 226 | allSegmentFillsPerDay / ByTag             | bulk mirror           | FillsPerDay             |
| 227 | ddDepthPctBySymbol / ByTag                | per-segment primitive | DDDepthPercentiles      |
| 228 | allSegmentDDDepthPct / ByTag              | bulk mirror           | DDDepthPercentiles      |

## New pitfall catalogue entry

`DrawdownEvent.trough_depth` — NOT `maxDrawdown` (round 11
hit this for the second time; round 10 had `start_ts/trough_ts`
but not this one). Use:

```cpp
if (it->trough_depth > 0) depths.push_back(it->trough_depth);
```

NOT:

```cpp
if (it->maxDrawdown > 0) depths.push_back(it->maxDrawdown); // wrong field
```

Confirmed by `grep -A 10 "struct DrawdownEvent" src/data/trade_journal.hpp`:
fields are `start_ts`, `trough_ts`, `end_ts`, `peak_before`,
`trough_value`, `trough_depth`, etc. — NO `maxDrawdown`. The
`maxDrawdown()` METHOD returns a Drawdown struct that has a
`.maxDrawdown` field, but the EVENT struct itself only has
`trough_depth`.

Add this to the SKILL.md pitfall catalogue (between `end_us on
DrawdownEvent` and the existing entries).

## Kelly fraction formula

```
K = W - (1 - W) / R
W = wins / total
R = avgWin / |avgLoss|
halfKelly = K / 2
```

`if (K < 0) K = 0;` — clamp at zero (negative Kelly means
"don't bet" but the user-facing return is 0, not negative).

`K/2` (half-Kelly) is the practical recommended bet size
because the full Kelly is volatile in real data. The struct
exposes both.

## Fills-per-day semantics

`fillsPerDayBySymbol(symbol)` returns:
- `totalFills` — count of all fills in the symbol
- `activeDays` — number of distinct YYYY-MM-DD buckets
- `avgFillsPerDay = totalFills / activeDays`

NOT `(fills / spanDays)` — the user wants "how often do I
trade when I AM trading" not "how often do I trade per
calendar day including flat ones". The struct name is
`FillsPerDay` but the denominator is active days, not
calendar days. (If you want the calendar-days version,
just use `totalFills / spanDays` — the math is `journalMetadata()`.)

## DD depth percentiles via `DrawdownEvent.trough_depth`

For each symbol, gather `trough_depth` from every completed
DrawdownEvent into a vector, sort, then pick p10/p25/p50/p75/p90
via `idx = (int)(p * n)` with bounds clamp at `n-1`. The simple
`floor` percentile is fine for analytics — no need for
linear-interpolation methods unless the trader asks.

Useful for the "how bad is my typical drawdown?" panel
plus a "what's my worst-10% tail?" view. Sorted DESC by p90
in the bulk variant answers "which symbol has the most
extreme tail risk?".

## PICK+SHIP discipline — held

This round went 6 sprints in a row with NO mid-chain summary
between commits. The only artifact between commits was the
`mcp__mazemaker__mazemaker_remember` save (which is silent).
When the user typed `WEITER!` they got the next sprint
immediately, not a recap. The chain ran clean.

The PICK+SHIP rule from rounds 9-10 is now muscle memory
for the model: after a commit, either nothing, one word,
or the next sprint number. NEVER a multi-paragraph summary.

## Cumulative stats update (through sprint #228)

- **228 commits** on `0.0.2` (from 222 at end of round 10)
- **32 widgets** (unchanged from round 7)
- **913 ✓ across 213 cases** (from 907 ✓ across 207 at round 10)
- TradeJournal surface: **284+ methods** (from 272+)
- **43+ templated `build*<Pred/Iter>()` helpers** (from 40+)
- New derived analytics structs (round 11): `KellyFraction`,
  `FillsPerDay`, `DDDepthPercentiles` — bringing the total
  derived-struct count to ~50+.
- 6 sprints, 6 commits, 0 widgets, 6 new ✓ tests.
- 0 failures.

## What was NOT done in round 11 (and why)

- No widget wiring — the per-segment + bulk mirror pairs are
  pure data-layer additions. The 32 widgets already consume
  the per-symbol variants; adding the bulk mirrors in the
  data layer means the widgets can switch to bulk rendering
  in a single follow-up sprint if needed.
- No PanelListPanel addition — round 6 + round 7 already
  exhausted the obvious panel types.
- No method consolidation / refactor — every sprint is
  pure addition. The 284+ method count is high enough that
  a future round should start the consolidation pass.
