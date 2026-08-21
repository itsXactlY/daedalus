#!/usr/bin/env python3
"""
Test script for Mazemaker autonomous loop components.
Usage: python3 scripts/test_components.py
"""

import subprocess, sys, json, os, time

SCRIPTS = os.path.expanduser('~/mazemaker-maze/scripts')

def run_step(name, cmd):
    print(f"[TEST] {name}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  FAIL: {result.stderr[:200]}")
        return False
    print(f"  OK: {result.stdout[:100]}")
    return True

if __name__ == '__main__':
    run_id = f"test_{int(time.time())}"
    
    # Test maze generation
    run_step("Maze", ['python3', f'{SCRIPTS}/generate_maze.py', run_id, '12345'])
    
    # Test voiceover (uses fallback sine wave since Qwen may not be available)
    run_step("Voiceover", ['python3', f'{SCRIPTS}/generate_voiceover.py', run_id, '/dev/stdin', 'aiden'])
    
    print(f"\n[Test complete for {run_id}]")