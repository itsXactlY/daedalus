# Infographic Generation Recipe

## Context

When the user asks to create an infographic "like this" and provides a reference image (e.g., the "Clone Profiles From Any Source" style), they want:

- **Dark blue grid background** with scientific/lab theme
- **Teal and pink neon accents** for highlights
- **Structured sections** (numbered, left-to-right flow)
- **Technical icons** (API diagrams, lab flasks, gears, checkmarks)
- **Clean modern design** with readable text

## Preferred Approach

**Use ComfyUI with SDXL** when the user explicitly asks to "use the comfy setup" or when HTML-rendered infographics are rejected as "trash" or "pathetic". Do not keep iterating on HTML/CSS after a quality correction — switch methods.

## Minimal SDXL Workflow (API Format)

```json
{
  "1": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}
  },
  "2": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "A professional technical infographic titled '<TITLE>'. Dark blue grid background with scientific laboratory theme. <SECTION_DETAILS>. Teal and pink neon accents, clean modern design, technical icons, dark blue background with subtle grid pattern, white and cyan text, professional layout, high quality, sharp details",
      "clip": ["1", 1]
    }
  },
  "3": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "blurry, low quality, distorted, bad text, misspelled, ugly, deformed, watermark, signature, low resolution, grainy, noisy, out of frame",
      "clip": ["1", 1]
    }
  },
  "4": {
    "class_type": "EmptyLatentImage",
    "inputs": {"width": 1024, "height": 576, "batch_size": 1}
  },
  "5": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 42,
      "steps": 30,
      "cfg": 7.5,
      "sampler_name": "dpmpp_2m",
      "scheduler": "karras",
      "denoise": 1.0,
      "model": ["1", 0],
      "positive": ["2", 0],
      "negative": ["3", 0],
      "latent_image": ["4", 0]
    }
  },
  "6": {"class_type": "VAEDecode", "inputs": {"vae": ["1", 2], "samples": ["5", 0]}},
  "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "<TOPIC>-infographic", "images": ["6", 0]}}
}
```

## Execution

```bash
python3 ~/.hermes/skills/creative/comfyui/scripts/run_workflow.py \
  --workflow /home/alca/comfy/ComfyUI/workflows/<topic>-infographic-sdxl.json \
  --args '{"seed": 42, "steps": 30}' \
  --output-dir /home/alca/comfy/ComfyUI/output/<topic>
```

## Setup Notes from Session (June 13, 2026)

1. **ComfyUI wasn't running** — started manually:
   ```bash
   cd /home/alca/comfy/ComfyUI && .venv/bin/python main.py --listen 127.0.0.1 --port 8188
   ```

2. **No checkpoint models installed** — `comfy model list` showed only placeholder files and VAEs. Downloaded SDXL via direct curl:
   ```bash
   curl -L -o /home/alca/comfy/ComfyUI/models/checkpoints/sd_xl_base_1.0.safetensors \
     https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
   ```
   Result: 6.46GB downloaded in ~68 seconds.

3. **`comfy model download` failed** with:
   - "Unauthorized access to Hugging Face model" (HF token auth issue)
   - "No module named pip" (Python 3.14 in comfy-cli venv)
   - Direct curl worked for public models.

4. **Output**: `mazemaker-infographic_00001_.png` (1024×576, 729KB) generated successfully in 24.83 seconds.

## Quality Control

After generation, inspect the output visually. If the user says it's "trash" or "pathetic":
- **Do not** keep tweaking the same approach
- Switch to ComfyUI if you used HTML/CSS, or vice versa
- Ask for a specific reference image if the style is unclear
