# BTQuant Vulkan — Phase 21: HotkeyMap (user-mappable bindings)

**Date:** 2026-06-20
**Scope:** Data-layer HotkeyMap with 22 actions, persistence to
`~/.config/btquant_vulkan/hotkeys.ini`, F-key table refactor for runtime
remapping, Test 28 (8 invariants).

## What landed

- `src/util/hotkey_config.{hpp,cpp}` — new `util::HotkeyMap` class
  + 22-action `HotkeyAction` enum.
- `WindowManager`:
  - new `m_hotkeyMap` member (pointer to `util::HotkeyMap`)
  - constructor loads `~/.config/btquant_vulkan/hotkeys.ini`
    (`loadFromFile` static; fallback to `defaults()` on miss/malformed)
  - constructor auto-saves the resolved map back to disk so the user
    has a concrete template to edit
  - destructor `delete m_hotkeyMap`
- F-key table refactored from `(glfwKey, member-ptr)` to
  `(HotkeyAction, member-ptr)`. Runtime consults
  `m_hotkeyMap->get(action).glfwKey` so user remappings take effect
  without recompiling the table.
- Test 28 (8 invariants): defaults, round-trip remap, comments+
  Ctrl+Shift parsing, nullopt-on-missing-file, match() respects
  modifiers, label round-trip, enumerate covers all 22.

## Format & semantics

INI key=value, one binding per line:

```
# Comments start with '#', blank lines ignored.
# Format: ActionName=Ctrl+Shift+K (Ctrl/Shift optional; K = key)
ToggleOrderBook=F2
KillSwitch=Ctrl+K
OpenSymbolPicker=Ctrl+Shift+P
```

22 actions — full enum at the top of `hotkey_config.hpp`:
`ToggleOrderBook`, `ToggleOrderBookDepth`, `ToggleDOM`, `ToggleTrades`,
`ToggleTPO`, `ToggleFootprint`, `ToggleVPVR`, `ToggleAlerts`,
`ToggleMultiVWAP`, `ToggleRiskPanel`, `ToggleSettings`,
`ResetLayout`, `OpenSymbolPicker`, `OpenThemeEditor`,
`ToggleOrderTicket`, `TogglePositionPanel`, `ToggleRiskLimits`,
`ToggleMiniPriceChart`, `KillSwitch`, `ToggleStats`,
`ToggleHotkeyHelp`, `ToggleHotkeyEditor`.

## Design decisions

- **`HotkeyMap::defaults()` is the single source of truth** for the
  default key bindings. Adding a new action requires editing FOUR
  places in `hotkey_config.cpp`: the enum, `defaults()`,
  `actionName()`, and the implicit coverage from `enumerate()`.
- **No Alt key** in the modifier set — collides with WM keys on
  Linux/Wayland. Ctrl and Shift only.
- **`HotkeyBinding` is a POD** — `glfwKey`, `ctrl`, `shift`. Equality
  operator compares all three so partial matches never fire
  accidentally. `matches()` takes a live `glfwGetKey` snapshot +
  observed modifier state and returns true only when all three align.
- **`loadFromFile` is `static`** — see pitfalls section.
- **`m_hotkeyMap` is owned by `WindowManager`**, not by `main.cpp`.
  WindowManager writes the file, reads it back, deletes it on
  destruction. `main.cpp` has zero hotkey-related code.
