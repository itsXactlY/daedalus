---
name: btquant-full-stack
version: "1.38"
description: >-
  BTQuant Hermes integration for the HFT framework. Vulkan UI
  sprints 1-252: 252 commits, 32 widgets, 237 tests
  (937 green, 0 failures). TradeJournal surface 334+ methods
  + 57 templated build helper functions + 70+ derived
  analytics structs. PICK+SHIP rule: never offer a pick-list,
  never recap between commits, never use emoji or narrative in
  mid-chain. Between commits: zero or one-word chat reply only.
  Chain patterns in references/sprint-patterns-2026-06-20-round{1..16}.md.
  Critical pitfalls: journal wiring must follow TradeJournal
  construction; DDStreakStats.segment field; localtime_r returns
  local time; DrawdownEvent uses start_ts/trough_ts AND
  trough_depth (NOT maxDrawdown on the event struct);
  loadAll() does NOT return sorted timestamps — sort before
  gap-difference math; std::array/std::map fields require
  top-of-file includes in trade_journal.hpp; ALWAYS grep hpp
  for method name BEFORE declaring (round 8 / #182, round 12,
  round 16 #252 — rollingWinRateByTag already existed).
tags: []
category: trading
---

# BTQuant Full-Stack (Vulkan HFT framework integration)

[Pointer + summary. New details go to references/. Historical
phase content lives in references/btquant-vulkan-phase*.md files;
sprint-workflow notes in references/sprint-patterns-2026-06-20*.md.]

## When to use

- Adding features to `btquant_vulkan/` (the C++/Vulkan/ImGui UI layer)
- Wiring a new RiskGuard / PositionBook / TradeJournal field through the UI
- Adding a new widget to the WindowManager dock
- Picking the next BTQuant sprint after a commit

## PICK+SHIP — non-negotiable

The user said "FRAG NICHT IMMER SO BEHINDERT: WEITER!" at the
start of the #53-#68 chain AND has repeated it at every major
checkpoint through #98, #100, #202, #211, #216, #225,
#235-#238, #249-#252 (round 13 had FOUR more WEITER! triggers in
sequence with zero narrative reply). Do not respond
with "WEITER — pick: A, B, C, D" or any pick-list after a
commit. Immediately pick the next step and start patching.

**Final-summary rule (STRICTER as of round 13, 2026-06-21):**

1. **NEVER** write a long wrap-up after a sprint commit
   ("Wachstum in dieser Sitzung", "BTQuant Vulkan Sprint-
   Bombardement — final summary", narrative recap, emoji
   decorations). Even mid-chain summaries are forbidden —
   the user reads the terminal and sees the commit count
   and test count themselves. If you write a "summary"
   between commits, the user reads it as a stop signal and
   fires "FRAG NICHT IMMER SO BEHINDERT: WEITER!".

2. The right shape is a terse table or ≤8-line status block
   ONLY at the END of a sprint chain (after a real natural
   pause — user typing something different, final milestone
   hit, or work direction change). Between commits: nothing
   or one word ("Done." / "Shipped."). The chat reply after
   a commit should be silent or one-word max.

3. If you captured a real bug pattern or new technique, save
   it via `mcp__mazemaker__mazemaker_remember` AND/OR
   `skill_manage` — do NOT put it in the chat reply.

4. **The natural next step after any commit is the one the
   unfinished work implies** — if a journal method was just
   added but no UI, do the UI. If a per-symbol variant exists
   but no per-tag, do per-tag. If recovery date was added, do
   Calmar. If per-tag was done, do bulk all-segments. If
   bulk was done, do the by-tag bulk. The shape of the work
   IS the roadmap. The user doesn't want to be asked; they
   want autonomous execution against the implied next step.

5. **Even in middle of a chain: do NOT recap before committing
   the next sprint.** Commit, then immediately patch the
   next one. The `mcp__mazemaker__mazemaker_remember` call after
   each commit is the only "writing" between commits — it is
   silent and persistent, not chat-visible.

