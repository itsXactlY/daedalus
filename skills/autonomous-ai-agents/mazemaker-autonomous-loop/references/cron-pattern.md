# Cron-Job Integration Pattern

## The Pattern
When running the Mazemaker loop as a Hermes cron job, the agent generates concepts via Mazemaker recall, then executes the pipeline. Key integration points:

### 1. Concept Generation (via mazemaker_browse/recall)
- Query recent memories for thematic clusters
- Extract philosophical angle (memory, knowledge, navigation)
- Generate unique title and script (~50-60 words for 55-60s voiceover)

### 2. Seed Derivation
Use `date +%N | cut -c1-5` for 5-digit maze seed, or `date +%s % 100000` for deterministic hash-based seed.

### 3. Pipeline Execution
For cron jobs, use the `run_with_duration.py` wrapper to automatically calculate frame count based on voiceover duration, ensuring the output video covers the full narration.

### 4. Output Verification
After pipeline completion, verify:
- Video exists and duration matches target (30-45s)
- Maze has reasonable cluster count (3-8 clusters typical)
- Voiceover quality is acceptable (no clipping, natural pacing)

### 5. Memory Persistence
Save completed cycle to Mazemaker graph with label `ops:autonomous-cycle-complete` including:
- run_id, seed, video path
- Duration achieved
- Theme/concept explored