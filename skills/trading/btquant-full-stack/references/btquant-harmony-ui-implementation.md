# BTQuant Harmony UI Implementation Notes

## Purpose

This reference captures the implementation pattern learned while turning the BTQuant Harmony UI concept into a static prototype.

## Core Correction

Do not build a generic trading dashboard for BTQuant. BTQuant is a full quantitative operating system. The UI must expose every major stack domain as a first-class surface:

- CCAPI exchange ingestion
- HotSpine shared memory
- C++ manipulation detectors
- BTQ Vulkan Render Engine
- modified Backtrader / Cerebro
- strategy catalogue and Strategy Factory
- 100+ indicators
- brokers, stores, and feeds
- MsSQL BigBrainCentral
- QuantStats / Research-Spine
- Autonomous Agency
- Neural Trading Pipeline
- Live Deployer gate
- MCP adapter
- PULSE macro integration
- Known Limitations Board

If a component exists in BTQuant but has no UI surface, the UI is incomplete.

## Implementation Pattern

1. Audit the BTQuant project before building UI.
   - Confirm existing UI paths, e.g. `ui-prototype/index.html` and `UI_CONCEPT.md`.
   - Confirm MCP adapter path: `mcp-adapter/server.py`.
   - Confirm major stack paths from the skill before inventing new abstractions.

2. Build the prototype in the existing UI path first.
   - Primary artifact: `ui-prototype/index.html`
   - Support artifact: `ui-prototype/README.md`

3. Use a static self-contained prototype before wiring live services.
   - No secrets.
   - No live trading commands.
   - Mock data only.
   - Command actions should be drafted/logged, not executed.

4. Represent the stack as an Operating Map.
   - Stack Harmony Vector as the top-level view.
   - Graph nodes for real BTQuant components.
   - Signal Matrix for strategy/feed/indicator/detector/risk/action.
   - Inspector panel for component details.
   - Command Audit panel for safe command drafting.

5. Add a Known Limitations Board.
   - No perpetual/futures support.
   - No Hyperliquid connector.
   - CCAPI spot-only.
   - Detectors spot-only.
   - Live deployer sandbox by default.
   - Python 3.14 native `fast_mssql` limitation.

6. Verify the artifact.
   - Serve with: `python -m http.server 8123 --directory ui-prototype`
   - Open: `http://127.0.0.1:8123/`
   - Confirm title, stack vector, graph nodes, matrix rows, and no JavaScript errors.

## User-Visible Product Language

Use this framing:

> BTQuant Harmony UI is the operating map for the entire BTQuant quantitative organism: every component visible, every dependency traceable, every risk explainable, every action safe.

Avoid framing it as merely a dashboard, chart page, or trade monitor.
