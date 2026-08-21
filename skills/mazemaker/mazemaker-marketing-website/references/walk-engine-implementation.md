# Walk Engine — implementation notes (Gigaplan Phase 1/2, committed 05717bb)

Session-specific detail on the living-maze walk engine that was committed on
`visual/cockpit-demo`. Read this before touching `website/assets/intro.js`,
`website/assets/glyph.js`, or `website/assets/maze-engine.js`.

## File map (website/assets/)

- `maze-engine.js` — the shared 2D-canvas maze engine, self-contained
  `window.initMaze(canvas, {...})`, faithful rebuild of the Architect's
  `maze-panel.js` with a `generateSynth()` fallback (renders with no pod). Pre-existed
  this commit; the intro hands control to it on the scroll seam.
- `intro.js` (550 lines, IIFE on `window`) — the whole walk:
  - `GLYPH_ORDER = ['AWAKE','NREM','REM','INSIGHT']`.
  - **Share-safe memories** array — identical seed strings to maze-engine.js. All
    node labels are public categories (decision/build/fact/bug/invariant/ops/dream/
    bridge/conflict/supersession). Never add private/real-person/hostname/token data.
  - **Seed**: `?seed=` query param beats `sessionSeed + '::' + YYYY-MM-DD` date
    fingerprint. `seedHex = fnv1a(seedStr)`; `rng = mulberry32(fnv1a(seedStr))`.
    Logged via `console.log('intro seed ' + seedHex + ' (' + seedStr + ')')`.
    Uses `sessionStorage` for the session counter — acceptable here, but the plan
    says no dependence on browser persistence as a hard requirement.
  - **Opening pool** (all converge on the fixed anchor): the 6 lines exactly as the
    plan lists them, each `{ a: <opening>, b: 'The architect awaited you already.' }`.
  - **Typing**: `typeInto(lineEl, text, {speed, rng})`; `prefers-reduced-motion`
    skips flicker and uses fast/static typing.
  - **Glyph finalize**: `renderGlyph(canvas, walkPath.join('::') + '::' + seedHex,
    18)`, caption `FINGERPRINT GLYPH · <hex>`.
  - **Closing**: types "The maze remembers you." then re-types the opening anchor.
  - Phase label via `GLYPH_ORDER[Math.min(n.state,3)]`; walkPhase advances on seeded
    pacing.
  - Exposes `window.<name>.getSeed() -> seedHex` and an `initIntro(canvas, {...})`
    entry the hero boot calls (see index.html inline script — it polls for
    `window.initIntro` then boots `#heroMaze`; on first scroll after the glyph it
    hands the canvas to `initMaze`).
- `glyph.js` (61 lines) — **deterministic fingerprint glyph**: `fnv1a(str)` → 32-bit
  seed → `mulberry32(a)` → 8×2 cell canvas pattern. Documented as a faithful rebuild
  of `backend/client/pod/wonderland/architect/src/keys.js` — same seed string → same
  glyph forever. Exposes `renderGlyph`/`hashHex`/`fnv1a`/`mulberry32` on `global`.

## Determinism contract (Gigaplan Gate B/E)

- Same seed + same path → same glyph. Different path → different glyph.
- Same seed → same experience; different seed → visibly different route/layout/glyph.
- No `localStorage`; no external tracking; no audio by default; no popups/tooltips/
  modals during crystallization.
- `?seed=maze-01..05` are the Gate-B test seeds.

## Phase choreography

State machine (intro): BOOT → TYPO → WALK → CRYSTAL → GLYPH → SEAM → SITE. States
must not jump arbitrarily. Cursor is a light-point "consciousness focus" with
physical easing — not a neon laser pointer. Phase colors carry meaning:
AWAKE=recognition, NREM=consolidation, REM=association, INSIGHT=insight,
EMBER=causality/critical transition, GREEN=valid/sparse, VIOLET=semantic activation.

## Pitfalls encountered

- Branch is `visual/cockpit-demo` (slash) — the Gigaplan writes `visualcockpit-demo`.
  Gate-A compare against the real branch.
- `prologue.mp4` (118 MB reference master) must stay gitignored
  (`website/media/film/prologue.mp4`); only `prologue-web.mp4` is web-usable.
- **The intro renders to a dedicated FULLSCREEN canvas, NOT the caller's canvas.**
  (commit `352224b`) `buildDom()` creates `#introCanvas` (`position:fixed;
  inset:0; width/height:100%`, stage bg `#050308`) and re-points every `ctx.*`
  call to `stageCtx`. The passed-in `#heroMaze` canvas is ONLY used by
  `completeIntro()` to hand the graph to `initMaze` after the scroll seam. If the
  intro draws into the hero's 60%-bleed canvas instead, the static SaaS skeleton
  stays visible around it → operator rejects it as "statischen Dreck".
- **Impatience cap must key off `walkStartedAt`, not `walkPhaseAt`.** The phase
  clock resets every 9–17s as phases advance, so a cap on `walkPhaseAt` never
  fires and the walk stalls on the last few unvisited nodes. Set a dedicated
  `walkStartedAt` in `beginWalk()` and cap on `now - walkStartedAt > 14000`.
- **Walk liveliness knobs** (the walk must never read as a static screen):
  wander acceleration `0.00055→0.0022`, idle-wander window `3500→1200ms`, node
  visit radius `110→150`, node maturation `2300→1200ms`, wander hold `900→380ms`.
- **Verify glyph determinism via `node` with a mocked canvas**: `glyph.js` is a
  browser UMD `(function(global){...})(window)`. In node, set `const window={};
  const global=window; eval(src)` and mock `canvas.getContext('2d')` with a Proxy
  that no-ops every method. Then assert same input → identical serialized result,
  different path → different result. (A raw `node --check` passes but can't run
  `renderGlyph` — it needs a real 2D context.)
- `website/media/` is now WIRED into the page (film=video, receipts, worlds) —
  NOT orphaned (see SKILL.md, commits `316d7bf`/`6127936`). Do not assume it's
  unused.
- Filenames are `kf_01`/`slide_00` (underscore), not `kf01`/`slide0` — a naive glob
  misses them and reports assets "missing" that actually exist.
