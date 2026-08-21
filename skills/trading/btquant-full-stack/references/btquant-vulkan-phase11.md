# BTQuant Vulkan Phase 11 — Risk Metrics, Connection Panel, Profile Manager, Symbol Picker

## Overview

Phase 11 closed four Phase 10 "Open / next" items and added one
cross-cutting capability (the Ctrl+P command palette / symbol picker).
Seven commits shipped in three sub-sprints within one extended session.

| Commit       | Widget / Feature                 | Lines | Role                                                              |
|--------------|----------------------------------|-------|-------------------------------------------------------------------|
| `d24a84ff`   | AlertsPanel                      | ~195  | Phase 10 carryover — price-move + volume-spike detector + bell   |
| `89309b29`   | WatchlistWidget                  | ~535  | Phase 10 carryover — multi-symbol sparkline ticker               |
| `98d51cc9`   | LogPanel + BTQ_LOG_* macros      | ~530  | Phase 10 carryover — thread-safe ring buffer + variadic macros   |
| `49001cda`   | RiskPanel metrics expansion      | ~270  | Sharpe / max DD / win rate / profit factor / expectancy          |
| `270b9f8a`   | ConnectionPanel                  | ~200  | Spine status: LIVE/SYNTHETIC/DISCONNECTED + tick-rate EWMA       |
| `91d5be8f`   | ProfileManager                   | ~330  | Save-as / list / delete / reload named layouts                   |
| `1b4478a5`   | SymbolPicker (Ctrl+P)            | ~190  | Modal symbol palette with substring filter + arrow nav           |

Total: ~2250 lines of new widget code, 16 → 17 tests (Test 11-17 each
covering 4-9 invariants). Build + smoke clean at every commit.

## Cross-cutting additions this phase

### MarketDataProcessor accessor extension (required for ConnectionPanel)

`ConnectionPanel` needs spine-state metrics that aren't in `Snapshot`.
The fix is small: add four read-only accessors + two atomic counters.

```cpp
// market_data_processor.hpp
const std::string& sourcePath() const noexcept { return m_sourcePath; }
const std::string& symbol    () const noexcept { return m_symbol; }
uint64_t           ticksSeen () const noexcept { return m_ticksSeen.load(...); }
uint64_t           parseErrors() const noexcept { return m_parseErrors.load(...); }
```

`start(path, interval_ms)` resets both counters to 0 and stores
`m_sourcePath = path`. The run loop's both-branches (real-spine read
AND synthetic fallback) call `m_ticksSeen.fetch_add(1, relaxed)` on
every aggregated tick. Test 15 verifies the accessors + that
`ticksSeen() > 0` after 300 ms with synthetic fallback.

### WindowManager::captureCurrentSettings() (required for ProfileManager)

`ProfileManager` saves the current state. Without a snapshot helper,
every callsite would have to enumerate all 14 toggle fields. The
clean fix:

```cpp
util::Settings WindowManager::captureCurrentSettings() const {
    util::Settings s;
    s.showOrderBook      = showOrderBook;
    s.showOrderBookDepth = showOrderBookDepth;
    // ... 11 more fields ...
    s.theme              = theme;
    s.heatmapDensity     = heatmapDensity;
    return s;
}
```

Then `ProfileManager` holds a `CaptureFn` (std::function<util::Settings()>)
that defaults to calling WM::captureCurrentSettings. The ProfileManager
test (Test 16) doesn't exercise the WM lambda (no ImGui context); it
just verifies `saveCurrentAs(name)` writes a file with the captured
state. Reusing `applyPreset(loaded)` for the Load button means the
load path doesn't need its own helper.

### Push-only vs setMarketData API split (NEW widget plumbing pattern)

Phase 11 widgets split into two API styles:

- **Pull model** (AlertsPanel, ConnectionPanel, RiskPanel): WM owns the
  MarketDataProcessor ptr and calls `widget->setMarketData(data)` in
  `WindowManager::setMarketData`. The widget reads fresh state in
  `render()`. This is the Phase 4 pattern.
- **Push model** (WatchlistWidget): WM has no setMarketData hook. Instead
  WM exposes `updateWatchlist(symbol, price, size, isBuy, ts)` which
  main.cpp's render loop calls per-frame with the most-recent trade.
  The widget doesn't poll. Comment in WM::setMarketData makes this
  explicit:

```cpp
if (m_alertsPanel) m_alertsPanel->setMarketData(data);
if (m_connectionPanel) m_connectionPanel->setMarketData(data);
// Watchlist uses push-only API (WindowManager::updateWatchlist) — no
// setMarketData hook needed.
```

Future symbol routing would shift Watchlist to pull model once the
multi-symbol spine lands.

### `Settings::save(path)` is the right call for profile persistence

