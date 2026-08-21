# Multi-Comic Pipeline — Orchestration Pattern

For generating multiple comic series in parallel, with resume capability, content filter handling, and daily quota management. Proven pattern from the 11-comic Mazemaker Universe generation (105 images across 7 complete comics).

## Architecture

```
Phase 1: WRITE (pro model)
  └─ Source story → Characters → Storyboard → 15 page prompts
  └─ Delegate to subagents in parallel (3 at a time)

Phase 2: GENERATE (riverflow, free tier)
  └─ Launch 5 concurrent generation processes
  └─ Stagger bonus comics every 60s
  └─ Wait for completion notifications
  └─ Retry failed pages (content filter → rewrite → retry)

Phase 3: RETRY (next quota cycle)
  └─ Rewrite blocked prompts (focus on data/systems layer)
  └─ Delete failed output files
  └─ Re-run generation script (resumes automatically)
```

## Phase 1: Writing (Use Pro Model)

Delegate story writing to subagents for throughput:

```python
delegate_task(tasks=[
    {"goal": "Write comic #1 story + prompts", "toolsets": ["terminal","file"]},
    {"goal": "Write comic #2 story + prompts", "toolsets": ["terminal","file"]},
    {"goal": "Write comic #3 story + prompts", "toolsets": ["terminal","file"]},
])
```

Each subagent creates 18 files:
- `source-{slug}.md` — prose narrative
- `characters/characters.md` — character definitions
- `storyboard.md` — 15-page panel breakdown
- `prompts/00-cover.md` through `prompts/14-epilogue.md` — per-page prompts

Every prompt file MUST contain:
1. Character descriptions embedded (for cross-page consistency)
2. Shared Story Timeline (1-2 sentences summarizing story position)
3. Art Style specification
4. Scene description with panel layouts (16:9 landscape)
5. `[DIALOGUE: ...]` / `[LABEL PLATE: ...]` markers for blank speech bubbles
6. NO baked text — all typography is post-production

## Phase 2: Generation Script (Resume-Capable)

Each comic needs its own generation script with these properties:

```python
# Resume: skip existing files
if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
    log(f"SKIP (exists): {outpath}")
    continue

# Retry: max 2 attempts per page
for attempt in range(1, 3):
    result = call_riverflow(prompt)
    if result: break
    time.sleep(10)

# Continue on failure: don't stop the whole batch
if not result:
    log(f"FAIL: {page}")
    failed_pages.append(page)
    # Move on — retry later with rewritten prompt
```

## Phase 2: Launch Strategy

```bash
# Start 5 partial comics immediately (they skip existing pages)
bash run_gen.sh 02  # 1 page remaining
bash run_gen.sh 03  # 9 pages remaining
bash run_gen.sh 04  # 7 pages remaining
bash run_gen.sh 05  # 7 pages remaining
bash run_gen.sh 06  # 9 pages remaining

# Stagger bonus comics every 60s to avoid hammering the API
sleep 120 && bash run_gen.sh 07
sleep 180 && bash run_gen.sh 08
sleep 240 && bash run_gen.sh 09
sleep 300 && bash run_gen.sh 10
sleep 360 && python3 generate_11_eternal.py
```

## Content Filter Handling

SEE `references/riverflow-openrouter-api.md` → "Content Filter Triggers" for the complete table.

When a page triggers the filter:
1. Identify the blocked element (surgery/combat/rescue/injury)
2. Rewrite the prompt to focus on DATA/SYSTEMS — never on physical harm
3. DELETE the failed output file (so the resume check doesn't skip it)
4. Re-run the generation script

## Daily Quota Planning

Riverflow free tier: ~57 images/day at ~170s per image = ~2.7 hours.

Maximize output by:
1. Launching 5 concurrent streams immediately
2. Prioritize completing existing partial comics before starting new ones
3. The staggered bonus comics will hit the quota when it runs out — that's expected
4. Next day: retry failed pages + generate bonus comics

## Content Filter Hit Rates

From the 11-comic Mazemaker Universe generation (165 pages attempted):

| Trigger | Pages Blocked | Fix Success Rate |
|---------|--------------|------------------|
| Surgery / OR | 1 of 1 | 100% (rewrite → data viz) |
| Drone strike / explosions | 1 of 1 | 100% (rewrite → tactical map) |
| Trapped child / rubble rescue | 1 of 1 | 100% (rewrite → terminal screen) |
| Provider timeout (>300s) | 1 of 2 | 50% (retry succeeded) |
| Rate limited (daily quota) | ~55 of 165 | N/A (waited for reset) |

## File Layout

```
/home/alca/comic/mazemaker-use-cases/
├── MANIFEST.md                  # Master index of all comics
├── gallery.html                 # HTML gallery (dark theme)
├── generate_all.py              # Multi-comic generation script (resume-capable)
├── run_gen.sh                   # Bootstrap runner (reads API key from config)
├── run_all_remaining.sh         # Sequential runner for all remaining comics
├── test_quota.py                # Quick quota check
├── logs/                        # Per-comic generation logs
├── 01-medical-frontier/         # Each comic: source, characters, storyboard, prompts, outputs/
│   ├── source-*.md
│   ├── characters/characters.md
│   ├── storyboard.md
│   ├── prompts/00-*.md ... 14-*.md
│   └── outputs/                # Generated .webp images
└── ... 10 more comic directories
```
