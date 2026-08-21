---
name: alice-maze-router-v2-design
description: "Design target for a future Alice-Router — an ID-anchored maze-navigator that does the Phase-1 recon walk (mazemaker_get/think from a prior memory id) as a cheap first hop, instead of her current narrow job of picking between two recall tool variants. NOT IMPLEMENTED. No path to a running backend today (single GPU, can't hold two models alongside the main one)."
category: devops
version: 0.1
tags: [alice, router, mazemaker, design, redesign, delegation, maze-navigation]
priority: low
status: design-draft-not-implemented
---

# Alice-Router v2 — maze-navigator design target

## Status: NOT IMPLEMENTED. This is a spec, not a description of current behavior.

Do not write anything into `config.yaml`'s live `system_prompt` or
`personalities.*` claiming Alice does what's described here — she doesn't,
and there's currently no backend for her to run on this box (single GPU;
running her alongside the main model isn't possible without swapping one
out). The main agent's [MAZE NAVIGATION PROTOCOL] block (in `system_prompt`
and `personalities.architect`) already does the job described below
directly, with no dependency on Alice. This skill exists so that if/when a
second GPU, a smaller/quantized Alice, or a time-sliced scheduling scheme
becomes available, the redesign work has a starting spec instead of
starting from "what was Alice for, again?"

## What Alice actually is today (read these first)

- `alice-routing-debugging` — the real, current, narrow scope: given a
  `mazemaker_recall`/`mazemaker_recall_multi` call, Alice picks WHICH of
  those two tool variants to use. The caller's query/args always win — she
  never touches ids, never walks the graph, never reconstructs history.
- `alice-ab-token-measurement` — measured real value of that narrow scope:
  ~1% main-model token savings (2026-08-11, 5-query harness). Her real
  value today is local/free decision tokens + consistency, not context
  reconstruction.
- `agent/alice_router.py` docstring: "ALICE routes the TOOL TYPE only...
  Any failure fails OPEN to the direct pod call."

Neither of those two skills, nor the source, describe an id-anchored
context-reconstruction role. That's the gap this design fills.

## The gap: what a v2 Alice would need to do instead

The operator's framing (2026-08-16): the harness runs near-zero historical
context by design — the memory graph is the real state, not the prompt.
The main agent already does the Phase-1/2/3 loop itself (see
[MAZE NAVIGATION PROTOCOL] in config.yaml):

1. **Recon** — given a prior memory id (an anchor), walk the graph from it
   (`mazemaker_get`/`mazemaker_think(depth=2-3)`) instead of a cold
   keyword search, to reconstruct the full picture BEFORE a plan exists.
2. **Plan/think** — synthesize that picture into a plan.
3. **Execute near-zero** — drop back to a terse working context, carrying
   forward only the plan + the new anchor id for next time.

Phase 1 is the expensive, deliberate step — exactly the kind of bounded,
well-specified sub-task a small dedicated router model is good at
offloading from the (larger, more expensive) main model. That's the v2
role: **Alice does the graph walk, not just the tool-name pick**, and
hands back a synthesized "here's the full picture as of anchor <id>"
result instead of just "use recall_multi."

## What would actually need to change (real engineering, not config)

- `ALICE_ROUTE_TOOLS` (`agent/alice_router.py`) currently only contains
  `mazemaker_recall`/`mazemaker_recall_multi`. A v2 scope needs to
  include the graph-walk tools (`mazemaker_get`, `mazemaker_think`) and a
  new entry point that takes an anchor id + a budget (depth/hop count),
  not just a query string.
- The "parent's query always wins, Alice's args are ignored" contract
  (deliberate, per the docstring, because Alice hallucinates queries) would
  need to flip for the walk itself — she needs to actually traverse and
  summarize, not just pick a tool name. That's a materially different
  model capability than a 3B recall-variant classifier was trained for;
  it may need retraining/fine-tuning, not just an expanded tool allowlist.
- `delegation.*` in config.yaml is the general `delegate_task` subagent
  path (fixed 2026-08-16 — see commit/memory on the dead-8768 bug) and is
  a SEPARATE mechanism from `alice_router.py`'s narrow bridge. A v2 Alice
  used for Phase-1 recon would likely want its own explicit call site
  (not `delegate_task`, not the current `ALICE_ROUTE_TOOLS` bridge) —
  design that entry point rather than overloading either existing path.
- Fail-open still applies: if v2 Alice is down/absent, Phase 1 must fall
  back to the main agent doing the walk itself directly — exactly what
  happens today, since that's the only path that currently exists.

## The infra blocker (why this is priority: low)

Single GPU. The main model (currently `gpt-oss-20b-UD-Q6_K_XL.gguf` on
:8888) and Alice (`alice_qwen_lora_merged...gguf`, systemd unit
`alice-router.service`, configured for :8801, stopped since 2026-08-11)
cannot both be resident at once. Until there's a second GPU, a much
smaller/quantized Alice that fits alongside the main model in the same
VRAM budget, or a time-sliced load/unload scheme, this redesign has no
runtime to target — it's a spec to pick up later, not a task to schedule
now.
