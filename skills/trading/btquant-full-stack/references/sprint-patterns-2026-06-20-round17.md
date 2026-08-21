# Sprint Patterns — Round 17 (#253-#255)

**3 sprints, 0 widgets added, 3 new ✓ tests.**

## What was added

- **Sprint #253**: `MonthlyWinLossCount` bulk mirror — pure 1-method-pair sprint following the established round 14-16 four-pattern. (Per-segment from #252, this sprint added the two bulk methods.)
- **Sprint #254**: `WeekdayHourPnLMatrix` (per-symbol + per-tag) — 7×24 std::array matrix variant. This is the **refined duplicate-declaration lesson**.
- **Sprint #255**: `WeekdayHourPnLMatrix` bulk mirror — 2 bulk methods.

## Round 17 lesson — name collision ≠ duplicate declaration

Round 16 documented: if `grep -n "<methodName>" src/data/trade_journal.hpp` finds the name, you have a duplicate and must reuse or rename.

Round 17 refined this: the conflict can be of **two kinds**:

1. **Duplicate declaration** — same name, same return type, same signature. The build error is `kann nicht überladen werden` (cannot be overloaded) with identical signatures. The fix: pick a different name OR reuse the existing method.

2. **Name collision, different return type** — same name, different return type. The build error is the SAME `kann nicht überladen werden`, but the signatures DIFFER. The fix: pick a **semantically-distinct suffix** that describes the data shape.

In round 17, `weekdayHourPnLBySymbol` already existed from round 6 / #182, returning `vector<SegmentHeatmapCell>` (a flat list of cells, one per (dow, hour) pair with non-zero data). The new method needed to return a 7×24 raw matrix `WeekdayHourPnLMatrix` with `std::array<std::array<double, 24>, 7>`. The recovery was to use the suffix `Matrix` in the new name → `weekdayHourPnLMatrixBySymbol`. This communicates the data-shape difference to future readers.

The grep-then-decide recipe (extended):

```bash
grep -n "<methodName>\|<methodName>Matrix\|<methodName>Cells\|<methodName>Stats" src/data/trade_journal.hpp
```

If a hit exists with a **suffix** that distinguishes the data shape, that suffix pattern is the convention — name your new method with the appropriate suffix. If a hit exists WITHOUT a suffix (i.e. same shape), you have a duplicate — must reuse or pick a different concept.

The trade-journal surface has been growing with `-Matrix` / `-Cells` / `-Stats` / `-Distribution` / `-Summary` suffixes since round 14. The convention is to suffix the data shape, not to overload the same name.

## Established four-pattern coverage (canonical)

After round 17, the established four-pattern is now:

1. Per-symbol — `<X>BySymbol(symbol)`
2. Per-tag — `<X>ByTag(tag, includeUntagged=false)`
3. Bulk all-segments — `allSegment<X>()`
4. Bulk all-segments-by-tag — `allSegment<X>ByTag(includeUntagged=true)`

Every new derived analytics struct gets all 4 unless the operator has a reason otherwise. Round 17 had 3 sprints covering: bulk mirror of #252 (#253), per-segment variant with new shape suffix (#254), bulk mirror of #254 (#255).

## Cumulative run stats (through sprint #255)

- **255 commits** on `0.0.2` (+3 from round 16)
- **32 widgets** (unchanged since round 7)
- **940 ✓ across 240 cases** (+3 from round 16: 937 ✓ across 237)
- TradeJournal surface: **340+ methods** + 70+ derived analytics structs (+6 methods from round 16: 334+, +2 new structs: `WeekdayHourPnLMatrix`, `MonthlyWinLossCount` was carry).
- **58 templated `build*<Pred/Iter>()` helpers** (+1 from round 16: 57). 58th (`WeekdayHourPnLMatrix`).
- **Round 17 alone: 3 sprints, 3 commits, 0 widgets, 3 new ✓ tests.** Cadence: ~2 minutes per commit including the mcp save.
- 0 failures across all 940 tests in 240 cases.

## PICK+SHIP held

Round 17 had 3+ mid-chain WEITER! triggers. Zero narrative reply between commits. The mcp save IS the artifact.
