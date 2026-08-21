# Keyword Shortcut System — Field Notes

The baoyu-infographic skill includes a **Keyword Shortcuts** table that auto-selects layout + style + aspect based on user input keywords. This worked well in practice.

## Trigger Keywords Tested

| User Input | Auto-Selected Layout | Auto-Selected Style | Aspect | Result |
|------------|---------------------|---------------------|--------|--------|
| "high-density-info" / "고밀도정보대그림" / mazemaker technical overview | `dense-modules` | `pop-laboratory` (primary) | portrait (9:16) | ✓ Perfect match for data-rich technical system |
| "infographic" / "信息图" | `bento-grid` | `craft-handmade` | landscape | Not tested this session |

## Why dense-modules + pop-laboratory Works for Mazemaker

Mazemaker is a **high-density technical system** with:
- 15+ live corpus metrics (204K memories, 39K dreams, 138M strengthened connections)
- 7-phase dream engine with per-phase metrics
- 9-channel recall architecture with weights
- 4-container pod architecture with security details
- 70+ skills across 6 categories
- PULSE 22-source recursive research
- Federation mesh topology

The `dense-modules` layout's design principles match perfectly:
- "6-7 distinct modules per image, each serving a specific information function"
- "Every module contains concrete data: brand names, numbers, percentages, parameters"
- "Coordinate-labeled variant: precision and systematicity — each module has alphanumeric coordinate (A-01, B-05, C-12), ruler/axis markers"

The `pop-laboratory` style's aesthetic matches:
- "Lab manual precision meets pop art color impact — coordinate systems, technical diagrams, fluorescent accents on blueprint grid"
- "Coordinate-style labels on every module (e.g., R-20, G-02, SEC-08)"
- "Technical diagrams: exploded views, cross-sections with anchor points"
- "Strictly systematic color usage: only teal, pink, yellow, charcoal"

## Workflow Notes

1. **Keyword match triggers auto-selection** — no need for Step 3 layout inference
2. **Step 3 still runs** — presents the auto-selected combo as top recommendation with rationale
3. **Step 4 (clarify)** — user confirms or overrides; timeout defaults to auto-selection
4. **Aspect ratio** — portrait is default for dense-modules per keyword shortcut table

## Pitfalls

- If user input contains multiple matching keywords, first match wins (table order)
- "infographic" keyword maps to bento-grid + craft-handmade — very different aesthetic
- For maximum density technical content, explicitly use "high-density-info" or "고밀도정보대그림"