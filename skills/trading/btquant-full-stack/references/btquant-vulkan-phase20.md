# Phase 20 — MiniPriceChart (Ctrl+M): OHLC visualization via ImPlot

Phase 20 shipped `src/widgets/mini_price_chart.{hpp,cpp}` — a candlestick
chart driven by `MarketDataProcessor::snapshot().recent_candles`.
Two-subplot layout: price (close line + per-candle wicks) + volume
(buy/sell bars). History size is a runtime setter (`historyN`,
default 60). OHLC validation rejects malformed series with a ⚠
warning instead of rendering garbage.

## Wiring

- `m_miniPriceChart` member added to `WindowManager`
- `setMarketData` propagates to the chart (in addition to OrderTicket)
- `showMiniPriceChartWindow()` method re-binds market data on every
  render in case the data source arrived after construction
- `Ctrl+M` hotkey toggle (M for Mini-chart)
- Main menu entry + hotkey help row
- Main render dispatch

## Pure-math validation (test surface)

- `validateCandle(c)` — open>0, low>0, high>=max(O,C), low<=min(O,C), volume>=0
- `validateSeries(v)` — returns index of first bad candle or -1 if all valid

## Pitfalls (Phase 20 specific)

- **ImPlot API version detection**: grep the installed `implot.h` BEFORE
  writing code that assumes newer features. This tree's ImPlot lacks
  `PlotCandlestick` AND `ImPlotCol_Fill`. Symptom: linker errors at the
  call site + clangd "no member named X in namespace ImPlot". Detection
  recipe: `grep -nE 'PlotCandle|ImPlotCol_Fill' build/_deps/implot-src/implot.h`
  → returns nothing if feature missing. Fix: render candlesticks manually
  with `PlotLine` (per-candle wick: 2-point segment from low→high) +
  `PlotLine` (close price) + skip bodies OR use raw ImGui draw lists.
- **`PlotBars(values, count, bar_size)` uses single-value-per-bar from y=0**,
  NOT base+height. No equivalent of the typical `PlotBars(xs, bases, heights, ...)`.
  If you need stacked bars, draw two separate series (buy + sell) and let
  them overlay — ImPlot doesn't sum them. For candle bodies specifically,
  the cleaner workaround is `PlotBars` on a single `bodyHeight` array
  with the axis starting at `bodyBase` (impossible directly) — switch to
  ImGui draw-list rectangles or per-bar PlotLine segments.
- **`ImAxis_X` / `ImAxis_Y` do NOT exist** in this ImPlot version — the
  enum is `ImAxis_X1` / `ImAxis_X2` / `ImAxis_X3` / `ImAxis_Y1` / `ImAxis_Y2`
  / `ImAxis_Y3` (enum ImAxis_ typedef'd to int ImAxis). Wrong name fires
  "Use of undeclared identifier 'ImAxis_X'" at compile time.
- **`ImPlotCond_Always` locks axis limits** — fine for an X axis spanning
  exactly the bar index range, but if the bar count varies across
  frames (e.g. live updates), use `ImPlotCond_Once` to let ImPlot
  re-fit. With Always, growing bars overflow the right edge of the plot
  silently — they still render but get clipped.
- **`PlotLine` with 2 points = single segment**, but ImPlot's auto-scaling
  ignores the segment if it's a single point (N=1). Always pass N>=2 for
  a wick segment. N=1 plots nothing visible.

## Test (Test 27, 11 invariants)

1. default closed, historyN=60
2. setOpen(true) → isOpen
3. setHistoryN(120) → historyN=120
4. valid candle accepted
5. reject high < open
6. reject low > close
7. reject zero open
8. reject negative volume
9. validateSeries(5 good candles) → -1
10. validateSeries flags bad index 2
11. validateSeries(empty) → -1

## Sprint progression through Phase 20

After Phase 20 the sprint reached: 17 commits, 21 widgets, 27 tests, all
green. The "FRAG NICHT IMMER SO BEHINDERT: WEITER!" trigger fired at
the start of EVERY turn from 8 through 13 (PositionBook → OrderTicket
→ PositionBook → RiskGuard → TradeJournal → RiskLimitsPanel →
MiniPriceChart). The user's standing pattern: bare "WEITER!" reply, no
question, no clarification, no scope-bounding — they want momentum, not
check-ins. The right response every time: read the previous turn's
"Open / next" list (or memory fact:btquant-vulkan-sprint-*), pick the
next item, ship end-to-end, commit, report `commit SHA + what landed +
"going for #N next"`.

## Lessons carried forward

- **Always grep third-party library headers for the exact API surface**
  before writing code that assumes a newer version. Phase 20 would have
  shipped on the first try if the assistant had grepped `implot.h` for
  `PlotCandlestick` / `ImPlotCol_Fill` / `ImAxis_X` BEFORE writing the
  cpp. The pattern: `grep -nE 'Symbol1|Symbol2' /path/to/library.h`
  (5 seconds), then write code against the actual surface. Saves a
  rebuild cycle and a redesign.
- **For an ImPlot chart with version-skewed features, render a
  simplified primitive rather than fight the API**: Phase 20's
  redesign dropped the candle bodies (ImPlot lacks PlotCandlestick in
  this version) and kept the close line + wicks. The chart is still
  useful for trend identification; the missing bodies are a cosmetic
  loss. Trade functionality for visual richness in exchange for
  shipping speed.
- **Per-candle PlotLine for wicks (N=2 each) scales fine for historyN<=120**:
  120 candles × 1 wick line each = 120 line draws per frame, which
  ImPlot handles in <1ms on any modern GPU. For historyN>500, switch
  to a single PlotLine with NaN separators (ImPlot skips NaN pairs),
  giving one draw call for all wicks.