## Sprint pattern references

- **references/sprint-patterns-2026-06-20.md** — #44-#52 (pure-helper
  extraction, schema-extension back-compat, brace-init pain, paired-sprint,
  lazy-capture for ImGui, commit cadence).
- **references/sprint-patterns-2026-06-20-round2.md** — #53-#68
  (PICK+SHIP reinforcement, three-layer per-symbol architecture, tag
  attribution threading, state-coupling pitfall, LSP stale-error pattern,
  atomic file rewrite, test density, memory format, status checkpoint,
  sprint shape variety).
- **references/sprint-patterns-2026-06-20-round4.md** — #91-#98
  (shared-helper refactor → per-axis variants thin wrappers; "zip by
  name" pattern for cross-referenced UI columns; recovery algorithm
  using absolute cumulative equity NOT from-trough; test arithmetic
  discipline — always pencil-verify peak/trough; local pass/fail
  counters in tests; per-symbol & per-tag drawdown / Sharpe / Calmar;
  Drawdown.recoveryDate + recoveryDays fields).
- **references/sprint-patterns-2026-06-20-round5.md** — #99-#100
  (Sortino = mean / downside-vol; completes the three-metric
  risk-adjusted panel closure alongside Sharpe + Calmar; "∞"
  sentinel for all-positive days mirrors profit-factor's no-loss
  convention; headline summary row at the top of the panel uses
  perSymbolCalmar() sorted DESC for best/worst, zipped with
  perSymbolSharpe() for the dual-metric display; "no DD yet"
  sentinel renders as "—" (not 0.00) so the trader knows the metric
  is undefined, not zero).
- **references/sprint-patterns-2026-06-20-round6.md** — #103-#111
  (two new widgets: PnLHeatmapPanel Ctrl+Shift+H, EquityCurvePanel
  Ctrl+E; journal wiring bug fix; tabbed JournalStatsPanel with
  `BeginTabBar`/`EndTabItem` wrapping; calendar analytics
  DayOfWeek + HourOfDay via shared `bucketByCalendarIndex<>`
  helper; rolling Sharpe with calendar-day zero-fill semantics;
  bestTrade/worstTrade single-trade extremes via `extremeTrade<>`
  template helper; CRITICAL: 4-place widget wiring checklist;
  localtime_r arg-order pitfall; test-fixture TZ-fragility fix;
  bucketByDay sentinel-key pitfall).
- **references/sprint-patterns-2026-06-20-round7.md** — #112-#171
  (60+ sprints in a single session — largest chain yet). The
  **four-layer pattern**: every primitive gets journal-wide →
  per-symbol → per-tag → bulk all-segments → top-N variants.
  22+ `build*<Pred>()` helper templates established. CRITICAL
  bug-squash catalogue: BestTrade.realized (not realizedDelta),
  PnLDistribution.p50 (not median), maxDrawdown returns Drawdown
  struct (not double), SymbolSummary.roundTripCount (not
  totalCount), sessions() takes int (not size_t). 856 ✓
  tests / 157 cases / 0 failures / 160 commits / 32 widgets
  at end of round 7.
- **references/sprint-patterns-2026-06-20-round8.md** — #172-#202
  (30 sprints, hits the 200-commit milestone). The
  **five-pillar build-out**: every new primitive gets
  journal-wide → per-symbol → per-tag → bulk all-segments →
  bulk all-segments-by-tag. New primitive families: weekday-hour
  P&L heatmap; per-segment risk-of-ruin (Gambler's ruin
  approximation); CAGR; journalSummaryJson (manual JSON);
  Sharpe stability stats; all-segment bulk variants for 12+
  primitives. Already-exists detection: Sprint #182 attempted
  to re-declare per-symbol rolling Sharpe that already
  existed from #134 — caught, rolled back. The lesson: grep
  the hpp for the method name BEFORE adding the declaration.
