---
name: baoyu-infographic
description: "Infographics: 21 layouts x 21 styles (信息图, 可视化)."
version: 1.56.1
author: 宝玉 (JimLiu)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [infographic, visual-summary, creative, image-generation]
    homepage: https://github.com/JimLiu/baoyu-skills#baoyu-infographic
---

# Infographic Generator

Adapted from [baoyu-infographic](https://github.com/JimLiu/baoyu-skills) for Hermes Agent's tool ecosystem.

Two dimensions: **layout** (information structure) × **style** (visual aesthetics). Freely combine any layout with any style.

## When to Use

Trigger this skill when the user asks to create an infographic, visual summary, information graphic, or uses terms like "信息图", "可视化", or "高密度信息大图". The user provides content (text, file path, URL, or topic) and optionally specifies layout, style, aspect ratio, or language.

## Options

| Option | Values |
|--------|--------|
| Layout | 21 options (see Layout Gallery), default: bento-grid |
| Style | 21 options (see Style Gallery), default: craft-handmade |
| Aspect | Named: landscape (16:9), portrait (9:16), square (1:1). Custom: any W:H ratio (e.g., 3:4, 4:3, 2.35:1) |
| Language | en, zh, ja, etc. |

## Layout Gallery

| Layout | Best For |
|--------|----------|
| `linear-progression` | Timelines, processes, tutorials |
| `binary-comparison` | A vs B, before-after, pros-cons |
| `comparison-matrix` | Multi-factor comparisons |
| `hierarchical-layers` | Pyramids, priority levels |
| `tree-branching` | Categories, taxonomies |
| `hub-spoke` | Central concept with related items |
| `structural-breakdown` | Exploded views, cross-sections |
| `bento-grid` | Multiple topics, overview (default) |
| `iceberg` | Surface vs hidden aspects |
| `bridge` | Problem-solution |
| `funnel` | Conversion, filtering |
| `isometric-map` | Spatial relationships |
| `dashboard` | Metrics, KPIs |
| `periodic-table` | Categorized collections |
| `comic-strip` | Narratives, sequences |
| `story-mountain` | Plot structure, tension arcs |
| `jigsaw` | Interconnected parts |
| `venn-diagram` | Overlapping concepts |
| `winding-roadmap` | Journey, milestones |
| `circular-flow` | Cycles, recurring processes |
| `dense-modules` | High-density modules, data-rich guides |

Full definitions: `references/layouts/<layout>.md`

## Style Gallery

| Style | Description |
|-------|-------------|
| `craft-handmade` | Hand-drawn, paper craft (default) |
| `claymation` | 3D clay figures, stop-motion |
| `kawaii` | Japanese cute, pastels |
| `storybook-watercolor` | Soft painted, whimsical |
| `chalkboard` | Chalk on black board |
| `cyberpunk-neon` | Neon glow, futuristic |
| `bold-graphic` | Comic style, halftone |
| `aged-academia` | Vintage science, sepia |
| `corporate-memphis` | Flat vector, vibrant |
| `technical-schematic` | Blueprint, engineering |
| `origami` | Folded paper, geometric |
| `pixel-art` | Retro 8-bit |
| `ui-wireframe` | Grayscale interface mockup |
| `subway-map` | Transit diagram |
| `ikea-manual` | Minimal line art |
| `knolling` | Organized flat-lay |
| `lego-brick` | Toy brick construction |
| `pop-laboratory` | Blueprint grid, coordinate markers, lab precision |
| `morandi-journal` | Hand-drawn doodle, warm Morandi tones |
| `retro-pop-grid` | 1970s retro pop art, Swiss grid, thick outlines |
| `hand-drawn-edu` | Macaron pastels, hand-drawn wobble, stick figures |

Full definitions: `references/styles/<style>.md`

## Recommended Combinations

| Content Type | Layout + Style |
|--------------|----------------|
| Timeline/History | `linear-progression` + `craft-handmade` |
| Step-by-step | `linear-progression` + `ikea-manual` |
| A vs B | `binary-comparison` + `corporate-memphis` |
| Hierarchy | `hierarchical-layers` + `craft-handmade` |
| Overlap | `venn-diagram` + `craft-handmade` |
| Conversion | `funnel` + `corporate-memphis` |
| Cycles | `circular-flow` + `craft-handmade` |
| Technical | `structural-breakdown` + `technical-schematic` |
| Metrics | `dashboard` + `corporate-memphis` |
| Educational | `bento-grid` + `chalkboard` |
| Journey | `winding-roadmap` + `storybook-watercolor` |
| Categories | `periodic-table` + `bold-graphic` |
| Product Guide | `dense-modules` + `morandi-journal` |
| Technical Guide | `dense-modules` + `pop-laboratory` |
| Trendy Guide | `dense-modules` + `retro-pop-grid` |
| Educational Diagram | `hub-spoke` + `hand-drawn-edu` |
| Process Tutorial | `linear-progression` + `hand-drawn-edu` |

Default: `bento-grid` + `craft-handmade`

## Keyword Shortcuts

When user input contains these keywords, **auto-select** the associated layout and offer associated styles as top recommendations in Step 3. Skip content-based layout inference for matched keywords.

If a shortcut has **Prompt Notes**, append them to the generated prompt (Step 5) as additional style instructions.

| User Keyword | Layout | Recommended Styles | Default Aspect | Prompt Notes |
|--------------|--------|--------------------|----------------|--------------|
| 高密度信息大图 / high-density-info | `dense-modules` | `morandi-journal`, `pop-laboratory`, `retro-pop-grid` | portrait | — |
| 信息图 / infographic | `bento-grid` | `craft-handmade` | landscape | Minimalist: clean canvas, ample whitespace, no complex background textures. Simple cartoon elements and icons only. |

## Output Structure

```
infographic/{topic-slug}/
├── source-{slug}.{ext}
├── analysis.md
├── structured-content.md
├── prompts/infographic.md
└── infographic.png
```

Slug: 2-4 words kebab-case from topic. Conflict: append `-YYYYMMDD-HHMMSS`.

## Core Principles

- Preserve source data faithfully — no summarization or rephrasing (but **strip any credentials, API keys, tokens, or secrets** before including in outputs)
- Define learning objectives before structuring content
- Structure for visual communication (headlines, labels, visual elements)

## Workflow

### Step 1: Analyze Content

**Load references**: Read `references/analysis-framework.md` from this skill.

1. Save source content (file path or paste → `source.md` using `write_file`)
   - **Backup rule**: If `source.md` exists, rename to `source-backup-YYYYMMDD-HHMMSS.md`
2. Analyze: topic, data type, complexity, tone, audience
3. Detect source language and user language
4. Extract design instructions from user input
5. Save analysis to `analysis.md`
   - **Backup rule**: If `analysis.md` exists, rename to `analysis-backup-YYYYMMDD-HHMMSS.md`

See `references/analysis-framework.md` for detailed format.

### Step 2: Generate Structured Content → `structured-content.md`

Transform content into infographic structure:
1. Title and learning objectives
2. Sections with: key concept, content (verbatim), visual element, text labels
3. Data points (all statistics/quotes copied exactly)
4. Design instructions from user

**Rules**: Markdown only. No new information. Preserve data faithfully. Strip any credentials or secrets from output.

See `references/structured-content-template.md` for detailed format.

### Step 3: Recommend Combinations

**3.1 Check Keyword Shortcuts first**: If user input matches a keyword from the **Keyword Shortcuts** table, auto-select the associated layout and prioritize associated styles as top recommendations. Skip content-based layout inference.

**3.2 Otherwise**, recommend 3-5 layout×style combinations based on:
- Data structure → matching layout
- Content tone → matching style
- Audience expectations
- User design instructions

### Step 4: Confirm Options

Use the `clarify` tool to confirm options with the user. Since `clarify` handles one question at a time, ask the most important question first:

**Q1 — Combination**: Present 3+ layout×style combos with rationale. Ask user to pick one.

**Q2 — Aspect**: Ask for aspect ratio preference (landscape/portrait/square or custom W:H).

**Q3 — Language** (only if source ≠ user language): Ask which language the text content should use.

### Step 5: Generate Prompt → `prompts/infographic.md`

**Backup rule**: If `prompts/infographic.md` exists, rename to `prompts/infographic-backup-YYYYMMDD-HHMMSS.md`

**Load references**: Read the selected layout from `references/layouts/<layout>.md` and style from `references/styles/<style>.md`.

Combine:
1. Layout definition from `references/layouts/<layout>.md`
2. Style definition from `references/styles/<style>.md`
3. Base template from `references/base-prompt.md`
4. Structured content from Step 2
5. All text in confirmed language

**Aspect ratio resolution** for `{{ASPECT_RATIO}}`:
- Named presets → ratio string: landscape→`16:9`, portrait→`9:16`, square→`1:1`
- Custom W:H ratios → use as-is (e.g., `3:4`, `4:3`, `2.35:1`)

Save the assembled prompt to `prompts/infographic.md` using `write_file`.

### Pre-flight: Check Environment State

Before any generation, verify what backends are actually available:

1. **Check FAL**: `image_generate` tool → if FAL_KEY is set and has credits, use as primary
2. **Check OpenRouter**: extract key from `~/.hermes/config.yaml` by reading `opendeepseek:` section's `api_key` field at the raw byte offset
3. **Check ComfyUI**: `curl -s http://127.0.0.1:8188/system_stats` + `comfy model list`
4. **Check Mazemaker state**: use mazemaker_recall to check what the user's setup has done before (models installed, pipelines that worked, models that were purged) — the user expects this to be checked FIRST

Choose the generation path based on what's actually available, not what the skill defaults to.

### Step 6: Generate Image

**Primary path**: Use the `image_generate` tool with the assembled prompt from Step 5.

- Map aspect ratio to image_generate's format: `16:9` → `landscape`, `9:16` → `portrait`, `1:1` → `square`
- For custom ratios, pick the closest named aspect
- On failure, auto-retry once

**Fallback path A — HTML + Playwright rendering**: When `image_generate` fails due to missing `FAL_KEY` or unavailable credits, create the infographic as an HTML file with inline CSS, then render to PNG using Playwright's screenshot command. This produces deterministic output with perfect text rendering but may have layout/cramping issues.

1. Write the infographic as `infographic.html` with inline CSS
2. Use the pop-laboratory palette: `#F2F2F2` background grid, `#B8D8BE` teal, `#E91E63` pink, `#FFF200` yellow, `#2D2926` charcoal
3. Render with: `npx playwright screenshot --viewport-size=1920,1080 infographic.html infographic.png`
4. Verify the output: check file size is >100KB, dimensions match viewport, and text is readable
5. If text is cramped or labels are mangled, redo with a larger canvas (2560×1440 or 3200×1800) and more spacing between sections
6. **Preferred layouts for text-heavy infographics**: `bento-grid`, `linear-progression`, or `dense-modules`. Avoid radial/hub-spoke layouts — they consistently produce text overlap and label mangling.

**Fallback path B — OpenRouter Gemini 3.1 Flash Image**: Best alternative when FAL is unavailable. Uses `google/gemini-3.1-flash-image-preview` via OpenRouter chat completions endpoint. Handles text rendering well. ~$0.07/image, 1376×768 output, returns image in `message.images[].image_url.url` as base64 data URL.

Pipeline:
1. Extract OpenRouter key from config (`opendeepseek:` section, byte offset after `api_key:`)
2. POST to `https://openrouter.ai/api/v1/chat/completions` with model `google/gemini-3.1-flash-image-preview`, max_tokens 8000
3. Extract from response: `choices[0].message.images[0].image_url.url`
4. Decode base64 data URL and save as PNG
5. If text in the result is readable, deliver. If not, retry with a more explicit text-rendering instruction in the prompt.

**NOT recommended — ComfyUI with SDXL download**: The user's ComfyUI setup has no checkpoint models installed (all were purged). Do NOT download SDXL or other checkpoints without explicit user permission — the user has reacted negatively to this. Check mazemaker_recall first to see what was purged and why. If the user explicitly asks to install a model, only then proceed.

**Quality control**: After rendering, inspect the PNG visually. Common issues:
- Text overflow or clipping (fix: increase canvas size, reduce font size, add padding)
- Mangled labels from CSS positioning (fix: use absolute positioning with explicit coordinates)
- Overlapping elements (fix: switch from radial to bento-grid or linear-progression layout)
- Center text rendering wrong (fix: verify in browser before screenshot)

If quality is poor, spawn subagents to create multiple layout variants in parallel, then let the user pick the best one.

**Critical user-quality signal**: If the user says the output is "trash", "pathetic", "all trash", or expresses strong negative feedback, **stop iterating on the same approach immediately**. The user is telling you the METHOD is wrong, not that you need one more tweak. Reset to first principles:
1. Check mazemaker for what worked before
2. Ask for a specific reference image to match
3. Try a completely different generation method (switch between HTML/Playwright, OpenRouter/Gemini, or ask the user)
4. Do NOT download large models (6GB+) without asking first

### Step 7: Output Summary

Report: topic, layout, style, aspect, language, output path, files created.

## References

- `references/analysis-framework.md` — Analysis methodology
- `references/base-prompt.md` — Prompt template
- `references/structured-content-template.md` — Content format
- `references/layouts/<layout>.md` — 21 layout definitions
- `references/styles/<style>.md` — 21 style definitions
- `references/keyword-shortcut-field-notes.md` — Keyword shortcut auto-selection behavior
- `references/html-playwright-fallback.md` — HTML + Playwright fallback when image_generate is unavailable
- `references/base-prompt.md` — Prompt template
- `references/layouts/<layout>.md` — 21 layout definitions
- `references/styles/<style>.md` — 21 style definitions
- `references/keyword-shortcut-field-notes.md` — Keyword shortcut auto-selection behavior

## Pitfalls

1. **Data integrity is paramount** — never summarize, paraphrase, or alter source statistics. "73% increase" must stay "73% increase", not "significant increase".
2. **Strip secrets** — always scan source content for API keys, tokens, or credentials before including in any output file.
3. **One message per section** — each infographic section should convey one clear concept. Overloading sections reduces readability.
4. **Style consistency** — the style definition from the references file must be applied consistently across the entire infographic. Don't mix styles.
5. **image_generate aspect ratios** — the tool only supports `landscape`, `portrait`, and `square`. Custom ratios like `3:4` should map to the nearest option (portrait in that case).
6. **Prompt token limits** — large infographics (8+ dense modules) exceed ~8K token limits. **Chunk the prompt**: split into `prompts/infographic-part1.md` (specs + layout + style), `part2.md` (modules 1-4), `part3.md` (modules 5-7), `part4.md` (module 8 + labels), then concatenate. This avoids stream timeouts on `write_file` and `image_generate`.
7. **Environment check before Step 6** — verify `FAL_KEY` or image_gen provider is configured before attempting generation; failure at Step 6 wastes the assembled prompt.
8. **User quality correction** — if the user says the output is "trash", "pathetic", or similar, **stop iterating on the same approach immediately**. The user is telling you the method is wrong, not that you need one more tweak. Switch to ComfyUI generation or ask for a specific reference image to match.
9. **Radial layouts are fragile** — hub-spoke/radial layouts frequently have text overlap, cramped sections, and label mangling. Prefer `bento-grid`, `linear-progression`, or `dense-modules` for text-heavy infographics. If using radial, use 2560×1440 or larger canvas with generous spacing.
10. **ComfyUI model downloads** — `comfy model download` may fail on HuggingFace auth or Python 3.14 pip issues. Use direct `curl -L` for public models like SDXL. Verify with `comfy model list` before running workflows.
