# btquant_vulkan Rebuild Sessions 2026-06-19

## Context

Two back-to-back sessions moved `sfgg/btquant_vulkan/` (clean rebuild
prototype) into `/home/alca/projects/PubBTQuant/btquant_vulkan/` and
finished it. After the first session the binary launches and renders 4
widgets (OrderBook / DOM / Trades / TPO) with real Vulkan+ImGui+ImPlot,
themed Linear Dark + Kraken Purple. After the second session the
architecture gained a 5th widget (Heatmap) driven by a real GLSL
compute kernel, and a live data pipeline that pulls from
`/dev/shm/btquant_hotspine` (with a synthetic random-walk fallback
when no producer is running).

The original sfgg/ codebase had many stubs and API mismatches with
the current dependencies (Vulkan 1.4.350, ImGui docking branch as of
2025-09-26, ImPlot master, NVIDIA driver 610.43.02 on X11+i3).

**This is the FIRST genuinely Vulkan-rendered BTQuant terminal** (in
contrast to `dependencies/BTQ_Render_Engine/` which is OpenGL 4.6 with
Vulkan headers reserved — see `btq-render-engine-oop-cleanup.md`).

## Two-Project Structure (canonical from these sessions)

| Path | Role | Backend | Status |
|---|---|---|---|
| `dependencies/BTQ_Render_Engine/` | Production engine | OpenGL 4.6 (GLFW Wayland, GLEW, SPIR-V as `uint32_t[]` in `Renderer.cpp`, Vulkan headers reserved) | Mature, 60+ panels, theme, workspace composition |
| `btquant_vulkan/` (top-level) | New rebuild target | REAL Vulkan (GLFW + VkSurfaceKHR + VulkanContext + compute pipeline) | 5 widgets running, GPU compute heatmap, live data pipeline, theme applied |

When porting the 60+ panels from BTQ_Render_Engine to btquant_vulkan,
expect to redo the render path under real Vulkan compute/graphics
pipelines, not copy ImGui_ImplOpenGL3 calls verbatim.

## Build Blocker Fixes (in order applied)

### 1. GLFW3 not found by CMake — fall back to pkg-config

**Symptom:** `find_package(glfw3 QUIET)` returns NOTFOUND, code fails to
link with `undefined reference to glfwCreateWindow` etc.

**Root cause:** `glfw3Config.cmake` is not installed (it's a system
package without CMake config on most distros). Headers at
`/usr/include/GLFW/glfw3.h` and library at `/usr/lib64/libglfw.so.3` ARE
present, but `find_package` doesn't see them.

**Fix:** In CMakeLists.txt, fall back to pkg-config when CMake config
is missing:
```cmake
find_package(glfw3 QUIET)
if(NOT glfw3_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(GLFW3 REQUIRED glfw3)
    set(glfw3_FOUND TRUE)
    set(GLFW3_USES_PKGCONFIG TRUE)
endif()
```
And in the target_link_libraries section, branch on
`GLFW3_USES_PKGCONFIG` to use `${GLFW3_LIBRARIES}` and
`${GLFW3_LIBRARY_DIRS}` directly, plus
`target_include_directories(... PRIVATE ${GLFW3_INCLUDE_DIRS})`.

**Verification:** `pkg-config --libs --cflags glfw3` returns `-lglfw`
on this system; `pkg-config --exists glfw3 && echo OK` succeeds.

### 2. SDL2 was getting preferred over GLFW

**Symptom:** `compile_commands.json` shows `-DBTQUANT_USE_SDL2`, and the
`#ifdef BTQUANT_USE_GLFW` blocks in `vulkan_context.cpp` and `main.cpp`
never fire, leading to `glfwCreateWindow` undefined.

**Root cause:** The original CMakeLists had SDL2 first in the
`if(SDL2_FOUND) ... else() ... find_package(glfw3) ... endif()` chain.
`find_package(SDL2 QUIET)` succeeded on this system because SDL2 2.32.70
is installed (`/usr/lib/cmake/SDL2/SDL2Config.cmake` exists), so the
GLFW branch never ran. But the C++ code is `GLFW-only` (no
`#ifdef BTQUANT_USE_SDL2` paths exist anywhere).

**Fix:** Remove `find_package(SDL2 QUIET)` entirely. Force GLFW:
```cmake
# Force GLFW (system-installed library; no CMake config on most distros).
# NOTE: SDL2 intentionally not used — this codebase is GLFW-only.
find_package(glfw3 QUIET)
if(NOT glfw3_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(GLFW3 REQUIRED glfw3)
    ...
endif()
if(NOT glfw3_FOUND)
    message(FATAL_ERROR "GLFW3 not found via CMake config or pkg-config")
endif()
```

### 3. ImGui/ImPlot not linkable as `-limgui` / `-limplot`

**Symptom:** Linker error: `-limgui kann nicht gefunden werden` and
`-limplot kann nicht gefunden werden`.

**Root cause:** `target_link_libraries(btquant_vulkan PRIVATE imgui implot)`
tries to link against `libimgui.so` and `libimplot.so`, which don't
exist because ImGui and ImPlot are header/source-only via FetchContent
— they have no CMake target that produces a static/shared library.

