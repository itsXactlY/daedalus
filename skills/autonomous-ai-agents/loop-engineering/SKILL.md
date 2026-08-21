---
name: loop-engineering
description: Design and deploy autonomous loop systems that prompt agents instead of you. Covers the 5+1 primitives (automations, worktrees, skills, plugins, sub-agents, state) extended with graph-native cadence patterns using mazemaker as the control plane — not just storage.
version: 1.0.0
author: hermes
tags: [loop-engineering, autonomous-agents, multi-agent, orchestration, mazemaker, graph-native, cron, cadence]
related_skills: [ai-coding-agents, kanban-orchestrator, hermes-agent]
category: autonomous-ai-agents
---

# Loop Engineering — Graph-Native Autonomous Agent Loops

> Loop engineering is replacing yourself as the person who prompts the agent. You design the system that does it instead. A loop is a recursive goal where you define a purpose and the AI iterates until complete.
>
> — Steinberger, Cherny, June 2026

## When to use this skill

- User asks about loop engineering, agent automation, or "designing loops that prompt agents"
- User wants to build a system that runs on a timer, spawns sub-agents, and feeds itself
- User asks about the 5+1 primitives (automations, worktrees, skills, plugins, sub-agents, state)
- User wants to combine cron jobs, mazemaker, and delegate_task into an autonomous system
- User wants comprehension debt detection, convergence measurement, or failure pattern analysis

## THE RULE: mazemaker FIRST, always

Before proposing ANY loop design, call mazemaker_recall and mazemaker_think to understand what already exists. The user has ~205k memories and 55k edges — proposing without querying is wasting their time. They will tell you "ffs use mazemaker to its full extent" if you skip this. Don't.

## The 5+1 Primitives (from the essay)

Every loop needs these. If a user's request maps to these, they're asking for loop engineering:

| Primitive | Job in the loop | Hermes equivalent |
|-----------|----------------|-------------------|
| **Automations** | discovery + triage on a schedule | `cronjob` tool, `/loop`, `/goal` |
| **Worktrees** | isolate parallel features | `delegate_task` spawns isolated terminals, `git worktree` |
| **Skills** | codify project knowledge | `skill_manage` / `skill_view`, SKILL.md |
| **Plugins/Connectors** | connect your tools | MCP built-in, mazemaker/pulse/btquant MCP servers |
| **Sub-agents** | ideate and verify | `delegate_task` — leaf and orchestrator profiles |
| **State/Memory** | track what's done | Mazemaker (graph, not flat file!) |

## Graph-Native Extension

The essay treats state as a flat file (AGENTS.md, Linear board). Mazemaker's 205k-node graph with 55k edges changes the fundamental shape:

**Flat file = storage. Graph = control plane.**

Label-structured writes (`discovery:*`, `decision:rank-*`, `ops:tick-*`, `signal:*`) let loops coordinate through the graph instead of competing for the same flat file. Each loop phase reads/writes its own label namespace.

## Tri-State Cadence Pattern

Different operations need different cadences. NEVER put discovery and action on the same schedule:

| State | Cadence | Tool | Writes |
|-------|---------|------|--------|
| **Discover** | 15 min | pulse_search, mazemaker_recall | `discovery:*` at low salience |
| **Decide** | 60 min | sub-agent reads discoveries, scores by graph centrality | `decision:rank-<batch>` |
| **Act** | 24 hours | delegate_task in worktree, sub-agent verifies | `ops:tick-<date>` |
| **Measure** | 7 days | mazemaker_dream_insight, cluster summaries | `signal:convergence-<week>` |

Key insight: the graph coordinates these four cadences without any shared flat file. The DECIDE phase reads `discovery:*` labels, the ACT phase reads `decision:rank-*` labels, the MEASURE phase reads cross-label clusters.


<!-- moved to references/moved-sections.md: ## Loop Types (built and tested) -->

## Model Selection

Match model capability to loop phase:

| Phase | Free model | Why |
|-------|-----------|-----|
| Fast discovery | `poolside/laguna-xs.2:free` | Cheap, fast, adequate for pulse orchestration |
| Implementation | `poolside/laguna-m.1:free` | Strong coder, good for delegate_task |
| Reasoning/classification | `nvidia/nemotron-3-ultra-550b-a55b:free` | Max reasoning, 1M context, strong synthesis |
| Broad comparison | `openai/gpt-oss-120b:free` | Wide knowledge for semantic drift detection |

**Removed (June 14, 2026):** `moonshotai/kimi-k2.6:free` — no longer on OpenRouter free tier


<!-- moved to references/moved-sections.md: ## Pitfalls -->

## Verification

