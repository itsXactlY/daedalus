# Media Content Generation Pipeline — Deployment Reference

Architecture designed 2026-06-14 for autonomous stickman/maze video generation loop.

## Machine Roles

| Machine | Hardware | Role | Software |
|---------|----------|------|----------|
| **alca-desktop** | RTX 4060 Ti 16GB VRAM, CUDA 13.3 | GPU worker | ComfyUI (WAN 2.2), Qwen3-TTS |
| **tpad** (Tpad-P50) | Quadro M2000M 4GB VRAM, CUDA 13.0 | Orchestrator | Hermes v0.15.1, Mazemaker MCP, llama-turbo (CPU-only) |

Connection: `mosh alca@alca-desktop -- ssh-cmd "ssh -J alca"` or direct SSH.

## Concept: "Mazemaker: Memory Maze"

An autonomous series where:
- A stickman ("The Wanderer") navigates a maze/labyrinth
- The maze layout is derived from Mazemaker's actual memory graph topology (spreading-activation paths, Louvain community clusters)
- Voiceover is philosophical/narrative about memory, knowledge, finding one's path
- Every video is unique because the maze changes as the memory graph grows
- Visual style: stickman (minimal B&W) against increasingly complex knowledge-graph labyrinths
- Marketing: "Powered by Mazemaker — 205,130 memories visualized. Find your way."

## Autonomous Loop (cron trigger, every 6h)

### Phase 1: Conceive (on orchestrator, ~30s)
```
1. mazemaker_recall("trending memory clusters") → top clusters
2. mazemaker_think(memory_id=X, depth=2) → graph neighbours
3. Generate concept: pick a cluster + a philosophical angle
4. Write narration script (60-90 seconds, ~150-200 words)
```

### Phase 2: Voiceover (on worker, ~60s per page)
```
1. Qwen3-TTS generate_custom_voice(text, speaker="aiden"|"ono_anna")
2. Parameters: temperature=0.7, top_p=0.9, max_new_tokens=4096
3. Output: WAV, 24kHz, mono, 16-bit PCM
4. Path: /output/voiceover_{tick}.wav
```

### Phase 3: Maze Layout (on worker, Python, ~5s)
```
1. Read mazemaker graph stats: top nodes, edge weights, cluster IDs
2. Convert to maze grid: cluster IDs → maze rooms, edge weights → corridor widths
3. Spreading-activation path → stickman's route through maze
4. Output: JSON maze layout matrix (ASCII or coordinate-based)
```

### Phase 4: Animation (on worker, ComfyUI, ~5-15 min)
```
1. ComfyUI API call with WAN 2.2 GGUF Q4
2. Prompt: stickman walking through abstract knowledge-graph labyrinth
3. Resolution: 720p, 81-161 frames (5-10 sec at 16fps)
4. Output: video segment(s)
```

### Phase 5: Assembly (on orchestrator or worker, ~30s)
```
1. ffmpeg: join video segments with voiceover audio track
2. Add title card: "Mazemaker: Memory Maze — Episode N"
3. Add subtle ambient sound/music
4. Output: /output/mazemaker_maze_{tick}.mp4
```

### Phase 6: Memorize (on orchestrator)
```
mazemaker_remember(
  label=f"media:tick-{date}-{seq}",
  content=f"Generated maze video episode {seq}. Concept: {concept}. Cluster: {cluster_name}. Duration: {seconds}s."
)
```

## ComfyUI API Setup

The worker machine needs ComfyUI running with `--listen 0.0.0.0` and `--enable-cors-header`:

```bash
comfy launch -- --listen 0.0.0.0 --port 8188 --enable-cors-header
```

Then the orchestrator sends prompts via POST to `http://worker-ip:8188/prompt` with a JSON workflow payload. The workflow ID comes back immediately; poll `http://worker-ip:8188/history/{workflow_id}` for the rendered output.

## Stickman Visual Design (to iterate on)

Key constraints for maintaining consistent character across ticks:
- Fixed CLIP text encoder seed for stickman character
- Consistent negative prompt (low quality, distorted, extra limbs)
- Maze aesthetic: monochrome or sepia, hand-drawn lines, minimalist
- Camera: tracking shot following the stickman, or birds-eye maze view
- The labyrinth walls should subtly suggest neural network / knowledge graph topology (nodes at junctions, edges as corridor walls)

## TTS Speaker Reference (Qwen3-TTS)

```python
spks = model.get_supported_speakers()
spks[0]  # 'aiden' — male, narrative/philosophical tone (primary narrator)
spks[1]  # 'dylan' — male, explainer/guide
spks[3]  # 'ono_anna' — female, wise/authority (could be "the maze itself")
```

## First Build Checklist

- [ ] Verify ComfyUI API is accessible from orchestrator
- [ ] Test single-completion pipeline: script → TTS → ffmpeg silence → verify output
- [ ] Test ComfyUI WAN 2.2 generation with stickman+maze prompt
- [ ] Generate first 3 test episodes for review
- [ ] Register cron job on orchestrator
- [ ] Create YouTube channel if publishing
