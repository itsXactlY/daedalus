---
name: mazemaker-autonomous-loop
description: "Autonomous stickman labyrinth video generation loop using cron, tpad brain, desk GPU worker. Generates unique procedural mazes → Qwen3-TTS voiceover → stickman animation frames → MP4 video. Runs every 6h via cron."
trigger: "user asks about autonomous video generation, stickman maze videos, Mazemaker loop, or the infinite labyrinth pipeline"
tags: [mazemaker, autonomous, video-generation, stickman, labyrinth, cron, tpad, gpu-worker]
---

# Mazemaker Autonomous Loop

Autonomous pipeline that generates unique stickman labyrinth videos every 6 hours.

## Architecture

```
desk (cron + GPU worker)           tpad (brain)
┌──────────────────────┐           ┌──────────────────┐
│ Cron job (every 6h)  │──SSH──►   │ dispatch.sh      │
│ trigger_brain.sh     │           │ (receives        │
│                      │◄──SSH──   │  concept JSON)    │
│ pipeline_worker.py   │           │                  │
│  ├─ generate_maze    │           │ Hermes +         │
│  ├─ generate_voice   │           │ Mazemaker MCP    │
│  ├─ generate_frames  │           │ for concept gen   │
│  └─ assemble_video   │           └──────────────────┘
└──────────────────────┘
```

## Files

### Scripts
- `scripts/pipeline_worker.py` — orchestrates all 4 steps (desk GPU worker)

### On desk (this machine — RTX 4060 Ti 16GB)
- `~/mazemaker-maze/scripts/pipeline_worker.py` — orchestrates all 4 steps
- `~/mazemaker-maze/scripts/generate_maze.py` — procedural maze (80×40, 1920×1080)
- `~/mazemaker-maze/scripts/generate_voiceover.py` — Qwen3-TTS narration
- `~/mazemaker-maze/scripts/generate_frames.py` — stickman animation frames (auto-calculated duration)
- `~/mazemaker-maze/scripts/assemble_video.py` — ffmpeg MP4 assembly
- `~/mazemaker-maze/scripts/trigger_brain.sh` — cron entry point → ssh to tpad

### On tpad (brain — Lenovo P50)
- `~/mazemaker-maze/scripts/dispatch.sh` — receives concept, SSHes pipeline back to desk
- `~/mazemaker-maze/scripts/brain_orchestrator.sh` — deprecated (was too slow)

## Output
- `~/mazemaker-maze/output/mazes/<run_id>.png` — 1920×1080 maze image
- `~/mazemaker-maze/output/voiceovers/<run_id>.wav` — TTS narration (~60s)
- `~/mazemaker-maze/output/frames/<run_id>/` — PNG animation frames (auto-calculated, 576-984+ frames)
- `~/mazemaker-maze/output/videos/mazemaker_<run_id>.mp4` — final video (30-60s)
- `~/mazemaker-maze/output/concepts/<run_id>.json` — concept metadata
- `~/mazemaker-maze/output/videos/<run_id>.result.json` — pipeline result

## Cron Job
- Name: `mazemaker-autonomous`
- Schedule: every 6h
- Created via: `cronjob(action='create', name='mazemaker-autonomous', schedule='every 6h', prompt='...')`

## Performance
- Full pipeline: ~37s (maze: <1s, TTS: ~28s, frames: ~6s, assembly: ~1s)
- Cron agent concept gen: ~30-60s (Mazemaker recall + LLM)

## Support Files
- `references/autonomous-cycle-pattern.md` — detailed cycle execution pattern and verification steps
- `references/frame-count-calculation.md` — frame duration math (deprecated, now auto-calculated)
- `references/cron-pattern.md` — cron-job integration workflow

