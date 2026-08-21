---
name: dayz-settings-widget-sync
description: "Pattern for syncing DayZ settings UI changes to actual HUD widgets in real-time, with JSON persistence"
triggers:
  - settings menu doesn't update widget
  - slider changes value but widget doesn't move
  - settings don't persist after restart
  - HUD position settings not working
---

# DayZ Settings ↔ Widget Sync Pattern

Problem: Settings UI changes (sliders, checkboxes) modify values internally but never reach the actual HUD widgets or persist.

## Root Cause
Settings UI and HUD widgets are decoupled — UI stores values locally but nothing bridges to the widget or JSON file.

## Solution: Central HUD Manager Singleton

All HUD state changes must flow through one manager that:
1. Holds `Widget` references to actual HUD elements (PlayerList, Minimap, Chat, Compass)
2. `SetWidgetPos(name, x, y)` — applies to widget live AND writes to settings struct
3. `SaveToFile()` — persists JSON after every change (not batched)
4. Widgets read initial state from saved settings on `Init()`

```c
class VPPHUDManager {
    private static ref VPPHUDManager s_Instance;
    private Widget m_PlayerListRoot;
    private Widget m_MinimapRoot;
    private Widget m_ChatRoot;

    static VPPHUDManager Get() {
        if (!s_Instance) s_Instance = new VPPHUDManager();
        return s_Instance;
    }

    void RegisterWidget(string name, Widget w) {
        if (name == "PlayerList") m_PlayerListRoot = w;
        else if (name == "Minimap") m_MinimapRoot = w;
        else if (name == "Chat") m_ChatRoot = w;
    }

    void SetWidgetPos(string name, float x, float y) {
        VPPClientSettings s = VPPClientManager.GetInstance().GetClientSettings();
        Widget w;
        if (name == "PlayerList") {
            s.pos_PlayerListX = x; s.pos_PlayerListY = y;
            w = m_PlayerListRoot;
        }
        // ... etc
        if (w) w.SetPos(x * 1000.0, y * 1000.0);
        VPPClientManager.GetInstance().SaveClientSettings();
    }
}
```

## Settings UI Integration

Override `OnChange` on sliders/editboxes to call the manager immediately:

```c
override bool OnChange(Widget w, int x, int y, bool finished) {
    if (w == sliderPX || w == sliderPY) {
        string elemName = "PlayerList"; // based on m_SelectedPos
        VPPHUDManager.Get().SetWidgetPos(elemName, sliderPX.GetCurrent(), sliderPY.GetCurrent());
        UpdatePositionPreview();
        return true;
    }
    return false;
}
```

Checkboxes (OnChanged) must also call manager for immediate visibility:
```c
if (chkCompass) { s.CompassEnabled = chkCompass.IsChecked(); VPPHUDManager.Get().SetCompassVisible(s.CompassEnabled); }
```

## Critical: No Widget Owns Its Own State
Widgets must NEVER store position/state independently. Always read from manager at init, always update through manager on change.

## DayZ Layout Crash Fixes

### Exact size overflow
`size 1104 25` with `hexactsize 1` causes engine crash on containers > screen width.
Fix: Use relative `size 1 25` with `hexactsize 0`.

### Texture path format
Layout files use backslash separators: `imageTexture "VanillaPPMap\\GUI\\Compass_slim.png"`
Must match actual file (`.png` not `.edds` unless EDDS file exists).
Always check `*.edds` files exist before referencing them.

### Widget not found crashes
`FindWidget()` returns null → crash at method call.
Always use `FindAnyWidget()` for name-based lookup, never `FindWidget()`.
Always null-check before calling methods on result.

### onChange per keystroke
DayZ fires `OnChanged` per keystroke on edit boxes, not on submit.
Guard with `if (finished)` for edit-box + slider sync to avoid infinite loops.
