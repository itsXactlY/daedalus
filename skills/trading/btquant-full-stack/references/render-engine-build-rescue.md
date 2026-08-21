# BTQ_Render_Engine Build-Rescue Recipes

Session: 2026-06-17 (TASK_ULTIMA_MMT_GENESIS_WIRED.md build green from cold).

Captures the specific fixes that took a 2026-04-14-stale binary to a fresh
build + commit on branch 0.0.2. Most are reusable on any future build
breakage in this engine.

## Dual TradeData Pattern (CRITICAL — read first)

There are TWO coexisting TradeData structs in BTQ_Render_Engine. They are
NOT interchangeable.

| Struct | Location | Field access | Used by |
|---|---|---|---|
| `BTQuant::Data::TradeData` | `include/data/TradeData.h` | `trade.ts.timestamp_us`, `trade.symbol_id`, `trade.side`, `trade.flags`, `trade.volume` | hot path / SPSC / MarketDataProcessor / quality_monitor |
| `BTQuant::RenderEngine::TradeData` | `include/market_data_processor.hpp:54` | `trade.timestamp` (uint64 directly), `trade.size`, `trade.is_buy`, `trade.symbol` (std::string) | analytics / panel renderers / cluster_engine / most components |

Both have a `timestamp` field, but the field name in Data::TradeData is
inside a `TimestampAlias ts` union, so `trade.timestamp` does NOT compile —
must be `trade.ts.timestamp_us` or `trade.ts.timestamp`.

`Data::TradeData` is a 64-byte aligned POD with static_asserts. The union
provides backward-compat aliasing:
```cpp
union TimestampAlias {
  uint64_t timestamp_us;  // canonical
  uint64_t timestamp;     // deprecated alias — same storage
};
```

### Refactor rules

When migrating code from old `trade.timestamp` (RenderEngine struct) to
spec `trade.ts.timestamp_us` (Data struct):
1. Verify the file's `namespace` block — `namespace BTQuant::Data {`
   means it uses `Data::TradeData`.
2. Don't blanket-sed across the tree — only files in `src/data/` use
   Data::TradeData; everything else uses RenderEngine::TradeData.
3. Function parameters and local variables named `timestamp` are
   uint64_t scalars. They will be accidentally caught by a `trade\.timestamp`
   sed if the pattern is too greedy. Use `trade\.timestamp` (with the dot)
   to scope it.

## Build Blocker Fixes (in order applied)

### 1. Missing `<iomanip>` include

`include/error_handling/error_reporter.hpp` uses `std::put_time`,
`std::setfill`, `std::setw` without including `<iomanip>`. Six errors,
single root cause.

```cpp
#include <chrono>
#include <thread>
#include <iomanip>   // <-- add
```

### 2. SPIR-V embedded array

`include/shader_spirv.hpp` had `VERTEX_SHADER_SPIRV` and
`FRAGMENT_SHADER_SPIRV` but not `LOB_HEATMAP_COMPUTE_SPIRV` that
`src/vulkan/lob_heatmap_compute_pipeline.cpp:35` references.

The `.spv` file already exists at
`shaders/spirv/lob_heatmap.comp` (1744 uint32_t words = 6976 bytes).
Generate the C array via Python struct unpack:
```python
import struct
with open("shaders/spirv/lob_heatmap.spv", "rb") as f: data = f.read()
n = len(data) // 4
words = struct.unpack(f"{n}I", data[:n*4])
# format as static const uint32_t LOB_HEATMAP_COMPUTE_SPIRV[] = { ... };
```

After any change to `lob_heatmap.comp`, regenerate with
`glslc -fshader-stage=comp shaders/lob_heatmap.comp -o shaders/spirv/lob_heatmap.spv`
and re-embed.

### 3. CMakeLists.txt orphan detection

```bash
find src -name '*.cpp' | sort > /tmp/all_cpp.txt
grep -E '^\s*src/' CMakeLists.txt | sed 's/^[[:space:]]*//' | sort -u > /tmp/in_cmake.txt
comm -23 /tmp/all_cpp.txt /tmp/in_cmake.txt
```

