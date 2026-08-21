# BTQuant Vulkan — Phase 17: RiskGuard + kill switch (Ctrl+K)

Date: 2026-06-20. Commit: `2506c72a feat: RiskGuard + kill switch — pre-trade checks + Ctrl+K flatten`. Test 24: 16 invariants, all green. Sprint state at end: 14 commits, 19 widgets, 24 tests.

## What landed

- `src/data/risk_guard.{hpp,cpp}` — pre-trade check + session P&L tracker + kill switch
  - `RiskConfig { maxPositionSizeUSD, maxLeverage, killOnDailyLossUSD, equityUSD }`
    with `conservative()` ($100k / 10x / $5k / $10k) and `aggressive()`
    ($1M / 50x / $25k / $10k) presets
  - `checkOrder(qty, price, isLong) → optional<string>` — rejects on
    qty/price non-positive, notional cap, leverage cap, kill-tripped
  - `addRealized(delta) / resetSession() / sessionRealized()`
  - `isKillTripped()` — `sessionRealized <= -killOnDailyLossUSD`
  - `remainingLossBudget()` — loss capacity before kill trips
  - Pure math: `effectiveLeverage(notionalUSD, equityUSD)` + `killReason(...)`
- WindowManager integration:
  - `m_riskGuard` member constructed with conservative defaults
  - OrderTicket submit callback: `checkOrder` BEFORE applying fill —
    rejection logged via `BTQ_LOG_WARN` with reason
  - After each fill with non-zero realized, session P&L updated; auto-log
    `BTQ_LOG_ERROR` when kill trips
  - **Ctrl+K hotkey**: instant manual flatten at next snapshot price
    (falls back to order book mid). Logs WARN with realized + session P&L
- Hotkey help row added for Ctrl+K

## Architecture: RiskGuard as pure check + side-effect-free accessor

`RiskGuard` follows the same pattern as `PositionCalculator` and `OrderTicket`: math is exposed as static or const methods, the runtime state is a thin POD wrapper, and the UI integration is in WindowManager.

```cpp
auto r = g.checkOrder(0.5, 67000.0, true);
if (r.has_value()) {
    BTQ_LOG_WARN("REJECTED: %s", r->c_str());
    return;
}
```

`checkOrder` never mutates `RiskGuard` — it's `const`. The caller is responsible for calling `addRealized(delta)` after the trade lands. This separation keeps the guard testable as a pure function and lets the caller decide whether realized P&L from a partial close should or shouldn't count toward the kill threshold.

## Kill switch wiring: two paths converge

1. **Auto-trip**: after `OrderTicket.submit` calls `positionBook.fill(...)`,
   if the returned realized delta is non-zero, `riskGuard.addRealized(realized)`
   feeds the session. If `isKillTripped()` returns true, log ERROR.
   Subsequent `checkOrder` calls return the kill reason and reject.
2. **Manual trip**: Ctrl+K hotkey. `positionBook.flatten(snapshot_price)`
   closes the open position immediately, `riskGuard.addRealized(realized)`
   updates the session total, WARN log explains what happened.

Both paths share the same downstream: any future `checkOrder` will reject until `resetSession()` is called.

## Session P&L = sum of all realized, not just the open position

`sessionRealized` is cumulative across the entire session — it survives flatten events. `position().realizedPnL` is only meaningful for partial closes (the closed portion of an open position). `RiskGuard` tracks the trader-relevant number ("how much have I lost today?"), not the per-position accounting number.

## Test 24 — 16 invariants

- default config: $100k / 10x / $5k
- accept small order (0.5 BTC @ $67k = $33.5k, 3.35x)
- reject notional cap (5 BTC @ $67k = $335k > $100k)
- reject over-leverage (0.5 BTC @ $30k on $1k equity = 15x > 10x)
- reject invalid input (qty=0, price=0)
- session starts at 0 (not tripped)
- session tracks +$300 alive
- kill trips at -$5100 (limit -$5000)
- post-kill orders rejected with kill reason
- resetSession clears state
- effectiveLeverage math + zero-equity guard
- killReason format string
- aggressive preset ($1M / 50x / $25k)
- aggressive accepts $335k order (under $1M cap)
- remainingLossBudget = $5000 fresh
- after -$1500 loss → remainingLossBudget = $3500

