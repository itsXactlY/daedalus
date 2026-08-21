---
name: btquant-vulkan-phase13
description: Theme persistence — ThemeIO loads/saves ThemeEditor::Snapshot to ~/.config/btquant_vulkan/theme.ini with auto-apply on startup and live "Save to disk" button. Pitfall: digit-based separators in INI keys are ambiguous for 2-digit indices.
---

# Phase 13 — Theme Persistence (ThemeIO)

## Scope

Phase 12 left ThemeEditor as a live in-memory color/style editor with a
Snapshot POD for testability. Phase 13 closes the loop: persist the
Snapshot to disk, auto-apply on startup, expose a manual "Save to disk"
button in the modal.

## Files

- `src/util/theme_io.{hpp,cpp}` — `btquant::ui::ThemeIO` static class
- `src/widgets/theme_editor.cpp` — adds "Save to disk" button to modal
- `src/ui/window_manager.cpp` — `applyPersistedTheme()` called from
  `initialize()`, `saveCurrentTheme()` exposed for explicit calls
- `src/util/theme_io.cpp` — INI format + load/save

## API

```cpp
namespace btquant::ui {
class ThemeIO {
public:
    static std::filesystem::path defaultPath();
        // ~/.config/btquant_vulkan/theme.ini (respects BTQUANT_CONFIG +
        // XDG_CONFIG_HOME)

    static std::optional<ThemeEditor::Snapshot> load(path);
        // nullopt on missing file; malformed lines silently skipped

    static bool save(path, const Snapshot&);
        // atomic: tmp + rename; creates parent dirs
};
}
```

## Format

```
# btquant_vulkan theme snapshot — auto-generated
c<i>.<k>=<float>      # 192 lines (i in 0..47, k in 0..3)
windowPadding=<float>
framePadding=<float>
rounding=<float>
alpha=<float>
dark=0|1
```

The single-letter `c` prefix plus a `.` separator make the index parse
unambiguous. See the "2-digit index ambiguity" pitfall below.

## Wire-up

```cpp
// WindowManager::initialize() — load + apply on startup
void WindowManager::initialize() {
    m_initialized = true;
    applyPersistedTheme();   // BTQ_LOG_INFO on success / "no persisted theme"
}

void WindowManager::applyPersistedTheme() {
    if (!m_themeEditor) return;
    auto snap = ThemeIO::load(ThemeIO::defaultPath());
    if (!snap) return;
    ThemeEditor::applySnapshot(ImGui::GetStyle(), *snap);
}

// "Save to disk" button in ThemeEditor modal
if (ImGui::Button("Save to disk")) {
    ThemeIO::save(ThemeIO::defaultPath(),
                  ThemeEditor::capture(ImGui::GetStyle()));
}
```

## Pitfalls

### 1. 2-digit index ambiguity in INI keys — DO NOT use underscore separators

`themeColor_<idx>_<ch>` is **unambiguous only when `<idx>` is a single
digit**. For 2-digit indices, the parser that uses `rfind('_')` and
takes `substr(lastUs - 12)` ends up with the LAST DIGIT ONLY of the
index, not the full number. Symptom: `themeColor_40_0=1.600000` is
parsed as `colors[0][0] = 1.6`, not `colors[40][0] = 1.6`. Round-trip
test fails with values systematically shifted.

Fix: use a non-digit separator. `c<i>.<k>=<float>` works because the
period can never be confused with an integer. Same applies to any
INI/JSON-like config where index digits can exceed 9.

Other safe options:
- fixed-width zero-padded: `c<i:02d>.<k:02d>=<float>`
- different prefix per axis: `c<i>d<k>=<float>`

### 2. Default-init `std::array` in Snapshot struct

`struct Snapshot { std::array<float, 4> colors[48]; ... };` leaves the
colors UNINITIALIZED when default-constructed (`Snapshot s;`). Use
member-init `std::array<float, 4> colors[48] = {};` so default-constructed
snapshots have all-zero colors. Tests that check `colors[i][k] == 0`
on a fresh snapshot rely on this.

### 3. `applyPersistedTheme` must run AFTER ImGui context exists

`ImGui::GetStyle()` only returns a valid reference after
`UIContext::initialize()`. If `WindowManager::initialize()` runs before
the UI context is up, `applyPersistedTheme()` reads garbage. Order:
`uiContext.initialize()` → `windowManager.initialize()` (which calls
`applyPersistedTheme()`).

### 4. `defaultPath()` must match `Settings::defaultPath()` resolution

Same env-var precedence: `BTQUANT_CONFIG` > `XDG_CONFIG_HOME` > `$HOME`.
If Settings uses one resolution and ThemeIO uses another, the two
files end up in different dirs and the theme applies but the user's
widget toggles don't. Read both files to confirm during smoke.

### 5. Test isolation: write to a tmp file, not `defaultPath()`

Tests must NOT overwrite the user's actual `theme.ini`. Always pass
an explicit `fs::temp_directory_path() / "btquant_test_theme.ini"` to
`load()` and `save()`. The default-arg-free API supports this.

## Test pattern

```cpp
ThemeEditor::Snapshot orig{};
for (int i = 0; i < ThemeEditor::kColorCount; ++i)
    for (int k = 0; k < 4; ++k)
        orig.colors[i][k] = static_cast<float>(i * 4 + k) / 100.0f;
orig.windowPadding = 11.5f;
// ... more fields

ThemeIO::save(tmpFile, orig);
auto loaded = ThemeIO::load(tmpFile);
assert(loaded.has_value());
assert(ThemeEditor::equals(orig, *loaded));   // 1e-4 tolerance

// Malformed-file recovery
std::ofstream bad(tmpFile, std::ios::trunc);
bad << "not_a_valid_key=foo\n";
bad << "c3.1=0.7\n";          // valid
bad << "alpha=0.55\n";         // valid
bad << "### corrupted data ###\n";
auto partial = ThemeIO::load(tmpFile);
assert(partial.has_value());                  // did NOT bail
assert(std::abs(partial->alpha - 0.55f) < 1e-3);
assert(std::abs(partial->colors[3][1] - 0.7f) < 1e-3);
```

## Lessons carried forward

- **Test data ordering**: tests must construct deterministic
  fingerprints per slot (e.g. `i*4+k`) so equality failures pinpoint
  the exact slot. Random or zero data hides index-parsing bugs.
- **Diagnostic dumps**: when a round-trip fails, dump the file's
  first few lines to stdout and print the drifted `(orig, loaded)`
  pair with the index. Saves an entire cycle of "add prints, rebuild,
  rerun, squint, repeat".
- **Format-design rule for any future INI writer**: prefer a single
  letter prefix + non-digit separator (`a.b=`, `c.d=`) for keys that
  index arrays. Underscore-as-separator is fine when every dimension
  is a fixed-width zero-padded integer, but NEVER for free-form
  decimal indices.