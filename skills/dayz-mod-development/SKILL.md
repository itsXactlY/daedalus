---
name: dayz-mod-development
description: DayZ mod development — UI components, rendering, RPC, server config, admin panels, settings, and audit workflows
version: 1.0.0
category: gaming
tags: [dayz, mod-dev, ui, rpc, rendering, settings, admin, enforce-script]
---

# DayZ Mod Development — Skill Index

All substantive content lives in linked skills. This file is the index.

## UI Development
- `dayz-mod-ui-dev` — UI development methodology, component patterns, DayZ .layout specifics
- `dayz-lbmaster-admin-layout` — LBMaster admin panel widget structure (exact pixel layouts)
- `dayz-vppmap-settings-menu` — VPPMap full-screen settings menu implementation
- `vppmaps-sidebar-layout` — VPPMaps sidebar (440px constraint), 4-quadrant grid, server connect hooks

## Build & Deployment
- `dayz-pbo-build-deploy` — PBO build, pack, and deploy workflow (use positional args, NOT -P flag)
- `dayz-mod-merge-workflow` — Merging complementary DayZ mods (e.g., VPPMaps + VPPAdminTools)

## Script & Config
- `dayz-enforce-script` — Enforce Script syntax constraints and common pitfalls
- `dayz-enforce-script-fix-undefined-methods` — Fixing "undefined method" errors
- `dayz-rpc-communication` — Client-server RPC patterns using VPPRPCManager
- `dayz-server-config-system` — JSON-based server config system (admin lists, RPC, tier system)

## Debugging
- `dayz-layout-crash-debug` — SEH exceptions, font loading failures, layout file crashes
- `dayz-mod-ui-dev` — Crash-prevention patterns (Init/Show/Hide re-entrancy guards)

## Settings & Widget Sync
- `dayz-settings-widget-sync` — VPPHUDManager singleton for settings→widget sync with JS

## Quick Reference

### Build + Deploy (from mod dir)
```bash
cd ~/dayz/Steam/steamapps/common/DayZServer/@VPPMaps
makepbo -N -P 4_World 5_Mission
# Restart server
```

### Crash Debug Order
1. Check Enforce Script syntax errors (layout crashes cascade as "undefined function")
2. Check `FileExist()` on directory paths (unreliable — use file checks)
3. Check `SetPos()` uses pixel offsets, not relative values
4. Check `OnClientReadyEvent` override doesn't crash connections
5. Check `FindWidget` vs `FindAnyWidget` — plain widgets need `FindAnyWidget`
6. Check `hideall3dmarkers()` called for map menu (FPS)

### RPC Pattern
```c
// Server: Register
GetRPCManager().AddRPC("Category", "HandlerName", funccallback(this, "HandleFunction"));

// Client: Call
GetRPCManager().SendRPC("Category", "HandlerName", new Param1<Type>(value), true);
```

### Settings Widget Sync (VPPHUDManager)
```javascript
// Widget → Settings (JS)
settingsWidget.GetAsyncHint().Set(icon_index, value);
VPPHUDManager.Get(SettingsMenu).OnSettingChanged(icon_index, value);

// Settings → Widget (C++)
VPPHUDManager.Get(SettingsMenu).UpdateWidget(widget_id, value);
```

## Critical Pitfalls
1. **NEVER** use `-P` flag in `makepbo` — causes compiler errors
2. **NEVER** use `override` keyword on plain classes (Enforce Script compiler crashes)
3. **Method insertion** can break braces — always verify brace balance after insertion
4. **FileExist()** on directories is unreliable in DayZ — verify with actual file
5. **UIScriptedMenu** registration: `GetGame().GetWorkspace().CreateWidgets()` path must match layout file location
6. **PanelWidgetClass** vs plain **Widget** — layout files use plain Widget, script uses PanelWidgetClass
