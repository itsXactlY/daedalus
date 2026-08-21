# Wan 2.1 Local Setup (16 GB VRAM)

Run Wan 2.1 text-to-video or image-to-video locally on a 16 GB NVIDIA GPU.
This uses LOCAL ComfyUI nodes (UNETLoader, CLIPLoader type=wan), NOT the
cloud API nodes (Wan2TextToVideoApi etc.) which have a code-level bug in
the current ComfyUI build.

## Model Layout

Download from `Comfy-Org/Wan_2.1_ComfyUI_repackaged` on HuggingFace.
Use the HF token from the environment to access gated repos.

| File | Destination | Size | Notes |
|------|------------|------|-------|
| `split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors` | `models/diffusion_models/` | ~1.7 GB | bf16 variant also available (~3.1 GB) |
| `split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `models/text_encoders/` | ~2.3 GB | fp8 saves ~2.3 GB vs fp16 |
| `split_files/vae/wan_2.1_vae.safetensors` | `models/vae/` | ~350 MB | |

**VRAM budget:** Model (~1.7 GB) + Text encoder (~2.3 GB) + VAE (~0.3 GB) =
~4.3 GB loaded, leaving ~11 GB for inference on a 16 GB card.

## Workflow (API format)

Use `workflows/wan_video_t2v.json` as a starting point. Key nodes:

```json
{
  "37": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.1_t2v_1.3B_fp16.safetensors", "weight_dtype": "default"}},
  "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
  "39": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
  "3":  {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 30, "cfg": 6.0, "sampler_name": "uni_pc", "scheduler": "simple", ...}},
  "40": {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": 832, "height": 480, "length": 33, "batch_size": 1}},
  "9":  {"class_type": "VHS_VideoCombine", "inputs": {"frame_rate": 16, "format": "video/h264-mp4", ...}}
}
```

## Important Caveats

- **The cloud API nodes (Wan2TextToVideoApi, WanTextToVideoApi) are BROKEN**
  on this ComfyUI build: `execute() missing 1 required positional argument: 'model'`.
  Do NOT attempt to use them. Always use the local node chain instead.
- **`EmptyHunyuanLatentVideo`** is used for Wan's latent space in this build,
  despite the name. Do not change to `EmptyARVideoLatent` unless you verify
  the node interfaces against the server's `/object_info`.
- **33 frames at 16 fps** = ~2 seconds of video. For longer output, increase
  `length` (up to 81 frames = ~5s at 16 fps) or use `WanFirstLastFrameToVideo`
  for interpolation between start/end frames.
