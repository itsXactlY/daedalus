# Phase 29 — DOMWidget heatmap view toggle

**Status:** shipped 2026-06-20. Commit 1134af1e. 19 commits / 23 widgets / 36 tests.

## What landed

`DOMWidget` got a heatmap rendering branch alongside the existing bar chart.
The user-facing control is a **Heatmap view** checkbox in the existing
controls row plus a 1–16px **Cell height** slider that appears only when
heatmap mode is on.

**State additions:**
- `bool m_heatmapMode = false;` — toggles between bar-chart (default) and
  heat-strip rendering.
- `float m_cellHeightPx = 6.0f;` — overridable via `setCellHeightPx(float)`
  for programmatic drivers (tests, hotkeys, profiles).
- `void setHeatmapMode(bool on) { m_heatmapMode = on; }` — public setter.
- `bool heatmapMode() const { return m_heatmapMode; }` — public getter.
- `float cellHeightPx() const { return m_cellHeightPx; }` — public getter.

**Rendering branch (`m_heatmapMode && bidCount>0 && askCount>0`):**
- Computes Y range across all levels with 5% padding so extreme wicks
  don't sit on the canvas edge.
- For each price level, draws a **full-width filled rectangle** of
  `cellHeightPx` height. Bid rows lerp `green(0,200,80)` →
  `cyan(0,255,255)` by size/maxSize; ask rows lerp `red(220,40,40)` →
  `yellow(255,230,40)` by size/maxSize.
- **Top quartile** (top `m_maxLevels/4` rows) gets a price + size label.
  Bid labels anchored left, ask labels anchored right.
- White mid line on top, full opacity (200) to separate bid/ask zones.

Test 36: 5 invariants covering defaults (off, 6px cells), toggle on/off,
custom 1.5px + 16px heights. 5/5 green.

## PITFALL: `static` getters defined inline in header

Phase 29 added `bool heatmapMode() const { return m_heatmapMode; }` and
`float cellHeightPx() const { return m_cellHeightPx; }` as **inline
header definitions**. This works because the accessors are trivial and
the header doesn't pull in any heavy includes. For non-trivial getters
(return by value with computation, allocate, etc.), the inline-in-header
pattern still works but forces every consumer to include the full
header. The current approach is correct: trivial accessors stay inline,
non-trivial accessors get a `.cpp` definition.

**Reusable rule:** inline getters in the header are fine for trivial
field-read accessors. For accessors that compute, log, or allocate,
move to `.cpp` to keep the header light.

## Pattern: heat-strip visualization for any ladder-shaped data

The DOM heatmap is one specific instance of a general pattern: **a
ladder of values rendered as a vertical heat strip where row position
encodes value and color intensity encodes magnitude.** The same code
shape works for:

- **Order flow ladders** (where intensity = trade volume at that price)
- **Liquidity heat strips** (intensity = resting size at each tick)
- **Time-and-sales** (intensity = print frequency at that price)
- **VPVR** (intensity = volume traded at that price over a window)

Whenever a widget shows a vertical list of bars and the user might
benefit from "see the big walls without parsing each bar's exact width",
add a heat-strip toggle. The pattern is ~80 lines of ImDrawList code
on top of the existing bar-chart render.

## How this fits with the deferred-list from Phases #25+

This closes the **"DOM heatmap widget"** deferred item from Sprint #25
(Open/next list at end of `references/btquant-vulkan-phase25.md`).
The "candlestick bodies via raw draw-list" item from the same list is
closed in Phase 30.

## Notes / non-changes

- Existing bar chart stays the default view. No user-visible default change.
- `m_heatmapMode` is intentionally NOT persisted via Settings/LayoutIO
  yet — the menu bar would be the natural home for a `View → DOM Heatmap`
  toggle, but that's a separate UI integration.
- Cell height slider range (1-16px) was picked empirically — 1px is
  "tight strip, see all levels", 16px is "chunky blocks, see big walls".
