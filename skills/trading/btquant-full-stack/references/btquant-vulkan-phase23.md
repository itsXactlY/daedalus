# NEW engine: Phase 23 — Hotkey dispatch unification

## What landed

Three commits, one feature, each independently shippable:

1. **HotkeyMap data layer** — 22 actions, persistence via
   `~/.config/btquant_vulkan/hotkeys.ini`, F-key table refactor to
   `(HotkeyAction, member-ptr)` for runtime lookup. Test 28 (8 checks).
2. **HotkeyEditor widget** — `Ctrl+H` opens a 3-column ImGui table
   (`Action | Current Binding | Remap / Reset`). Capture-next-key flow:
   `[Remap]` enters capture state, next non-modifier keypress becomes
   the binding, Esc cancels, modifier-only keys leave capture open.
   Test 29 (11 checks).
3. **Unified `dispatchAction()` refactor** — deleted 10+ duplicate
   edge-trigger blocks (Ctrl+L/P/T/Enter/B/K/R/M, Shift+F1, Shift+/).
   ONE loop over `m_hotkeyMap->enumerate()` with
   `prevAction[HotkeyAction::COUNT]` per-action debounce. Single
   `dispatchAction(HotkeyAction)` switch holds the side-effects.
   Hotkey Reference overlay reads live bindings from the map (was
   hardcoded). Test 30 (6 checks).

## Architecture: the three-layer hotkey system

```
+----------------------------------------------------------+
| Layer 1: HotkeyMap (util::HotkeyMap)                     |
|   - 22-action enum (HotkeyAction::COUNT = 22)            |
|   - bindings: map<HotkeyAction, HotkeyBinding>            |
|   - persistence: loadFromFile/saveToFile INI format      |
|   - match(key, ctrl, shift) -> HotkeyAction or COUNT      |
+----------------------------------------------------------+
                          ^
                          | consulted per-frame
+----------------------------------------------------------+
| Layer 2: WindowManager::processHotkeys                   |
|   - kHotkeys[] table: (HotkeyAction, bool WM::*flag)     |
|     for F2..F12 toggle widgets - uses member pointers    |
|   - Unified loop: enumerate() -> match -> dispatchAction  |
|     for everything else                                  |
+----------------------------------------------------------+
                          ^
                          | calls
+----------------------------------------------------------+
| Layer 3: WindowManager::dispatchAction(HotkeyAction)    |
|   - Single switch statement, side-effect per action      |
|   - Kill switch path lives here (flatten + journal)      |
|   - Modal toggles, panel toggles, overlay toggles        |
+----------------------------------------------------------+
```

F-key toggles stay on the `kHotkeys[]` table because member pointers
cleanly express the bool toggle. Everything else flows through the
unified loop -> `dispatchAction()`. `ToggleHotkeyEditor` (Ctrl+H) is
in BOTH paths: the early-exit capture-loop block runs first so the
H keypress doesn't get consumed by capture routing.

## Pitfalls

- **`patch replace_all=true` on multi-line function bodies**: when
  the original line is duplicated (e.g. a previous patch left an
  orphan `void WindowManager::showMiniPriceChartWindow()` line
  because the sibling subagent also touched the file), `replace_all`
  injects the replacement into BOTH lines, producing
  `void WindowManager::showMiniPriceChartWindow() {` followed by
  `void WindowManager::showMiniPriceChartWindow() {` on the next
  line. The error chain is "function definition not allowed here"
  -> "expected }" -> "too many errors". Diagnose by reading the diff,
  not the LSP errors (which point to the END of the file, hundreds
  of lines past the actual damage). Always grep the file for
  duplicate definitions before patching function bodies.

- **`(void)parameter;` is a footgun**: when patching the start of a
  function, the impulse is to add `(void)paramName;` to silence
  unused-variable warnings. If the parameter is actually used later
  in the function (the warning was a false positive that another
  patch fixed), the explicit `(void)` cast triggers a different
  error. Don't add `(void)` casts defensively — let the compiler
  tell you if it's actually unused.

- **`F2..F12 toggle widgets stay on the kHotkeys[]` table; the
  unified loop handles ONLY non-toggle actions**: trying to merge
  both into the unified dispatch is tempting but the F-key path's
  `(bool WindowManager::*flag)` member-pointer pattern is much
  cleaner than an 11-arm switch for the bools. Keep the dual path:
  the table for toggles, the loop for everything else.

- **`ToggleHotkeyEditor` (Ctrl+H) is in BOTH paths**: the early-exit
  block in `processHotkeys` handles the press BEFORE the capture
  loop and BEFORE the unified dispatch, so the same-frame H press
  doesn't get routed to capture injection (which would set
  `m_capturing = some-row` from a real H keypress the user
  intended as the editor toggle). The unified dispatch has its own
  `case HA::ToggleHotkeyEditor` for menu/menu-toggle symmetry —
  both call `toggleOpen()` so it's idempotent.

