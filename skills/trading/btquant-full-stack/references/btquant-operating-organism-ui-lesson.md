# BTQuant Operating Organism UI Lesson

## Lesson

The operator corrected the UI direction away from a generic trading dashboard. BTQuant UI work must start from the actual operating system:

```text
DATA → HOTSPINE → DETECTORS → RENDER → SIGNAL → STRATEGY → INDICATORS → RISK → EXECUTION → AGENCY → NEURAL → INFRA → LIMITATIONS
```

A BTQuant UI is incomplete unless every known stack component has a visible UI surface.

## Created Artifacts

- Spec: `/home/alca/BTQuant_Operating_Organism_UI.md`
- Prototype: `/home/alca/BTQuant_Operating_Organism_UI.html`

## Prototype Verification Pattern

Serve the standalone HTML locally and verify in-browser state, not backend state:

```text
title: BTQuant Operating Organism UI
vector: 18
domains: 18
edges: 19
signals: 6
surfaces: 11
limitations: 9
layers: 4
externalScripts: 0
liveDisabled: true
dryRun path: working
JavaScript errors: none
```

## Safety Invariant

Prototype UI work for BTQuant must not:

```text
touch backend code
call live trading APIs
read secrets
send live orders
claim live execution happened
```

The safe command path is draft → dry-run → audit only.

## UI Coverage Checklist

A BTQuant UI pass should expose:

```text
CCAPI spot connectors
HotSpine SHM
C++ manipulation detectors
BTQ Vulkan Render Engine
modified Backtrader/Cerebro
Strategy Factory and strategy catalogue
100+ indicators
Broker Matrix
Store Matrix
Feed Matrix
MsSQL BigBrainCentral
QuantStats / Research-Spine
Autonomous Agency
Neural Trading Pipeline
Live Deployer sandbox gate
MCP adapter :8910
PULSE macro integration
Known Limitations Board
```

## Pitfall

Do not let a metaphor replace domain truth. Weather, harmony, organism, cockpit, or console metaphors are useful only if they make the real BTQuant dependency chain clearer. If the metaphor hides CCAPI, HotSpine, detectors, Backtrader, brokers, stores, feeds, agency, neural, MCP, PULSE, or limitations, it is the wrong abstraction.
