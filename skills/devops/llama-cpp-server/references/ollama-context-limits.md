# Ollama Context Length Limits

## Key Facts

- **Native context is per-model**: Each model has a baked-in maximum context size in its GGUF weights. `qwen2.5:3b` = 32,768; `openbmb/minicpm5:q8_0` = 131,072.
- **OPTIONS.num_ctx can only REDUCE**: The `options: {num_ctx: X}` parameter in API calls cannot extend beyond native limits, only shrink them.
- **Hermes minimum**: 64,000 tokens required for reliable tool use (tool schemas + system prompt are large).

## Configuration

Set in `~/.hermes/config.yaml`:
```yaml
model:
  ollama_num_ctx: 131072  # Injects options.num_ctx into Ollama API calls
  context_length: 131072  # For compression calculations (should match)
```

## Verifying Native Context

```bash
# List models and check their native context
curl -s http://localhost:11434/api/tags | jq '.models[].name'
for m in $(curl -s http://localhost:11434/api/tags | jq -r '.models[].name'); do
  curl -s http://localhost:11434/api/show -d "{\"model\": \"$m\"}" | \
  jq -r '.model_info // .details | "context_length // empty"'
done
```

## Model Recommendations (128k+ native)

- `openbmb/minicpm5:q8_0` - 131,072 tokens (already available)
- `qwen2.5-coder:3b` - Larger context variants exist
- `gemma3:27b` - 131,072 tokens (if VRAM available)

## Debugging Context Issues

Check running server flags:
```bash
ps aux | grep llama-server | grep -v grep | grep -o '\-c [0-9]*'
```

If `-c 32768` appears but you requested 128k, the model's native limit is the bottleneck.