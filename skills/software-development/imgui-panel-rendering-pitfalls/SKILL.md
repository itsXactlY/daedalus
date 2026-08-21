---
name: imgui-panel-rendering-pitfalls
description: "Diagnose and fix ImGui panel rendering failures — ID stack corruption, PushID/PopID leaks, docking issues, window flag misuse. Load when ImGui panels don't render, show blank, or spew imgui-error messages."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [imgui, debugging, cpp, ui, rendering, panels]
    category: software-development
    related_skills: [btquant-maintenance-routine, systematic-debugging]
---

# ImGui Panel Rendering Pitfalls

Diagnose and fix ImGui panels that don't render, show blank, or spew `imgui-error` messages. Covers the most common failure modes in C++ ImGui applications with panel-based architectures.

## When to use this skill

Load this skill when:
- A panel or widget that should be visible is not rendering
- The log shows many `[imgui-error] Mismatching PushID/PopID!` or `Missing PopID()` messages
- ImGui's ID stack corruption is suspected (widgets render in wrong parents, click targets are wrong, IDs collide)
- Docking doesn't work as expected (panels don't dock, dock layout doesn't persist)
- Window flags prevent expected behavior (e.g., a panel can't be moved/resized when it should be)

## The #1 pitfall: PushID/PopID imbalance in loops

This is the single most common ImGui bug that silently breaks rendering. It caused 4283 errors in a single run of a trading terminal, corrupting every widget ID in the application.

### The pattern

```cpp
for (const auto& entry : list) {
    ImGui::PushID(entry.id);  // ← pushed inside the loop

    // ... render widgets using entry.id as part of ImGui ID stack ...

    if (someCondition) {
        ImGui::BeginDragDropTarget();
        // ...
        ImGui::EndDragDropTarget();
    }
}  // ← NO PopID! ID stack grows by 1 per iteration per frame
```

If you have **two** PushIDs inside the loop (e.g., one for column 0 and one for column 10), you need **two** PopIDs at the end. A single PopID leaves the second PushID leaked.

### The symptom

```
[imgui-error] In window 'Watchlist###panel_...': Mismatching PushID/PopID!
[imgui-error] In window 'Watchlist###panel_...': Missing PopID()!
```

These repeat every frame. After a few seconds, the ID stack is thousands deep, and **every subsequent widget ID in the application is wrong**. Widgets either don't render, render in wrong parents, or have broken click targets.

### The fix

```cpp
for (const auto& entry : list) {
    ImGui::PushID(entry.id);  // first push
    // ... widgets for column 0 ...
    ImGui::PushID(entry.id);  // second push (if needed)
    // ... widgets for column 10 ...
    ImGui::EndDragDropTarget();

    // Match every Push with a Pop. Order matters (LIFO).
    ImGui::PopID();  // matches second PushID
    ImGui::PopID();  // matches first PushID
}
```

### How to find the bug

1. Search for `PushID` and count them: `grep -c PushID file.cpp`
2. Search for `PopID` and count them: `grep -c PopID file.cpp`
3. If counts don't match, there's a leak (or an extra PopID)
4. For loops, count PushIDs inside the loop body and PopIDs at the end of the loop body — they must match per iteration

### The diagnostic chain

When the terminal shows blank panels or broken rendering:

1. **Check the log for imgui-errors** — `grep imgui-error logfile`
2. **Count errors per run** — more than a few dozen means real corruption
3. **Identify the offending window** — the error message includes the window name
4. **Find PushID/PopID in that file** — count them, fix the imbalance
5. **Rebuild and re-run** — errors should drop to 0

### "0" file fallback: ImGui silently writes a single-digit ini file

When `io.IniFilename` is set to a path whose parent directory does NOT
exist, ImGui's `SaveIniSettingsToDisk` opens the path via `ImFileOpen`
which fails silently (returns null). ImGui then falls back to writing
its settings to a file literally named `"0"` in the **current working
directory**. You end up with BOTH:

1. The intended `imgui.ini` is missing (because the dir didn't exist)
2. A stray file called `0` appears in CWD, with the full ImGui ini content

The `0` file has no extension, no obvious purpose, and silently
pollutes the working directory. On every subsequent run it gets
overwritten with current ImGui state.

**Reproduction:** delete `/dev/shm` (or any path component ImGui is
configured to write to), launch the binary, observe:

```
$ ls -la
-rw-r--r-- 1 alca alca 855 Jun 20 04:38 0
$ xxd 0 | head -3
00000000: 5b57 696e 646f 775d 5b44 6f63 6b53 7061  [Window][DockSpa
```

**Fix:** call `std::filesystem::create_directories(parent_path())`
BEFORE composing any child path. Order in `initUI` is critical:

```cpp
auto settingsPath = util::Settings::defaultPath();
std::filesystem::create_directories(settingsPath.parent_path());  // ← FIRST
auto iniPath = (settingsPath.parent_path() / "imgui.ini").string();  // ← THEN
```

If `parent_path()` already exists, `create_directories` is a no-op.
Safe to call unconditionally.

**Defensive `.gitignore`:** even with the fix, add the fallback
filenames to the project `.gitignore` so a future regression doesn't
pollute git history:

```
# ImGui fallback ini (single-digit filename)
/0
/btquant_vulkan/0
/btquant_*/0
```

The skill `agent-delivery-integrity` and the BTQuant Vulkan
`btquant-full-stack` skill both document this fix in their phase-7
reference.

### "Continue from where you left off" → re-verify, don't re-trust

Use `ImGui::BeginTable` with `ImGuiTableFlags_RowBg` for any tabular
reference (hotkey lists, key-value displays, settings panels).
Row backgrounds make alternating rows visible without forcing the user
to read every label. Pattern:

```cpp
if (ImGui::BeginTable("hotkeys", 2, ImGuiTableFlags_RowBg)) {
    ImGui::TableSetupColumn("Key",  ImGuiTableColumnFlags_WidthFixed, 110.0f);
    ImGui::TableSetupColumn("Action");
    ImGui::TableHeadersRow();

    for (const auto& [key, action] : hotkey_list) {
        ImGui::TableNextRow();
        ImGui::TableNextColumn(); ImGui::TextUnformatted(key);
        ImGui::TableNextColumn(); ImGui::TextUnformatted(action);
    }
    ImGui::EndTable();
}
```

For hand-rolled tables (not generated from a data structure), prefer
inline lambdas over a vector + loop — clearer at the call site and
you can keep the table close to the place it's used:

```cpp
auto row = [](const char* key, const char* action) {
    ImGui::TableNextRow();
    ImGui::TableNextColumn(); ImGui::TextUnformatted(key);
    ImGui::TableNextColumn(); ImGui::TextUnformatted(action);
};
row("F2", "Toggle Order Book");
row("F3", "Toggle Order Book Depth");
// ...
```

For dynamic tables (data-driven), `if (...) row(key, action)` inside
a loop is fine. The hand-rolled static pattern is for documentation
that the user can read — don't auto-generate from the same source
as the hotkey table; the help table usually needs MORE entries (Ctrl+L,
ESC, ? key, Shift+combos) than the binding table has.

## Theme switching: StyleColorsDark/Light then override specific ImGuiCol entries

When implementing a runtime theme toggle, the pattern is:

1. Call `ImGui::StyleColorsDark()` OR `ImGui::StyleColorsLight()` to set
   the base palette (~40 colors).
2. THEN override the specific `ImGuiCol_*` entries you care about with
   your brand colors. Don't try to set every color — the base palette
   has good defaults for the rest.

```cpp
void UIContext::applyTheme(Theme t) {
    if (t == Theme::Dark) ImGui::StyleColorsDark();
    else                  ImGui::StyleColorsLight();

    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 8.0f;
    style.FrameRounding  = 4.0f;
    style.ScrollbarSize  = 12.0f;

    if (t == Theme::Dark) {
        style.Colors[ImGuiCol_WindowBg]        = ImVec4(0.031f, 0.035f, 0.039f, 1.0f);
        style.Colors[ImGuiCol_Text]           = ImVec4(0.969f, 0.973f, 0.973f, 1.0f);
        style.Colors[ImGuiCol_Button]         = ImVec4(0.443f, 0.196f, 0.961f, 1.0f);
        // ... brand-specific overrides
    } else {
        style.Colors[ImGuiCol_WindowBg]        = ImVec4(0.973f, 0.973f, 0.980f, 1.0f);
        style.Colors[ImGuiCol_Text]           = ImVec4(0.078f, 0.086f, 0.102f, 1.0f);
        style.Colors[ImGuiCol_Button]         = ImVec4(0.196f, 0.408f, 0.961f, 1.0f);
        // ...
    }
}
```

**Pitfall:** `MenuItem(selected=bool*)` for radio buttons requires a
STABLE bool reference. The pointer is dereferenced every frame; if
the bool goes out of scope, you get a use-after-free crash. Use
file-local `bool kBoolTrue = true;` (never changes) and pass it
unconditionally; switch the *argument* (which theme the radio is
for), not the target.

```cpp
// WRONG — kRadioForDark is a local that goes out of scope:
if (ImGui::BeginMenu("Theme")) {
    bool kRadioForDark = (theme == 0);
    if (ImGui::MenuItem("Dark", nullptr, &kRadioForDark)) { theme = 0; }
    ImGui::EndMenu();
}

// RIGHT — stable file-local refs:
namespace { bool kBoolTrue = true; bool kBoolFalse = false; }
if (ImGui::BeginMenu("Theme")) {
    if (ImGui::MenuItem("Dark", nullptr, theme == 0 ? &kBoolTrue : &kBoolFalse)) {
        theme = 0; markSettingsDirty();
    }
    ImGui::EndMenu();
}
```

**Pitfall:** `ImGui_ImplVulkan_RenderDrawData` is camelCase with a
CAPITAL D in the post-2025-09-26 docking branch. Renaming to
`RenderDrawdata` (lowercase d) compiles in the TU that uses it but
fails at link time (undefined reference). Always grep BOTH the
declaration in `backends/imgui_impl_vulkan.h` AND the definition
when renaming API calls.

**Pitfall:** load persisted settings BEFORE `UIContext::initialize`,
not after. If init runs with the default theme and the second frame
mutates, Light-theme users see a one-frame dark flash. Order:

```
create_directories(parent)   ← fix for "0" file
Settings::load(path)         ← get theme + flags
uiContext.initialize(..., theme)   ← apply on first frame
WindowManager.pushBooleans(settings.showXxx)
```

The fix for the "0" file is also load-bearing here — without
`create_directories`, the loaded settings can't be saved later (same
silent-failure path).

## Docking pitfalls

### No DockSpace created

If `ImGuiConfigFlags_DockingEnable` is set but no `DockSpaceOverViewport()` is ever called, docking is enabled in the config but no dock space exists. Panels float at their default positions and can't be docked.

**Fix:** Call `DockSpaceOverViewport()` (or a manual `DockSpace()` inside a fullscreen host window) at the top of the render frame, before any panels render.

### Window name mismatch with DockBuilder

`DockBuilderDockWindow("Status", node)` only works if a panel calls `ImGui::Begin("Status...")`. ImGui matches on the display title (text before `###`). If your panel uses `title + "###panel_" + pointer`, the display title is just `title`. The DockBuilder name must match exactly.

```cpp
// Panel does:
std::string window_title = config_.title + "###panel_" + std::to_string(ptr);
ImGui::Begin(window_title.c_str(), ...);

// DockBuilder must use:
ImGui::DockBuilderDockWindow(config_.title.c_str(), node);  // "Status", not "Status###panel_..."
```

### `NoDocking` flag on the dock space host

The fullscreen host window that contains the `DockSpace` must have `ImGuiWindowFlags_NoDocking` so it can't be docked INTO itself (which would be a paradox). It can still be the parent of other dock nodes.

```cpp
constexpr ImGuiWindowFlags host_flags =
    ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse |
    ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
    ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus |
    ImGuiWindowFlags_NoBackground | ImGuiWindowFlags_NoDocking;
ImGui::Begin("##DockSpaceHost", nullptr, host_flags);
ImGui::DockSpace(dockspace_id, ImVec2(0, 0), ImGuiDockNodeFlags_PassthruCentralNode);
ImGui::End();
```

## Window flag pitfalls

### `NoDocking` on panels you want to dock

If a panel's `Begin()` call includes `ImGuiWindowFlags_NoDocking`, it will float permanently and ignore any dock layout. Check for this flag if docking "doesn't work" for a specific panel.

### `NoSavedSettings` + `FirstUseEver` conflict

`ImGuiCond_FirstUseEver` means "use this on first use, then save to ini". If the window also has `NoSavedSettings`, the position is never saved. This is usually intentional for overlays (performance monitor, debug info) but a bug for regular panels.

## Verifying a render is actually working

You can't see the GUI from the terminal, so verify rendering from the log:

1. **Count imgui-errors per run** — 0 is the target. More than a few dozen = real problem.
2. **Check for panel-specific init messages** — `[WatchlistPanel] Created new watchlist group: ...`
3. **Check data flow** — `Trade W=N Book W=M` should increment steadily
4. **Check for periodic render messages** — `[OrderbookPanel] Rendering. SymID=N ActiveSyms=20`
5. **Check for clean shutdown** — `Shutdown complete. Goodbye!` without Vulkan validation errors

If all five pass, the render is working. If imgui-errors are high, the widgets are not drawing correctly even if the log looks otherwise clean.

## References

- `references/pushid-popid-leak-watchlist.md` — the full diagnostic transcript from a real session
- `references/docking-host-window.md` — the exact host window pattern with flags
- `references/verification-checklist.md` — the 5-point log-based render check

## Attribution

Skill distilled from a real debugging session on the BTQuant trading terminal (C++/ImGui/Vulkan, June 2026). The PushID/PopID leak was a pre-existing bug that broke all panel rendering — 4283 errors in one run, corrupting every widget ID. The fix was a single missing `ImGui::PopID()` call.
