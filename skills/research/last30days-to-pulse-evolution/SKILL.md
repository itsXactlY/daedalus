---
name: last30days-to-pulse-evolution
description: The history of how last30days became PULSE - the multi-source search engine evolution
category: research
version: 1.0
tags: [pulse, last30days, evolution, history, search-engine, social-search]
priority: high
---

# last30days → PULSE Evolution

The story of how a simple GitHub search became a 15-source social search engine.

## The Origin

**last30days** by [mvanhorn](https://github.com/mvanhorn/last30days-skill):
- 14+ sources
- ~15,000 lines
- Built by a human who knew exactly what he wanted
- GitHub-only search, last 30 days

## PULSE v0.0.1 (Ground-Up Reconstruction)

Independent reimplementation. NOT a fork. Pure Python stdlib, zero dependencies.
- GitHub search only
- Last 30 days filter
- Basic engagement scoring

## PULSE v0.0.3 (The Big Leap)

- **10 sources**: Reddit, HN, Polymarket, YouTube, GitHub, ArXiv, Lobsters, RSS, Web, News
- **~9,370 lines** of pure Python
- **stdlib-only**: no pip dependencies
- **5-Signal Scoring**: engagement, recency, authority, diversity, relevance
- **WRRF**: Weighted Reciprocal Rank Fusion
- **3-Pass Dedup**: content deduplication
- **Self-Learning Source Weights**: sources learn which ones are most useful
- **Neural Memory Integration**: results stored in knowledge graph

## PULSE v0.0.4 (Current — The Agent Build)

**"The human built the scaffolding. The agent builds the cathedral."**

- **15 sources**: + Bluesky, Dev.to, Lemmy, OpenAlex, Semantic Scholar, StackExchange, Manifold, Metaculus
- **Query Router**: type-aware routing (breaking news vs academic deep-dive vs prediction scan)
- **Adaptive Lookback**: adjusts time window based on query type
- **7-Signal Scoring**: + temporal_decay + source_confidence
- **Iterative Retrieval**: refine search based on initial results
- **Trend Detection**: identify emerging topics
- **Multi-Agent Research Crew**: parallel agents for deep research
- **1,430 new lines**

## Design Decisions

| Decision | Reason |
|----------|--------|
| stdlib-only | Zero install friction for agent |
| Engagement scoring | Real signal > SEO > editors |
| Multi-source | No single source has full picture |
| Self-learning weights | Sources improve over time |
| Neural memory integration | Research compounds |
| Agent-built | Designed to be evolved by machines |

## The Symlink Disaster

9 agents, 2 rounds, symlink ate everything. A `lib` symlink at project root pointing to `scripts/lib` caused `write_file` to silently overwrite through the symlink. `git checkout` destroyed the work. Lesson: ALWAYS check for symlinks before spawning parallel agents.

## Where It Lives

- Project: `~/projects/pulse/`
- Skill: `~/.hermes/skills/devops/pulse/SKILL.md`
- Research: `~/The Architects Palace/pulse_arxiv_deep_research.md`
- Free APIs research: `~/The Architects Palace/pulse_free_apis_research.md`
