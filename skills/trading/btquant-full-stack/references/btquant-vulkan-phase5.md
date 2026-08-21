# BTQuant Vulkan — Phase 5: Docking + Settings + Persistence

Session: 2026-06-19 (commit 6d3e9a02). Adds the workspace-management layer
on top of the 10 widgets from Phase 4.

## What landed

1. **`src/util/settings.{hpp,cpp}`** — hand-rolled key=value persistence to
   `~/.config/btquant_vulkan/state.ini` (overridable via `BTQUANT_CONFIG`).
   Atomic write (`*.tmp` + `rename`). 12 fields: 9 widget-visibility bools +
   `fpsLimit` (long) + `heatmapDensity` (long) + `tradeWindowSeconds`
   (double). No external JSON dep — for a flat bool/int/double config,
   hand-rolled beats pulling nlohmann_json.

2. **`WindowManager::buildDockLayout()`** — uses `ImGui::DockBuilder*` (in
   `imgui_internal.h`) to lay out a default 5-region tree on the first
   frame after `DockSpaceOverViewport` registers the dockspace:

   ```
   LEFT 22%  →  OrderBook (55% top) + OrderBookDepth (45% bot)
   RIGHT 28% →  MultiVWAP (40% top) + VPVR (30% mid) + Footprint (30% bot)
   CENTER     →  Trades (20% top) + DOM (52% mid) + RiskPanel|TPO (14% bot, split 50/50)
   ```

   Heatmap docks to root as a floating overlay (currently rendered
   separately in `mainLoop` via `heatmapWidget.render()`).

3. **`applyInitialDockLayoutIfNeeded()`** — idempotent one-shot gate with
   `m_layoutApplied` flag. **`requestDockLayoutReset()`** — sets
   `m_layoutResetRequested` flag; next frame, layout is rebuilt from
   scratch (used by "View → Reset Layout").

4. **View menu expanded from 4 → 9 widget toggles + Settings + Reset
   Layout**. Settings window exposes `fpsLimit` (0=uncapped → swap
   interval 0), `heatmapDensity` (64–512), the 9 widget toggles, Reset
   Layout button, Close.

5. **`main.cpp`** wires it up:
   - `initUI()` reads settings BEFORE `windowManager.initialize()`, then
     pushes values into `windowManager.showXxx` + `fpsLimit` +
     `heatmapDensity`, then sets `glfwSwapInterval(fpsLimit > 0 ? 1 : 0)`.
   - `mainLoop()` calls `applyInitialDockLayoutIfNeeded()` immediately
     after `DockSpaceOverViewport()` and `showSettingsWindow()` after
     the widget calls.
   - `cleanup()` builds a `Settings` from current state, calls `save()`,
     then tears down Vulkan.

## Pitfalls (Phase 5 specific)

- **`operator<<` strips `.0` from whole doubles**, breaking key=value
  roundtrip. `out << 30.0` writes `"30"`, not `"30.0"`, so the parser's
  type-inference heuristic (looks for `.`) classifies it as int and the
  field round-trips wrong. Fix: `out << std::fixed << std::setprecision(6)
  << tradeWindowSeconds`. (This is generic C++ — apply to any hand-rolled
  config writer.)
- **`DockBuilder*` API is in `imgui_internal.h`**, not `imgui.h`. The
  `docking` branch of imgui makes it accessible but doesn't promote it
  to the public header. Add `#include <imgui_internal.h>` in
  `window_manager.cpp`.
- **Apply initial dock layout one frame AFTER `DockSpaceOverViewport()`
  returns**, otherwise `DockBuilderGetNode(dockspaceId)` returns nullptr
  (the dockspace ID isn't registered yet). The current implementation
  early-outs when the node is null and re-tries next frame.
- **Anonymous `namespace { ... }` blocks must appear at the TOP of the
  translation unit if their constants are used by code above the block**.
  LSP (clangd) fires `undeclared_var_use` errors at parse time even
  though the C++ compiler accepts forward-references to namespace
  members. Move the namespace block above its first use, or pull the
  constants out into file-static `const` declarations.
- **Stale function definitions trip "keine Deklaration passt zu X"** when
  you remove the declaration from the header but leave the body in the
  `.cpp`. The C++ error is misleading (German: "no declaration matches")
  but the fix is mechanical: delete the orphan body. Always grep the
  `.cpp` for definitions of symbols you remove from the `.hpp`.
- **`exit=$?` after `cmd 2>&1 | tail` returns the LAST command's exit
  code (tail = 0), not the producer's**. For verification use
  `echo "exit=${PIPESTATUS[0]}"` instead. `[ $? -eq 124 ]` will report
  success when the binary actually timed out.
- **`namespace fs = std::filesystem;`** inside a block scope sometimes
  trips LSP `Expected namespace name` errors (clangd parsing quirk on
  C++17 inline namespace alias). The compiler accepts it; ignore the
  LSP diagnostic.

## Reusable patterns

- **Atomic config write**: open `path.tmp`, write, close, `fs::rename`.
  Best-effort crash safety without `fsync`. Pair with a header
  `static path defaultPath()` that respects `$MYAPP_CONFIG` env var.

- **Type-inferring key=value parser**: classify each value as
  bool=("0"|"1"|"true"|"false"), int=(all digits + optional leading `-`),
  double=(everything else). Update the classifier in one place when a
  new type appears.

- **Dock layout reset path**: `requestDockLayoutReset()` sets a flag,
  `applyInitialDockLayoutIfNeeded()` consumes it on next frame by
  resetting `m_layoutApplied = false` and rebuilding. Keeps the
  DockBuilder call out of the click handler (which would race with the
  current frame's ImGui draw list).

- **Settings state ownership**: `WindowManager` owns the live mutable
  state (visibility flags, slider values). `main.cpp` reads/writes the
  file. This avoids a "Settings as a separate singleton" class with
  cross-cutting getters; everything stays in the widget tree where the
  user expects it.

## Verification recipe (Phase 5 add-on)

```bash
cmake --build build -j$(nproc) | tail -5
# expect: [100%] Built target btquant_vulkan
./build/test/test_integration 2>&1 | grep -E "Test|✓|✗"
# expect: Test 1..6 all ✓ (Test 6 = settings roundtrip)
timeout 5 ./build/btquant_vulkan 2>&1 | tail -5
# expect: "[BTQuant] loaded settings from /home/alca/.config/btquant_vulkan/state.ini"
# expect: exit 124 (timeout-killed, no crash)
ls -la ~/.config/btquant_vulkan/state.ini
# expect: file written on graceful shutdown (Ctrl+C). SIGKILL/SIGTERM
# without graceful handler won't write — that's expected.
```

## Open / next

- `imgui.ini` load+save is NOT yet wired (window positions don't persist
  across runs — only visibility flags do). ImGui provides
  `ImGui::LoadIniSettingsFromDisk` / `SaveIniSettingsToDisk` for this.
- `heatmapDensity` slider is read at startup but not applied to the
  live `HeatmapWidget` — needs a `resize()` call when the value changes.
- `showSettings` itself isn't persisted (Settings window always starts
  hidden).
- Settings save fires only on graceful shutdown. Per-toggle save would
  need a debounced timer or save-on-every-change (file I/O per click is
  cheap, but not free).
- Hotkeys: F2..F9 for widget toggles, Ctrl+L for reset layout.
- Live stats overlay: bottom-right FPS / frame time / data queue depth.
