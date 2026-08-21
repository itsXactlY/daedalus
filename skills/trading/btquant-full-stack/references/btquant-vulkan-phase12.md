---
name: btquant-vulkan-phase12
description: "BTQuant Vulkan Phase 12 — ProfileManager/SymbolPicker/ThemeEditor dialog widgets, Snapshot POD testability pattern, ImGui 1.90+ color count gotcha, 4-widget-per-turn rhythm under 'FRAG NICHT IMMER SO BEHINDERT'."
---

# Phase 12 — Dialog widgets + Theme customization

Session 2026-06-20 (continued). Closes several Phase 11 "Open / next" items
and adds a new dimension (live theme customization) that no prior phase
covered.

## What landed (in order, one commit each)

1. **ProfileManager** (`91d5be8f`) — ImGui window with 4-column table
   (Name / Modified / Size / Actions). Save-As text input + Save button.
   Per-row Load (calls `applyPreset()` + dock reset) + Delete. Reload
   button refreshes the directory scan. View → "Profile Manager…"
   menu item.

2. **SymbolPicker** (`1b4478a5`) — Modal popup with 12 default USDT
   pairs, substring filter (case-insensitive), scrollable list,
   click/Enter to select, ↑/↓ keyboard nav, Esc cancels. Wired with
   `SelectFn` callback (currently logs via BTQ_LOG_INFO; multi-symbol
   wireup would update MarketDataProcessor.symbol). **Ctrl+P hotkey**
   for open/close.

3. **ThemeEditor** (`7ca11591`) — Modal with 48-color picker grid + 4
   style sliders (WindowPadding/FramePadding/Rounding/Alpha). Reset
   to Dark / Reset to Light preset buttons. **Ctrl+T hotkey**.
   `Snapshot` POD (48 colors + 4 floats + dark flag) for Settings
   persistence.

Plus the RiskPanel metrics expansion (Phase 11, but exercised in this
session: Sharpe/maxDD/win rate/profit factor/expectancy with 7
invariants in Test 14).

## Pitfalls (new in this phase)

### #1: Widget plumbing 5-step recipe is the same as Phase 10, with two additions

Phase 10's recipe (`references/btquant-vulkan-phase10.md` #1) holds.
This phase added two refinements that future widget adders should
follow:

- **Singleton widget dtor trap** (already in Phase 10 #6): check
  `m_X = &X::instance();` in ctor → do NOT add `delete m_X;` to the
  WM dtor. LogPanel and (future) any cross-cutting singleton falls
  into this category.
- **Push-only vs setMarketData split** (already in Phase 11): widgets
  driven by the main loop calling `updateWatchlist(sym, price, ...)`
  don't need `setMarketData()` — they pull from the WM directly. Only
  widgets that read from `MarketDataProcessor::snapshot()` need the
  setter hook. ConnectionPanel needs it (reads seq/path/latency);
  SymbolPicker doesn't (purely UI).

For SymbolPicker specifically: the SelectFn fires on click/Enter
inside the popup. When the picker is opened via Ctrl+P, the modal
needs to reset state on close (filter buffer, selected index). The
`firstAppear = true` static + `memset(m_input)` on close pattern in
the SymbolPicker.cpp is the recipe for this.

### #2: `ImGui::ColorEdit4` inline color picker pattern

For a multi-color editor grid (32 or 48 rows), the compact form is:

```cpp
for (int i = 0; i < kColorCount; ++i) {
    ImGui::TableNextRow();
    ImGui::TableNextColumn();
    ImGui::TextUnformatted(colorName(i));
    ImGui::TableNextColumn();
    ImGui::PushID(i);
    ImGui::ColorEdit4("##c", &style.Colors[i].x,
                      ImGuiColorEditFlags_AlphaBar |
                      ImGuiColorEditFlags_NoInputs |
                      ImGuiColorEditFlags_NoLabel);
    ImGui::PopID();
}
```

Three flags matter:
- `AlphaBar` — shows the alpha channel as a horizontal bar in the
  swatch
- `NoInputs` — kills the RGBA numeric inputs (would eat horizontal
  space)
- `NoLabel` — no "(R=255, G=..., A=...)" text trailing the swatch

`PushID(i)` per row gives the editor stable state across frames
without conflicts with other ColorEdit4 widgets on the same screen.

### #3: `ImGuiCol_COUNT` is 48 in ImGui 1.90+, NOT 32

When a hardcoded 32-slot array is the basis for "all the ImGui
colors", the 16 newer colors (DockingPreview, DockingEmptyBg,
TableRowBg, TableRowBgAlt, TextLink, TreeLines, DragDropTargetBg,
UnsavedMarker, NavCursor, NavWindowingHighlight, NavWindowingDimBg,
plus Tab/TabHovered renames) silently drop out of round-trips.

Symptom: `colorName(i)` returns `"?"` for `i >= 32` because the
switch has no case for it. Test loop iterates over the real range
and the assertion fires.

Fix:
1. Bump `kColorCount` to 48 (or use `IM_ARRAYSIZE` of a named list).
2. Add an auto-fallback formatter for unknown indices:
   ```cpp
   default: {
       static thread_local char buf[24];
       std::snprintf(buf, sizeof(buf), "Color[%d]", i);
       return buf;
   }
   ```
