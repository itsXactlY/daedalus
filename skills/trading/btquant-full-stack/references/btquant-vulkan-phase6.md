# BTQuant Vulkan — Phase 6: Workspace Polish (stats, hotkeys, imgui.ini)

Session: 2026-06-19 (commit 952ebd72). Sits on top of Phase 5 (dock
layout + Settings + state.ini). Closes the "Open / next" list at the
bottom of `btquant-vulkan-phase5.md`.

## What landed

1. **`src/ui/stats_overlay.{hpp,cpp}`** — top-right corner overlay:
   FPS, frame-time EWMA (α=0.10), min/max, trade queue depth, candle
   count. No-input flags
   (`NoTitleBar|NoResize|NoMove|NoScrollbar|NoSavedSettings|NoInputs|
   NoFocusOnAppearing`) + `SetNextWindowBgAlpha(0.65f)`. Lifecycle:
   `tick()` once per frame BEFORE render (records one EWMA sample);
   `render()` once per frame AFTER widgets (with live counters pushed
   in from `MarketDataProcessor::snapshot(0, 0).size()`).

2. **`UIContext::initialize(..., const char* iniFilename)`** — takes
   the path to `imgui.ini`. On shutdown, `ImGui::SaveIniSettingsToDisk`
   flushes window positions + custom dock layout. Path lives next to
   `state.ini` at `~/.config/btquant_vulkan/imgui.ini`, overridable
   via `BTQUANT_INI` env. Now window state survives restarts — Phase 5
   only persisted visibility flags, not positions.

