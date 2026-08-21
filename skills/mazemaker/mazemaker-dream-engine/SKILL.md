---
name: mazemaker-dream-engine
category: devops
description: How to run the mazemaker dream cycle (NREM/REM/Insight) — via MCP tool, not via scripts.
---

# Mazemaker Dream Engine

Background memory consolidation for the mazemaker store. Three phases inspired by biological sleep:

- **NREM** — replay recent memories, strengthen activated edges (sim ≥ 0.4 → +0.05 weight), prune below 0.05
- **REM** — find isolated memories, create bridge edges (weight 0.1-0.3, `edge_type='bridge'`)
- **Insight** — Louvain community detection, identify bridge nodes between communities, emit `derived:cluster` insight memories

## How to run it — MCP tool only

```
mazemaker_dream(phase='all')   # all three phases sequentially
mazemaker_dream(phase='nrem')  # replay + strengthen only
mazemaker_dream(phase='rem')   # bridges only
mazemaker_dream(phase='insight') # community detection only
```

That is the whole interface. Do NOT shell out to `dream_worker.py`, do NOT search for symlinks under `~/.hermes/plugins/`, do NOT touch any venv. The MCP tool dispatches into the engine and returns the cycle stats. If the user types `mazemaker_dream(phase='all')` literally, that is them telling you to call exactly that MCP tool with that argument — call it.

## Background daemon — already running

A standalone `dream_worker` runs on the host (separate from the MCP container) and triggers a full cycle every 5 minutes. You almost never need to invoke `mazemaker_dream` manually — fresh memories get consolidated within minutes automatically.

The one legitimate manual case: same-day recall returned weak / empty hits. Call `mazemaker_dream(phase='all')` once, wait for it to return, then retry `mazemaker_recall`. The cycle lifts fresh memories into stable retrieval.

## Stats

`mazemaker_dream_stats()` returns recent cycle counts, NREM strengthen/weaken/prune totals, REM bridge counts, Insight community counts. Use this to confirm the daemon is healthy or to inspect a manual cycle's output.

## Anti-patterns

- Running `dream_worker.py` directly from a shell — there is one host daemon already; a second process fights the SQLite WAL lock and slows both.
- Setting `EMBED_IDLE_TIMEOUT=0` from the agent — the host daemon owns the embed-server lifecycle.
- Passing `--backend sqlite` or any flag — that interface is gone; the MCP tool has no flags except `phase`.
- Reading the engine's Python source to figure out parameters — the MCP tool description in `tools/list` is canonical.
