# Complex-System Harmony Maps

## Rule

For dense technical systems, do not reduce the interface to a generic dashboard. Show the system as a human-readable operating map: one top-level harmony vector, a dependency graph, and drilldowns into each domain.

## Pattern

1. **Harmony vector** — one glance at the whole system's health and tension points.
2. **Operating map** — graph or layered map showing how components depend on one another.
3. **Signal matrix** — rows for signals, actions, or subsystems; columns for confidence, freshness, blocker, and next safe action.
4. **Inspector drawer** — detailed state for the selected component without losing the global map.
5. **Command/audit panel** — when actions exist, show draft, dry-run, idempotency, rollback, and audit trail.
6. **Limitations board** — always-visible constraints that qualify the UI's conclusions.

## Why it works

A harmony map preserves system truth while reducing cognitive load. It lets operators see the whole organism and still trace any single component back to its source, status, and risk.

## Example

BTQuant's UI should not become a chart page or trade monitor. It should expose the full quantitative organism: CCAPI, HotSpine, detectors, render engine, Backtrader, strategies, brokers, stores, feeds, MsSQL, agency, neural pipeline, live gate, MCP, PULSE, and known limitations.

## Pitfalls

- Hiding missing connectors or sandbox-only execution.
- Turning the UI into a flat component list without dependency flow.
- Showing only one generic score when the system needs a vector.
- Letting the prototype execute live actions before the command audit path exists.
