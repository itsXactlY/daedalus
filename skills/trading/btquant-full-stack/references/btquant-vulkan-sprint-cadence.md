# BTQuant Vulkan Sprint Cadence (Sprint #40+, post-Phase 38)

The pattern the operator runs when iterating on `btquant_vulkan/`. Established across Sprints #28–#40 (Phases 28–40). Every session that picks up "WEITER" or "FRAG NICHT IMMER SO BEHINDERT" uses this cadence.

## Operator workflow (the "WEITER" rhythm)

When the user says "WEITER", "FRAG NICHT IMMER SO BEHINDERT", "continue", or any equivalent in the BTQuant Vulkan sprint, the agent MUST:

1. **Pick the next item from the deferred list** (see `references/btquant-vulkan-deferred-items.md` if it exists; otherwise pick from the most recent sprint's "WEITER" suggestions in the prior turn's output).
2. **Ship it in 1–2 commits** — pure plumbing first (test surface + static methods), then render wiring. Each commit compiles + all tests green before the next starts.
3. **Run `git add src/ test/ CMakeLists.txt`** — NEVER `git add -A`. The parent project tree has sibling-agent directories (e.g. `autonomous_agency/`) that pollute the commit. See "Parallel-agent tree contamination" below.
4. **Smoke-test the build** with `timeout 3 ./build/btquant_vulkan` — must produce "[BTQuant] loaded settings from …" without crashing. If it segfaults, fix before commit.
5. **Save a `fact:btquant-sprint-NN-…` memory entry** with: WHAT IS TRUE (new state), WHY IT MATTERS (user-visible payoff), HOW IT WAS RESOLVED (commit ref + file changes), and the running sprint count.
6. **Suggest the next 3–4 deferred items as a single short list** at the end of the response. NOT a question, NOT a multi-choice prompt. A flat list the user can scan in 2 seconds.
7. **Stop and wait** for "WEITER" / "FRAG NICHT IMMER SO BEHINDERT". Do NOT ask "what next?", do NOT propose a feature, do NOT explain trade-offs.

When the user says "stop", "undo", "roll back", or expresses frustration with the cadence, STOP IMMEDIATELY and don't surface the deferred list. The user's "FRAG NICHT IMMER SO BEHINDERT" is a workflow preference, not an invitation to fill silence with suggestions.

## Test pattern: ImGui plumbing without a live ctx

Almost every BTQuant Vulkan widget needs ImGui to render. Tests don't have an ImGui context. The standard pattern that lets us test plumbing without driving the full render loop:

### 1. Guard every public method that touches ImGui globals

```cpp
void MyWidget::applyDpiScale(double scale) {
    if (ImGui::GetCurrentContext() == nullptr) return;  // ← guard
    // ... real work
}
```

Add this guard to:
- `saveCurrentTheme()`, `resetThemeToDefault()` (Theme)
- `applyDpiScale()` (HiDPI)
- `applyInitialDockLayoutIfNeeded()` (Layout)
- `submit()` (OrderTicket — submits to a callback, doesn't actually need ImGui globals but the `m_open`/`m_sideIsBuy` state can be inspected)
- Any future public method that calls `ImGui::GetIO()`, `ImGui::GetStyle()`, `ImGui::GetCurrentContext()`, `ImGui::PushID/PopID`, or `ImGui::Render*`.

If you forget the guard, the test crashes with SIGSEGV at exit (the ctor allocates widgets; the public method reaches into a null ImGui ctx).

### 2. Make plumbing fields public for testability

```cpp
public:
    // Last scale we applied — public for testability
    // (matches the m_defaultStyleSnap pattern).
    double m_appliedDpiScale = 1.0;
private:
    // real private state
```

The pattern from `m_defaultStyleSnap`, `pendingDockLayout`, `m_appliedDpiScale`. Tests assert against the public field; the private machinery stays encapsulated.

### 3. Test surface = static methods + public accessors

For math:
```cpp
static double priceToPixelY(double price, double yMin, double yMax,
                           float canvasY, float canvasH);
```

For state:
```cpp
bool isOpen() const;
void setSideBuy(bool v);
double liveRefPrice() const;
```

For I/O:
```cpp
static std::string formatTradesCSV(const std::vector<Trade>&);
static bool exportTo(const std::path& dest, const std::string& name);
```

Tests cover: default state, setter round-trips, pure math against known inputs, bad-input rejection, determinism. Smoke tests cover actual rendering.

### 4. Test isolation for filesystem-affecting code

`LayoutIO` / `ThemeIO` / `TradeJournal` / `PositionBook` all touch `~/.config/btquant_vulkan/`. Tests must:

```cpp
std::string isoHome = "/tmp/btquant_test_X_" + std::to_string(::getpid());
std::filesystem::create_directories(isoHome);
setenv("HOME", isoHome.c_str(), 1);
// ... test ...
unsetenv("HOME");
std::filesystem::remove_all(isoHome);
```

Always restore HOME afterwards — leaking the env var pollutes downstream tests.

## HotkeyAction extension pattern

Every new hotkey follows the same 4-step pattern:

1. **Header (hotkey_config.hpp):** add the enum value before `COUNT`, bump COUNT.
2. **Defaults (hotkey_config.cpp):** `m.set(HotkeyAction::NewAction, { GLFW_KEY_X, ctrl, shift });` — pick a key combo that doesn't collide with existing F-key or Ctrl-shortcut.
3. **Dispatch (window_manager.cpp):** `case HA::NewAction: /* handler */; break;` inside the `dispatchAction` switch.
4. **Tests (test_integration.cpp):** verify (a) the action is in `defaults()`, (b) the binding shape (key + ctrl + shift) is correct, (c) `match()` routes the right key combo to the right action, (d) `actionName()` round-trips the name.

After 4 hotkey tests you can ship in 1 commit. Test 28's `enumerate() covers all 31 actions` is the regression guard — bump that number when COUNT goes up.

HotkeyAction::COUNT acts as the public API. Any new value inserted before COUNT must NOT reorder existing values' ordinals (the hotkey.ini save format uses positional indexing implicitly via the `enumerate()` iteration order — but values are keyed by name so reordering is technically safe; still, don't reorder unless you have a reason).

