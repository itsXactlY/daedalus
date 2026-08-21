# Sprint patterns #103–#111 (round 6)

Two new widgets, three time-series families, and a critical
journal-wiring bug fix. The shape of the work: implement what
the previous sprint implies — heatmap data → heatmap widget,
equity-curve data → equity-curve widget, calendar data →
calendar UI, time-series data → rolling analytics → chart
overlay. Each widget unblocked the next method.

## 1. Journal wiring bug fix (CRITICAL — read first)

**The bug.** For 27 sprints (Sprint #67 → #100), the WindowManager
constructor called `m_journalStatsPanel->setJournal(m_tradeJournal)`
BEFORE `m_tradeJournal = new ::btquant::TradeJournal(...)`. The
early call passed nullptr, the conditional `if (m_tradeJournal)`
skipped the null case, and the JournalStatsPanel rendered
"journal not wired" forever — silently. Every test against
the journal passed because the tests construct a journal
directly without going through WindowManager.

**The fix (Sprint #103).** Move both `setJournal()` calls to
AFTER the journal construction:

```cpp
m_journalStatsPanel = new JournalStatsPanel();   // no setJournal here
m_pnlHeatmapPanel   = new PnLHeatmapPanel();
m_equityCurvePanel  = new EquityCurvePanel();
// ... (later, after m_tradeJournal is constructed)
m_tradeJournal = new ::btquant::TradeJournal(journalPath);
if (m_journalStatsPanel) m_journalStatsPanel->setJournal(m_tradeJournal);
if (m_pnlHeatmapPanel)   m_pnlHeatmapPanel->setJournal(m_tradeJournal);
if (m_equityCurvePanel)  m_equityCurvePanel->setJournal(m_tradeJournal);
```

**Why this keeps biting.** Adding a new journal-backed widget
means adding another `setJournal()` call. Future sessions
will instinctively put it next to the `new`. Don't. Put it
in the "wiring after construction" block — same pattern
for every journal-backed panel. If you find yourself writing
`m_xxxPanel = new XxxPanel(); m_xxxPanel->setJournal(m_tradeJournal);`
in the same line, you're at the bug.

## 2. Widget wiring checklist (4+ places)

Every new widget touches this many files / functions:

1. `src/widgets/xxx_panel.hpp` — header
2. `src/widgets/xxx_panel.cpp` — impl
3. `CMakeLists.txt` — add to app sources
4. `test/CMakeLists.txt` — add to test sources (linking test
   binaries against new symbols)
5. `src/util/hotkey_config.hpp` — `enum class HotkeyAction`
   value (bump COUNT)
6. `src/util/hotkey_config.cpp` — default binding in
   `HotkeyMap::defaults()` + `actionName()` case
7. `src/ui/window_manager.hpp` — forward decl + member
   pointer + `showXxx` flag + `showXxxWindow()` method decl
8. `src/ui/window_manager.cpp` — `#include` + `new XxxPanel()`
   in init + `delete m_xxxPanel` in dtor + `setJournal` after
   journal construction + `case HA::ToggleXxx` in hotkey
   dispatch + `void WindowManager::showXxxWindow()` impl +
   View menu item (`MenuItem("Xxx (Ctrl+?)")`) + `display()`
   entry in hotkey reference
9. `src/main.cpp` — `windowManager.showXxxWindow()` in render
   loop

Items 5-9 only exist for togglable widgets (visible/hidden).
Data-display widgets (rendered always) skip the hotkey path.

**Hotkey conflict resolution.** Ctrl+H is HotkeyEditor. Ctrl+J
is JournalStats. Ctrl+E is EquityCurve. Ctrl+Shift+H is
PnLHeatmap. When adding a new binding, grep for the target
key in `hotkey_config.cpp` first.

## 3. Tabbed JournalStatsPanel (Sprint #108)

Panel grew to 15+ sub-sections — flat CollapsingHeaders didn't
scale. Sprint #108 wrapped the existing structure in 3 tabs
without moving any sections:

```
ImGui::BeginTabBar("JournalStatsTabs", ...)
  if (ImGui::BeginTabItem("Overview")) {
    // existing Stats / Risk / Streaks / Risk-Adjusted
  } ImGui::EndTabItem();
  if (ImGui::BeginTabItem("Breakdowns")) {
    // existing By symbol / By tag / By day / per-axis risk
  } ImGui::EndTabItem();
  if (ImGui::BeginTabItem("When I trade")) {
    // existing Calendar tables
  } ImGui::EndTabItem();
ImGui::EndTabBar();
```

**Pitfall — DON'T MOVE SECTIONS.** The first instinct is to
move per-symbol tables out of Breakdowns into a new
"By Symbol" tab. Don't. Moving CollapsingHeaders between
tabs requires moving their full bodies (the `if (...) { ... }`
block including the inner table setup) and risks breaking
the indentation. Wrapping in-place is mechanical and
reversible. Add new tabs to move sections LATER if needed.

**Active tab persistence.** Add a `Tab m_activeTab` enum
field + `m_activeTab = Tab::X;` assignment inside each
`BeginTabItem()` call. Pass `ImGuiTabItemFlags_SetSelected`
when `m_activeTab == Tab::X` so the chosen tab opens
first on panel reopen.

## 4. Calendar analytics — day-of-week + hour-of-day (Sprint #106)

Two pairs of methods, identical structure:

```
perSymbolDayOfWeekStats() → { symbols[], grid[symbols.size()*7] }
perSymbolHourOfDayStats() → { symbols[], grid[symbols.size()*24] }
perTag{DOW,HourOfDay}Stats(b) — same with tags, honor includeUntagged
```

Bucket struct:
```cpp
struct DayOfWeekBucket {
  size_t roundTrips = 0;
  size_t wins       = 0;
  size_t losses     = 0;
  double realized   = 0.0;
};
```

**Local-time, not UTC.** `tm_wday` and `tm_hour` come from
`localtime_r(&secs, &tm)` — the trader's calendar, not
Coordinated Universal Time. Day-of-week shifts when the
trader travels. Acceptable for v1; flagging for Sprint #113+
if multi-tz support is needed.

**Tag filter pitfall.** `includeUntagged` rolls untagged fills
under `"__untagged__"`. Don't fall through with empty-key
filtering — every caller needs to decide explicitly.

## 5. Time-series: equity curve + drawdown + rolling Sharpe (Sprint #104, #109, #110)

Three methods + one widget enhancement:

```
equityCurve()           → [EquityPoint]   per-fill cumulative
equityDrawdownSeries()  → [DrawdownPoint] per-fill peak + drawdown
dailyPnLSeries()        → [DailyPnL]      per-day bucketing
rollingSharpe(N=30)     → [RollingSharpePoint] rolling window
```

**CRITICAL: zero-fill semantics.** `rollingSharpe` zero-fills
calendar gaps so the rolling window aligns with calendar
days, not days-with-fills. This means:

- 3 fills on days D-10, D-5, D-0 → `dailyPnLSeries` has 3
  entries BUT `rollingSharpe(2)` returns `(11 calendar days)
  - 2 + 1 = 10 points`.
- Tests must compute `span_days + 1 - window`, NOT
  `input.size() - window + 1`.

**Localtime_r arg order — got it wrong TWICE.**
Signature is `localtime_r(const time_t *timep, struct tm *result)`.
The first call was `localtime_r(&tm, &t)` — wrong direction.
Fixed in Sprint #106 (helper) AND Sprint #109 (fmtDay).
When writing any new time-conversion helper, double-check
the signature. POSIX: result is the second arg. MSVC
`localtime_s` is reversed: result is the first arg.

**Implementation.** `bucketByDay<>` template helper used by
all three daily-series methods. `computeRollingSharpe<>` shared
between `rollingSharpe()` and `rollingSharpeBySymbol()`. The
whole-journal daily variant uses a sentinel key (`"$all"`)
because the helper skips empty keys (used by perTag's
"skip untagged" path).

## 6. BestTrade / worstTrade (Sprint #111)

Single template helper drives all 6 methods:
```cpp
template <typename FilterFn>
TradeJournal::BestTrade
extremeTrade(const std::vector<JournalFill>& fills,
             FilterFn filter,
             bool findMax) {
  // walk fills, apply filter, track running max/min
}
```

The filter closure is the only thing that varies between
the 6 methods. Per-tag filters honor `includeUntagged`.
Per-symbol filters use simple `f.symbol == symbol`.

**Empty-journal sentinel.** Returns a default-constructed
`BestTrade` (all zeros, empty strings, ts=0). The caller
tests for emptiness via `b.realized == 0 && b.symbol.empty()`.

## 7. Test-fixture design patterns (gotchas)

Three traps caught during #103-#111:

**a) Timezone-fragile hour fixtures (Sprint #106).** First
attempt hardcoded `tm_anchor.tm_hour = 14` then mktime'd it.
Result depended on system TZ — UTC system stored as hour 14,
but the test read back hour X. Fix: read `anchorHour` back
from `localtime_r` on the same anchor:
```cpp
int anchorHour = tm_anchor.tm_hour;
// ...store mktime(tm_anchor) in ts...
// The bucket that ends up with the fill is at hour = anchorHour,
// because mktime + localtime_r round-trip preserves it.
```

**b) Sparsity assertions on too-few distinct dates (Sprint
#102).** First sparse-grid fixture had 2 distinct dates
(days -3 and -1) — the test asserted 3 dates including a
"sparse middle" that didn't exist. Fix: add a 3rd symbol
that fills the middle date so the union has 3 dates and
the target row's middle cell is genuinely sparse.

**c) Field name typo (Sprint #105).** `stats()` returns
`Stats.roundTripCount`, NOT `Stats.roundTrips`. Test had to
rename. Always check the struct field name in `trade_journal.hpp`
before writing the test.

## 8. Stats struct — field names

```cpp
struct Stats {
  size_t fillCount      = 0;
  size_t roundTripCount = 0;   // NOT roundTrips
  size_t winCount       = 0;
  size_t lossCount      = 0;
  double winRate        = 0.0;
  double avgWinner      = 0.0;
  double avgLoser       = 0.0;
  double profitFactor   = 0.0;
  double expectancy     = 0.0;
  double netRealized    = 0.0;
};
```

**PITFALL:** Tests must use `roundTripCount`, not `roundTrips`.

## 9. Stats invocations on round 6 methods

- `Σ perSymbolDayStats().grid[].roundTrips == stats().roundTripCount`
  (every round-trip in exactly one (symbol, date) bucket)
- `Σ perSymbolDayOfWeekStats().grid[].roundTrips == stats().roundTripCount`
  (same for (symbol, weekday))
- `Σ perSymbolHourOfDayStats().grid[].roundTrips == stats().roundTripCount`
  (same for (symbol, hour))
- `Σ dailyPnLSeries().realized == stats().netRealized` AND
  `Σ dailyPnLSeries().roundTrips == stats().roundTripCount`
  (every round-trip in exactly one calendar day)
- `Σ recentStreaks.length == stats().roundTripCount` (Sprint #105)

These invariants catch bugs where a method silently drops or
doubles counts.

## 10. LSP errors during rapid hpp+cpp edits

When patching both the header (new struct declarations) and
the .cpp (definitions) in quick succession, the LSP can go
stale — reporting errors that the actual compiler doesn't
emit. **Always trust the actual build output over LSP.**

Two specific cases this round:
- Sprint #106 LSP complained about `PerSymbolDayOfWeekStats`
  being undeclared in `.cpp` — but the actual `cmake --build`
  succeeded. The LSP hadn't reparsed the .hpp diff yet.
- Sprint #107 LSP complained about a missing `<functional>`
  include — but it was already there. Stale cache.

Pattern: if the build succeeds and the test passes, ignore
the LSP. If the build fails, debug from compiler output.

## 11. Hotkey numbering convention

When adding a new `HotkeyAction` enum value:

```cpp
ToggleFoo = N,    // next sequential number
COUNT = N+1,      // bump COUNT
```

Don't reuse retired numbers (compiles fine but breaks
persisted hotkeys.ini files). HotkeyMap::defaults() provides
a default binding; `actionName()` switches on the enum.
The persisted `hotkeys.ini` is keyed by `actionName()` strings
so renaming a value preserves user customizations across
versions.