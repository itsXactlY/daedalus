---
name: local-image-generation
description: Local image gen on consumer GPUs with VRAM management.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Local Image Generation

Class-level umbrella for local image generation on consumer GPUs.

## Backends

| Backend | Speed | Quality | VRAM | Use case |
|---------|-------|---------|------|----------|
| Bonsai Image 4B (gemlite/HQQ) | ~5s | Good | ~7 GB | Fast iteration |
| Krea-R-Turbo Q6_K (sd-cpp) | ~90s | Photorealistic | ~14 GB | Portraits, realism |
| Kreamagine Q6_K (sd-cpp) | ~55s | Excellent | ~14 GB | Artistic, atmospheric |
| ComfyUI | Varies | Varies | Varies | Custom workflows |

**Krea-R-Turbo vs Kreamagine**: Same krea2 architecture, same GGUF format.
R-Turbo is a LoRA merge of Krea-2-Turbo with photorealism style LoRAs baked in.
Kreamagine is a Grok Imagine style finetune. R-Turbo wins for portraits/realism;
Kreamagine wins for fantasy/conceptual. Same sampler settings (CFG=1.0, 8 steps).

## Bonsai Image 4B

**Repo:** `PrismML-Eng/Bonsai-Image-Demo` — NOT `Bonsai-demo` (that's the 27B LLM).
User WILL get frustrated if you download the wrong one.

Setup at `/home/alca/comfy/Bonsai-Image-Demo/`. Run `./scripts/serve.sh` for backend :8000.
4-step FlowMatch-Euler, guidance 1.0, no CFG. ~5s/512px, ~10s/1024px, ~7GB VRAM.

```bash
curl -o out.png -H 'Content-Type: application/json' \
  -d '{"prompt":"...","backend":"bonsai-ternary-gemlite","steps":4,"width":512,"height":512}' \
  http://127.0.0.1:8000/generate
```

## Kreamagine Q6_K

Uses stable-diffusion.cpp (sd-cpp) — ComfyUI-GGUF does NOT support krea2 architecture.
See `references/kreamagine-sdcpp.md` for build, model layout, and VRAM notes.

**Quick:** `python3 /home/alca/comfy/kreamagine.py -p "prompt"`
**1920x1080:** `python3 /home/alca/comfy/kreamagine.py -p "prompt" -W 1920 -H 1080 --full-vram`

Settings from model card (CRITICAL — these are not defaults):
- CFG=1.0 (turbo distilled, NO guidance — raising CFG wrecks output)
- 8 steps, euler sampler, simple scheduler
- Negative prompts ignored at CFG 1.0

## ComfyUI

Custom workflows, video (Wan/Hunyuan), upscaling, ControlNet.
Start: `cd /home/alca/comfy/ComfyUI && .venv/bin/python main.py --listen 127.0.0.1 --port 8188`

## VRAM Management (16GB RTX 4060 Ti)

- Bonsai alone: ~7 GB, safe
- Kreamagine 512x512: ~14 GB with offload-to-cpu, mazemaker can stay
- Kreamagine 1024x1024+: must stop mazemaker first (`systemctl --user stop mazemaker.target`)
- ComfyUI + Bonsai: won't fit simultaneously at high res

**Model warm daemon** (keep model loaded between generations, 15-min keepalive):
```bash
/home/alca/comfy/kreamagine_daemon.sh 15
```

## Model Files

```
/home/alca/comfy/ComfyUI/models/
├── diffusion_models/Kreamagine-Q6_K.gguf         (10.9 GB)
├── unet/Krea-R-Turbo-Q6_K.gguf                   (10.9 GB)
├── vae/qwen_image_vae.safetensors                 (243 MB)
├── text_encoders_gguf/Qwen3-VL-4B-Instruct-Q6_K.gguf  (3.1 GB)
├── text_encoders_gguf/mmproj-BF16.gguf            (801 MB)
├── text_encoders/qwen3vl_4b_fp8_scaled.safetensors   (4.9 GB)
└── loras/krea2_identity_edit_v1_1.safetensors     (230 MB)
```

## ComfyUI Krea2 GGUF Node

`RealRebelAI/ComfyUI-GGUF_KREA-2` — custom node that adds krea2 architecture
support to ComfyUI-GGUF. Install: `git clone` into `custom_nodes/`, then
`pip install -r requirements.txt`. Node types: `UnetLoaderGGUF` (krea2-aware).

**However**: even with this node, ComfyUI core may still fail on some krea2
variants. sd-cpp is more reliable for krea2 GGUF loading.

## Pitfalls

1. **Wrong Bonsai repo** — `PrismML-Eng/Bonsai-demo` = 27B LLM. `PrismML-Eng/Bonsai-Image-Demo` = image generation. User WILL get frustrated if you download the wrong one.
2. **ComfyUI-GGUF doesn't support krea2** — use stable-diffusion.cpp instead. Patching the GGUF whitelist isn't enough — ComfyUI core can't instantiate the model class.
3. **Kreamagine CFG=1.0** — turbo distilled. Raising CFG wrecks output. Negative prompts ignored.
4. **Don't download entire repos** — user wants ONE file, not all variants.
5. **Prompt style** — no LLM garbage, no "ultra detailed 8k", no "volumetric lighting", no color scheme specs. Concrete, specific, natural language describing the SCENE. Render concepts in the model's BEST style — don't force a specific art style (e.g. don't force manga). The user showed the Mazemaker Inception OS trailer as reference — cyberpunk, CRT-grit, violet phosphor, dark void.
6. **Model warm daemon** — always keep models warm between generations (15-min keepalive). Cold-start is 30+ seconds of loading. The daemon script generates a tiny warmup image then pings every 60s.
7. **VRAM kills mazemaker** — for high-res (1024+), stop mazemaker first. For 512x512, mazemaker can coexist with offload-to-cpu.
8. **Bonsai-Image-Demo needs serve.sh** — `generate.sh` on GPU requires `--force-gpu-run` flag or use the daemon (serve.sh) + curl API instead.
9. **Don't force art styles** — user rejected manga/comic panel prompts for Kreamagine. Use the model's BEST output style (photorealism, atmospheric, cinematic). Don't impose styles the model isn't designed for. The user wants Mazemaker concepts rendered in Kreamagine's natural strength, not as comic panels.
10. **Download ONE file, not all** — when user asks for Q6_K, download Q6_K only. Don't grab the full repo. User said "do NOT download ALL models! only the 2qb".
11. **Act, don't ask** — when user says "kill boinsai", kill it immediately. Don't ask "which do you prefer?". Don't present options when the action is obvious.
12. **Resolution: ask first** — don't default to512. User wanted 2KQHD. Always confirm resolution before generating.
