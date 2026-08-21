# Crop-Based Ken Burns Video Rendering

Render a sequence of still images into a 1920×1080 video with smooth camera
drift (Ken Burns effect) using ffmpeg's `crop` filter. **~30× faster than
`zoompan`** because crop selects existing pixels instead of synthesising new ones.

## Why crop beats zoompan

| Filter | 1365 frames at 1920×1080 | Mechanism |
|--------|--------------------------|-----------|
| `zoompan` | ~10 minutes | Re-renders every pixel every frame |
| `crop`+`scale` | ~20 seconds | Selects a region, scales to output |

## Technique

1. **Pre-scale each image to ~110%** of the target resolution (e.g. 1336×756
   for a 1216×688 source → 1920×1080 output). This gives room for the crop
   window to drift without exposing edges.
2. **Use `crop` with animated x/y expressions.** The crop window (1216×688)
   moves linearly from a start position to an end position over the clip's
   duration.
3. **Scale the cropped region back to 1920×1080.**

## Per-shot ffmpeg command

```bash
# Pre-scale first
python3 -c "
from PIL import Image
img = Image.open('shot.png')
img = img.resize((1336, 756), Image.Resampling.LANCZOS)
img.save('shot_scaled.png')
"

# Crop with drift animation (moves 60px right + 34px down over 1s at 30fps)
ffmpeg -y -loop 1 -i shot_scaled.png \
  -vf "crop=1216:688:'60*(t/1)':'34*(t/1)',scale=1920:1080,format=yuv420p" \
  -frames:v 30 -r 30 \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
  shot_clip.mp4
```

The expression `'start_x + (end_x - start_x)*(t/duration)'` produces a
linear drift. For variety across 24 shots, derive start/end offsets from
the shot index:

```python
import math
angle = shot_index * 1.7
dx = int(60 * math.sin(angle))
dy = int(40 * math.cos(angle))
end_dx = int(60 * math.sin(angle + 0.7))
end_dy = int(40 * math.cos(angle + 0.3))
max_cx = 1336 - 1216  # 120px drift range
max_cy = 756 - 688     # 68px drift range
sx = max(0, min(max_cx, dx))
sy = max(0, min(max_cy, dy))
# ...
x_expr = f"'{sx}+({ex}-{sx})*(t/{duration})'"
y_expr = f"'{sy}+({ey}-{sy})*(t/{duration})'"
```

## Full pipeline (24 shots, 45.5s, ~30s total render)

1. Pre-scale all images to 110% (PIL LANCZOS)
2. For each shot: ffmpeg crop + scale → short clip (0.5s each, ~12 total seconds)
3. Create an ffconcat file listing all clips with their durations
4. Final ffmpeg pass: concat + ASS typography overlay + vignette + audio mux
   ```bash
   ffmpeg -f concat -safe 0 -i clips.txt -i soundtrack.flac \
     -vf "ass=text.ass,vignette=PI/4" \
     -map 0:v -map 1:a -shortest \
     -c:v libx264 -preset veryfast -crf 18 \
     -c:a aac -b:a 320k -ar 48000 -ac 2 \
     final.mp4
   ```

## When to use

- You need smooth camera motion across multiple still images
- The stills are generated at a consistent resolution (e.g. 1216×688 from Flux)
- You want a single output video without browser rendering
- `zoompan` is too slow (>2 min per render) and you need <30s turnaround

## When NOT to use

- The output needs CSS-animated effects (shake, glitch, bloom) — those require
  browser rendering. Use the HTML trailer + Xvfb + headless capture instead.
- You need frame interpolation or optical flow — use ffmpeg's `minterpolate`.
- The images are already at target resolution — crop becomes a no-op.
