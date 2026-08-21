# PushID/PopID Leak in WatchlistPanel — Full Diagnostic

## Symptom

User reports: "nothing of the visuals working correctly, no candles, nothing. a chunk of crap."

The terminal starts, the producer streams data, the log shows "HotSpineDataBridge Connected to SHM", OrderbookPanel "Auto-selected: BTCUSDT (ID=1), ActiveSyms=20". Everything looks correct in the log. But on screen, the panels are blank or broken.

## The diagnostic step nobody skips

Run the terminal, let it run for ~30 seconds, then:

```bash
grep -c "imgui-error" /tmp/btq_terminal.log
```

If the count is in the hundreds or thousands, the ID stack is being corrupted every frame. That's the root cause.

## What the error messages look like

```
[00879] [imgui-error] (current settings: Assert=1, Log=1, Tooltip=1)
[00879] [imgui-error] In window 'Watchlist###panel_94255314085920': Mismatching PushID/PopID!
[00879] [imgui-error] In window 'Watchlist###panel_94255314085920': Missing PopID()!
```

The window name in the error tells you which file to look at. The pattern is consistent: the same window name appears thousands of times.

## The bug

In `watchlist_panel.cpp`, the per-row render loop (around line 1200-2130) has:

```cpp
for (const auto& [symbol_id, entry] : get_current_watchlist()) {
    // Column 0: Symbol — has its own PushID
    ImGui::PushID(static_cast<int>(entry.symbol_id));  // ← PUSH #1
    if (ImGui::Selectable(entry.symbol.c_str(), ...)) { ... }
    // ... drag-and-drop source/target ...
    
    // Column 10: Action — has its own PushID
    if (column_info_[10].visible) {
        ImGui::PushID(static_cast<int>(entry.symbol_id));  // ← PUSH #2
        // ... delete button + context menu popup ...
        ImGui::EndPopup();
    }
    
    ImGui::PopID();  // ← only ONE PopID for TWO PushIDs
}
```

Every row pushes 2 IDs and pops 1. After rendering N rows, the ID stack is N deep. After ~500 rows (rendered at ~60fps), the stack is 30,000 deep. At that point, ImGui's internal ID hashing overflows or wraps, and **every subsequent widget ID in the entire application is wrong**.

The fix is one line: add a second `PopID()` before the existing one.

```cpp
    ImGui::EndPopup();
}

ImGui::PopID();  // matches second PushID (column 10)
ImGui::PopID();  // matches first PushID (column 0)
```

## Why the 100-iteration code review missed it

The bug was tagged with the comment "Fix ID conflict" on the first PushID — the developer who wrote it knew there was an ID conflict and tried to fix it with PushID. But they only counted one of the two PushIDs when adding the PopID. This is a common mistake: PushIDs inside conditional branches (`if (column_info_[10].visible)`) are easy to miss when counting at the end of a loop.

## Verification

After the fix:
- `grep -c "imgui-error" /tmp/btq_terminal.log` → 0
- Terminal renders all panels correctly
- Widgets are interactive (click targets are correct)
- ID stack stays at depth 1 regardless of how many rows are rendered

## How to prevent this in code review

1. **Every `for` loop with PushIDs gets a PopID count check.** The number of PushIDs inside the loop body must equal the number of PopIDs at the end of the loop body, not the number at the end of the enclosing function.

2. **PushIDs inside `if` branches are a smell.** If you have `if (visible) { PushID(); ... }`, the matching PopID is conditional too. Consider whether the PushID should be unconditional (outside the if) so the pairing is obvious.

3. **Lint rule idea:** A static analyzer could match PushID/PopID calls within loop bodies and count them. ImGui doesn't have this out of the box, but a custom clang-tidy check is feasible.

## Related patterns

- `Begin()/End()` imbalance causes "Missing End()" errors, not PushID errors
- `TreePush()/TreePop()` imbalance causes similar ID stack growth but with different symptoms
- `BeginGroup()/EndGroup()` imbalance affects layout, not IDs