First attempt routed through `util::Settings::profilePath(name)` which
returns a path under `~/.config/btquant_vulkan/profiles/`. That broke
the test that wanted a temp dir. Fix: ProfileManager uses its own
`m_profilesDir` (default: `Settings::profilePath("").parent_path()`,
overrideable for tests) and applies its own path-traversal sanitizer
inline. Don't invent `saveToProfile` — `save(path)` already does what
you need.

## Pitfalls discovered in Phase 11

### 1. Test data ordering for newest-first trade vectors

`MarketDataProcessor::snapshot(N).recent_trades` is newest-first:
`front()` = newest tick, `back()` = oldest. `computeMetrics()` walks
via `rbegin()/rend()` to get chronological order.

**The pitfall**: writing the test with `for (int i = 0; i < N; ++i)`
pushes the lowest-priced tick first → `front()` ends up the OLDEST.
When `computeMetrics` walks rbegin (oldest first), every "consecutive
return" is `(older - newer) / newer` = negative on a monotonic-up
series. Sharpe comes out NEGATIVE, maxDrawdown = N-1.

**Fix**: push in REVERSE order for any test that uses monotonic data:

```cpp
for (int i = N - 1; i >= 0; --i) {
    Trade t{};
    t.price = base + i;  // highest price pushed FIRST → becomes front()
    trades.push_back(t);
}
```

This is the canonical fixture for any future metric test (Sortino,
Calmar, Information Ratio). Document it in the metric test header.

### 2. Duplicate struct in cpp/hpp after sibling subagent edit

When a sibling subagent rewrites `risk_panel.cpp` and adds an internal
`struct PositionState { ... }` inside the TU, and you subsequently
add the same struct to `risk_panel.hpp`, you get a duplicate. The
compiler reports "no declaration matches" when the cpp's `static
PositionState computePosition(...)` tries to use the local struct.

**Fix sequence** when refactoring a sibling-modified file:
1. `grep -n "struct PositionState\|struct X" file.cpp` to find any
   internal struct definitions
2. Delete the duplicate from the cpp (`patch` with 5 lines of context
   above + below)
3. Drop the `static` keyword on the cpp definition if the hpp declares
   it without `static` — mismatched linkage/storage is also an error
4. Add `#include "../data/market_data.hpp"` to the hpp if the hpp
   parameter types reference `btquant::data::Trade` (forward-decl at
   global scope is NOT enough for `std::vector<btquant::data::Trade>`)

### 3. Path-traversal sanitizer for user-named file writers

When a widget exposes a "Save as…" text input that writes to
`m_dir / (name + ".ini")`, reject:
- empty name
- `/` or `\` (subdirectory traversal)
- `..` (parent directory traversal)
- embedded NUL

Settings::profilePath does this; reusing it forces the path under
the global config dir and breaks tests with custom tmpDirs. Inline
the check:

```cpp
if (name.empty()) return false;
if (name.find('/')  != std::string::npos) return false;
if (name.find('\\') != std::string::npos) return false;
if (name.find("..") != std::string::npos) return false;
if (name.find('\0') != std::string::npos) return false;
```

Test 16 verifies `../escape` is rejected, empty string is rejected,
and a normal name writes a real file.

### 4. `BTQ_LOG_*` macro requires the header to be included

The macros live in `src/widgets/log_panel.hpp`. If `src/main.cpp`
calls `BTQ_LOG_INFO(...)` before `#include "widgets/log_panel.hpp"`,
the compiler reports "Use of undeclared identifier 'BTQ_LOG_INFO'".
Always include the header in any TU that calls the macros.

### 5. Patching inside a sibling-modified for-loop body

When a sibling subagent rewrites `market_data_processor.cpp::runLoop()`,
the `for (const auto& e : entries) { ... }` loop body has a specific
shape (lines 59-66). My patch to add `m_ticksSeen.fetch_add(1)`
closed the for-loop with an extra `}`, leaving the next 4 statements
(`synthBid = e.bid_price; ...`) as orphan code. The compiler reports
"undeclared identifier 'e'" and "else without previous if" cascading.

**Fix**: always re-read the function body (offset/limit pagination)
before patching inside a sibling-modified file. Better: use `patch`
with the loop's full body as `old_string` so the patcher can't
mismatch brace boundaries.

### 6. SymbolPicker modal popup sequencing