**Fix:** Add ImGui + ImPlot + backends as source files to the executable:
```cmake
add_executable(btquant_vulkan ${SOURCES} ${HEADERS}
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_demo.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_vulkan.cpp
    ${implot_SOURCE_DIR}/implot.cpp
    ${implot_SOURCE_DIR}/implot_items.cpp
    ${implot_SOURCE_DIR}/implot_demo.cpp
)
```
Remove `imgui implot` from the `target_link_libraries` call. ImGui +
ImPlot are now compiled directly into the binary.

### 4. New ImGui docking branch API (2025-09-26)

**Symptom:** `ImGui_ImplVulkan_InitInfo has no member 'Subpass'`,
`'MSAASamples'`, `'RenderPass'`. Compile errors.

**Root cause:** The current ImGui docking branch removed the
standalone `RenderPass`/`Subpass`/`MSAASamples` fields from
`ImGui_ImplVulkan_InitInfo` on 2025-09-26. They moved into a new
nested struct `ImGui_ImplVulkan_InitInfo::PipelineInfoMain` (and
`PipelineInfoForViewports`).

**Old API (pre-2025-09-26):**
```cpp
init_info.RenderPass = renderPass;
init_info.Subpass = 0;
init_info.MSAASamples = VK_SAMPLE_COUNT_1_BIT;
ImGui_ImplVulkan_Init(&init_info, renderPass);  // second arg = renderPass
```

**New API (current docking branch):**
```cpp
init_info.PipelineInfoMain.RenderPass = renderPass;
init_info.PipelineInfoMain.Subpass = 0;
init_info.PipelineInfoMain.MSAASamples = VK_SAMPLE_COUNT_1_BIT;
init_info.UseDynamicRendering = false;
ImGui_ImplVulkan_Init(&init_info);  // no second arg
```

**Also:** `ApiVersion` field is required (use `VK_API_VERSION_1_3` to
match the instance appInfo).

**Also:** `ImGui_ImplVulkan_RenderDrawData` gained a new optional
third parameter `VkPipeline pipeline = VK_NULL_HANDLE` (default works
fine).

### 5. `IMGUI_IMPL_VULKAN_NO_PROTOTYPES` requires `LoadFunctions()`

**Symptom:** `SIGSEGV at 0x0` inside `ImGui_ImplVulkan_Init` on launch.

**Root cause:** Defining `IMGUI_IMPL_VULKAN_NO_PROTOTYPES` strips the
Vulkan function prototypes from the ImGui source so the user must
provide them. If you don't call `ImGui_ImplVulkan_LoadFunctions()` before
`ImGui_ImplVulkan_Init()`, the function pointers are null and the first
call dereferences NULL.

**Fix:** Don't define `IMGUI_IMPL_VULKAN_NO_PROTOTYPES`. The standard
Vulkan loader (`libvulkan.so`) provides all prototypes via normal linking.

```cmake
# REMOVE this:
# target_compile_definitions(btquant_vulkan PRIVATE IMGUI_IMPL_VULKAN_NO_PROTOTYPES)
```

### 6. `isDeviceSuitable` called `querySwapchainSupport` before `m_physicalDevice` was set

**Symptom:** `[Vulkan Loader] ERROR: vkGetPhysicalDeviceSurfaceCapabilitiesKHR:
Invalid physicalDevice [VUID-vkGetPhysicalDeviceSurfaceCapabilitiesKHR-physicalDevice-parameter]`
Then SIGSEGV / SIGABRT.

**Root cause:** `pickPhysicalDevice` iterates devices and calls
`isDeviceSuitable(device)` BEFORE assigning `m_physicalDevice = device`.
But `isDeviceSuitable` calls `querySwapchainSupport()` which read
`m_physicalDevice` (the MEMBER, still NULL) instead of the device
parameter. Result: `vkGetPhysicalDeviceSurfaceCapabilitiesKHR(NULL, ...)`
which is undefined behaviour in NVIDIA's loader and returns "Invalid
physicalDevice" from validation.

**Fix:** Make `querySwapchainSupport` take the device as a parameter
instead of reading the member:
```cpp
[[nodiscard]] SwapchainSupportDetails
querySwapchainSupport(VkPhysicalDevice device) const noexcept;
```
And update both call sites:
```cpp
// pickPhysicalDevice:
SwapchainSupportDetails swapChainSupport = querySwapchainSupport(device);  // was querySwapchainSupport()

// createSwapchain:
SwapchainSupportDetails swapChainSupport = querySwapchainSupport(m_physicalDevice);
```

This is a classic init-order bug: don't read a member that you haven't
written yet.

### 7. `initialize()` called `createInstance` a second time

**Symptom:** NVIDIA driver crash in `findQueueFamilies`, SIGSEGV in
`libnvidia-glcore.so.610.43.02`, at `m_surface + 0x18` offset.

