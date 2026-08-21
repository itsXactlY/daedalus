# 2026-06-18 08:45 Pulse-Wurm 2.0 Tick — Hybrid Pattern

## Outcome
- **15 novel discoveries** saved to mazemaker (memory ids 361137–361146, 361149–361153)
- **consecutive_empty: 0** (10 GitHub + 5 MCP = hybrid)
- **visited_urls: 583 → 599** (+16)
- **Method: hybrid** — `pulse_tick.py` GitHub script (3 seeds) + direct `mcp__pulse__pulse_search` (2 seeds)

## Seeds processed

### Via `pulse_tick.py` (GitHub API only)
| Seed | Novel | Top discovery |
|---|---|---|
| OpenAI Codex CLI integration patterns 2026 | **0** (saturated, 4+ consecutive ticks) | — |
| AI agent security vulnerabilities 2026 | 5 | samsaeed22/kevlar-benchmark |
| AI coding agent production deployment | 5 | jimtin/production-ai |

### Via direct `mcp__pulse__pulse_search`
| Seed | Novel (high-signal) | Top discovery |
|---|---|---|
| AI coding agent production deployment verification gates planning preflights | 5 | vibecoding-db-deletion |
| OWASP ASI Top 10 LLM agent vulnerability 2026 injection benchmark | 0 (LLM filter kept 0/30, all tail-passed were off-topic) | — |

## Top discoveries (operator-relevance ranked)

1. **vibecoding-db-deletion** [361149] — Reddit thread: vibe-coding AI agent autonomously deleted production DB after panic state. **Direct case study for agent-delivery-integrity anti-pattern.**
2. **jimtin/production-ai** [361142] — Planning-gates + test-preflights framework. **Reusable patterns for operator's skill ecosystem.**
3. **Basketmakerfaitaccompli622/awesome-claude-code-security** [361145] — Vertical-specific Claude Code security tooling list. **Cross-link to operator's hermes-mcp-security-audit skill.**
4. **samsaeed22/kevlar-benchmark** [361137] — OWASP ASI-aligned quantitative scoring for agent injection. Pairs with veldt-kya (earlier today) + agentic-redteam-langgraph (earlier today).
5. **yaalalabs/agent-kernel** [361143] — Enterprise agent OS layer with compliance framing.

## Cross-tick clusters

### AI coding dev-vs-prod gap (4 threads this tick, all from MCP)
- `vibecoding-db-deletion` [361149] — panic state → DB delete
- `$4000 spent on AI coding, nothing worked in production` [361152a]
- `Amazon blames human employees for AI coding agent's mistake` [361152b]
- `AI coding productivity data is in, it's not what anyone expected` [361151]

This cluster **validates jimtin/production-ai's planning-gate+preflight approach** as the defense — and is the perfect cluster-anchor for a `fact:` + `decision:` memory pair. **The 08:45 tick missed this opportunity** (see "Triple-memory violation" pitfall below).

### Agentic red-team cluster (continued from earlier today)
- 4 new tools this tick: kevlar-benchmark, PatchCascade-SOC, agentic-ai-red-teaming-2026, protocol-guardian
- Joins earlier: agentic-redteam-langgraph [361023], redteam-cli [360974]
- Six tools in one day on agentic red-teaming across both "AI for security" and "security for AI" axes.

## Lessons encoded in skill

This tick added **5 new pitfalls** and **1 new section** to the SKILL.md:

1. **Persistently-zero seed rotation bug** — Codex-CLI has been at 0 novel for 4+ ticks but never triggered rotation because the script's `consecutive_empty` only counts total-tick yield. Symptom: dead seed wastes one of 3 search slots. Fix: manually saturate the seed (`saturation_scores[seed] = 10`) or drop from `next_seeds` directly.

2. **Triple-memory shape violation** — saved 15 discovery memories but ZERO fact/decision memories. The cluster-anchor fact memory is what makes findings graph-resilient. **The 08:45 tick regressed from the 08:32 3+3+1 pattern to discovery-only.** Future ticks should write at minimum 1 fact + 1 decision per cluster (3+ discoveries on one topic).

3. **Hybrid GitHub-script + MCP-pulse_search yields strictly non-overlapping discoveries** — confirmed empirically. GitHub-only script misses Reddit/paper/blog entirely. MCP search misses GitHub repos. Combined finds ~50% more unique discoveries per tick.

4. **Pulse search LLM filter keep-rate is topic-dependent** — `kept=0` with `tail_passed_through > 5` is a search-failure signal (similar to Cornell-Triedman). `kept >= 5` with `tail_passed_through > 5` is broad-topic noise. Parser should print filter_stats for every tick.

5. **Lobsters fallback to off-topic topics** — when `lobsters` source appears in `items_by_source` of a failing seed, treat its candidates as noise unless title is unambiguously on-topic.

## State at end of tick
```
visited_urls: 599
discovery_topics: 355
consecutive_empty: 0
last_tick: 2026-06-18T06:54:11Z
next_seeds: [OpenAI Codex CLI integration patterns 2026, DRIFT injection isolation LLM agents,
             information-flow control AI agents, Autonomous agent red teaming,
             OpenSSF SLSA supply chain framework 2026]
saturation bottom-3: [('OpenAI Codex CLI integration patterns 2026', 0),
                       ('DRIFT injection isolation LLM agents', 2),
                       ('information-flow control AI agents', 2)]
```

## Memory id allocation
- 361137–361146: GitHub-script discoveries (10)
- 361149–361153: MCP-pulse_search discoveries (5)
- **Missing:** `fact:pulse-discovered-ai-coding-dev-prod-gap-20260618` and `decision:pulse-wurm-action-20260618-prod-verification` — these were not created, which is the triple-memory violation.
