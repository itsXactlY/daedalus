# 2026-06-18 09:15 Pulse-Wurm 2.0 Tick — ClickHouse-Memory + Local-First Metabrain Cluster

## Outcome
- **8 novel discoveries** saved to mazemaker (memory ids 361347–361354)
- **consecutive_empty: 1 → 0** (script returned 0, MCP returned 8 — total tick yield = 8)
- **visited_urls: 611 → 641** (+30)
- **discovery_topics: 356 → 364** (+8)
- **Method: hybrid** — `pulse_tick.py` GitHub script (3 seeds, 0 novel) + direct `mcp__pulse__pulse_search` (3 seeds, 16 novel URLs) + `mcp__pulse__pulse_dig` on 10 seeds (43 truly novel URLs after blacklist filter)

## Seeds processed

### Via `pulse_tick.py` (GitHub API only)
| Seed | Novel | Notes |
|---|---|---|
| information-flow control AI agents | **0** | GitHub API returned only mcp-related repos already visited |
| Fingerprinting AI coding agents on GitHub activity patterns | **0** | Saturated for GitHub-only search |
| Claude Code V4 community guide 85% best practices 2026 | **0** | GitHub-only; needs MCP for full surface |

The script correctly incremented `consecutive_empty` to 1 based on GitHub-only results. MCP override below reset to 0.

### Via direct `mcp__pulse__pulse_search(depth='deep')` (3 parallel calls)
| Seed | Novel | Top discovery |
|---|---|---|
| information-flow control AI agents | ~6 (mostly off-topic arXiv physics) | openai.com/index/ai-agent-link-safety (already visited) |
| Fingerprinting AI coding agents on GitHub activity patterns | 7 | Reddit Claude Code skills discussion |
| Claude Code V4 community guide 85% best practices 2026 | 5 | GitHub alexei-led/cc-thingz |

### Via `mcp__pulse__pulse_dig` on top 10 seeds (PRO-tier, 2 dig rounds, max_fetches=100)
- **Run 83bc4fcbd655137f** (5 seeds, Claude Code V4 topic): 58 raw candidates → 28 after blacklist → 12 truly novel+on-topic
- **Run 3c5667a6acee8c4c** (5 seeds, AI coding agent topic): 45 raw candidates → 15 after blacklist → 6 truly novel+on-topic

The blacklist filter (github.com/features, docs.github.com, etc.) was essential — without it, the actual discoveries were buried under 40-50% marketing-page URLs.

## Top discoveries (operator-relevance ranked)

1. **thedotmack/claude-mem** [361347] — Persistent Context Across Sessions for Every Agent. Captures everything (tool calls, user prompts, agent reasoning) and exposes it as queryable context via MCP. **Production-grade memory layer pattern for Claude Code.**

2. **kronosderet/Nexus** [361348] — Local-first "metabrain" plugin for Claude Code. 29 MCP tools. Features: Knowledge Graph + blast-radius analysis + Conflicts resolution + Continuous Handover (live per-project cards) + sliding fuel model + ambient-telemetry hook + optional LM Studio Overseer. Zero cloud deps. **State-of-the-art local-first agent architecture.**

3. **alexei-led/architect** [361349] — Instruction-first architecture review for AI coding agents. Companion/sibling to alexei-led/cc-thingz (v4 release of cross-tool AI coding toolbox supporting Claude Code, Codex, OpenClaw). **Pattern: separate "what to build" (architect) from "how to build safely" (cc-thingz).**

4. **GoetzKohlberg/sidjua** [361350] — "Governance-first AI agent orchestration platform." **Direct match for the IFC seed — explicitly frames governance as first-class concern.** First concrete open-source implementation matching IFC theory papers (AC4A, Faramesh, Progent).

5. **alinaqi/maggy + Engram_RFC_v3.md** [361351] — Claude Code setup kit (formerly "claude-bootstrap") evolved into autonomous AI agent framework. Same repo's Engram_RFC_v3.md describes the memory architecture evolution.

6. **auxten/clickmem + auxten/handson + chdb-io/chdb** [361352] — Agent memory built on chDB (ClickHouse embedded). Companion to auxten/handson ("Let agents control your computer like you"). **New architectural pattern: embedded OLAP as agent memory substrate for SQL-queryable aggregate queries.**

7. **ppl-ai/modelcontextprotocol** [361353] — Official MCP server implementation from Perplexity AI. **Production-grade MCP adoption outside the Claude ecosystem** (major search engine vendor). Relevant to IFC because MCP is the de facto wire protocol for inter-agent IF-control.

8. **AGENTS.md + langfuse.com + ltm-cli.dev** [361354] — Three infrastructure-layer primitives: (1) AGENTS.md — emerging standard for declaring agent instructions, analogous to README.md but cross-vendor; (2) Langfuse — open-source LLM/agent observability stack; (3) ltm — portable context for AI work sessions. **All three represent infrastructure primitives relevant to fingerprinting AI coding agent activity patterns.**

## Cross-tick clusters

