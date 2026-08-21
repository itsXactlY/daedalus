# BTQuant Vulkan — Phase 16

**Session date:** 2026-06-20
**Commits shipped:** 1 (`5ac6a0d0`)
**Widgets added:** 1 (`PositionPanel`)
**Data classes added:** 1 (`PositionBook`)
**Test count delta:** +13 invariants (Test 23)
**Files modified:** 14

## What landed

### PositionBook — single-symbol position aggregator with full fill-state machine

`src/data/position_book.{hpp,cpp}` — owns the open position for the
active symbol. Stateless apart from the position struct + a
session-realized accumulator.

`fill(symbol, isLong, qty, price)` covers 4 cases:

1. **Flat → open**: set `size = qty`, `avgEntry = price`, no realized.
2. **Same direction**: weighted-average entry —
   `avgEntry = (oldSize*oldAvg + fillQty*fillPrice) / (oldSize + fillQty)`
3. **Opposite direction, fills less than open size**: close that portion,
   realize P&L on the closed qty, keep remainder. Returns the realized
   delta so the caller can log/record.
4. **Opposite direction, fills more than open size**: close everything,
   realize on the closed portion, then flip the residual into the
   opposite side at the fill price (e.g. SELL 2.0 against a long of 1.0
   closes the long at +$1500 realized and opens a short of 1.0).

**Symbol-switch auto-flatten:** if a fill arrives for a different
symbol while a position is open, the old symbol's position is
flattened at the new fill's price (treating the new fill as a
mark/print for the old symbol). Without this, switching symbols would
leave the position "stuck" on the old symbol with stale data.

**`markToMarket(price)`** updates `unrealizedPnL` each frame:
`diff = isLong ? (current - avg) : (avg - current)` then `unrealized =
size * diff`. Returns the new value. Cheap (no allocations, no
locking) so it's safe to call every render frame from the panel.

**`flatten(price)`** zeros the position and realizes all unrealized
into `realizedPnL` AND `sessionRealized`. Used by the kill-switch and
when the user clicks the panel's "Flatten at market" button.

**`sessionRealized()`** is a separate accumulator that survives
flatten events. `position.realizedPnL` resets to 0 when the position
is flattened (since the position no longer exists); `sessionRealized`
preserves the trader's cumulative P&L for the session until
`clearAll()` is called.

Pure-math statics exposed for testing:
- `averageEntry(oldSize, oldAvg, fillQty, fillPrice)` — weighted-avg
- `applyClose(openSize, openAvg, closeQty, closePrice, openIsLong) → CloseResult` — close portion

### PositionPanel — read-only ImGui view + fill history

`src/widgets/position_panel.{hpp,cpp}` — bound to a PositionBook via
`setPositionBook(book)`. Renders:

- **Empty state**: "No open position. Submit an order from the Order
  Ticket (Ctrl+Enter) to open one." Plus recent-fill history (if any
  fills were already applied during this session).
- **Open state**: side (color-coded LONG/SHORT), size, avg entry, fill
  count, realized P&L, unrealized P&L, total P&L. Color-coded
  green/red on every P&L field.
- **"Flatten at market" button**: logs an intent (handler will be
  wired in a later turn — currently just logs).
- **Recent fills table**: bounded to `kMaxHistory=64`, ring-trimmed,
  newest-first. Columns: seq, symbol, side, qty, price, Δrealized.

`recordFill(FillRecord)` is called by the WindowManager OrderTicket
submit callback after `PositionBook.fill()` succeeds. It bumps the
internal seq counter and prepends to the history.

### OrderTicket → PositionBook wireup (closes the loop)

The OrderTicket's submit callback (added in Phase 15) previously just
logged the summary. Phase 16 wires it to PositionBook:

1. Read `m_orderTicket.quantity()` and `m_orderTicket.isBuy()`.
2. Resolve fill price: prefer `m_marketData->snapshot().recent_trades.front().price`
   (the most recent live trade), fall back to `m_orderTicket.limitPrice()`.
3. Call `m_positionBook->fill(symbol, isBuy, qty, price)`.
4. Build a `PositionPanel::FillRecord` and call `m_positionPanel->recordFill(r)`.
5. Log the realized delta when non-zero.

`showPositionPanelWindow()` drives `markToMarket` off the latest
snapshot each frame BEFORE rendering, so the panel shows live
unrealized P&L without polling.

### Hotkey: Ctrl+B toggles PositionPanel

Edge-triggered, same pattern as Ctrl+P / Ctrl+T / Ctrl+Enter.
Added to:
- `WindowManager::handleHotkeys` (the bool-gated GLFW key-check block)
- View menu (between Order Ticket and Settings)
- Hotkey Reference table (`Ctrl+B  Toggle Position Panel`)

## Pitfalls caught this sprint

### 1. Capture state BEFORE mutation in partial-close logic

**Bug:** in `PositionBook::fill()`, after the
`applyClose(m_pos.size, ...)` call, the position struct was already
mutated (`m_pos.size = cr.newSize = 0`). The leftover calculation

