#!/usr/bin/env python3
"""
Mazemaker Pipeline Wrapper with automatic frame calculation.
Ensures video duration matches or exceeds voiceover duration.
"""

import json
import sys
import os
import subprocess
import time

BASE = "/home/alca/mazemaker-maze"
SCRIPTS = f"{BASE}/scripts"
OUTPUT = f"{BASE}/output"

def run_pipeline(run_id, script_text, speaker="aiden", duration_target=45):
    """Run full pipeline with calculated frame count for target duration."""
    
    # Step 1: Generate maze
    print(f"[{time.strftime('%H:%M:%S')}] Step 1/4: Maze generation...")
    seed = hash(run_id) % 100000
    result = subprocess.run(
        ['python3', f'{SCRIPTS}/generate_maze.py', run_id, str(seed)],
        capture_output=True, text=True, timeout=120
    )
    maze_info = json.loads(result.stdout.strip())
    maze_path = maze_info['path']
    
    # Step 2: Generate voiceover
    print(f"[{time.strftime('%H:%M:%S')}] Step 2/4: Voiceover generation...")
    script_file = f"{OUTPUT}/voiceovers/{run_id}_script.txt"
    os.makedirs(os.path.dirname(script_file), exist_ok=True)
    with open(script_file, 'w') as f:
        f.write(script_text)
    
    result = subprocess.run(
        ['python3', f'{SCRIPTS}/generate_voiceover.py', run_id, script_file, speaker],
        capture_output=True, text=True, timeout=300
    )
    # Parse JSON from stdout (skip warnings)
    for line in reversed(result.stdout.strip().split('\n')):
        if line.strip().startswith('{') and line.strip().endswith('}'):
            voice_info = json.loads(line.strip())
            break
    voice_path = voice_info['path']
    
    # Step 3: Calculate and generate frames
    # For 24fps, need enough frames to cover voiceover duration
    voiceover_sec = voice_info['duration_sec']
    # Add 10% buffer for ffmpeg trimming
    num_frames = int(voiceover_sec * 24 * 1.1)
    num_frames = max(num_frames, 720)  # Minimum 30s
    
    print(f"[{time.strftime('%H:%M:%S')}] Step 3/4: Frame generation ({num_frames} frames)...")
    result = subprocess.run(
        ['python3', f'{SCRIPTS}/generate_frames.py', run_id, maze_path, voice_path, str(num_frames)],
        capture_output=True, text=True, timeout=300
    )
    frame_info = json.loads(result.stdout.strip())
    frame_dir = frame_info['frame_dir']
    
    # Step 4: Assemble video
    print(f"[{time.strftime('%H:%M:%S')}] Step 4/4: Video assembly...")
    result = subprocess.run(
        ['python3', f'{SCRIPTS}/assemble_video.py', run_id, frame_dir, voice_path, '24'],
        capture_output=True, text=True, timeout=300
    )
    video_info = json.loads(result.stdout.strip())
    
    return {
        'run_id': run_id,
        'maze': maze_info,
        'voiceover': voice_info,
        'frames': frame_info,
        'video': video_info
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: run_with_duration.py <run_id> <script_file> [speaker]")
        sys.exit(1)
    
    run_id = sys.argv[1]
    script_file = sys.argv[2]
    speaker = sys.argv[3] if len(sys.argv) > 3 else "aiden"
    
    with open(script_file) as f:
        script_text = f.read()
    
    result = run_pipeline(run_id, script_text, speaker)
    print(json.dumps(result, indent=2))