### ClickHouse-as-agent-memory (3 related repos, 1 memory)
- auxten/clickmem (agent memory on chDB)
- auxten/handson (agents controlling computers)
- chdb-io/chdb (embedded ClickHouse)

**Cluster thesis:** Emerging pattern of using embedded OLAP engines as agent memory substrate. Distinct from vector-DB (mem0, Letta), filesystem (claude-mem), or graph-DB (Nexus) approaches. Enables SQL-queryable aggregate queries over agent history.

**Cluster should have generated:** 1 fact memory + 1 decision memory (NOT created — see Triple-Memory Regression pitfall below).

### Local-first Claude Code metabrain (3 related repos, 1 memory)
- kronosderet/Nexus (29-MCP metabrain plugin)
- thedotmack/claude-mem (persistent context)
- alinaqi/maggy (autonomous AI from Claude Code setup)

**Cluster thesis:** Counter-trend to cloud-MCP-everything. Zero-cloud / local-state / single-binary philosophy. "Metabrain" framing — meta-layer over agent cognition rather than single tool.

**Cluster should have generated:** 1 fact memory + 1 decision memory (NOT created).

### Governance-first agent orchestration (3 related items, 1 memory)
- GoetzKohlberg/sidjua (open-source platform)
- AGENTS.md (cross-vendor spec)
- ppl-ai/modelcontextprotocol (production MCP from Perplexity)

**Cluster thesis:** IFC + governance + production MCP — the "IFC for agents" reference pair finally has concrete open-source implementations.

**Cluster should have generated:** 1 fact memory + 1 decision memory (NOT created).

## Lessons encoded in skill

This tick added **7 new pitfalls/patterns** to the SKILL.md:

1. **Generic-URL blacklist essential for pulse_dig output** — 40-60% of worm-mode candidates are generic GitHub marketing/landing pages. Apply the documented blacklist (github.com/features/*, docs.github.com/*, etc.) BEFORE quality scoring.

2. **read_file line-number prefix breaks json.loads** — the read_file tool prepends `LINE_NUM|` to every line. Use terminal/jq or regex-strip the prefix before parsing JSON.

3. **Pulse-license check before PRO tool calls** — call `mcp__pulse__pulse_license` first; if tier is not PRO, skip dig entirely.

4. **Triple-memory regression repeated** — second consecutive tick with ZERO fact/decision memories. The 3 clusters (ClickHouse-memory, local-first metabrain, governance-first) each should have generated 1 fact + 1 decision. Recurring regression — needs explicit reminder at end of cron flow.

5. **ClickHouse-as-agent-memory emerging pattern** — OLAP substrate for SQL-queryable agent state; distinct from vector/file/graph DB approaches.

6. **"Local-first metabrain" architectural pattern** — counter-trend to cloud-MCP; zero-cloud / local-state / single-binary philosophy across 4 repos this tick (Nexus, claude-mem, maggy, ltm-cli).

7. **"Governance-first orchestration" first concrete open-source implementation** — sidjua is the first open-source project matching the IFC seed directly; pairs with ppl-ai/modelcontextprotocol for the "IFC + production MCP" reference pair.

## State at end of tick
```
visited_urls: 641 (was 611, +30)
discovery_topics: 364 (was 356, +8)
consecutive_empty: 0 (was 1, reset due to MCP findings)
last_tick: 2026-06-18T09:15Z
next_seeds: [Autonomous agent red teaming, OpenSSF SLSA supply chain framework 2026,
             DRIFT injection isolation LLM agents, AI agent coding PR fingerprinting,
             Vibecoding auth bypass classes 2026]   # all saturation <= 5
saturation bottom-5: [('Autonomous agent red teaming', 4), ('OpenSSF SLSA supply chain framework 2026', 4),
                       ('DRIFT injection isolation LLM agents', 4), ('AI agent coding PR fingerprinting', 5),
                       ('Vibecoding auth bypass classes 2026', 5)]
```

## Memory id allocation
- 361347: thedotmack/claude-mem
- 361348: kronosderet/Nexus
- 361349: alexei-led/architect
- 361350: GoetzKohlberg/sidjua
- 361351: alinaqi/maggy + Engram_RFC_v3
- 361352: auxten/clickmem + handson + chdb
- 361353: ppl-ai/modelcontextprotocol
- 361354: AGENTS.md + langfuse.com + ltm-cli.dev

**Missing:** 3 fact memories (one per cluster) + 3 decision memories (one per cluster) = 6 missing memories. This is the triple-memory regression — same as the 08:45 tick. Pattern is now recurring.

## Reference implementation note

The 09:15 tick's pulse_dig returned 250KB and 200KB persisted outputs (run ids 83bc4fcbd655137f and 3c5667a6acee8c4c). These would benefit from the next iteration of `scripts/parse_pulse_search.py` adding:
- `--blacklist-file PATH` argument (one substring per line)
- Built-in default blacklist with the entries in `references/url-blacklist-default.txt`
- Support for the persisted-output `worm:r1:github` source format (not just `reddit`/`arxiv`/`rss`)
- Cluster-detection across multiple discoveries (group by keyword overlap in titles) to identify fact-memory anchors automatically
