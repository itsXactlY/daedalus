---
name: comfyui-video-gen-masterpiece
version: "1.0"
description: "ComfyUI video generation workflow for >16GB VRAM — generate cinematic trailer masterpieces using HunyuanVideo, WAN 2.2, and LTX-2 with GGUF quantization, Kijai nodes, and multi-step optimization."
author: Hermes
trigger: "user asks about ComfyUI video generation, video model setup, cinematic trailer generation, or HunyuanVideo/WAN/LTX workflow"
user-invocable: true
metadata:
  tags: [comfyui, video-generation, hunyuanvideo, wan2.2, ltx-video, gguf, kijai, cinematic, trailer, workflow]
---

# ComfyUI Video Generation — Masterpiece Workflow (>16GB VRAM)

Build cinematic-grade video in ComfyUI using open-source models. This skill covers model selection, installation, VRAM optimization, workflow patterns, and trailer-specific techniques.

---

## 1. HARDWARE TIERS

| Tier | VRAM | What you can run | Quality |
|------|------|-----------------|---------|
| Entry | 12-16GB | WAN 2.2 14B GGUF Q4, HunyuanVideo GGUF Q4, LTX-2 | Good, 480p-720p |
| **Sweet spot** | **16-24GB** | **WAN 2.2 14B full, HunyuanVideo 1.5 GGUF, LTX-2 full** | **Great, 720p-1080p** |
| High-end | 24-48GB | HunyuanVideo 1.5 full, WAN 2.2 14B full + high-res | Excellent, 1080p+ |
| Pro | 48-80GB | Multiple models, ensemble, 4K upscaling | Masterpiece |

## 2. MODEL SELECTION GUIDE

### For Cinematic Trailers (your use case)

| Model | VRAM | Quality | Speed | Trailer Fit |
|-------|------|---------|-------|-------------|
| **WAN 2.2 14B** | 12-20GB | ★★★★☆ | ★★★★☆ | Best all-rounder. Cinematic motion, good consistency |
| **HunyuanVideo 1.5** | 20-48GB | ★★★★★ | ★★★☆☆ | Highest quality. Best for establishing shots, slow pans |
| **LTX-2** | 12-20GB | ★★★☆☆ | ★★★★★ | Audio-sync capable. Best for dialogue/talking head scenes |
| **LTX-2 I2V** | 16-24GB | ★★★★☆ | ★★★★☆ | Image-to-video. Perfect for consistent character shots |
| **CogVideoX-5B** | 18-24GB | ★★★☆☆ | ★★★☆☆ | Good for abstract/surreal sequences |

### VRAM-Aware Selection Matrix

```
                    VRAM
            12GB  16GB  24GB  48GB
WAN 2.2      GGUF  GGUF  Full  Full
Hunyuan 1.5  -     GGUF  Full  Full
LTX-2        Full  Full  Full  Full
CogVideoX-5B -     Full  Full  Full
```

## 3. INSTALLATION

### Required ComfyUI Custom Nodes

```bash
# Kijai's wrappers (the backbone — everything connects through these)
cd ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-KJNodes
git clone https://github.com/kijai/ComfyUI-HunyuanVideoWrapper
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper

# GGUF support (for quantized models on lower VRAM)
git clone https://github.com/city96/ComfyUI-GGUF

# LTX-Video
git clone https://github.com/Lightricks/ComfyUI-LTXVideo

# Optional: upscaling for cinematic quality
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
```

### Model Downloads

```bash
# --- WAN 2.2 14B ---
# Full model (~30GB)
cd ComfyUI/models/checkpoints
wget https://huggingface.co/Wan-AI/Wan2.2-T2V-14B/resolve/main/Wan2.2-T2V-14B-fp16.safetensors

# GGUF Q4 quant (~12GB, fits 16GB VRAM)
cd ComfyUI/models/checkpoints
wget https://huggingface.co/city96/Wan2.2-T2V-14B-gguf/resolve/main/Wan2.2-T2V-14B-Q4_K_M.gguf

# --- HUNYUAN VIDEO 1.5 ---
# Full model (~35GB)
cd ComfyUI/models/checkpoints
wget https://huggingface.co/tencent/HunyuanVideo-1.5/resolve/main/hunyuan_video_1.5_fp16.safetensors

# From Comfy-Org (repackaged, easier to use)
wget https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/hunyuan_video_1.5_repackaged.safetensors

# --- LTX-2 ---
cd ComfyUI/models/checkpoints
wget https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2-0.safetensors
```

