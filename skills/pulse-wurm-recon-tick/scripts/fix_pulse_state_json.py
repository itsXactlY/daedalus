#!/usr/bin/env python3
"""Fix pulse_state.json control-character corruption in-place.

Symptom: json.decoder.JSONDecodeError: Invalid control character at: line N column M
Run this when pulse_tick.py or any state-reader crashes with that error.

Companion to references/pulse-state-json-corruption-fix.md in the
pulse-wurm-recon-tick skill.
"""
import json
import os
import re
import sys

PATH = os.path.expanduser('~/.hermes/loops/pulse-wurm2/pulse_state.json')
BACKUP = os.path.expanduser('~/.hermes/loops/pulse-wurm2/pulse_state.json.bak')

# Control char regex: keep \t (0x09), \n (0x0a), \r (0x0d); replace rest
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def fix_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, 'rb') as f:
        data = f.read()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = data.decode('utf-8', errors='replace')
    fixed = CONTROL_CHAR_RE.sub(' ', text)
    try:
        state = json.loads(fixed, strict=False)
    except json.JSONDecodeError as e:
        print(f'  FAILED: structural JSON error after control-char strip: {e}')
        return False
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f'  FIXED: {path}')
    print(f'    size: {os.path.getsize(path)} bytes')
    print(f'    discovery_topics: {len(state.get("discovery_topics", []))}')
    print(f'    visited_urls: {len(state.get("visited_urls", []))}')
    print(f'    next_seeds: {len(state.get("next_seeds", []))}')
    print(f'    saturation_scores: {len(state.get("saturation_scores", {}))}')
    return True


def main() -> int:
    print('Pulse-state control-character corruption fix')
    print('=' * 50)
    ok_main = fix_file(PATH)
    ok_backup = fix_file(BACKUP) if os.path.exists(BACKUP) else False
    if not ok_main:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())