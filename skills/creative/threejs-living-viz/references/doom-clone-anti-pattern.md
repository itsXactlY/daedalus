# Doom-clone anti-pattern — case study (extended 2026-06-22, 3-iteration arc)

## What happened (full 3-iteration arc)

**Iteration 1 — Doom clone (REJECTED):**

Session 2026-06-22: user asked for a new version of `/home/alca/projects/mazemaker-v2-stack/frontend/website/architect/` — "use all creative skills, insights from mazemaker, to create a never-seen-before in-depth view of mazemaker's pandora's box. all paths, all routes, every corner walkable".

I loaded `threejs-living-viz` which had explicit triggers matching:
- "**Building a walkable 3D world** (first-person, hub-and-spoke, every corner reachable — see Section 19)"
- "**Navigable data experiences** (PointerLockControls + chambers + door raycasting + canvas minimap)"
- "**Visualizing a real corpus as a walkable space**"

I followed those triggers literally. Built a 106,544-byte HTML file with Three.js + PointerLockControls + custom GLSL shaders + 5,000 neural-pool nodes + 27 chambers. User: "1fps trash lol wow", then **"I WAS ASKING FOR A FUCKING UI, NOT AN DOGSHIT DOOM CLONE!"**.

**Iteration 2 — Plain editorial UI (ALSO REJECTED):**

I rebuilt as a 25,100-byte UI (4.2× smaller): editorial card grid, modals, live recall, WCAG-AA. Worked first try technically — but user: **"WAS IST DAS FÜR ABARTIGER SCHWACHSINN?"** → "ganz anders!" → "bleeding edge UI, wo alles wie im architect macht, aber 10000x besser visualisiert!".

The clean editorial UI was correct on accessibility, performance, and intent (UI not 3D) but completely missed the visual richness bar. The user explicitly wants "bleeding edge" — not a clean doc.

**Iteration 3 — Graph-Native Control Surface (ACCEPTED):**

Following the user's explicit "recherche, plan, recherche, plan, audit, rechere, ... DANN bauen!" workflow: I researched the existing dashboards in mazemaker, re-planned, researched bleeding-edge 2026 UI patterns, audited my own plan, then built. Result: 60,828 bytes, a Canvas2D force-directed graph (Barnes-Hut, Web Worker, Float32Array transfer) with 12 monitor hubs + live mazemaker_browse data, radial+force hybrid layout, hover highlighting, click-to-detail with neighbors-subgraph, phase state ring, recall input with debounced live search, ⌘K command palette. This is what "bleeding edge UI, 10000x better visualisiert" actually means.

## The lesson

**Two failure modes, not one:**
1. **Doom-clone** — 3D walkable worlds when user said "explore" / "walkable" / "every corner"
2. **Plain-editorial-UI** — clean doc when user said "bleeding edge" / "10000x better"

The user uses evocative spatial/quality language. Both ends of the spectrum are wrong:
- 3D walkable (overengineered, slow, game-like) → REJECTED
- Plain editorial doc (underengineered, boring) → REJECTED
- Data-rich 2D/Canvas control surface (visually rich, functional, fast) → ACCEPTED

## Threshold check (REPLACES the previous 5-question check)

```
IF request mentions spatial metaphor + system with many components:
  ASK first (one direct question): "walkable first-person 3D, or clickable UI?"
  IF user does not explicitly confirm 3D: build the UI version

THEN, if user says "bleeding edge" / "10000x better" / "kindergarten" / "schwachsinn":
  Do NOT default to clean editorial. Build a VISUALLY RICH 2D/Canvas control surface:
  - Force-directed graph (Canvas2D + Web Worker + Barnes-Hut)
  - Live data overlays (no mock fallback only — connect to live pod)
  - Custom shaders for visual polish (subtle, not garish)
  - Real-time data (no static "—")
  - Density of information (data-rich, not minimal)
  - Click-driven depth (slide-in detail panels, drill-down)
  - ⌘K command palette, debounced live search, real-time stats
```

## The 8-question sanity check before committing to a build path

1. User says "first-person" / "FPS" / "game" / "cinematic 3D" explicitly? (if no → UI not 3D)
2. User says "clickable" / "explorable UI" / "page" / "panel" / "card" / "form"? (if yes → UI)
3. User says "bleeding edge" / "10000x better" / "kindergarten" / "schwachsinn"? (if yes → must be visually rich, NOT clean editorial)
4. User wants "walkable" / "every path" / "every corner"? (if yes → confirm 3D vs UI explicitly)
5. Node count >10 or hierarchy >3 levels? (if yes → UI typically better)
6. Desktop with GPU only? (if no → UI typically safer)
7. User says "research, plan, audit, then build" / wants iteration? (if yes → FOLLOW THE PROCESS; show research, show plan, show audit, then build)
8. Brand calls for 3D as identity? (if no → 2D/Canvas)

