# BTQuant Vulkan — Phase 7: Live heatmap resize + auto-save + ini path bug

Session: 2026-06-19 (commit e35b76d2). Closes the last three items
from `btquant-vulkan-phase6.md` § "Open / next".

## What landed

1. **`HeatmapCompute::setSize(uint32_t newSize)`** — live resize of
   the GPU output image. Algorithm:
   - Early-out if `newSize == m_cfg.image_width` (no VK calls)
   - If uninitialized: store the size into `m_cfg` and return —
     `initialize()` picks it up on next call
   - Else: call `destroySizeDependentResources()` to free image +
     view + memory + sampler + ImGui texture registration + the
     descriptor set (it references the soon-destroyed view), update
     `m_cfg`, then rebuild: `createOutputImage()` + `AddTexture` +
     `buildDescriptorSet()`. Returns an error string if any step
     fails; size is left in `m_cfg` so a retry can succeed.

   Refactor: extracted `destroySizeDependentResources()` from
   `shutdown()` so both code paths share the cleanup. `shutdown()`
   now calls it before tearing down size-INDEPENDENT resources
   (pipeline, descriptor pool, descriptor set layout, config buffer,
   input SSBO).

2. **`HeatmapConfig` plumbed through `main.cpp`** — `initCompute()`
   builds a `HeatmapConfig` from `windowManager.heatmapDensity` (long
   → uint32_t with `static_cast`) and passes it to
   `HeatmapCompute::initialize(device, physDev, pool, queue, family, cfg)`.
   The startup size therefore honors the persisted slider value, so
   closing the app at 256 and reopening it comes back at 256.

3. **`mainLoop` heatmap-density watcher** — every frame, if
   `windowManager.heatmapDensity != windowManager.lastAppliedHeatmapDensity`,
   clamp to `[64, 512]`, call `heatmapCompute.setSize(target)`, and
   store `lastAppliedHeatmapDensity = target`. Cheap no-op when
   unchanged (`setSize` returns immediately on equal sizes).

4. **`settingsDirty` + per-toggle auto-save** — replaces
   "save-on-shutdown only" from Phase 5:
   - `WindowManager::settingsDirty() / markSettingsDirty() /
     clearSettingsDirty()` — file-private `m_settingsDirty` bool.
   - Every `MenuItem`, `SliderScalar`, F-key hotkey, Ctrl+L, and
     the "Reset Layout" / "Close" buttons in the Settings window
     call `markSettingsDirty()` on activation.
   - `mainLoop` checks `(windowManager.settingsDirty() &&
     frameCounter % 60) == 0` and writes `state.ini` via the same
     `Settings::save()` atomic-write path. Debounced to ~1 s at 60 fps
     so holding a key doesn't spam disk.

5. **`Test 8: settingsDirty flag toggles correctly`** — three asserts:
   fresh `WindowManager` is clean, `markSettingsDirty()` flips,
   `clearSettingsDirty()` resets.

6. **`test_integration` cascade fix** — adding `window_manager.cpp`
   to the test target brought transitive dependencies on every
   widget `.cpp` + `market_data_processor.cpp` + implot
   (`implot.cpp`, `implot_items.cpp`). All linked via
   `target_sources(test_integration PRIVATE ...)`.

## Pitfalls (Phase 7 specific)

- **ImGui silent ini-write fallback to a file literally named "0" in
  CWD when the target directory does not exist.** Symptom: a small
  file `0` appears in the working directory after the app exits; it
  contains real ImGui ini content (Window/DockSpace sections).
  Root cause: `io.IniFilename = "/home/alca/.config/btquant_vulkan/
  imgui.ini"` is set, but the parent dir doesn't exist yet.
  `ImGui::SaveIniSettingsToDisk` calls `ImFileOpen(ini_filename, "wt")`
  which fails silently (returns null) — but ImGui's INTERNAL
  save-on-platform-event path falls back to a default name "0" in
  CWD when the configured path write fails. Result: two files
  written, one valid one orphan.
  **Fix:** `std::filesystem::create_directories(settingsPath.
  parent_path())` in `mainLoop::initUI` BEFORE
  `(parent_path / "imgui.ini").string()`. After the fix the `0`
  file is gone and `~/.config/btquant_vulkan/imgui.ini` is written
  correctly. Same fix applies to ANY first-run user that has no
  `~/.config/<app>/` yet — ImGui's silent fallback is a real gotcha.

