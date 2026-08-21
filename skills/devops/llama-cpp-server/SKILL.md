---
name: llama-cpp-server
description: Use when running GGUF models with llama.cpp server - local LLM serving, MTP speculative decoding, model caching, and inference acceleration.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, llama-cpp, gguf, inference, gpu, mtp]
    related_skills: []
---

# Running LLM Models with llama.cpp Server

## Overview

llama.cpp server provides an OpenAI-compatible API for GGUF-quantized models with GPU acceleration. Key features include MTP (Multi-Token Prediction) speculative decoding, flash attention, and automatic HuggingFace model downloading.

## When to Use

- Starting a local LLM server for chat/completions API
- Running GGUF models with CUDA acceleration
- Enabling speculative decoding (MTP, draft models)
- Serving multimodal models (vision, audio)
- Gemma, Llama, Qwen, or other supported architectures

## Quick Reference Table

| Flag | Purpose | Example |
|------|---------|---------|
| `-hf` | HuggingFace model with quantization | `-hf unsloth/gemma-4-12B-it-qat-GGUF:UD-Q4_K_XL` |
| `-ngl` | GPU layers | `-ngl 999` (all layers) |
| `-fa` | Flash attention | `-fa on` |
| `--spec-type` | Speculative decoding | `--spec-type draft-mtp` |
| `--reasoning` | Thinking mode toggle | `--reasoning off` |

## One-Shot Startup Recipes

### Basic model serving (cached model)
```bash
cd ~/models/llama-cpp-turboquant
LD_LIBRARY_PATH=~/models/llama-cpp-turboquant/build/bin \
./build/bin/llama-server \
  --model /path/to/model.gguf \
  -ngl 999 -fa on \
  --host 0.0.0.0 --port 18080
```

### HuggingFace model with MTP
```bash
cd ~/models/llama-cpp-turboquant
LD_LIBRARY_PATH=~/models/llama-cpp-turboquant/build/bin \
./build/bin/llama-server \
  -hf unsloth/gemma-4-12B-it-qat-GGUF:UD-Q4_K_XL \
  --spec-type draft-mtp --spec-draft-n-max 4 \
  -ngl 999 -fa on \
  --host 0.0.0.0 --port 18080 \
  --alias "gemma4-qat" \
  --ctx-size 52000 \
  --reasoning off
```

## Common Pitfalls

1. **CUDA build required for GPU**: Default cmake config may not include CUDA. Use `-D GGML_CUDA=on` when configuring.

2. **Build directory path mismatch**: If build exists at different path, remove and rebuild:
   ```bash
   rm -rf build && cmake -B build -D GGML_CUDA=on
   ```

3. **Multimodal projector fails**: Gemma 4 mmproj requires gemma4uv support. Pull latest and rebuild if you see `unknown projector type: gemma4uv`.

4. **Background process exits gracefully but server remains running**: The parent bash wrapper process may exit with code 0 while llama-server continues. Check with `ps aux | grep llama-server` and verify `curl localhost:PORT/health`. Never trust background process output alone; always probe the actual endpoint.

4. **MTP draft model fails**: Same - requires gemma4-assistant architecture support. Pull latest and rebuild.

5. **Deprecated thinking config**: `--chat-template-kwargs '{"enable_thinking":false}'` is deprecated. Use `--reasoning off` instead.

6. **Model cache location**: HuggingFace models cache to `~/.cache/huggingface/hub/`. Use `ls ~/.cache/huggingface/hub/models--*/snapshots/*/ | grep gguf` to find cached files.

7. **VRAM requirements**: QAT models are ~6GB. Verify free VRAM with `nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits`.

## Verification Checklist
- [ ] Server responds to `curl http://localhost:PORT/health`
- [ ] Model shows in `curl http://localhost:PORT/v1/models`
- [ ] Chat completions work with non-empty `content` field
- [ ] MTP active when `timings.draft_n > 0` in response
- [ ] All layers on GPU when `n_gpu_layers = 999` in model meta

## Ollama Context Limits

For Ollama-specific context length behavior (native limits, `ollama_num_ctx` config, model recommendations), see `references/ollama-context-limits.md`.