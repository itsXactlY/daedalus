---
name: vppmaps-sidebar-layout
description: VPPMaps sidebar layout trap - 440px sidebar vs full-screen sizing
category: dayz-mod-development
version: 1.0
tags: [dayz, vppmaps, layout, sidebar, lbmaster]
---

# VPPMaps Sidebar Layout

## The Trap
Layouts go into a 440px sidebar, NOT full-screen. If you size for 1920px it BREAKS.

## Container Hierarchy
Sidebar_Root -> Sidebar_Content -> panel_settings_root
Sub-panels load dynamically into sidebar containers (LBmaster pageWidgets pattern)

## Sidebar Sizing (440px total)
Q1: (5, 35) 204x345 | Q2: (219, 35) 204x345
Q3: (5, 390) 204x345 | Q4: (219, 390) 204x345
Sliders: 150px wide. Checkboxes: 194px wide. Buttons: 62px each. 10px gaps.

## Full-Screen Alternative
Move panel_settings_root to ROOT level with size 1 1, priority 800.

## Server Connect
Timer-based (12s delay). WARNING: OnClientReadyEvent override CRASHES connections.

## Pitfalls
- All-or-nothing exact pixel sizing: if parent exact, ALL children must be exact
- Mixing relative/absolute -> unpredictable rendering
- LBMenuPopulator/LBGapHandler are for dynamic layouts only
- .edds referenced but only .png exists -> CreateWidgets() crash