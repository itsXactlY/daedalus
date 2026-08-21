# BTQuant Vulkan — Phase 19: RiskLimitsPanel + live risk dashboard

Date: 2026-06-20. Commit: `d95f0066 feat: RiskLimitsPanel — live risk dashboard + limit editor`. Test 26: 6 invariants, all green. Sprint state at end: 16 commits, 20 widgets, 26 tests.

## What landed

- `src/widgets/risk_limits_panel.{hpp,cpp}` — ImGui dashboard panel for RiskGuard
  - Status banner: red (kill-tripped) / amber (loss budget <20%) / green (armed)
  - Session stats: realized P&L, remaining loss budget, kill threshold
  - Budget-used progress bar (green→amber→red as it fills)
  - Current exposure breakdown (when position is open) — uses PositionBook
  - Edit fields: maxPositionSizeUSD, maxLeverage, killOnDailyLossUSD, equityUSD
  - **Apply** button writes to RiskGuard via `RiskGuard::setConfig`
  - **Reset** button re-syncs the edit buffers from the current guard state
  - **Clear session** button — `RiskGuard::resetSession()` (kill-trip recovery)
  - Preset shortcuts: Apply conservative / aggressive presets
- WindowManager integration:
  - `m_riskLimitsPanel` member, `setRiskGuard` + `setPositionBook` bindings
  - `showRiskLimitsWindow()` method
  - **Ctrl+R** hotkey toggle (R for Risk)
  - Main menu: View → Risk Dashboard (Ctrl+R)
  - Hotkey help row added for Ctrl+R
  - Main render loop dispatches `showRiskLimitsWindow`

## Architecture: edit-buffer round-trip

The panel keeps `char[32]` buffers for the four limit values (e.g. `m_maxPos = "100000"`) rather than storing doubles directly. The pattern:

1. On first render with a guard bound, `syncFromGuard()` writes the
   current guard config into the buffers via `snprintf`.
2. While the user edits the buffers in ImGui, `editedMaxPositionSizeUSD()`
   etc. parse the buffers with `strtod` and return the live value.
3. **Apply** writes the parsed buffer values back to the guard via
   `setConfig` and logs the change. **Reset** re-runs `syncFromGuard()`.

This is the same pattern as `Settings::Settings` (Phase 5) and
`PositionCalculator` (Phase 14) — text buffers as the source of truth
for round-trippable user-editable values, with parsed-double accessors
for live read-back.

## Architecture: status banner colors

Three states derived from `RiskGuard::isKillTripped()` + remaining budget:

| Condition                    | Banner color | Banner text                       |
|------------------------------|--------------|-----------------------------------|
| `isKillTripped()` true       | red          | "KILL SWITCH TRIPPED — orders blocked" |
| `remainingLossBudget < 20%`  | amber        | "WARNING — loss budget low"       |
| otherwise                    | green        | "ARMED — risk checks active"      |

The 20% threshold matches the warning bar color (also amber) so the
banner and the progress bar tell the same story. Implementation uses
`ImGui::Selectable(text, false, ...)` with three pushed style colors
for header/hovered/active — keeps the click target accessible but
non-interactive.

## Architecture: budget progress bar

The progress bar shows "budget used" (1 - remaining/killLimit) with a
matching color scheme. As fills realize losses, the bar grows and
changes color at 50% (amber) and 80% (red). ImGui's `ProgressBar(0..1)`
takes a single float — `min(1.0f, max(0.0f, 1.0f - fracLeft))` clamps
both ends.

## Test 26 — 6 invariants

- Panel default closed
- `setOpen(true)` → isOpen
- Default edit buffers: `100000 / 10 / 5000 / 10000` (NOT zero — see pitfall)
- Edit buffer holds defaults until first render (lazy sync)
- `setConfig` propagation: after `g.setConfig(c)`, `g.config().maxPositionSizeUSD == c.maxPositionSizeUSD`
- `setPositionBook` accepts a book without crashing

## Pitfalls (NEW — captured this phase)

