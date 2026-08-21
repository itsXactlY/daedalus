---
name: btquant-vulkan-phase32
version: "1.0"
description: "NEW engine: Phase 32 — TradesWidget time-and-sales CSV export. formatTradesCSV pure RFC-4180 helper, exportCSV writer respecting on-screen size filter, modal popup for filename, snapshotTrades extracted as public seam, per-instance synthetic fallback fix (function-local statics → this-keyed unordered_map)."
---

# Phase 32 — TradesWidget CSV export (2026-06-20)

**Sprint count entering**: 21 commits / 23 widgets / 38 tests
**Sprint count exiting**:  22 commits / 23 widgets / 39 tests

## What landed

- `TradesWidget::formatTradesCSV(const vector<Trade>&)` — pure static helper, RFC-4180. Header row first (`id,timestamp_iso,price,size,side`), ISO-8601 UTC timestamps with microsecond precision (`gmtime_r` + `snprintf`), locale-neutral price/size via `snprintf("%0.8f")`, BUY/SELL side encoding, RFC-4180 quote-if-needed helper (kept for future fields; current fields are ASCII-clean so the helper is a no-op).
- `TradesWidget::exportCSV(const string& path)` — calls `snapshotTrades(50)`, applies `m_filterSize` filter (WYSIWYG — what you see is what you get), writes via `std::ofstream` in binary+trunc mode. Returns false on open or write failure.
- `TradesWidget::snapshotTrades(size_t maxCount = 50)` — extracted the live-or-synthetic data-source logic from `render()` into a public method. Both render and export now share one path.
- New modal popup: "Export trades to CSV" with filename InputText + Save/Cancel buttons. `m_exportModalOpen` bool flag + `m_exportFilename` string buffer (default `"trades.csv"`).
- New "Export CSV…" button next to the size filter slider in the Trades window.
- Setters/getters for the modal state: `setExportModalOpen(bool)`, `exportModalOpen()`, `setExportFilename(string)`, `exportFilename()`.

## What was fixed (latent multi-instance bug)

The old `render()` had function-local statics for the synthetic fallback:
```cpp
static auto lastUpdate = std::chrono::steady_clock::now();
static std::vector<data::Trade> fallbackTrades;
```
Two `TradesWidget` instances in the same process (e.g. test + production) shared state. Fixed by extracting into a `static thread_local std::unordered_map<const TradesWidget*, vector<Trade>> fbMap` keyed on `this`. Test 39 doesn't exercise the multi-instance case directly, but the fix is a latent-bug-eradication change.

## Pitfalls

- **`namespace btquant::data { struct Trade; }` forward-decl required in trades_widget.hpp**: writing `std::vector<data::Trade> snapshotTrades(...)` in the header without forward-declaring `data::Trade` in that namespace makes the class definition unparseable, which surfaces as "class TradesWidget has no member named snapshotTrades" — confusing because the member IS in the source. Always forward-declare the data namespace's struct in widget headers that reference it.
- **`setExportFilename(const string& s)` returns void; getter is `const string& exportFilename() const`**: const-ref getter avoids the copy on read. Match this pattern for any other state that survives a render cycle.
- **`const_cast<TradesWidget*>(this)->snapshotTrades(50)` inside a const exportCSV()**: `snapshotTrades` mutates the per-instance fallback map, so it can't be const. Don't make it const — the per-instance state IS the seam. const_cast is the canonical pattern when the public method is const but the implementation needs to update cached state.
- **Modal popup needs the SAME-frame `OpenPopup` BEFORE `BeginPopupModal`**: when the user clicks "Export CSV…", `m_exportModalOpen = true` is set in the same frame. `render()` then calls `ImGui::OpenPopup("Export trades to CSV")` before `BeginPopupModal`. The pattern from Phase 11/12 holds.
- **CSV file write must be `std::ios::binary | std::ios::trunc`**: text mode would convert `\n` to platform-specific sequences on Windows. The CSV uses `\n` row terminators (RFC-4180 strict). Binary mode is portable; consumer tools (Excel, pandas, DuckDB) handle bare `\n` fine.

## Test 39 — 10 invariants

- empty input → header only
- single trade: header + 1 row, BUY + ISO timestamp + price/size present
- SELL side encoding
- 5 trades → 6 lines (1 header + 5 data rows)
- exportCSV(bad path) → false (no crash)
- formatTradesCSV is deterministic (same input twice → identical output)
- write+read file round-trip preserves CSV byte-for-byte
- modal defaults: closed + filename="trades.csv"
- setExportModalOpen/setExportFilename round-trip

Total: 252 ✓ checks across 39 tests, 0 failures. 3 files changed, 345 insertions.
