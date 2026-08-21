# mazemaker-marketing-website — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## The Gigaplan (visualcockpit-demo) — the CURRENT active build plan

As of 2026-08-02 the visual-rebuild work runs under a formal **Gigaplan** document
("MAZEMAKER — HELLO AGENT", an elaborate site-as-living-art brief). It governs the
walk-engine phase work. Two hard facts that differ from earlier sessions:

- **The active fork is now a worktree INSIDE `.claude/worktrees/`**: the isolated
  fork is `~/projects/mazemaker-v2-stack/frontend/.claude/worktrees/site-visual-fork`
  (a **sibling** of `design-import`, NOT inside it — still pristine-safe).
- **Branch is `visual/cockpit-demo`** (WITH the slash). The Gigaplan text repeatedly
  writes `visualcockpit-demo` (no slash) — the plan's name is wrong vs the real
  branch. Any Gate-A check (pwd + branch) must compare against the REAL
  `visual/cockpit-demo`, or it will falsely fail.

### The protocol (operator requirement — plan is CONTEXT, not execution right)

The Gigaplan forbids autonomous phase-advancing. On context restore or handoff:
1. Read the plan fully.
2. Check git/file/server state **read-only** (pwd, `git branch --show-current`,
   `git status --short`, `git log -1`).
3. Produce a precise status report (present state / last approved phase / files
   changed / open decisions / risks).
4. **STOP** and ask: *"Welchen einzelnen nächsten Schritt soll ich ausführen?"*
5. Execute ONLY the explicitly granted step, then STOP and wait again.

Only explicit instructions count as release ("Führe nur Phase X aus", "Baue die
Seed-Engine", "Commit den Stand"). NOT releases: "Lies den Plan", "Mach weiter",
"Was ist der Stand?", a stale grant from a previous session. Do not combine phases.

### The operator's AUTONOMOUS override (corrected 2026-08-02, forceful)

The stop-and-ask protocol above describes the Gigaplan's WRITTEN contract. It is
NOT how the operator actually wants the work run. When the operator is unhappy
with the pace of per-step asking, they say so with force and expect the agent to
**execute the entire remaining scope autonomously to a working, tested, committed
state, then report once at the end** — not to re-ask after every phase.

Verbatim this session: *"NERV MICH NICHT MIT JEDEM KACK DRECKS FURZ, AUTONOM!
FFS!"* and *"KEINE VERFICKTEN STATISHEN DRECK! CUTTING BLEEDING EDGE+++++++++++"*.

Three lessons, all loaded:
1. **Don't micro-ask.** After an explicit grant (e.g. the user replies "A" to a
   proposed next step), that grant covers finishing the WHOLE task to done —
   build, test in the browser, commit, report. Do not stop after one sub-phase to
   ask for the next. The operator is an architect who sets direction and wants the
   crew to execute and deliver.
2. **"CUTTING BLEEDING EDGE / no static shit"** is the operator's quality bar for
   the walk. A working walk that still *feels* like a static SaaS page underneath
   is a failure — the graph must become the hero, not hover over a static skeleton.
   See "Fullscreen walk → living hero" below.
3. **Even 25/25 gates passing is not enough if the site still FEELS static.**
   After the walk intro + receipts + worlds + film + FAQ were all committed and
   verified (commit `09b2660`), the user's verdict was: *"not bad für einen
   ersten proof of concept. aber bei weitem noch immer lichtjahre von NICHT
   statischem müll, super bleeding cutting edge technologie entfernt!"* — "not
   bad for a first proof of concept, but still light years away from NOT being
   static garbage, super bleeding cutting edge technology REMOVED!" The session
   then started building a **persistent full-viewport living background maze**
   (a fixed full-screen canvas behind the entire page, seeded graph breathing
   throughout, scroll-velocity coupling) but the session DIED with a
   `BadRequestError` (reasoning_effort: Invalid option) before it could ship.
   The lesson: verification gates test correctness, not feeling. The operator's
   bar is "does the whole page breathe" — not "do all tags balance."

This autonomy is bounded: it still must NOT touch live roots, `design-import`,
`/mnt/BSC-Node/comic`, prod, DBs, Stripe, MCP, or push/merge. Autonomy of execution
within the fork, not authority over the live systems.

