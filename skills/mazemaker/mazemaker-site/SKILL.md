---
name: mazemaker-site
description: Deploy, debug, and clean up the Mazemaker marketing site (127.0.0.1:8899, /home/alca/projects/showcase). Covers the three maze engine bugs (black void, no scroll, missing chambers), headless verification, AND the two recurring trash-tier annoyances (red flashing OFFLINE status, "cancer sound" ambient audio). Absorbs the narrower mazemaker-site-ops and mazemaker-showcase-cleanup skills.
---

# Mazemaker Site (8899 / showcase)

Class-level skill for the Mazemaker marketing/showcase site. The original narrow
skills `mazemaker-site-ops` and `mazemaker-showcase-cleanup` are absorbed as the
two sections below — same site, same server, different bug clusters.

## A — Site/engine ops (absorbed from `mazemaker-site-ops`)

### Context
`http://127.0.0.1:8899/` serves `/home/alca/projects/showcase/` via `python3 -m http.server 8899 --bind 127.0.0.1` (cwd = showcase).
The site is the rework maze experience: 12 chambers (hero, film, receipts, worlds, moat, dream, door, quickstart, pricing, faq, unseen, close), intro typing sequence (intro.js / MazeIntro), WebGPU/2D graph (maze-engine.js), React/Divjoy DOM world (inline `class Component extends DCLogic` in index.html + support.js runtime).

### Deploy rework → showcase
```bash
cd /home/alca/projects/showcase && mkdir -p _v1_archive && mv index.html index_2.html index_v1.html package.json package-lock.json lib assets node_modules _v1_archive/ 2>/dev/null
cp -r /home/alca/projects/rework/website/. .
rm -rf .git .claude _ds self-evolve
```
Add robots.txt + sitemap.xml. Old files → _v1_archive.

### THE THREE MAZE BUGS (all fixed 2026-08-09 in showcase/index.html)
The rework site ships with a black-void scroll death. Fixes:
1. **Intro handshake**: intro.js dispatches `maze:intro:complete`, but the React component never listened → `locked=true` forever, camera stuck on overview, chambers hidden. Fix: in `componentDidMount` add `document.addEventListener('maze:intro:complete', () => this.crystal(true))` + remove in unmount + 30s fallback unlock.
2. **World position**: world div must be `position:relative` (NOT fixed/absolute). The walk spacer inside must drive document scrollHeight — fixed/absolute worlds collapse the page to viewport height (docH = vh).
3. **Scroll compensation**: world transform needs `+window.scrollY` in the vertical translate:
   `'translate(' + vw/2 + 'px,' + (vh/2 + scrollY) + 'px) scale(' + s + ') translate(' + (-cam.x) + 'px,' + (-cam.y) + 'px)'`
   Without it every chamber drifts up out of the viewport when you scroll.
4. **frame() cvRef optional**: `cvRef` is declared but never bound → `frame()` early-returns on `!cv`. Change guard to `if (!world || !this.stations) return;` and wrap canvas drawing in `if (cv) { ... }` (maze-engine.js owns the graph canvas).
5. **command-bridge.js**: broken selector `document.querySelector('[style*="agent@maze:\\$"].closest("form")')` throws SyntaxError. Fix: query element first, then `.closest('form')`.
6. **dormantRate**: set default 0 in data-props (HTML-escaped `&quot;default&quot;:0`) so ALL chambers are lit — dark rooms are bad for a sales page.

### CTA navigation (marketing layer)
`window.__mzGoto(id)` walks the React fiber from `[data-ch="hero"]` to find the `logic` instance (`stateNode.logic` with `.frame`), then calls `logic.goTo(id)` (or `logic.crystal(true)` if still locked). Do NOT dispatch form submits — command-bridge owns the form and only handles RECALL/DREAM/WALK/WHO.

