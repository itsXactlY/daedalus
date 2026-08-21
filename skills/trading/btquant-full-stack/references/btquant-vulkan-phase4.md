# btquant_vulkan Phase 4 — Order-Flow Widgets + ImPlot API Gotchas

## Context

Fourth session on the `btquant_vulkan/` rebuild (2026-06-20). After
Phase 3 wired 5 widgets (OrderBook / DOM / Trades / TPO / Heatmap) to
the live `MarketDataProcessor` and added per-minute OHLCV candle
aggregation, the user asked for 5 order-flow analysis widgets in one
shot (the "1, 2, 3, 4, 5" response to a numbered proposal = "do all
of them"):

| # | Widget | Data source | Output |
|---|---|---|---|
| 1 | `OrderBookDepthWidget` | `snap.order_book` | Ladder + cumulative-depth bars + imbalance gauge + microprice |
| 2 | `FootprintWidget` | `snap.recent_trades` | bid@ask cluster cell-grid (candle × preis) |
| 3 | `VPVRWidget` | `snap.recent_trades` | Volume profile with POC + VAH/VAL (70%) + VWAP line |
| 4 | `MultiVWAPWidget` | `snap.recent_trades` | VWAP-20/50/100/200/all with line chart + summary table |
| 5 | `RiskPanel` | `snap.recent_trades` | Position (LONG/SHORT/FLAT) + unrealized + realized + total P&L |

Result: 5 new widget .hpp+.cpp pairs, 30 files changed, +1329 lines,
5 commits (`2d503e85`…`88fa3b5f`). All wired through the same
`setMarketData(::btquant::MarketDataProcessor*)` pattern from Phase 3.

For Phases 1–3, see `references/btquant-vulkan-rebuild-fixes.md` and
`references/btquant-vulkan-phase3.md`. This file documents ONLY the
new patterns and gotchas from Phase 4.

## 27. `MarketSnapshot` data-source map (canonical reference for any future widget)

After Phase 3, `Snapshot` carries everything a widget needs. The
mapping below is the contract — if you add a new `data::*` field,
update this table and add a getter to `MarketDataProcessor::snapshot()`.

| Snapshot field | Type | Used by | When to use |
|---|---|---|---|
| `snap.order_book` | `data::OrderBook` (top-N bids + asks with sizes) | OrderBook, OrderBookDepth | Display top-of-book ladder, depth bars, imbalance |
| `snap.recent_trades` | `std::vector<data::Trade>` (last N ticks, microsecond timestamps, bid_size/ask_size) | Trades, Footprint, VPVR, MultiVWAP, RiskPanel | Per-tick analysis: footprint clustering, VWAP rolling sums, position entry/exit, volume-profile bucketing |
| `snap.recent_candles` | `std::vector<data::Candle>` (bucket-aligned OHLCV+buyVol+sellVol+delta) | TPO, Heatmap (future) | Aggregated minute-bucketed view; cheap to iterate, no per-tick folding |
| `snap.current_candle` | `const data::Candle*` (in-progress bucket, null if empty) | TPO, Heatmap (future) | The "live" candle being built — append with `*` marker |
| `snap.snapshot_seq` | `uint64_t` (increments on every push) | All widgets | Detect "no data yet" (== 0) vs live |

`snapshot(N)` returns the last N trades; `snapshot(N, M)` returns the
last N trades AND the last M candles. Default 1 trade, 60 candles.

## 28. Widget skeleton recipe (canonical 6-file add)

Adding a new widget is six mechanical steps. Total ~250 lines for a
non-trivial widget like Footprint or VPVR.

### Step 1: `src/widgets/<name>.hpp`
```cpp
#pragma once
#include "ui_context.hpp"            // for ImGuiContext, ImPlotContext
#include <string>

namespace btquant { class MarketDataProcessor; }

namespace btquant::ui {

class MyNewWidget {
public:
    MyNewWidget();                    // set sensible defaults
    void render();                    // called every frame
    void setMarketData(::btquant::MarketDataProcessor* data) { m_data = data; }

private:
    ::btquant::MarketDataProcessor* m_data = nullptr;
    // widget-local state (toggle buttons, scroll position, color prefs)
};

}  // namespace btquant::ui
```

NOTE the global fwd-decl + fully-qualified `::btquant::X*` — see
Phase 3 pitfall #22 for why the bare `class MarketDataProcessor*` is
wrong here.

### Step 2: `src/widgets/<name>.cpp`
```cpp
#include "widgets/<name>.hpp"
#include "data/market_data_processor.hpp"   // full def for snap.recent_trades etc.
#include "data/market_data.hpp"              // data::Trade, data::Candle, ...
#include <implot.h>

namespace btquant::ui {

MyNewWidget::MyNewWidget() = default;

void MyNewWidget::render() {
    ImGui::Begin("My New Widget");
    bool isLive = false;
    std::vector<data::Trade> trades;
    if (m_data) {
        auto snap = m_data->snapshot(256);   // 256 ticks is a good default
        if (snap.snapshot_seq > 0) {
            trades = snap.recent_trades;
            isLive = true;
        }
    }
    if (!isLive) {
        // synthetic fallback (small random walk) — keeps UI alive
    }
    ImGui::Text("Source: %s", isLive ? "LIVE" : "synthetic");
    // ... ImPlot::BeginPlot / PlotLine / PlotBars / EndPlot ...
    ImGui::End();
}

}  // namespace btquant::ui
```

### Step 3: `src/widgets/window_manager.hpp` — add member + getter
```cpp
#include "widgets/<name>.hpp"
class WindowManager {
    // ... existing widgets ...
    MyNewWidget m_myNewWidget;
public:
    MyNewWidget& myNewWidget() { return m_myNewWidget; }
};
```

### Step 4: `src/widgets/window_manager.cpp` — propagate in `renderAll` and `setMarketData`
```cpp
void WindowManager::renderAll() {
    // ... m_orderBook.render(); m_dom.render(); ...
    m_myNewWidget.render();
}

void WindowManager::setMarketData(::btquant::MarketDataProcessor* data) {
    // ... m_orderBook.setMarketData(data); ...
    m_myNewWidget.setMarketData(data);
}
```

### Step 5: `src/main.cpp` — call from `WindowManager::renderAll` chain
(may already be done by step 4 — verify in your tree)

### Step 6: `CMakeLists.txt` — add the new .cpp
```cmake
add_executable(btquant_vulkan
    # ... existing sources ...
    src/widgets/<name>.cpp
)
```

`cmake --build` → `Built target btquant_vulkan` → `./build/btquant_vulkan`
for a smoke test. No `head -N` pipe, no `kill` mid-run.

## 29. ImPlot 1.x API gotchas (real, hit-this-session)

These are the API quirks that bit us building the 5 widgets. They
are durable — ImPlot's API is not stable between minor versions.

### 29a. `signed` is a C++ reserved keyword — do NOT name a variable `signed`
```cpp
double signed;  // ERROR: declaration of 'signed' [-fpermissive]
double deltaSigned;  // OK
```
Compiler error is misleading: "expected unqualified-id before numeric
constant" or "declaration of 'signed' as [-fpermissive]". Rename to
`deltaSigned`, `signedDelta`, `netDelta`, etc.

### 29b. `ImPlot::SetNextLineStyle` does NOT exist
- This appeared in some ImPlot versions and was removed.
- Workaround: skip the next-line style call; instead, set the color
  in the actual `PlotLine()` call (ImPlot 1.x has overloads taking
  `const ImVec4& color` and `float thickness`).
- If you need different per-line colors, use `ImPlot::PushStyleColor(ImPlotCol_Line, ...)`
  BUT note pitfall 29c: that enum also doesn't exist in some versions.

### 29c. `ImPlotCol_Line` does NOT exist (use `ImGuiCol_PlotLines` instead)
```cpp
// WRONG (compile error: 'ImPlotCol_Line' was not declared):
ImPlot::PushStyleColor(ImPlotCol_Line, ImVec4(0.5f, 0.8f, 1.0f, 1.0f));

// RIGHT (use the ImGui color enum — ImPlot reuses it):
ImPlot::PushStyleColor(ImGuiCol_PlotLines, ImVec4(0.5f, 0.8f, 1.0f, 1.0f));
```
ImPlot in this tree reuses the ImGui `ImGuiCol_*` enums for color
styling. If a color doesn't show, swap the enum and rebuild.

### 29d. `ImPlot::PushStyleVar` / `PopStyleVar` for line thickness
```cpp
ImPlot::PushStyleVar(ImPlotStyleVar_LineWeight, 2.0f);
// ... PlotLine calls ...
ImPlot::PopStyleVar();
```
This works. Only the color enum is the trap.

## 30. Data-driven widget patterns (reusable across Phase 4)

### Bidirectional cluster grid (Footprint)
The Footprint cell-grid is a 2D histogram: `candle_idx × price_level →
bid_volume + ask_volume`. The cell color encodes imbalance
(`(ask - bid) / (ask + bid) > 0.3` → red/green). Implementation
sketch:
```cpp
// Outer loop: candles (X axis = time)
for (size_t ci = 0; ci < candles.size(); ++ci) {
    const auto& c = candles[ci];
    // Inner loop: price levels inside this candle's range
    for (double p = c.low; p <= c.high; p += tickSize) {
        auto [bidVol, askVol] = aggregateTradesInBucket(trades, c, p, tickSize);
        // ImGui::SameLine() / draw cell
    }
}
```

### Rolling VWAP (MultiVWAP)
```cpp
double vwap = 0.0, cumPV = 0.0, cumV = 0.0;
for (size_t i = 0; i < std::min<size_t>(period, trades.size()); ++i) {
    cumPV += trades[i].price * trades[i].size;
    cumV  += trades[i].size;
}
vwap = (cumV > 0) ? cumPV / cumV : 0.0;
```
For "VWAP-20/50/100/200/all", compute each as the rolling sum of the
last K trades, then plot as separate `PlotLine` calls on a single
ImPlot axis.

### Volume profile (POC / VAH / VAL)
```cpp
std::map<double, double> volByPrice;  // price level → cumulative volume
for (const auto& t : trades) volByPrice[round(t.price / tickSize) * tickSize] += t.size;
auto maxIt = std::max_element(volByPrice.begin(), volByPrice.end());
double poc = maxIt->first;
// VAH/VAL = price levels bounding the 70% of volume closest to POC
```
For a clean horizontal bar plot, use `ImPlot::PlotBars` with the
price as X (so bars extend horizontally) and volume as Y.

### Realized P&L from FIFO position (RiskPanel)
```cpp
double realized = 0.0, unrealized = 0.0;
double position = 0.0;  // signed: +N long, -N short
double avgEntry = 0.0;
for (const auto& t : trades) {
    // If t.side == 'B' and position < 0, we CLOSE short → realize P&L
    // If t.side == 'B' and position >= 0, we OPEN long → update avgEntry
    // Symmetric for t.side == 'A'
}
// Unrealized = (lastPrice - avgEntry) * position  (sign-correct)
```

## 31. Verification after adding widgets

After every widget add:
```bash
cd /home/alca/projects/PubBTQuant/btquant_vulkan
cmake --build build 2>&1 | tail -10          # must end in "Built target btquant_vulkan"
timeout 5 ./build/btquant_vulkan 2>&1 | head -20  # must not crash
echo $?                                       # expect 124 (timeout) — NOT 134 (assert/abort)
```

If exit 134: crash in widget render. Re-run with a longer timeout and
inspect for missing includes, mismatched brace scope in `ImPlot::BeginPlot/EndPlot`,
or an ImPlot API misuse (see 29a-29d).

## 32. Commit-prefix style (already in the codebase)

Recent commits follow `feat:` and `fix:` (Conventional Commits).
Match the prefix to the change type:
- `feat: WidgetName — one-line description`
- `fix: WidgetName — what was wrong + how fixed`
- `refactor: WidgetName — what changed structurally`

Example from this session:
```
feat: OrderBookDepthWidget — ladder with depth bars + imbalance gauge
feat: FootprintWidget — bid/ask cluster chart per (candle × price)
feat: VPVRWidget — volume profile with POC / VAH / VAL / VWAP
feat: MultiVWAPWidget — VWAP-20/50/100/200/all with chart + table
feat: RiskPanel — position + P&L tracker from recent_trades
```

## Cross-references

- `references/btquant-vulkan-rebuild-fixes.md` — Phases 1+2 (build rescue, compute pipeline, live data ingestion, 21 fixes)
- `references/btquant-vulkan-phase3.md` — Phase 3 (widget wire-up, namespace fwd-decl trap, candle aggregation, TPO refactor)
- `references/btquant-ui-design.md` — Linear Dark + Kraken Purple design language
- `references/btquant-harmony-ui-implementation.md` — OLD engine's panel patterns (60+ panels, OpenGL backend)
