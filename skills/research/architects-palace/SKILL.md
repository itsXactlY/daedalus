---
name: architects-palace
description: The Architect's Palace research archive — 1.6GB autonomous AI research (April 14-19, 2026)
category: research
---
# Architects Palace — Research Archive

## What
`~/The Architects Palace/` — 1.6GB autonomous AI research (April 14-19, 2026).
6 nights, zero human micromanagement. Every finding, every "holy shit" moment captured.

## Core Discoveries

### 1. Benchmark Contamination Crisis (ALWAYS REMEMBER)
Every major LLM cheats — including ours. Microsoft MMLU-CF proves 13-17pt drops across ALL models on contamination-free benchmarks:
```
Model               MMLU    MMLU-CF   Drop
GPT-4o              88.0    73.4      -14.6
GPT-4-Turbo         86.5    70.4      -16.1
Llama-3.3-70B       86.3    68.8      -17.5
Qwen2.5-72B         85.3    71.6      -13.7
```
String-matching decontamination fails — 8-18% HumanEval contamination found despite "decontamination." ETH Zurich proved malicious providers can evade ALL detection. The Stack: 18.9% HumanEval contaminated.

### 2. SmolVM × Neural Memory
Zero-config KI-Gedächtnis. Option D hybrid: SQLite fast-start (<200ms) + MSSQL hot-swap. 4 phases to production. MSSQL cold boot (5-15s) is the real bottleneck, not VM startup.

### 3. Gemma 4 Killed the 100B Narrative
26B-A4B MoE (128 experts, 3.8B active params) = ~1450 Elo competitive with 400B+ dense models. 51 tok/s on M4 MacBook Pro. Apache 2.0 license.

### 4. Musk Cognitive Architecture
**First Principles**: Strip to fundamental truths, build up from scratch. Battery example: $600/kWh conventional → $80/kWh material cost.
**5-Step Algorithm**: Question → Delete → Simplify → Accelerate → Automate. "Best part is no part."
**Asymmetric Betting**: Bet 100% on civilization-scale upside.

### 5. Geopolitical Convergence
FRAGILITY CONCENTRATION + RAPID PERTURBATION = CASCADE. 9 threads converging:
- Private Credit: Blue Owl/Baring/Morgan Stanley caps, Moody's ALL BDCs negative
- Hormuz: Iran's leverage = INSURANCE COSTS not kinetic closure
- Iran Nuclear: 2-4 weeks to weapon, IAEA needs 6-8 weeks to verify
- Food Chain: Oil→Gas→Fertilizer→Food. Egypt 105M, 60-65% wheat import dependent
- Timeline: Q2-Q3 2026 (credit cascade 60%), Q3-Q4 2026 (food 50%), Q4 2026+ (systemic 35%)

### 6. PULSE Extension Roadmap
7 fields from 93 arXiv papers: query-type-aware routing (SelRoute), iterative retrieval (SubSearch), multi-agent research crews (HLER), retentive relevance, cross-source confirmation, adaptive lookback, prediction market enrichment.

### 7. 100+ Coding Conventions
15 categories: SOLID, Design Patterns, Error Handling, Type Hints (PEP 695), Protocols, Dataclasses, Async, Testing (Hypothesis), Clean/Hexagonal/CQRS/EventSourcing Architecture.

## Repository Structure
```
The Architects Palace/
├── MASTER_CONVERGENCE_SYNTHESIS.md   # Geopolitical signal map
├── convergence_tracker.md              # Live tracking
├── benchmark_contamination_research.md # MMLU-CF crisis
├── OOP_DELUXE_MASTER.md              # 100+ conventions
├── smoltvm-neural-memory-feasibility.md # SmolVM packaging
├── musk_cognitive_architecture_report.md
├── pulse_arxiv_deep_research.md      # 7 extension fields
├── ai_model_war_deep_dive_2026-04-18.md # Gemma 4 + Claude leak
├── self-improvement-audit-2026-04-09.md # 32 issues audit
├── architecture_patterns_research.md  # Clean/Hexagonal/CQRS
├── BDC-mitigation-assessment/        # ICML'25 mitigation
├── DICE/                            # Contamination detection
├── MMLU-CF/                         # Contamination-free benchmark
├── malicious-contamination/          # ETH Zurich evasion
├── neural-dashboard-research/        # Terminal UI research
└── convention_research/             # 662-line conventions
```

## Key Insights
- **All retrieval queries return session-summary hub nodes** (24+ edges) — new memories need time to build connections
- **MEMORY.md (SOUL) is NOT stored as neural memory** — it's injected from config at session start
- **REGEL 1**: neural_remember > session_search > memory tool
- The Palace represents "what happens when an autonomous AI agent is given a research mandate and left to run overnight"
