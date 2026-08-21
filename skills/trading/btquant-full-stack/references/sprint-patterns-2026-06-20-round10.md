# Sprint patterns — 2026-06-20 round 10 (#216–#222)

The seventh stretch of the BTQuant sprint chain. 7 sprints,
7 commits, 0 widgets added, 7 new ✓ tests. **Bug pattern
re-occurrence**: `DrawdownEvent.start_ts/trough_ts` field
name pitfall (already known from round 8 but re-encountered
and now formally added to the catalogue). 222 commits, 32
widgets, 907 ✓ across 207 tests, 0 failures. 40 templated
`build*<Pred/Iter>()` helpers.

## 1. All-bulk mirror pattern — 4 of the 7 sprints are pure mirrors

Sprints #216, #218, #220, #222 are all `allSegment*` and
`allSegment*ByTag` bulk variants of primitives that were
already added in earlier rounds:

| Sprint | Primitive                      | Sort key           |
|--------|--------------------------------|--------------------|
| #216   | allSegmentTradeSizeHHI         | hhi DESC           |
| #218   | allSegmentDayStreak            | longestWinDays DESC|
| #220   | allSegmentDailyVol             | stddevDaily DESC   |
| #222   | allSegmentDDDuration           | avgDurationDays DESC|

Each is 35-50 lines: enumerate segments, call per-segment
method, sort DESC by sort key, return vector. No new
domain logic. The "five-pillar" rule (per-symbol, per-tag,
bulk, bulk-by-tag, plus top-N) drove these — once the
per-segment method exists, the bulk variant is mandatory
for the panel UI.

The 4 mirror commits shipped in ~10 minutes total. The
shape of the work IS the roadmap; user said "WEITER!" at
each commit.

## 2. dayStreakBySymbol/ByTag — per-segment day-level win/loss streaks

`dayStreakBySymbol(symbol)` returns a `DayStreakSeg` struct:
`longestWinDays`, `currentWinDays`, `longestLossDays`,
`currentLossDays`, `totalDays`. The 38th templated helper
`buildDayStreakBySegment<Pred>` walks fills, buckets
realized by calendar day (via `strftime("%Y-%m-%d")`),
then tracks the longest/current run of positive/negative
days.