### Headless verification (CDP, node 26 global WebSocket)
- Launch: `google-chrome-stable --headless=new --disable-gpu --no-sandbox --remote-debugging-port=9222`
- Intro takes ~15-30s (typewriter is slow; headless rAF is throttled). Wait 30-35s before asserting post-intro state.
- Check: `logic.phase === 'site'`, `logic.stations.length >= 13`, `document.documentElement.scrollHeight > 8000`, `world.style.transform` non-empty, chamber rect centered (`getBoundingClientRect().y + h/2 ≈ vh/2`).
- Camera easing is slow in headless — force `logic.cam/tgt = station` before screenshots.

### verify.mjs
`RUNTIME-CENSUS.json` needs BOTH camelCase (census.js output) AND snake_case aliases (`body_class`, `engine_surface`) — verify.mjs reads snake_case. Capture live via `JSON.stringify(window.__census())` (sync, 900ms busy-wait) then add aliases. Node checks: `node --check assets/*.js support.js`.

### Pitfalls (site/engine)
- /tmp is a 16GB tmpfs — Chrome headless scoped dirs (163MB each) fill it fast. `pkill -f google-chrome.*headless; rm -rf /tmp/com.google.Chrome.*`
- grep in this shell is broken ugrep alias — use search_files tool for greps.
- Always re-capture census after editing assets (verify freshness check).

## B — Trash-tier cleanup (absorbed from `mazemaker-showcase-cleanup`)

### Trigger
User is furious about "red flashing trashtier on top" and "cancer sound" on
http://127.0.0.1:8899/ (serves /home/alca/projects/showcase/).

### The two recurring trash sources (2026-08-09, fixed)
1. **Red flashing status on top** — `app.js` polls `https://api.mazemaker.dev/api/health`
   every 30s. From localhost it always fails → header + hero eyebrow show a RED
   "OFFLINE · waking the maze" pill with pulsing red dot (`--err: #ef4444`).
   Fix: delete the status-dot-wrap from `assets/partials/header.html`, remove the
   `statusDotHero`/`statusLabelHero` spans from `index.html` hero eyebrow, and strip
   `checkHealth`/`initHealth`/`setStatus` from `app.js` (also remove `initHealth()`
   from `boot()`). The header is the shared partial — one edit fixes ALL pages.
2. **"Cancer sound"** — `assets/ambient-audio.js` starts a 55Hz sine drone +
   heartbeat LFO (70 BPM) on the FIRST click/touch anywhere. Fix: remove the
   `<script src="assets/ambient-audio.js">` tag from `index.html`. Nothing else
   references `window.ambientAudio`, so no breakage. Do NOT re-add it — user calls
   it cancer.

### Verification (must be measured, not claimed)
1. DOM check:
   `google-chrome-stable --headless=new --disable-gpu --no-sandbox --user-data-dir=/tmp/x --virtual-time-budget=8000 --dump-dom "http://127.0.0.1:8899/"`
   → grep for `statusDot|statusLabel|OFFLINE|waking|ambient-audio` must return 0.
2. Pixel check for red in header band (top 18%) — must be 0 red px:
   PIL: crop (0,0,w,h*0.18), count pixels with r>150,g<90,b<90.
3. `node verify-hero.mjs` → heroStats has nodes>0, JS ERRORS (0).
4. Console via `--enable-logging=stderr --dump-dom` — no errors except benign
   WebGL/headless warnings. CORS noise from seats endpoint: app.js now stops
   polling after first failed check (dataset.failed=1).

### Pitfalls (cleanup)
- `verify.mjs` (root) is STALE — it expects v2-era `data/graph.json` +
  `assets/style.css` and crashes. Use `verify-hero.mjs` for the current build.
- The page loads three.js from CDN (jsdelivr importmap) — headless screenshots
  may hang on it; use `--virtual-time-budget` and a timeout.
- `--err/--ok/--warn` ARE defined in style.css (lines 71-73) — grep with `-e` or
  the `--` separator or search_files, plain `grep -n '--err'` mangles args.
- User hates stacked scripts: don't "fix" by adding another script; remove or
  neutralize the offending code instead.
