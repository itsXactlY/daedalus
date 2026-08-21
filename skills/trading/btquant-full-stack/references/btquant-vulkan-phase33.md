---
name: btquant-vulkan-phase33
version: "1.0"
description: "NEW engine: Phase 33 — Theme menu wiring (Save current theme + Reset theme to default). m_defaultStyleSnap captured at ctor (ImGui::GetCurrentContext guard), resetThemeToDefault applies + persists, saveCurrentTheme also ImGui-guarded to prevent test SIGSEGV."
---

# Phase 33 — Theme menu plumbing (2026-06-20)

**Sprint count entering**: 22 commits / 23 widgets / 39 tests
**Sprint count exiting**:  23 commits / 23 widgets / 40 tests

## What landed

- `WindowManager::resetThemeToDefault()` — applies the snapshot captured at construction (`m_defaultStyleSnap`) and persists to `ThemeIO::defaultPath()`. The capture-at-ctor approach means the reset is deterministic regardless of how many times the user has mutated the theme since launch.
- `m_defaultStyleSnap = std::optional<ThemeEditor::Snapshot>` — new private-but-public-for-tests field, captured in the WM ctor when `ImGui::GetCurrentContext() != nullptr`. Nullopt in tests (no ImGui context).
- Two new View → Theme submenu items: "Save current theme" (calls existing `saveCurrentTheme()`) + "Reset theme to default" (calls new `resetThemeToDefault()`). Separated from the existing Dark/Light radio items by a horizontal rule so the lifecycle actions read as a separate group.
- `WindowManager::saveCurrentTheme()` now guards on `ImGui::GetCurrentContext() == nullptr` → return false. Without this, tests calling `saveCurrentTheme()` (e.g. for plumbing checks) segfaulted on the `ImGui::GetStyle()` call inside, because `m_themeEditor` is allocated in the ctor and the early-return only checked for null pointer, not for live context.

## Forward-decl resolution

- Was: `namespace btquant::ui { class ThemeEditor; }` inside the header → clang reports "incomplete type ThemeEditor named in nested name specifier" because the forward-decl creates a NEW class in that namespace, not a reference to the real one. Compiles to a different type, fails at every use site.
- Fix: `#include "../widgets/theme_editor.hpp"` in window_manager.hpp. The full type is needed because the member field uses `ThemeEditor::Snapshot` directly. Forward-decl would work for a `ThemeEditor*` member but not for `std::optional<ThemeEditor::Snapshot>`.

## Pitfalls

- **`m_defaultStyleSnap` is a `std::optional<ThemeEditor::Snapshot>` not a `Snapshot`**: tests construct `WindowManager` without a live ImGui ctx, so the capture fails. The optional makes that explicit; without it, a default-constructed `Snapshot` would be value-initialized and the ctor's "did capture succeed" check would lie.
- **ImGui-context guard pattern: 3 places now have it** — `applyInitialDockLayoutIfNeeded` (Phase 28), `applyPersistedTheme` (Phase 33, indirectly via `ThemeEditor::applySnapshot(ImGui::GetStyle(), ...)`), and `saveCurrentTheme` (Phase 33 fix). Pattern: guard is the FIRST line of the function (after any trivial early-outs) and the function returns a safe default. Zero cost in production (ImGui is always live when render runs).
- **Public field for testability instead of getter method** — `m_defaultStyleSnap` is public to match the established codebase pattern (`pendingDockLayout`, `m_heatmapMode`, `m_exportModalOpen`, `m_layoutResetRequested`, etc.). Tests assert `wm.m_defaultStyleSnap.has_value()` directly. Adding a `defaultStyleSnapshot()` getter would deviate from the existing style and force every other test in the file to use accessor style.
- **ThemeIO::save is already a `no_throw` path** but `applySnapshot` can throw if a future ImGui version starts raising on bad style data. Wrap the ctor capture in a try/catch if that ever happens; for now the snapshot is read-only from the live style and safe.
- **`saveCurrentTheme` was the only existing method that could segfault in tests** — caught on the first test run with exit 139 (`Speicherzugriffsfehler`). The defensive-guard pattern from Phase 28 paid off: when the same class of bug appeared, the fix was identical (one-line context check at the top). Now documented as a reusable pattern for ANY method that calls `ImGui::*` AND is exposed for tests.

## Test 40 — 4 invariants

- ctor left snapshot empty when no ImGui ctx (expected, tests don't init ImGui)
- `resetThemeToDefault()` with no snapshot → no-op (early return, no crash)
- `saveCurrentTheme()` without ImGui ctx → false (post-fix guard, no longer crashes)
- `resetThemeToDefault()` with snapshot populated but no ImGui ctx → no-op (second guard)

Total: 256 ✓ checks across 40 tests, 0 failures. 7 files changed, 274 insertions.
