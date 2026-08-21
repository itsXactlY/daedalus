---
name: dayz-mod-ui-dev
description: DayZ UI development patterns - rendering, widgets, build-debug loop
category: dayz-mod-development
version: 1.0
tags: [dayz, ui, widget, rendering, debug]
---

# DayZ UI Development

## UIScriptedMenu vs Plain Widget
- UIScriptedMenu: for open/close menus. USE `override` keyword.
- Plain widget: for always-visible HUD. NO `override` keyword.
- NEVER MIX THEM.

## VPPHUDManager Plain Widget Pattern
Full lifecycle: Init/Update/Show with VPPHUDManager registration and MissionGameplay integration.

## Layout Properties
- `hexactpos`/`vexactpos`/`hexactsize`/`vexactsize` on ALL widgets
- Without them, layout collapses

## Build-Debug Loop
Check logs when build script exec-s the server.

## Method Insertion
Brace breakage causes "Broken expression (missing ';'?)". Be precise when editing.

## HideAll3dMarkers
Map menu needs `HideAll3dMarkers()` in `OnShow()` to prevent 3D marker overlay.

## Fonts
- `sdf_Metron*` don't exist outside VPPAdminTools
- Use `Chat`/`PuristaMedium`/`PuristaBold` instead
- Layout textures: forward slashes

## VPPMaps Layout
- `size 1 1` root for VPPMaps
- LBmaster 2x2 quadrant: `0.49 0.46`
- VPPAdminTools `GetPermissionManager()` returns NULL - fallback admin checks needed