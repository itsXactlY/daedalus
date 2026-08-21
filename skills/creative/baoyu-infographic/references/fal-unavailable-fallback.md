# FAL Unavailable Fallback — HTML-to-PNG via Playwright

When `image_generate` fails due to missing FAL_KEY, use Playwright to convert the HTML infographic to PNG.

## Prerequisites
- Node.js + npm installed
- Playwright installed: `npm install -g playwright` (or `npx playwright` without install)

## One-Liner Capture (tested 2026-06-13)

```bash
npx playwright screenshot \
  --viewport-size=1920,1080 \
  /path/to/infographic.html \
  /path/to/output.png
```

## Full Pattern Used for Mazemaker

1. Generated `infographic.html` with embedded CSS (no external dependencies)
2. Used `npx playwright install chromium` first (if not cached)
3. Ran screenshot command → 253KB PNG in ~20 seconds

## Constraints

- Works best with self-contained HTML (embedded CSS)
- Viewport size must match design intent
- Requires network access for browser download (one-time)
- Produces faithful render matching style guide (pop-laboratory, etc.)

## Why This Works

- FAL needs paid credits/credit card
- HuggingFace inference API timed out for large prompts
- Playwright gives deterministic, high-fidelity output
- No base64 encoding/decoding overhead