# BTQuant Harmony Weather Organism

Session-specific reference for the `flawless-ui-ux-backend-design-principles` skill.

## Purpose

Use this pattern when a dense backend stack needs a simple, human-readable operating surface without touching backend code. The goal is not a generic dashboard; it is a stack-level harmony map that preserves complexity underneath while exposing simple weather on top.

## Theme

```text
BTQuant Harmony Weather Organism
```

Metaphor:

```text
DATA is the atmosphere.
FEEDS are wind.
DETECTORS are radar.
STRATEGIES are pressure systems.
RISK is gravity.
EXECUTION is lightning.
AGENTS are pilots.
INFRASTRUCTURE is terrain.
LIMITATIONS are the map legend.
```

## Model Path Used

```text
qwen/qwen3-coder:free
OpenRouter via kilocode
```

This was the best FREE fit for implementation-aware UI architecture and prototype reasoning. For pure ideation, `nvidia/nemotron-3-ultra-550b-a55b:free` is a stronger alternate, but less implementation-focused.

## Session Artifacts

```text
/home/alca/BTQuant_Harmony_Weather_Organism.md
/home/alca/BTQuant_Harmony_Weather_Organism.html
```

## Required UI Regions

1. Current Weather Bar
2. Stack Domains
3. Harmony Weather Map
4. Signal Matrix
5. Inspector Drawer
6. Limitations Board
7. Command Draft + Audit Drawer

## Non-Negotiables

- Do not touch existing backend code when the user asks for a theme, idea, or prototype.
- Do not call live trading APIs from the prototype.
- Do not read secrets.
- Do not execute live commands.
- Do not hide missing connectors, stale data, sandbox limits, or unknown states.
- Do not reduce the stack to one fake health score.
- Do not turn the UI into a flat component list.

## Prototype Safety Pattern

The command drawer should support:

```text
DRAFT
DRY-RUN
RISK-CHECK
APPROVE
EXECUTE
AUDIT
```

But in a standalone prototype:

```text
Live execute must remain disabled.
Dry-run must not call backend systems.
Audit log should be local/mock only.
```

## Verification Checklist

For standalone prototypes:

```text
No external scripts.
No live trading API calls.
No secret reads.
No live command execution.
Node/edge/signal selection updates inspector and command target.
Draft command enables dry-run.
Dry-run completion updates status and disables dry-run.
Live execute remains disabled.
Browser console has no JavaScript errors.
```

Session verification returned:

```text
vector: 8
domains: 24
edges: 24
signals: 6
limitations: 7
externalScripts: 0
liveDisabled: true
audit log after dry-run: 1 event
```

## Pitfalls Found

- If selecting a node/edge/signal does not update the command target, the command drawer feels disconnected from the map.
- If dry-run completion leaves the dry-run button enabled or status stale, the UI looks fake.
- If the prototype calls live systems, it violates the safety contract.
- If limitations are hidden, the UI becomes false certainty instead of operator trust.
