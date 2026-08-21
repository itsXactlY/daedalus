# Phase 15 — OrderTicket widget (Ctrl+Enter) + test-only link failure diagnostic

## Scope

Close the gap left by Phase 13/14: a live order entry form tied to the
MarketDataProcessor's reference price. PositionCalculator (Phase 13)
was math-only; OrderTicket adds the trader-facing submit flow, fee/slip
preview, and quick-fill helpers against the live ref price.

## Files touched (commit `907a1252`, 12 files / +261/-5)

| File | Change |
|---|---|
| `src/widgets/order_ticket.{hpp,cpp}` | new — 290 LOC hpp + 240 LOC cpp |
| `src/widgets/CMakeLists` entry | `src/widgets/order_ticket.cpp` + `order_ticket.hpp` |
| `test/CMakeLists.txt` entry | `../src/widgets/order_ticket.cpp` (see Pitfall #1) |
| `src/ui/window_manager.hpp` | + `OrderTicket* m_orderTicket = nullptr;` + `bool showOrderTicket = false;` + `void showOrderTicketWindow();` |
| `src/ui/window_manager.cpp` | + `<algorithm>` (no-op, already added in Phase 14); + `setMarketData()` now also binds the OrderTicket; + Ctrl+Enter hotkey (edge-triggered); + main menu entry "Order Ticket (Ctrl+Enter)"; + hotkey help table row |
| `src/main.cpp` | + `windowManager.showOrderTicketWindow();` in the dispatch chain |
| `test/test_integration.cpp` | + Test 22 (10 invariants) |

## OrderTicket architecture

### Three pure-math statics, exposed for testing

The widget's submit-flow math lives in static helpers that have no
ImGui / no data-source dependencies:

```cpp
class OrderTicket {
public:
    static double computeFee        (double size, double price, double feeBps);
    static double estimateFillPrice (bool isBuy, bool isLimit,
                                     double limitPrice, double refPrice,
                                     double slippageBps);
    static double computeTotalCost  (double size, double effectivePrice,
                                     double feeBps);
    /* ... */
};
```

This is the **same pattern** as `PositionCalculator::computeSize /
computeNotional / computeRR` (Phase 13). Pure-math static helpers are
the test seam — the ImGui render path never has to be exercised by
tests, only the math invariants. Tests verify:

| Test | What |
|---|---|
| 22.1 | `computeFee(1.0, 67000, 10)` = $67.00 (= 1.0 × $67000 × 10bps) |
| 22.2 | market buy fill = ref + slip = 67000 + 5bps = 67033.5 |
| 22.3 | market sell fill = ref − slip = 67000 − 5bps = 66966.5 |
| 22.4 | limit buy that crosses (limit ≥ ref) → fills at limit |
| 22.5 | limit buy below market → rests at ref (no fill) |
| 22.6 | buy total = notional + fee = $67067 |
| 22.7 | sell total = −(notional − fee) = −$66933 |
| 22.8 | submit callback wiring stored |
| 22.9 | defaults: closed / buy / market |
| 22.10 | setOpen toggle round-trip |

**General rule:** any widget with submit / fill / P&L / sizing math
should expose those helpers as static or const methods. Tests cover
the math surface; the render path is exercised only in interactive use.

### `m_limit` doubles as both limit-price and ref-price field

When `m_typeIsLimit` is true, the input shows "Limit price" and the
user types a value. When market, the input is greyed out via
`ImGui::BeginDisabled()` and shows "Ref price (auto)" — `render()`
calls `refreshRefPrice()` which copies the latest trade price from
`m_data->snapshot(1).recent_trades.front().price` into `m_limit` via
`snprintf(%.2f, …)`. The fill-price calc reads `m_limit` regardless
of mode (limiting itself only kicks in when `m_typeIsLimit`).

This avoids two separate input fields and keeps the preview formula
single-source (`limitPx = parseOrZero(m_limit)`).

### Quick-fill against a $1 notional budget

The 25/50/75/100% buttons fill against a notional budget of $1 of quote
currency — for BTC/USDT at $67000 that's a quantity of `pct / 67000`.
It's a deliberate default: gives the user a sensible starting size
without needing them to type a quantity first. If they want a different
budget, they edit the qty field directly. The tooltip in render() makes
this explicit.

### Slippage direction matters

`estimateFillPrice(isBuy=true, …)` returns `ref + slip` (trader pays
more). `estimateFillPrice(isBuy=false, …)` returns `ref − slip` (trader
receives less). Slippage is asymmetric — `computeTotalCost` then
reflects this in the buy/sell sign convention:

```cpp
return (size >= 0.0) ? (notional + fee) : -(notional - fee);
```

Symmetric slippage around ref would be wrong for live trading. Test
22.2 + 22.3 lock this in.

### Submit button is conditionally disabled

```cpp
bool canSubmit = (qty > 0.0) && (fillPx > 0.0);
if (!canSubmit) ImGui::BeginDisabled();
if (ImGui::Button(...) || (ImGui::IsKeyPressed(ImGuiKey_Enter) &&
                            ImGui::IsKeyDown(ImGuiKey_LeftCtrl))) {
    /* submit + log */
}
if (!canSubmit) ImGui::EndDisabled();
```

The `Enter` key inside the ticket window submits only when Ctrl is
held. Plain Enter falls through to ImGui's default behavior (focus
advance / text-field commit). This avoids accidental submits while
typing in the qty field.