### Fullscreen walk → living hero (the "no static shit" fix, 2026-08-02)

The Gigaplan's core demand — "the walk becomes the site, the graph becomes the
hero" — failed the first time because the intro was rendered into the
`#heroMaze` canvas that only occupies the right-hand `.hero-bleed`
(`width: min(60%, 940px)`). The full static SaaS skeleton (h1 "Your agents stop
forgetting.", 3 CTA buttons, spec-rail, wire-rail) stayed visible around it, so
the experience read as a static marketing page with a small animation on the side.
The operator rejected this as "statischen Dreck".

The fix that satisfies "visuals == KING / graph becomes hero" (commits `352224b` +
`316d7bf` + `6127936`):
1. **The intro owns a dedicated FULLSCREEN canvas** (`#introCanvas`, `position:
   fixed; inset:0`, `width/height:100%`, stage bg `#050308`) created in
   `intro.js` `buildDom()` — the walk is the ENTIRE viewport; nothing leaks
   through. The caller's `#heroMaze` canvas is reserved for the handoff after the
   seam. All `ctx.*` drawing calls were re-pointed to `stageCtx`.
2. **Make the traversal livelier** so the walk never stalls on a static screen:
   raise autonomous wander acceleration (`0.00055`→`0.0022`), shorten idle-wander
   window (3500ms→1200ms), raise node-visit radius (110→150), compact maturation
   (2300ms→1200ms), and add an **impatience cap** that wakes stragglers at ~14s so
   the crystal lands reliably. Critical bug: the cap must key off a DEDICATED
   `walkStartedAt` set in `beginWalk()`, NOT `walkPhaseAt` — the phase clock resets
   every 9–17s, so a cap keyed on it never fires.
3. **The hero becomes the maze.** Widen `.hero-bleed` to `min(72%,1100px)`, add
   `#heroMaze { width:100%; height:100%; object-fit:cover }`, soften the scrim.
   Replace the static SaaS hero copy with the Gigaplan manifest: H1 "Memory
   formation, not retrieval." + "The graph preserves decisions, not just
   documents." and DROP the spec-rail + "WIRES ITSELF INTO" wire-rail from the
   first viewport.
4. **Seam verified**: first scroll after the glyph calls `completeIntro()`, which
   hands the same graph to `initMaze(canvas)` on `#heroMaze`; the graph keeps
   living as the hero (NREM→REM→INSIGHT). Verified live: `window.__heroMaze` set,
   intro stage removed, `intro-lock` released.

### "THE PAGE IS THE PRODUCT" — the live pod (operator-corrected 2026-08-02, forceful)

The fullscreen walk + living hero was still not enough. The operator pasted a
reference page (Bonsai 27B, a 27B-parameter WebGPU LLM that RUNS IN THE BROWSER)
with: *"CUTTING EDGE, NO GARBAGE OVERLAY OVER GARBAGE STATIC CRAP I NEVER ASKED
FOR!"* The bar is: **the visitor operates a working miniature of the product, not
a marketing page with decorations.** For Mazemaker that means a real, in-browser
memory pod the visitor can use.

**REJECTED first attempt — the decorative overlay.** A full-viewport `background.js`
backdrop (fixed canvas, seeded graph, section↔node flare coupling, `mix-blend-mode:
screen` over the whole page) was built and then **deleted**. Two failures: (a) at
~0.4% painted pixels it was invisible on the dark theme; turning it up to be visible
made it a "garbage overlay over garbage static crap"; (b) it was decoration — the
page still didn't DO anything. A living backdrop over a static page is the exact
anti-pattern. Deleted entirely (file, script tag, CSS) before the pod shipped.

**ACCEPTED pattern — the page IS the pod** (commits `33169a9`, `e9a0e92`,
`01e2b7e`, `0df3a2e`). Section 00 "This page is a pod." sits right after the hero
with a real, working engine:
- `assets/pod.js` — `window.createPod()`: token-overlap similarity, formation with
  edge linking, ranked recall with one-hop edge boost, supersession with edge
  re-weighting, three-phase dream (NREM strengthen / REM bridge / INSIGHT
  crystallise). Seeded from the SAME share-safe memories as the walk.
- `assets/pod-ui.js` — live console: form memories, contradict (newer truth
  supersedes, old node dims + drops out of recall), run dream cycles, recall with
  real scores; graph canvas runs a continuous rAF loop (nodes breathe, particles
  flow along real edges, formation/supersession flare green halos, superseded
  links stay as dashed red history). Reduced-motion → single static paint.
- **Persistence**: `sessionStorage` (`mzPodV1`), `load()` on create / `save()` on
  every mutation — formed memories, edges and dream count survive reloads within
  the tab ("the maze remembers you" made literal, not staged). Honest scope:
  sessionStorage only, cleared when the tab closes.
- **Section numbering**: the pod is 00 (the entry after the hero); peek-behind-the-
  door 01, in-one-minute 02, film 03, receipts 04, kernel 05, proof 06, scheduler
  07, worlds 08, deep dives 09, spawning 10, license 11, objections 12, family 13.

Engine pitfalls learned the hard way (verification caught them, not vibes):
- **Pure Jaccard fails on the long-prose seed corpus** (links almost nothing).
  Use token-overlap: `max(jaccard, coverage*0.75)` where coverage = inter /
  min(lenA, lenB).
- **Supersession needs a tie-break**: on equal similarity it picked the WRONG
  memory. Sort by similarity, ties → most recently formed (that's what the user
  is contradicting now).
- **Persistence must load before seeding** — `if (!load()) { seed; save(); }`, or
  every reload re-seeds on top of the visitor's graph.

Full implementation detail: `references/pod-implementation.md`.

### Verified asset inventory (committed 2026-08-02, commit 05717bb)

- `website/media/film/`: `mazemaker-dc-trailer.mp4` (24 MB, the primary film asset),
  `prologue-web.mp4` (1.4 MB web transcode). **`prologue.mp4` (118 MB reference
  master) is gitignored** via `.gitignore` (`website/media/film/prologue.mp4`) — the
  plan §10 marks it reference-only, never initial-load. Do not re-transcode
  `prologue-web.mp4`; it already exists.
- `website/media/shots/`: the 13 receipt screenshots (incl. `gh_estate.png`,
  `test_mazemaker_commits.png`) + `SCREENSHOT-LIST.md`. **`mobile.png` is ABSENT** —
  the plan's receipt list names it, but it's not on disk; never claim it exists.
- `website/media/worlds/`: exactly 6 worlds × 15 panels (01 medical-frontier, 02
  defense-protocol, 03 academic-archive, 04 space-comms, 05 grid-stability, 06
  disaster-response). No Legal/Education/Climate worlds exist — do not present them.
- `website/media/stills/`: `keys/kf_01–04.png` + `slides/slide_00–07.png` +
  `_contact_sheet.png` (note: filenames are `kf_01`/`slide_00`, not `kf01`/`slide0`).
- **`website/media/` is now WIRED into the page** (commits `316d7bf` + `6127936`,
  this session), not orphaned:
  - **Film section = native `<video>`** (commit `316d7bf`) sourcing
    `media/film/mazemaker-dc-trailer.mp4` (24 MB, 112 s) with `preload="metadata"`,
    `poster="assets/film-poster.webp"`, an overlay `<button>` poster that calls
    `video.play()` on click. **No iframe, no `trailer/` link** — the earlier
    design (poster `<a href="trailer/">` + `assets/film.js` swapping a hidden
    iframe `src="trailer/"`) was replaced per Gigaplan §9-01 (conscious play, no
    autoplay, no sound without action). The `trailer/index.html` Web-Audio page
    still exists but is no longer the homepage's film entry.
  - **Receipts section (03)** = the engineering-archaeology timeline: 9 commit
    cards (genesis, dream, cython, nvidia, dim1024, identity, pgvector, stripe,
    colbert) + 4 git-ledger figures, all from `media/shots/*.png`. Dates/milestones
    taken verbatim from `SCREENSHOT-LIST.md` — never invent a receipt.
  - **Worlds section (07)** = the 6 real worlds × cover+2 panels from
    `media/worlds/`. All `<img loading="lazy" decoding="async">`; lazy-load only
    near viewport (verified: not loaded until scrolled into view).
