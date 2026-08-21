# Mazemaker Trailer Rebuild — Neural Memory Extraction

## Source Context
- **Memory IDs:** `492352`, `492358`, `492343`, `511489`
- **Extracted session:** `20260523_011902_88d1ec`
- **Request:** "Rebuild the trailer from memory"
- **Rebuild spec written:** `2026-05-28` (this session)

## HTML Rebuild
| Asset | Memory Derivation | Size | Recovery Method |
|-------|-------------------|------|-----------------|
| `trailer-final.html` | Memory id=511489 → `http://127.0.0.1:8911/video/lab/trailer-v14.html` → file copy | 9.9 KB | Direct file copy from `~/projects/mazemaker-architect/public/trailer-final.html` |
| `trailer4-final.html` | Memory id=492352 → beat timing + Three.js excerpts; build spec `TRAILER_TASK.md` beat-by-beat | 18.8 KB | Reconstructed from beat timing + VO/SFX cues |
| `trailer7-final.html` | Memory id=492352 → VO sync + federation moment | 15.1 KB | Reconstructed from "pods + bridges" scene |

## VO Lines (Neural Only)
| Source Filename | Content | Time | Duration | Channel |
|-----------------|-------------|------|----------|-------|
| `every-mind.wav` | "Every mind, one brain" | 2.8 s | 2.5 s | typewriter |
| `while-you-sleep.wav` | "While you sleep, Mazemaker remembers" | 8.1 s | 2.1 s | recall |
| `two-minds.wav` | "Two minds, joined" | 2.1 s | 2.7 s | federation |
| `your-key.wav` | "Your key to autonomous agents" | 9.8 s | 2.4 s | federation |
| `future.wav` | "The future is federated" | 16.5 s | 2.2 s | vision |
| `walk-through.wav` | "Walk through" | 12.4 s | 1.2 s | climax |

## SFX Cues (Neural Only)
| Filename | Type | Time | Trigger |
|----------|------|------|---------|
| `/assets/sfx/crt-click.wav` | Click | 0.3 s | Death start |
| `/assets/sfx/bloom.wav` | Bell | 7.5 s | Recall bloom |
| `/assets/sfx/thrash.wav` | Zapp | 20.1 s | Dream crash |
| `/assets/sfx/connect.wav` | Pulse | 1.5 s | Federation handshake |
| `/assets/sfx/pulse.wav` | Sub-pulse | 13.2 s | Helix collapse climax |

## Build Recovery Recipes

### 1. Recover `/tmp/mazemaker-vo/*.wav`
```bash
# Use Chatterbox to regenerate (existing takes assumed lost)
mkdir -p /tmp/mazemaker-vo/
for line in "Every mind" "One brain" "While you sleep" "Mazemaker remembers" \
           "Two minds" "joined" "Your key to autonomous agents" "The future is federated" \
           "Walk through"; do
  curl localhost:9091/synthesize?text="$line" -o /tmp/mazemaker-vo/${line// /-}.wav
  ffmpeg -i /tmp/mazemaker-vo/${line// /-}.wav -af "pan=stereo|c0=c0|c1=c0, loudnorm=I=-16" -y /tmp/mazemaker-vo/${line// /-}.norm.wav
  mv /tmp/mazemaker-vo/${line// /-}.norm.wav /tmp/mazemaker-vo/${line// /-}.wav
```

### 2. Add `manifest.json`
```json
{
 "lines": [
 {"file": "every-mind.wav", "text": "Every mind, one brain", "start": 2.8, "duration": 2.5},
 {"file": "while-you-sleep.wav", "text": "While you sleep, Mazemaker remembers", "start": 8.1, "duration": 2.1},
 {"file": "walk-through.wav", "text": "Walk through", "start": 12.4, "duration": 1.2},
 {"file": "two-minds.wav", "text": "Two minds, joined", "start": 2.1, "duration": 2.7},
 {"file": "your-key.wav", "text": "Your key to autonomous agents", "start": 9.8, "duration": 2.4},
 {"file": "future.wav", "text": "The future is federated", "start": 16.5, "duration": 2.2}
 ]
}
```

### 3. Firedragon Re-capture Batch
```bash
cd ~/projects/mazemaker-trailer-rebuild/
python3 -m http.server 31234 & # Serve HTMLs
sleep 2

cat > ~/godlike-batch.sh <<'EOF'
#!/bin/bash
set -eu
PORT=31234
OUTPUT=video/godlike/
mkdir -p $OUTPUT

# Trailer 1
firedragon-capture \
  --url "http://localhost:${PORT}/trailer-final.html" \
  --duration 15 \
  --profile hazel-sun \
  --output "${OUTPUT}/trailer1-final-16x9.mp4" \
  --size "1920,1080" \
  --fps 30
firedragon-capture \
  --url "http://localhost:${PORT}/trailer-final.html" \
  --duration 15 \
  --profile hazel-sun \
  --output "${OUTPUT}/trailer1-final-9x16.mp4" \
  --size "1080,1920" \
  --fps 30

# Trailer 4
firedragon-capture \
  --url "http://localhost:${PORT}/trailer4-final.html" \
  --duration 23 \
  --profile silver-violet \
  --output "${OUTPUT}/trailer4-final-16x9.mp4" \
  --size "1920,1080" \
  --fps 30
firedragon-capture \
  --url "http://localhost:${PORT}/trailer4-final.html" \
  --duration 23 \
  --profile silver-violet \
  --output "${OUTPUT}/trailer4-final-9x16.mp4" \
  --size "1080,1920" \
  --fps 30

# Trailer 7
firedragon-capture \
  --url "http://localhost:${PORT}/trailer7-final.html" \
  --duration 21 \
  --profile hazel-spark \
  --output "${OUTPUT}/trailer7-final-16x9.mp4" \
  --size "1920,1080" \
  --fps 30
firedragon-capture \
  --url "http://localhost:${PORT}/trailer7-final.html" \
  --duration 21 \
  --profile hazel-spark \
  --output "${OUTPUT}/trailer7-final-9x16.mp4" \
  --size "1080,1920" \
  --fps 30

pkill -f "python3.*31234"
EOF
chmod +x ~/godlike-batch.sh
```

### 4. FFmpeg Mix + Normalize
```bash
for f in trailer*-final-*.mp4; do
  base=${f%.mp4}
  ffmpeg -i "$f" \
    -stream_loop 1 -i "/tmp/mazemaker-vo/${base%-*}.wav" \
    -codec:v libx264 -pix_fmt yuv420p \
    -af "pan=stereo|c0=c0|c1=c0, loudnorm=I=-18" \
    -shortest \
    "${base}-mixed.mp4"
```

## Verification Checklist
- [ ] `git log` shows all 3 HTMLs committed with 1-line messages
- [ ] `video/godlike/` contains 6 MP4s post-firedragon capture
- [ ] `ffprobe` on each MP4 shows duration ±0.2 seconds vs memory
- [ ] `TRAILER_SPEC.md` lists every asset with derivation trail
- [ ] `/tmp/mazemaker-vo/manifest.json` lists every VO line
- [ ] `/tmp/mazemaker-vo/*.wav` exists and plays cleanly
- [ ] Firedragon profiles (`hazel-sun`, `silver-violet`, `hazel-spark`) are available
- [ ] Workspace is persistent + git-tracked (`~/projects/mazemaker-trailer-rebuild/`)