## Parallel-agent tree contamination (CRITICAL)

`/home/alca/projects/PubBTQuant/btquant_vulkan/` is a subdirectory of `/home/alca/projects/`. The parent contains sibling-agent trees:

- `autonomous_agency/` — autonomous research agency (writes strategy files, results, evolution data, archive/)
- Other agent directories that appear + disappear without notice

If you `git add -A` here, you will pull in 666KB+ of unrelated agent output (json results, pdf reports, png visualizations). The first time this happened (Sprint #34, layout export/import), the fix was:

```bash
git reset --soft HEAD~1            # back out the bad commit, keep changes staged
git reset HEAD -- ../autonomous_agency/  # unstage sibling tree
git commit -m "..."                 # recommit with the correct 5 files only
```

**Rule (in MEMORY.md):** always list explicit paths: `git add src/ test/ CMakeLists.txt`. Never `-A`. Verify with `git status --short | head -10` before `git commit`.

## Common build/test commands

```bash
# Build (single thread, no incremental jank)
cmake --build build -j$(nproc) 2>&1 | tail -10

# Full test suite
./build/test/test_integration 2>&1 | tail -50

# Quick check: how many green checks?
./build/test/test_integration 2>&1 | grep -c "✓"
./build/test/test_integration 2>&1 | grep -c "✗"

# Smoke test the live binary (3s timeout — it would otherwise run forever)
timeout 3 ./build/btquant_vulkan 2>&1 | tail -3
```

Expected baseline: 298 ✓, 0 ✗ across 46 tests (as of Sprint #40). If that drops, the last change regressed something.

## Memory cadence

After every sprint, save a `fact:btquant-sprint-NN-<short-name>` memory via `mcp__mazemaker__mazemaker_remember`. Body 60–300 words. Lead with WHAT IS TRUE (new state), WHY IT MATTERS (user-visible payoff), HOW IT WAS RESOLVED (commit ref + file changes), and the running sprint count. One memory per discrete fact — multiple `mazemaker_remember` calls per turn are expected on substantive turns.

**Do NOT save:** session progress logs, "Phase N done", "fixed bug X" without context, file counts that will be stale in 7 days.

## Per-sprint failure modes (recent)

These are the bugs that cost time in Sprints #28–#40. Watch for them:

- **Forward-declaring `btquant::ui::Foo` then using it as a complete type in the same namespace block** → "incomplete type" error. Fix: include the actual header, not a forward declaration.
- **`data::Trade` referenced in widget header without the include** → field "is incomplete type". Fix: `namespace btquant::data { struct Trade; }` forward decl works for pointer types but not for value fields. Use the value-type include if the field is a value, not a pointer.
- **Clang's `unique_ptr`-move warning from `setSubmitFn(std::move(fn))`** when the parameter is `const std::function<...>&` → use `SubmitFn` by value and `std::move` on the member. Or accept by rvalue reference.
- **m_xxx private + tests need access** → use the public-for-testability pattern, same as `pendingDockLayout`, `m_defaultStyleSnap`, `m_appliedDpiScale`.
- **Save format includes ordinal position** → reordering enum values breaks saved hotkey.ini. Don't reorder.
- **glfwGetWindowMonitor returns null in tests** → the main loop check must `if (mon)` guard before calling `glfwGetMonitorContentScale`.
- **ImPlot::PlotCandlestick missing in vendored ImGui** → draw bodies via raw `ImDrawList` instead, with pure-static pixel helpers for testability.
- **Templated `static thread_local std::unordered_map` for per-instance state** (TradesWidget synthetic fallback) — use `this` as the key so two widget instances don't share state.

## What NOT to capture in skill updates

- Specific commit SHAs (rot, become stale)
- Sprint counts (move with each commit)
- File paths that move during refactors
- "Fixed bug X" without WHY + HOW (the WHY/HOW is the lesson, the X is just one instance)

Capture the PATTERN. The pattern outlives any single instance.
