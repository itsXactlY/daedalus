# New-theme design system + viral facts DB

Session-specific detail on the REAL current Mazemaker site (worktree
`.claude/worktrees/design-import/website/`, branch `design/site-rebuild`). Two
authoritative docs live in that directory — this file distils the parts a rebuild
needs. Pull exact wording from `REDESIGN-NOTES.md` and
`LAUNCH_PAYLOAD_VIRAL_FACTS.md` before quoting on a page.

## The new design language (REDESIGN-NOTES.md)

- Shadow-as-border — every frame `box-shadow: 0 0 0 1px …`, zero `border:` in the
  design layer.
- Luminance stepping — elevation via `--surface` → `--surface-2`, never dark shadows
  on dark.
- Compressed display type — H1 to 6rem at `-0.04em`, H2 `-0.03em`, H3 `-0.018em`,
  weight 600 max, no weight 700 anywhere.
- Inter `cv01` + `ss03` on every text element via `--feat`.
- Violet discipline — `#8b5cf6`/`#a78bfa` interactive only; solid fills carrying
  white text use `--accent-fill` `#7f4ff2` (white on `--accent` is only 4.23:1).
- Contrast floor — WCAG AA everywhere, lowest 4.88:1. `--text-dim` `#8a8a97` (5.8:1),
  used for real content at ~12px, never a 3:1 grey.
- Ember `#d1552b` — the one warm voice, exactly four places: hero wash, image rim,
  install block, `// section` marks. Never on a control.
- Section marks — `01 / the name` mono rail above every section heading.
- Hairlines not boxes; figure rails (mono, tabular, hairline-separated runs); station
  spine (long-form indexes down a gradient spine with rotated-diamond nodes).
- All paths depth-relative (not root-absolute) so sub-pages work in previews/subfolders.
- `paper.html` carries its own token copy (self-contained for printing) — a colour
  change must propagate to it and `docs/assets/docs.css` too.

## Key token deltas vs the OLD main theme

| Token | Old (`main`) | New (worktree) |
|---|---|---|
| `--text-dim` | `#5e5e6b` (3.1:1) | `#8a8a97` (5.8:1) |
| `--accent-fill` | (none) | `#7f4ff2` |
| `--on-accent` | (none) | `#ffffff` |
| `--t-h1` | `clamp(2.6,5.6vw,4.4rem)` | `clamp(2.9,7.6vw,6rem)` |
| `--r-pill` | (none) | `999px` |

## The viral facts DB (LAUNCH_PAYLOAD_VIRAL_FACTS.md) — every number is real & verified

Never invent any of these. Pull verbatim from the file or the site.

- **Reframe:** "Operating system for AI agents." Not a memory product, not a vector DB.
  "Your agents die every conversation. Mazemaker keeps them alive." "The labyrinth,
  not the cloud." "Evidence, not vibes."
- **LongMemEval-S 500q (ColBERT @ 1.5):** R@1 0.8574 · R@5 **0.9787** · R@10 0.9894 ·
  MRR 0.9114 · p50 56.9ms. Per-type R@5: knowledge-update/multi-session/ssa all 1.0000.
- **LongMemEval-Oracle (hard, 25k-mem haystack):** 100 iters / 4 eras, R@5 0.6851→0.8426,
  R@10 broke 0.90, ssu R@10 1.0000. Total OpenAI spend < **$0.10**.
- **Comparison Bench:** **188/200 = 94.0%** — the 10 small models Hindsight published
  as "0/N not viable" (gemma3:270m 18/20 = 90% on a Raspberry Pi). 0 JSON leaks.
- **Negative controls:** Hop-2 R@10 0.00→1.00 (vector DBs can't); shuffled edges
  1.00→0.27; post-dream 0.00→0.43; conflict supersession 0.03→0.33; cross-session
  R@5 0.06→0.62; lean vs skynet 0.60 vs 0.42.
- **8-round GPT-5.5 adversarial audit:** v2 NO → v8 UNCONDITIONAL YES, no residual
  caveat.
- **Architecture:** rootless Podman, 4 containers, BGE-M3 1024d + ColBERT @1.5 + DAE,
  vault key HKDF-SHA256(JWT, hardware-fingerprint) never on disk, 7-day offline grace,
  AES-256-GCM vault, Ed25519 JWT, 12-monitor Architect cockpit, 31 MCP tools.
- **Pricing:** Community $0 · Builder $15 ($9 founder) · Pro $49 ($29 founder) · Team
  $149 · Enterprise custom. Founder seats 100/100 sold.
- **Tier split:** Community = open-source engine (SQLite, CPU, 3-phase dream, CLI+MCP);
  Pro = same engine + ColBERT (R@5 0.96→0.98), DAE, Stage S synthesis, Architect
  cockpit, Postgres + pgvector, unlimited agents.
