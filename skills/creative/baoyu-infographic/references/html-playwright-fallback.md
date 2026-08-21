# HTML + Playwright Fallback Workflow

Use this when `image_generate` fails due to missing `FAL_KEY` or unavailable credits.

## Why This Works

- HTML/CSS gives deterministic vector-like output with perfect text rendering
- Playwright screenshots render exactly what's in the browser, no AI image model hallucination
- Works offline once Playwright is installed
- Output is editable — fix layout issues by editing HTML, not re-prompting

## Commands

```bash
# Install Playwright if needed (one-time)
npx playwright install chromium

# Render HTML to PNG
npx playwright screenshot --viewport-size=1920,1080 infographic.html infographic.png
```

## Verification Checklist

After rendering, check:
1. File size > 100KB (indicates actual content, not blank output)
2. Dimensions match viewport (`file infographic.png` should show 1920×1080)
3. Text is readable — zoom to 100% and inspect
4. No overlapping elements
5. Labels are correct (not mangled by CSS positioning)

## Common Fixes

| Issue | Fix |
|-------|-----|
| Text cramped | Increase canvas to 2560×1440 or 3200×1800 |
| Labels clipped | Add padding inside sections, reduce font size |
| Elements overlapping | Switch from radial to bento-grid or linear-progression layout |
| Center text wrong | Verify in browser before screenshot, check CSS z-index |
| Mangled labels | Use absolute positioning with explicit pixel coordinates |

## Quality Control Pattern

If the first render has quality issues:
1. Spawn 2-3 subagents with different layout approaches (radial, bento-grid, linear-progression)
2. Each creates HTML + renders to PNG independently
3. User picks the best one
4. Clean up the losers

This is faster than iterative manual fixing when the layout concept itself is wrong.