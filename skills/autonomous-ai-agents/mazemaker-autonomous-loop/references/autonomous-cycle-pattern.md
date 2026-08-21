# Autonomous Cycle Pattern (2026-06-15)

## Full Cycle Execution

When running the Mazemaker autonomous cycle, the pattern is:

1. **Concept Generation** (via trigger_brain.sh)
   - Generate unique concept title + philosophic script (30-45s narration)
   - Use timestamp-based seed for maze generation
   - Suggest visual mood (dark, contemplative)

2. **Dispatch** (tpad → desk)
   - SSH with base64-encoded script to avoid shell escaping issues
   - Pipeline worker handles all 4 steps on desk GPU

3. **Pipeline Steps** (desk GPU worker)
   ```
   Step 1: generate_maze.py → PNG (1920×1080)
   Step 2: generate_voiceover.py → WAV (24kHz, ~24-41s)
   Step 3: generate_frames.py → PNG frames (auto-calculated from voiceover)
   Step 4: assemble_video.py → MP4 (24fps)
   ```

4. **Duration Matching Fix**
   - Frames = voiceover_duration × 24
   - Implemented in `pipeline_worker.py::step_generate_frames()`
   - WAV header parsing for accurate duration extraction

5. **Verification**
   - ffprobe to confirm video duration matches voiceover
   - Result JSON saved to `~/mazemaker-maze/output/videos/<run_id>.result.json`

## Example Output (maze_1781543586)

| Component | Value |
|-----------|-------|
| Seed | 99706 |
| Voiceover Duration | 24.0s |
| Frames Generated | 576 |
| Video Duration | 24.0s |
| Video Size | 1.02 MB |
| Clusters | 4 |

## Script Generation Template

For 30-45s target:
- Word count: 60-100 words
- Topic: memory, knowledge, navigation, finding your way
- Tone: philosophical, contemplative, slightly dark
- Structure: 3-4 sentences with poetic flow