- **Vulkan live-resize requires `vkFreeDescriptorSets` + recreation,
  not just image/view destroy.** The existing `m_descriptorSet`
  holds a `VkDescriptorSetLayoutBinding` pointing at the destroyed
  `m_outputView`; after `vkDestroyImageView` the set is a dangling
  reference. The destroySizeDependentResources helper calls
  `vkFreeDescriptorSets(device, pool, 1, &m_descriptorSet)` BEFORE
  tearing down the view so the freed set's memory is returned to
  the pool (a fresh set is allocated in `buildDescriptorSet()`).
  Forgetting this yields a validation-layer error on the next
  `vkCmdBindDescriptorSets` and (in Release) undefined behavior
  when the GPU actually tries to sample from the freed view.

- **`setSize()` must be tolerant of pre-init calls.** `main.cpp`
  used to call `windowManager.heatmapDensity` to seed
  `HeatmapConfig` BEFORE `HeatmapCompute::initialize()` ran. The
  first call to `setSize()` therefore sees `m_device == VK_NULL_HANDLE`.
  The implementation handles this with an early-return that just
  stores the size into `m_cfg`; `initialize()` then reads it from
  `cfg` and builds at the right size. Without this guard, the
  startup size would always be the default 256×256 and the slider
  would have no effect on first boot.

- **`Settings::save` is called from BOTH `mainLoop` (auto-save every
  60 frames when dirty) AND `cleanup()` (final save on shutdown).**
  When both fire on the same process, the second `save()` overwrites
  the first. This is intentional — the final save wins and reflects
  the last in-memory state. But if you add a signal handler or
  watchdog, do NOT add a third `save()` path; the atomic
  write-tmp-then-rename guarantees that at most one save is in
  flight, but interleaved writes can drop the last user edit.

- **The `<<` strips-`.0`-from-doubles bug** (Phase 5 pitfall #1) has
  a sibling: **`std::to_string(double)` also strips trailing zeros**
  AND locale-dependently formats the decimal separator (`,` on
  European locales). Always use `std::fixed << std::setprecision(N)`
  for any hand-rolled config writer that emits floats.

## Reusable patterns (Phase 7)

- **Vulkan resource split by lifetime dependency.** A clean resize
  pattern: identify which Vulkan objects depend on the size (image,
  view, sampler, memory, descriptor set that binds the view, ImGui
  texture registration), group them into a `destroySizeDependent
  Resources()` helper, refactor `shutdown()` to call it. Now both
  `setSize(N)` and `shutdown()` share the exact same teardown code.
  Add new size-dependent resources by touching one helper, not two
  call sites.

- **Edge-triggered "I changed" signal via dirty flag + periodic
  flush.** Pattern: caller mutates state → `markDirty()`. Render
  loop checks dirty + frame counter modulo N (debounce) → writes
  config. Cleanest when paired with an atomic-write + tmp-rename
  file backend. Settings file is never written on the hot path of
  every frame, so the I/O cost is bounded at one write per N frames.

- **`create_directories(parent)` BEFORE composing child path.** Any
  code path that derives a child path from a `defaultPath()` helper
  that returns `~/.config/<app>/foo.ext` MUST call
  `create_directories(parent_path())` first. Otherwise the very
  first launch leaves no config dir, the file write fails
  silently, and (in ImGui's case) a `0` file appears in CWD.

## Verification recipe (Phase 7 add-on)

```bash
cmake --build build -j$(nproc) | tail -3
# expect: [100%] Built target btquant_vulkan + test_integration
./build/test/test_integration 2>&1 | grep -E "Test|✓|✗" | tail -12
# expect: Tests 1..8 all ✓ (Test 8 = settingsDirty flag toggles)
timeout 6 ./build/btquant_vulkan 2>&1 | tail -3
# expect: "loaded settings from /home/alca/.config/btquant_vulkan/state.ini"
# expect: exit 124 (timeout-killed, no crash)
ls -la ~/.config/btquant_vulkan/
# expect: state.ini + imgui.ini both present (after at least one
# frame that triggers a write — opening a MenuItem or pressing a
# hotkey is enough)
ls 0
# expect: No such file (the "0 file in CWD" bug is fixed by
# create_directories before ini path is resolved)
```

To exercise the auto-save without manual interaction: edit the
Settings slider for FPS limit → save fires within ~1 s. Or press
any F-key hotkey from another shell with `xdotool key F2` if you
have a display attached.

## Workflow note

This phase was shipped under explicit "weiter, nicht fragen"
directive. The session pattern was: agent presents a numbered list
of "Open next steps" → user replies "weiter" → agent picks the
highest-value item, executes, commits, reports. Three iterations of
this in one session produced phases 5 → 6 → 7. The numbered menu
at the end of each phase is itself the authorization for the next
phase. If you find yourself writing "Soll ich X oder Y machen?" at
the end of a turn on a "weiter" task, stop and pick — the user
already authorized the whole list.

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

(Light theme + Hotkey help overlay moved to `btquant-vulkan-phase8.md`.)
