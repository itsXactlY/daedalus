# BTQuant Vulkan — Phase 27: WindowManager Save/Load Layout Menu Wiring

Sprint state at start: 16 commits / 23 widgets / 33 tests / LayoutIO
data layer shipped (Phase 26). Sprint state at end: 17 commits /
23 widgets / 34 tests. Open from Phase 26: "Wire LayoutIO into
WindowManager UI — Save/Load menu items calling the API we just
shipped".

## What shipped

`WindowManager::applyLayoutSnapshot(const util::LayoutSnapshot& snap)`
— single-pass copy of every layout-relevant field:
1. **11 widget visibility bools**: showOrderBook, showOrderBookDepth,
   showFootprint, showVPVR, showMultiVWAP, showRiskPanel, showDOM,
   showTrades, showTPO, showSettings, showStatsOverlay.
2. **Theme + general scalars** owned by WindowManager: theme,
   heatmapDensity, fpsLimit. (`tradeWindowSeconds` is NOT touched —
   it lives only in Settings; the markSettingsDirty() + next save
   cycle writes it back to state.ini.)
3. **Risk config → RiskGuard**: copy the 4 `risk_*` doubles into a
   fresh `RiskConfig` and call `m_riskGuard->setConfig(c)`. This
   propagates to `checkOrder()` immediately.
4. **Dock reset**: call `requestDockLayoutReset()` so the next
   `applyInitialDockLayoutIfNeeded()` rebuilds the dock with the
   new visibility set. `markSettingsDirty()` so the next save
   cycle persists the booleans to state.ini.
5. **Dock text** from `snap.dockLayout` is logged ("dock text N
   bytes") but NOT auto-restored — applying it mid-session needs
   `ImGui::DockBuilderLoadNodes()` which requires a live dockspace.
   Stored in the .btqlayout file for a future iteration that does
   the restore at the right moment (post-dockspace-creation).

`WindowManager::saveLayoutAs(const std::string& name)`:
```cpp
util::Settings s = captureCurrentSettings();
util::LayoutSnapshot snap = util::LayoutIO::fromSettings(s, "", name);
auto path = util::LayoutIO::layoutPath(name);
return util::LayoutIO::save(path, snap);
```
Empty `dockLayout` for now (no live capture yet). Returns true on
success, false on write failure (logged via BTQ_LOG_WARN).

`WindowManager::loadLayout(const std::string& name)`:
```cpp
auto path = util::LayoutIO::layoutPath(name);
auto snap = util::LayoutIO::load(path);
if (!snap.has_value()) { log + return false; }
applyLayoutSnapshot(*snap);
log + return true;
```

View menu integration: new `Layout` submenu with three actions:
- "Save layout as…" — sets `m_layoutSaveOpen = true`, opens a modal
  popup with a text input for the profile name + Save/Cancel
  buttons. On Save: `saveLayoutAs(name)`, close popup.
- "Load layout…" — sets `m_layoutLoadOpen = true`, opens a modal
  popup listing existing `.btqlayout` files via `LayoutIO::list()`.
  Click one: `loadLayout(name)`, close popup.
- Quick-pick submenu — every `.btqlayout` file as a menu item
  directly, no modal. Skips the list popup for known profiles.

## Patterns that emerged

### Modal popup pattern (matches Phase 11)

```cpp
// In render() — typically at the end of showMainMenu() or wherever
// the menu lives.
if (m_layoutSaveOpen) {
    ImGui::OpenPopup("Save Layout");
    m_layoutSaveOpen = false;  // one-shot, gate the OpenPopup
}
if (ImGui::BeginPopupModal("Save Layout", nullptr,
                           ImGuiWindowFlags_AlwaysAutoResize)) {
    ImGui::InputText("Profile name", m_layoutNameBuf,
                     sizeof(m_layoutNameBuf));
    if (ImGui::Button("Save")) {
        if (saveLayoutAs(std::string(m_layoutNameBuf))) {
            ImGui::CloseCurrentPopup();
        }
    }
    ImGui::SameLine();
    if (ImGui::Button("Cancel")) ImGui::CloseCurrentPopup();
    ImGui::EndPopup();
}
```

The `if (m_xxxOpen) { OpenPopup; m_xxxOpen = false; }` pattern is
REQUIRED — `OpenPopup` must run BEFORE `BeginPopupModal` in the same
frame, otherwise the popup appears one frame late. The `m_xxxOpen`
flag is a one-shot; resetting it inside the `if` prevents a re-open
loop. This is the same pattern documented in Phase 11 for
SymbolPicker.

### Type taken by const-ref in declaration → include the full header

`window_manager.hpp` has been getting away with forward-declaring
types like `class HotkeyMap;` because they're used as raw pointers
(`HotkeyMap*`). But Phase 27's `applyLayoutSnapshot(const
LayoutSnapshot& snap)` takes the type by const-ref in the
declaration. Forward-declaration is INSUFFICIENT for that — the
compiler needs the full type to know the function signature.

Symptom: `No type named 'LayoutSnapshot' in namespace 'btquant::util'`
when `applyLayoutSnapshot` is declared in the header.

Fix: `#include "../util/layout_io.hpp"` in window_manager.hpp (top
of the file, with the other util includes). NOT a forward-declare.
Generalizes: ANY type used by-value or by-const-ref in a header
declaration needs the full include, not just a forward-declare.
Pointer members (`T*`) can stay as forward-declares; only the
const-ref / value-by-parameter cases need the full type.