`ImGui::OpenPopup("name")` MUST be called in the same frame as
`ImGui::BeginPopupModal("name", ...)`. If you call `setOpen(true)`
from a hotkey handler but `OpenPopup` is inside the widget's `render()`,
the popup opens on the NEXT frame (because `setOpen` is read inside
`render()` and triggers `OpenPopup` for that frame's `BeginPopupModal`).

Better pattern: in `render()`, call `ImGui::OpenPopup("Symbol Picker")`
unconditionally when `m_open` is true. `BeginPopupModal` returns false
on the first frame after the popup is queued (no window yet), and
true on subsequent frames.

### 7. SymbolPicker state reset on close

When the user picks a symbol OR clicks Cancel, `m_open` flips to false.
The input buffer (`m_input[64]`), filter (`m_filter`), selected index,
and `firstAppear` flag need to be reset BEFORE the next `setOpen(true)`,
otherwise stale state lingers. Reset happens inside the
`if (!m_open) { ... }` block at the bottom of `render()`.

Test 17 verifies open/close toggle and that the select callback is NOT
invoked without UI (proving the callback wiring is sound and not
spuriously firing during construction).

## WEITER workflow reinforcement (Phase 11 signals)

In this extended session, the user issued "FRAG NICHT IMMER SO BEHINDERT:
WEITER!" four times. Existing workflow section in the umbrella already
captures this trigger phrase. The Phase 11 session is the largest
demonstration yet that this is a STABLE preference, not a one-off
frustration. Concrete behavior that worked:

- Each "FRAG NICHT IMMER SO BEHINDERT" → immediately pick the next
  widget from "Open / next", execute the full 5-7 step recipe,
  commit, report, pick the next.
- Never end a turn with "Soll ich X oder Y?" — that IS the
  ask-bombing antipattern.
- After 3 commits, save a status memory so the next session can
  resume from a known point.
- The user did NOT respond to intermediate reports (AlertsPanel done,
  Watchlist done, etc.). They expect the next item immediately.

## Open / next (Phase 12 candidates)

In priority order:

1. **Multi-symbol spine wireup** — add `setSymbol(string)` on
   MarketDataProcessor, parse the symbol field from the wire format,
   make ConnectionPanel + Watchlist + AlertsPanel all read the active
   symbol and filter accordingly. Touches the spine, the processor,
   3 widgets, and main.cpp.

2. **RiskPanel time-of-day grouping** — current RiskPanel computes
   window-scoped metrics. Add `dailyPnL` from grouping trades by
   trade.timestamp_us / 86400000000. ~50 lines.

3. **Order entry widget stub** — a `OrderEntry` panel with a side
   selector, size input, price input, submit button (no-op stub for
   now). Hook into the BTQ_LOG pipeline so submit logs an intent.
   ~200 lines.

4. **ChartPanel port (trimmed)** — pick the most useful 600 lines from
   chart_panel.cpp (candlestick + VWAP + volume subplot). Use the
   ImGui::PlotLines / ImPlot path. Existing MultiVWAP widget already
   does the VWAP math; reuse it.

5. **LogPanel file sink** — `enableFileSink(path)` writes the ring
   buffer to a rotating log file. Useful for crash postmortem.
   ~100 lines.

6. **Hotkey customization dialog** — let the user map a hotkey to any
   menu item. Replaces the static `kHotkeys[]` table with a key→action
   map persisted in settings.ini.

7. **ImGui theme customizer** — color picker for ImGui style colors
   (frame bg, text, accent, etc.) persisted alongside the theme enum.
   ~250 lines.

## Files touched in Phase 11

```
btquant_vulkan/src/widgets/risk_panel.hpp             (RiskMetrics + computeMetrics decl)
btquant_vulkan/src/widgets/risk_panel.cpp             (computeMetrics + render section)
btquant_vulkan/src/widgets/connection_panel.hpp       (new)
btquant_vulkan/src/widgets/connection_panel.cpp       (new)
btquant_vulkan/src/widgets/profile_manager.hpp        (new)
btquant_vulkan/src/widgets/profile_manager.cpp        (new)
btquant_vulkan/src/widgets/symbol_picker.hpp          (new)
btquant_vulkan/src/widgets/symbol_picker.cpp          (new)
btquant_vulkan/src/data/market_data_processor.hpp     (4 accessors + 2 atomic counters + 2 string members)
btquant_vulkan/src/data/market_data_processor.cpp     (start() resets counters + stores path; runLoop increments ticksSeen)
btquant_vulkan/src/ui/window_manager.hpp              (3 widget ptrs + 3 show* + 3 flags + captureCurrentSettings)
btquant_vulkan/src/ui/window_manager.cpp              (10 additions: includes, ctor new ×3, dtor delete ×3, show* ×3, View menu ×3, hotkey Ctrl+P, captureCurrentSettings impl)
btquant_vulkan/src/main.cpp                           (3 show*Window calls + 1 BTQ_LOG_INFO + Watchlist push)
btquant_vulkan/CMakeLists.txt                         (4 .cpp + 4 .hpp added)
btquant_vulkan/test/CMakeLists.txt                    (4 .cpp added -- link-error fix)
btquant_vulkan/test/test_integration.cpp              (4 Test blocks, ~50 invariants)
```

Total: 16 files, ~2250 lines net new, 7 commits, 17 tests green.