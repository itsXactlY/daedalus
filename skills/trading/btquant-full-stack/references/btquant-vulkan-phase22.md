# BTQuant Vulkan — Phase 22

**Scope:** HotkeyEditor widget (Ctrl+H) — runtime remap of HotkeyMap bindings
via ImGui 3-column table + capture-next-key flow. 23rd widget, 19 commits /
23 widgets / 29 tests.

## New widget: `widgets::HotkeyEditor`

`src/widgets/hotkey_editor.{hpp,cpp}` — paired with the Phase 21
`util::HotkeyMap`. Renders an ImGui window with three columns:
**Action | Current Binding | [Remap][Reset]**.

Public API (the test seam):

```cpp
void setHotkeyMap(::btquant::util::HotkeyMap* m);
bool isOpen()  const;
void setOpen(bool v);
void toggleOpen();

bool isDirty() const;
void clearDirty();

void beginCapture(int actionIndex);   // enter capture state for action[i]
void injectCapture(int glfwKey, bool ctrlDown, bool shiftDown);
                                       // drive the capture state machine

bool isCapturing() const;             // public query of m_capturing
int  capturingAction() const;
```

## WindowManager wiring

Forward-declare `widgets::HotkeyEditor`, add a member + `m_hotkeyEditorOpen`
flag (used by the View menu), instantiate after `m_miniPriceChart`. The map
is wired via `setHotkeyMap(&*m_hotkeyMap)` after `m_hotkeyMap` is loaded
(constructor order: hotkey map loads AFTER the editor is created).

`Ctrl+H` toggles `m_hotkeyEditorOpen` and `m_hotkeyEditor->toggleOpen()` in
lock-step. The menu entry reads/writes `m_hotkeyEditorOpen` and re-syncs
the editor's `isOpen()` flag every frame:

```cpp
if (ImGui::MenuItem("Hotkey Editor (Ctrl+H)", nullptr, &m_hotkeyEditorOpen)) {
    if (m_hotkeyEditor) m_hotkeyEditor->setOpen(m_hotkeyEditorOpen);
    markSettingsDirty();
}
```