### Public bool members are valid test accessors

WindowManager declares `bool showOrderBook = true;` etc. as PUBLIC
members (in the public block of the class). Test 34's first
attempt used `wm.isOrderBookOpen()` etc. — which don't exist. The
fix is to read `wm.showOrderBook` directly. No need to add getter
methods for fields that are already public.

Same logic applies to `theme`, `heatmapDensity`, `fpsLimit` if
those need to be tested directly. The `m_xxx` private members
(intentional hidden state) need friend declarations or getter
methods; the public bools do not.

### HOME-redirect for tmp-dir WindowManager tests

```cpp
namespace fs = std::filesystem;
fs::path fakeHome = fs::temp_directory_path() / "btquant_test_layout_home";
fs::remove_all(fakeHome);  // clean prior runs
fs::create_directories(fakeHome / ".config/btquant_vulkan/profiles");
setenv("HOME", fakeHome.string().c_str(), 1);

btquant::ui::WindowManager wm;
// ... drive wm.applyLayoutSnapshot + saveLayoutAs + loadLayout ...

unsetenv("HOME");  // restore for downstream tests
```

Why this matters: WindowManager's save/load paths hardcode
`~/.config/btquant_vulkan/profiles/<name>.btqlayout` derived from
`$HOME`. Without redirecting HOME, the test would write to the
operator's real config dir. Worse: the operator could end up with
a stray `TestRoundtrip.btqlayout` file in their live profiles dir.

`remove_all` at the start handles cross-run pollution — even with
the redirect, a prior test might have left files in fakeHome.

`unsetenv("HOME")` at the end prevents leaking the fake value into
subsequent tests (e.g. Test 35 might read settings from HOME and
get confused by a missing dir). Restore is cheap.

Generalizes: any test that exercises code paths which read env vars
(usually HOME, USER, or XDG_CONFIG_HOME) should set up a tmp fake
+ redirect + unsetenv the trio. Same pattern works for unit tests
of any class with constructor-time config-dir resolution.

## Pitfalls captured

- **Don't `setOpen()` on widgets that don't expose it.** Phase 27's
  first attempt called `m_orderBookWidget->setOpen(showOrderBook)`
  etc. inside `applyLayoutSnapshot`. These widgets don't have a
  `setOpen()` method — they're controlled by the show* booleans via
  the `showXxxWindow()` render guard. Calling `setOpen()` on a
  class that doesn't have it fires "No member named 'setOpen' in
  'btquant::ui::OrderBookWidget'". Fix: just mutate the booleans
  and let the render path handle the rest.
- **`tradeWindowSeconds` is Settings-only** — WindowManager doesn't
  store it locally; only Settings does. The earlier `applyLayoutSnapshot`
  draft tried `wm.tradeWindowSeconds = s.tradeWindowSeconds`, which
  fails with "undeclared identifier". The correct pattern: don't
  try to keep a WindowManager copy. The next `Settings::save(state.ini)`
  cycle persists it via `markSettingsDirty()`.
- **`captureCurrentSettings()` already exists** — Phase 11's
  ProfileManager work added it. `saveLayoutAs` reuses it instead of
  re-reading from individual member fields. Don't reimplement the
  read-back from scratch.
- **`<imgui.h>` does not define `Selectable` until imgui 1.80+** —
  if the test build pulls in a much older imgui from a system
  package, `ImGui::Selectable` fires "no member". Verify the imgui
  version before relying on Selectable for the Load popup.

## Test 34: 6 invariants

1. `applyLayoutSnapshot` writes all 9 widget flags (1 spot-checked
   bool per flag — showOrderBook off, showOrderBookDepth on, etc.)
2. `saveLayoutAs` writes the file (`fs::exists` check)
3. `applyLayoutSnapshot(LayoutSnapshot{})` resets to defaults
   (showOrderBook=true, showRiskPanel=true)
4. `loadLayout` restores the saved flags
5. `LayoutIO::list()` picks up the new profile from the fake HOME
6. `loadLayout("Nonexistent")` returns false without crashing

The test pattern matches Phase 11's ProfileManager tests — same
fake-HOME redirect, same `unsetenv` cleanup, same public-bool
assertions.

## Sprint progression

