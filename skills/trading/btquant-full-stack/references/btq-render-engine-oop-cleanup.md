# BTQ_Render_Engine Iterative OOP-Cleanup Recipe

Session: 2026-06-17 (100+ iterations of deep code review on
`dependencies/BTQ_Render_Engine/`, branch 0.0.2).

Net result across 13 commits: 26 files changed, 218 insertions,
749 deletions. The codebase is meaningfully smaller AND more correct
than when the session started.

This recipe describes the workflow that worked. It is **not** a one-off
script — it is a multi-pass pattern for systematically tightening any
C++ codebase that mixes procedural code with OOP.

## The Workflow

### 1. Establish a green baseline

```bash
cd /home/alca/projects/PubBTQuant/dependencies/BTQ_Render_Engine/build
cmake --build . -j$(nproc)
ls -la BTQuantTerminal   # confirm size and timestamp
./BTQuantTerminal --help  # smoke test — should print banner then exit
```

If the baseline is not green, **fix the build first**. Do not start
OOP review on a broken codebase — every later edit will pile on top
of the unresolved errors. The 100-iteration cleanup was preceded by
~15 iterations of pure build-fix work (iomanip include, orphan .cpp
discovery, libuuid stub, CachedTexture stub, etc.).

### 2. Inventory the surface

Before touching code, count and classify what you have:

```bash
cd /home/alca/projects/PubBTQuant/dependencies/BTQ_Render_Engine
echo "=== File counts ==="
find . -name '*.cpp' -not -path './build/*' | wc -l
find . -name '*.hpp' -not -path './build/*' | wc -l
find . -name '*.h' -not -path './build/*' | wc -l

echo "=== .cpp files NOT in CMakeLists ==="
comm -23 <(find src -name '*.cpp' | sort) \
          <(grep -oE 'src/[a-zA-Z_/.-]+\.cpp' CMakeLists.txt | sort -u)

echo "=== Headers without #pragma once or #ifndef ==="
for f in include/components/*.hpp include/*.hpp; do
  head1=$(head -1 "$f")
  echo "$head1" | grep -qE 'pragma once|#ifndef' || echo "$f"
done
```

### 3. Pick an iteration theme, do one pass, commit

Each iteration picks **one** narrow OOP issue class, fixes it across
the whole codebase, commits, then verifies the build is still green
before picking the next theme. Themes used in the actual 2026-06-17
session:

| Pass | Theme | Files touched |
|------|-------|---------------|
| 1 | Orphan duplicate header | 1 |
| 2 | Orphan forward declarations (structs) | 1 |
| 3 | Raw `new` for never-read raw pointer | 2 |
| 4-7 | `static` locals → instance members | 7 |
| 19-23 | Orphan .cpp / .hpp deletions | 6 |
| 34 | Stub UI control → real implementation | 2 |
| 40 | Duplicate loop body → helper | 2 |
| 44 | `#ifndef` → `#pragma once` | 1 |
| 62 | `// TODO` button bodies → real logic | 2 |
| 70 | By-value string getter → `const std::string&` | 1 |
| 76 | `strcpy`/`strncpy` → `std::string` | 1 |
| 80-81 | Deprecated empty methods + call sites | 3 |
| 90 | Free utility funcs → anonymous namespace | 2 |

### 4. The build-after-every-edit discipline

After every patch, run:

```bash
cd build && cmake --build . -j$(nproc) 2>&1 | tail -10
```

If a single edit breaks the build, fix it before the next iteration.
Do **not** stack edits — 5 changes with 5 broken builds is worse
than 5 changes with 0 broken builds.

### 5. Anti-Patterns Found (the actual checklist)

These are real patterns observed in BTQ_Render_Engine, in priority
order. Use this list as a starting checklist for any C++ cleanup:

#### High-impact (correctness bugs, not just style)