15+ .cpp files were missing from CMakeLists. After adding, 5 more files
turned out to be orphans (compile errors, no consumer):
- `src/components/realtime_dashboard_component.cpp` — `__access::_Data` error
- `src/memory/memory_pool.cpp` — `FastTradePaceDataPool::pool_` is `int`
- `src/components/tabbed_panel.cpp` — override errors
- `src/performance_monitor.cpp` — duplicate symbol with `src/monitoring/performance_monitor.cpp`
- the orphan `IndicatorValuePairPool` block in `src/memory/memory_pool.cpp`

Fix: comment out with explanation, do NOT delete the file (the header is
still useful for future code).

### 4. CachedTexture type missing

`include/vulkan/lob_heatmap_compute_pipeline.hpp` uses `CachedTexture`
but the type wasn't defined anywhere. Add to
`include/vulkan_base_types.hpp` (after the standard includes):
```cpp
struct CachedTexture {
    VkImageView     image_view     = VK_NULL_HANDLE;
    VkSampler       sampler        = VK_NULL_HANDLE;
    VkImageLayout   layout         = VK_IMAGE_LAYOUT_UNDEFINED;
    VkDescriptorSet descriptor_set = VK_NULL_HANDLE;
    void*           im_texture_id  = nullptr;
};
```

The full Phase 1 wiring (GPUMemoryManager::add_texture() wrapping
`ImGui_ImplVulkan_AddTexture`) is still TODO. The stub unblocks the
build.

### 5. TelemetryCollector needs libuuid

`telemetry_collector.cpp` calls `uuid_generate` and `uuid_unparse`. libuuid
is not available in this build environment. Stub the .cpp with no-op
implementations that satisfy the header — keeps the Phase 7.4 TSC
telemetry interface (`recordPerformanceMetric`) intact without
requiring the system library.

## Backward-Compat Conventions Established

- **Crosshair globals**: declared in `include/sync/global_state.hpp`
  (`g_crosshair_price`, `g_crosshair_symbol_id`). Helpers in
  `include/sync/crosshair_helper.hpp` (write/read/render_dashed_hline).
  No consumer panel calls these yet — future Phase 7.1 work.

- **FramePacer**: declared `pace(uint64_t budget_us=6944)` +
  `mark_frame_start()` + `g_frame_pacer()` singleton accessor in
  `include/rendering/frame_pacer.hpp`. Existing
  `begin_frame()`/`end_frame()`/`wait_for_next_frame()` API kept intact.

- **MemoryArena**: implementation at `src/memory/memory_arena.cpp`.
  Constructor `mmap`s 1GB with `MAP_PRIVATE | MAP_ANONYMOUS`. Bump
  allocator with CAS on `offset_`. Free-list with CAS on `free_head_`.
  Zero memory only in debug builds. `g_arena` global defined at file
  scope.

- **TradeRing**: declared in `include/market_data_processor.hpp`.
  `MarketDataProcessor` constructor allocates 100 × 1024 × 64B = 6.55MB
  from `g_arena` at startup. `get_trade_ring(uint32_t symbol_id)` returns
  const ref. Verified at runtime: "100 arena trade rings (6553600 bytes)".

## Build-Run Verification

```bash
cd /home/alca/projects/PubBTQuant/dependencies/BTQ_Render_Engine/build
cmake --build . -j$(nproc)   # ~20s incremental, ~5min from clean
ls -la BTQuantTerminal       # ~15.7MB
./BTQuantTerminal --help      # prints v1.0.0 banner, initializes, then
                              # gracefully exits if /dev/shm/btquant absent
```

Runtime output on this machine:
```
========================================
  BTQuant Trading Terminal v1.0.0
========================================
Initializing Data Layer...
[CacheManager] Initialized with max size: 104857600 bytes
[MarketDataProcessor] Initialized with 16 shards, 100 arena trade rings
(6553600 bytes) and 16 worker threads
[ERROR] Failed to open shared memory '/btquant': No such file or directory
```

`6553600 bytes` = 100 × 1024 × 64 confirms Phase 0.4 acceptance criterion:
"MarketDataProcessor constructor allocates all TradeRing buffers from
g_arena at startup without `new`."

