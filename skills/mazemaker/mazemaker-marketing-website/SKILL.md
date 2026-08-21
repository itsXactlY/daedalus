---
name: mazemaker-marketing-website
description: Mine the maze first when redesigning the Mazemaker site.
category: mazemaker
---

# Mazemaker Marketing Website — Mine the Maze First

## THE governing rule (operator-corrected 2026-08-01, forceful)

When asked to redesign or "come up with a full idea for" the Mazemaker website, the
FIRST move is **discovery of what already exists — NEVER invention.** The operator's
exact words when an agent pitched a fresh concept instead of using the on-disk
assets:

> "STOP GUESSING, FOR WHAT DID I GAVE U ALL THE INFOS?" ... "use mazemaker, recall
> everything about the trailer, marketing, everything what matters the deeper u walk
> the maze ... dig much much deeper into the maze, there are gigabytes produced
> artwork. everything what matters is inside mazemaker. all preferences, everything!"

Inventing a palette, voice, narrative, or metric out of thin air is the failure mode
this skill exists to prevent. Every number, every visual, every proof point already
exists somewhere in the maze or on disk — find it, don't fabricate it.

## Source of truth & layout

**CRITICAL (operator-corrected 2026-08-01): the NEW site is NOT on `main`.**

- Live site: `https://mazemaker.online`
- Repo: `github.com/itsXactlY/mazemaker-v2-frontend`
- **THE REAL NEW-THEME SITE** lives in a git **worktree**:
  `~/projects/mazemaker-v2-stack/frontend/.claude/worktrees/design-import/website/`
  on branch **`design/site-rebuild`** (commit fbd5be5). This is the current
  theme — do NOT build against the old `main`.
- Old/legacy source: `~/projects/mazemaker-v2-stack/frontend/website/` (branch
  `main`) — stale, superseded. A rebuild touching this tree is building the wrong thing.
- Deploy intent (per `REDESIGN-NOTES.md`): copy the worktree `website/` tree over
  `frontend/website/` and push to `main` when happy. The worktree is the active base.

### Verify which tree you're in BEFORE building

An agent forked `visual/immersive-rebuild` off `main` and built the whole demo in the
OLD tree before the operator corrected the path. **First action: `git worktree list`
and confirm the worktree branch.** Fork off `design/site-rebuild`, never `main`.

### DUAL-PATH WORKTREE TRAP (operator-corrected 2026-08-02, forceful — "DAS ALLES, /home/alca/projects/rework")

The fork worktree is reachable via **TWO different directory paths that are NOT the
same files**:

- `/home/alca/projects/rework/site-visual-fork/` — **THE OPERATOR'S WORKING PATH.**
  `SCHLACHTPLAN.md` lives in `/home/alca/projects/rework/`. This is where the work
  belongs and where the operator looks.
- `/home/alca/projects/mazemaker-v2-stack/frontend/.claude/worktrees/site-visual-fork/`
  — the git-admin path. Same gitdir (`frontend/.git/worktrees/site-visual-fork`),
  same branch, same commits — **but the on-disk working files DIVERGE.**

Both `.git` files are the identical one-liner `gitdir: ...`, so `git` considers them
one worktree — but `realpath` proves two separate directories with independent file
contents. A file written via one path is NOT visible via the other until committed.
This silently corrupted the session: the HTTP server + browser tested the
mazemaker-v2-stack copy while the real work (and a parallel OpenCode session) lived
in rework; commits landed on the shared git history so both `git log` looked right,
while `git status` and file contents disagreed.

**Rules that prevent the trap:**
1. Work and serve from `/home/alca/projects/rework/site-visual-fork/website`.
   `python3 -m http.server` MUST be started with `cd ~/projects/rework/site-visual-fork/website`.
2. When browser tests show a stale/wrong page, verify what the server actually
   serves: `curl -s http://127.0.0.1:PORT/index.html | wc -c` and
   `ls -la /proc/<server-pid>/cwd` — not the git log, which is shared.
3. Before/after edits, confirm sync: `cmp <(cat rework/.../index.html)
   <(cat mazemaker-v2-stack/.../index.html)` or byte-compare via `execute_code`.
4. If `git status` in one path shows changes you didn't make, a PARALLEL AGENT is
   writing through the other path — see the parallel-session section below.

### PARALLEL AGENT in the same worktree (2026-08-02)