## Ctrl+Enter hotkey wiring (Phase 15)

Same edge-trigger pattern as Phase 11/14:

```cpp
static bool prevCtrlEnter = false;
bool currCtrlEnter = !textFieldFocus &&
                     glfwGetKey(win, GLFW_KEY_ENTER) == GLFW_PRESS &&
                     (glfwGetKey(win, GLFW_KEY_LEFT_CONTROL) == GLFW_PRESS ||
                      glfwGetKey(win, GLFW_KEY_RIGHT_CONTROL) == GLFW_PRESS);
if (currCtrlEnter && !prevCtrlEnter) {
    showOrderTicket = !showOrderTicket;
    if (m_orderTicket) m_orderTicket->setOpen(showOrderTicket);
    markSettingsDirty();
}
prevCtrlEnter = currCtrlEnter;
```

`markSettingsDirty()` is called so the visibility bit gets persisted
to `state.ini` like every other window toggle.

## Pitfalls (Phase 15)

### Pitfall #1: `test_integration` link failure is silent — main app builds fine

Same trap as Phase 10, but with a NEW diagnostic signature: only the
test executable fails. The main `btquant_vulkan` build succeeds because
`CMakeLists.txt` has the new `.cpp`. But `test_integration` has its own
source list in `test/CMakeLists.txt`. The new file is missing there,
and link fails for the test only:

```
/usr/bin/ld: ... undefined reference to
  btquant::ui::OrderTicket::computeFee(double, double, double)
/usr/bin/ld: ... undefined reference to
  btquant::ui::OrderTicket::estimateFillPrice(bool, bool, ...)
/usr/bin/ld: ... undefined reference to
  btquant::ui::OrderTicket::render()
collect2: error: ld gab 1 als Ende-Status zurück
make[2]: *** [test/CMakeFiles/test_integration.dir/build.make:647:
              test/test_integration] Fehler 1
```

**Diagnostic rule:** when `cmake --build build` succeeds but
`./build/test/test_integration` doesn't even start (or fails at link),
check `test/CMakeLists.txt` FIRST. The main app being green is NOT
proof the test will build.

**Fix:** add `../src/widgets/order_ticket.cpp` (and its `.hpp` for
consistency) to `test/CMakeLists.txt`. Then re-run
`cmake -S .. -B .` (CMakeLists change requires reconfigure, not just
rebuild). Phase 10 pitfall #1 already documents this in general;
Phase 15 surfaces it as "diagnostic signature: only test fails".

