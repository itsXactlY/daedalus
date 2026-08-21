# Phase 30 — MiniPriceChart candlestick bodies via raw draw-list

**Status:** shipped 2026-06-20. Commit 505b5cfb. 20 commits / 23 widgets / 37 tests.

## What landed

`MiniPriceChart` got a real candlestick rendering branch that draws
**OHLC bodies + wicks via raw `ImDrawList`** instead of the ImPlot
fallback that could only render wicks. This closes the
**"Candlestick bodies via raw draw-list"** deferred item from Sprint #25.

**State additions:**
- `enum class RenderMode { Line = 0, Candle = 1 };`
- `RenderMode m_renderMode = RenderMode::Candle;` — **default is Candle**
  (real OHLC bodies, the whole point of this phase)
- `void setRenderMode(RenderMode m)` — public setter
- `RenderMode renderMode() const` — public getter
- Header row gains **Line / Candle radio buttons** (SameLine after the
  existing summary text)

**Pure static helpers exposed as test seam:**
- `static float priceToPixelY(double price, double yMin, double yMax,
  float canvasY, float canvasH)` — maps price → screen Y. Higher
  price → smaller Y. **Clamps out-of-range prices** so they don't
  produce negative Y. Returns canvas center on degenerate range
  (`yMax <= yMin`).
- `static float indexToPixelX(int idx, int count, float canvasX,
  float canvasW, float bodyFrac)` — maps candle index → screen X.
  Returns slot-centered X with body width = `slotW * bodyFrac`.
  Returns canvas center on `count <= 0`.

**Rendering branch (`m_renderMode == RenderMode::Candle`):**
- Computes Y range across all candles with 5% padding (same pattern
  as DOM heatmap Phase 29).
- For each candle:
  - Computes `yOpen / yClose / yHigh / yLow` via `priceToPixelY`.
  - Body rectangle from `min(yOpen, yClose)` to `max(yOpen, yClose)`.
  - **Doji guard**: if body height < 1px, force bottom = top + 1px so
    flat candles stay visible.
  - Color: green if `close >= open`, red otherwise.
  - Wick: single vertical line from `yLow` to `yHigh` through body
    center.
  - Black outline around body so adjacent doji candles stay
    distinguishable.
- Last-close price tag on the right margin, white text.
- Line mode unchanged — keeps the cheap at-a-glance trend read.

Test 37: 7 invariants covering default mode (Candle), Line toggle,
Candle round-trip, Y-axis inversion (top<mid<bot), out-of-range clamp,
X slot-centering matches expected, X monotonic increase. 7/7 green.

## PITFALL: `reinterpret_cast<int*>(&m_renderMode)` for RadioButton

`ImGui::RadioButton(label, int* v, int v_button)` requires an `int*`
that lives for the entire frame. The pattern:

```cpp
ImGui::RadioButton("Line", reinterpret_cast<int*>(&m_renderMode),
                   static_cast<int>(RenderMode::Line));
ImGui::SameLine();
ImGui::RadioButton("Candle", reinterpret_cast<int*>(&m_renderMode),
                   static_cast<int>(RenderMode::Candle));
```

`m_renderMode` is `RenderMode` (enum class, sizeof == sizeof(int)),
so the cast is well-defined for read/write. Tests toggle
`chart.setRenderMode(...)` directly to verify state transitions.
This is the same pattern as Phase 8's radio buttons for the theme
toggle.

**Reusable rule:** when wiring an ImGui radio to a 1-byte enum that
fits in an `int`, `reinterpret_cast<int*>(&field)` is the standard
trick. Tests should NOT exercise the radio (no ImGui ctx) — they
verify the field directly via setters.

## PATTERN: pure-function test surface for render-bound widgets

Phase 30 establishes the most important testability pattern for
render-bound widgets:

**Identify the geometry math in the render path.** For MiniPriceChart
that's `priceToPixelY` (price → screen Y) and `indexToPixelX`
(candle index → screen X). For a future heatmap widget it would be
the same kind of mapping. For a future orderbook ladder it's the
price-row position calculator.

**Extract those pure functions as `static` members of the widget class.**
Static because they don't need `this`. Public so tests can call
them. Header-only is fine because they're trivial.

**Tests assert the math, not the draw calls.** Test 37 step 3
asserts `priceToPixelY(120) < priceToPixelY(110) < priceToPixelY(100)`
when canvasY=100, canvasH=200, range=[100,120]. No ImGui context
required.

**Generalizes to ANY render-bound widget.** When you're about to write
the render path, ask: "what's the pure math in here?" Pull it out
into a static. Tests verify the math. Smoke + ImGui verify the
draw calls. Same architecture as Phase 12's ThemeEditor
(capture/apply/equals POD snapshot), Phase 15's OrderTicket
(computeFee/estimateFillPrice/computeTotalCost), and Phase 30's
MiniPriceChart (priceToPixelY/indexToPixelX).

**The two failure modes this pattern prevents:**
1. Tests trivially no-op because ImGui calls crash without context.
2. Geometry regressions slip through because tests can't see pixels.

## PITFALL: clamping out-of-range prices is required

`priceToPixelY` accepts `yMin/yMax` as the chart's Y bounds. A user
dragging the slider aggressively OR a tick arriving with extreme
price can produce `price < yMin` or `price > yMax`. Without clamping,
the draw-list call silently writes negative or off-canvas pixel
coordinates that get clipped or even produce NaN paths on some
drivers.

Fix: `if (frac < 0.0) frac = 0.0; if (frac > 1.0) frac = 1.0;` after
the normalization. The candle is still drawn (just clamped to the
canvas edge), and the chart stays usable.

**Reusable rule:** any `valueToPixelY` helper in this codebase MUST
clamp. Add a clamp-test invariant (Phase 30 Test 37 step 4) so future
refactors can't silently drop it.

## How this relates to the ImPlot version gap

`build/_deps/imgui-src/` doesn't ship `DockBuilderLoadNodes` /
`SaveDockBuilderToText` (Phase 28 ref). The ImPlot in the same tree
also lacks `PlotCandlestick` + `ImPlotCol_Fill` (Phase 20 ref). Both
gaps mean: **don't use ImGui/ImPlot APIs that aren't in the vendored
tree**. Verify the API surface with `grep` BEFORE writing code that
assumes a newer version. The 5-second grep saves a 30-second rebuild
+ redesign cycle.

When `PlotCandlestick` does land upstream, the Candle render branch
in MiniPriceChart can be simplified to a single ImPlot call. Until
then, the raw draw-list branch IS the implementation.

## Deferred (unchanged, still future ImPlot upgrade)

- ImPlot::PlotCandlestick — staged for upgrade, raw draw-list works today
- ImPlot::ImPlotCol_Fill — same
- Volume subplot still uses ImPlot::PlotBars (2x separate series for
  buy/sell); no upgrade needed there