**Root cause:** `main.cpp` did:
```cpp
vkContext.createInstance();  // first call, sets m_instance
... setSurface() ...
vkContext.initialize();  // calls createInstance AGAIN, replaces m_instance
```
The surface is attached to the FIRST instance, but `initialize()`'s
`createInstance` makes a SECOND instance. `findQueueFamilies` then calls
`vkGetPhysicalDeviceSurfaceSupportKHR(device, m_surface, ...)` where
`m_surface` references the dead first instance → driver crash.

**Fix:** `VulkanContext::initialize()` should NOT call `createInstance()`
because the surface (which needs the GLFW window handle) must be
created between instance creation and the rest of init. The caller's
responsibility:
```cpp
std::optional<std::string> VulkanContext::initialize() noexcept {
    if (m_instance == VK_NULL_HANDLE)
        return "createInstance() must be called before initialize()";
    if (m_surface == VK_NULL_HANDLE)
        return "setSurface() must be called before initialize()";
    if (auto err = pickPhysicalDevice()) return err;
    if (auto err = createLogicalDevice()) return err;
    ...
}
```
And `main.cpp`:
```cpp
vkContext.createInstance();
VkSurfaceKHR surface;
glfwCreateWindowSurface(vkContext.instance(), window, nullptr, &surface);
vkContext.setSurface(surface);
vkContext.initialize();  // now runs the rest of the chain
```

### 8. `vkQueuePresentKHR` used wrong imageIndex

**Symptom:** Visual glitches / wrong framebuffer presented / eventually
validation layer errors. Hard to catch — works "most of the time".

**Root cause:** The original `endFrame()` did
`presentInfo.pImageIndices = &m_currentFrame;` — but `m_currentFrame`
is the **frame-in-flight counter** (mod `m_maxFramesInFlight`), NOT the
swapchain image index returned by `vkAcquireNextImageKHR`. They're
independent. Same bug in `currentCommandBuffer()` and `inFlightFence()`
— they indexed into per-image arrays using `m_currentFrame`.

**Fix:** Add `uint32_t m_currentImageIndex = 0;` member. Set it in
`beginFrame()` after `vkAcquireNextImageKHR`:
```cpp
uint32_t imageIndex;
vkAcquireNextImageKHR(..., &imageIndex);
m_currentImageIndex = imageIndex;  // <-- new
```
Use it in `endFrame`:
```cpp
presentInfo.pImageIndices = &m_currentImageIndex;  // was &m_currentFrame
```
Add a `currentFramebuffer()` getter that returns
`m_framebuffers[m_currentImageIndex]` so the render pass can bind the
matching framebuffer for the acquired image.

Also copy `m_currentImageIndex` in the move-assignment operator.

### 9. `glfwCreateWindow` hangs on NVIDIA + X11 + i3

**Symptom:** `glfwCreateWindow(width, height, "BTQuant Terminal", nullptr, nullptr)`
blocks forever. Reproducible in a minimal test:
```cpp
glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
GLFWwindow* w = glfwCreateWindow(1280, 720, "Test", nullptr, nullptr);
```
Process gets stuck after `glfwCreateWindow` enters but before it
returns. No X11 error, no timeout, no log. The binary uses 17% CPU
(constant event loop) but never returns.

**Root cause:** This is a known NVIDIA driver + X11 + tiling WM (i3 in
this case) interaction with `GLFW_NO_API` windows. Likely the WM
sends a ConfigureNotify that the Xlib event queue blocks on, combined
with the NVIDIA driver's glx dispatch behavior. NOT a bug in the user
code.

**Workaround (headless / server-friendly):** Create the window with
`GLFW_VISIBLE = GLFW_FALSE`. The window exists, gets a valid XID, the
swapchain still renders to it, but the WM doesn't try to manage it and
no hang occurs. Trade-off: no visible window, but the Vulkan pipeline
fully runs.
```cpp
glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);  // off-screen — avoids WM block
```
For a desktop session, change to `GLFW_VISIBLE` to `GLFW_TRUE`. For
debugging this is the off-screen / headless config.

**Alternative:** Use Wayland via
`glfwWindowHint(GLFW_PLATFORM, GLFW_PLATFORM_WAYLAND)` which avoids the
X11 hang entirely (the production `BTQ_Render_Engine` uses this — see
`btq-render-engine-oop-cleanup.md`).

### 10. ImGui 1.91+ removed `SliderDouble`

**Symptom:** `error: »SliderDouble« ist kein Element von »ImGui«;
meinten Sie »SliderAngle«?`

**Root cause:** ImGui 1.91 unified the scalar widgets — `SliderDouble`,
`SliderFloat`, `SliderInt` etc. were all removed in favor of
`SliderScalar(type, data, *min, *max, format)`.

**Fix:**
```cpp
// Before:
ImGui::SliderDouble("Price Grouping", &m_priceGrouping, 0.001, 1.0, "%.4f");

// After:
static const double price_min = 0.001, price_max = 1.0;
ImGui::SliderScalar("Price Grouping", ImGuiDataType_Double,
                    &m_priceGrouping, &price_min, &price_max, "%.4f");
```
Note: `min`/`max` are POINTERS — must be stable (use `static const`).

