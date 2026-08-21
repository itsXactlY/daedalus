# Gemma 4 QAT Configuration Details

## Model Information
- Repo: unsloth/gemma-4-12B-it-qat-GGUF
- Quantization: UD-Q4_K_XL
- Size: ~6.2GB (6700531904 bytes)

## Cache Paths
```
~/.cache/huggingface/hub/models--unsloth--gemma-4-12B-it-qat-GGUF/snapshots/7102bdea62863acff919c945405ef29973113d66/
├── gemma-4-12B-it-qat-UD-Q4_K_XL.gguf  (main model)
├── mtp-gemma-4-12B-it.gguf               (MTP draft model)
└── mmproj-BF16.gguf                        (multimodal projector)
```

## Architecture Requirements

The following architecture files are required in llama.cpp for Gemma 4:
- `src/models/gemma4.cpp` - main Gemma 4 support
- `src/models/gemma4-assistant.cpp` - for MTP draft model
- `tools/mtmd/models/gemma4uv.cpp` - for multimodal projector (mmproj)

These were merged in `llama-cpp-turboquant` feature/turboquant branch.

## Error Messages Seen During Setup

### Before rebuild (architecture not found):
```
E llama_model_load: error loading model: unknown model architecture: 'gemma4-assistant'
E mtmd_init_from_file: error: Failed to load CLIP model ... unknown projector type: gemma4uv
```

### Deprecated flag warning:
```
W Setting 'enable_thinking' via --chat-template-kwargs is deprecated. Use --reasoning on / --reasoning off instead.
```

## Working Configuration Flags

```bash
-hf unsloth/gemma-4-12B-it-qat-GGUF:UD-Q4_K_XL \
  --spec-type draft-mtp --spec-draft-n-max 4 \
  -ngl 999 -fa on \
  --host 0.0.0.0 --port 18080 \
  --alias "gemma4-qat" \
  --ctx-size 52000 \
  --reasoning off
```

## Timing Metrics (Success)

```json
{
  "predicted_per_second": 41.10,
  "draft_n": 36,
  "draft_n_accepted": 11,
  "draft acceptance rate": 0.30556
}
```

MTP acceptance ~30% indicates speculative decoding is working.