## Phase 3/4/7 Panel Wiring (commit 3a74a138)

After the build was green, the per-panel work (Phase 3 Tape helpers,
Phase 4 DOM auto-center, Phase 7 crosshair readers, Phase 7.4 TSC
telemetry) was completed in small targeted patches rather than by a
single big subagent. The lesson: on this codebase, **subagent timeouts
are the bottleneck** — see the `subagent-driven-development` skill's
"Subagent Timeout Pitfall (observed 2026-06-17)" section. Below are
the exact patterns that shipped.

### Phase 3 — TapePanel helpers

Three helper methods declared in `include/components/tape_panel.hpp`
and implemented in `src/components/tape_panel.cpp`. All work against
`RenderEngine::TradeData` (the rich struct), not the spec struct —
because that's what `cached_trades_` actually contains.

```cpp
// 3.3 alpha percentile: O(N*W) rank-by-size for last 500 trades.
std::vector<double> TapePanel::computeAlphaRanks(
    const std::vector<RenderEngine::TradeData>& trades,
    size_t last_n = 500) const;

// 3.5 sweep: 50ms (50_000us) + price-delta between two consecutive trades.
bool TapePanel::detectSweep(const std::vector<RenderEngine::TradeData>& trades,
                            size_t original_index) const;

// 3.6 size filter slider (header inline).
bool passesSizeFilter(const RenderEngine::TradeData& t) const noexcept {
  return t.size >= static_cast<double>(size_filter_);
}
```

The size rule when adding fields to TapePanel: don't shrink `_pad` —
the existing code uses `t.size` (not `t.volume`); renaming the spec
struct's name would break the subscription-based feed path.

### Phase 4 — DOMSurfacePanel auto-center

Header fields added:
```cpp
bool   auto_center_enabled_ = true;
void*  heatmap_tex_id_       = nullptr;  // ImGui texture id from CachedTexture
double last_known_mid_      = 0.0;
```

`setHeatmapTextureId(void*)` / `getHeatmapTextureId()` accessor for the
caller (LobHeatmapComputePipeline). The AddImage call from the spec
(4.2) is NOT wired — the heatmap pipeline itself is a stub.

`updateAutoCenter()` is called at the top of every `render()` frame
(not only on dirty):
```cpp
void DomSurfacePanel::updateAutoCenter() {
  if (!auto_center_enabled_ || !processor_ || current_symbol_id_ == 0) return;
  auto snap_opt = processor_->get_atomic_snapshot(current_symbol_id_);
  if (!snap_opt) return;
  double mid = snap_opt->mid_price;
  if (mid <= 0.0) return;

  // Derive tick size from the first two book levels
  double tick_size = 0.01;
  auto book_opt = processor_->getOrderbookData(current_symbol_id_);
  if (book_opt) {
    const auto& book = *book_opt;
    if (book.bids.size() >= 2) tick_size = std::abs(book.bids[0].price - book.bids[1].price);
    else if (book.asks.size() >= 2) tick_size = std::abs(book.asks[0].price - book.asks[1].price);
  }
  if (tick_size <= 0.0) tick_size = 0.01;

  if (bounds_max_[1] > bounds_min_[1]) {
    double center = 0.5 * (bounds_min_[1] + bounds_max_[1]);
    double delta = mid - center;
    if (std::abs(delta) > tick_size * 5.0) {
      double shift = 0.1 * delta;
      bounds_min_[1] += shift;
      bounds_max_[1] += shift;
    }
  }
  last_known_mid_ = mid;
}
```

### Phase 7.1 — Crosshair global sync pattern

Header `include/sync/global_state.hpp`:
```cpp
inline std::atomic<double>  g_crosshair_price{0.0};
inline std::atomic<int32_t> g_crosshair_symbol_id{-1};
```

Helper `include/sync/crosshair_helper.hpp`:
```cpp
inline void write_crosshair(double price, int32_t symbol_id) noexcept;
inline void clear_crosshair() noexcept;
inline bool crosshair_active_for(int32_t active_symbol_id) noexcept;
inline double load_crosshair_price(int32_t active_symbol_id) noexcept;
inline void render_dashed_hline(ImDrawList* dl, float x_min, float x_max,
                                float y, ImU32 col, float dash_px) noexcept;
```