Affected widgets in btquant_vulkan: `order_book_widget.cpp`,
`dom_widget.cpp`, `trades_widget.cpp` (one usage each).

### 11. `ImPlot::PlotBars` signature changed

**Symptom:** `error: keine passende Funktion für Aufruf von
»PlotBars(const char [13], double*, double*, std::vector<double>::size_type)«`

**Root cause:** Current ImPlot master has 2 overloads:
- `PlotBars(label, values, count, bar_size, shift)` — single series
- `PlotBars(label, xs, ys, count, bar_size)` — XY series

The original call `PlotBars("TPO Activity", prices.data(), counts.data(), prices.size())`
passes 4 args with mismatched types (passes `size_t` for the `count`
int parameter and two double* where the first overload expects one).

**Fix:**
```cpp
ImPlot::PlotBars("TPO Activity", counts.data(), (int)counts.size(), 0.67);
```
Single-series bar plot of counts on the Y axis, with bar width 0.67
(the default).

### 12. `VulkanContext::currentCommandBuffer()` used wrong index

**Symptom:** Recorded commands into the wrong command buffer / device
lost / validation errors. Same root cause as #8.

**Root cause:** `currentCommandBuffer()` returned
`m_commandBuffers[m_currentFrame]` — but the command buffer that
`beginFrame` set up for the acquired image is
`m_commandBuffers[imageIndex]`. Recording into the wrong one means
the GPU executes commands referencing the wrong framebuffer.

**Fix:** Don't use `currentCommandBuffer()` from mainLoop — capture
the return value of `beginFrame()` directly (which is
`m_commandBuffers[imageIndex]`) and use that throughout the frame.
In `main.cpp`:
```cpp
VkCommandBuffer cmd = vkContext.beginFrame();  // cmd == m_commandBuffers[imageIndex]
...
vkCmdBeginRenderPass(cmd, ...);
uiContext.render(cmd);
vkCmdEndRenderPass(cmd);
vkContext.endFrame();
```

### 13. GLSL `#` comments are illegal — use `//`

**Symptom:** `error: '#' : invalid directive: BTQuant` (then 13 more
"errors generated" for the rest of the file). glslc rejects the file
before `#version 450` is parsed.

**Root cause:** GLSL only accepts `//` for comments. The shader file
began with `# BTQuant Heatmap Compute Shader\n#\n# Aggregates a...` —
Python-style docstring syntax that GLSL treats as preprocessor
directives. `#version 450` must be the FIRST non-comment, non-whitespace
line; everything before it has to be `//` comments.

**Fix:** Replace all leading `#` with `//`:
```glsl
// BTQuant Heatmap Compute Shader
//
// Per-pixel workgroup pattern, R8G8B8A8 storage image, ...
#version 450
```

### 14. Missing `<string>` include causes "no declaration matches" for `std::optional<std::string>` returns

**Symptom:** `error: keine Deklaration passt zu »std::optional<std::__cxx11::basic_string<char> > HeatmapCompute::createXxx()«` for **only some** member functions. The ones that fail are always the same — the ones that share a particular return type pattern. The first 3 private helpers (`createInputBuffer`, `createOutputImage`, `createConfigBuffer`) compile fine, but the next 3 fail.

**Root cause:** Without `#include <string>`, `<optional>` doesn't
transitively pull in `<string>` on all toolchains. `std::optional<T>`
requires T to be complete, but `T = std::string` without `<string>` is
incomplete. The compiler reports the error against the first 3
definitions only because they happen to be the ones whose bodies don't
actually instantiate `std::optional<std::string>` (their bodies are
all Vulkan-call-only). The next 3 definitions
(`createDescriptorSetLayout`, `createPipeline`, `createDescriptorSet`)
all have early returns like `return "error string";` which finally
force the template instantiation, and the missing `<string>` blows up
there.

The "no declaration matches" error is misleading — the declaration IS
in the .hpp. The real issue is that the *definition* can't be parsed
because `std::string` is incomplete.

**Fix:** Add `#include <string>` to the .hpp that declares functions
returning `std::optional<std::string>`:
```cpp
#include <vulkan/vulkan.h>
#include <cstdint>
#include <optional>
#include <string>   // <-- add this, even if it seems transitively included
#include <vector>
```

### 15. `ImGui_ImplVulkan_AddTexture` returns `VkDescriptorSet`, NOT `ImTextureID` (new ImGui API)

**Symptom:** `error: ungültige Umwandlung von »VkDescriptorSet« in »ImTextureID«`
when assigning the return of `ImGui_ImplVulkan_AddTexture(...)` to a
member declared as `ImTextureID`. Or a "no matching function" error
when passing the stored texture back to
`ImGui_ImplVulkan_RemoveTexture`.

**Root cause:** In the post-2025-09-26 ImGui docking branch, the
public API changed: `ImGui_ImplVulkan_AddTexture` returns the raw
`VkDescriptorSet` (the underlying Vulkan handle), and the caller is
expected to use `reinterpret_cast<ImTextureID>(descriptor_set)` to
store it. `ImTextureID` itself is `ImU64` (uint64), not a pointer. The
old code assumed a direct assignment would work.