```cpp
double leftover = qty - (m_pos.size > 0.0
                         ? (qty - m_pos.size)
                         : qty);
```

always evaluated the else branch (`leftover = qty - qty = 0`).
Symptom: flipping from long to short never produced a new short
position. Test 23 step 5 (`fill(symbol, false, 2.0, 69000.0)` against
long 1.0 @ $67500) showed `isLong=1 size=0` after the call.

**Fix:** capture `appliedClose = std::min(qty, m_pos.size)` BEFORE
the close mutation. Then `leftover = qty - appliedClose`. Always do
this when computing residuals from a partial-state change.

**Generalizes:** ANY function that mutates state mid-calculation and
then tries to compute "what was left over" needs the pre-mutation
amount captured first.

### 2. Off-by-10× test assertions on magnitude calculations

**Bug:** Test 23 step 3 expected `markToMarket(69000.0) → 300.0`
unrealized, actual was `3000.0`. I had:

```cpp
// 3) Mark to market at $69000 → unrealized = 2.0 * (69000 - 67500)
//    = $300.       <-- WRONG
```

2.0 base × ($69000 - $67500) = 2.0 × $1500 = **$3000**, not $300.
Tests for unrealized/realized P&L require the actual magnitude, not
the per-unit delta. Same trap caught me on every subsequent
assertion in Test 23 (close-half, flip, short-mark, flatten).

**Fix rule:** when writing P&L test assertions, do the full
multiplication: `qty * priceDiff`, not `priceDiff` alone.

### 3. `position.realizedPnL` vs `sessionRealized` after flatten

`flatten(price)` zeros `m_pos.realizedPnL` because the position no
longer exists. UI panels that show "session P&L" must read
`sessionRealized()`, not `position().realizedPnL`, to preserve the
number across flatten events.

Initial PositionPanel draft read `m_book->position().realizedPnL`,
which went to 0 after a flatten. Fix: panel reads `sessionRealized()`
and labels the field accordingly. The position's `realizedPnL` is
only meaningful for the OPEN portion's accumulated realized (e.g.
partial closes that didn't fully flatten).

### 4. PositionPanel history ring-trim happens on insert, not on render

`recordFill` does `if (m_history.size() > kMaxHistory) resize(kMaxHistory);`
immediately. This is correct (newest-first, so resize drops the
oldest from the back). Alternative (trim on render) would defer the
work but means `historySize()` could be temporarily > `kMaxHistory`.

The current pattern is fine; just don't `reserve(kMaxHistory)` in the
constructor — `vector::push_back` on insert is fast enough at
kMaxHistory=64 that no pre-allocation is needed.

## Lessons carried forward

- **The "FRAG NICHT IMMER SO BEHINDERT" trigger is sprint-permanent**:
  once the user fires it in a session, every subsequent
  "WEITER" / numbered-list-pointer turn ends with
  `commit SHA + what landed + "going for #N next"`, NOT with
  "Soll ich X oder Y?". This sprint fired the trigger 3 times across
  turns 8 and 9 (after PositionCalculator → OrderTicket →
  PositionBook); each time the right response was to pick the next
  highest-value item from the previous turn's "Open / next" list and
  ship it. The user does NOT want a recap of what's pending — they
  want the next commit SHA.
- **Data → Widget → Wireup → Tests is the canonical 4-step widget
  add**: PositionCalculator → OrderTicket → PositionBook + PositionPanel
  all followed the same pattern. PositionBook is pure data
  (no ImGui); PositionPanel is pure UI (no business logic); the
  WindowManager wireup connects them. Test N covered the data layer
  with 13 invariants (math + edge cases), which surfaced both bugs
  above without needing a UI harness.
- **MarkToMarket per-frame is safe as long as it's O(1) and lock-free**:
  PositionBook::markToMarket is 4 multiplications + 1 conditional.
  Calling it from `showPositionPanelWindow()` every frame, even at
  144 Hz, is fine. If it grew to scan a trade list, you'd need to
  throttle or move it into the snapshot path.

## What's open after Phase 16

- **Hotkey customization** — currently hardcoded in
  `WindowManager::handleHotkeys`. Need a `~/.config/btquant_vulkan/hotkeys.ini`
  reader and a "Remap…" submenu in Settings.
- **Trade history persistence** — PositionBook in-memory only.
  `clearAll()` wipes session-realized. Need SQLite-backed journal
  for restart-survival.
- **Risk limits** — PositionBook has no max-size / max-loss / kill
  switch. Flatten button currently just logs intent.
- **JSON layout profiles** — currently INI-only via Settings.
- **MiniPriceChart widget** — candlestick viz using
  `snap.recent_candles + snap.current_candle` (the
  Phase-3 candle aggregation path is in place, just no widget for
  it yet).
- **DOM heatmap widget** — heatmap_compute is in place; widget
  surface not started.
- **Chart panel port from sfgg** — `/home/alca/Schreibtisch/sfgg/`
  still uncompared (original turn-7 ask). 5167 lines for chart_panel
  alone.