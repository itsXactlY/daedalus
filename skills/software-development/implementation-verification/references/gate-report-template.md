---
title: Gate Report Template
description: Structured template for implementation verification gate reports
---

# GATE-REPORT.md — {Project} Gate Verification

**Date:** {YYYY-MM-DD}
**Worktree:** `{path}`
**Branch:** `{branch}`
**Commit (HEAD):** `{sha}`
**Server:** `{server-command}` (real background process, PID {pid})
**Browser:** Hermes browser tools only (`browser_navigate`, `browser_console`, `browser_vision`, `browser_snapshot`)

---

## 1. Static Verification

### 1.1 JS Syntax (`node --check`)

All served JavaScript files pass syntax checks:

| File | Result |
|------|--------|
| `assets/{file}.js` | PASS/FAIL |
| `support.js` | PASS/FAIL |

No syntax errors. Inline `<script>` blocks extracted and checked separately.

### 1.2 Media Paths Referenced in `index.html` (`test -f`)

Paths grepped from `index.html` `src`/`href` attributes and verified with `test -f`:

| Path | Exists? |
|------|---------|
| `./assets/style.css` | OK/MISSING |
| `./support.js` | OK/MISSING |
| `./assets/webgpu-boot.js` | OK/MISSING |
| `./assets/gpu-graph.js` | OK/MISSING |
| `./assets/glyph.js` | OK/MISSING |
| `./assets/intro.js` | OK/MISSING |
| `./assets/renderer.js` | OK/MISSING |
| `media/{asset}.webp` | OK/MISSING |
| ... | ... |

All referenced paths resolve. `test -f` clean.

### 1.3 HTTP Server Status

| Endpoint | HTTP Status |
|----------|-------------|
| `http://127.0.0.1:{port}/index.html` | 200 |
| `http://127.0.0.1:{port}/assets/style.css` | 200 |
| `http://127.0.0.1:{port}/assets/*.js` | 200 |

---

## 2. Browser Evidence (Hermes Tools, Same Session)

### 2.1 `navigator.gpu`

`{true/false}` — the WebGPU API namespace is present in the verification browser.

### 2.2 `requestAdapter()` Outcome

`{adapter object / null}` — `{explanation}`. Verbatim console witness:

```
{console output}
```

### 2.3 `window.__webgpuBoot.backend()`

`"{webgpu|webgl2|canvas2d}"` — the paint-first 3-tier ladder correctly demoted: {explanation}. Verbatim console witness:

```
{console output}
```

### 2.4 `window.__webgpuBoot.isPrimary()`

`{true/false}`

### 2.5 `document.body.className`

`"{className}"` — both tier-legibility class and intro-completion class.

### 2.6 `document.documentElement.className`

`"{className}"`

### 2.7 Canvas Inventory

Every canvas on the page, with `getImageData` non-zero count sampled from a 64×64 region:

| # | id | width | height | clientWidth | clientHeight | Non-zero pixels (64×64 sample) |
|---|----|-------|--------|-------------|--------------|-------------------------------|
| 1 | `{id}` | {w} | {h} | {cw} | {ch} | **{count}** |
| 2 | `{id}` | {w} | {h} | {cw} | {ch} | {count} |
| ... | ... | ... | ... | ... | ... | ... |

- `#{id}` description and interpretation

### 2.8 Console Messages (Complete, Verbatim)

Console capture was active during page load. All {N} messages:

1. `{message}` (console.{level})
2. `{message}` (console.{level})
...

### 2.9 `js_errors`

`[]` — **zero uncaught JavaScript exceptions**. {Explanation of critical fix if applicable}.

### 2.10 `browser_vision` Description (Verbatim)

> {vision analysis output}

### 2.11 `browser_snapshot` Element Count

`{N}` elements — {description of rendered content}.

---

## 3. Live Root Integrity

| Check | Result |
|-------|--------|
| `index.html` served with dc-runtime (not a stale fork copy) | ✓/✗ verified |
| `design-import` pristine | ✓/✗ not touched in this worktree |
| No inline styles in hand-authored content | ✓/✗ (dc-runtime template uses inline styles, which is the framework's mechanism) |

---

## 4. Self-Test Results

### {Test Suite Name} (e.g., `glyph-det-test.js`)

```
{test output}
```

**Result:** {PASS/FAIL} — {N} passed, {M} failed

### {Test Suite Name} (e.g., `gpu-graph-selftest.js`)

```
{test output}
```

**Result:** {PASS/FAIL} — {N} passed, {M} failed

---

## 5. Backlog — Media Gap vs Spec ({spec-file} §{section})

{Spec file} §{section} specifies {targets}; Current on-disk state measured in this session:

| Category | Target (spec) | Current | Gap |
|---|---|---|---|
| {Category} | {target} | {current} | **{gap}** ({details}) |

---

## 6. Summary

| Check | Result |
|-------|--------|
| JS syntax (`node --check`) | All {N} files PASS |
| Media paths (`test -f`) | All {N} referenced paths OK |
| HTTP server | 200 on all endpoints |
| `navigator.gpu` | `{true/false}` |
| `requestAdapter()` | `{adapter/null}` ({explanation}) |
| `window.__webgpuBoot.backend()` | `"{backend}"` |
| `document.body.className` | `"{className}"` |
| Canvas `#{id}` non-zero pixels | **{count}** ({interpretation}) |
| `js_errors` | `[]` — **zero uncaught exceptions** |
| `{Engine}` loaded | `{type}` |
| Media gap — {category} | {current}/{target} |

**Verdict:** {Summary statement — e.g., "The Q1 paint-first boot fix is verified — the site is no longer a black screen..."}

*Evidence collected via Hermes browser tools only. No Chrome/Chromium/Playwright processes spawned by this worker.*