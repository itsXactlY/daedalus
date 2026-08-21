---
name: daedalus-model-output-budget
description: "Avoid output token exhaustion AND context destruction from wrong model selection."
category: software-development
---


> Ported from `hermes-model-output-budget` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Model Output Budget

Avoid output token exhaustion on free-tier models AND context destruction from wrong model selection.

## Trigger conditions

- Using a free-tier model (e.g. `ling-3.0-flash:free`) with `reasoning_effort: xhigh`
- Large mazemaker-recall responses (10+ entries) that need synthesis into a response with tool calls
- Observed cascade: truncated tool call → 4 retries → "refusing to execute incomplete tool arguments"
- Agent "turns in circles", loses context, repeats itself, forgets earlier work
- `BadRequestError: reasoning_effort: Invalid option` (using `ultra` which is invalid)

## Root cause

`reasoning_effort: xhigh` allocates maximum tokens to chain-of-thought reasoning *before* any response content. Free-tier models have very low max output tokens, so the reasoning phase alone can exhaust the budget, truncating the tool call formatting mid-stream.

## Recommended configuration

In `~/.daedalus/config.yaml`:

```yaml
model:
  default_model: <your-model>
  provider: <your-provider>
  reasoning_effort: low   # or medium; NOT xhigh on free-tier models
```

## Workarounds

- **Targeted mazemaker queries**: Instead of broad "show me everything" searches, ask specific questions to limit result size.
- **Batch recall**: Break large recall into multiple small queries rather than one massive one.
- **Switch models for heavy recall work**: Use a model with higher output limits when doing mazemaker-intensive tasks.

## Tool-call truncation failure cascade

When mazemaker-recall returns many results and the model runs out of output tokens:
1. Model truncates mid-response inside tool call formatting
2. Daedalus detects malformed `arguments` JSON → flags "Truncated tool call detected"
3. Daedalus retries up to 4 times with same broken arguments
4. Final refusal: "refusing to execute incomplete tool arguments"

The cascade is correct behavior but frustrating when it's a model-budget issue rather than a genuinely ambiguous query.

## Wrong model for the job (context destruction)

The INVERSE problem: using a trash-tier free model when you NEED large context.

**Symptoms**: Agent "turns in circles", loses context mid-conversation, repeats itself, forgets earlier work. User frustration: "NO WONDER ALL U FUCKS TURN IN CIRCLES".

**Root cause**: Default `openrouter_free` provider uses `inclusionai/ling-3.0-flash:free` with small context. Compression kicks in at 55% using the same trash model as summarizer, nuking large context down to ~128K.

**Fix sequence** (run BEFORE starting work on large tasks):
```bash
# 1. Switch to large-context model
daedalus config set model.provider <provider-with-1m-model>
daedalus config set model.default <model-with-1m-context>

# 2. DISABLE compression (it uses trash models)
daedalus config set compression.enabled false

# 3. Set valid reasoning_effort (ultra is INVALID — causes 400)
daedalus config set agent.reasoning_effort max
```

**Valid reasoning_effort values**: `max`, `xhigh`, `high`, `medium`, `low`, `minimal`, `none`. NEVER use `ultra` — it crashes with `BadRequestError`.

**Gotcha**: Some config keys need `--force` flag:
```bash
daedalus config set agent.reasoning_effort max --force  # may warn "not a recognized config key"
```

**Verification**:
```bash
daedalus config get model           # should show large-context model
daedalus config get compression     # should show enabled: false
```

## Related

- `daedalus-core-capabilities`: umbrella that covers model configuration; this reference supplements it.
- `references/free-tier-truncation-cascade.md`: detailed reproduction of the truncation cascade.