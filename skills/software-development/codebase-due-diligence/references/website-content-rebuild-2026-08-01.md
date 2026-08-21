# mazemaker.online Visual Rebuild — Worked Example (2026-08-01)

The "messaging spine" technique applied to the Mazemaker marketing site. This is the
session-specific detail behind the `codebase-due-diligence` pitfall "STOP GUESSING".

## Context

- Repo: `itsXactlY/mazemaker-v2-frontend` (the site IS `mazemaker.online`, deployed via Cloudflare Pages)
- Local path: `/home/alca/projects/mazemaker-v2-stack/frontend/website/`
- Site was already rebuilt once via the "GOATED prompt" (2026-07-28) + Claude Design overlay, imported as commit 0808807 on branch `design/site-rebuild`. This is a THIRD iteration.
- Ask: "make it like BridgeMind.ai — full of images and short movies that sell what we do/build/offer."

## The design-language (from commit 0808807 + live `style.css`) — non-negotiable

- shadow-as-border (zero `border:` declarations), luminance stepping for elevation, hairline rows not boxes
- violet `#8b5cf6` on interactive elements ONLY; ember `#d1552b` second voice in exactly ≤4 places
- compressed display type, weight 600 max (no weight 700 anywhere)
- tokens live in `:root` of `style.css`; `paper.html` carries its OWN duplicate token set (drift trap — update both, nothing enforces it)
- voice = "Mazemaker Oracle" — declarative, no hedging

Live tokens (verified): `--bg #0a0a0d`, `--accent #8b5cf6`, `--accent-hi #a78bfa`, `--ok #10b981`, `--warn #f59e0b`, `--err #ef4444`, Inter + JetBrains Mono.

## The visual gap (confirmed from live files, not opinion)

- ZERO video assets on disk (no .mp4/.webm/.mov anywhere). The "tiny movies" must be PRODUCED.
- 9 static posters: brain (1920×1088), architect-room (1920×1080), manifesto-poster (1600×900), hero (900×900), hero-270m, playground-demo, og.png, og.webp, og.svg
- Hero = static 900×900 webp with only a CSS `brainDrift` rotate. No canvas / Three.js / motion.
- The only animation in style.css is `pulse-live` (status dot) + `brainDrift`.

## The messaging spine (6 beats, each from REAL page copy)

Story: "Your agents die every conversation. Mazemaker keeps them alive — with evidence, not vibes."

1. **Death/Rebirth loop** (hero hook) — node dims/dies → cyan pulse re-lights → memory graph snaps back. "Every conversation is a rebirth." From hero tagline.
2. **Memory formation, not retrieval** — two tiny movies side-by-side (search fumbles vs memory crystallizes). From "Memory formation, not retrieval."
3. **Dream consolidation** (background work) — animate `mazemaker-brain.webp`: weak edges fade, strong edges brighten/rewire. From "Background consolidation while they sleep."
4. **Conflict supersession** — two nodes collide, old dims/struck, newer wins and re-routes edges. From "Conflict supersession when your mind changes."
5. **Knowledge-graph filesystem** — trace a path node-to-node, walk-don't-search. From "your agent walks instead of searches."
6. **The proof** — animated badges: `R@5 = 0.9787`, `188/200 Hindsight`, `v8 audited`. From the real meta description.

Caption style (Oracle voice): "The model forgets. The memory does not."

## Fork-before-build (verified command)

```bash
cd /home/alca/projects/mazemaker-v2-stack/frontend
git stash push -u -m "wip-2026-08-01-before-visual-fork"   # parked 30 dirty-tree edits
git checkout main && git checkout -b visual/immersive-rebuild
```
Result: fork `visual/immersive-rebuild` clean off origin/main, stash@{0} preserved, all 9 assets intact. Prod (`main`) untouched.

## Phase gate

0. Fork → 1. Messaging spine → 2. Produce media → 3. Build/wire → 4. Autonomous loop → 5. Verify+ship. Run ONE, surface a decision, wait.

Decision point before Phase 2 (offer to operator): **procedural motion (Three.js/Canvas embedded — crisp, on-brand, honors dark theme, recommended for abstract beats) vs screen-recorded mp4 (heavier, social-ready).** BridgeMind sells with abstract on-brand motion, not literal footage.

## Carried-forward bugs to NOT reintroduce

- `website/_v1/` is a frozen snapshot served publicly with dead relative asset paths
- `research.html` links `./blog/beam-10m-conv-1-multirecall/` which has never existed
- `newsletter/index.html` loads Plausible, contradicting `privacy/index.html` §2

## Autonomous loop

Paused cron `mazemaker-website-autonomous-loop` (claude-sonnet-4, toolsets browser/terminal/file, schedule `0 */6 * * *`) is the target engine to revive for record-and-iterate once media exists. It paused with an error 2026-07-21.