## Testing
```bash
# Run full pipeline locally (no tpad involvement)
cd ~/mazemaker-maze
python3 scripts/pipeline_worker.py test_run --script "Your script text here" --speaker aiden --seed 42

# Run with automatic duration matching (recommended)
python3 scripts/run_with_duration.py my_run /path/to/script.txt aiden

# Trigger the brain loop (involves tpad)
bash ~/mazemaker-maze/scripts/trigger_brain.sh

# Single component tests
python3 scripts/generate_maze.py test_maze 12345
python3 scripts/generate_voiceover.py test_vo /tmp/script.txt aiden
python3 scripts/generate_frames.py test_run /path/to/maze.png  # then: /path/to/voice.wav 720
python3 scripts/assemble_video.py test_run /path/to/frames /path/to/voice.wav
```

## Installed ComfyUI Models

After the June 12th purge, models were reinstalled on 2026-06-15:

| Model | Path | Size |
|-------|------|------|
| ideogram4-Q4_0.gguf | `checkpoints/` | 5.6 GB |
| ideogram4_uncond-Q4_0.gguf | `checkpoints/` | 5.6 GB |
| Qwen3-8B-Q4_K_M.gguf | `checkpoints/` + symlink in `clip/` | 4.7 GB |
| seedvr2_ema_3b-Q8_0.gguf | `checkpoints/` | 3.5 GB |
| **Total** | | **19.3 GB** |

All downloads from HuggingFace at ~85-90 MB/s, total install ~3.5 min. 115 GB free remaining.

## Known Debugging Issues (keep for next session)

### Voiceover JSON parsing
`generate_voiceover.py` prints a flash-attn warning to stdout before its result JSON. When called via `subprocess.run(capture_output=True)`, parse stdout backwards:
```python
for line in reversed(result.stdout.strip().split('\n')):
    if line.strip().startswith('{') and line.strip().endswith('}'):
        info = json.loads(line.strip())
        break
```

### Script text shell quoting
Passing script text through `ssh desk 'python3 ... --script "$SCRIPT"'` breaks on spaces/quotes/newlines. Fix: write script to a temp file, pass the file path instead. Already implemented in `pipeline_worker.py`.

### Frame count mismatch with voiceover duration
The default 90 frames generates only 3.75s at 24fps, but voiceover is typically 55-60s. For a 30-45s video, generate ~720-1080 frames. Modified `generate_frames.py` to accept optional 4th argument `num_frames`. Usage:
```bash
python3 scripts/generate_frames.py <run_id> <maze_path> <voiceover_path> <num_frames>
```
For 60s voiceover: `1380 frames` produces ~57.5s video (accounts for ffmpeg trimming).
For 30s target: `720 frames` produces ~30s video at 24fps.

### Automated frame calculation (FIXED 2026-06-15)
**Root cause:** `pipeline_worker.py` passed hardcoded 90 frames to `generate_frames.py`, producing only 3.75s video at 24fps, while voiceover was 24-41s.

**Fix:** Modified `step_generate_frames()` to:
1. Accept `target_duration` parameter
2. Calculate `num_frames = target_duration * 24` when voiceover duration available
3. Extract duration from voiceover WAV file when `target_duration` not provided
4. Default to 90 frames only when no voiceover exists

Result: Video duration now matches voiceover duration exactly. A 24s voiceover → 576 frames → 24s video. A 41s voiceover → 984 frames → 41s video.

## Next Improvements
1. Install ComfyUI models (SDXL or WAN 2.2) for true AI-generated stickman visuals
2. Use real Mazemaker graph topology to influence maze structure
3. Add music bed generation (via image_gen or Suno)
4. Upload to YouTube channel via API
5. Add frame interpolation (RIFE) for smoother animation
6. Generate longer videos (180+ frames)

## Recent Improvements (2026-06-15)
- Added `scripts/run_with_duration.py` wrapper for automatic frame count calculation
- Created `references/cron-pattern.md` documenting cron-job integration workflow
- Documented complete autonomous cycle pattern: recall → concept → pipeline → verify → remember