**Reader pattern (in every panel's render, at the end):**
```cpp
if (BTQuant::crosshair_active_for(symbol_id_)) {
  double ch_price = BTQuant::load_crosshair_price(symbol_id_);
  if (ch_price > 0.0) {
    ImVec2 panel_min = ImGui::GetWindowPos();
    float y = ImPlot::PlotToPixels(0.0, ch_price).y;  // or ChartMath::MapToScreen
    BTQuant::render_dashed_hline(ImGui::GetWindowDrawList(),
                                 panel_min.x + 30.0f,
                                 panel_min.x + ImGui::GetWindowWidth() - 10.0f,
                                 y);
  }
}
```

The **ChartPanel writer** (Phase 7.1) is the part still TODO — it
requires finding the mouse-hover handler inside the 5137-line
chart_panel.cpp and writing `BTQuant::write_crosshair(price,
active_symbol_id_)` whenever the mouse hovers a price level. The
inverse of `MapToScreen` for converting mouse-Y back to price is:

```cpp
double price_at_y = viewport_.minPrice + (1.0 - (y / panel_height_)) *
                     (viewport_.maxPrice - viewport_.minPrice);
```

### Phase 7.4 — TSC telemetry pattern

Calibrate once per process (in any `update()` or `render()` entry):
```cpp
static const double tsc_freq_mhz_ = []() {
#if defined(__x86_64__) || defined(__i386__)
  auto t0 = std::chrono::high_resolution_clock::now();
  uint64_t r0 = __rdtsc();
  std::this_thread::sleep_for(std::chrono::milliseconds(100));
  uint64_t r1 = __rdtsc();
  auto t1 = std::chrono::high_resolution_clock::now();
  double us = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();
  return (us > 0.0) ? (static_cast<double>(r1 - r0) / us) : 0.0;
#else
  return 0.0;  // portable fallback for non-x86
#endif
}();
```

Per-frame record at the end of update/render:
```cpp
#if defined(__x86_64__) || defined(__i386__)
static uint64_t tsc_last = __rdtsc();
uint64_t tsc_now = __rdtsc();
double us = (tsc_freq_mhz_ > 0.0)
                ? static_cast<double>(tsc_now - tsc_last) / tsc_freq_mhz_
                : 0.0;
btq::TelemetryCollector::getInstance().recordPerformanceMetric(
    "<panel>_render_us", us, "us");
tsc_last = tsc_now;
#endif
```

`TelemetryCollector` is the stub from earlier — `recordPerformanceMetric`
appends to an in-memory `std::vector` per metric. No remote endpoint
(no libuuid). To inspect: `TelemetryCollector::getInstance().getMetricSamples(...)`.

## What's still TODO (don't pretend it's done)

- Phase 1 GPU compute — `LobHeatmapComputePipeline::initialize()` is a
  stub. `GPUMemoryManager::add_texture()` doesn't exist yet. Real
  dispatch requires a working Vulkan instance.
- Phase 4.2 AddImage call — heatmap setter exists, but no caller wires
  the texture into DOM render.
- Phase 4.4 instanced volume bars — DOM still uses per-row AddRectFilled,
  not a single PrimReserve+memcpy pattern.
- Phase 7.1 ChartPanel crosshair **writer** — readers in footprint/tpo
  are wired; the writer in chart_panel.cpp is still TODO (requires
  finding the mouse-hover handler in 5137 lines).
- Real TTF fonts — `font_data.hpp` has empty 1-byte placeholder arrays.
  Drop in JetBrainsMono-Regular.ttf and FontAwesome6-Free-Solid-900.ttf
  to enable.
- ChartPanel end-of-render TSC pair — render() has the start __rdtsc()
  but no corresponding end record; pair it with another
  `recordPerformanceMetric` call.
- Vulkan TPO Compute Pipeline — `MarketMicrostructureRenderer::renderTPOProfile()`
  in `microstructure_renderer.cpp:1176` is still `// Draw TPO Histogram`
  comment + return. Pipeline exists but the actual GPU dispatch is
  unwritten.

---

## SHM Layout Drift Bugs (2026-06-18 acceptance test)

Two structural bugs were caught only by end-to-end smoke testing the
mock_data_producer.py → BTQuantTerminal pipeline. Both are silent
data-corruption bugs that produce valid-looking but wrong output.

### Bug A — HEADER_SIZE mismatch (80 vs 4096)

**Symptom:** `[WARNING] Invalid trade data - price: 2.121995799e-314,
size: 0` appears once per cycle in the log.

**Root cause:** `mock_data_producer.py` originally had
`HEADER_SIZE = 80`, but the C++ `HotSpineDataBridge` reserves
`HOTSPINE_HEADER_SIZE = 4096` (cache-line aligned). Python wrote
trades starting at offset 80 in the SHM; C++ read at offset 4096.
The first ~4016 bytes after the Python header were noise interpreted
as trades (denormal price `2.12e-314`, size 0).

**Fix:** `HEADER_SIZE = 4096  # must match C++ HOTSPINE_HEADER_SIZE
in hotspine_data_bridge.cpp` in `mock_data_producer.py`. The comment
is mandatory — the next person to touch the file needs to know.

**Why unit tests missed it:** Within each file the offsets were
correct. Only end-to-end testing reveals the cross-language drift.

### Bug B — `HotOrderbookSnapshot` missing `alignas(64)` (sizeof 6424 vs 6464)

**Symptom:** `[OrderbookPanel] Auto-selected: UNKNOWN (ID=2965605936)`
and `ActiveSyms` grew unbounded (218 → 378 → 500+). OrderbookPanel
title showed "UNKNOWN Orderbook".

**Root cause:** C++ struct had no `alignas` directive, so its
natural `sizeof` was 6424 bytes. Python wrote orderbooks at stride
`OB_SIZE = 6464` (40 bytes of cache-line padding — Python comment
even says `alignas(64): 6424 -> 6464`). The C++
`HotSpineDataBridge` iterates the orderbook ring buffer using
`sizeof(HotOrderbookSnapshot)` as the implicit stride, so after the
first orderbook the C++ was reading misaligned data — garbage
symbol_ids from random slots.

**Fix:** Add `alignas(64)` to the struct:
```cpp
struct alignas(64) HotOrderbookSnapshot {
  uint64_t ts_exchange;
  uint64_t ts_local;
  uint32_t symbol_id;
  // ... 200 bids, 200 asks
};
```
This rounds `sizeof` up from 6424 to 6464, matching the Python's
stride. `HotTrade` does NOT need `alignas(64)` — its natural
`sizeof(40)` already matches Python's `TRADE_SIZE = 40`.

**Verification (Python-side ground truth):**
```python
import mmap, struct
with open('/dev/shm/btquant', 'rb') as f:
    s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    ob_base = 4096 + 50000 * 40
    sids = [struct.unpack_from('<I', s, ob_base + i * 6464 + 16)[0]
            for i in range(5)]
    # sids should be [1..20], not garbage
```

### Root cause for both bugs

No shared `btquant_shm_layout.py` header between Python producer
and C++ consumer. The 100-iteration code review and the openhands
smoke test both missed these because neither did an end-to-end
symbol_id round-trip verification. **Future SHM layout changes
MUST update BOTH the Python producer and C++ consumer in the same
commit, with a shared constants file** (e.g. `btquant_shm_layout.py`
generated from `hotspine_data_bridge.hpp`).

---

## Mock Data Acceptance Test Procedure (2026-06-18)

End-to-end smoke test that catches the SHM layout drift bugs above
and similar data-flow breakage. Run this after ANY change to SHM
struct definitions, producer scripts, or HotSpineDataBridge.

### The 8-step procedure

```bash
# 1. Kill any zombie producer first
ps auxf | grep mock_data_producer | grep -v grep
# Check /proc/PID/fd for entries like "/dev/shm/btquant (deleted)"
# which means the producer is writing to a dead inode — kill it
kill <PID> || true

# 2. Start producer cleanly. NEVER use `| head -10` — see SIGPIPE pitfall
python3 mock_data_producer.py > /tmp/btq_producer.log 2>&1 &

# 3. Verify SHM is alive and sized correctly (15M = 4096 + 50000*40 + 2000*6464)
sleep 3
ls -la /dev/shm/btquant        # should be ~15M, not "No such file"
python3 -c "import mmap,struct; s=mmap.mmap(open('/dev/shm/btquant','rb').fileno(),0,access=mmap.ACCESS_READ); \
  print(struct.unpack_from('<I', s, 4096 + 50000*40 + 16)[0])"
# should print 1-20 (a real symbol_id), not garbage

# 4. Build clean — must end with "Built target BTQuantTerminal"
cd dependencies/BTQ_Render_Engine/build
cmake --build . -j$(nproc) 2>&1 | grep -E "error:|Built target" | grep -v nlohmann

# 5. Run terminal in background, capture full log
cd ..
./build/BTQuantTerminal > /tmp/btq_test.log 2>&1 &

# 6. Wait for initialization
sleep 10

# 7. Grep the log for these acceptance signals (ALL must appear):
grep "HotSpineDataBridge Connected" /tmp/btq_test.log        # proves producer reachable
grep "OrderbookPanel Auto-selected: [A-Z]" /tmp/btq_test.log # real symbol, not UNKNOWN
grep "ActiveSyms=20" /tmp/btq_test.log                       # exactly 20 symbols, no garbage
# These MUST be zero:
echo "WARNINGS: $(grep -c WARNING /tmp/btq_test.log)"
echo "ERRORS: $(grep -c ERROR /tmp/btq_test.log)"
echo "Invalid trade data: $(grep -c 'Invalid trade data' /tmp/btq_test.log)"
echo "UNKNOWN refs: $(grep -c UNKNOWN /tmp/btq_test.log)"

# 8. Acceptable stability metrics
grep "Trade W=" /tmp/btq_test.log | tail -3
# Rate should be ~100 trades/s, ~20 OBs/s. CPU 30-60%, RAM 1.5-1.8GB
ps -o pid,pcpu,pmem,rss,etime -p <terminal_pid>
```

### SIGPIPE pitfall — `python3 ... 2>&1 | head -10`

The bash pattern `python3 mock_data_producer.py 2>&1 | head -10`
**kills the producer** via SIGPIPE once head reads its 10 lines and
exits. The producer's SHM file may then appear in `/proc/PID/fd` as
`(deleted)` — the producer is writing to a dead inode that no
consumer can ever reach.

**Symptom pattern to recognize:**
```
$ ls -la /dev/shm/btquant
ls: cannot access '/dev/shm/btquant': No such file or directory
$ ps auxf | grep mock_data_producer  # still running
$ ls -la /proc/PID/fd 4
... /dev/shm/btquant (deleted)
```

**Always use the clean pattern:**
```bash
python3 mock_data_producer.py > /tmp/btq_producer.log 2>&1 &
```
No pipe to `head`, no pipe to `less`, no `timeout` that sends SIGTERM
after a few seconds.

### Mazemaker recall cache fallback when MCP goes down

`mcp__mazemaker__mazemaker_recall` and friends may time out mid-session
("MCP server unreachable after 3 consecutive failures"). The result
file is still written to `/tmp/hermes-results/call_function_*.txt`.
Extract with:
```python
import json
with open('/tmp/hermes-results/call_function_<id>.txt') as f:
    outer = json.loads(f.read())
inner = json.loads(outer['result'])
for h in inner:
    print(f"id={h['id']} sim={h.get('similarity',0):.3f}")
    print(h.get('content','')[:500])
```
This is the only reliable way to dig through memory during MCP
outages — once the cache file is gone, the data is unrecoverable
until MCP comes back.

---

## Quantower UI Feature Patterns (2026-06-18)

Patterns for closing the visual gap to Quantower. Three features
shipped as concrete commits on branch 0.0.2:
- `8ebd2933` ImGui Docking — draggable/resizable/undockable panels
- `1dbab780` TPO + Footprint wired to live ClusterEngine
- `b7ecd798` Order Flow Bars on Candles (Quantower signature)

### ImGui Docking setup pattern

`ImGuiConfigFlags_DockingEnable` was already set in `init()` since
2026, but no `DockSpaceOverViewport()` call existed, so docking was
inert. The fix is a fullscreen host window in `render_frame()`
right after `ImGui::NewFrame()`:

```cpp
ImGuiViewport* viewport = ImGui::GetMainViewport();
ImGui::SetNextWindowPos(viewport->WorkPos);
ImGui::SetNextWindowSize(viewport->WorkSize);
ImGui::SetNextWindowViewport(viewport->ID);
constexpr ImGuiWindowFlags host_flags =
    ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse |
    ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
    ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus |
    ImGuiWindowFlags_NoBackground | ImGuiWindowFlags_NoDocking;
ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
ImGui::Begin("##DockSpaceHost", nullptr, host_flags);
ImGui::PopStyleVar(2);
ImGuiID dockspace_id = ImGui::GetID("BTQuantMainDockSpace");
ImGui::DockSpace(dockspace_id, ImVec2(0, 0), ImGuiDockNodeFlags_PassthruCentralNode);

// First-run default layout via DockBuilder — static guard runs only once
static bool default_layout_set = false;
if (!default_layout_set) {
  default_layout_set = true;
  ImGui::DockBuilderRemoveNode(dockspace_id);
  ImGui::DockBuilderAddNode(dockspace_id, ImGuiDockNodeFlags_DockSpace);
  ImGui::DockBuilderSetNodeSize(dockspace_id, viewport->WorkSize);
  // ... DockBuilderSplitNode + DockBuilderDockWindow calls for each panel
  ImGui::DockBuilderFinish(dockspace_id);
}
ImGui::End();
```

Critical gotchas:
- The host window itself must have `ImGuiWindowFlags_NoDocking` set
  so it can't be detached from the viewport
- The panel `Begin()` calls must NOT have `NoDocking` (PanelBase already
  uses `ImGuiWindowFlags_None`, so this is fine)
- Panel window names use `"<Title>###panel_<ptr>"` format — the `###`
  separates display title from unique ID, so `DockBuilderDockWindow("Title", ...)`
  matches correctly
- On first run, delete `/dev/shm/../imgui.ini` (or wherever ImGui is
  configured to save state) to ensure a clean default-layout application
- After the first frame, ImGui persists the user's arrangement to
  `imgui.ini` automatically — the `static bool` guard prevents
  re-running the builder every frame

### ClusterEngine cross-panel wiring pattern

Panels that need the live ClusterEngine (TPO, Footprint, ChartPanel
for order flow bars) cannot get it via constructor injection because
the renderer and panel manager are independent. Pattern:

1. Add a public getter to `MarketMicrostructureRenderer`:
```cpp
Analytics::ClusterEngine* get_cluster_engine() { return cluster_engine_.get(); }
```

2. Add a public panel-map getter to `PanelManager`:
```cpp
const std::unordered_map<uint32_t, std::unique_ptr<PanelBase>>& get_panels() const {
  return panels_;
}
```

3. Add a `set_cluster_engine(Analytics::ClusterEngine*)` setter on each
   consumer panel (`TpoPanel`, `FootprintPanel`, `ChartPanel`).

4. In `VulkanDashboard::init_wiring()` (called AFTER `init_components()`):
```cpp
if (micro_renderer_ && workspace_) {
  if (auto* pm = workspace_->getPanelManager()) {
    Analytics::ClusterEngine* engine = micro_renderer_->get_cluster_engine();
    if (engine) {
      int wired = 0;
      for (auto& [id, panel] : pm->get_panels()) {
        if (auto* tpo = dynamic_cast<TpoPanel*>(panel.get())) {
          tpo->set_cluster_engine(engine); ++wired;
        }
        if (auto* fp = dynamic_cast<FootprintPanel*>(panel.get())) {
          fp->set_cluster_engine(engine); ++wired;
        }
        if (auto* chart = dynamic_cast<ChartPanel*>(panel.get())) {
          chart->set_cluster_engine(engine); ++wired;
        }
      }
      std::println("[VulkanDashboard] Wired {} panels to live ClusterEngine.", wired);
    }
  }
}
```

`MarketMicrostructureRenderer::set_cluster_engine_panel_manager()`
already exists as a stub — it can either be removed (use the
explicit `init_wiring()` path) or implemented properly. Don't
leave both paths active; double-wiring confuses the callback chain.

### Order Flow Bars on Candles (Quantower signature)

Draw a horizontal split bar INSIDE every candle body showing buy/sell
volume split. Requires per-time-bucket aggregation from the
ClusterEngine.

1. Add `ClusterEngine::getTimeBucketVolumes(time_bucket_idx)` that
   sums `buy_volume` and `sell_volume` across all price levels:
```cpp
struct TimeBucketVolumes { double buy{0.0}; double sell{0.0}; bool valid{false}; };
TimeBucketVolumes getTimeBucketVolumes(size_t idx) const {
  TimeBucketVolumes r;
  if (cluster_canvas_.empty()) return r;
  const size_t bucket_count = cluster_canvas_[0].size();
  if (idx >= bucket_count) return r;
  for (const auto& row : cluster_canvas_) {
    if (idx < row.size()) {
      r.buy += row[idx].buy_volume;
      r.sell += row[idx].sell_volume;
      r.valid = true;
    }
  }
  return r;
}
```

2. In the candle render loop, after `draw_list->AddRectFilled(body_tl,
   body_br, color);`:
```cpp
if (cluster_engine_) {
  const size_t bucket_count = cluster_engine_->getTimeBucketCount();
  if (bucket_count > 0) {
    const size_t bucket_idx = i % bucket_count;
    const auto vols = cluster_engine_->getTimeBucketVolumes(bucket_idx);
    if (vols.valid) {
      const double total = vols.buy + vols.sell;
      if (total > 0.0) {
        const float buy_ratio = static_cast<float>(vols.buy / total);
        const float bar_h = std::max(2.0f, (body_br.y - body_tl.y) * 0.6f);
        const float bar_y_top = (body_tl.y + body_br.y) * 0.5f - bar_h * 0.5f;
        const float sell_w = (body_br.x - body_tl.x) * (1.0f - buy_ratio);
        draw_list->AddRectFilled(body_tl, {body_tl.x + sell_w, bar_y_top + bar_h},
                                  IM_COL32(230, 25, 38, 180));   // crimson sell
        draw_list->AddRectFilled({body_tl.x + sell_w, bar_y_top}, body_br,
                                  IM_COL32(0, 230, 102, 180));     // mint buy
      }
    }
  }
}
```

First-pass mapping is `candle_index % bucket_count` (modular). A
more accurate version would compute the bucket from the candle's
timestamp using the cluster engine's session start and bucket size.

### LSP false positives when adding cross-cutting types

When patching a header to add a new field of a type from another
namespace (e.g. `Analytics::ClusterEngine*`), the LSP often reports
"Use of undeclared identifier 'Analytics'" even though the actual
compiler succeeds. **Always confirm with `cmake --build`, not the
LSP diagnostics.** The fix is usually:
- Add the include `#include "../analytics/cluster_engine.hpp"` at
  the top of the consuming header (not just the .cpp)
- Or add a forward declaration in a namespace scope the consumer
  can see

---

## Build state as of 2026-06-18

Branch `0.0.2`, 23 commits ahead of `origin/0.0.2`:

- ImGui Docking enabled — draggable/resizable/undockable panels
- TPO Profile + Footprint panels wired to live ClusterEngine
- Order Flow Bars on Candles (Quantower signature)
- Phase 3.3 tape alpha-by-size rank
- Phase 4.2 DOM GPU heatmap texture backdrop
- char[N]→std::string migration in 3 panels (36 strcpy calls gone)
- alignas(64) on HotOrderbookSnapshot (fixes OrderbookPanel UNKNOWN bug)
- mock_data_producer.py HEADER_SIZE 80→4096 (fixes denormal noise trades)

Acceptance test: `Wired 3 TPO/Footprint panels`, `Default dock
layout applied`, 0 warnings/errors/UNKNOWN/`Invalid trade data`,
400k+ trades and 70k+ orderbooks in 10-min stability run.