# Numbers Cross-Check — fill from a LIVE mazemaker_* pull (THE TABLE WINS)

Copy this into the asset library's README. Re-pull every tool THIS turn; do not reuse
last month's numbers. Corpus counts drift monthly.

| Metric | Value | Source (tool) |
|---|---|---|
| memories | <mazemaker_stats.memories> | mcp__mazemaker__mazemaker_stats |
| connections | <mazemaker_stats.connections> | mcp__mazemaker__mazemaker_stats |
| embedding_dim | <mazemaker_stats.embedding_dim> | mcp__mazemaker__mazemaker_stats |
| DAE coverage | <mazemaker_health.dae.coverage> | mcp__mazemaker__mazemaker_health |
| DAE vectorised | <mazemaker_health.dae.vectorised> | mcp__mazemaker__mazemaker_health |
| AFE atomic facts | <mazemaker_health.afe.facts_count> | mcp__mazemaker__mazemaker_health |
| dream sessions | <mazemaker_dream_stats.sessions> | mcp__mazemaker__mazemaker_dream_stats |
| dream processed | <mazemaker_dream_stats.total_processed> | mcp__mazemaker__mazemaker_dream_stats |
| dream strengthened | <mazemaker_dream_stats.total_strengthened> | mcp__mazemaker__mazemaker_dream_stats |
| dream pruned | <mazemaker_dream_stats.total_pruned> | mcp__mazemaker__mazemaker_dream_stats |
| dream bridges | <mazemaker_dream_stats.total_bridges> | mcp__mazemaker__mazemaker_dream_stats |
| dream insights | <mazemaker_dream_stats.total_insights> | mcp__mazemaker__mazemaker_dream_stats |
| LongMemEval-S R@5 | 0.9787 (R@1 0.8574 · R@10 0.9894 · MRR 0.9114) | benchmarks/external/results/*.json (sha d6f21ea9) |
| godbench-oracle R@5 | 0.8426 | iter100 result JSON |
| Hindsight demolition | 188/200 = 94.0% | demolition_*.json |
| gemma3:270M | 18/20 = 90% | demolition_*.json |
| Hop-2 graph | 0.00 → 1.00 | benchmarks/external/results/hop2_* |
| Shuffled-edge | 1.00 → 0.27 | same |
| Post-dream synthesis | 0.00 → 0.43 (n=75, k=5) | same |
| Conflict supersession | 60% → 33% stale dominance | same |
| Audit chain | v2 NO → v8 unconditional YES | benchmarks/audit/v[2-8]_verdict.md |
| Federation | JRWL / JackrabbitDLM (port 37373) + X3DH + Double Ratchet (Signal-grade FSE) | hermes-crypto module |
| Retrieval channels | 8: semantic · BM25 · entity · temporal · salience · PPR · ColBERT@1.5 · DAE | engine config |
| Dream phases | 7: NREM · Supersedes · REM · Insight · AFE · DAE · Synthesis | engine config |
| Android app | v1.1.0, 2.58 MB release-signed APK, Pro benefit | mazemaker.online/app/ |
| Pricing | Builder $15 ($9 founder) · Pro $49 ($29 founder, first 100 / until 2026-09-30) · Team $149 | live Stripe |

**Rule:** if any number on the live site, in any post, or in the video disagrees with
this table, the table wins and the asset must be re-rendered before re-drop.
