# Local ComfyUI Generation for Comics

When the `image_generate` tool (FAL) is unavailable due to missing API keys or credits, use **local ComfyUI** via the `creative/comfyui` skill for comic panel generation.

## When to Use

- FAL_KEY not set / no paid credits
- Need full control over model, resolution, sampling
- Generating many panels (batch) without API rate limits
- Custom character consistency via prompt engineering (not reference images)

## Setup

1. Run hardware check:
   ```bash
   python3 /home/alca/.hermes/skills/creative/comfyui/scripts/hardware_check.py --json
   ```
   Need: NVIDIA GPU ≥8 GB VRAM for SDXL/Flux, or Apple Silicon ≥16 GB unified.

2. Install ComfyUI locally:
   ```bash
   bash /home/alca/.hermes/skills/creative/comfyui/scripts/comfyui_setup.sh
   ```
   Or manually: `pipx install comfy-cli && comfy install --nvidia`

3. **Critical Python 3.14+ workaround**: `comfy launch --background` crashes with `RuntimeError: There is no current event loop`. Use manual background launch instead:
   ```bash
   cd ~/comfy/ComfyUI && .venv/bin/python main.py --listen 127.0.0.1 --port 8188
   ```
   Run via `terminal(background=true, notify_on_complete=true)`. Verify with `curl http://127.0.0.1:8188/system_stats`.

## Model Recommendations

| Use Case | Model | Loader | Resolution |
|----------|-------|--------|------------|
| Manga/Anime | Flux Dev fp8 | CheckpointLoaderSimple | 832×1216 (3:4) |
| General | SDXL | CheckpointLoaderSimple | 1024×1024 |
| Lightweight | SD 1.5 | CheckpointLoaderSimple | 512×768 |

**Flux fp8 layout** (required):
- `flux1-dev-fp8.safetensors` → `models/checkpoints/`
- `clip_l.safetensors` + `t5xxl_fp8_e4m3fn.safetensors` → `models/clip/`
- `ae.safetensors` → `models/vae/`
- Use `CheckpointLoaderSimple` (outputs: MODEL, CLIP, VAE) — NOT `UNETLoader`

## Workflow JSON Cleanliness

ComfyUI 0.22.0+ strictly validates API format. **Every node must have exactly two keys: `class_type` and `inputs`**. Strip all `_meta`, `_comment`, and other extra fields before submission.

## Character Consistency

Since `image_generate` (and ComfyUI) is **prompt-only**, character consistency is enforced by **embedding character descriptions inline in every page prompt**. Write detailed character definitions to `characters/characters.md` (per `references/character-template.md`), then include key identifying features in each page prompt.

## Batch Generation Pattern

For multi-page comics (10-20 pages), create a batch script:

```python
# Template: /home/alca/comic/mazemaker-inception-os/scripts/batch_generate.py
# 1. Load base workflow (clean API format, CheckpointLoaderSimple for Flux)
# 2. For each prompt file: inject prompt text, set filename_prefix, set seed
# 3. Submit via run_workflow.py --workflow /tmp/workflow_X.json --output-dir ./outputs
# 4. Use fixed seeds per page for reproducibility (e.g., 100, 101, 102...)
```

## Integration with baoyu-comic Workflow

| baoyu-comic Step | Local ComfyUI Adaptation |
|------------------|--------------------------|
| Step 5: Generate prompts | Write prompt files as usual (`prompts/NN-page-slug.md`) |
| Step 7.1: Character sheet | Generate via ComfyUI batch script (optional) |
| Step 7.2: Generate pages | Run batch script instead of `image_generate` tool |
| Output | PNGs land in `comic/{slug}/outputs/` — copy to `NN-page-slug.png` |

## Pitfalls

1. **Seed must be ≥0** — `RandomNoise` node rejects `-1`. Use fixed seeds per page.
2. **Aspect ratio mapping** — 3:4 comic pages → `width: 832, height: 1216` in `EmptySD3LatentImage`.
3. **Background process stdout may be empty** — output goes to stderr. Don't rely on `watch_patterns`. Poll via `curl` instead.
4. **Flux fp8 in wrong folder** → `unet_name not in []` error. Must be in `models/checkpoints/` with `CheckpointLoaderSimple`.
5. **Workflow JSON extra fields** → HTTP 500 `AttributeError: 'str' object has no attribute 'get'`. Clean all `_meta`, `_comment`.