`showHotkeyEditorWindow()` (called from main.cpp's render chain) reads the
flag, sets the editor's open state, renders, then syncs BACK in case the
user closed via the [X] button:

```cpp
void WindowManager::showHotkeyEditorWindow() {
    if (!m_hotkeyEditor) return;
    m_hotkeyEditor->setOpen(m_hotkeyEditorOpen);
    m_hotkeyEditor->render();
    m_hotkeyEditorOpen = m_hotkeyEditor->isOpen();   // sync back
    if (!m_hotkeyEditorOpen && m_hotkeyEditor->isDirty()) {
        m_hotkeyEditor->clearDirty();
        if (m_hotkeyMap) m_hotkeyMap->saveToFile(m_hotkeyPath);
    }
}
```

## Capture-loop in `processHotkeys`

When the editor is open AND the user clicks [Remap], `m_capturing = i`. The
hotkey loop scans GLFW keys 32..511 for a rising edge and routes the first
non-modifier hit into `injectCapture`. Modifier-only keys are rejected but
the capture stays open (so holding Shift while pressing the actual letter
works). Esc cancels; sentinel `-1` is a test-friendly cancel signal.

```cpp
if (m_hotkeyEditor && m_hotkeyEditor->isOpen()) {
    static bool prevCapturedKeys[512] = {};
    for (int key = 32; key < 512; ++key) {
        bool down = glfwGetKey(win, key) == GLFW_PRESS;
        if (down && !prevCapturedKeys[key] && !textFieldFocus) {
            m_hotkeyEditor->injectCapture(key, ctrlDown, shiftDown);
            prevCapturedKeys[key] = true;
            if (m_hotkeyMap) m_hotkeyMap->saveToFile(m_hotkeyPath);
            break;
        }
        prevCapturedKeys[key] = down;
    }
}
```

`m_hotkeyPath` is a new member so `saveToFile` works from the hotkey loop
(the original `hotkeyPath` was a constructor-local `std::string`).

## Test 29 — 11 invariants

Widget state machines need a different test surface than the pure-math
seam used by trader widgets. The pattern for capture/modality widgets is:

1. `isOpen() / isDirty() / isCapturing()` initial state
2. `setOpen(true) / toggleOpen()` lifecycle
3. `setHotkeyMap(nullptr)` safety check — no-op without crash
4. `beginCapture(i)` followed by `injectCapture(ESC)` — Esc cancels,
   map unchanged, dirty=false, capturing=false
5. `beginCapture(i)` followed by `injectCapture(key, ctrl, shift)` —
   map updated, dirty=true, capturing=false (capture exited cleanly)
6. `beginCapture(i)` followed by `injectCapture(modifierOnlyKey)` —
   map unchanged, dirty=false, capturing=true (STAYS OPEN — user is
   still holding Shift)
7. After (6), `injectCapture(realKey)` — capture completes
8. `clearDirty()` — flag resets without touching map
9. Sentinel `-1` cancels capture without applying

The "STAYS OPEN" assertion on modifier-only keys is what catches a
common off-by-one error where the cancel logic incorrectly fires on
modifier presses too.

## Pitfalls

- **Patch removed definition but kept declaration**: Phase 22 patched
  `showMiniPriceChartWindow()` and accidentally removed the original
  body, then added a duplicate `showHotkeyEditorWindow()` body INSIDE
  it. Symptom: cascade of `function_definition_not_allowed` + `expected
  '}'` errors at the end of the file. Fix: ALWAYS re-read the function
  body with offset/limit pagination BEFORE patching, especially when
  multiple sibling subagents have edited the same file. When the patch
  result mentions "LSP diagnostics introduced", check for duplicate
  braces BEFORE chasing the named errors. The errors near the file's
  end are SYMPTOMS of an earlier patch mismatch, not the cause.

- **`beginCapture(i)` is the public test seam for internal state
  machines**: when a widget has private state (e.g. `m_capturing`)
  that tests need to drive, expose a public `beginX(i)` method rather
  than making the internal field public or writing tests that
  trivially pass when the state is never entered. The widget's render
  path calls `beginCapture` from the [Remap] button; tests call it
  directly. Without this, the test suite proves only that
  `injectCapture` no-ops without entering capture — worthless.

- **Widget internal `isOpen()` must sync back to WindowManager's flag
  every frame**: when the user closes a docked window via the [X]
  button, only the widget's internal flag changes. WindowManager's
  outer boolean (used for menu state, settings persistence, etc.)
  stays `true`. Fix: `outer_flag = widget->isOpen();` at the end of
  every render call. Otherwise the menu checkbox and the on-screen
  window go out of sync — user clicks "Hotkey Editor" in the menu,
  sees the window, clicks the [X], the window closes, but the menu
  checkbox still shows checked.

- **Capture-loop must persist `hotkeys.ini` on every successful
  remap**: don't wait for the user to close the editor or the
  application. Each successful `injectCapture` writes the file
  immediately. A crash before close should not lose the remap.
  Pattern: `if (m_hotkeyMap) m_hotkeyMap->saveToFile(m_hotkeyPath);`
  inside the loop right after `injectCapture`.

- **GLFW key scan range 32..511** covers printable ASCII (32-126),
  GLFW_KEY_ESCAPE (256), GLFW_KEY_ENTER (257), GLFW_KEY_TAB (258),
  GLFW_KEY_BACKSPACE (259), and the F1-F25 range (290-314). Plus
  cursor / arrow / nav keys (up to 348). Iterating the full range
  every frame is ~500 glfwGetKey calls; cheap at 60fps. Going past
  511 is undefined (GLFW_KEY_LAST was 348 in older versions but the
  spec allows extension up to 511).

- **Constructor-order dependency for `setHotkeyMap`**: the editor
  instance is created BEFORE `m_hotkeyMap` is loaded (the map needs
  the hotkeyPath string which is composed from `configDir`). Pattern:
  `new HotkeyEditor();` early in the ctor → load hotkey map later →
  `editor->setHotkeyMap(m_hotkeyMap);` after the load. Don't try to
  inline the map into the editor constructor — circular dependency
  on the file path.

## Sprint progression

Phase 22: HotkeyEditor widget + capture flow + Ctrl+H dispatch.
12 commits / 23 widgets / 29 tests. The HotkeyMap data layer from
Phase 21 now has a UI on top of it; F-key table consults the map for
runtime remaps; Ctrl-prefixed hotkeys (Ctrl+L/P/T/B/R/M/K) are still
hardcoded inline — moving them to the map is the next item on
"Open / next".