# `pulse_state.json` Control-Character Corruption Fix

## Symptom

`python3 ~/.hermes/loops/pulse-wurm2/pulse_tick.py` crashes with:

```
json.decoder.JSONDecodeError: Invalid control character at: line N column M (char K)
```

The crash points at a specific line/column in `pulse_state.json`. The control char is almost always `\x1a` (SUB, ASCII 26) embedded in a string-typed field, but any char in the range `\x00-\x1f` (except `\t` `\n` `\r`) can cause this.

## Root cause

An unescaped control character leaked into a string field — most likely `discovery_topics[]` (which holds free-form tick summaries and discovery memos). The most common vectors observed in 2026-06-20 ticks:

- A tool result that contained a raw `\x1a` and was stored verbatim.
- A prompt-injection text block that included control chars and was captured into a `discovery_topics` entry.
- A copy-paste from a terminal paste buffer that included escape sequences.

## Why `pulse_search` and `pulse_research_start` are unaffected

These MCP tools do not read `pulse_state.json` — they talk to the Pulse pod directly. So even when the state file is corrupted, the discovery channel keeps working. Only the **state-update path** (`pulse_tick.py` and the cron-kickoff agent that writes to `pulse_state.json`) is blocked.

## Fix recipe — preserves all data, no loss

The corruption is in a string, not in the JSON structure. `json.loads(text, strict=False)` succeeds even with control chars in strings — the parser accepts them as part of string content. So:

1. **Read** the file as text (do not parse yet)
2. **Strip** the control chars (replace with space) — this is the surgical fix
3. **Parse** with `strict=False` to validate the structure is intact
4. **Re-write** with `ensure_ascii=False, indent=2` to match the existing format

```python
#!/usr/bin/env python3
"""Fix pulse_state.json control-character corruption in-place.

Symptom: json.decoder.JSONDecodeError: Invalid control character at: line N column M
Run this when pulse_tick.py or any state-reader crashes with that error.
"""
import json
import os
import re
import sys

PATH = os.path.expanduser('~/.hermes/loops/pulse-wurm2/pulse_state.json')
# Also fix the inline-state backup if present
BACKUP = os.path.expanduser('~/.hermes/loops/pulse-wurm2/pulse_state.json.bak')

def fix_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, 'rb') as f:
        data = f.read()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = data.decode('utf-8', errors='replace')
    # Replace control chars except tab (\x09), newline (\x0a), CR (\x0d) with space
    fixed = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', text)
    try:
        state = json.loads(fixed, strict=False)
    except json.JSONDecodeError as e:
        print(f'  FAILED: structural JSON error after control-char strip: {e}')
        return False
    # Preserve structure exactly
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f'  FIXED: {path}')
    print(f'    size: {os.path.getsize(path)} bytes')
    print(f'    discovery_topics: {len(state.get("discovery_topics", []))}')
    print(f'    visited_urls: {len(state.get("visited_urls", []))}')
    print(f'    next_seeds: {len(state.get("next_seeds", []))}')
    return True

print('Pulse-state control-character corruption fix')
print('=' * 50)
ok_main = fix_file(PATH)
ok_backup = fix_file(BACKUP) if os.path.exists(BACKUP) else False
sys.exit(0 if ok_main else 1)
```

## Preflight recipe (run BEFORE pulse_tick.py)

A 1-line preflight that catches the corruption before `pulse_tick.py` crashes:

```bash
python3 -c "import json,sys; json.load(open('$HOME/.hermes/loops/pulse-wurm2/pulse_state.json'))" \
  || python3 -c "
import json, re, os
p = os.path.expanduser('~/.hermes/loops/pulse-wurm2/pulse_state.json')
t = open(p, 'rb').read().decode('utf-8', errors='replace')
s = json.loads(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', t), strict=False)
json.dump(s, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('pulse_state.json was corrupted — fixed.')
"
```

## Validation

After the fix, all data is preserved:
- `discovery_topics` count unchanged (just spaces inserted where control chars were)
- `visited_urls` count unchanged
- `next_seeds` order unchanged
- `saturation_scores` unchanged
- `last_tick` / `consecutive_empty` unchanged

The 2026-06-20 18:36Z tick applied this fix to a 389 KB file with 248 discovery_topics and 2958 visited_urls — all 2958+248 entries preserved through the round-trip.

## Prevention

- When saving tick summaries into `discovery_topics`, scrub the content for control chars before calling `mazemaker_remember` (or before writing to the state file directly). A one-liner: `content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', content)`.
- The Pulse MCP tool results sometimes include control chars in their JSON-encoded bodies (e.g., `\u001a` escapes). When extracting text from a tool result for storage, unescape first, then scrub.
- The pulse_state.json `.bak` files are NOT auto-rotated; the cron-kickoff agent should rotate `.bak` periodically (the existing script does NOT do this — known gap).