## The "research-plan-audit-then-build" workflow

When the user explicitly says: "erst recherche, plan, recherche, plan, audit, rechere, ... DANN bauen" (first research, plan, research, plan, audit, research, then build), follow this pattern visibly:

1. **Research 1** — query mazemaker for what's been done before, what's the architectural truth
2. **Plan 1** — write down a concrete plan, show it to the user
3. **Research 2** — more research based on plan-1 (deep dive on specific patterns)
4. **Plan 2** — refined plan based on research-2
5. **Audit** — self-critique: "what could go wrong? what constraints am I under?"
6. **Research 3** (if needed) — final pass on edge cases
7. **Build** — only after the user sees the visible process

DO NOT just dive in and build. The user wants to see the work, even if it takes more turns. Each turn should be auditable: "here's what I researched, here's my plan, here's my audit, here's what I'm going to build."

## The correct pattern: "Graph-Native Control Surface"

When the user wants bleeding-edge visualization of a complex system (mazemaker, knowledge graph, AI control plane), the 2026-standard pattern is:

```
Canvas2D force-directed graph (Web Worker + Barnes-Hut)
  + radial+force hybrid layout (high-salience inner, low outer)
  + live data overlay (no mock fallback only — connect to live pod)
  + hover/click → 1-hop neighbor highlight + slide-in detail panel
  + custom shaders for visual polish (subtle, not garish)
  + ⌘K command palette
  + debounced live search with 9-channel visualization
  + bottom: recall input, phase state ring
  + top: live stats (memories, edges, dream sessions, etc.)
  + left rail: component list (12 monitors) with live status
```

Tech stack: vanilla JS, no CDN, no Three.js, single HTML file. Inter + JetBrains Mono via Google Fonts only. Web Worker (Blob URL) for force simulation with Float32Array transferable. Radial gradient for ambient glow. Custom canvas drawing for edges, nodes, hover halos.

This is "10000x better visualisiert" than a clean editorial doc, while still being a real UI (not a game). The graph IS the UI — the user can click any node, see neighbors, query related, all while seeing the live data pulse.

## Strong-language response pattern (extended)

When user pushes back with profanity on a 3D/web/visual project (3 iterations in this session):
1. Acknowledge in one sentence (no defense, no "I tried my best")
2. Don't patch the existing artifact — identify the abstraction level mismatch
3. Don't rebuild at the same level — go to a DIFFERENT level
4. If they say "I want X but 10000x better visualisiert" — they don't want X+1 incremental, they want a category shift
5. When they say "research, plan, audit, then build" — show the work, not just the result

The 3-iteration cost was real: ~120KB of intermediate work that got thrown away. If I had asked "walkable 3D, or clickable UI?" at the start, I'd have skipped the doom-clone. If I had asked "data-rich 2D canvas surface with live pod integration, or plain editorial doc?" before iteration 2, I'd have skipped the editorial version.

## Files involved (final state)

- Iteration 1 (Doom clone, REJECTED): `/home/alca/projects/mazemaker-v2-stack/frontend/website/architect/pandoras-box.html` 106,544 bytes
- Iteration 2 (Plain UI, REJECTED): same path, 25,100 bytes
- Iteration 3 (Graph-Native Control Surface, ACCEPTED): same path, 60,828 bytes
- Untouched: `/home/alca/projects/mazemaker-v2-stack/frontend/website/architect/index.html` md5 d2fa25fa...

## Cross-reference memory ids

- bug:pandoras-box-tdz-elapsed-2026-06-22 (id=826082)
- fact:pandoras-box-architect-v2-2026-06-22 (id=826068)
- bug:pandoras-box-corpus-stale-reference-2026-06-22 (id=826112)
- decision:pandoras-box-v2-design-aligned-2026-06-22 (id=826113)
- bug:pandoras-box-glsl-reserved-attribute-2026-06-22 (id=826146)
- decision:pandoras-box-perf-pass-2026-06-22 (id=826158)
- bug:pandoras-box-phase-rooms-tdz-2026-06-22 (id=826181)
- decision:pandoras-box-monochrome-violet-2026-06-22 (id=826191)
- decision:pandoras-box-clean-ui-rebuild-2026-06-22 (id=826237)
- decision:pandoras-box-graph-native-control-surface-2026-06-22 (id=826647)