Phase 27 = 1 commit, 3 files changed, 282 insertions. The full
sprint (Phases 21-27) shipped:
- 7 commits
- HotkeyMap (data) → HotkeyEditor (widget) → unified dispatch
  (refactor) → RiskConfig persistence (state.ini) → journal replay
  (PositionBook rehydration) → LayoutIO (file format) → WindowManager
  save/load menu (UI wiring)
- 7 tests (28-34), ~50 invariants total

The "Open / next" list as of Phase 27 end:
1. ~~LayoutIO data layer~~ (Phase 26, done)
2. ~~WindowManager save/load UI wiring~~ (Phase 27, done)
3. Dock layout text capture + restore — capture via
   `ImGui::SaveDockBuilderToText(window->DockNode)`, restore via
   `ImGui::DockBuilderLoadNodes(...)` after dockspace creation.
4. Auto-restore last layout on startup — pick a "default layout"
   name in Settings, apply it in `initialize()` after dockspace
   creation.
5. DOM heatmap widget (Open from Phase 1)
6. Candlestick bodies via raw draw-list (ImPlot lacks PlotCandlestick,
   Open from Phase 20)
7. Multi-symbol book (would require PositionBook redesign)

#27 is the natural next step. Ship end-to-end (capture text in
saveLayoutAs, restore in a new post-dockspace hook), commit, move
on.

## Lessons carried forward

- **Const-ref in declaration = full header, not forward-declare**.
  This is the inverse of Phase 11's "forward-declare MarketDataProcessor
  at global scope before opening the btquant::ui namespace". That
  pattern works for POINTER types in declarations. For VALUE
  types or CONST-REF types in declarations, the full include is
  mandatory. Internalize: read the declaration signature, count
  the asterisks.
- **Test paths via HOME redirect, not path injection**. Don't add
  a `savePath` constructor parameter to `WindowManager` for test
  purposes — that's leakage. Set `HOME` to a tmp dir before
  construction, unset after. Same pattern works for any class
  that derives config paths from `$HOME` or `$XDG_CONFIG_HOME`.
- **apply* is a single-pass field copy** — `applyLayoutSnapshot`
  is 30 lines of `wm.field = snap.field` for every layout-relevant
  field. Future `apply*Snapshot` functions (applyTheme, applyDock
  etc.) follow the same pattern: bulk copy, side-effect on
  Manager-owned state (RiskGuard in this case), mark dirty, mark
  reset for things that need rebuild. Don't try to factor a
  generic `apply(Settings)` that handles both theme AND risk AND
  widget visibility — the three flows have different side-effect
  targets (ThemeEditor::applySnapshot vs RiskGuard::setConfig vs
  show* bools vs dock reset). Three explicit functions beats one
  generic with conditionals.

## Test setup pattern for env-dependent config paths

```cpp
// 1. Choose a fresh tmp dir.
fs::path fakeHome = fs::temp_directory_path() / "btquant_test_X";
fs::remove_all(fakeHome);  // wipe prior runs
fs::create_directories(fakeHome / ".config/btquant_vulkan/profiles");

// 2. Redirect env.
setenv("HOME", fakeHome.string().c_str(), 1);

// 3. Construct the object — its ctor reads HOME-derived paths.
btquant::ui::WindowManager wm;

// 4. Drive the test.
wm.saveLayoutAs("Foo");
// ...

// 5. Restore env (CRITICAL — leaks affect downstream tests).
unsetenv("HOME");
```

Step 5 is what most ad-hoc tests forget. If you only `setenv` and
never unset, every subsequent test sees the fake HOME. Test 34
explicitly runs `unsetenv("HOME")` at the end as a documented
hygiene step.

## Architectural note: LayoutIO + WindowManager coupling

The data layer (LayoutIO) and the apply layer (applyLayoutSnapshot)
are now cleanly separated. The data layer's only obligation is to
load/save `LayoutSnapshot` objects — it knows nothing about
WindowManager or any specific UI. The apply layer knows how to
translate a snapshot into manager state changes. Tests can verify
the data layer independently of the apply layer (Test 33) and the
apply layer independently of the data layer (Test 34 with a
manually-constructed snapshot).

This separation is what made Test 34's `applyLayoutSnapshot(
::btquant::util::LayoutSnapshot{}); // all defaults` work — the
test bypasses LayoutIO entirely and constructs a default snapshot
in-place to reset WindowManager's state. The data layer's
sanitization, forward-compat, version-rejection logic is verified
in Test 33; the apply layer's field-copy correctness is verified
in Test 34. Two tests, two layers, zero coupling.

Future layout extensions (dock-text capture/restore, auto-restore
on startup) follow this pattern: extend LayoutSnapshot + LayoutIO
in the data layer, extend applyLayoutSnapshot (or add a new
applyDockSnapshot) in the apply layer, test each independently.