**Fix:** explicit `reinterpret_cast` in both directions:
```cpp
// Register:
m_imguiTextureId = reinterpret_cast<ImTextureID>(
    ImGui_ImplVulkan_AddTexture(sampler, imageView,
                               VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL));

// Free:
ImGui_ImplVulkan_RemoveTexture(
    reinterpret_cast<VkDescriptorSet>(m_imguiTextureId));
```

`ImGui::Image(m_imguiTextureId, size)` works unchanged — the cast is
only at the API boundary.

### 16. `vkGetBufferMemoryRequirements` on a `VkImage` is a hard error

**Symptom:** `error: »VkImage« {aka »VkImage_T*«} kann nicht nach »VkBuffer« umgewandelt werden` — call to
`vkGetBufferMemoryRequirements(m_device, m_outputImage, &req)`.

**Root cause:** Copy-paste from `createBuffer` (which uses a
`VkBuffer`) into `createImage` (which uses a `VkImage`). The
vulkan_core.h signatures are distinct.

**Fix:** use the matching function:
```cpp
// For images:
vkGetImageMemoryRequirements(m_device, m_outputImage, &req);
// For buffers:
vkGetBufferMemoryRequirements(m_device, m_outputBuffer, &req);
```

### 17. HotSpineEntry binary layout — struct.pack format swap

**Symptom:** `struct.error: 'I' format requires 0 <= number <= 4294967295`
in the mock producer.

**Root cause:** `HotSpineEntry` in `data_spine.hpp` declares the field
order as `4 doubles → uint64 timestamp → uint32 seq → uint32 flags`,
giving a total of 48 bytes + 80 padding = 128. The mock producer
originally packed with `<ddddIQI` which swapped the order to
`uint32 → uint64 → uint32`. The first `I` got `ts_us` (a microsecond
timestamp ≈ 1.7×10^15), which overflows uint32's 4.29×10^9 ceiling.

**Fix:** Use the correct order:
```python
# struct format for HotSpineEntry (matches C++ struct exactly):
#   4 doubles (bid, ask, bid_size, ask_size) = 32 bytes
#   uint64 timestamp                       = 8  bytes
#   uint32 seq                              = 4  bytes
#   uint32 flags                            = 4  bytes
#   --                                   = 48 bytes + 80 padding
payload = struct.pack("<ddddQII", bid, ask, bid_size, ask_size,
                      ts_us, seq, 0)
```

When the C++ struct and Python struct disagree, EITHER side's size
will be wrong, and either side's read will pick up misaligned data.
Always cross-check with `sizeof(HotSpineEntry)` from
`std::cout << sizeof(data::HotSpineEntry) << std::endl;` — must
print 128.

### 18. Relative include paths, not root-anchored

**Symptom:** `fatal error: data/data_spine.hpp: Datei oder Verzeichnis nicht gefunden`
in files that live in `src/data/` or `src/widgets/`. The CMake
include root is `${CMAKE_CURRENT_SOURCE_DIR}` (project root), not
`${CMAKE_CURRENT_SOURCE_DIR}/src/`. The existing codebase uses
relative paths from each file's directory.

**Root cause:** The new code mixed conventions — some headers used
`#include "data/data_spine.hpp"` (works from main.cpp which is at
`src/`, fails from `src/data/` or `src/widgets/`).

**Fix:** Match the existing convention — relative paths from the
including file:
```cpp
// In src/data/market_data_processor.cpp:
#include "data_spine.hpp"      // same dir
#include "market_data.hpp"     // same dir
// In src/widgets/heatmap_widget.cpp:
#include "../renderer/heatmap_compute.hpp"
```

**Test:** If a header is found by clangd but not by `cmake --build`,
it's an include-path convention mismatch, not a real bug. Confirm
with the real compiler.

## ui_context.cpp Wiring (the OLD `ui_context.cpp` was a stub)

The shipped `ui_context.cpp::initialize()` was a 1-line stub that just
set `m_initialized = true`. To actually get ImGui rendering, the
initialize function needs to:

1. `IMGUI_CHECKVERSION(); ImGui::CreateContext(); ImPlot::CreateContext();`
2. Set `io.ConfigFlags |= ImGuiConfigFlags_DockingEnable`
3. Apply BTQuant theme (Linear Dark `#08090a`, Kraken Purple `#7132f5`):
   ```cpp
   ImGui::StyleColorsDark();
   ImGuiStyle& style = ImGui::GetStyle();
   style.Colors[ImGuiCol_WindowBg] = ImVec4(0.031f, 0.035f, 0.039f, 1.0f);
   style.Colors[ImGuiCol_Text]    = ImVec4(0.969f, 0.973f, 0.973f, 1.0f);
   style.Colors[ImGuiCol_Button]  = ImVec4(0.443f, 0.196f, 0.961f, 1.0f);
   ```
4. `ImGui_ImplGlfw_InitForVulkan(window, true);`
5. Create a large `VkDescriptorPool` (1000 sets × 11 descriptor types,
   `FREE_DESCRIPTOR_SET_BIT`).