An OpenCode session (`opencode -s ses_040ff3...`, PID visible via
`ps aux | grep opencode`) was running concurrently in the same git worktree and
silently: deleted `pod.js`/`pod-ui.js`, added `worlds.js`, edited `intro.js`/
`film.js`/`index.html`, copied `prologue.mp4`. Symptoms: uncommitted changes in
`git status` you never made; the page "changing itself"; divergent file sizes
between the two paths. Never keep writing into a worktree another agent is
actively using — the two writers corrupt each other's files.

Handle it cleanly:
1. Snapshot the other agent's work so nothing is lost, then get back to your state:
   `git checkout -b opencode-wip-YYYYMMDD && git add -A && git commit -m "wip: parallel-session snapshot"`
   then `git checkout visual/cockpit-demo` (the branch is back on YOUR last commit,
   working tree clean).
2. If the other path holds a stale working copy of a file (older than your commit),
   reset it so both paths agree: `git checkout -- website/index.html` from the
   other path (its diff is stale by definition), or save the diff first as a patch
   file (`git diff > /tmp/...patch`) before discarding.
3. Do NOT continue editing until the conflict is resolved; write your changes
   through the rework path only and re-verify sync.

### The WebGPU rebuild — "CUTTING EDGE FROM SCRATCH" (2026-08-02, final accepted direction)

The operator's bar escalated twice in one session: first "no static shit" (fixed by
fullscreen walk), then the pod (page IS the product), then, after pasting the
Bonsai WebGPU references (`huggingface.co/spaces/webml-community/bonsai-image-webgpu`,
`bonsai-webgpu-kernels`), the verdict was: **stop patching the old page entirely —
rebuild from scratch, WebGPU, like the reference.** Verbatim: *"DU BEHINDERTER AFFE
SOLLST DAS NICHT AUF DEIN STATISCHEN DRECKSMÜLL ÜBERTRAGEN! CUTTING EDGE FROM SCRATCH
FFS"* and *"WAS IST DAS FÜR ABARTIGER SCHWACHSINN? /home/alca/projects/rework DAS
ALLES, CUTTING EDGE, WEBGPU, BASTARD!"* Two instructions, both hard: (1) the work
belongs in `~/projects/rework` (see dual-path trap), (2) the page must be rebuilt
new with real WebGPU, not enhanced old HTML.

The accepted result (commit `524018e`, from-scratch `index.html`):
- **Warm-dark Bonsai identity**: bg `#0c0a08`, cream `#f4ecde`, amber `#e8a55e`,
  green `#7fb069`, red `#c96f5a`; Instrument Serif for display, Geist + Geist Mono
  for UI/code; `body opacity:0 → .loaded opacity:1` fade-in.
- **Real WebGPU compute scene**: `#gpuScene` full-viewport fixed canvas; WGSL
  compute shader integrates N=1400 particles on the GPU (uniform params buffer,
  storage pos+vel buffers, `dispatchWorkgroups(ceil(N/64))`), instanced-quad
  vertex render with mouse-repulsion field and amber→green hash palette. The
  renderer is DISCLOSED in the stats strip (`renderer: webgpu | canvas2d`) —
  no fake GPU claims.
- **Honest fallbacks**: `navigator.gpu.requestAdapter()` missing/failed →
  CPU canvas-2d fallback (~220 particles); `prefers-reduced-motion` → no
  simulation at all (static, label "static"). The badge reads "running locally
  · webgpu" or "· canvas2d".
- **The page IS the pod**: landing composer (form / contradict / dream / recall)
  against the real `pod.js` engine (persistent via sessionStorage), then the
  evidence sections (receipts, film, six worlds) below.

Reference-fidelity notes from the Bonsai pages: their flow is Landing (hero-scene
canvas + CTA) → Gate (token) → Loading (real % readouts) → App (prompt + controls +
output, "running locally" badge). A product page for an in-browser engine should
follow that arc, not a marketing scroll.

Verification limits to report honestly: headless browsers have NO GPU adapter
(`navigator.gpu.requestAdapter()` → null), so only the canvas-2d fallback can be
browser-tested there (frames differ = animating); the WebGPU/WGSL path is
structurally verified (markers + syntax) but needs the operator's RTX-4060-Ti
machine for real execution.

### The new-theme design differs from the old (do not reuse old-token assumptions)

- New `style.css` is **135 KB** (old was 79 KB) — a far richer design system.
- **H1 = "Your agents stop forgetting."** ("operating system for AI agents" is now the tagline).
- Hero visual = `architect-room.webp` labeled `architect.mazemaker.dev · 12 monitors ·
  loopback data`, plus a **spec-rail** of 6 live benchmark metrics in the hero.
