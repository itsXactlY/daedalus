# BTQuant Vulkan — Phase 8: Theme toggle + Hotkey Reference overlay

Session: 2026-06-19 (commit 9f09f689). Closes two of the six items
from `btquant-vulkan-phase7.md` § "Open / next" (light theme + hotkey
help overlay).

## What landed

1. **`UIContext::Theme` enum + `applyTheme()` runtime swap.**
   ```cpp
   enum class Theme { Dark = 0, Light = 1 };
   bool initialize(..., Theme theme = Theme::Dark);
   void applyTheme(Theme t);   // re-runs base palette + BTQuant overrides
   Theme theme() const;        // current value (for change-detection)
   ```
   The initialize path takes a theme argument so the first frame
   already has the user's chosen palette (no flash-of-dark-theme on
   Light users). After init, `applyTheme(t)` is callable at any time;
   it does:
   - `ImGui::StyleColorsDark()` OR `ImGui::StyleColorsLight()` to seed
     the palette from ImGui's stock palette
   - Layer BTQuant-specific colour overrides on top (WindowBg,
     Text, Button, FrameBg, TitleBg, MenuBarBg, Header states)

   Two palettes:
   - **Dark:** WindowBg `#08090a`, Text `#f7f8f8`, Button
     `#7132f5` (Kraken Purple), TitleBg `#14161a`, MenuBarBg
     `#101215`, Header purple at 40–80% alpha
   - **Light:** WindowBg `#f8f8fa`, Text `#14161a`, Button `#3268f5`
     (blue accents), TitleBg `#e8eaef`, MenuBarBg `#e8eaef`,
     Header blue at 30–70% alpha

   Style overrides include `WindowRounding=8`, `FrameRounding=4`,
   `GrabRounding=4`, `ScrollbarSize=12` — same rounding across both
   themes so layout doesn't shift on switch.

2. **Runtime theme change wired through `mainLoop`.** Pattern matches
   the heatmap-density watcher from Phase 7:
   ```cpp
   if (static_cast<long>(uiContext.theme()) != windowManager.theme) {
       uiContext.applyTheme(windowManager.theme == 0
                                ? UIContext::Theme::Dark
                                : UIContext::Theme::Light);
   }
   ```
   `WindowManager::theme` is the desired state (driven by the View →
   Theme submenu); `uiContext.theme()` is what's actually applied.
   The compare-and-swap runs every frame so menu toggles are
   immediate. Same `markSettingsDirty()` pattern as the visibility
   toggles → auto-save picks it up within ~1 s.

3. **`Settings::theme` field** — `long` (0/1) at the bottom of the
   Settings struct, defaults to 0 (Dark). Roundtripped through the
   `state.ini` config:
   - Numeric form: `theme=0` / `theme=1`
   - String form (more human-readable, written by `save()`): `theme=dark`
     / `theme=light`. Loader accepts both:
     ```cpp
     else if (key == "theme") {
         if      (val == "dark"  || val == "0") s.theme = 0;
         else if (val == "light" || val == "1") s.theme = 1;
         else if (isInt)                        s.theme = std::stol(val);
     }
     ```
   Save uses the string form for readability:
   `out << "theme=" << (theme == 0 ? "dark" : "light") << "\n";`

