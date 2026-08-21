---
name: video-generation
description: |
  Generate video artifacts from source content — four techniques under one class:
  colored ASCII video (MP4/GIF), 4K cinematic films from static panels + TTS, kinetic
  self-contained HTML trailers, and Manim CE math/algo animations. Use when the user
  wants any video output from images, audio, text, or math and you need the right
  technique + its detailed recipe.
---

# Video Generation

Class-level skill for producing video from non-video source material. Pick the technique
that matches the input, then drill into the re-homed support for that technique.

## Technique 1 — Colored ASCII video (absorbed from `ascii-video`)

Convert video/audio to colored ASCII MP4/GIF. Best for stylized, terminal-aesthetic
output from an existing clip or audio track.

Support (under `references/ascii-video/`): `architecture.md`, `composition.md`,
`effects.md`, `inputs.md`, `optimization.md`, `shaders.md`, `scenes.md`,
`troubleshooting.md`.

## Technique 2 — 4K cinematic film from panels (absorbed from `ffmpeg-cinematic-film`)

Build 4K cinematic films from static panel images + TTS voiceovers with ffmpeg: Ken
Burns pans, drawtext overlays (lower-thirds, title/end cards), color grade + film grain,
sidechain-ducked music bed, h264_nvenc encoding, multi-segment concat.

Support (under `references/ffmpeg-cinematic-film/`): `ffmpeg-filter-chains.md`,
`deluxe-mastering-recipe.md`, `cinematic-impact-layers.md`.

## Technique 3 — Kinetic HTML trailer (absorbed from `cinematic-html-trailer`)

Self-contained HTML cinematic trailers with kinetic typography, Web Audio SFX, a scene
timing system, blackout/flash transitions, and a synchronized soundtrack.

Support (under `references/cinematic-html-trailer/`): `act-timing-templates.md`,
`headless-capture.md`, `100-iterations-pattern.md`, `mazemaker-render-config.md`.
Scripts: `scripts/cinematic-html-trailer/validate-js.py`, `cdp-validate.py`.

## Technique 4 — Manim CE animations (absorbed from `manim-video`)

3Blue1Brown-style math/algo explainer videos with Manim Community Edition.

Support (under `references/manim-video/`): `animation-design-thinking.md`,
`animations.md`, `camera-and-3d.md`, `decorations.md`, `equations.md`,
`graphs-and-data.md`, `mobjects.md`, `paper-explainer.md`, `production-quality.md`,
`rendering.md`, `scene-planning.md`, `troubleshooting.md`, `updaters-and-trackers.md`,
`visual-design.md`. Script: `scripts/manim-video/setup.sh`.

## Choosing

- Have a clip/audio → ASCII video.
- Have panels + voiceover → ffmpeg film.
- Want a slick promo loop → HTML trailer.
- Explaining a concept/math → Manim.
