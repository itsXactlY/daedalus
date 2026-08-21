# Flux Dev fp8 — Setup & Workflow Guide

## Model Sources (16 GB VRAM target)

### Download using huggingface_hub (preferred over `comfy model download`)

```python
from huggingface_hub import hf_hub_download

# 1. UNET / diffusion model (~7 GB on disk, 17 GB xet)
#    alternative: curl -L -o models/checkpoints/flux1-dev-fp8.safetensors \
#      "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors"

# 2. CLIP models (public repo — no auth needed)
hf_hub_download('comfyanonymous/flux_text_encoders', 'clip_l.safetensors',
    local_dir='models/clip')
hf_hub_download('comfyanonymous/flux_text_encoders', 't5xxl_fp8_e4m3fn.safetensors',
    local_dir='models/clip')

# 3. VAE (gated — needs HF token with access to black-forest-labs/FLUX.1-dev)
from huggingface_hub import login
login(token='YOUR_HF_TOKEN')
hf_hub_download('black-forest-labs/FLUX.1-dev', 'ae.safetensors',
    local_dir='models/vae')
```

### `comfy model download` caveat
- Fails with "Input is not a terminal (fd=0)" when called inside Hermes terminal tool
- Workaround: use `curl -L` directly or `huggingface_hub` via venv Python

## Model Layout (ComfyUI 0.22.0)

| File | Directory | Loader | Purpose |
|------|-----------|--------|---------|
| `flux1-dev-fp8.safetensors` | `models/checkpoints/` | CheckpointLoaderSimple | UNET + model wrapper |
| `clip_l.safetensors` | `models/clip/` | DualCLIPLoader | CLIP-L text encoder |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/clip/` | DualCLIPLoader | T5 text encoder |
| `ae.safetensors` | `models/vae/` | VAELoader | Flux-specific VAE |

**CRITICAL**: `flux1-dev-fp8.safetensors` goes in `models/checkpoints/` NOT `models/unet/`.
- `CheckpointLoaderSimple` scans `models/checkpoints/` and auto-wraps Flux models
- `UNETLoader` scans `models/unet/` — this directory is empty by default
- If you get `"unet_name: 'flux1-dev-fp8.safetensors' not in []"`, the model is in
  the wrong folder — remove `_meta`/`_comment` from the workflow JSON first though
  (see below), because the same 500 error can come from _meta pollution

## Workflow: CheckpointLoaderSimple Approach (Recommended for fp8)

Modern ComfyUI (≥0.22.0) handles Flux through `CheckpointLoaderSimple`:

```json
{
  "3": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"}
  },
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {"text": "your prompt", "clip": ["3", 1]}
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {"samples": ["31", 0], "vae": ["3", 2]}
  },
  "9": {
    "class_type": "SaveImage",
    "inputs": {"filename_prefix": "output", "images": ["8", 0]}
  },
  "27": {
    "class_type": "EmptySD3LatentImage",
    "inputs": {"width": 1216, "height": 832, "batch_size": 1}
  },
  "16": {
    "class_type": "KSamplerSelect",
    "inputs": {"sampler_name": "euler"}
  },
  "17": {
    "class_type": "BasicScheduler",
    "inputs": {"scheduler": "simple", "steps": 30, "denoise": 1.0, "model": ["3", 0]}
  },
  "25": {
    "class_type": "RandomNoise",
    "inputs": {"noise_seed": 42}
  },
  "22": {
    "class_type": "BasicGuider",
    "inputs": {"model": ["3", 0], "conditioning": ["6", 0]}
  },
  "31": {
    "class_type": "SamplerCustomAdvanced",
    "inputs": {
      "noise": ["25", 0], "guider": ["22", 0],
      "sampler": ["16", 0], "sigmas": ["17", 0],
      "latent_image": ["27", 0]
    }
  }
}
```

### Node wiring (CheckpointLoaderSimple outputs):
- Output [0] = MODEL → KSamplerSelect / BasicGuider
- Output [1] = CLIP → CLIPTextEncode
- Output [2] = VAE → VAEDecode

### Resolution guidelines for Flux
- Native resolutions: 1024x1024, 1216x832, 1344x768, 1536x640
- Stick to these for best quality; upscale afterwards for 4K

## Workflow JSON Cleanliness (New Pitfall)

ComfyUI 0.22.0 API strictly validates prompt structure. **Every extra field
crashes the submission with HTTP 500.**

- **Remove `_meta` fields** like `{"title": "My Node"}` — these cause
  `AttributeError: 'str' object has no attribute 'get'` in execution validation
- **Remove `_comment` fields** — same parsing failure
- A clean workflow node has exactly two keys: `class_type` and `inputs`
- The workflow template at `workflows/flux_dev_txt2img.json` has `_meta` keys —
  strip them before submitting via the API

Symptoms: `"Submission HTTP error", http_status: 500` from `run_workflow.py`,
with server log showing `node_data.get('_meta')` → `AttributeError`.

## Performance (RTX 4060 Ti, 16 GB VRAM)

| Resolution | Steps | Time | VRAM |
|------------|-------|------|------|
| 1024x1024 | 30 | ~85s | ~13 GB |
| 1216x832 | 30 | ~95s | ~14 GB |
| 1024x1024 | 20 | ~60s | ~13 GB |

Flux fp8: ~7 GB UNET + ~5 GB T5 CLIP = ~12-14 GB total.
CheckpointLoaderSimple auto-handles weight dtype.