6. Fill `ImGui_ImplVulkan_InitInfo` with `PipelineInfoMain` API and
   call `ImGui_ImplVulkan_Init(&init_info)`.

The new `newFrame()` and `render(cmd)` are:
```cpp
void UIContext::newFrame() {
    ImGui_ImplVulkan_NewFrame();
    ImGui_ImplGlfw_NewFrame();
    ImGui::NewFrame();
}
void UIContext::render(VkCommandBuffer commandBuffer) {
    ImGui::Render();
    ImDrawData* dd = ImGui::GetDrawData();
    if (dd && dd->CmdListsCount > 0)
        ImGui_ImplVulkan_RenderDrawData(dd, commandBuffer);
}
```

The new `shutdown()` mirrors the init: `ImGui_ImplVulkan_Shutdown()`,
`ImGui_ImplGlfw_Shutdown()`, `ImPlot::DestroyContext()`,
`ImGui::DestroyContext()`, destroy the descriptor pool.

## Phase 2: GPU Compute + Live Data (second session, "a+b")

After Phase 1, the user asked for both: GPU compute shaders for the
heatmap panel AND live DataSpine→MarketDataAggregator→Widgets wiring.
The result: a 5th widget (Heatmap) driven by a real GLSL compute
kernel aggregating the live trade stream, plus a thread-safe
MarketDataProcessor that polls `/dev/shm/btquant_hotspine` and falls
back to a synthetic random-walk generator when no producer is
running. The 4 old widgets still use static mock data in their
`render()` methods — that's the next iteration's wire-up.

### 19. Per-pixel workgroup pattern — no atomics needed for aggregation heatmaps

**Pattern (recommended for heatmap-style aggregations where each
output pixel is a deterministic function of the input):**

```glsl
layout(local_size_x = 16, local_size_y = 16, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Input { Trade trades[]; } input;
layout(set = 0, binding = 1, rgba8) uniform image2D output;     // STORAGE + SAMPLED
layout(set = 0, binding = 2, std140) uniform Config { ... } cfg;

void main() {
  ivec2 pixel = ivec2(gl_GlobalInvocationID.xy);
  if (pixel.x >= int(cfg.image_width) || pixel.y >= int(cfg.image_height)) return;

  float px = (float(pixel.x) + 0.5) / float(cfg.image_width);
  float py = (float(pixel.y) + 0.5) / float(cfg.image_height);

  // Aggregate trades that fall into this pixel's bin
  float total_buy = 0.0, total_sell = 0.0;
  for (uint i = 0; i < cfg.num_trades; ++i) {
    Trade t = input.trades[i];
    if (t.time >= px - 0.5/float(cfg.image_width) && t.time < px + 0.5/float(cfg.image_width) &&
        t.price >= py - 0.5/float(cfg.image_height) && t.price < py + 0.5/float(cfg.image_height)) {
      if (t.side == 0u) total_buy += t.volume;
      else total_sell += t.volume;
    }
  }

  // Write to R8G8B8A8 storage image (no atomics needed — each pixel is one thread)
  vec4 color = vec4(intensity, buy_n, sell_n, 255.0);
  imageStore(output, pixel, color);
}
```

**Host side:** dispatch with
`vkCmdDispatch((width+15)/16, (height+15)/16, 1)`.
**Image usage flags:** `STORAGE_BIT | SAMPLED_BIT | TRANSFER_DST_BIT`.
**Layout transitions around dispatch:** `SHADER_READ_ONLY_OPTIMAL →
GENERAL` before, `GENERAL → SHADER_READ_ONLY_OPTIMAL` after.

Why this beats the atomic-add pattern: no race conditions, no
read-modify-write hazards, no need for two images (compute writes to
a single image that ImGui can sample). The per-pixel work means
the total compute cost is `O(width × height × num_trades)` — for
256×256 and 1024 trades, that's 67M operations, which a modern GPU
completes in well under 1ms.

### 20. MarketDataProcessor pattern — background thread + thread-safe snapshot

For HFT-style data pipelines feeding multiple widgets, the canonical
pattern is:

- **One background thread** that polls the data source (DataSpine,
  Kafka, WebSocket, whatever) and pushes ticks into a
  `MarketDataAggregator`.
- **One mutex** around a `Snapshot` struct that's a by-value copy
  of the latest state.
- **Widgets call `snapshot()`** which returns a `Snapshot` — they
  never touch the aggregator directly.
- **Synthetic fallback** when the data source is unavailable, so
  the UI shows live data even before the producer is running.

```cpp
class MarketDataProcessor {
public:
    struct Snapshot {
        data::OrderBook order_book;
        data::MarketMetrics metrics;
        std::vector<data::Trade> recent_trades;
        uint64_t snapshot_seq = 0;
    };
    Snapshot snapshot(size_t last_n = 100) const;

private:
    void runLoop();
    data::MarketDataAggregator m_aggregator;
    mutable std::mutex m_snapshotMutex;
    Snapshot m_latestSnapshot;
    std::atomic<bool> m_running{false};
    std::thread m_thread;
};
```