- New tokens: `--text-dim` `#8a8a97` (5.8:1 WCAG fix, NOT `#5e5e6b`),
  `--accent-fill` `#7f4ff2` (solid fills w/ white text), `--on-accent` `#fff`,
  `--ember` `#d1552b` = "the one warm voice" (hero wash, image rim, install block,
  section marks ONLY — never on controls), `--t-h1` up to 6rem, `--r-pill` 999px.
- Two docs govern it: `REDESIGN-NOTES.md` (design rules) and
  `LAUNCH_PAYLOAD_VIRAL_FACTS.md` (the definitive facts DB — every number, verified).
  See `references/new-theme-and-viral-facts.md`.

## Discovery checklist (run BEFORE any proposal — every item is a real, verified asset)

1. **`mcp__mazemaker__mazemaker_recall` the trailer/marketing/visualization history
   first.** Label prefixes to target: `commit:*` (e.g. commit:0808807), `ops:*`,
   `fact:*`, `auto:turn:*`. Recall surfaces decisions, the design commit, and past
   marketing attempts.
2. **`/home/alca/projects/video/lab/`** — the produced cinematic trailer production
   (33 MB). See `references/trailer-production-inventory.md` for the full file map:
   - `trailer-v19.html` — the final, self-contained 1920×1080 HTML/CSS/JS film
     (113s, Web Audio synth soundtrack, poster click-to-play, film-grain/vignette/
     glitch/bomb-drop receipts), with 23 versions (v12–v19, viral, ultimate, fomo,
     claude, geminipro, gpt55).
   - Soundtrack masters: `master.mp3`, `master-v14/14b.mp3`, `master-extended.mp3`,
     `trailer-soundtrack.wav/.flac`.
   - `shots-launch/` — 21 storyboard PNGs across the full act0→act5 arc.
3. **`mazemaker-pro/assets/`** — `cover_video.mp4` (9.7 MB), `cover.png`,
   `neural_brain_hero.png`, `hermes_mind.png`, `brain_krang.png`.
4. **`~/projects/mazemaker-architect/public/`** — the three `maze-crew-*.html`
   Three.js visualizations (bio/dream/trailer), iterated by the `maze-crew-loop`
   cron. Interactive-motion candidates.
5. **The site's own copy** is the moat-messaging source of truth. See
   `references/website-moat-messaging.md` for the exact AES terminology, Alpine-
   on-phone claims, and benchmark wins already written in `index.html`,
   `architect/index.html`, `app/index.html`, and `comparison/index.html`.

## Locked design language (from commit:0808807 — do NOT invent a new one)

- **shadow-as-border** — zero `border:` in the design layer; elevation via
  `box-shadow: 0px 0px 0px 1px rgba(...)` and luminance stepping
- **Compressed display type**, weight 600 max (no weight 700 anywhere)
- **Violet `#8b5cf6`** on interactive elements ONLY; **ember `#d1552b`** as a second
  voice in exactly four places
- **Hairline rows instead of boxes**; tokens live in `:root` of `style.css`
- **"Mazemaker Oracle" voice** — declarative, confident, no hedging
- Honor `prefers-reduced-motion`; keep tokens in `:root`
- Drift trap: `paper.html` and `docs/assets/docs.css` carry their own token copies —
  a colour change must propagate to all three (see the `mazemaker` skill /
  invariant `paper-html-own-tokens`)

## Current visual state (verified 2026-08-01)

The LIVE tree (`main`) has ZERO self-contained motion today: the hero is a static
`mazemaker-hero.webp` (900×900) with only a slow CSS `brainDrift` rotate; there are
no `.mp4/.webm` anywhere in the website tree. This is the gap the rebuild closes —
and the raw material to close it already exists in the video lab + maze-crew files.

**The FORK (`visual/cockpit-demo`) holds the motion work**: a shared
`assets/maze-engine.js` (self-contained `initMaze` canvas engine) and the
hero-integrated living maze. The live `main` is untouched. NOTE: an earlier
standalone `demo/index.html` + iframe wiring was **rejected** by the operator as
"awful pathetic / 99.9% worse" — the accepted direction is integrating the maze
into the site's own archetypes (see "Wire the maze into the new index.html" below).

