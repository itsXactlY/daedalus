# Riverflow Batch Generation with Resume

Pattern for generating large multi-comic batches (6+ comics, 90+ pages) via sourceful/riverflow-v2.5-pro:free with resilience, resume, and logging.

## Architecture

```
run_gen.sh (bootstrap: extracts key, sets env, calls generate_all.py)
  → generate_all.py (orchestrator: iterates comics → pages, skips existing)
    → generate_page() (single riverflow API call with retries)
```

## Core Pattern: generate_all.py

```python
# ─── CONFIG ────────────────────────────────────────────────
COMICS = [
    {"id": "01", "slug": "comic-slug", "style": "art style description",
     "prompt_dir": "01-comic-slug"},
]

# API key read at runtime (never hardcoded — write_file redacts keys)
def get_api_key():
    with open('/home/alca/.hermes/config.yaml') as f:
        c = f.read()
    idx = c.find('opendeepseek:')
    if idx < 0: idx = c.find('openddeepseek:')
    s = c[idx:idx+200]; k = s.find('api_key:')
    return s[k+9:k+82].strip().strip("'").strip('"').strip()

# Resume: skip already-generated files
if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
    log_f.write(f"SKIP (exists): {base_name} ({os.path.getsize(outpath)} bytes)\n")
    success_count += 1
    continue

# Retry logic — 2 attempts, API error handling
for attempt in range(1, max_retries + 1):
    # ... call riverflow ...
    if 'error' in d and d['error']:
        if "rate" in err_msg.lower() or "429" in err_msg:
            time.sleep(30); continue  # Rate limited
        if attempt < max_retries: time.sleep(10); continue
```

## API Key Handling (Critical)

The key MUST be read at runtime, never written into a `.py` file. When `write_file` or `skill_manage write_file` detects an `sk-or-` pattern, it REDACTS it to `***`, breaking the script. Solution:

```python
# In the Python script itself:
def get_api_key():
    with open('/home/alca/.hermes/config.yaml') as f: ...
```

Or via a bootstrap shell script that passes the key as an environment variable:

```bash
#!/bin/bash
KEY=$(python3 -c "
with open('/home/alca/.hermes/config.yaml') as f: c = f.read()
i = c.find('opendeepseek:'); s = c[i:i+200]; k = s.find('api_key:')
print(s[k+9:k+82].strip().strip(\"'\").strip('\"').strip())
")
HERMES_RIVERFLOW_KEY="$KEY" python3 generate_all.py "$@"
```

## Prompt File Structure

Each comic directory:
```
comic-slug/
├── source-{slug}.md           # Full story narrative
├── characters/characters.md    # Character definitions
├── storyboard.md               # 15-page panel breakdown
├── prompts/
│   ├── 00-cover.md             # One file per page
│   ├── 01-page-name.md
│   └── ...
└── outputs/                    # Generated .webp files (created by script)
```

## Prompt File Format (per page)

```markdown
# Page NN: Title

## Characters
[Embedded character descriptions — crucial for consistency]

## Shared Story Timeline
[1-2 sentence story position summary — helps riverflow maintain continuity]

## Art Style
[One of the 23 pre-tested styles from mazemaker-art-styles.md]

## Scene Description
[3-5 panel layout, detailed visual descriptions]

## Dialogue / Narration Zones
- SPEECH BUBBLE 1: [DIALOGUE: text]
- NARRATOR BOX: [NARRATOR: text]
- LABEL PLATE: [TERM: text]

IMPORTANT: Describe empty speech-bubble zones. Do NOT render text in the image — letterer adds text later.
```

## Known Pitfalls

1. **Don't use `reasoning: {"effort": "xhigh"}` for production** — use `"high"`. xhigh regularly times out at 300s with no quality benefit over high.

2. **Don't describe surgery, combat, explosions, or gore** — Sourceful blocks these with HTTP 422. Rewrite as data-visualization scenes.

3. **Don't run duplicate processes** — each additional concurrent process for the same comic causes duplicate API calls and wasted rate limit. Kill stale processes with `pkill -f generate_all.py` before restarting.

4. **Don't use 21:9 aspect ratio** — causes HTTP 500. Stick to 16:9 landscape.

5. **Don't rely on Hermes process(action='wait') for long batches** — wait times are clamped to 60s. Use `notify_on_complete=True` or check logs manually.

6. **Always use `--max-time` with curl** — riverflow can hang; timeout kills the request cleanly.

## Process Management Pattern

```python
# Launch from terminal with notify
terminal(background=True, notify_on_complete=True,
         command="bash run_gen.sh 01")

# Check logs periodically
terminal(f"tail -5 /path/to/logs/01-comic.log", timeout=10)

# Kill all stale processes before restart
terminal("pkill -f generate_all.py", timeout=5)

# Launch all comics in parallel (not sequential — too slow)
for comic in range(2, 7):
    terminal(background=True, notify_on_complete=True,
             command=f"bash run_gen.sh 0{comic}")
```

## Expected Throughput

| Setup | Pages/Hour | Notes |
|-------|-----------|-------|
| 1 process, high reasoning | ~20 | 170s avg per page |
| 3 concurrent, high reasoning | ~60 | No rate limiting observed |
| 5 concurrent, high reasoning | ~90 | More prone to timeouts |
