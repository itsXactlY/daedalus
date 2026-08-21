# Frame Count Calculation Reference

## Problem
Default 90 frames at 24fps = 3.75 seconds, but voiceover duration is typically 55-60 seconds.

## Solution
Generate frames matching voiceover duration:

| Target Duration | Frames Needed (24fps) | Note |
|-----------------|----------------------|------|
| 10s | 240 | Short teaser |
| 30s | 720 | Half voiceover |
| 45s | 1080 | 1.5x voiceover padding |
| 60s | 1380 | Full voiceover (ffmpeg -shortest reduces ~5% trimming) |

## Usage
```bash
python3 scripts/generate_frames.py <run_id> <maze_path> <voiceover_path> <num_frames>
```

## Implementation
Modified `generate_frames.py` line 125-140 to accept optional 4th argument.

## Example
For 60s voiceover (recorded at natural pace):
```bash
python3 scripts/generate_frames.py maze_run maze_result.png voice_result.wav 1380
```
This produces ~57.5s final video due to ffmpeg `-shortest` flag trimming silence.