---
name: dayz-vppmap-settings-menu
description: VPPMap full-screen settings menu implementation using LBMenuPopulator, UIControllerExtension, and server-authoritative persistence
category: dayz-mod-development
---

# DayZ VPPMap Settings Menu

## Architecture Overview

The settings menu is a full-screen UIControllerExtension with a 4-quadrant layout, following the LBmaster `page_3_0` pattern.

## UI Structure

### 4-Quadrant Layout (LBmaster page_3_0 Pattern)

Each quadrant uses size `0.49 0.46`:
```
+-----------+-----------+
|           |           |
|  Quad 1   |  Quad 2   |
|           |           |
+-----------+-----------+
|           |           |
|  Quad 3   |  Quad 4   |
|           |           |
+-----------+-----------+
```

### Settings Panel Widget Patterns

Each settings panel contains:
- **Titles** - section headers
- **Sliders + Edit Boxes** - paired value controls
- **Reset Buttons** - restore defaults per section

## LBMenuPopulator Pattern

Use LBMenuPopulator to dynamically build menu items from configuration data.

## Input Flow Architecture

### Full Chain + Controller Check Pattern

1. Input event fires
2. Check which controller owns the input
3. Route to appropriate handler
4. Process and update state

### Global Actions + Inventory Blocks

- Define global action bindings for menu navigation
- Block inventory input while settings menu is open
- Ensure clean input state transitions

## Settings Persistence

### Server-Authoritative Settings

**VPPClientSettingsManager** handles:
- **Validate** - check incoming values are within bounds
- **Cache** - keep active settings in memory
- **Persist** - write per-player JSON to disk

### Per-Player JSON Storage
```
$profile:VPPSettings/<player_id>.json
```

## OnChange Event Handling

### Critical: Fires Per Keystroke

The `OnChange` callback fires on EVERY keystroke, not just on commit.

**WRONG (fires constantly):**
```c
void OnChange(string value) {
    ApplySetting(value);  // Applied on every keystroke
}
```

**CORRECT (guard with finished):**
```c
void OnChange(string value, bool finished) {
    if (finished) {
        ApplySetting(value);  // Only applied on commit
    }
}
```

## Live Preview vs Save Button Pattern

- **Live Preview:** Apply visual changes immediately (cosmetic only, not persisted)
- **Save Button:** Persist settings to server JSON
- **Cancel:** Revert to last saved state
- **Reset:** Restore defaults

## Pitfalls

### JsonLoadFile Parameters
- Must provide correct parameter count
- Wrong params causes silent failure

### NULL Player from BBP
- BBP (Base Building Plus) can return NULL player references
- Always null-check player before accessing settings
- Handle gracefully - don't crash the menu

### Enforce Script Constraints
- See enforce-script-syntax skill for language limitations
- NO switch statements, use if/else
- NO ternary operators
- NO object literals

## Example Settings Flow

1. Player opens settings menu
2. UIControllerExtension loads with current values from VPPClientSettingsManager cache
3. Player adjusts sliders (live preview applies visual changes)
4. OnChange guarded by `if (finished)` for commit-only actions
5. Player clicks Save
6. Settings sent to server via ScriptRPC
7. Server validates and persists to per-player JSON
8. Server acknowledges to client