- **F-key table is hand-rolled** (per Phase 8's lesson — the table
  shape differs from the help overlay, don't unify them). The new
  shape uses `(HotkeyAction, member-ptr)` so the runtime can swap
  the underlying key without rebuilding the table.

## Pitfalls (Phase 21)

- **`HotkeyMap::loadFromFile` MUST be declared `static` in the
  header** — it's a factory that returns a new `HotkeyMap` and
  does not need an instance. I shipped it as non-static and called
  it as `HotkeyMap::loadFromFile(path)`, producing this German
  compile error in BOTH `window_manager.cpp` AND `test_integration.cpp`:
  `Elementfunktion »std::optional<btquant::util::HotkeyMap>
  btquant::util::HotkeyMap::loadFromFile(const std::string&)«
  kann nicht ohne Objekt aufgerufen werden`. Fix: add `static` to
  the declaration. Symptom pattern: a method that does not access
  `m_bind` and constructs the result from scratch needs `static`
  in BOTH the declaration and the definition.
- **`replace_all=true` on `test/CMakeLists.txt` is destructive when
  the same line appears multiple times** — three identical
  `theme_io.cpp` / `position_calculator.cpp` lines existed from
  Phase 10/12/15 edits, and `replace_all=true` inserted
  `hotkey_config.cpp` into all three, producing
  `../src/widgets/position_calculator.cpp/src/util/hotkey_config.cpp`
  (concatenated garbage path) and a second copy of the rest of the
  list. Fix: NEVER use `replace_all=true` on structural config
  files. Read the file, find a unique anchor with surrounding
  context, and patch manually. The diff shows clearly that
  `replace_all=true` is the wrong tool whenever the search string
  is NOT actually unique.
- **The `BTQUANT_HOTKEY_CONFIG_NO_GLFW` guard was overengineered and
  was reverted** — I initially wrapped the GLFW include with a
  `#ifdef BTQUANT_HOTKEY_CONFIG_HAS_GLFW` + inlined key constants
  for the test build. That made the file 90 lines longer and the
  inlined constants conflict with the real `<GLFW/glfw3.h>` values
  in any build that links GLFW. Simpler: include `<GLFW/glfw3.h>`
  unconditionally, since BOTH the main binary and `test_integration`
  already link GLFW (vulkan_context.cpp needs it). This generalizes
  to ANY util file that needs key constants: GLFW is always
  available in this build, don't bother with conditional compilation.
- **The two-CMakeLists trap now also fires for util files, not just
  widgets** — adding `hotkey_config.cpp` to the main `CMakeLists.txt`
  was NOT enough; `test_integration` failed at link with undefined
  references to `HotkeyMap::loadFromFile`, `defaults()`, etc. The
  diagnostic signature is the same as Phase 15/19: main app builds
  green, test build fails at link. Internalize the two-edit rule
  for ALL new `.cpp` files (util, data, widgets), not just widgets.
- **`Test N` numbering counts sub-blocks, not just `Test N: ...`
  headers** — when adding Test 28 to `test_integration.cpp`, the
  file already had 27 numbered test blocks. Continue the sequence
  to 28, don't restart. Keep the header comment
  `// Test 28: <feature>...` consistent with the existing format
  (subject under test + colon + brief description).
- **First build attempt for any new util/header pair usually fails
  with a header include or symbol visibility issue** — this turn
  had TWO such issues: (1) `static` missing on `loadFromFile`, and
  (2) the test file didn't have `#include <GLFW/glfw3.h>` so
  `GLFW_KEY_F2` etc. were undeclared. Build, read the errors
  carefully, fix the root cause (not the surface symptom). The
  German clang error wording ("kann nicht ohne Objekt aufgerufen
  werden") is verbose but informative — translate to English and
  the fix is usually obvious.

## Member-pointer dispatch pattern (reusable)

```cpp
// In the .cpp anonymous namespace:
struct HotkeySlot {
    HotkeyAction action;
    bool WindowManager::*flag;  // member pointer
};
constexpr HotkeySlot kHotkeys[] = {
    { HotkeyAction::ToggleOrderBook,      &WindowManager::showOrderBook      },
    // ...
};

// In the hotkey loop:
for (size_t i = 0; i < N; ++i) {
    int boundKey = m_hotkeyMap->get(kHotkeys[i].action).glfwKey;
    bool ctrlReq = m_hotkeyMap->get(kHotkeys[i].action).ctrl;
    // ...
    if (keyPressed && !prevPressed[i]) {
        this->*(kHotkeys[i].flag) = !(this->*(kHotkeys[i].flag);
    }
}
```

The data layer (`HotkeyMap`) owns the key bindings; the dispatch
table (`kHotkeys[]`) owns the action→flag mapping. The two are
decoupled — adding a new action requires only the enum, the default
binding, and one line in `kHotkeys[]`. The runtime lookup means the
user can remap F2 to F3 in `hotkeys.ini` without touching any code.

## Lessons carried forward

- **Use `${PIPESTATUS[0]}` after pipe** — still applies, but no
  verification command in this turn hit the bug (no pipe after a
  binary that could fail).
- **Don't pause for approval after the FRAG NICHT IMMER SO BEHINDERT
  trigger** — applied end-to-end: picked HotkeyMap from the deferred
  list, designed the data layer, wrote it, integrated the table,
  wrote tests, ran build+tests, committed, saved to memory. No
  "Soll ich auch noch Y?" or "Was wäre mit Z?" closing question.
  The numbered list at the bottom of any phase reference IS the
  authorization.
- **One substantial commit per turn is the rhythm** — single commit
  `d83e4bb3`, 16 files, 1062 insertions, 28 deletions, one feature
  (HotkeyMap data layer + WindowManager wiring + Test 28).
- **Pitfalls from earlier phases all still apply**:
  - Two-CMakeLists edit (#15, #19)
  - Forward-decl at global scope (#22)
  - Load persisted state before init (#8 Phase 8)
  - Auto-write template file on first launch (similar to
    `create_directories(parent)` from Phase 7 — proactively create
    the artifact the user will edit)
  - 22nd widget = data layer (no UI yet). UI editor ships next
    turn (Ctrl+H capture-next-key flow).