- **`char[N]` with `= "literal"` is NOT value-initialized** — `char m_maxPos[32] = "100000";`
  leaves bytes `[5..31]` as zero (the literal NUL terminator + padding),
  but the FIRST 5 bytes are `"10000"` — i.e. the buffer parses to
  `100000.0`, not `0.0`. Test 26's first attempt assumed "unbound edit
  buffers parse to 0"; the assertion failed because the buffer holds
  the default literal. The lesson: when writing tests against
  `char[N]` members with member initializers, ALWAYS assert the actual
  literal value, not zero. `std::array<char, N> = {};` would be zero-
  initialized but raw `char[N]` with `= "literal"` is not. (See
  `btquant-vulkan-phase19.md` pitfall #1.)
- **`ProgressBar(used, size, overlay)` clamps `used` to [0..1]? No —
  YOU clamp it.** ImGui's ProgressBar does NOT clamp `fraction` to
  [0..1]; it just renders whatever you pass. A `used > 1.0` overflows
  the bar visually (and may fire a NaN path on some platforms). Always
  clamp with `std::min(1.0f, std::max(0.0f, x))` before passing. (See
  `btquant-vulkan-phase19.md` pitfall #2.)
- **ImGui Selectable with custom colors needs ALL three style slots
  pushed** — `ImGuiCol_Header`, `ImGuiCol_HeaderHovered`, and
  `ImGuiCol_HeaderActive`. Forgetting one (typically the active
  variant) makes the banner flash the wrong color on click. Use a
  balanced `PushStyleColor` × 3 / `PopStyleColor` × 3 pair. (See
  `btquant-vulkan-phase19.md` pitfall #3.)
- **Ctrl+R was already a known hotkey for "Reload"** in some ImGui
  shortcuts. In BTQuant's context it's free (no other R-binding
  exists), but if you reuse Ctrl+R in a context that does, pick a
  different modifier combo (Shift+Ctrl+R or just Ctrl+Shift+R). (See
  `btquant-vulkan-phase19.md` pitfall #4.)

## Architecture: per-frame state refresh

PositionBook's `markToMarket(price)` is driven from
`showPositionPanelWindow()` before the panel renders. The
RiskLimitsPanel does NOT need its own refresh — it reads guard state
directly, and the guard's session P&L is updated from the OrderTicket
submit callback + Ctrl+K flatten. The only time the panel becomes
"stale" is when the session P&L changes via another path (manual
reset via a future button). Currently no such path exists; if one is
added, it must update the panel via a refresh signal.

## Hotkey inventory (final after Phase 19)

| Hotkey        | Action                                          |
|---------------|-------------------------------------------------|
| F2..F12       | Widget toggles (OrderBook, OB-Depth, DOM, Trades, TPO, Footprint, VPVR, Alerts, MultiVWAP, RiskPanel, Settings) |
| Ctrl+L        | Reset dock layout                               |
| Ctrl+P        | Symbol picker                                   |
| Ctrl+T        | Theme editor                                    |
| Ctrl+Enter    | Order ticket toggle                             |
| Ctrl+B        | Position panel toggle                           |
| Ctrl+R        | Risk dashboard toggle                           |
| Ctrl+K        | Kill switch — flatten open position at market   |
| Shift+F1      | FPS / frame-time overlay                        |
| ?             | Hotkey reference                                |

10 hotkeys total, 4 dedicated to trading-pipeline control (Ctrl+Enter,
Ctrl+B, Ctrl+R, Ctrl+K), 3 to widgets/windows (Ctrl+P, Ctrl+T, ?), 1
to layout (Ctrl+L), 1 to overlay (Shift+F1), 1 to the F-key widget
toggle family (F2..F12).

## Sprint progression summary

End of Phase 19: 16 commits, 20 widgets, 26 tests. The "FRAG NICHT
IMMER SO BEHINDERT: WEITER!" trigger fired 6+ times across this
sprint. Every "weiter" turn in this phase landed a substantive commit
(OrderTicket → PositionBook → RiskGuard → TradeJournal → RiskLimitsPanel).
Each turn followed the canonical recipe:
1. Pick next item from "Open / next"
2. Write the new file(s)
3. Patch WindowManager.hpp/cpp + CMakeLists.txt + test/CMakeLists.txt
4. Append test block (Test N)
5. `cmake --build build` (verify clean compile)
6. `./build/test/test_integration` (verify all green)
7. `git add -A && git commit` (one substantial commit per turn)
8. Save memory fact for next session
9. Report: commit SHA + what landed + "going for #N next"

The "two-CMakeLists" trap fired AGAIN in Phase 19 — `risk_limits_panel.cpp`
was added to top-level CMakeLists but test/CMakeLists link failed until
the second edit. This is the 5th time the trap has fired across the
sprint (Phases 10, 11, 15, 17, 19). Consider adding the file-path as
an explicit reminder in a future refactor.

## Lessons carried forward (new this phase)

- **Test assertions for `char[N]` members must match the actual literal
  initializer**, not zero. A test that assumes unbound buffers parse to
  0 is wrong when the buffer is `char[N] = "100000"`. Cross-check the
  default value in the header before writing the assertion.
- **ProgressBar does NOT clamp its fraction argument** — always clamp
  to [0..1] before passing. ImGui renders overflow as a fully-filled
  bar (or NaN on some platforms).
- **The "two-CMakeLists" trap is now 5-for-5 across the sprint** —
  any new `.cpp` source file needs to be added to BOTH
  `CMakeLists.txt` (lines ~41-79) AND `test/CMakeLists.txt` (lines
  ~65-94). The diagnostic signature: main app builds fine, test build
  fails at link with `undefined reference to btquant::ui::X::render()`
  for one of the new widget's methods. Phase 19 hit this on
  `risk_limits_panel.cpp`.
- **`char[N]` member-init with a string literal**: the bytes after the
  NUL terminator are zero-initialized (per C++11 aggregate-init rules),
  but the FIRST `strlen(literal)+1` bytes are the literal itself. This
  is rarely what tests want but is sometimes what production wants
  (e.g. a text input buffer with a placeholder default).