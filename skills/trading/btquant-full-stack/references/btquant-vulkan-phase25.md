# BTQuant Vulkan — Phase 25: Journal replay → PositionBook rehydration

**Date:** 2026-06-20
**Sprint state:** 15 commits / 23 widgets / 32 tests all green.

## Goal

Phase 24 made RiskConfig persist through `state.ini`. Phase 25 closes
the same loop for `TradeJournal`: fills are written to
`~/.config/btquant_vulkan/journal.jsonl` on every OrderTicket submit
and every Ctrl+K flatten (Phases 17 + 18), but `PositionBook` started
empty on every launch. Result: trader runs a session, exits, relaunches
— PositionPanel shows no position, session realized P&L reads 0, even
though the journal has the complete fill history. This phase replays
the journal on startup so the open position + session P&L survive
restart.

## Implementation

### `PositionBook::replay<JournalT>(journal, *lastPrice)` — template

Added a templated replay method on `PositionBook` (header decl,
`.cpp` body, explicit instantiation for `TradeJournal`):

```cpp
// position_book.hpp
template <typename JournalT>
size_t replay(const JournalT& journal, double* lastPrice = nullptr);

// position_book.cpp
template <typename JournalT>
size_t PositionBook::replay(const JournalT& journal, double* lastPrice) {
    m_pos = Position{};
    auto fills = journal.loadAll(nullptr);
    for (const auto& f : fills) {
        if (f.qty <= 0.0 || f.price <= 0.0) continue;
        fill(f.symbol, f.isLong, f.qty, f.price);
        if (lastPrice) *lastPrice = f.price;
    }
    return fills.size();
}
template size_t PositionBook::replay<TradeJournal>(
    const TradeJournal& journal, double* lastPrice);
```

The body:
1. Clears the existing `m_pos` (no stale state from the constructor's
   synthetic init).
2. Walks every `JournalFill` in chronological order.
3. Skips rows with `qty<=0 || price<=0` (defensive — the writer
   shouldn't produce them but JSONL can be hand-edited).
4. Calls `fill(symbol, isLong, qty, price)` with the **same semantics
   the live system used** — `isLong=true` means "this fill is a BUY".
5. Tracks the final fill price via `*lastPrice` out-param so the
   caller can call `markToMarket(lastPrice)` to seed `unrealizedPnL`.

### Why `isLong` passes through unchanged

Confirmed by reading the two journal-write sites in
`window_manager.cpp`:

- **Open fill** (OrderTicket submit, line ~252):
  `jf.isLong = isBuy;` — the side of the order.
- **Close fill** (Ctrl+K kill switch, line ~628):
  `jf.isLong = !m_positionBook->position().isLong;` — the OPPOSITE
  side of the current position, i.e. the side that closes it.

Both are stored as "this fill is a BUY" (`isLong=true` → buy side).
`PositionBook::fill(symbol, isLong, qty, price)` already uses the same
convention (Phase 16). Replay passes `jf.isLong` through verbatim —
no direction-flipping needed.

### WindowManager ctor: replay right after journal load

```cpp
m_tradeJournal = new ::btquant::TradeJournal(journalPath);
{
    int skipped = 0;
    size_t onDisk = m_tradeJournal->count();
    auto history  = m_tradeJournal->loadAll(&skipped);
    BTQ_LOG_INFO("TradeJournal: %zu fills on disk at %s (skipped %d)",
                 onDisk, journalPath.c_str(), skipped);
    // Rehydrate PositionBook from persistent journal
    if (m_positionBook && m_tradeJournal && onDisk > 0) {
        double lastPx = 0.0;
        size_t applied = m_positionBook->replay(*m_tradeJournal, &lastPx);
        BTQ_LOG_INFO("PositionBook: replayed %zu/%zu fills (last price %.2f)",
                     applied, onDisk, lastPx);
        if (m_positionBook->hasPosition() && lastPx > 0.0) {
            m_positionBook->markToMarket(lastPx);
        }
    }
}
```

Guard `onDisk > 0` skips the replay + log on fresh installs where the
journal file doesn't exist yet (Phase 18's "lazy create" semantics).
The `markToMarket` after replay seeds `unrealizedPnL` so the
PositionPanel shows live P&L on the first frame instead of waiting
for the first tick to flow through.

## Pitfalls

### **Templated method body in .cpp + explicit instantiation**

When you want a generic algorithm that takes a concrete dependency
type by reference (e.g. `TradeJournal`), putting the template body
in the header forces every consumer of `PositionBook` to also include
`<trade_journal.hpp>`. For BTQuant this means ~15 TUs pull in the
JSONL parser, the file I/O machinery, and the chrono include chain
— for a single method call.

The fix is three-part:
1. **Header**: `template <typename JournalT> size_t replay(const JournalT&);`
2. **CPP**: full body, ending with `template size_t PositionBook::replay<TradeJournal>(...)`.
3. **Caller**: passes the concrete `TradeJournal&` — the explicit
   instantiation forces the linker to emit the symbol for that one
   type only.

Adding a new journal type later = one more `template size_t ...` line
in the .cpp. No header churn, no include bloat. Generalizes to ANY
template that takes a concrete dependency type by reference — the
key heuristic is "does this method ever need a different type than
the one we use today?". If yes, template + explicit instantiation
beats putting the body in the header.

