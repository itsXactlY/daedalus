---
name: dayz-lbmaster-admin-layout
description: LBmaster admin panel layout - shell vs pages, widget properties, colors
category: dayz-mod-development
tags: [dayz, lbmaster, admin, layout, gui]
---

# DayZ LBmaster Admin Layout

## Shell vs Page Separation
Shell (VPPGlobalAdminDashboard): bg 0.506 0.506 0.506 0.392
Pages: flat PanelWidgetClass loaded into pageWidgets. FLAT - no nesting.

## 4-Quadrant Pattern
position 0/0.51, size 0.49 0.46, style LB_Clean_outline. Header: 1 0.6 0.1 1 (amber).

## Close-Button Wiring
Parent passes layoutRoot via Init(root, parentRoot). Child: parentRoot.FindAnyWidget().

## Widget Cheat Sheet
Headers: sdf_MetronBook72, white. Labels: gray 0.8 0.8 0.8 1, right-aligned.
Checkboxes: hexactpos 1, hexactsize 1. Sliders: 1 0.5 0 1, fill in 1.
Close: red 1 0.196 0.196 1. Save: green 0 1 0 1.

## Anti-Patterns
1. Nesting FrameWidgetClass (use flat PanelWidgetClass)
2. Wrong font (sdf_Metron* doesn't exist - use Chat/PuristaMedium/PuristaBold)
3. Missing hexactpos/hexactsize
4. Mixing relative/absolute positioning
5. LBmaster script classes for static panels