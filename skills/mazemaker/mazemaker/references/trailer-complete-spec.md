# MAZEMAKER Trailer — Complete Specification

## File Details

- **Path:** `public/maze-crew-trailer.html`
- **Lines:** 3,034
- **Bytes:** ~169KB
- **Type:** Self-contained Three.js ES module cinematic loop

## Architecture Constants

```
LOOP_DURATION   = 20s      # Total loop time
FADE_DURATION   = 0.9s     # Black overlay fade between iterations
SPARK_CAP       = 40       # Max concurrent additive particles
SPARK_LIFE      = 1.5s     # Particle lifetime
HEART_WAVE_CAP  = 4        # Max icosahedron ripple shells
FIRING_RING_CAP = 48       # Max source wavefront rings
NODE_COUNT      = 900      # REGIONS[].count: 130+110+100+90+80+60+150+180
STAR_COUNT      = 4000     # Background starfield (r=60-200)
DISTANT_COUNT   = 10       # Peripheral wireframe structures
```

## 6-Act Viral Structure (42-46s total)

| Act | Time | Content |
|-----|------|---------|
| 0 | 0-2s | INSTANT EXECUTION — fullscreen kinetic text, SHAKE, audio BRAAM |
| 1 | 2-10.5s | EMOTIONAL DAMAGE — 6 PTSD flashbacks @ 1.1-1.7s each |
| 2 | 10.5-22.5s | THE IMPOSSIBLE MOMENT — cross-agent recall with MATCH CONFIRMED |
| 3 | 22.5-31s | RECEIPTS — 8 benchmark bombs with hit() on each |
| 4 | 31-37s | OS REFRAME — "This is not memory. This is an OS for AI agents." |
| 5 | 37-45.5s | RELIGIOUS ENDING + PRICING CARDS — $9/$29 founder rates, HARD CUT |

## Heartbeat-Driven Layers (8 total in trailer)

1. **FOV breath** — 58°→59.5° on beat peak
2. **Fog density** — 0.011→0.014 on beat
3. **Vignette alpha** — 0.42→0.60 on beat
4. **Camera tremor** — beat×0.10u displacement
5. **Nucleus scale/opacity** — core 1.0→1.35, opacity 0.65→0.90
6. **Halo scale/opacity** — 1.0→1.12, opacity 0.10→0.28
7. **Heart waves** — icosahedron shells spawn on beat peak
8. **Cognitive thought-sparks** — additive particles from nucleus on beat

## Soundtrack (generate_soundtrack.py)

- **Output:** `public/trailer-soundtrack.flac`
- **Duration:** 46.0s
- **Segments:** Part 1 (0-22s) build-up + Part 2 (22-46s) climax
- **Crossfade:** 2.0s linear between segments
- **Model:** facebook/musicgen-small (FP16 for VRAM efficiency)

## 4K Render (render_4k.sh)

```
HTML=trailer-viral.html     # Note: may need update to maze-crew-trailer.html
OUTPUT=trailer-viral-4k.mp4
RES=3840x2160
FPS=60
CRF=16
METHOD= Xvfb + google-chrome-stable --user-data-dir + ffmpeg x11grab
```

## Cross-File Parity Status

| Feature | Bio | Dream | Trailer |
|---------|-----|-------|---------|
| try/catch | ✓ | ✓ | ✓ |
| setSize | ✓ | ✓ | ✓ |
| Phase progress bar | ✓34 | ✓52 | ✓65 |
| Distant structures | ✓4 | ✓4 | ✓8 |
| Thought propagation | ✓ | ✓ | ✓ |
| Heartbeat emission | ✓18 | ✓21 | ✓25 |
| Cognitive sparks | ✓29 | ✓30 | ✓31 |

## Last Iterations (2026-06-23)

- **#31:** Cognitive thought-sparks backport (Bio→Dream→Trailer parity)
- **#67:** EKG QRS-spike overlay (Bio only)