### Pitfall #2: When the render() path references an ImGui static that doesn't exist

NOT encountered this session, but worth flagging for future
OrderTicket-style widgets: `ImGui::IsKeyPressed(ImGuiKey_Enter)` and
`ImGui::IsKeyDown(ImGuiKey_LeftCtrl)` were both available in the
docking branch's ImGui 1.91+. If a user is on an older ImGui without
`ImGuiKey_Enter`, fall back to `ImGui::IsKeyPressed(ImGuiKey_KeyPadEnter)`
or a numeric check.

### Pitfall #3: `snprintf(buf, sizeof(buf), "%.2f", price)` for ref-price display

`%.2f` is locale-independent but `snprintf` itself is not — `%f` in
some locales uses `,` as the decimal separator. We use C `snprintf`
(not `std::to_string`) specifically because it's locale-stable in
the C library. If you ever swap to `std::ostringstream`, set the
locale explicitly:

```cpp
ss.imbue(std::locale::classic());   // never use the user's locale
```

Same as Phase 5 pitfall #1 + Phase 7 pitfall #5 — keep this in mind
for any future config / display writer.

## Test 22 (10 invariants)

See OrderTicket architecture section above. All pass on
`./build/test/test_integration`. Smoke test
(`timeout 3 ./build/btquant_vulkan`) exits 0.

## State after Phase 15

- **12 commits** (Phase 15 = 1: `907a1252`)
- **18 widgets** (OrderTicket added)
- **22 tests** all green
- Build + smoke clean

## Lessons carried forward

- **Two-CMakeLists trap has a diagnostic signature.** When the main app
  builds but `test_integration` link fails with `undefined reference`,
  the cause is always a missing entry in `test/CMakeLists.txt`.
  Internalize the two-edit rule: every new `.cpp` goes into BOTH
  `CMakeLists.txt` AND `test/CMakeLists.txt` in the same turn.
- **Pure-math statics are the test seam.** PositionCalculator, ThemeEditor
  Snapshot POD, OrderTicket — all three follow the same pattern: expose
  the math as static or const methods, keep ImGui render path in the
  render-only function. Tests never instantiate an ImGui context.
- **`m_limit` field-doubling is a pattern, not a hack.** When a widget
  has "live price" + "user override" semantics in the same logical field,
  reuse one char buffer + grey it out when overridden. Saves a column,
  keeps the fill formula single-source.
- **Asymmetric slippage is a feature, not a bug.** `estimateFillPrice`
  treats buy/sell as `ref ± slip`, not `ref × (1 ± slip/2)`. The former
  is what real exchanges report. Test 22.2 + 22.3 lock this in.
- **Submit disabled when qty/fillPx = 0.** Cheap invariant: prevents
  accidental zero-quantity submissions. `BeginDisabled/EndDisabled` is
  the canonical ImGui way.

## Next open / hot candidates

- **Hotkey customization** — F2..F12 + Ctrl+{L,P,T,Enter} + Shift+F1 + ?
  are hardcoded in `WindowManager::handleHotkeys`. Next iteration:
  per-binding user-mappable config in `state.ini` or a separate
  `~/.config/btquant_vulkan/hotkeys.ini`.
- **JSON config export for layout profiles (.btqlayout)** — current
  format is hand-rolled INI; JSON would round-trip better with
  complex nested settings (docking layout, theme, hotkeys).
- **MiniPriceChart widget (candlestick visualization)** — pure ImGui
  draw-list rendering of OHLC candles, fed by `snap.recent_candles +
  snap.current_candle`.
- **DOM heatmap widget** — port from sfgg if available, otherwise
  rebuild from order-book snapshot.
- **Order fill simulator** — track open positions, mark-to-market P&L,
  persist trade journal. Wire into the OrderTicket submit callback.
- **Port chart_panel (5167 lines) and watchlist_panel (3696 lines)
  from `/home/alca/Schreibtisch/sfgg/`** — original comparison ask,
  deferred through Phase 13/14/15 in favor of higher-impact work.