3. **`WindowManager::processHotkeys(GLFWwindow*)`** — edge-triggered
   via `static bool prevPressed[kNumHotkeys]` (function-local statics
   survive across frames; rising edge fires once per key press so
   holding a key doesn't rapid-fire toggle). Suppressed when
   `io.WantCaptureKeyboard && io.WantTextInput` so text-field input
   still works. Bindings (file-static table `kHotkeys[]`):

   | Key      | Action                          |
   |----------|---------------------------------|
   | F2       | toggle OrderBook                |
   | F3       | toggle OrderBookDepth           |
   | F4       | toggle DOM                      |
   | F5       | toggle Trades                   |
   | F6       | toggle TPO                      |
   | F7       | toggle Footprint                |
   | F8       | toggle VPVR                     |
   | F10      | toggle MultiVWAP                |
   | F11      | toggle RiskPanel                |
   | F12      | toggle Settings window          |
   | Shift+F1 | toggle StatsOverlay             |
   | Ctrl+L   | reset dock layout               |

   F9 skipped (collides with ImGui's default "show demo window").
   Member pointers (`&WindowManager::showOrderBook`) require the
   `kHotkeys[]` table to be inside `namespace btquant::ui`, NOT in a
   global `namespace { ... }` block — see pitfalls below.

4. **`Settings` extended** with `showSettings` + `showStatsOverlay`
   (now 14 fields roundtrip). `WindowManager` mirrors both bools;
   `main.cpp` saves them in `cleanup()`.

5. **`test_integration` extended with Test 7**: StatsOverlay EWMA
   convergence — 60 × 16 ms sleeps → avg ≈ 16 ms, fps ≈ 60. Tests
   `m_ewmaMs == 0` after first tick (seed), range checks the EWMA,
   and `setEnabled(false)` propagates to `enabled()`.

## Pitfalls (Phase 6 specific)

- **`test_integration` doesn't link imgui by default.** Sources like
  `stats_overlay.cpp` that call `ImGui::Begin/End/Text` need the imgui
  translation units in the test target. Add to `test/CMakeLists.txt`:
  ```
  target_sources(test_integration PRIVATE
      ${_parent_imgui_src}/imgui.cpp
      ${_parent_imgui_src}/imgui_draw.cpp
      ${_parent_imgui_src}/imgui_tables.cpp
      ${_parent_imgui_src}/imgui_widgets.cpp)
  ```
  Without this you get a linker error for every ImGui symbol called.
  Doesn't affect the main `btquant_vulkan` target — that one already
  pulls imgui sources via the FetchContent block in the root
  `CMakeLists.txt`.

- **Member pointers to a namespaced class must live INSIDE that
  namespace, not in a global `namespace { ... }` block.** A table
  like `static HotkeyBinding kHotkeys[] = { { GLFW_KEY_F2,
  &WindowManager::showOrderBook, ... } };` declared at file scope
  fails unqualified lookup because `WindowManager` is
  `btquant::ui::WindowManager`, not in the global namespace. Two
  fixes that work:
  1. Move the block into `namespace btquant::ui { ... }` (the
     choice in this codebase).
  2. Qualify every entry: `&btquant::ui::WindowManager::showOrderBook`.
  The compiler accepts this because the namespace is open above the
  block. LSP (clangd) occasionally still fires warnings — they are
  false positives; the build is green.

- **`std::filesystem` roundtrip in tests**: `namespace fs =
  std::filesystem;` inside a brace-block trips some clangd versions
  with `Expected namespace name`. The compiler accepts it; ignore the
  LSP diagnostic, the build is green.

- **`MarketSnapshot` field name**: `recent_candles` (plural, not
  `candles`). The other fields are `order_book`, `metrics`,
  `recent_trades`, `current_candle`, `snapshot_seq`. Snapshot call:
  `snapshot(last_n_trades, last_n_candles)` — two positional args,
  NOT `snapshot(N)`.

## Reusable patterns (Phase 6)

- **Edge-triggered input via prev/curr key state**: keep
  `static bool prev[N]` inside the input-handling function, sample
  `curr[i] = glfwGetKey(...) == GLFW_PRESS`, fire on
  `curr[i] && !prev[i]`, then `prev[i] = curr[i]`. Works for any
  one-shot-on-keypress binding without installing a GLFW key callback.
  Pattern works in any framework that exposes "is key down" without
  edge events (SDL_KEYDOWN without a callback, raw X11 KeyPress
  polling, etc.).

- **EWMA FPS overlay**: 60-frame exponential moving average is enough
  to smooth jitter while still reacting to drops within a second.
  α=0.10 is a good default; α=0.05 for very smooth but slow-reacting,
  α=0.20 for fast reaction but visible jitter. Track min/max in
  parallel for "did we ever stall" diagnostic.

- **Persisting UI visibility**: every widget-window toggle AND
  per-element overlay toggle belongs in `Settings`. Users expect
  "I closed this, why is it back?" never to happen. The pattern is
  `bool showFoo` in `WindowManager` + same-named field in `Settings`
  + read/write in `initUI`/`cleanup`. Add both at the same time —
  the asymmetry is a common source of "I keep losing my Settings
  window state" complaints.

- **ImGui ini path beside state.ini**: `defaultPath().parent_path() /
  "imgui.ini"` keeps the config dir tidy. ImGui writes
  automatically on platform events; explicit `SaveIniSettingsToDisk`
  in `shutdown()` is the only reliable way to flush on plain process
  exit (no SIGTERM handler).

## Verification recipe (Phase 6 add-on)

```bash
cmake --build build -j$(nproc) | tail -5
# expect: [100%] Built target btquant_vulkan + test_integration
./build/test/test_integration 2>&1 | grep -E "Test|✓|✗" | tail -10
# expect: Tests 1..7 all ✓ (Test 7 = stats overlay EWMA convergence)
timeout 5 ./build/btquant_vulkan 2>&1 | tail -3
# expect: "[BTQuant] loaded settings from .../state.ini"
# expect: exit 124 (timeout-killed, no crash)
```

After a graceful shutdown (Ctrl+C) verify both files are written:
```bash
ls -la ~/.config/btquant_vulkan/{state.ini,imgui.ini}
# expect: both files present, sizes > 0
```

## Open / next

- `heatmapDensity` slider value is still read at startup but not
  pushed to the live `HeatmapWidget`. Needs `resize()` call on
  change — would close Phase 5 open item #2.
- Per-toggle save (write `state.ini` on every MenuItem click) — file
  I/O cost is negligible but the asymmetry (visibility flags persist
  per-frame while other state only persists on shutdown) is a
  confusing mental model.
- Light theme toggle (Kraken Purple is the default; a daylight-mode
  theme would round out the polish).
- Symbol picker — currently hardcoded `/dev/shm/btquant_hotspine`.
- Sound alerts on price/volume spikes (proportional to spike
  magnitude).
- Per-symbol widget instance — currently each widget reads the
  shared market data; multi-symbol would need a
  `m_activeSymbolId` + per-symbol snapshot cache.

## Time budget

Phase 6 commit was ~330 lines across 12 files (3 new) in roughly
the same wall-clock time as Phase 5. The pattern is converging:
read state from `Settings` → render widgets → take input via
edge-triggered hotkeys → tick stats overlay → render overlay →
commit + smoke test. Future phases that fit this rhythm can be
shipped in one shot.