- **references/sprint-patterns-2026-06-20-round9.md** — #203-#215
  (13 sprints, hits the 200-test-case milestone). New families:
  Sharpe trend slope (OLS on rolling-Sharpe series); best
  day-of-week; best hour-of-day; trade size stats; risk-reward
  ratio; expectancy per trade; trade size HHI. Three new
  catalogue entries: DDStreakStats has `segment` field (not
  `symbol`); DDStreakStats struct lives inside TradeJournal
  namespace; `localtime_r` returns LOCAL, not UTC. Summary
  rule made stricter mid-chain (see SKILL.md § PICK+SHIP).
- **references/sprint-patterns-2026-06-20-round10.md** — #216-#222
  (7 sprints, no widgets added). The mirror-only stretch:
  4 of the 7 sprints are pure `allSegment*` bulk mirrors
  of earlier primitives (#216 HHI, #218 day streak, #220
  daily vol, #222 DD duration). 3 per-segment methods added
  with new derived structs: dayStreakBySymbol (#217),
  dailyVolBySymbol (#219), ddDurationBySymbol (#221). CRITICAL
  new catalogue entry: `DrawdownEvent.start_ts/trough_ts` (NOT
  `start_us/trough_us`) — encountered twice now, finally
  added to the catalogue. The pattern: derived analytics
  event structs use `*_ts`, the underlying `JournalFill` uses
  `timestamp_us`. Naming is inconsistent and stable — don't
  try to fix it, just grep before you write.
- **references/sprint-patterns-2026-06-20-round11.md** — #223-#228
  (6 sprints, no widgets added). 3 new derived structs:
  KellyFraction (#223-#224), FillsPerDay (#225-#226),
  DDDepthPercentiles (#227-#228). All follow the
  per-segment + bulk mirror pattern. New pitfall catalogue
  entry: `DrawdownEvent.trough_depth` (NOT `maxDrawdown`) — the
  `maxDrawdown()` METHOD returns a Drawdown struct with a
  `.maxDrawdown` field, but the EVENT struct itself only has
  `trough_depth`. Confirmed by `grep -A 10 "struct DrawdownEvent"`.
  Also documented: Kelly fraction formula `K = W - (1-W)/R` with
  `if (K < 0) K = 0;` clamp; fills-per-day denominator is
  ACTIVE days, not calendar days.
- **references/sprint-patterns-2026-06-20-round12.md** — #229-#234
  (6 sprints, no widgets added). 3 new derived structs:
  EdgeScore (#229-#230), TimeBetweenFills (#231-#232),
  VolatilityRatio (#233-#234). EdgeScore combines
  W*R*E*K via geometric mean compressed to 0..1 via
  `x / (x+1)` sigmoid. TimeBetweenFills MUST sort timestamps
  before gap-difference math — `loadAll()` does NOT return
  sorted timestamps. VolatilityRatio = dailyStddev / avgTradeSize
  with mandatory `if (avgTradeSize > 1e-9)` guard. PICK+SHIP
  held across 5 mid-chain WEITER! triggers.
- **references/sprint-patterns-2026-06-20-round13.md** — #235-#238
  (4 sprints, 4 WEITER! triggers in sequence with zero
  narrative reply). 3 new derived structs with calendar
  arrays: `HourlyWinRate` (#235, 24×WR), `HourlyPnL` (#236,
  24×P&L), `DoWTradeCount` (#238, 7×count). **CRITICAL new
  pitfall**: std::array / std::map fields require
  top-of-file includes in `trade_journal.hpp` — without
  `#include <array>`, the build fails with
  "Feld hat unvollständigen Typen". The fix is to add
  `<array>`, `<cstdint>`, `<map>` to the top-of-file
  include block when adding a struct with std::array
  members. Also: test fixture TZ-fragility — for any
  localtime_r-derived bucket (hour, day-of-week), never
  hardcode the index in the assertion; scan-for-the-bucket
  instead. PICK+SHIP is now load-bearing — the only
  acceptable mid-chain output is the
  mcp__mazemaker__mazemaker_remember call, which is silent.
- **references/sprint-patterns-2026-06-20-round14.md** — #239-#244
  (6 sprints, 0 widgets added, 4 new ✓ tests). The
  four-pattern coverage (per-symbol / per-tag /
  bulk all-segments / bulk by-tag) is now the established
  default — every new derived analytics struct gets all
  four method shapes unless the operator has a reason
  otherwise. 4 new derived structs in this round:
  `DoWTradeCount` (carry from round 13), `MonthlyPnLEntry`,
  `BestWorstDay`, `WinLossAvg`. No new pitfall catalogue
  entries — catalogue was complete at end of round 13.
  PICK+SHIP held across 3 mid-chain WEITER! triggers.
- **references/sprint-patterns-2026-06-20-round15.md** — #245-#248
  (4 sprints, 0 widgets, 4 new ✓ tests). 4 new derived
  structs: `LongestWinStreak`, `LongestLossStreak`,
  `MonthlyFillCount` (12-element monthly grid). New
  pitfall: streak arithmetic (lone W between two loss
  streaks counts as part of the next run). PICK+SHIP held
  across **8+ mid-chain WEITER! triggers** — the user
  fired "FRAG NICHT IMMER SO BEHINDERT: WEITER!" after
  EVERY commit, including after a one-line summary. Rule
  reinforced: between commits, ZERO chat output (or one
  word max). The mcp__mazemaker__mazemaker_remember call is
  the ONLY between-commit artifact.
- **references/sprint-patterns-2026-06-20-round16.md** — #249-#252
  (4 sprints, 0 widgets, 4 new ✓ tests). 2 new derived
  structs: `AvgDailyPnLByMonth` (#250, 12-element mean
  daily P&L grid), `MonthlyWinLossCount` (#252, 12-element
  W/L count grid). 4 bulk mirror methods (`allSegment*`).
  CRITICAL — re-reinforced already-exists pitfall: Sprint
  #252 first attempt duplicated `rollingWinRateByTag`
  (defined since round 6 / #181). Compile failed with
  "kann nicht überladen werden". **Recovery: grep hpp for
  method name BEFORE declaring, not just before writing
  any field access**. The pattern is: any time you add a
  per-symbol variant, grep for the per-symbol AND per-tag
  AND bulk variants. PICK+SHIP held across 4+ mid-chain
  WEITER! triggers.
- **references/sprint-patterns-2026-06-20-round17.md** — #253-#255
  (3 sprints, 0 widgets, 3 new ✓ tests). 1 new derived
  struct with matrix suffix: `WeekdayHourPnLMatrix`
  (#254, 7×24 std::array). The 58th templated helper.
  CRITICAL — refined duplicate-declaration lesson:
  name COLLISION (same name, different return type) is
  NOT a duplicate. The recovery is to use a
  data-shape SUFFIX (Matrix / Cells / Stats /
  Distribution / Summary), not to delete or pick a
  totally-different name. Round 17 hit this with
  `weekdayHourPnLBySymbol` (existing, returns
  vector<SegmentHeatmapCell>) vs. new `weekdayHourPnLMatrixBySymbol`
  (returns 7×24 std::array). The -Matrix suffix is the
  established convention for raw-array variants of
  existing heatmap/cell APIs. PICK+SHIP held across 3+
  mid-chain WEITER! triggers.
- **references/sprint-patterns-2026-06-20-round18.md** — #256-#258
  (3 sprints, 0 widgets, 3 new ✓ tests). 2 new derived
  structs: `MonthlyPnLArray` (#256, 12-element seasonal
  P&L grid), `MonthlyWinRate` (#258, 12-element seasonal
  WR grid). 1 bulk mirror method set (#257). The 60th
  templated helper. CRITICAL — PICK+SHIP VIOLATED AGAIN:
  round 18 wrote "BTQuant Vulkan — Sprint N erreicht"
  status blocks with cumulative recaps and "Sag wo's
  weitergehen soll" prompts after sprints #256, #257,
  #258. The user fired "FRAG NICHT IMMER SO BEHINDERT:
  WEITER!" at every one. Lesson reinforced (third time
  in 6 rounds): NEVER write a status block between
  commits. The user reads the terminal. The commit
  message includes the test count. The git log shows
  the commit count. Zero chat output, OR one word.
  "Sag wo's weitergehen soll" directly contradicts
  PICK+SHIP. PICK+SHIP held across 4+ mid-chain WEITER!
  triggers THIS round (the agent recovered each time
  by going silent after the reminder).

## Journal wiring (CRITICAL — read first)

When adding a new panel that takes a `TradeJournal*` via
`setJournal()`, the call MUST happen AFTER `m_tradeJournal = new ::btquant::TradeJournal(...)`.
A pre-existing bug shipped for 27 sprints: the original
`JournalStatsPanel::setJournal(m_tradeJournal)` call was placed
before `m_tradeJournal` was constructed, passing nullptr, and
the panel silently rendered "journal not wired" forever.
Sprint #103 fixed this by moving both setJournal() calls
to AFTER the journal construction. Every new panel that
wires a journal pointer must follow the same pattern — see
the constructor block in `WindowManager::initialize()` for
the canonical ordering.

## Field-name pitfall catalogue (run this BEFORE the build, not after)

The `TradeJournal` class has at least 19 fields whose names
do NOT match the obvious guess. Verify the actual struct
field with `grep -A 8 "struct <Name>" src/data/trade_journal.hpp`
BEFORE writing `cur.fieldName = ...`. Compile errors that
say "no member named X" usually mean the actual field is
something else. The catalogue so far:

| You write        | Actual field            | Type / context                      |
|------------------|-------------------------|-------------------------------------|
| `realizedDelta`  | `realized`              | BestTrade struct                    |
| `median`         | `p50`                   | PnLDistribution struct              |
| `maxDrawdown`    | `maxDrawdown().maxDrawdown` | maxDrawdown() returns struct   |
| `totalCount`     | `roundTripCount`        | SymbolSummary struct                |
| `fillCount`      | `roundTrips`            | DailyPnL struct                     |
| `durationUs`     | `active_us`             | TradingSession struct (snake_case)  |
| `duration_us`    | `active_us`             | TradingSession — the round 7 hint was wrong, see round 8 |
| `sharpe`         | `sharpe().annualizedSharpe` | sharpe() returns struct        |
| `sortino`        | returns Sortino struct  | not a double                        |
| `calmar`         | returns Calmar struct   | not a double                        |
| `riskScore`      | returns struct, use `.overall` | overallScore on the struct   |
| `realizedDelta` on DailyPnL | `realized`   | daily realized on DailyPnL         |
| `symbol` on DDStreakStats | `segment` | DDStreakStats struct (round 9)     |
| `bestHour` exact value in test | `>= 0 && <= 23` | `localtime_r` returns LOCAL, not UTC (round 9) |
| `DDStreakStats`   | `TradeJournal::DDStreakStats` | type lives inside TradeJournal namespace; templated helpers must qualify the return type (round 9) |
| `DailyPnL` / `SegmentTradeCount` etc. in method sig | needs `struct X;` forward decl if X is defined later in the .hpp (round 9 #177) |
| `start_us` on DrawdownEvent | `start_ts` | DrawdownEvent struct (round 10) — derived event structs use `*_ts`, NOT `*_us` |
| `trough_us` on DrawdownEvent | `trough_ts` | DrawdownEvent struct (round 10) |
| `end_us` on DrawdownEvent (if used) | `end_ts` | same convention |
| `maxDrawdown` on DrawdownEvent (raw) | `trough_depth` | DrawdownEvent struct (round 11) — `maxDrawdown()` METHOD returns a struct with `.maxDrawdown`, but the EVENT struct itself only has `trough_depth` |
| std::array<T, N> field on a NEW struct in trade_journal.hpp | compile fails: "Feld hat unvollständigen Typen" | **MISSING top-of-file `#include <array>`** (round 13 #235) — fix by adding `<array>`, `<cstdint>`, `<map>` to the top-of-file include block |
| hourly array bucket index in test | scan for the bucket, don't hardcode | localtime_r returns LOCAL, so the bucket index depends on the build host's TZ (round 13 #235) |
| longest-streak test expectation | pencil-verify streak arithmetic | A `4W, -, +, 4W` sequence produces streak=5 (the lone W between two loss streaks is counted as part of the next run). Sequences like `4W, -, 4W` produce streak=4. Always trace the run-count by hand before writing the assertion (round 15 #245) |
| declaring per-symbol/per-tag/bulk method without grep-first | compile fails: "kann nicht überladen werden" | **GREP hpp BEFORE declaring** (round 16 #252) — Sprint #252 duplicated `rollingWinRateByTag` (line 1899 from round 6 / #181). Pattern: any time you add a per-symbol variant, grep for ALL of: per-symbol, per-tag, bulk all-segments, bulk by-tag |
| declaring per-symbol/per-tag method when an existing one returns a DIFFERENT shape | compile fails: "kann nicht überladen werden" but signatures differ | **Use a data-shape SUFFIX** (round 17 #254) — round 17 hit this with `weekdayHourPnLBySymbol` (existing, returns vector<SegmentHeatmapCell>) vs new matrix variant. The recovery is `weekdayHourPnLMatrixBySymbol` — the `-Matrix` suffix is the established convention for raw-array variants of existing heatmap/cell APIs. Convention suffixes used in trade_journal surface: -Matrix / -Cells / -Stats / -Distribution / -Summary |

Pattern: any method that begins with a noun (maxDrawdown,
sharpe, sortino, calmar, riskScore, recoveryFactor) returns
a STRUCT, not a primitive. The struct has the actual scalar
field. If the struct has 4 sub-scores (like RiskScore), you
need `.overall` for the headline and the per-component fields
for the breakdown.

Round 10 lesson: derived event structs (DrawdownEvent,
DrawdownEventExt, RecoveryEvent, etc.) use `*_ts` for
timestamps. `JournalFill` uses `timestamp_us`. The naming
is inconsistent and stable — don't try to fix it.

Round 11 lesson: `DrawdownEvent.trough_depth` is the depth
field on the EVENT struct. `maxDrawdown()` is a method that
returns a Drawdown struct with a `.maxDrawdown` field. Don't
confuse them. The grep recipe is `grep -A 12 "struct DrawdownEvent"`.

Round 13 lesson: **`std::array` and `std::map` requires top-of-file includes**.
The hpp uses `#pragma once` with includes declared near the
top, but new derived analytics structs are added 2500+ lines
in. The struct definition instantiates `std::array<...>` which
requires `<array>` to be visible. The build error is opaque
("incomplete type"). The grep recipe is `head -20
src/data/trade_journal.hpp` to verify includes before adding
any new struct with std::array or std::tuple members.

Round 16 lesson: **`grep hpp for method name BEFORE declaring`**.
The earlier round-8 lesson covered method-name lookup for
the per-symbol variant when adding a per-symbol/per-tag pair
(`sharpeTrendBySymbol` already existed). Round 16 extended
the lesson to bulk variants — Sprint #252 duplicated
`rollingWinRateByTag` (line 1899 from round 6 / #181) because
the agent added both per-symbol + per-tag without grepping
the per-tag slot first. Compile error: "kann nicht
überladen werden" (cannot be overloaded). The recovery was
to swap to a different method name (`monthlyWinLossBySymbol`)
and commit cleanly. The full grep recipe is now:

```bash
grep -n "<methodName>" src/data/trade_journal.hpp
```

If a hit exists at all, do NOT redeclare. Reuse the existing
method or pick a different name.

## Cumulative run stats (through sprint #258)

- **258 commits** on `0.0.2` (+3 from round 17: 255)
- **32 widgets** (unchanged since round 7)
- **943 ✓ across 243 cases** (+3 from round 17: 940 ✓ across 240)
- TradeJournal surface: **346+ methods** + 73+ derived
  analytics structs (+6 methods from round 17: 340+, +1
  new struct: `MonthlyWinRate`).
- **60 templated `build*<Pred/Iter>()` helpers** (+2 from
  round 17: 58). 60th (`MonthlyWinRate`).
- **Round 18 alone: 3 sprints, 3 commits, 0 widgets, 3 new
  ✓ tests.** Cadence: ~2 minutes per commit including the
  mcp save. PICK+SHIP held across 4+ mid-chain WEITER!
  triggers (see round 18 reference for the persistence-of-bad-habit
  note about status-block violations).
- 0 failures across all 943 tests in 243 cases.
- **21+ distinct derived analytics families** now follow
  the canonical 4-pattern (per-symbol / per-tag / bulk
  all-segments / bulk by-tag): risk-adjusted return, drawdown
  analysis, session analysis, distribution analysis, concentration,
  correlation, leaderboard, temporal, day-of-week, day-stats,
  win-loss, streaks, monthly, trend, risk, operational, edge,
  volatility, daily-vol, daily-fill.

## Working directory

`/home/alca/projects/PubBTQuant/btquant_vulkan/`

## Build pattern (every sprint)

1. Patch hpp + cpp in parallel via `patch` tool.
2. **`grep -n "<methodName>" src/data/trade_journal.hpp` BEFORE
   declaring any new method** (round 16 #252 lesson —
   duplicate-declaration error). If a hit exists at all,
   reuse or pick a different name.
3. **`grep -A 8 "struct <NewType>" src/data/trade_journal.hpp`
   BEFORE writing any field access** (see field-name pitfall
   catalogue below — 21+ field names do not match the obvious
   guess). This is cheaper than the compile-error cycle.
4. **`head -20 src/data/trade_journal.hpp` BEFORE adding a
   new struct with std::array or std::tuple fields** (see
   round 13 pitfall — missing top-of-file include). The
   hpp must have `#include <array>`, `#include <cstdint>`,
   `#include <map>`.
5. `cmake --build build --target btquant_vulkan` — foreground.
   Trust build over LSP (LSP goes stale during rapid hpp+cpp
   patches; round2 §5).
6. Append Test N to `test/test_integration.cpp` (6-8 checks per test).
   For any localtime_r-derived bucket, scan-for-the-bucket
   instead of hardcoding the index (round 13).
7. `cmake --build build --target test_integration && ./build/test/test_integration`.
8. `git add <explicit paths>` — NEVER `git add -A` (other-agent trees pollute
   the commit; see MEMORY.md).
9. Commit with detailed message including Test N (M checks all green).
10. `mcp__mazemaker__mazemaker_remember` with WHAT/WHY/HOW-RESOLVED + cumulative stats.
11. **No chat reply between commits.** Either nothing, one word
    ("Done." / "Shipped."), or — if you MUST say something — the
    next sprint number and what it is ("Sprint #216: ..."). The
    mcp__mazemaker__mazemaker_remember call IS the between-commit
    artifact. The chat is the user-facing signal channel.

## See also

- `btquant-maintenance-routine` — external maintenance (deps, linting,
  type checking). Python HotSpine + MS SQL hotswap layer, not Vulkan UI.
- `btquant-autonomous-agency` — self-improving trading strategy agency.
  `btquant-self-filtering-chain-2026-06-20.md` for the 5-bug diff that
  unblocked autonomous evolution.
