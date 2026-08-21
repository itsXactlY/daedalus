# Community `pulse` vs Pro-Wurm — what actually worked

## TL;DR for niche/technical queries
Use the COMMUNITY skill. It returns real, on-topic signals. Pro-worm returns
junk even after extensive fixes (see parent SKILL.md failure modes).

## Working command (community)
```bash
cd /home/alca/.hermes/skills/devops/pulse
python3 scripts/pulse.py "WebGL vectorized GPU instancing OOP rendering architecture best practices" \
  --depth deep --lookback 100 --emit full --no-llm
```
- `--emit full` (not `md`) so you get the raw scored clusters, not a truncated summary.
- `--no-llm` avoids the planner drifting the query (same drift problem the pro-pod has).
- Runs in seconds-to-minutes; no async job dance needed.

## Why pro-wurm failed for this topic (evidence, not theory)
Runs 1-11 on the pro Pod, topic = "WebGL vectorized GPU instancing OOP rendering
architecture best practices 2026":
- Run 1 (qwen2.5:3b): 483 aggregated, LLM filter kept 7 -> all GitHub-Copilot i18n pages (off-topic collapse).
- Runs 2/3: dig-1 = 0 growth -> 0 returned (wurm died).
- Run 4 (Gemma + filter on): dig-2 +442% growth but filter kept 0/103.
- Runs 5-11: anchor-filter + graphics_tech router + strict host allow-list +
  Gemma backend + `cache.db` deleted (Run 11) -> STILL
  `anchor-filter | dropped 60 kept 0`.
Conclusion: the pro-Pod Search-fan-out returns non-WebGL results at the source
layer; the worm/anchor patches cannot recover signal that was never retrieved.

## Curated "11/10" WebGL / vectorized / OOP findings (from community `--emit full`)
TOP-TIER (cutting-edge + production-relevant):
1. WebGPU Render Bundles — Loke.dev post-mortem
   https://loke.dev/blog/webgpu-render-bundle-performance-analysis
   Pre-recorded command sequences; kills CPU overhead on draw-call storms.
2. The Structure of a WebGPU Renderer — Ryosuke (2025)
   https://whoisryosuke.com/blog/2025/structure-of-a-webgpu-renderer/
3. Three.js TSL Instancing (official dev example)
   https://github.com/mrdoob/three.js/blob/dev/examples/webgl_tsl_instancing.html
   One draw call for thousands of objects via TSL node materials (2026 path).
4. NVIDIA GPU Gems Ch.3 — Inside Geometry Instancing
   https://developer.nvidia.com/gpugems/gpugems2/part-i-geometric-complexity/chapter-3-inside-geometry-instancing
5. ECS vs OOP Benchmark (GPU-side data modelling) — dmurph.com (2026)
   https://www.dmurph.com/posts/2026/06/ecs_vs_oop_benchmark/ecs_vs_oop_benchmark.html

SOLID (architecture + practice):
6. Scene Graph Architectures in Modern Game Engines — Korostin
   https://levelup.gitconnected.com/scene-graph-architectures-in-modern-game-engines-572b09f95e13
7. WebGL/Three.js CAD Rendering Optimization — RapidMade
   https://rapidmade.com/webgl-three-js-cad-rendering-optimization/
8. PlayCanvas Hardware Instancing docs
   https://github.com/playcanvas/developer-site/blob/main/docs/user-manual/graphics/advanced-rendering/hardware-instancing.md
9. Three.js Architecture: ECS — DEV
   https://dev.to/i_babkov/threejs-architecture-ecs-3fg2
10. Wonderland Engine WebGL Performance
    https://wonderlandengine.com/about/webgl-performance/
11. NullGraph (data-oriented WebGPU framework) — https://github.com/Zabrane/NullGraph
12. VectoriumEngine (vectorized math) — https://github.com/ntholm86/VectoriumEngine
13. Instanced Rendering & LOD: Millions at 60fps
    https://www.mysimulator.uk/content/articles/instanced-rendering-lod.html
14. GPU-side data modelling without OOP — Computer Graphics SE
    https://computergraphics.stackexchange.com/questions/14008/what-are-some-ways-of-modelling-data-for-gpu-side-where-e-g-oop-is-not-availabl

NOTE: the community `pulse` Arxiv fan-out returns noise (matched "all" as a
bigram -> tetraquarks/honeypots/spintronics papers). Ignore those; the Web-source
cluster is the signal.
