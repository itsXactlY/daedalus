# Mazemaker Neural Memory System

## Core Stats (2026)
- **Memories**: 204,971 stored facts
- **Connections**: 54,504 knowledge graph edges
- **AFE Facts**: 4,762 atomic facts extracted
- **DAE Coverage**: 99.9% vectorized

## Dream Engine
- **Sessions**: 41,667 dream cycles
- **Total Strengthened**: 147,092,005 connections
- **Total Pruned**: 19,168,141 weak connections
- **Bridges Created**: 52,077,408
- **Insights Generated**: 9,292,332 (bridge: 9,017,561, cluster: 275,457)

## Architecture
- **Semantic Search**: ~190k facts, 1024-d embeddings, hybrid recall
- **Hybrid Channels**: semantic, fts, colbert, dae, ppr, intent, temporal, salience, canonical
- **Graph Traversal**: Spreading activation from memory IDs
- **Conflict Detection**: SUPERSEDES phase for cross-session revision tracking

## API Layers
1. **Recall**: mazemaker_recall - semantic search over memory graph
2. **Remember**: mazemaker_remember - persist curated facts (60-300 words)
3. **Think**: mazemaker_think - graph traversal for related concepts
4. **Dream**: mazemaker_dream - autonomous consolidation (NREM/REM/Insight phases)
5. **Health**: mazemaker_health - corpus diagnostics

## Workflow
- **Query First**: Always mazemaker_recall before terminal/grep
- **Stop After Hit**: If similarity >= 0.4, answer from it exclusively
- **Save Automatic**: mazemaker_remember after every substantive turn
- **Labels**: decision:*, fact:*, bug:*, invariant:*, ops:*, user:*, signal:*, commit:*

## Query Types Detected
- **preference**: User preferences and habits
- **temporal**: Time-related questions ("when did X happen")
- **factual**: Concrete facts about the stack
- **general**: Open-ended queries