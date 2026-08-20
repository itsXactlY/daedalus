---
name: visual-mockup
description: |
  Throwaway / exploratory visual design mockups — three techniques under one class:
  one-off HTML artifacts (landing/deck/prototype) via claude-design, hand-drawn
  Excalidraw JSON diagrams (arch/flow/seq), and rapid 2-3-variant HTML mockups to
  compare. Use when the user wants a quick visual draft, diagram, or a few design
  variants to choose between — not a production design system.
---

# Visual Mockup

Class-level skill for fast, discardable visual drafts. These are exploration tools, not
the polished design-system skills (`creative/popular-web-designs`, `creative/design-md`,
`creative/architecture-diagram`). Pick the technique by what the user is comparing.

## Technique 1 — One-off HTML artifact (absorbed from `claude-design`)

Design a single HTML artifact: landing page, slide deck, or interactive prototype. Best
when the user wants one polished throwaway page. (No support files; the pattern is
self-contained HTML + CSS.)

## Technique 2 — Hand-drawn Excalidraw diagrams (absorbed from `excalidraw`)

Generate Excalidraw JSON for architecture / flow / sequence diagrams with a hand-drawn
aesthetic.

Support (under `references/excalidraw/`): `colors.md`, `dark-mode.md`, `examples.md`.
Script: `scripts/excalidraw/upload.py` (push the JSON to an Excalidraw instance).

## Technique 3 — Variant comparison mockups (absorbed from `sketch`)

Produce 2-3 design variants of the same screen as throwaway HTML so the user can compare
direction quickly. Best when the user is deciding between approaches, not finalizing one.

## When NOT to use this skill

- Need a real component library → `creative/popular-web-designs`.
- Need a token/design-spec file → `creative/design-md`.
- Need a dark-themed architecture SVG → `creative/architecture-diagram`.