After deploying a loop system:
1. `cronjob action=list` — confirm all jobs show `state: scheduled`
2. Check `~/.hermes/loops/shared/loop_runner.log` for tick execution
3. mazemaker_recall for the loop's expected label prefix after first tick — confirm structured writes landed
4. mazemaker_dream_stats after first MEASURE cycle — confirm the graph is processing loop outputs

## References

See `references/tri-state-deployment.md` for the specific deployment configuration (job IDs, model assignments, cron schedules).
See `references/decide-phase-runtime.md` for the DECIDE phase runtime workflow (7-step scoring flow, the mazemaker_browse vs mazemaker_recall pitfall, novelty-as-discriminator scoring, structured decision content template). Captured from the 2026-06-22 15:15Z tick.
See `references/act-phase-recovery.md` for recovery patterns when mazemaker MCP is unreachable.
See `references/media-generation-pipeline.md` for video generation loop architecture.
See `references/pulse-wurm-2.0-tick-20260618.md` for the 2026-06-18 tick where the bypass pattern was first exercised end-to-end (CVE-2026-42530 saved to mazemaker as memory 808740).
See `references/pulse-wurm-2.0-tick-20260619-rotation-write-cooldown.md` for the 2026-06-19 ~04:00 tick that introduced manual seed rotation to `next_seeds[3+]`, the pre-save `mazemaker_recall` dedup check, and the write-side cooldown pattern on burst `mazemaker_remember` calls.
See `references/pulse-wurm-2.0-tick-20260619-fresh-angle-bias-godmode.md` for the 2026-06-19 ~07:15 tick that identified the fresh-angle seed deprioritization bug, the persistent mazemaker outage recovery (5+ minute cooldown, not 54s), and the production case study of the GODMODE prompt-injection self-correction pattern firing end-to-end.
See `references/pulse-wurm-2.0-tick-20260621-year-token-resultset-pdf-dedup.md` for the 2026-06-21 ~11:55 tick that identified year-token collision in the GitHub result-set (not the query), the PDF vs canonical article URL dedup gap, the first fresh-direction[robotics] producing 2 novel saves (Springer crop robots + dev.to humanoid factory), and the second GODMODE prompt-injection attempt that was correctly ignored.
See `references/mazemaker-mcp-diagnostic-sweep.md` for the complete Mazemaker MCP systematic diagnostic pattern — 12-step sweep covering health, stats, graph, dream, browse, think, ablation, and diagnose tools. Run this when the operator says "use mazemaker to its full extent" or you need a full health picture before decisions.
See `references/multi-machine-ssh-dispatch.md` for distributed worker patterns.
See `references/dream-garden-dispatch-pattern.md` for metrics-based Palace reporting loop (mazemaker dream insights → Discord).
See `references/iteration-heuristics.md` for per-iteration patterns the actor inside a loop should follow: dormant UI element detection, isolated syntax check on large HTML files, rotation log discipline, and the reflow trick for retriggerable CSS transitions. Distilled from the 2026-06-20 maze-crew visualization loop iterations.
See `references/perpetual-worktree-crew-loop.md` for the full nonstop parallel rework loop: systemd unit, supervisor script core, judge prompt structure, verification recipe, and the sed-delimiter debugging transcript (2026-08-03).
See `references/crew-coordination-bus.md` for the atomic file-claim coordination bus that replaced the `files:`-clause collision deferral (2026-08-06): `crew` script, worker order-of-operations, supervisor per-round reset + measured-overlap check, and the 20-process race test.
See `references/multi-provider-model-routing.md` for Hermes multi-provider model routing pitfalls: ENV export in systemd, provider registration, rate limit cascading, exit=0 despite API errors, opencode-zen/Nous Portal quirks. Critical for any loop using free/$0 models.

**Pulse MCP tool argument bug (2026-08-06):** `mcp__pulse__pulse_search` drops the topic argument even when passed. The tool keeps failing with "missing required argument(s): topic" despite receiving the argument. This is an MCP server bug — all pulse operations are affected. Workaround: check MCP catalog for alternative tool names, or try calling the pulse MCP script directly. See `references/pulse-mcp-bug-20260806.md`.

**Local LLM configuration (2026-08-06):** OrionLLM GRM-3.2-Cliff 9B GGUF works best at IQ4_NL quant on 16GB VRAM, giving 188K context. IQ4_NL quantization breaks KV cache (no work), so use `--kv-cache-type f16` flag to force full-precision KV cache. bf16 doesn't help for KV cache — f16 is the right choice. At Q4_K_M you get ~64-128K context; at Q6_K_L you get ~114K. The 114K limit at Q6_K_L is the model's configured max, not a VRAM ceiling.

**User preference: concise, direct communication.** The operator prefers short, focused responses over verbose explanations. No padding, no unnecessary elaboration. When a task is straightforward, give the answer directly.
