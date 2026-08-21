# Trailer Production Inventory — `/home/alca/projects/video/lab/` (33 MB)

The produced cinematic trailer production. This is the artwork the operator means
when they say "there are gigabytes produced artwork" — mine it, don't re-invent it.

## The film

- **`trailer-v19.html`** — the final, self-contained 1920×1080 HTML/CSS/JS cinematic.
  No build, no external deps beyond Google Fonts. Poster click-to-play, Web Audio
  synth soundtrack, film-grain + vignette overlays, glitch text, bomb-drop receipts.
  113s runtime. This is the canonical source for the hero visual language.
- **23 versions**: `trailer-v12` … `trailer-v19`, `trailer-final`, `trailer.html`,
  `trailer-viral` (+ `.bak`), `trailer-launch`, `trailer-fomo`, `trailer-ultimate`,
  `trailer_claude`, `trailer_claude_2`, `claude.html`, `geminipro.html` (+
  `_refined`, `_burst`), `gpt55.html`, `maze-crew-trailer.html`,
  `maze-crew-dream.html`, `maze-crew-bio.html`.

## Soundtrack masters

- `master.mp3`, `master-v14.mp3`, `master-v14b.mp3`, `master-extended.mp3`
- `trailer-soundtrack.wav` (2.8 MB), `trailer-soundtrack.flac` (1.1 MB)
- `strudel-soundtrack.txt` — composition notes

## Storyboard — `shots-launch/` (21 PNGs, full act0→act5 arc)

| Act | Shots |
|-----|-------|
| act0 | void, execution |
| act1 | session_death, context_coffin, ghost_agents, isolation |
| act2 | memory_formation, dream_cycle, federation, kernel_cathedral, knowledge_graph |
| act3 | 270m_pi, negative_control, iterations, hop2_reasoning |
| act4 | claude_stores, hermes_finds, the_model_remembered |
| act5 | age_over, launch_cta, mazemaker_wordmark |

## The trailer narrative (this IS the selling story)

1. **act0 cold open (0–4s)**: "Agent frameworks are lying to you. Vector Databases are
   lobotomies."
2. **act1 problem (4–15s)**: Claude vs Hermes — session death, every agent starts
   empty. "Across sessions. Across models. Across teams."
3. **act2a Claude writes (15–25s)**: Claude stores a bug-fix memory (redis lock storm).
   `✓ stored · id=44291 · 0.04s · multilingual-e5-large · 1024-d`
4. **act2b Hermes recalls (26–60s)**: Hermes recalls it next session. "Hermes read
   this. From a memory another agent left."
5. **act3 receipts (60–97s)**: 13 proof bombs — Hindsight 188/200=94%, 270M params on
   a Pi 18/20=90%, Hop-2 R@10 0.00→1.00, negative controls edge-shuffle 1.00→0.27,
   100 iterations at $0.10 R@5 0.6851→0.8426, LongMemEval-S R@5=0.9787, ssu
   R@10=1.0000, post-dream 0.00→0.43, conflict supersession, 8 rounds adversarial v8
   = "UNCONDITIONAL YES", NO competitor does this, cross-session 0.62.
6. **act3 OS reframe (97–113s)**: "Your agents die every conversation. Mazemaker keeps
   them alive. This is not memory. Memory is a database. This is an operating system
   for AI agents." + the kernel stack (memory mgmt · consolidation · filesystem ·
   knowledge graph · scheduler · dream cycles · IPC · federation · audit).
7. **end card (113–130s)**: wordmark + pricing $9/$29 founder, first 100, locked
   forever, launch date.

## Extra media assets

- **`mazemaker-pro/assets/`**: `cover_video.mp4` (9.7 MB — a real video file),
  `cover.png`, `neural_brain_hero.png`, `hermes_mind.png`, `brain_krang.png`,
  `mazemaker_dashboard.png`.
- **`mazemaker/assets/`**: mirror of the same `cover_video.mp4`, `cover.png`,
  `neural_brain_hero.png`, `hermes_mind.png`, `brain_krang.png`.
- **`mazemaker-architect/public/`**: `maze-crew-bio.html`, `maze-crew-dream.html`,
  `maze-crew-trailer.html` — the three Three.js visualizations iterated by the
  `maze-crew-loop` cron. Interactive motion candidates.
- **`turbofit-no-docker/assets/`**: `turbofit-promo-1080p.mp4` (8.6 MB),
  `turbofit-hero.png` — for the turbofit/Bonsai local-LLM angle.

## CSS visual language of the trailer (reusable)

- Dark film aesthetic: `--bg-0:#020203`, `--bg-1:#0b0d12`, `--fg:#fff`,
  `--claude:#d97757`, `--hermes:#a78bfa`, `--ok:#34d399`, `--warn:#fbbf24`,
  `--info:#60a5fa`, `--red:#ef4444`, dream phase colors (NREM blue/REM pink/
  INSIGHT green).
- `.stage` 1920×1080 scaled via JS `fit()`; film grain + vignette via `::before`/
  `::after` with fractalNoise SVG + radial gradient.
- Receipt entrance: `bomb-drop` / `receipt-in` keyframes (blur+scale pop).
- Glitch: RGB-split text-shadow animation.