Important: this is the **DAY-level** streak (consecutive
calendar days with positive/negative net P&L). It's
distinct from `perSymbolStreakStats` (#122) which is the
**FILL-level** streak (consecutive winning/losing trades).
The two are complementary: fill-streak answers "how many
wins in a row", day-streak answers "how many green days
in a row".

For test, the test fixture used `t0 = 1705276800` (Jan 16
2024) as a clean epoch, then walked 3 days with +50/+50/-25
to produce `longestWinDays=2, longestLossDays=1`. The
`strftime` + `std::map<std::string, double>` for daily
bucketing is the same shape as #217's `ddStreakStats` but
without the recovery_us check.

## 3. dailyVolBySymbol/ByTag — per-segment daily P&L volatility

`dailyVolBySymbol(symbol)` returns `DailyVolSeg` struct:
`meanDaily`, `stddevDaily`, `minDaily`, `maxDaily`,
`activeDays`. The 39th templated helper
`buildDailyVolBySegment<Pred>` reuses the daily-bucketing
pattern from #217, then computes mean + stddev via the
two-pass mean-deviation formula.

Test #205 verifies `BTC 2 days [+50,-50] → mean=0,
stddev=50`. The `stddev = 50` for `±50` is correct: with
two values at ±50 from mean=0, variance = (50² + 50²)/2 =
2500, stddev = 50.

Use case: "which segments have the most volatile daily
returns?" Useful for the panel's volatility heatmap and
for position-sizing risk checks.

## 4. ddDurationBySymbol/ByTag — per-segment DD duration

`ddDurationBySymbol(symbol)` returns `DDDurationSeg`
struct: `avgDurationDays`, `maxDurationDays`,
`minDurationDays`, `completedDDCount`. The 40th templated
helper `buildDDDurationBySegment<Iter>` walks the
`drawdownRecoveriesBySymbol` event list and computes
duration per event.

**BUG RE-OCCURRENCE — start_ts/trough_ts field names:**

I had previously assumed `DrawdownEvent` had `start_us`
and `trough_us` fields (matching the `*_us` microsecond
convention used elsewhere in TradeJournal). I was wrong
the first time in round 8 too — the fields are `start_ts`
and `trough_ts`. The compile error:

```
error: 'struct btquant::TradeJournal::DrawdownEvent' hat
kein Element namens 'start_us'; meinten Sie 'start_ts'?
```

The compiler literally suggested the fix. Cost: 30 seconds
to fix in the IDE. Lesson: **grep the .hpp for the
struct definition BEFORE writing any field access**:

```bash
grep -A 20 "struct DrawdownEvent" src/data/trade_journal.hpp
```

This is now formally added to the field-name pitfall
catalogue in SKILL.md. The convention is: any event
struct (DrawdownEvent, RecoveryEvent, DrawdownEventExt,
etc.) uses `*_ts` for timestamps, NOT `*_us`. The
`JournalFill` struct uses `timestamp_us` (the underlying
fill data is in microseconds), but derived analytics
events use `*_ts`. The naming is inconsistent but stable.

## 5. The full back-half of round 10 (#217, #219, #221) is per-segment methods

The non-bulk methods (dayStreak, dailyVol, ddDuration) all
follow the same template:

```cpp
struct XxxSeg {
    std::string segment;
    /* 4-5 numeric fields */
};
XxxSeg xxxBySymbol(const std::string& symbol) const;
XxxSeg xxxByTag(const std::string& tag,
                 bool includeUntagged = false) const;
```

Each method is ~20 lines of body + ~5 lines of dispatch
to the templated helper. The build helper itself is ~30-40
lines. Total ~70 lines per primitive, three primitives =
~210 lines, three bulk mirrors = ~120 lines. The
cumulative TradeJournal.cpp is now 9510+ lines.

The helper template signature varies:

- `buildDayStreakBySegment<Pred>(fills, pred)` — uses fill list directly
- `buildDailyVolBySegment<Pred>(fills, pred)` — same
- `buildDDDurationBySegment<Iter>(segment, begin, end)` — uses iterator pair (DD events)

The iterator-pair signature is the natural one when the
per-segment method calls `drawdownRecoveriesBySymbol()`
which already returns the event list. No need to re-filter
in the helper. Just iterate the event list.

## 6. Field-name pitfall catalogue — formally add `start_ts/trough_ts`

Append to the existing catalogue in SKILL.md:

| You write               | Actual field     | Type / context        |
|-------------------------|------------------|-----------------------|
| `start_us` on DrawdownEvent | `start_ts`    | DrawdownEvent struct  |
| `trough_us` on DrawdownEvent | `trough_ts` | DrawdownEvent struct  |
| `recovery_us` on DrawdownEvent | `recovery_us` | correct — recovery IS in microseconds |
| `end_us` on DrawdownEvent | `end_ts`    | if it exists          |

The pattern: derived event structs use `*_ts` (not `*_us`)
for entry/trough/recovery timestamps. JournalFill uses
`timestamp_us`. The naming is inconsistent and stable —
don't try to fix it, just grep before you write.

This bug has now been encountered twice (round 8 implicit,
round 10 explicit). The catalogue entry will prevent a
third time.

## 7. No new widgets, no UI wiring — still pure backend

Round 10 is again pure backend / journal-surface. The
6 new methods added are:

1. `allSegmentTradeSizeHHI` + `allSegmentTradeSizeHHIByTag` (#216)
2. `dayStreakBySymbol` + `dayStreakByTag` (#217)
3. `allSegmentDayStreak` + `allSegmentDayStreakByTag` (#218)
4. `dailyVolBySymbol` + `dailyVolByTag` (#219)
5. `allSegmentDailyVol` + `allSegmentDailyVolByTag` (#220)
6. `ddDurationBySymbol` + `ddDurationByTag` (#221)
7. `allSegmentDDDuration` + `allSegmentDDDurationByTag` (#222)

The 14 new methods (#216-#222 × 2 each, plus the per-tag
sprint #217 #219 #221 × 2 each) all need wiring into
JournalStatsPanel in round 11. The natural plan is an
"Edge Quality" tab that aggregates Sharpe trend, R, E,
HHI, win streak, day streak, daily vol, DD duration.

OR: an "Edge Decay" tab that surfaces the failure modes —
DD streak, recovery time, daily vol, recovery factor,
expectancy. The trader wants to see WHEN their edge fades,
not just whether it exists.

## 8. The user "FRAG NICHT IMMER SO BEHINDERT" pattern — round 10 had it THREE times

The user fired the rage signal at:
- After Sprint #202 (my "200-commit milestone" wrap)
- After Sprint #211 (my mid-chain summary)
- After Sprint #215 (my "btquant-vulkan — 215 sprints" wrap)

In round 10, the user fired it ONCE at sprint #216, just
as the chain was re-starting. The pattern is consistent:
any time the agent writes prose between commits, the user
interprets it as a stop signal and demands continuation.

The fix is the same: ship the next sprint immediately, no
prose. The `mcp__mazemaker__mazemaker_remember` call IS the
between-commit artifact — silent, persistent, not
chat-visible.

**Implementation in this round**: every commit was
followed by either nothing, a one-line "Sprint #217: ..."
prefix, or the mcp save. No mid-chain wrap-up. The chain
went #216→#222 without any user complaint about format.

## 9. The chain ended naturally at #222

Round 10 ended at #222, not at a round number. The
back-half of the chain (#217, #219, #221 — the per-segment
methods) are all "compute statistics on daily aggregated
data" which is the natural ceiling of the journal-primitive
universe. The next batch of work is either:

(a) **UI wiring** — add 14 new methods to the
JournalStatsPanel as new sub-sections or new tabs.
Sprint #223+ would touch `src/ui/` files for the first
time in many rounds.

(b) **New domain primitives** — options/futures Greeks
(volatility surface, theta, vega), pair-trade analysis
(long/short P&L split), fill-level analytics (slippage,
fill quality, time-in-position).

(c) **Backtesting integration** — wire the 270+ methods
into the strategy backtester so each strategy run emits
the same metrics as a real journal.

The user's "WEITER" hasn't stopped, so option (a) is the
natural next step — wire what we have before building
more.

## Cumulative run stats (end of round 10)

- **222 commits** on `0.0.2` (from 215 at end of round 9)
- **32 widgets** (unchanged from round 7)
- **907 ✓ across 207 tests** (from 900 ✓ across 200 at end of round 9)
- TradeJournal surface: **272+ methods** + 40+ derived analytics structs
  (from 258+ methods at end of round 9). Round 10 added:
  14 new methods (3 per-segment primitive pairs + 4 bulk
  mirror pairs).
- 14 new derived analytics structs added in round 10:
  RiskOfRuin, SharpeTrend, BestDayOfWeek, BestHourOfDay,
  TradeSizeStatsSeg, RiskRewardRatio, Expectancy, TradeSizeHHI,
  DayStreakSeg, DailyVolSeg, DDDurationSeg (some from
  round 9 carryover, 3 new in round 10).
- **40 templated `build*<Pred/Iter>()` helpers** (from
  37 at end of round 9). The 38th, 39th, 40th added in
  this round.
- **Round 10 alone: 7 sprints, 7 commits, 0 widgets, 7
  new ✓ tests.** Cadence: ~2 minutes per commit including
  the mcp save.
- 0 failures across all 907 tests in 207 cases.

The TradeJournal is now a near-complete per-trade
analytics library. Every standard trader metric has both
a per-symbol and per-tag variant, plus a bulk
all-segments variant for the panel UI. The remaining
work is UI wiring of the 270+ methods, not new methods.