**The NEWEST fork `visual/top-notch` (2026-08-12, commit 3828071, worktree
`/home/alca/projects/mazemaker-website-fork`, forked off `design/site-rebuild`
fbd5be5)** layers the cockpit-demo motion onto the NEW theme: the hero's static
`architect-room.webp` plate is REPLACED by the living maze canvas (same
`assets/maze-engine.js`, real share-safe memory seeds, phase+path/edge readout
in the hero-visual-label, reduced-motion STATIC path), and a new **Section 00
"The pod, live"** embeds the in-browser mini-pod engine (`pod-demo.js`) directly
into the site — formation with edge discovery, contradict→supersession,
3-phase dream, one-hop recall boost, sessionStorage (`mzTopNotchPodV1`), zero
network. Same locked tokens (violet interactive-only, ember = trace voice,
shadow-as-border, hairline rows, weight ≤600). This is the fork that would be
copied over `frontend/website/` + pushed to main per REDESIGN-NOTES.md.

## Messaging spine (proven pattern)

Map every visual to a beat that is ALREADY WRITTEN in site copy. The one-sentence
story (verbatim from `index.html`): **"Your agents die every conversation. Mazemaker
keeps them alive — with evidence, not vibes."**

Six beats, all sourced from existing copy:
1. Death/rebirth loop (hero)
2. Memory formation, not retrieval
3. Dream consolidation (background work while they sleep)
4. Conflict supersession (the mind-changes beat)
5. The knowledge-graph filesystem (walk, don't search)
6. The proof (benchmarks, trust)

Three underrated moat pillars a rebuild MUST surface:
- **Sandboxed Alpine-native Hermes on an unrooted phone** ("the part nobody else ships")
- **AES-256-GCM at-rest terminology** (the full encryption story)
- **Named competitor benchmark wins** (never invent numbers — they're all real)


<!-- moved to references/moved-sections.md: ## The Gigaplan (visualcockpit-demo) — the CURRENT active build plan -->

## Workflow / fork pattern

**Verification pattern for this static-vanilla project (no test runner):** the
project has no canonical suite/lint/build command, so verification is
**ad-hoc throwaway scripts**: create `/tmp/hermes-verify-*.py` (or `.mjs`), run it
against the changed state, then delete it. Include: HTTP 200s on all served
assets, tag balance in the HTML, `node --check` on JS, pod-engine mechanics
exercised via node (form → recall → supersede → dream → determinism), and
worktree sync (byte-compare index.html across both paths). Two script bugs to
avoid — both produced FALSE failures this session:
1. When a `.mjs` helper reads a path passed on the command line, use
   `process.argv[2]` — with `node helper.mjs <path>`, argv is
   `[node, helper.mjs, path]`; `argv[1]` silently reads the helper itself.
2. `<input>`, `<img>`, `<br>`, `<source>`, `<meta>`, `<link>` are VOID elements —
   they have no closing tag; a naive open/close balance check flags them as
   mismatched. Exclude void tags from the balance check.

**Verification when `vision_analyze` is DOWN (OpenRouter credits 402, 2026-08-12)**
— do NOT block on the vision API; replace it with a measured pixel protocol that
proves each visual claim:

1. **Animation = frames differ**: two headless screenshots at different
   `--virtual-time-budget` (e.g. 2000 vs 5000 ms) of the same URL, then PIL
   pixel-diff ratio in the animated region (sample every 3rd px). `>0` (we saw
   1.82% on the hero maze) = the canvas is animating. Keep budgets far apart so
   a slow boot doesn't produce identical frames.
2. **DOM / JS actually loaded**: `--dump-dom` + grep for the presence markers
   (`id="heroMaze"`, `pod-demo.js`, `maze-engine.js`, populated phase label,
   spec-rail text, JSON-LD types). Screenshot bytes are NOT proof the page ran.
3. **Reduced-motion freeze path**: re-run dump-dom with
   `--force-prefers-reduced-motion`; assert the phase label reads `STATIC` and
   the stats note appears — proves the accessibility path, not just the main path.
4. **Canvas graph rendered**: count color-family pixels in the crop where the
   graph lives (violet family: `b>180, r<200, g<160, b-max(r,g)>60`). We saw 5102
   violet px in the pod region = nodes drew; ember ≈ 48 px = the single warm
   voice is restrained, not a flood.
5. Report the caveat honestly in the commit: "vision unavailable — pixel-level
   verification used instead."

Pitfall: a PIL diff inside `execSync` inside a `.mjs` try/catch can print NOTHING
(exception swallowed, buffer not flushed) — run the diff as its own standalone
`python3 -c` so its output is visible, or check the catch prints.

**Pod-engine functional test — build the hook INTO the module instead of
string-injection**: `pod-demo.js` exposes `window.PodEngine` with a guarded
`_test()` that runs the full suite (formation threshold edges, duplicate
rejection, REM bridge sim×0.3, supersession dead-edge marking, recall one-hop
boost, persistence, reset) and returns `{passed, failed}` — 14/14. Then a tiny
node harness requires the module in a VM-ish context and asserts
`PodEngine._test().failed === 0`. No IIFE surgery, no fragile string insert
before `})();`, and the test stays versioned with the engine. Keep the harness
ad-hoc (`/tmp/mz-engine-test.mjs`, delete after).

**CRITICAL SAFETY (operator-corrected 2026-08-01, forceful — "USE UR OWN BROKEN
DIPSHIT FORK"): NEVER edit files inside the live `design-import` worktree. The
`design-import` worktree is the OPERATOR'S LIVE new-site files; it must stay on
`design/site-rebuild`, CLEAN, at all times.**

The WRONG pattern (what happened and provoked fury): checking a fork branch out
*inside* the live worktree and editing its files on disk. Even on a separate
branch, the files on-disk are the operator's live files — that is production to
them. Committing the work then `git checkout design/site-rebuild` restores it, but
the violation already happened.

The CORRECT pattern — a **truly separate worktree**, so fork files never live in
the live directory:

```bash
cd ~/projects/mazemaker-v2-stack/frontend
# create a separate worktree for the fork (never inside .claude/worktrees/design-import)
git worktree add /home/alca/projects/mazemaker-website-fork -b visual/<name> design/site-rebuild
cd /home/alca/projects/mazemaker-website-fork
# ... work entirely in this directory ...
```

Rules:
- Fork off `design/site-rebuild`, never `main` (old tree).
- Never `git checkout -b ...` inside the live `design-import` worktree; never edit
  files under `.claude/worktrees/design-import/website/` directly.
- Keep the live worktree on `design/site-rebuild`, clean, at all times. Verify with
  `git -C .claude/worktrees/design-import status --short` (empty = pristine).
- Never `git push`, never merge, never touch prod `main`. Draft-only worker.
- Sanity check before/after: `git -C <fork> log --oneline design/site-rebuild..visual/<name>`
  shows your fork commits; confirm they are NOT an ancestor of `design/site-rebuild`
  (`git merge-base --is-ancestor ...` should fail).

1. Real git fork off the **new-site worktree branch** (`design/site-rebuild`) via a
   separate worktree (above). Stash any dirty tree first (`git stash push -u`).
2. Produce procedural motion (canvas / Three.js) for abstract beats; reuse the
   existing `cover_video.mp4` + storyboard PNGs as real media where they fit.
3. Verify with the browser (screenshot/vision), check contrast + reduced-motion,
   then ship the branch/PR.

## Interactive cockpit demo (Option C — "peek behind the closed door")

The operator's preferred shape for showing off the moat: a **guided, interactive
demo** rebuilt from the REAL live Architect, seeded with real cherry-picked memories
from the maze — not a static mock, not a screenshot. Two accepted shapes:
- (C1) an interactive cockpit like `architect.mazemaker.dev`; or
- (C2) a guided walkthrough where visitors explore but the narration steers them.

### The real Architect source to rebuild from

The live cockpit source is at
`~/projects/mazemaker-v2-stack/backend/client/pod/wonderland/architect/src/`:
- `main.js` — boot: `detectGate()` first; if denied render the preview-room (Alice +
  the door), else `bootLive()`.
- `maze-panel.js` — **the "living maze"** 2D-canvas engine (prime hero visual):
  constellation clustering, flowing edge particles, phase states AWAKE/NREM/REM/INSIGHT.
  Edge colors `EC = {bridge:#76d9ff, causal:#FF8C00, supports:#00FA9A,
  supersedes:#FF4444, default:#BF00FF}`; label colors `decision:#FF8C00 bug:#FF4444
  fact:#00FA9A ops:#DA70D6 …`. **It has a `generateSynth()` fallback** that draws a
  gorgeous maze with no pod — ideal for a marketing demo that embeds real memories as
  node labels over synthetic edges (zero pod needed at build time).
- `monitors.js` — the `PANELS` registry (M01–M12 + `peek()`/`enter()` contract).
- `wonderland.js` — talks to `127.0.0.1:8765`.
- Bridge sidecar: `mazemaker-hermes-bridge.py` on `:8769`.

### The 12 monitors + 4D layers (copy verbatim from the site's architect page)

M01 RECALL, M02 DREAM, M03 EDGES, M04 TOP, M05 SSNS, M06 PEERS (deferred), M07 TOOLS,
M08 HERMES, M09 INCPT, M10 MIRROR, M11 CHRONO, M12 KEYS. 4D layers: CHRONO-SCRUB,
DREAM REPLAY, AUDIBLE MATRIX (Web Audio), PHASE STATES, EDGE TENSION.

### Seed with REAL, share-safe memories

Use public-label memories only (never `private:`/encrypted): `decision:`, `bug:`,
`ops:`, `fact:`, `project:`, `skill:`. Pull via `mazemaker_recall_multi` on the moat
topics. Good verified seeds: `rc8 is canonical head` (engine release), `one-character
tool name` (the single-underscore bug), `swallowed exception` (recall_advanced
TypeError), `pod self-heal armed` (self-heal layer), `recall_advanced surface gap`,
`over rollback, ship to backend` (velocity principle).

### Two JS pitfalls that bite when building the cockpit demo

- **Apostrophes inside single-quoted JS strings break syntax** (`won't`, `can't`,
  `it's` terminate the string). Use **backtick template literals** for any body/seed
  string containing an apostrophe. Always run `node --check` on the extracted inline
  `<script>` before browser-verifying — the maze boots, but the wall/receipts silently
  die if the script threw early.
- **Duplicate HTML `id` wipes sibling sections.** The demo had `id="wall"` on BOTH the
  `<section>` and the inner monitor `<div>`; `getElementById` returns the first, so
  `renderWall()` emptied the whole section including `.focal`. Give the inner container
  a unique id (e.g. `monitor-wall`) and reference that in JS.

### Wire the maze into the new index.html — INTEGRATE, don't bolt (Phase 3, corrected)

**Operator-corrected 2026-08-01, forceful: "visuals == KING" — the iframe-bolted
demo was rejected as "awful pathetic / 99.9% worse than worse shit."** The failure
was building a standalone `demo/index.html` with its OWN hand-rolled CSS and
embedding it via iframe — a *stranger*, not a member of the site's design family.
The lesson: **the maze must be a first-class citizen of the site's OWN archetypes,
and the hero should BE the maze.**

The pattern that satisfies "visuals == KING":

1. **Extract the maze engine into a shared asset** `assets/maze-engine.js`
   (self-contained `window.initMaze(canvas, { memories, interactive, onPhase,
   onOracle })` — a faithful 2D-canvas rebuild of the Architect's `maze-panel.js`,
   with the `generateSynth()` fallback so it renders with no pod). Load it
   `<script src="assets/maze-engine.js" defer>` before `app.js`.
2. **Make the HERO the living maze.** Drop a `<canvas id="heroMaze">` into the
   existing `.hero-bleed` slot (where the static `architect-room.webp` picture sits)
   and boot it with `initMaze(...)` — same hero CSS, but a real memory graph in
   motion behind the scrims. Update the `hero-visual-label` to read `the living
   maze` + a live `#heroMazePhase` readout fed by `onPhase`.
3. **The "behind the door" section uses the SITE'S archetypes**, not new classes:
   `.section-mark`, `.head-split`, `.essay-cols` / `.essay` / `.essay-kicker`,
   `.index-list` / `.index-row` (monitor walk-through rows), `.figures` (telemetry
   rail), `.btn-row`. Add the minimal scoped CSS to `style.css` (`--hero-bleed
   canvas` sizing, `prefers-reduced-motion` freeze) — **styling belongs to the
   sheet, never inline `style=`** (REDESIGN-NOTES rule).
4. A full standalone interactive page is fine as a *deep link* (e.g. `./demo/` for
   the guided tour), but the homepage must integrate the maze directly.

Verify: `node --check` the extracted inline `<script>`, confirm
`<section>`/`</section>` still balanced in `index.html`, confirm `app.js` + `nav.js`
still load, browser-check zero JS errors, and confirm the maze booted (`window.__heroMaze`
set, phase element populated). Keep the demo commit and the wiring commit separate.
Fork branch `visual/cockpit-demo` holds the work (`fdee430`, `0f9360a`, `bb22908`).

### Autonomous loop — NEVER let it touch live (Phase 4, safety-critical)

The paused cron `mazemaker-website-autonomous-loop` (job `45c6e4cb98ec`) is a real
autonomous website-editing agent. When reviving it, the operator's rule is
**"never break the live systems."** Two hard facts learned:

1. The job carries **`openrouter_free` / `claude-sonnet-4`** — the deprecated provider
   the operator's config says never to recreate, and the cron `update` tool does NOT
   expose a model/provider override. It must be **deleted and recreated** (default model)
   to change provider — an `update` won't do it.
2. **Leave it PAUSED unless the operator explicitly approves resume.** Repointing
   `workdir` to the fork + writing hard guardrails into the prompt (work ONLY in the
   fork worktree, NEVER touch live `frontend/website`, NEVER `git push`/merge/checkout
   `main`/deploy — draft-only worker on `visual/cockpit-demo`) is necessary but NOT
   sufficient: the stale deprecated-provider config means it must not run unattended.
   Report the state and let the user decide.

## Standalone showcase conversion page (~/projects/showcase, 2026-08-09)

Operator: "create a *never seen before* index.html with excellent SEO + must-buy-now psychology, put it into ~/projects/showcase/, never break the live systems." It must NOT copy mazemaker.online — same locked design DNA, but built purely as a selling machine. Pattern that shipped (production build, 43 KB, single self-contained file):

- **The page IS the product** — section 00 embeds a LIVE mini-pod: in-browser token-overlap engine (max(jaccard, coverage*0.75)), formation (edges > 0.18), contradict (supersedes + dead edges), 3-phase dream (NREM strengthen + REM bridge), recall with one-hop edge boost, sessionStorage persistence (`mzPodV2`), seeded from share-safe facts. Canvas graph draws edges + live nodes. THIS is what makes it "never seen before" — the visitor operates a working miniature.
- Psychology layers (not shouted): loss aversion ("Every closed tab is a lobotomy", "money set on fire"), pattern interrupt (red strikethrough on "Every. Single. One."), social proof (100/100 Builder seats SOLD, GPT-5.5 "v2 NO → v8 UNCONDITIONAL YES", 94.0%), specificity (every number verified from LAUNCH_PAYLOAD_VIRAL_FACTS.md), anchoring ($29 was $49, $9 was $15, $0 forever), scarcity (honest 4h sessionStorage countdown, "11 of 11 Pro seats"), risk reversal ("keep the $0 tier forever, no lock-in, key never leaves your machine"), objection FAQ.
- SEO: SoftwareApplication + FAQPage + BreadcrumbList JSON-LD, OG/Twitter, canonical → mazemaker.online, one h1, semantic tree, details for FAQ, lang=en.
- Ember discipline: exactly 4 places (hero wash, section marks, brand dot, install block) — urgency/timer text uses violet2, not ember.
- Verify: `node --check` inline JS, tag balance (exclude void tags), no duplicate ids, HTTP 200 loopback, and a NODE FUNCTIONAL TEST of the pod engine (form→recall→contradict→dream→reset) by injecting the test INSIDE the IIFE before its final `})();` (closure vars aren't visible outside). Always `process.exit()` in the test or the countdown setInterval keeps node alive → timeout.

## Pitfalls

- **Never invent benchmark numbers, AES claims, or phone/on-device capabilities.**
  They are all real and already written in the site copy — pull them verbatim.
- **Do not propose a fresh visual identity.** The design language is locked; a
  rebuild layers motion/imagery onto the existing tokens, it does not replace them.
- **`_v1/` served publicly with dead asset paths** — don't reintroduce; the frozen
  snapshot should not be deployed.
- **`research.html` links `./blog/beam-10m-conv-1-multirecall/`** which has never
  existed (pre-existing on main) — flag, don't silently fix.
- **`newsletter/index.html` loads Plausible, contradicting `privacy/index.html`\n  section 2** — pre-existing; flag.

## Deployment

- **NEVER use `deploy-pages.sh`** — it contains `***` sanitization damage (broken API keys).
- Always deploy via wrangler directly:
  ```bash
  cd ~/projects/mazemaker-v2-stack/frontend
  wrangler pages deploy dist-online --project-name=mazemaker-online --branch main
  ```
- The build step is `scripts/build-pages.sh` which copies the website tree into
  `dist-online/`. Run that script first, then deploy with wrangler.

## Wire the Mazemaker MCP into OpenCode (verified 2026-08-01)

When the operator wants the pod's 31 `mcp__mazemaker__mazemaker_*` tools inside **OpenCode** (a separate CLI coding agent), use OpenCode's own MCP CLI — do not hand-edit its JSON.

```bash
export PATH="$HOME/.opencode/bin:$PATH"   # opencode often lives here, not on PATH
opencode mcp add mazemaker --url "http://127.0.0.1:8765/mcp"
opencode mcp list        # → "✓ mazemaker connected"
```

Writes `type: "remote"` into `~/.config/opencode/opencode.jsonc`. Pitfalls:

- **`mcp list` "connected" proves only the transport, not tool-call success.** A server can initialize and list tools yet fail at actual invoke. If the agent can't call a tool at runtime, re-point the same server at `/sse` instead of `/mcp` (both respond 200 here) and re-test.
- **Probe a remote MCP before wiring it** — a bare `POST /mcp` with an `initialize` JSON-RPC body returns 200 + an SSE `event: message` frame on a healthy pod. Wire only a live endpoint.
- **`opencode mcp add` manages the MCP server list only** — no model/provider override on that command.
- The loopback `127.0.0.1` URL works because opencode runs on the same host; no auth to configure for a local pod. Only add `--header` when the server actually needs it.

## The dump.txt — previous session history (2026-08-02)

`/home/alca/projects/rework/dump.txt` (4772 lines, ~1MB) is a raw OpenRouter API
conversation log from the previous session. It contains the FULL history of what
was built (walk intro, receipts, worlds, film, FAQ), all 25/25 verification gates
passing, the user's verdict ("lichtjahre von NICHT statischem müll"), and an
unfinished attempt to build a persistent full-viewport living background (session
died with BadRequestError before shipping). **Read completely** when the user
points to it — see `references/session-dump-reading-pattern.md` for the pattern.

## Parallel sub-agent delegation for multi-file website reworks

When reworking multiple pages under the new-theme design system, delegate safely:

### Safe to delegate (sub-agents can work independently)
- **Sub-pages** (`architect/index.html`, `comparison/index.html`, `privacy/index.html`,
  `architecture.html`, `paper.html`) — each has self-contained content and references
  `style.css` from the parent directory. Sub-agents mine existing copy, apply new-theme
  tokens, output a complete HTML file.
- **Supporting assets** (`maze-engine.js`, `pod-demo.js`) — if they're standalone JS
  modules with no dependency on other pages' structure.

### Central control (do NOT delegate)
- **`style.css`** — the design system root. All sub-pages reference it; changing tokens
  in one file requires updating ALL of them. Write this yourself.
- **`app.js`** — shared controller that wires nav highlighting, smooth scroll, and
  reduced-motion detection across all pages. Changes cascade.
- **`index.html` hero section** — the maze canvas integration touches multiple parts
  of the page (canvas element, init script, phase label, spec-rail). Keep ownership.

### Tag balance verification gotcha

A naive `<tag>` count check produces FALSE positives on:
1. **SVG inline elements** (`<line>`, `<polyline>`, `<circle>`, `<path>`, `<rect>`) —
   these are valid in HTML5 when inside `<svg>`, but a regex counting all `<word>` matches
   flags them as unbalanced. Exclude SVG content from the balance check, or strip `<svg>...</svg>`
   blocks before counting.
2. **JS variable names** (`<rows`, `<nodes`, `<count`) — if a regex is naive enough to
   match `var rows = ...` as `<rows`. Use a proper HTML parser or strip `<script>` blocks
   first.
3. **HTML comments containing tag-like text** (`<!-- <script> -->`) — the comment contains
   `<script>` which a regex counts as an opening tag. Strip comments before counting.

**Correct verification pattern:**
```python
# 1. Strip HTML comments
html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
# 2. Extract and remove script/style blocks
html = re.sub(r'<script[^>]*>.*?</script>', '%%SCRIPT%%', html, flags=re.DOTALL)
html = re.sub(r'<style[^>]*>.*?</style>', '%%STYLE%%', html, flags=re.DOTALL)
# 3. Count remaining open/close tags, exclude void elements
void_tags = {'area','base','br','col','embed','frame','hr','img','input','link','meta','param','source','track','wbr'}
# 4. Report only non-zero counts for non-void tags
```

## References
- `references/session-dump-reading-pattern.md` — how to read the dump.txt and what it contains
- `references/webgpu-hero-scene.md` — the from-scratch WebGPU compute scene
  (commit 524018e): WGSL compute+render pipelines, uniform/storage buffers,
  instanced-quad vertex render, CPU fallback, disclosure + verification limits.
- `references/walk-engine-implementation.md` — the living-maze walk engine
  (intro.js/glyph.js/maze-engine.js): seed system, opening pool, determinism
  contract, phase choreography, and pitfalls. Read before continuing Phase 1/2.
- `references/trailer-production-inventory.md` — the video lab file map (trailer
  versions, soundtrack masters, act0→act5 storyboard PNGs) and the trailer narrative.
- `references/website-moat-messaging.md` — the three moat pillars with the exact
  copy/terminology already in the site (AES, Alpine-on-phone, benchmarks).
- `references/new-theme-and-viral-facts.md` — the NEW worktree theme's design system,
  token deltas vs old `main`, and the `LAUNCH_PAYLOAD_VIRAL_FACTS.md` numbers (every
  benchmark/AES/pricing fact, verified). Read before quoting any figure.
