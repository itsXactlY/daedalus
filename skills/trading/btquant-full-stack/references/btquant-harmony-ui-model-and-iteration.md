# BTQuant Harmony UI — Model and Iteration Pattern

## Purpose

This reference captures the session-specific pattern for generating and refining a BTQuant UI concept that is simple for humans but honest about BTQuant's full stack complexity.

## Free Model Choice

For early UI ideation through the Kilocode/OpenRouter gateway, prefer the best free OpenRouter model available instead of burning Nous credits.

- Working choice in this session: `openrouter+gpt-oss-120b`
- Kilocode fallback syntax if the gateway expects provider:model form: `openrouter:gpt-oss-120b`

Use paid/frontier models only later for final polish, not for the first concept pass.

## Product Framing

Do not call BTQuant's UI a generic dashboard. Frame it as:

> BTQuant Harmony UI is the operating map for the entire BTQuant quantitative organism: every component visible, every dependency traceable, every risk explainable, every action safe.

The UI should answer five questions in one glance:

1. Is the stack healthy right now?
2. Which signals have conviction and why?
3. What changed in the market, data, strategy, or execution layer?
4. What command is safe to draft, inspect, and audit?
5. Which known limitations block or qualify execution?

## Core UI Pattern

Use a harmony model rather than a flat dashboard:

- **Stack Harmony Vector**: one top-level health vector with domains such as DATA, HOTSPINE, DETECTORS, RENDER, BACKTRADER, STRATEGIES, BROKERS, STORES, FEEDS, DB, RESEARCH, AGENCY, NEURAL, LIVE, MCP, PULSE, and LIMITATIONS.
- **Operating Map**: graph or layered map showing CCAPI → HotSpine → detectors/render/backtrader → strategies → brokers/live gate.
- **Signal Matrix**: rows for signals, strategies, feeds, indicators, detectors, risk, and actions; columns for confidence, freshness, source, blocker, and safe next action.
- **Inspector Drawer**: drill into the real BTQuant component behind any UI card.
- **Command Audit Panel**: draft commands with dry-run intent, signed-command placeholder, idempotency, rollback, and execution log; never execute live trading commands from an early prototype.
- **Known Limitations Board**: always visible, never hidden in settings.

## Backend Contract Pattern

A BTQuant Harmony UI is incomplete without the backend contract that makes the UI trustworthy:

- OpenAPI/AsyncAPI for REST and event streams.
- WebSocket primary transport with SSE fallback.
- Structured health endpoint returning the Stack Harmony Vector.
- Command draft/audit endpoint before any live command execution.
- Correlation IDs on every request/event/command.
- Explicit stale-data indicators and reconnect states.
- Rate limits, authentication, authorization, and audit logs for execution paths.

## Static Prototype Workflow

1. Write a short product spec before touching code.
2. Build a self-contained static HTML prototype with mock data only.
3. Serve it locally: `python -m http.server 8123 --directory ui-prototype`.
4. Open it in the browser and check title, stack vector, graph/map, matrix rows, inspector behavior, and JavaScript console.
5. If the user asks for iteration depth, run deterministic refinement passes over the same artifact rather than rewriting from scratch.

## 100-Iteration Refinement Pattern

When asked for "at minimum 100 iterations", treat it as a quality gate, not a gimmick. Each pass should improve at least one of:

- Accessibility and keyboard behavior.
- Semantic HTML and ARIA correctness.
- State coverage: loading, empty, error, reconnect, partial failure, stale data.
- BTQuant stack coverage.
- Command safety and auditability.
- Observability and traceability.
- Copy clarity and cognitive load.
- Visual hierarchy, tokens, and responsive layout.
- Documentation and handoff notes.

A pass that only changes colors or repeats the same text is not a real iteration.

## Pitfalls

- Do not reduce BTQuant to a chart page or trade monitor.
- Do not hide missing connectors, sandbox-only live deploy, Python 3.14 `fast_mssql` limitations, or other constraints.
- Do not use live secrets or live trading commands in prototypes.
- Do not spend paid model credits on first-pass UI ideation when a free OpenRouter model is sufficient.
- Do not create a flat list of components without showing dependency and data flow.
