# Round 13 — Sprints #235-#238 (2026-06-21)

4 sprints in this round, all adding new per-segment derived
structs with calendar-bucketed arrays. Zero widgets added.
End-of-round state: **238 commits / 304+ methods / 49
templated build helpers / 923 ✓ across 223 cases / 0 failures**.

User signal: PICK+SHIP was invoked FOUR more times in
this round alone ("FRAG NICHT IMMER SO BEHINDERT: WEITER!").
The PICK+SHIP rule from round 11-12 is now load-bearing —
the user does not want a "summary" between commits at all,
even a one-line "Done. Sprint #235: hourlyWinRate".
The mcp__mazemaker__mazemaker_remember call IS the
between-commit artifact. The chat reply after a commit
should be silent or one-word max.

## New derived structs (4)

Each is a per-segment analytics struct with calendar
buckets (24-element hour-of-day or 7-element day-of-week
arrays). All follow the canonical 3-pair pattern
(per-symbol / per-tag / bulk all-segments):

| #    | Struct         | Dimensions | Sprint  | Purpose                              |
|------|----------------|------------|---------|--------------------------------------|
| #235 | `HourlyWinRate`| 24×WR      | 235-237 | Win rate by hour-of-day (0..23)      |
| #236 | `HourlyPnL`    | 24×P&L     | 236-237 | Total P&L by hour-of-day (0..23)     |
| #237 | bulk wrapper   | -          | 237     | allSegmentHourlyPnL DESC by sum      |
| #238 | `DoWTradeCount`| 7×count    | 238     | Fill count by day-of-week (0=Sun..6) |

The "by-hour" arrays use `int hr = tm.tm_hour;` (0..23).
The "by-DoW" arrays use `int dow = tm.tm_wday;` (0..6, 0=Sun).
localtime_r returns LOCAL, not UTC — so the hour/DoW index
is in the user's local timezone, which means test fixtures
that pin to UTC midnight may end up in different array
slots depending on the build host's TZ.

## Test fixture TZ-fragility fix (round 13 specifically)

The original test for `hourlyWinRateBySymbol` tried to assert
`winRateByHour[12] == 1.0` after placing 2 fills at
`1704110400` (2024-01-01 12:00:00 UTC). The assertion FAILED
on the build host because `localtime_r` shifts UTC noon to
local 06:00, 07:00, etc. depending on TZ. The fix pattern is
now codified:

```cpp
// WRONG — assumes UTC
if (std::fabs(btcH.winRateByHour[12] - 1.0) < 1e-9) { ... }

// RIGHT — find the actual hour, then assert
for (int hr = 0; hr < 24; ++hr) {
    if (btcH.tradeCountByHour[hr] == 2) {
        if (std::fabs(btcH.winRateByHour[hr] - 1.0) < 1e-9) {
            // hour is the LOCAL hour — don't hardcode
        }
        break;
    }
}
```

This same fragility was already documented in round 9 for
`bestHourOfDayBySymbol` but the test for `hourlyWinRateBySymbol`
made the same mistake. **Always scan-for-the-bucket, never
hardcode-the-bucket** in tests for `localtime_r`-derived
indices.

## CRITICAL new pitfall: std::array / std::map include gap

When adding a new struct with `std::array<double, 24>` or
`std::array<size_t, 7>` fields to `trade_journal.hpp`,
the **top-of-file includes MUST include `<array>` and
`<map>`**. The header is structured as `#pragma once` with
includes declared near the top, but new derived analytics
structs were being added 2500+ lines into the file. The
struct definitions use `std::array<...>` which requires
`<array>` to be visible at the point of struct instantiation
NOT just at the point of the method declaration. The error
when missing is:

```
error: Feld »winRateByHour« hat unvollständigen Typen
       »std::array<double, 24>«
       (Field 'winRateByHour' has incomplete type
        'std::array<double, 24>')
```

Fix: add `#include <array>` and `#include <cstdint>` and
`#include <map>` to the top-of-file include block. This was
not previously needed because earlier structs used only
`std::vector`, `std::string`, and primitive types.

**Always check the top-of-file includes before adding a
new struct with std::array or std::tuple members.** The
grep recipe is `head -20 src/data/trade_journal.hpp` to
verify includes. Pattern of broken hpp's top:

```cpp
#pragma once
#include <atomic>
#include <cmath>          // ← no <array>, no <cstdint>, no <map>
#include <optional>
#include <string>
#include <vector>
```

Pattern of correct hpp's top:

```cpp
#pragma once
#include <array>          // ← needed for std::array fields
#include <atomic>
#include <cmath>
#include <cstdint>        // ← needed for uint64_t, size_t
#include <map>            // ← needed for std::map in templated helpers
#include <optional>
#include <string>
#include <vector>
```

