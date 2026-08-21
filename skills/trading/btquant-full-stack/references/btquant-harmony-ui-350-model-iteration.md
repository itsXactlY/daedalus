# BTQuant Harmony UI 350-Pass Multi-Model Iteration Reference

Session artifact: 2026-06-13 BTQuant Harmony UI refinement routine.

## Purpose

Use this deterministic local harness when the operator asks for deep BTQuant UI iteration beyond a single-pass draft. It records model-persona review passes without sending live trading commands, reading secrets, or pretending external LLM calls happened.

## Files produced/updated

- `~/projects/PubBTQuant/ui-prototype/iterate_350.py`
  - Current authoritative harness.
  - Runs 350 total passes: 100 deterministic baseline passes plus 250 FREE OpenRouter model-persona passes.

- `~/projects/PubBTQuant/ui-prototype/iterate_100.py`
  - Compatibility wrapper around `iterate_350.py`.
  - Prevents stale runners from reverting the prototype to 100 passes.

- `~/projects/PubBTQuant/ui-prototype/index.html`
  - Embeds 350-pass metadata, visible model roster, hidden log, visible log, and runtime `window.BTQ_UI_ITERATION_PASSES` / `window.BTQ_MODEL_ROSTER`.

- `~/projects/PubBTQuant/ui-prototype/ITERATION_REPORT.md`
  - Full 350-row report with model roster and per-pass improvements.

## Primary FREE OpenRouter model

`qwen/qwen3-coder:free`

Reason: strongest fit for code-heavy UI iteration, large context, implementation-oriented critique, and FREE OpenRouter availability.

## Model roster used in the 250 model-persona passes

- `qwen/qwen3-coder:free` — primary UI/code architect.
- `nvidia/nemotron-3-ultra-550b-a55b:free` — heavy systems reviewer.
- `nvidia/nemotron-3-super-120b-a12b:free` — efficient reasoning reviewer.
- `openai/gpt-oss-120b:free` — open-weight generalist reviewer.
- `nousresearch/hermes-3-llama-3.1-405b:free` — Nous flagship reviewer.
- `openrouter/owl-alpha` — agentic research reviewer.
- `meta-llama/llama-3.3-70b-instruct:free` — general UX reviewer.
- `google/gemma-4-27b-it:free` — human-facing UX reviewer.
- `nex-agi/nex-n2-pro:free` — precision reviewer.
- `poolside/laguna-m.1:free` — fast code reviewer.
- `poolside/laguna-xs.2:free` — fast triage reviewer.

## Verification pattern

Run:

```bash
cd ~/projects/PubBTQuant/ui-prototype
python3 -m py_compile iterate_100.py iterate_350.py
python3 iterate_100.py
```

Expected output shape:

```text
passes_executed=350
model_persona_passes=250
free_models=11
html=/home/alca/projects/PubBTQuant/ui-prototype/index.html
report=/home/alca/projects/PubBTQuant/ui-prototype/ITERATION_REPORT.md
html_bytes=224452
report_bytes=64901
```

Then assert:

```text
meta_passes=350
hidden_log_items=350
visible_log_items=350
report_rows=350
roster_models=11
```

## Pitfalls

- Do not claim live LLM calls happened unless the harness actually called them.
- Do not call live trading APIs during deterministic UI iteration.
- Do not read secrets during deterministic UI iteration.
- Do not leave stale `iterate_100.py` behavior that reverts the artifact to 100 passes.
- If live OpenRouter model availability cannot be verified in the current session, use the known verified roster or verify later; disclose the verification status honestly.
