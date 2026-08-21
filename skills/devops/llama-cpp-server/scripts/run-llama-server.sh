#!/bin/bash
# LLM Model Server Starter Template
# Usage: ./run-llama-server.sh <model-repo> <quantization> <port>

MODEL_REPO="${1:-unsloth/gemma-4-12B-it-qat-GGUF}"
QUANT="${2:-UD-Q4_K_XL}"
PORT="${3:-18080}"

cd ~/models/llama-cpp-turboquant
LD_LIBRARY_PATH=~/models/llama-cpp-turboquant/build/bin \
./build/bin/llama-server \
  -hf "${MODEL_REPO}:${QUANT}" \
  --spec-type draft-mtp --spec-draft-n-max 4 \
  -ngl 999 -fa on \
  --host 0.0.0.0 --port "$PORT" \
  --alias "$(basename "$MODEL_REPO")" \
  --ctx-size 52000 \
  --reasoning off