# Kreamagine via stable-diffusion.cpp

## When ComfyUI can't load a GGUF model

Some GGUF models use architectures not supported by ComfyUI-GGUF or ComfyUI core.
Kreamagine uses `krea2` architecture (Krea-2-Turbo finetune, 28 blocks + txtfusion)
which is NOT in ComfyUI-GGUF's `IMG_ARCH_LIST`. Patching the list lets the GGUF
loader accept the file, but ComfyUI core's `load_diffusion_model_state_dict` still
can't instantiate the model class.

**Working alternative**: `stable-diffusion.cpp` (`sd-cpp`) — C++ inference engine
with native `krea2` support since 2026-06-25.

## Build sd-cpp

```bash
cd /home/alca/comfy
git clone --depth 1 https://github.com/leejet/stable-diffusion.cpp.git sd-cpp
cd sd-cpp && git submodule update --init --recursive
mkdir build && cd build
cmake .. -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release -j$(nproc)
# Binary: sd-cpp/build/bin/sd-cli
```

## Supported krea2 GGUF models

| Model | Source | Size | Focus |
|-------|--------|------|-------|
| Kreamagine-Q6_K | `realrebelai/Kreamagine_v1.0` | 10.9 GB | Grok Imagine style, artistic |
| Krea-R-Turbo-Q6_K | `realrebelai/Krea-R-Turbo` | 10.9 GB | LoRA merge, photorealism/portraits |
| Kreamagine-Q5_K_M | `realrebelai/Kreamagine_v1.0` | 9.27 GB | Smaller, same arch |
| Krea-R-Turbo-Q4_K_M | `realrebelai/Krea-R-Turbo` | 7.71 GB | Fits with mazemaker running |

Both use krea2 architecture (28 blocks + txtfusion). Same VAE, same text encoder.
R-Turbo = Krea-2-Turbo + 2 style LoRAs baked in. Kreamagine = Grok Imagine finetune.

**LoRA**: Krea-R-Turbo workflow uses `krea2_identity_edit_v1_1.safetensors` (230 MB)
from `conradlocke/krea2-identity-edit`. Optional — improves face consistency.
Installed at `models/loras/krea2_identity_edit_v1_1.safetensors`. Also available
from `cocktailpeanut/krea2-identity-edit` and `neuralnetworker/krea2-identity-edit`.

## Component files needed

| Component | Source | Path |
|-----------|--------|------|
| Diffusion model | `realrebelai/Kreamagine_v1.0` | `models/diffusion_models/Kreamagine-Q6_K.gguf` (10.9 GB) |
| Text encoder | `unsloth/Qwen3-VL-4B-Instruct-GGUF` | `models/text_encoders_gguf/Qwen3-VL-4B-Instruct-Q6_K.gguf` (3.1 GB) |
| VAE | `Comfy-Org/Qwen-Image_ComfyUI` | `models/vae/qwen_image_vae.safetensors` (243 MB) |

**Pitfall**: The text encoder MUST be GGUF format for sd-cpp. The safetensors
version (`qwen3vl_4b_fp8_scaled.safetensors`) causes tensor shape mismatch errors.

## VRAM budget on 16GB (RTX 4060 Ti)

| Component | VRAM |
|-----------|------|
| Diffusion model (Q6_K) | ~10.4 GB |
| Text encoder (Q6_K) | ~3.1 GB |
| VAE | ~0.2 GB |
| Compute buffers | ~0.2 GB |
| **Total** | **~14 GB** |

With `--offload-to-cpu`, text encoder loads into VRAM for encoding then offloads.
This fits at **512x512**. At **1024x1024**, compute buffers grow and total exceeds 16GB.

**VRAM management pattern**: For 1024x1024, must stop mazemaker first:
```bash
systemctl --user stop mazemaker.target  # free ~2.5 GB
# ... generate ...
systemctl --user start mazemaker.target
```

## Kreamagine sampler settings

From model card (Krea-2-Turbo finetune, 8-step distilled):

| Setting | Value | Notes |
|---------|-------|-------|
| Steps | 8 | More steps does NOT improve quality |
| CFG | 1.0 | Turbo has NO classifier-free guidance. Raising CFG wrecks output |
| Sampler | euler | |
| Scheduler | simple | |
| Negative prompts | ignored at CFG 1.0 | |
| Resolution | 512-1536 | 1024 native |

**Key**: Lighting and camera terms carry more weight than on base Turbo.
This is the main lever for prompt engineering.

## Command

```bash
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
sd-cpp/build/bin/sd-cli \
  --diffusion-model models/diffusion_models/Kreamagine-Q6_K.gguf \
  --vae models/vae/qwen_image_vae.safetensors \
  --llm models/text_encoders_gguf/Qwen3-VL-4B-Instruct-Q6_K.gguf \
  -p "prompt" -W 512 -H 512 --steps 8 --cfg-scale 1.0 \
  --offload-to-cpu --diffusion-fa --vae-tiling \
  -o output.png
```

## Wrapper script

`/home/alca/comfy/kreamagine.py` handles VRAM management, auto-kill/restart
mazemaker with `--full-vram` flag, sane defaults (512x512, 8 steps, CFG 1.0).