3. Add named cases for the new colors.

Check the live ImGui header for the current count — this WILL change
in future releases. On 2026-06-20 the value was 48, defined at the
end of the `ImGuiCol_*` enum in `imgui.h`.

### #4: `std::array<T,N>` member is NOT value-initialized on default ctor

A struct like:

```cpp
struct Snapshot {
    std::array<float, 4> colors[32];
    float windowPadding = 8.0f;
    // ...
};
```

Has UNINITIALIZED `colors[i][k]` for all i,k after `Snapshot s;`. Only
the primitive members with `= X` initializers are zero/their-default.

Tests that expect fresh `Snapshot{}` to have `colors[5][0] == 0.0f`
will see garbage and fail with non-deterministic values.

Fix: explicit member initializer `= {}`:

```cpp
struct Snapshot {
    std::array<float, 4> colors[48] = {};  // zero-init
    // ...
};
```

Or `Snapshot s{};` at the call site (but the member-initializer is
less error-prone — no caller has to remember the brace syntax).

### #5: Testable ImGui-style widget pattern (capture/apply/equals trio)

When a widget has meaningful `ImGuiStyle` state but you want headless
tests (no ImGui context available), expose the state as a POD Snapshot
and three static helpers:

```cpp
class ThemeEditor {
public:
    struct Snapshot {
        std::array<float, 4> colors[48] = {};
        float windowPadding = 8.0f;
        float framePadding  = 4.0f;
        float rounding      = 0.0f;
        float alpha         = 1.0f;
        bool  dark          = true;
    };

    static void     applySnapshot(ImGuiStyle& dst, const Snapshot& s);
    static Snapshot capture(const ImGuiStyle& src);
    static bool     equals(const Snapshot& a, const Snapshot& b,
                           float tol = 1e-4f);
};
```

Tests construct `Snapshot s;`, mutate one field (e.g.
`s.colors[5][0] = 0.5f;`), verify:

```cpp
ThemeEditor::Snapshot s2 = s;
assert(ThemeEditor::equals(s, s2));      // identical
s2.rounding = 3.5f;
assert(!ThemeEditor::equals(s, s2));    // catches drift
```

The live `render()` path is never exercised by tests — only the POD
invariants are. This is the same pattern as the `Settings` capture/
apply in Phase 5, but at the widget level rather than the WM level.

The triad is small enough (capture = 8 lines, apply = 8 lines,
equals = 12 lines) that it should be the default for any widget with
non-trivial state.

## Workflow: "FRAG NICHT IMMER SO BEHINDERT: WEITER!" — accelerated pace

This session's most distinctive feature was the user's repeated
"FRAG NICHT IMMER SO BEHINDERT: WEITER!" (4 times in a single
session). The trigger fired and stayed fired — every "weiter" turn
afterwards shipped a complete widget (build + test + commit + report)
in one shot, no clarifying questions.

**Resulting rhythm:**

- 1 widget per turn at minimum
- 2 widgets per turn is normal (with the 5-step plumbing recipe)
- 4 widgets per turn (ProfileManager + SymbolPicker + ThemeEditor +
  Metrics, this session) is achievable when the user has set the
  trigger and the widget shape is mechanical

**Operational changes vs the Phase 10 baseline:**

| Phase 10 baseline | Phase 12 (after trigger) |
|---|---|
| End turn with "WEITER." + commit SHA + 3-5 line summary | Same |
| Numbered menu offered as last visible content: borderline | Numbered menu after trigger: HARD FAIL |
| Ask "Soll ich X oder Y?" after a list: borderline | Same question after trigger: HARD FAIL |
| Per-widget code lines: ~80-150 | Same (no shortcut; the recipe still takes time) |
| Per-widget tool calls: 5-8 (write files, patch WM, build, test, commit) | Same |
| Memory save per turn: 1 (commit summary) | Same (id 824555, 558, 560, 564, 581 — one per turn) |

The trigger does NOT shorten the per-widget work. It just removes the
"now what?" dead air between widgets. Each widget still gets its full
plumbing (write files, patch WM, update CMakeLists twice, add test,
build, run tests, commit). The acceleration is purely in removing the
decision overhead between commits.

## Open / next (Phase 13 candidate)

- SymbolPicker → MarketDataProcessor wireup (requires
  `MarketDataProcessor::setSymbol(s)` + restart loop)
- ThemeEditor → Settings persistence (auto-save on close path) —
  Snapshot is already POD, just need to extend `Settings` with a
  snapshot field + load/save serialization
- Port remaining BTQ_Render_Engine panels: `chart_panel.cpp` (5167
  lines, biggest single file), `watchlist_panel.cpp` (3696 lines).
  These are large ports; budget ~2-3 widgets per port
- ImGui theme customizer for the LIVE running style (ThemeEditor
  currently only mutates the ImGuiStyle — needs to call
  `ImGui::StyleColorsDark/Light` when the user clicks those buttons;
  verify this works in the running app, not just on a fresh style)
- Hotkey customization (user-mappable keys → menu items)
- Order-entry widget stub (placeholder stub + integration with
  order router — depends on external)
- JSON config export for layout profiles (`.btqlayout` format) —
  currently INI; a JSON export would let users share layouts with
  `jq`/shell tools