## Pitfalls (NEW — captured this phase)

- **`remainingLossBudget` must return POSITIVE**, not its negation. The
  function name reads as "how much can I still lose before the kill
  trips" — that's the BUDGET, always non-negative while alive. Returning
  `-budget` flips the sign and breaks every consumer that does the
  natural `if (remainingLossBudget() > 0)` check. The "Just say so
  honesty rule" applies: if the function name suggests a positive
  quantity, the math must agree. This is a generalization of the
  Phase 7 "std::to_string locale / strip-zeros" pitfall — both are
  cases where the math output contradicts the implicit semantic
  contract of the API. The fix that landed: drop the negation, the
  formula `killOnDailyLossUSD + sessionRealized` is already correct.
- **WindowManager needs `<cmath>` for std::abs in realized-delta
  check**: when adding `if (std::fabs(realized) > 0.0)` inside the
  OrderTicket submit lambda, `<cmath>` must be in scope. `<imgui.h>`
  doesn't transitively include it. Symptom: `'fabs' was not declared
  in this scope` on first build. (Phase 14 already covered
  `<algorithm>` for `std::find/std::rotate`; this is the same trap for
  `<cmath>`.) Fix: add `#include <cmath>` at the top of
  `window_manager.cpp`.

## Lessons carried forward (already in SKILL.md from earlier phases)

- **Pure-math statics as the test seam**: `RiskGuard::effectiveLeverage`,
  `RiskGuard::killReason` are static. The `checkOrder` const method is
  testable without instantiating the runner. Same pattern as Phase 15
  OrderTicket (computeFee / estimateFillPrice / computeTotalCost) and
  Phase 14 PositionCalculator.
- **Capture state BEFORE mutation**: `addRealized(realized)` runs
  AFTER the positionBook mutation (fill returns the delta), so there's
  no leftover problem here. But the *OrderTicket submit* lambda
  captures `m_orderTicket` and `m_marketData` by `this`; if any
  subsequent edit reorders the mutation vs the session-tracking call,
  the realized delta will read the pre-mutation value. Keep the
  `addRealized` call immediately after `fill`, never split by an
  unrelated operation.
- **Session-realized vs position-realized**: covered in Phase 16
  pitfalls. Reinforced here: `RiskGuard::sessionRealized()` is the
  trader-facing number, never `positionBook.position().realizedPnL`
  after a flatten event.
- **Two-CMakeLists trap**: this phase hit the same diagnostic
  signature as Phase 15 — adding `risk_guard.cpp` to `CMakeLists.txt`
  is not enough; `test/CMakeLists.txt` needs the entry too. Already
  in Phase 15 pitfalls.

## Sprint progression summary

This was the 10th turn of the sprint. The "FRAG NICHT IMMER SO BEHINDERT: WEITER!" trigger fired 3 times during this sprint (turns 8, 9, 10). Each time the response was the same: pick the next item from the previous turn's "Open / next" list, ship, commit, report. The user never deviated from this signal — they want commit SHAs and shipped code, not discussion.

10 turns → 14 commits → 19 widgets → 24 tests. Each commit is ~10-15 files / 200-600 lines. The 7-step widget-add recipe (Phase 10) holds up: hpp + cpp + WindowManager member + render dispatch + main dispatch + CMakeLists (×2) + test. Each phase adds one or two new mechanical changes to that recipe (Phase 15 added Ctrl+Enter hotkey, Phase 16 added mark-to-market wiring in showPositionPanelWindow, Phase 17 added pre-flight check in OrderTicket submit + Ctrl+K hotkey).