4. **Hotkey Reference overlay (`showHotkeyHelpWindow()`).**
   Rendered as a 14-row `ImGui::BeginTable("hotkeys", 2, RowBg)` with
   two columns (Key, Action). Toggled by:
   - Menu: `View → Hotkey Help…` (also adds `Help → Hotkey
     Reference`)
   - Hotkey: `?` (i.e. `Shift+/`, see Phase 6's edge-trigger
     pattern — `GLFW_KEY_SLASH` + `GLFW_KEY_LEFT_SHIFT` / `RIGHT_SHIFT`)

   The table is intentionally hand-rolled, not generated from the
   `kHotkeys[]` table in Phase 6, because:
   - `Ctrl+L` and `Shift+F1` are NOT in `kHotkeys[]` (they have
     different control-flow patterns — `requestDockLayoutReset()` vs
     a simple toggle)
   - `?` (this overlay's toggle) is itself in the table, which would
     be a chicken-and-egg if generated from the table

5. **`.gitignore` for the ImGui fallback `0` file.** Defensive
   measure even though the Phase 7 `create_directories` fix
   prevents the bug from happening — if a future regression
   reintroduces the issue, the orphan `0` file won't pollute git:
   ```
   /0
   /btquant_vulkan/0
   /btquant_vulkan/src/0
   /btquant_vulkan/build/0
   ```

## Pitfalls (Phase 8 specific)

- **Stable references for `MenuItem(selected=bool*)` radio buttons.**
  Theme radios need a stable bool pointer that doesn't change address
  — passing `&theme` directly gives you `theme == 0 ? &kBoolTrue :
  &kBoolFalse` pattern (where `kBoolTrue/kBoolFalse` are file-local
  `static` or anonymous-namespace globals that NEVER change). If you
  pass `&some_local_bool`, the menu's "selected" state is dangling
  the moment the local goes out of scope.

- **Don't rename `ImGui_ImplVulkan_RenderDrawData` to
  `ImGui_ImplVulkan_RenderDrawdata`.** Capitalisation matters — the
  post-2025-09-26 docking branch API uses camelCase with capital D.
  A diff with the lowercase form compiles on some TUs and breaks
  the link step on others (the symbol is only referenced from one
  call site, so the error surfaces late).

- **Load settings BEFORE `uiContext::initialize`** so the persisted
  theme is applied on the very first frame. If you initialize the
  UI context with the default (Dark) and then mutate from settings
  on the second frame, Light-theme users see a one-frame flash of
  dark. Order in `main.cpp::initUI`:
  1. `create_directories(settingsPath.parent_path())` (Phase 7 fix)
  2. `auto settings = Settings::load(settingsPath);`
  3. `uiContext.initialize(..., settings.theme == 0 ? Dark : Light)`
  4. Push `settings.show*` booleans + `settings.fpsLimit` etc.
     into WindowManager

- **The hotkey help table is NOT generated from `kHotkeys[]`.** If
  you keep `kHotkeys[]` (the F2–F12 table from Phase 6) and ALSO
  have a help table, treat them as independent. Trying to unify
  them causes: (a) the `?` key (which is OUTSIDE the F-key range)
  can't be in `kHotkeys[]` because that table is F-key-only, and
  (b) `Ctrl+L` and `Shift+F1` have entirely different control
  paths (reset layout vs simple toggle) so the
  `kHotkeys[i].glfwKey + bool* member pointer` pattern doesn't
  express them. Keep both, hand-roll the help table.

## Reusable patterns (Phase 8)

- **`enum class` settings with a `theme()` accessor on the owner
  + desired-state field on the controller.** Pattern: the component
  that OWNS the resource (here `UIContext`) exposes the actual
  current state via a getter. The component that the user
  manipulates (here `WindowManager`) holds the DESIRED state. A
  render-loop compare-and-swap applies the change. Same shape as
  the heatmap-density watcher in Phase 7. Extends cleanly to any
  future "user picks a thing in the menu → apply at runtime"
  setting without refactoring the persistence layer.

- **String-form enum values in hand-rolled key=value configs.**
  `theme=dark` is friendlier in `cat ~/.config/<app>/state.ini`
  than `theme=0` for debugging. Loader accepts both forms (string
  + numeric) so older configs keep working. Trade-off: one extra
  branch in the parser, no extra cost on save (just one ternary).

## Verification recipe (Phase 8 add-on)

```bash
cmake --build build -j$(nproc) | tail -3
./build/test/test_integration 2>&1 | grep -E "Test|✓|✗" | tail -15
# expect: Test 6 now has 3 sub-checks
#   ✓ Roundtrip preserved all 15 fields (incl. theme=light)
#   ✓ theme="light" string form parses to 1
#   ✓ theme="dark"  string form parses to 0
# expect: Test 7, Test 8 still ✓
timeout 6 ./build/btquant_vulkan 2>&1 | tail -3
# expect: "loaded settings from /home/alca/.config/btquant_vulkan/state.ini"
# expect: exit 124 (timeout-killed, no crash)
# expect: NO "0" file in CWD after exit (Phase 7 fix still holds)
```

Manual UI smoke (requires visible window, not the headless mode this
binary defaults to):
1. Toggle `View → Theme → Light (off-white)` → window repaints to
   white-with-blue
2. Toggle back to `Dark (Kraken Purple)` → repaints to dark
3. Press `?` → hotkey help overlay appears with the 14-row table
4. Press `?` again → overlay closes
5. Exit → `state.ini` has `theme=light` (or `theme=dark`)

## Open / next

- **Symbol picker** — currently hardcoded
  `/dev/shm/btquant_hotspine`. Need a widget that lists active
  symbols from the producer and switches the data source. Adds a
  `MarketDataProcessor::subscribe(symbol_id)` path.
- **60+ panel port from BTQ_Render_Engine** — Watchlist, Chart,
  Strategy, Backtest, P&L attribution. The Phase 4 6-file
  mechanical recipe still applies.
- **Profile switching** — save/load named window layouts (the
  imgui.ini file already supports a `[Window][name]` section per
  window). Could expose as a Profile menu.
- **Live demo producer in-binary** — currently depends on an
  external `scripts/mock_producer.py`. Embedding the GBM price
  stream into the binary removes a moving piece from the user's
  workflow.
- **Per-minute candle-aggregator test for boundary cases** — the
  current Test 5 covers in-progress folding and boundary
  finalization. Edge cases worth covering: empty tick (timestamp
  zero), out-of-order ticks, very late ticks after `max_candles`
  fills up.
