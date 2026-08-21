# Phase 35 — OrderTicket hotkey submit (Ctrl+Shift+B / Ctrl+Shift+S)

**Commit 96983cec** — Phase 35 ships hotkey-driven order submission.
Pattern: extract the render-path action (submit button click) into a
public method, then wire a hotkey action to it via dispatchAction.

## What landed

- 2 new `HotkeyAction` values: `SubmitBuy=31`, `SubmitSell=32`,
  `COUNT=33`
- Default bindings: `Ctrl+Shift+B` (SubmitBuy), `Ctrl+Shift+S`
  (SubmitSell)
- `OrderTicket::submit()` extracted from the render path as a public
  method. Returns `false` on bad draft (qty=0 or fillPx=0) or missing
  callback, `true` when the callback fires. The render path's
  Submit button now calls `submit()` — same code path as the hotkey.
- `OrderTicket::setSideBuy(bool)` setter for flipping side without
  going through render
- `WindowManager::dispatchAction(HA::SubmitBuy/SubmitSell)` opens the
  ticket in the matching side if closed, otherwise flips side +
  submits

## Patterns confirmed in this phase

### Pattern: extract-the-button — the right way to add a hotkey for an existing UI action

When the user asks for a hotkey for an action that already has a UI
button, the move is NOT to re-implement the action in
`dispatchAction`. Instead:

1. Find the existing button handler in `render()` — the bit that runs
   when `ImGui::Button(...)` is clicked.
2. Extract the BODY of that branch (the side-effects, the callback
   fire) into a public method on the widget class.
3. Have the render path's button call the new method.
4. Wire the hotkey's `dispatchAction` case to call the same public
   method.

`OrderTicket::submit()` is the canonical example. The render path's
"Submit BUY/SELL" button + the Ctrl+Shift+B/S hotkey + the
Ctrl+Enter-on-ticket shortcut now all flow through the same
`submit()` method. Adding a 4th trigger path (a right-click context
menu, a scheduled job, a remote command) is one more line, not a
re-implementation.

**This pattern generalizes to ANY widget action the user might want
to script or hotkey.** ThemeEditor::applySnapshot,
PositionBook::flatten, RiskGuard::addRealized — all would benefit
from the same treatment. When you're about to add a hotkey, look
for the existing button first.

### Pattern: chord-selection for new hotkey actions

The `HotkeyBinding` struct (Phase 21) deliberately lacks an Alt
modifier flag because Alt conflicts with WM keys on Linux
(Alt+Tab, Alt+F4 are owned by the window manager). When the user
asks for a hotkey like "Alt+B", the right move is:

1. **Explain in the commit message WHY** Alt doesn't work — the
   no-Alt note in `hotkey_config.hpp` is the canonical reference.
2. **Offer the closest available chord** — `Ctrl+Shift+X` for
   single-letter shortcuts. Browser-recognizable: Ctrl+Shift+B =
   toggle bookmark bar, Ctrl+Shift+S = "save as" — same muscle
   memory cue.
3. **Verify the chord doesn't conflict** with an existing default
   binding. `match()` routes chord-to-action; the test asserts
   `map.has(HA::SubmitBuy)` AND `map.get(SubmitBuy).glfwKey == 'B'`
   AND `.ctrl && .shift` AND nothing else maps to that chord.

**Caveat:** adding an Alt field to `HotkeyBinding` is technically
possible (the `m_bind` map is `std::map<HotkeyAction, HotkeyBinding>`,
just add `bool alt` to the struct) BUT the change ripples to:
- `hotkey_config.cpp` parseBinding() to read "Alt+" prefix
- `hotkey.ini` file format (loaded via parseBinding) — any existing
  user files with "Alt+" lines would parse correctly, no migration
- HotkeyEditor modal display (currently labels as "Ctrl+Shift+X"
  hardcoded in places) — needs a third label
- All N-parallel enum tests (Phase 31 pattern) — the
  `bBuy.ctrl && bBuy.shift` assertion becomes
  `bBuy.ctrl && bBuy.shift && bBuy.alt` for the new variant

If the user actually wants Alt+B and is OK with the file-format
ripple, do it as a separate change. The chord workaround is the
low-risk interim.

### Pattern: `setSideBuy` as a public setter for hotkey-driven side flipping

When a widget's state (side, type, mode) needs to be mutated by a
non-render trigger (hotkey, command palette, remote control), the
right move is to expose a public setter — NOT to synthesize a fake
UI click or to duplicate the state-machine logic in the dispatcher.

`OrderTicket::setSideBuy(bool)` is the setter pattern. It mutates
`m_sideIsBuy` directly. The render path's "click to toggle side"
button is the OTHER mutation site; both call the same internal
field, both observe the same internal state, both go through
`submit()` when submitting. The setters are the public API
surface; the render path is one consumer of those setters.

**Generalizes to:** `setTypeIsLimit(bool)` (if the user later asks
for a hotkey to flip market↔limit), `setQuantity(double)` (for a
hotkey to bump qty by ±0.01), `setReferencePrice(double)` (for a
hotkey to pin ref to the latest trade). Add the setter when the
hotkey arrives, not preemptively — YAGNI for hotkeys that aren't
requested.

## Tests added (Test 42, 9 invariants)

1. Default side is BUY, type is MARKET, ticket is closed
2. `setSideBuy(false)` flips to SELL
3. `setSideBuy(true)` flips back to BUY
4. `submit()` without a callback + bad draft returns false (no crash)
5. `submit()` with bad draft does NOT fire the callback
6. `SubmitBuy` and `SubmitSell` registered in `HotkeyMap::defaults()`
7. `SubmitBuy` binds `Ctrl+Shift+B`, `SubmitSell` binds `Ctrl+Shift+S`
   (key + ctrl + shift)
8. `match(Ctrl+Shift+B/S)` routes correctly; `match(plain B)` does
   NOT (so users can type "B" and "S" in input fields without
   accidentally submitting)
9. `actionName(SubmitBuy/Sell)` round-trips through the string
   formatter

## Sprint progression

- 25 commits
- 23 widgets
- 42 tests, 274 ✓ checks, 0 failures

## Lessons carried forward (Sprint 35 specifically)

- **The "extract-the-button" pattern is the right way to add a hotkey
  for an existing UI action.** Find the button, extract its body into
  a public method, call from both render and dispatch.
- **The "chord-selection" pattern handles the no-Alt limitation.**
  Ctrl+Shift+X is a familiar browser chord and doesn't conflict with
  input-field typing. Don't add Alt to HotkeyBinding unless the user
  is OK with the file-format ripple.
- **Public setters for state hotkeys.** `setSideBuy(bool)` is the
  pattern; `setTypeIsLimit`, `setQuantity` etc. will follow the same
  shape as more hotkey requests land.

## Open / next (deferred from Phase 35 onward)

- Add Alt modifier to `HotkeyBinding` (breaks file format, do as
  separate change)
- Position calculator hot-recalc on symbol/price change
- Multi-monitor DPI awareness for GLFW window
- OrderTicket limit-price hotkey (Alt+L = open ticket in limit mode
  pre-loaded with the latest trade price)
- OrderTicket quick-quantity hotkeys (Ctrl+= / Ctrl+- = bump qty by
  0.01)
- WindowManager::setQuantity(double) and setLimitPrice(double) as
  the public setters for the above
- DOMWidget heatmap density slider (already wired to
  `heatmapDensity` setting; needs to call `setCellHeightPx` on the
  widget)
- Theme editor preview pane (live apply-as-you-type instead of
  Save button)