### **`PositionBook` is single-symbol by design**

The journal can contain fills for `BTC/USDT`, then `ETH/USDT`, then
back to `BTC/USDT` (from a symbol swap + auto-flatten, Phase 14 + 16).
After replay, `m_pos.symbol == "ETH/USDT"`, `m_pos.size == 5`, all
the BTC exposure is gone. Documented as "last-fill-wins semantics"
in Test 32 step 5.

Multi-symbol support would require `PositionBook` to become a map of
`(symbol, Position)` — out of scope for the HFT terminal's single-
active-symbol design. If the user later wants multi-symbol, the
replay method's behavior changes (one book per symbol, symbol switch
= swap active book) and `JournalFill.symbol` becomes the key. The
template stays the same; the implementation needs a different
data structure. Document the limitation in `PositionBook`'s class
doc so future contributors don't try to "fix" the last-fill-wins
behavior.

### **`replay()` skips rows with `qty<=0 || price<=0`**

The journal writer (`TradeJournal::append`) accepts whatever the
caller provides. If a future caller writes a malformed fill (qty=0
because of a divide-by-zero in the OrderTicket pre-flight), replay
must not propagate it into the live book. The guard inside the loop
silently skips bad rows. Log a warning if this fires in practice
(add `BTQ_LOG_WARN` next to the skip — not done in Phase 25 because
the only current call site is WindowManager, which always writes
well-formed rows).

### **Replay order is `loadAll` order, NOT timestamp-sorted**

`TradeJournal::loadAll` returns rows in the order they appear in
the file, which IS chronological for an append-only journal (Phase
18). If a future journaling system allows out-of-order writes
(merging two journals, manual edits, replay of multiple sessions),
sort by `timestamp_us` before passing to `replay()`. Don't add the
sort inside `replay()` — `loadAll` is the I/O layer, `replay` is
the math layer, and adding a sort step to math mixes concerns.

## Test 32: 5 invariants

```
Test 32: Testing journal replay → PositionBook...
✓ empty journal → empty book                       (n=0, hasPos=false, realized=0)
✓ long open + partial close replays correctly     (n=2, isLong, size=0.6,
                                                   avg=50000, realized=4000, lastPx=60000)
✓ full close → flat book, P&L realized            (n=2, hasPos=false, realized=1000)
✓ markToMarket after replay (uPnL=2500)           (size=0.5, avg=50000, mark=55000
                                                   → 0.5×5000 = 2500)
✓ multi-symbol → last-fill-wins semantics        (BTC then ETH → final state = ETH)
```

Coverage:
- Empty journal doesn't crash (defensive — `loadAll` returns empty vec).
- Long + partial close verifies the averaging math (size 1.0 → 0.6,
  avgEntry unchanged at 50000).
- Full close verifies realized P&L accumulates identically to the
  live path.
- markToMarket after replay seeds unrealizedPnL correctly.
- Multi-symbol documents the last-fill-wins limitation with a test
  that will FAIL if a future contributor tries to add multi-symbol
  support without thinking through the bookkeeping.

## Lessons carried forward

- **Replay + markToMarket on startup** is the canonical pattern for
  any data class that has both an in-memory state and a persistent
  journal: clear → replay in chronological order → recompute derived
  quantities. Other candidates: `TradeJournal` for session P&L
  aggregations, `AlertHistory` for past alerts, `ProfileManager` for
  layout history.
- **`out-param` for lastPrice** beats returning a struct. The caller
  reads `*lastPrice > 0` as the "we have a live mark" signal — simpler
  than checking if a returned optional is engaged.
- **Replay guards on `onDisk > 0`** avoid spurious log noise on fresh
  installs. Use the file-exists check, not `journal.empty()`, because
  `loadAll` returns empty vec both for "no file" AND "file with all
  malformed rows". The count-based check distinguishes "never
  written" from "written but corrupt".

## Deferred (unchanged from Phase 24)

- Layout profiles (.btqlayout) — actual ImGui `SaveIniSettingsToDisk`
  window positions persist via Phase 7's `imgui.ini` flow; the
  remaining work is named profiles the user can switch between.
- DOM heatmap widget.
- Candlestick bodies via raw draw-list (Phase 20's open design
  decision).
- Session realized P&L on `RiskGuard` still resets on restart (only
  PositionBook.replay covers it now). A future Phase could add a
  `RiskConfig::persistedSessionRealized` field that the journal
  loader mutates on startup, so the kill-trip threshold's
  "remainingLossBudget" reads correctly post-restart.

## Sprint progression summary

| Sprint | Widgets | Tests | Net new |
|--------|---------|-------|---------|
| Phase 22 | 23 | 29 | HotkeyEditor (Ctrl+H runtime remap) |
| Phase 23 | 23 | 30 | Unified dispatchAction refactor (10+ Ctrl/Shift blocks → 1 loop) |
| Phase 24 | 23 | 31 | RiskConfig persists via state.ini + looksLikeDouble guard |
| **Phase 25** | **23** | **32** | **Journal replay → PositionBook rehydration on startup** |

The widget count stays at 23 because replay is a data layer change
in an existing class — no new widget, no new render path. The test
count +1 because replay is a new pure-math function with documented
edge cases that need explicit coverage.