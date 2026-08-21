# WAN 2.2 GGUF Quantization Notes

## Q8_0 vs Q4_K_M Comparison (download 2026-06-15)

| Variant | Size | VRAM | Quality | Speed |
|---------|------|------|---------|-------|
| Q4_K_M | ~12GB | 12-16GB | Good | Fast |
| Q8_0 | ~15GB | 14-18GB | Better | Moderate |

### Recommendation
Stick with **Q4_K_M** for 16GB VRAM setups. Q8_0 offers 10-15% quality improvement but requires 2-3GB more VRAM.

## Download Paths
```
QuantStack/Wan2.2-T2V-A14B-GGUF/HighNoise/Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf
QuantStack/Wan2.2-T2V-A14B-GGUF/HighNoise/Wan2.2-T2V-A14B-HighNoise-Q8_0.gguf
QuantStack/Wan2.2-T2V-A14B-GGUF/LowNoise/Wan2.2-T2V-A14B-LowNoise-Q*.gguf
```

## PRXPixel FP8 Path Notes

The FP8 transformer from `Lumatrix/prx-pixel-fp8` is 9.2GB but:
- Requires custom ComfyUI nodes that are not publicly released
- Must be combined with original text_encoder (3.4GB)
- Total ~12.5GB, still larger than WAN Q4

## Disk Cleanup
After downloads, remove:
```bash
rm -rf ~/.cache/huggingface/hub/models--.../snapshots/*/download_cache/
rm -rf /path/to/models/.cache/  # Created during download
```