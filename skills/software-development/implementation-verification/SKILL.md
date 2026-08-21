---
name: implementation-verification
description: Verify gated web apps syntax assets browser caps tests.
version: 1.0.0
metadata:
  hermes:
    tags: [verification, validation, web, gates, static-analysis, webgpu, canvas2d]
    related_skills: [dogfood, systematic-debugging]
---

# Implementation Verification: Static Gate Validation for Web Applications

## Overview

This skill covers systematic **static verification** of web application implementations against defined gate criteria. Unlike exploratory QA testing (see `dogfood`), this is a deterministic, repeatable validation workflow that checks:

1. **JavaScript syntax** — all served JS files pass `node --check`
2. **Asset existence** — all referenced media/assets resolve via `test -f`
3. **Browser capability evidence** — `navigator.gpu`, `requestAdapter()`, canvas state, JS errors
4. **Self-test execution** — deterministic test suites (e.g., `glyph-det-test.js`, `gpu-graph-selftest.js`)
5. **Gate criteria** — explicit pass/fail checks for defined gates (Gate D: 0 inline styles + clean JS; Gate F: user walkthrough trigger)

## When to Use

- Verifying a worktree/branch meets release gates before merge
- Validating WebGPU/Canvas2D fallback implementations
- Confirming deterministic rendering engines (glyphs, particle graphs, etc.)
- Pre-deployment static validation in CI/CD contexts

## Prerequisites

- Node.js available for `node --check`
- Shell access for `test -f` and test execution
- Hermes browser tools for capability evidence (optional but recommended)
- Target worktree path with `index.html`, `assets/`, `media/` structure

## Workflow

### Phase 1: Static Syntax & Asset Verification

```bash
# 1. Check all JS files
node --check assets/*.js support.js

# 2. Check inline scripts (extract to temp file first)
#    index.html inline <script> blocks -> /tmp/inline-script.js -> node --check

# 3. Verify all referenced media assets
grep -o 'src="media/[^"]*"' index.html | sed 's/src="//;s/"//' | xargs -I{} test -f {} && echo "All assets exist"

# 4. Check subdirectories (film/, shots/, worlds/, stills/)
ls -la media/film/ media/shots/ media/worlds/ media/stills/
```

### Phase 2: Browser Capability Evidence (Hermes Tools)

If browser tools available, collect:

1. `navigator.gpu` -> `true`/`false`
2. `navigator.gpu.requestAdapter()` -> adapter object or `null`
3. `window.__webgpuBoot.backend()` -> `"webgpu" | "webgl2" | "canvas2d"`
4. `document.body.className` -> tier indicator (e.g., `"canvas2d-fallback intro-done"`)
5. Canvas inventory: `getImageData` non-zero pixel counts per canvas
6. `browser_console()` -> JS errors array (must be `[]` for Gate D)
7. `browser_vision()` -> visual confirmation (not black screen)
8. `browser_snapshot()` -> element count, React/DC runtime verification

### Phase 3: Self-Test Execution

Run deterministic test suites:

```bash
# Glyph engine determinism
cd assets && node glyph-det-test.js

# GPU graph binding layout
cd assets && node gpu-graph-selftest.js
```

Expected: All assertions PASS, exit code 0.

### Phase 4: Gate Verification

| Gate | Criteria | Verification |
|------|----------|--------------|
| **Gate D** | 0 inline styles (hand-authored), all URLs 200, JS syntax clean | `grep -n 'style=' index.html` -> only dc-runtime template styles; `node --check` all JS |
| **Gate F** | User walkthrough: "Gänsehaut-Trigger" = opening->final-loop works; Worlds gallery & film smooth on target GPU | `browser_vision` + manual walkthrough; 60fps on target hardware |

## WebGPU/Canvas2D Fallback Specifics

For implementations using the 3-tier ladder (WebGPU -> WebGL2 -> Canvas2D):

### Expected Evidence in `canvas2d` Fallback Mode

| Check | Expected (No GPU) | Notes |
|-------|-------------------|-------|
| `navigator.gpu` | `true` | API namespace present |
| `requestAdapter()` | `null` | Software rasterizer / no driver |
| `__webgpuBoot.backend()` | `"canvas2d"` | Clean demotion |
| `#stage2d` non-zero pixels | >0 (e.g., 648) | 2D gradient lit |
| `#webgpuStage` non-zero | 0 | No GPU upgrade |
| `#intro-canvas` non-zero | 0 or >0 | Depends on intro phase |
| `js_errors` | `[]` | **Critical: zero uncaught exceptions** |
| `MazeIntro` loaded | `object` | Intro engine ready |
| `MazeGlyph` loaded | `object` | Glyph engine ready |
| `MazeGPUGraph` loaded | `object` (inert) | Stays inert when backend != webgpu |

### Common Failure Patterns

| Symptom | Cause | Fix |
|---------|-------|-----|
| Black screen / 0 pixels on all canvases | `createCanvas` ReferenceError in boot | Ensure boot ladder catches all tiers, no unwind |
| `js_errors` shows ReferenceError | Exception not caught in boot ladder | Add try/catch around each tier attempt |
| `requestAdapter` hangs | Missing timeout/guard | Add timeout promise race |
| Glyph canvas 0 pixels | Intro not reached GLYPH phase | Verify `intro-done` class, check `MazeGlyph.renderGlyph` call |

## Output

Produce a **Gate Report** (markdown) with:
- Static verification results (syntax, assets)
- Browser capability evidence table
- Canvas inventory with non-zero pixel counts
- Console error array (must be empty)
- Self-test results (PASS/FAIL)
- Gate D/F verdict
- Media gap analysis vs spec (e.g., `endstand.md`)

See `references/gate-report-template.md` for structure.

## References

- `references/gate-report-template.md` — Report structure
- `references/webgpu-canvas2d-checklist.md` — Detailed capability checklist
- `references/common-failure-patterns.md` — Known failure modes and fixes

## Related Skills

- `dogfood` — Exploratory QA testing (complementary: finds runtime/interaction bugs this misses)
- `systematic-debugging` — Root cause analysis when verification fails
- `maze-crew-iteration` — Autonomous iteration loop that includes verification