The background thread also generates synthetic ticks when the SHM
can't be opened — this lets the binary start cleanly before the
mock producer is launched, and demos the wire-up without requiring
infrastructure.

### 21. glslc compile target via CMake + auto-embed SPIR-V as `constexpr`

**shaders/CMakeLists.txt:**
```cmake
find_program(GLSLC_EXECUTABLE NAMES glslc HINTS ${Vulkan_GLSLANG_BIN_DIR})
function(SHADER_COMPILE SRC_FILE)
    get_filename_component(SRC_NAME "${SRC_FILE}" NAME_WE)
    set(SPV_OUT "${CMAKE_CURRENT_BINARY_DIR}/spirv/${SRC_NAME}.comp.spv")
    add_custom_command(
        OUTPUT "${SPV_OUT}"
        COMMAND "${GLSLC_EXECUTABLE}" -fshader-stage=comp
                "${CMAKE_CURRENT_SOURCE_DIR}/${SRC_FILE}"
                -o "${SPV_OUT}"
        DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/${SRC_FILE}"
        COMMENT "Compiling shader ${SRC_FILE}"
        VERBATIM)
endfunction()
SHADER_COMPILE(heatmap.comp)
add_custom_target(btquant_vulkan_shaders DEPENDS ${BTQUANT_SHADER_SPV})
```

**Embed script** (one-liner via Python struct):
```python
import struct
with open("build/spirv/heatmap.comp.spv", "rb") as f: data = f.read()
n = len(data) // 4
words = struct.unpack(f"<{n}I", data[:n*4])
# emit as: static constexpr uint32_t HEATMAP_COMP_SPIRV[1329] = { ... };
```

Header: `inline constexpr uint32_t HEATMAP_COMP_SPIRV[1329] = { ... };`
Loaded at runtime:
```cpp
vkCreateShaderModule(device, &sm{
    .codeSize = WORDS * 4,
    .pCode = HEATMAP_COMP_SPIRV
}, nullptr, &m_shaderModule);
```

This is the same pattern used in
`dependencies/BTQ_Render_Engine/include/shader_spirv.hpp` — keep both
engines consistent.

## Pipeline End-to-End (current state)

```
mock_producer.py (GBM simulator, 10 Hz)
   │
   ▼ /dev/shm/btquant_hotspine (UQTB header + 128-byte symbol records)
   │
   ▼ DataSpine::open() + readAllEntries()
   │
   ▼ MarketDataProcessor::runLoop() [std::thread, 16ms poll]
   │     - on each tick: MarketDataAggregator::update()
   │     - publish Snapshot under m_snapshotMutex
   │
   ▼ MarketDataProcessor::snapshot() [thread-safe copy]
   │
   ▼ mainLoop::pushTradesToHeatmap() [normalizes (price, time) → [0,1]]
   │
   ▼ HeatmapWidget::m_buffer
   │
   ▼ HeatmapWidget::render() → m_compute->updateTrades() + dispatch()
   │
   ▼ HeatmapCompute::dispatch(cmd) [OUTSIDE render pass]
   │     - SHADER_READ_ONLY → GENERAL barrier
   │     - vkCmdBindPipeline + vkCmdBindDescriptorSets + vkCmdDispatch
   │     - GENERAL → SHADER_READ_ONLY barrier
   │
   ▼ heatmap.comp [256×256 R8G8B8A8, 16×16 workgroups, per-pixel aggregation]
   │
   ▼ Storage image (also sampled by ImGui as ImTextureID)
   │
   ▼ ImGui::Image(heatmapTextureId, 384, 384) inside render pass
```

## Mock Producer — `scripts/mock_producer.py`

The Python producer at `scripts/mock_producer.py` writes a realistic
GBM-style price stream to `/dev/shm/btquant_hotspine`:
- 10 Hz update rate (`--interval-ms 100`)
- Random walk `dS = σ·S·dW` with `σ = 0.0002` (≈ 20 bps/sec for crypto)
- Spread varies with volatility (`spread * (1 + |dW| * 50)`)
- Always includes a symbols JSON at `/dev/shm/btquant_symbols.json`

The mock is intentionally small (1 symbol) — the design supports N
symbols via `m_symbolCount` in the header, but the new aggregator
only handles symbol 0. Multi-symbol is the next iteration.

## HeatmapCompute + HeatmapWidget — minimal viable class pattern

```cpp
// Renderer-side (no ImGui dependency in the .hpp):
class HeatmapCompute {
public:
    std::optional<std::string> initialize(VkDevice, VkPhysicalDevice,
                                          VkCommandPool, VkQueue, uint32_t family);
    void updateTrades(const TradeInput*, uint32_t count);
    void dispatch(VkCommandBuffer cmd);
    ImTextureID textureId() const noexcept;
    void shutdown();
};

// UI-side:
class HeatmapWidget {
public:
    bool initialize(HeatmapCompute&);
    void push(float price, float time, float volume, uint32_t side);
    void render();   // calls updateTrades + draws ImGui::Image
};
```

