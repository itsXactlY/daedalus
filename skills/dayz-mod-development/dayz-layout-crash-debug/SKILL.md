---
name: dayz-layout-crash-debug
description: Debugging DayZ layout file crashes - SEH exceptions, font issues, hexactsize overflow
category: dayz-mod-development
tags: [dayz, layout, crash, debug, seh, font, hexactsize]
---

# DayZ Layout Crash Debugging

**Trigger**: DayZ crashes with `SEH exception 0x80000101` in `CreateWidgets()` or during widget init, especially when layout braces appear balanced.

## Diagnosis Steps

1. **Check binary layout file** — read as bytes, check for BOM, null bytes, encoding issues
2. **Verify braces match** — `{` count must equal `}` count
3. **Check `size` + `hexactsize` pairs** — the #1 hidden cause of crashes:
   - `hexactsize 1` means EXACT PIXEL size — value is in pixels, not relative 0-1
   - Large pixel values (e.g., `size 1104 25`) with `hexactsize 1` can overflow the parent container and crash `CreateWidgets`
   - **Fix**: Either reduce the pixel value to screen width (≤980 for typical 1080p), OR change to `hexactsize 0` + `size 1 25` (relative width)
4. **Check `hexactpos`** — same principle, exact pixel positioning can place widgets off-screen

## Common Pitfalls

| Pattern | Problem | Fix |
|---------|---------|-----|
| `size 1104 25 hexactsize 1` | 1104px wide exceeds container | `size 1 25 hexactsize 0` |
| `size 1920 1080 hexactsize 1` | Full screen exact pixels | `size 1 1 hexactsize 0` |
| `.edds` referenced but only `.png` exists | Missing texture file | Change path to actual format |
| Non-existent font in `font` attribute | Crash on widget init | Replace with valid DayZ font |
| Brace count mismatch | Structural corruption | Rebuild from backup |

## Font-Related Crashes

Non-existent fonts cause **SEH exception 0x80000101** on startup when the engine tries to create text widgets. Common culprits from VPPAdminTools/other mods:

| Bad Font | DayZ Replacement |
|----------|-----------------|
| `gui/fonts/sdf_MetronBook72` | `gui/fonts/Chat` |
| `gui/fonts/sdf_MetronLight24` | `gui/fonts/PuristaMedium` |
| `gui/fonts/sdf_MetronBold16` | `gui/fonts/PuristaBold` |

**Scan command**: `grep -r "sdf_Metron" GUI/Layouts/` then bulk-replace with sed or script. These fonts are from VPPAdminTools - if that mod isn't loaded, the references break.

## Key Insight

A layout file can be **structurally valid** (braces balanced, no corruption) but still crash the engine if **pixel dimensions exceed container bounds** or **referenced textures don't exist**. Always verify `hexactsize` values against screen dimensions and texture file existence.