- **Replace `prevCtrlL = currCtrlL;` and similar statics when
  unifying the dispatch**: the per-key `static bool prevCtrlX`
  pattern gets deleted along with the per-key block. If you miss
  one (e.g. `prevCtrlM = currCtrlM;` left at the bottom of the
  file as a dangling assignment), the compiler fires
  "use of undeclared identifier 'prevCtrlM'" because the static
  was in the block you deleted. Grep for `prevCtrl` / `prevShift`
  / `prevQuestionMark` after the unification patch.

- **Header must include `hotkey_config.hpp` when declaring
  `dispatchAction(HotkeyAction)`**: the `HotkeyAction` enum lives
  in `util::HotkeyAction` namespace. Forward-declaring it via
  `namespace btquant::util { enum HotkeyAction : int; }` works for
  the parameter type, but `HotkeyMap::match()` etc. in the cpp need
  the full enum definition. Include the header directly in the
  manager header — don't try to forward-declare an enum.

- **`Match()` against an action index is meaningless if HotkeyAction
  ever gets re-ordered**: the unified loop uses
  `int idx = static_cast<int>(action);` as the prevAction array
  index. If anyone inserts/removes enum values, the array still
  covers `[0..COUNT)`, but the index-meaning changes. Always test
  the dispatch end-to-end after enum edits; don't rely on the
  prevAction array bound check alone.

- **HotkeyHelp overlay reads live bindings from m_hotkeyMap (was
  hardcoded)**: when the user remaps F2->F3 in the editor, the help
  window must reflect F3 on the next open. The overlay used to be
  a hand-rolled `row("F2", "...")` table; refactor to
  `display(HA::ToggleOrderBook, "Toggle Order Book")` and read the
  label from `m_hotkeyMap->get(a).label()`. If you forget the
  refactor, remappings appear invisible to the user.

- **Test 30 simulates the save->reload->match() round-trip**: the
  unified dispatch is only correct if the load-from-disk path
  restores the live bindings. Test 30 uses a tmp dir under
  `/tmp/btquant_test_hotkey_remap/hotkeys.ini`, writes a remap,
  reloads, asserts match() returns the remapped action for the new
  key and COUNT for the old key. Covers the full disk-to-runtime
  round-trip in one test block.

## Lessons carried forward

- **The "FRAG NICHT IMMER SO BEHINDERT" trigger fires 3x in this
  phase**: one per commit (HotkeyMap data layer -> HotkeyEditor
  widget -> unified dispatchAction). Each reply shipped, committed,
  reported one line, started the next. The trigger persists across
  the entire session, across all three commits. The pattern is
  now documented in three phase notes (17, 22, this one) — when in
  doubt during a Phase >=17 sprint, default to "ship the next item,
  no clarifying question, 3-line report".

- **One substantial commit per turn is the rhythm**: each of the
  three Phase 23 commits was 200-500 lines (data layer, widget,
  refactor). Trying to combine all three into one mega-commit would
  have broken the build mid-turn AND made the test-running step
  harder. Three sequential commits, each green, is the cadence
  that matches the trigger cadence.

- **`dispatchAction()` is the single source of truth for non-toggle
  side-effects**: future hotkey additions (e.g. "Show Onboarding",
  "Reset Risk Session") go in the switch statement, the default
  map, the test loop, and the editor table — but NEVER as
  per-key blocks again. The cost of the unified loop is paid once,
  in the dispatch table.

- **The "two-CMakeLists" trap now fires for util files too**
  (re-stated from Phase 21): `hotkey_config.cpp` had to be added
  to BOTH `CMakeLists.txt` AND `test/CMakeLists.txt` for the test
  build to link. The diagnostic signature (main builds green, test
  fails at link with `undefined reference to ...::loadFromFile`) is
  the same as for widgets.

- **`loadFromFile` MUST be declared `static`** (re-stated from
  Phase 21): the German compile error "Elementfunktion »...« kann
  nicht ohne Objekt aufgerufen werden" means "member function
  called without an object" — fix is `static` on both declaration
  and definition. Applies to any factory method that doesn't
  access instance state.

## Phase 24 deferred (open / next)

- Persist RiskConfig to state.ini (RiskLimitsPanel edits lost on restart)
- Journal replay -> PositionBook rehydration on startup
- Layout profiles (.btqlayout)
- DOM heatmap widget
- Candlestick bodies via raw draw-list (ImPlot lacks PlotCandlestick)
- 13 commits / 23 widgets / 30 tests / 0 TODOs in core flow