- **Static locals in render methods** — `static bool is_drawing = false;`
  inside `void Panel::render()` means every instance of that panel
  shares one global state. Two watchlists clobber each other's
  subscription_check_timer. Fix: instance member.

- **Empty method bodies with `// TODO` comments** — the method
  compiles, the caller succeeds, nothing happens. Delete both the
  method and its call site (or implement).

- **Forward-declared but never-implemented structs** — pollutes
  the type system, misleads readers about architecture. Delete the
  declarations.

- **Duplicate `.cpp` files with divergent implementations** — e.g.
  `src/symbol_registry.cpp` (regex-based, never built) vs
  `src/data/symbol_registry.cpp` (nlohmann-based, built). Both
  compile separately, but only one is wired. Delete the orphan.

#### Medium-impact (OOP purity)

- **Free functions at namespace scope** in panel `.cpp` — wrap in
  `namespace { ... }` for internal linkage.

- **Getters returning `std::string` by value** — return
  `const std::string&` unless the function constructs a fresh
  string (e.g. from a map lookup).

- **strcpy/strncpy for non-ImGui string output** — use `std::string`.
  Exception: `ImGui::InputText` requires `char[]`.

- **Inconsistent include guards** — some files `#pragma once`, some
  `#ifndef BTQ_*_HPP`. Pick one (project uses `#pragma once`).

#### Low-impact (style)

- **`__VA_ARGS__` GNU extension** — fine on GCC/Clang. If MSVC is
  ever needed, switch to `__VA_OPT__(,)`.

- **`<iomanip>` / `<chrono>` / `<thread>` in heavy headers** — push
  to `.cpp` where possible. Headers should pull only `<cstdint>`,
  `<memory>`, etc.

- **`std::endl` in hot paths** — replace with `'\n'`. Doesn't apply
  in debug/error paths.

### 6. Build-Rescue Recipes

The initial build green-up phase (~15 iterations) is documented in
`references/render-engine-build-rescue.md`. Common traps:

- `error_handling/error_reporter.hpp` — missing `#include <iomanip>`
  for `std::put_time` / `std::setfill` / `std::setw`.
- `shader_spirv.hpp` — needs `LOB_HEATMAP_COMPUTE_SPIRV` array embedded
  as `static const uint32_t[]`. Generate via Python `struct.unpack`
  from `shaders/spirv/lob_heatmap.spv` (1744 uint32_t words = 6976 bytes).
- `vulkan_base_types.hpp` — missing `CachedTexture` struct (5 fields).
- `telemetry_collector.cpp` — needs `libuuid` symbols (`uuid_generate`,
  `uuid_unparse`). Not available — stub the .cpp with no-op
  implementations that satisfy the header.

### 7. The Dual TradeData Trap (re-stated)

The most dangerous migration trap in this codebase. Two structs
coexist:

| Struct | Field path |
|--------|-----------|
| `BTQuant::Data::TradeData` | `trade.ts.timestamp_us` (union) |
| `BTQuant::RenderEngine::TradeData` | `trade.timestamp` (direct field) |

A blanket `sed -i 's/trade\.timestamp/trade.ts.timestamp_us/g'` breaks
half the codebase. Verify the file's namespace block first:
`namespace BTQuant::Data {` → uses Data::TradeData.
Otherwise → uses RenderEngine::TradeData.

The sed also accidentally hits:
- Local variables named `timestamp` (uint64_t)
- Function parameters named `timestamp`
- Comments mentioning timestamp

To scope the sed: use `\.` (the dot) as anchor: `trade\.timestamp`
only matches the field access pattern.

### 8. Verification Pattern After the Cleanup

```bash
cd /home/alca/projects/PubBTQuant
git diff --stat 3a74a138 HEAD   # see net change vs the pre-cleanup baseline
./BTQuantTerminal --help       # smoke test still passes
```

Expected outcome: net deletion (-X insertions, +Y deletions, |X| > |Y|)
because dead code removal outpaces new wiring.