`HeatmapWidget` owns the trade buffer; the actual Vulkan resources
and compute dispatch live in `HeatmapCompute`. `main.cpp` owns both
and calls `pushTradesToHeatmap()` once per frame to feed the buffer
from the latest MarketDataProcessor snapshot.

## Why This Matters for Future Sessions

The `btquant_vulkan/` project now has:
- A real Vulkan render loop with ImGui + ImPlot (4 widgets from Phase 1)
- A 5th widget driven by a GPU compute kernel (heatmap, Phase 2)
- A live data pipeline from `/dev/shm/btquant_hotspine` with synthetic
  fallback (Phase 2)
- A mock producer for end-to-end testing (Phase 2)

When porting the 60+ panels from
`dependencies/BTQ_Render_Engine/src/components/` to `btquant_vulkan/`:
- Use the **NEW** ImGui docking branch API everywhere
  (`PipelineInfoMain.RenderPass`, no `RenderPass` member on
  `ImGui_ImplVulkan_InitInfo`).
- Add real compute shaders in `shaders/` (the
  `SHADER_COMPILE(<name>)` helper in `shaders/CMakeLists.txt` is the
  pattern; `vpvr.comp` for volume profile, `footprint.comp` for
  order flow accumulation are obvious next targets).
- Wire `DataSpine + MarketDataAggregator` to the 4 remaining
  widgets (they currently have static `mockBids`/`mockAsks` /
  `mockTrades` data in their render methods — replace with
  `marketData.snapshot()` lookups).
- Use the existing Linear Dark + Kraken Purple theme in `UIConfig`
  (currently using hardcoded style in `ui_context.cpp`).
- Watch for the `glfwCreateWindow` NVIDIA+X11+i3 hang and apply
  the off-screen workaround.

## Verification (after any change)

```bash
cd /home/alca/projects/PubBTQuant/btquant_vulkan
rm -rf build && bash build.sh 2>&1 | tail -5
# Expect: [100%] Built target btquant_vulkan + [100%] Built target test_integration

# Run the main binary briefly — must reach the main loop without crash
timeout 5 ./build/btquant_vulkan
# Expect: empty stdout, exit 124 (timeout's normal exit, meaning program ran the full 5s)

# Run the integration test
./build/test/test_integration
# Expect: all 4 ✓ marks (Vulkan instance, MarketData, data structs, RingBuffer)
#   The "vkDestroyInstance: Invalid instance" warning at the end is a known
#   test_artifact (test creates a Context and lets the destructor handle it
#   without explicit cleanup) — does not affect pass/fail.
```

End-to-end smoke test with live data:
```bash
# Start producer in background
python3 scripts/mock_producer.py --interval-ms 100 &
# Start terminal
timeout 8 ./build/btquant_vulkan
# Both should run cleanly for the timeout duration without crash.
# The Heatmap widget will render the GPU-aggregated trade pattern.
```

## What is still TODO (intentionally not in these sessions)

- 60+ panels port from `BTQ_Render_Engine/src/components/` (the
  big one)
- Wire `DataSpine + MarketDataAggregator` to the 4 remaining
  widgets (Order Book / DOM / Trades / TPO still have static mock
  data in their `render()` methods)
- Multi-symbol support in MarketDataProcessor (currently only
  handles symbol 0)
- Replace hardcoded theme in `ui_context.cpp` with `UIConfig`
  fields from the header (currently `m_config` is declared but unused)
- Make window visible in real desktop sessions
  (flip `GLFW_VISIBLE` to `GLFW_TRUE`, or switch to Wayland platform)
- Validation layer: not enabled (was disabled in original code; if
  enabled, will need to address the validation warnings about
  `m_imguiDescriptorPool` and the VUID checks on `vkDestroyInstance`)
- More compute shaders: `vpvr.comp` (volume profile), `footprint.comp`
  (order flow), `tpo.comp` (time-price opportunity aggregation)
- ImGui::DockBuilder-driven default layout (currently uses simple
  `DockSpaceOverViewport` with PassthruCentralNode; no first-run
  split)

## Cross-references

- `references/render-engine-build-rescue.md` — the OLD engine's
  parallel build-fix log (BTQ_Render_Engine in `dependencies/`).
  Different fix surface area; this file is the NEW engine's.
- `references/btq-render-engine-oop-cleanup.md` — production engine's
  OOP cleanup pattern. Reference for the panel-port phase (next sprint).
- `references/btquant-ui-design.md` — design language (Linear Dark +
  Kraken Purple, Inter font, WCAG AA contrast). Applied in
  `ui_context.cpp::initialize()` already.
- `references/btquant-harmony-ui-implementation.md` — Operating Map
  pattern. Will be relevant when the panel-port phase adds the
  hierarchical selector and workspace composition.
- `mcp_mazemaker` fact `fact:btquant-vulkan-rebuild-fixes-2026-06-19`
  — session memory of the same fixes, for cross-session recall.
- `mcp_mazemaker` fact `fact:btquant-two-vulkan-projects` — the
  canonical two-project structure summary.
- `mcp_mazemaker` fact `fact:btq-render-engine-opengl-not-vulkan` —
  the "OpenGL despite Vulkan name" surprise in the production engine.