## 4. WORKFLOW PATTERNS

### Pattern A: WAN 2.2 Cinematic (Sweet Spot — 16-24GB VRAM)

This is the pattern from the Reddit post (r/comfyui, 725 pts):

```
1. Load Checkpoint: WAN 2.2 14B (full or GGUF Q4)
2. CLIP Text Encode (positive): cinematic trailer prompt
3. CLIP Text Encode (negative): low quality, artifacts
4. Kijai WAN Sampler:
   - Steps: 30-50 (higher = better quality, slower)
   - CFG: 6-8
   - Resolution: 480p-720p for fast iteration
   - Frames: 81 (≈5 sec at 16fps) or 161 (≈10 sec)
5. VAE Decode
6. Optional: Upscale to 1080p with Video Upscaler
```

**Key optimization for 16GB VRAM:**
- Use WAN 2.2 GGUF Q4_K_M → fits in 12GB, leaving 4GB for VAE/upscaling
- Use Kijai's Lightning LoRA (2-step high + 3-step low schedule)
- Resolution: 480p then upscale (don't render at 1080p directly)

### Pattern B: HunyuanVideo 1.5 Premium (24-48GB VRAM)

For your best trailer shots:

```
1. Load Checkpoint: HunyuanVideo 1.5 (full)
2. CLIP Text Encode: detailed cinematic prompt
3. Kijai HunyuanVideo Sampler:
   - Steps: 50-100 (Hunyuan needs more steps)
   - CFG: 7.0
   - Resolution: Up to 720p native (higher with tiling)
   - Frames: 93 (≈6 sec at 16fps)
4. VAE Decode
5. Optional: Frame interpolation (RIFE) to 30fps
```

**VRAM optimization:**
- Use city96/HunyuanVideo-gguf for Q4 quantization → 20-24GB
- Enable CPU offloading for text encoder (saves 4-6GB)
- Use teacache for 2x speedup (Kijai node includes this)

### Pattern C: LTX-2 Audio-Sync (for dialogue/trailer narration)

From the LTX-2 audio workflow (r/StableDiffusion, 985 pts):

```
1. Load Checkpoint: LTX-2
2. Load Audio: trailer narration / music track
3. CLIP Text Encode + Audio Conditioning
4. LTX Sampler:
   - Steps: 20-30 (LTX is fast)
   - CFG: 4-5
   - Resolution: 512x512 or 768x768
   - Frames: Up to 257 (≈16 sec)
5. VAE Decode
6. Optional: Audio-sync refinement with Distill LoRA
```

## 5. PROMPT ENGINEERING FOR CINEMATIC TRAILERS

### Structure

```
[Cinematic style], [shot type], [subject], [action], [environment],
[lighting], [color grade], [mood], [camera movement], [era/period]
```

### Example Trailer Prompts

```
Cinematic trailer shot, epic wide angle, ancient warrior standing on a cliff edge
overlooking a stormy sea at sunset, golden hour lighting, volumetric god rays
piercing through dark clouds, slow camera pan right, dramatic orchestral mood,
8k resolution, film grain, anamorphic lens flare, rich teal and amber color grade

Close-up portrait of a cyberpunk detective in the rain, neon city reflections
on wet pavement, blue and magenta lighting, cinematic bokeh, shallow depth of field,
slow motion, noir atmosphere, cinematic film look, hyperrealistic textures,
subtle particles floating in the air
```

### Negative Prompt

```
blurry, low quality, distorted faces, bad anatomy, extra limbs, ugly, 
oversaturated, cartoon, 3d render, ai artifacts, flickering, inconsistent
motion, morphing, static, watermark, text, logo, copyright
```

## 6. VRAM OPTIMIZATION TECHNIQUES

### Technique 1: GGUF Quantization
```yaml
Q4_K_M:  (12GB)  Good quality, 40% VRAM savings — RECOMMENDED for 16GB
Q5_K_M:  (15GB)  Better quality, 30% VRAM savings
Q6_K:    (18GB)  Near-lossless, 20% VRAM savings
Q8_0:    (22GB)  Virtually lossless, 10% VRAM savings
```

### Technique 2: Wan2GP / HunyuanVideoGP
From the Reddit post (r/StableDiffusion, 339 pts): deepbeepmeep's optimizations cut VRAM by 50%.
```
GitHub repos:
- https://github.com/deepbeepmeep/Wan2GP
- https://github.com/deepbeepmeep/HunyuanGP
```

### Technique 3: Multi-Step Schedule (Kijai Lightning LoRA)
```
- High steps: 2 (quality pass at high resolution)
- Low steps: 3 (details pass)
- Combined: fast 5-minute generation instead of 15+ minutes
```

### Technique 4: GPU Direct Storage (GDS)
From the r/StableDiffusion post (764 pts): ComfyUI GDS integration offloads to system RAM.
```bash
git clone https://github.com/maifeeulasad/ComfyUI.git
git checkout offloader-maifee
python3 main.py --enable-gds --gds-stats
```

## 7. TRAILER-SPECIFIC WORKFLOW

### Shot-by-shot pipeline:

```
1. Script breakdown → list of shots with description + duration
2. For each shot (in order):
   a. Select model: Establishment → HunyuanVideo | Action → WAN 2.2 | Dialogue → LTX-2
   b. Generate at 480p for iteration (3-5 variations)
   c. Select best, generate at 720p with higher steps
   d. Upscale to 1080p with Video Upscaler
   e. If dialogue: run LTX-2 audio sync pass
3. Post-process: frame interpolation to 24/30fps (RIFE)
4. Compile shots with video editor
```

### Quick iteration tips:
- Start at 480p, 30 frames, 20 steps → 30-60 sec per gen
- Refine prompt → 2-3 more tries
- Final render at 720p, 81+ frames, 50 steps → 5-15 min per gen
- Batch multiple variations in parallel if you have VRAM headroom

## 8. KNOWN ISSUES & FIXES

| Problem | Fix |
|---------|-----|
| OOM (out of memory) | Lower resolution, use GGUF Q4, reduce frames, enable CPU offload |
| Flickering video | Increase CFG (7-8), use more steps, enable FreeLong for consistency |
| Distorted faces | Reduce CFG (5-6), add "detailed face" to prompt, use face fidelity LoRA |
| Slow generation | Use Lightning LoRA + multi-step schedule (2 high + 3 low) |
| WAN/Hunyuan won't load | Check safetensors isn't corrupted, verify Kijai node versions match |
| LTX-2 audio out of sync | Re-run audio sync pass, check audio sample rate (should be 16kHz) |
| Black frames in output | Update ComfyUI, update node versions, check VAE compatibility |

## 9. QUICK START (NEW SETUP)

### Pitfall: HuggingFace Model Download Authentication
- Model files on HuggingFace often need an access token. Set the `HF_TOKEN` environment variable or run `huggingface-cli login` before `wget`. If omitted you’ll receive a `401 Unauthorized` error.
- As a fallback, manually download the model via a browser and place it in `models/checkpoints`.


If starting from scratch on a fresh ComfyUI:

```bash
# 1. Clone ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI

# 2. Install Kijai nodes
cd custom_nodes
git clone https://github.com/kijai/ComfyUI-HunyuanVideoWrapper
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper
pip install -r ComfyUI-HunyuanVideoWrapper/requirements.txt
pip install -r ComfyUI-WanVideoWrapper/requirements.txt

# 3. Download best starter model (WAN 2.2 GGUF — works on 16GB)
cd ../models/checkpoints
wget https://huggingface.co/city96/Wan2.2-T2V-14B-gguf/resolve/main/Wan2.2-T2V-14B-Q4_K_M.gguf

# 4. Launch
cd ../..
python3 main.py
```

## PRXPIXEL T2I — Pixel-Space Diffusion (Qwen3-VL)

**Not GGUF-compatible** — safetensors diffusion transformer, denoises RGB pixels directly (no VAE).

| Model | VRAM | Resolution | Type |
|-------|------|------------|------|
## PRXPIXEL T2I — Pixel-Space Diffusion (Qwen3-VL)

**Not GGUF-compatible** — safetensors diffusion transformer, denoises RGB pixels directly (no VAE).

### Installation

PRXPixelPipeline is **not in released diffusers** — install from PR #13928:

```bash
# Install from PR branch
cd /tmp
git clone --depth 1 --branch main https://github.com/huggingface/diffusers
cd diffusers
git fetch origin pull/13928/head:prx-pixel
git checkout prx-pixel
pip install . --break-system-packages

# Download model (full size)
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Photoroom/prxpixel-t2i',
    local_dir='/path/to/models/pixel_prx'
)
"
```

### FP8 Quantized Alternative

**Lumatrix/prx-pixel-fp8** (9.2GB transformer) uses mixed fp8 storage:
- Requires custom ComfyUI nodes (`Load PRX Pixel model`, `lumina_prx_pixel`)
- Still needs original text_encoder (3.4GB) → total ~12.5GB
- Not compatible with stock diffusers loading

```bash
# FP8 transformer only
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='Lumatrix/prx-pixel-fp8',
    filename='prxpixel_transformer_fp8_mixed.safetensors',
    local_dir='/path/to/models/diffusion_models/unet'
)
```

### Requirements

- `transformers >= 4.57` (for Qwen3VLTextModel)
- `torch` with CUDA
- Full model: ~17.5GB (transformer + text_encoder, no VAE)
- FP8 variant: ~12.5GB (9.2GB transformer + 3.4GB text_encoder)

### Usage

```python
from diffusers import PRXPixelPipeline
import torch

pipe = PRXPixelPipeline.from_pretrained(
    '/path/to/models/pixel_prx',
    torch_dtype=torch.bfloat16
).to('cuda')

image = pipe(
    'cinematic wide shot, epic warrior on cliff overlooking stormy sea',
    num_inference_steps=28,
    guidance_scale=5.0
).images[0]
```

## 10. THE ULTRA GOAT — Bonsai Image 4B Keyframe Pipeline

**The closed-loop media factory** — Bonsai thinks, Bonsai sees, ComfyUI moves it, mazemaker remembers.

```
Bonsai 27B (think)  →  writes the prompt/storyboard
        ↓
Bonsai Image 4B (see)  →  generates keyframe stills (1024², ~4.5s each)
        ↓
ComfyUI (WAN/Hunyuan I2V)  →  animates keyframes into cinematic motion
        ↓
mazemaker  →  remembers every prompt/frame/decision, refines next iteration
```

### Bonsai Image 4B — Model Specs

| Item | Spec |
|------|------|
| Base | FLUX.2 Klein 4B (MMDiT diffusion transformer) |
| Params | ~4.0B (25 MMDiT blocks: 5 double + 20 single stream) |
| Sampler | FlowMatchEuler, **4 steps**, guidance=1.0, shift=3.0 |
| Text encoder | Qwen3-4B at 4-bit HQQ (2.84 GB, offloaded after prompt encode) |
| VAE | Flux2 32-channel latent, tiled decode (128px tiles) |
| Resolution | 1024×1024 native (also 512×512, arbitrary multiples of 32) |
| Transformer | 1.21 GB (ternary {-1,0,+1} + FP16 group-wise scales) |
| Total payload | **4.55 GB** (transformer + text encoder + VAE) |
| Peak HBM | ~6.8 GiB on RTX 3080 |
| Speed | ~4.5s per 1024² image on 3080-class |
| License | Apache 2.0 |

### Installation

```bash
# Clone the demo repo
cd /home/alca/comfy
git clone https://github.com/PrismML-Eng/Bonsai-demo.git
cd Bonsai-demo

# Setup (installs deps + downloads models)
./setup.sh

# Or manual:
uv venv .venv --python 3.12
source .venv/bin/activate
pip install -e .

# Download models (ternary 2bit + GGUF)
./scripts/download_models.sh
```

### GGUF Quantized Diffusion Pipeline

The Bonsai Image 4B diffusion transformer can be served as GGUF for even lower VRAM:

```bash
# Quick generation — GGUF ternary 2-bit
python -m bonsai_image.sd \
  --diffusion-model bonsai-flux2-klein-ternary-q2_k.gguf \
  --vae flux2-vae.safetensors \
  --llm qwen_3_4b.gguf \
  -p "a red fox in snow, detailed, 8k" \
  --cfg-scale 1.0 --steps 4 \
  --offload-to-cpu --diffusion-fa --vae-tiling

# Key flags:
#   --diffusion-model   GGUF quantized transformer (1.21 GB)
#   --vae               Flux2 VAE (0.17 GB)
#   --llm               Qwen3-4B text encoder GGUF (2.84 GB)
#   --cfg-scale 1.0     No CFG needed (model is guidance-distilled)
#   --steps 4           Designed for exactly 4 steps
#   --offload-to-cpu    Offload text encoder after prompt encode
#   --diffusion-fa      Flash attention for diffusion loop
#   --vae-tiling        Tiled VAE decode (saves VRAM on large images)
```

### Integration with ComfyUI (I2V Keyframe → Video)

```
1. Generate keyframe with Bonsai Image 4B (standalone script)
2. Save keyframe to /home/alca/comfy/ComfyUI/input/
3. In ComfyUI: Load Image → WAN 2.2 I2V or HunyuanVideo I2V
4. Animate keyframe into 5-10 sec cinematic motion
5. mazemaker_remember the prompt + settings + output path
```

### VRAM Budget (RTX 4060 Ti 16GB)

| Component | VRAM | Notes |
|-----------|------|-------|
| Bonsai Image 4B (inference) | ~6.8 GiB | Peak at 1024² |
| Text encoder (during encode) | ~2.84 GB | Offloaded after prompt |
| VAE (decode) | ~0.17 GB | Tiled decode |
| **Remaining for ComfyUI** | **~6 GB** | Enough for WAN GGUF Q4 |

**Strategy:** Generate keyframe with Bonsai (uses ~7GB), then switch to ComfyUI for I2V animation (uses ~10GB for WAN GGUF). Don't run both simultaneously on 16GB.

## 11. MODEL LINKS (Quick Reference)

| Model | HuggingFace | Type |
|-------|-------------|------|
| **Bonsai Image 4B Ternary** | **prism-ml/bonsai-image-ternary-4B-gemlite-2bit** | **Keyframe** |
| **Bonsai Demo** | **PrismML-Eng/Bonsai-demo** | **Pipeline** |
| WAN 2.2 T2V 14B | Wan-AI/Wan2.2-T2V-14B | Full |
| WAN 2.2 GGUF Q4 | city96/Wan2.2-T2V-14B-gguf | Quantized |
| WAN 2.2 I2V 14B | Wan-AI/Wan2.2-I2V-14B-720P | Full |
| HunyuanVideo 1.5 | tencent/HunyuanVideo-1.5 | Full |
| HunyuanVideo GGUF | city96/HunyuanVideo-gguf | Quantized |
| HunyuanVideo repack | Comfy-Org/HunyuanVideo_1.5_repackaged | Easy install |
| Kijai ComfyUI node | Kijai/HunyuanVideo_comfy | Custom node |
| LTX-Video 2.0 | Lightricks/LTX-Video | Full |
| CogVideoX-5B | THUDM/CogVideoX-5B | Full |

---

*Built from pulse pod deep research — 85 candidates across 17 sources, 2 directly relevant Reddit workflows (725pts, 985pts), 5 HuggingFace model cards verified. Bonsai Image 4B section added from prism-ml/bonsai-image-ternary-4B-gemlite-2bit verified specs + PrismML-Eng/Bonsai-demo pipeline.*

## PRXPIXEL T2I — Pixel-Space Diffusion (Qwen3-VL)

PRXPixel is a specialized T2I model (not GGUF-compatible) that denoises RGB pixels directly without VAE. Quality: ~7B params, 1024 resolution.

### Installation
PRXPixelPipeline is in PR #13928 (`prx-pixel` branch, NOT `prx-pixel-pipeline` as README states):
```bash
git clone https://github.com/huggingface/diffusers /tmp/diffusers
cd /tmp/diffusers
git fetch origin pull/13928/head:prx-pixel
git checkout prx-pixel
pip install . --break-system-packages
```

### Model Details
- VRAM: 12-16GB
- Resolution: 1024px
- Size: ~17.5GB (3.4GB text_encoder + 13GB transformer)
- Requires: `transformers >= 4.57` for Qwen3VLTextModel