## Forward-decl for in-sig structs (round 9, surfaced again in 13)

When a method's signature uses a struct (e.g. `DailyPnL`)
that is defined LATER in the same `.hpp`, you need a
forward declaration ABOVE the method declaration:

```cpp
// Forward decl for dailyPnLSeriesBySymbol/Tag (Sprint #177).
// DailyPnL is defined further down; we declare its
// existence here so the method ...
```

This came up in round 9 with `DailyPnL` and is still
relevant for any new derived struct.

## The per-segment + per-tag + bulk all-segments pattern (now 14+ families)

Round 13 added 2 more families that follow the canonical
3-pair pattern. The current count of derived analytics
families that follow this exact shape:

| Family                | struct       | bulk var  | per-symbol | per-tag |
|-----------------------|--------------|-----------|------------|---------|
| expectancy            | #213         | #214      | ✓          | ✓       |
| risk-reward ratio     | #211         | #212      | ✓          | ✓       |
| day streak            | #217         | #218      | ✓          | ✓       |
| daily vol             | #219         | #220      | ✓          | ✓       |
| DD duration           | #221         | #222      | ✓          | ✓       |
| Kelly fraction        | #223         | #224      | ✓          | ✓       |
| fills per day         | #225         | #226      | ✓          | ✓       |
| DD depth percentiles  | #227         | #228      | ✓          | ✓       |
| edge score            | #229         | #230      | ✓          | ✓       |
| time between fills    | #231         | #232      | ✓          | ✓       |
| volatility ratio      | #233         | #234      | ✓          | ✓       |
| hourly win rate       | #235         | (none)    | ✓          | ✓       |
| hourly P&L            | #236         | #237      | ✓          | ✓       |
| DoW trade count       | #238         | (none)    | ✓          | ✓       |

Note: `hourlyWinRate` and `DoWTradeCount` do NOT have
all-segments bulk mirrors yet — those would be
`allSegmentHourlyWinRate` and `allSegmentDoWTradeCount`
in a future round.

## PICK+SHIP stress test

This round had FOUR consecutive "WEITER!" triggers with
zero narrative reply between them. The pattern that worked:

1. Commit Sprint #235 with `mcp__mazemaker__mazemaker_remember`
2. **No chat reply.** Begin the next patch immediately.
3. Commit Sprint #236 with `mcp__mazemaker__mazemaker_remember`
4. **No chat reply.** Begin the next patch immediately.
5. Continue until the user types something other than
   "WEITER!" or there's a natural pause.

The user's tolerance for silence between commits is now
ZERO narrative. Status updates, even terse ones, are
interpreted as "are you done?". The only acceptable
mid-chain output is the `mcp__mazemaker__mazemaker_remember`
tool call, which is silent and persistent.

## Cumulative run stats (through sprint #238)

- **238 commits** on `0.0.2` (from 234 at end of round 12)
- **32 widgets** (unchanged from round 7)
- **923 ✓ across 223 cases** (from 919 ✓ across 219 at end of round 12)
- TradeJournal surface: **304+ methods** + 56+ derived analytics
  structs (from 296+ methods at end of round 12). Round 13
  added 10 new methods:
    - hourlyWinRateBySymbol/ByTag (#235)
    - hourlyPnLBySymbol/ByTag (#236)
    - allSegmentHourlyPnL/ByTag (#237)
    - dowTradeCountBySymbol/ByTag (#238)
- 3 new derived analytics structs in round 13:
  HourlyWinRate, HourlyPnL, DoWTradeCount.
- **49 templated `build*<Pred/Iter>()` helpers** (from
  46 at end of round 12). 47th (hourly WR), 48th
  (hourly P&L), 49th (DoW count) added in round 13.
- **Round 13 alone: 4 sprints, 4 commits, 0 widgets, 4
  new ✓ tests.** Cadence: ~2 minutes per commit.
- 0 failures across all 923 tests in 223 cases.

## Build / test commands used in this round

```bash
cmake --build build -j4 2>&1 | tail -3
cmake --build build -j4 2>&1 | grep "error:" | head -5
./build/test/test_integration 2>&1 | grep -E "Test 22[3-5]" | tail -3
```

## Open follow-ups for round 14+

- `allSegmentHourlyWinRate` — bulk DESC by total wins
- `allSegmentDoWTradeCount` — bulk DESC by total fills
- `hourlyWinRate` heatmap widget (analogous to PnLHeatmapPanel)
- `DoWTradeCount` heatmap widget
- Header-include audit: grep for any future std::array or
  std::tuple uses that might re-introduce the include gap
