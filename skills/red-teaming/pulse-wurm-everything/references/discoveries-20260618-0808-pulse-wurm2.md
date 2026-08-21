# Pulse-Wurm 2.0 Discoveries — 2026-06-18 08:08 UTC Tick

## Outcome
- **3 novel discoveries**, **7 mazemaker memories** (3 discovery + 3 fact + 1 decision, ids 361090-361099)
- consecutive_empty: 1 → 0
- visited_urls: 535 → 538 (+3)
- 7 niche seeds (arXiv-numbered topics) saturated to 10 — effectively retired from the queue

## Method (corrected from simple script)
1. Ran `pulse_tick.py` first (GitHub-only) — returned 0 across 3 niche arXiv seeds
2. Recognized the GitHub-only script is the "NOT the cron path" anti-pattern (skill pitfall 2026-06-17 23:30)
3. Routed to `mcp__pulse__pulse_search` directly with `depth='default'` (NOT `depth='deep'` per 2026-06-18 06:00 pitfall — deep also times out at 120s)
4. Applied `llm_filter=true`, `llm_filter_top_n=20`, `lookback_days=30-45`
5. Quality filter: `quality = local_relevance * 0.7 + final_score * 5`, threshold 0.05
6. Dedup against visited_urls (535 entries prior)
7. Saved top 3 to mazemaker via triple-memory pattern

## Discoveries

### 1. Hermes Agent v0.15.0 — The Velocity Release (SELF-REFERENTIAL)
- **URL:** https://old.reddit.com/r/hermesagent/comments/1tqfrgq/hermes_agent_v0150_the_velocity_release/
- **Q=0.291** (LR=0.223, FS=0.027) | **Engagement: 269 upvotes / 96 comments** | Published 2026-05-28
- **Self-referential finding:** The pulse-wurm tick searching "Fingerprinting AI coding agents" surfaced the agent's own release notes as the highest-engagement result. The agent running this tick is v0.15.0; the thread documents that v0.15.0 has been superseded by hotfix v0.15.1-2.
- **Operational implication:** Production deployments should track the hotfix series, not pin to 0.15.0. The thread references `hermes update` for upgrading.
- **Memories:** discovery 361090, fact 361095

### 2. Stack Overflow for Agents
- **URL:** https://stackoverflow.blog/2026/06/10/announcing-stack-overflow-for-agents/
- **Q=0.195** (LR=0.072, FS=0.029) | Source: lobsters (ai tag) | Published 2026-06-10
- Stack Overflow launched an agent-targeted product surface on 2026-06-10, joining GitHub (Copilot/Codex) and Hugging Face in releasing agent-first content APIs in 2025-2026.
- **Implication:** Future pulse-wurm reconnaissance will increasingly need to consume agent-targeted content APIs (rate-limited, structured) rather than scrapes of human-facing pages. SO's 2023 policy restricting LLM training access is the historical counter-context.
- **Memories:** discovery 361091, fact 361096

### 3. Warp + GPT-5.5 integration
- **URL:** https://openai.com/index/warp
- **Q=0.198** (LR=0.105, FS=0.025) | Source: openai.com RSS | Published 2026-05-27
- OpenAI announces Warp's adoption of GPT-5.5 to coordinate coding agents across local, cloud, and open-source workflows.
- **Implication:** Major commercial signal that GPT-5.5 (May 2026 release) is the new default for terminal-class coding agents. Pairs with the 05-22 Gartner Magic Quadrant leadership announcement.
- **Memories:** discovery 361092, fact 361098

## Week-Cluster Market Signal (2026-05-22 to 2026-05-28)

Three high-quality findings clustered in one week, all pointing at the same macro trend — **GPT-5.5 + OpenAI coding-agent stack consolidation**:
| Date | Discovery | Source |
|---|---|---|
| 2026-05-22 | OpenAI named Leader in Gartner Magic Quadrant for Enterprise AI Coding Agents | openai.com RSS |
| 2026-05-27 | Warp + GPT-5.5 integration announced | openai.com RSS |
| 2026-05-28 | Hermes Agent v0.15.0 (Velocity Release) | r/hermesagent |

This cluster was surfaced by ONE productive seed and the cross-references in the discovery + fact + decision memories. The decision memory (361099) explicitly captures this as a Q2 2026 action item for hermes-agent: evaluate GPT-5.5 as the terminal-class default.

## Decision Memory
**Memory 361099** (`decision:pulse-wurm-action-20260618_hermes-q2-2026`): Three action items:
1. **Track Hermes hotfix series** (low effort, immediate): Verify local installation is on v0.15.1-2
2. **Prepare for agent-content API wave** (low effort, monitor): Add discovery seed for "agent content API rate limits"
3. **Evaluate GPT-5.5 as terminal-class default** (medium effort, decide): Decide by end of Q2 2026

Cross-references: `decision:hermes-agent-isolation-2026-q3` (07:21 tick), `decision:hermes-agent-defense-2026-q2` (06-17 23:30 tick).

## Niche Seeds Saturated (effectively retired)
- Linux kernel 6.18 LTS features and changes
- Prefill awareness LLM attack surface arXiv 2606.12747
- ModSleuth LLM supply chain dependency auditing arXiv 2606.12385
- Type-error ablation AI coding agents arXiv 2606.01522
- Stagehand Anthropic $PARAMETER_NAME wrapper tool response fix
- Lean4Agent formal modeling verification agent workflow arXiv 2606.06523
- Dr-CiK foresight-driven agents testbed arXiv 2605.27904

## State Hygiene Note
The state file has a case-variant duplicate of "Fingerprinting AI coding agents" (one with "activity patterns" suffix, one without) — this is a minor hygiene issue but doesn't affect dedup. Also: two spellings of the eTAMP topic coexist in the saturation_scores (one at sat=2, one at sat=10). These were not introduced this tick; they predate it. Worth a follow-up cleanup pass.

## Files Updated This Tick
- `~/.hermes/loops/pulse-wurm2/pulse_state.json` (visited +3, saturation updated, next_seeds rotated)
- `~/.hermes/loops/pulse-wurm2/discoveries_20260618_pulse-wurm.json` (fallback with full records)
- `~/.hermes/loops/pulse-wurm2/pulse_wurm_tick_20260618_0808.md` (tick report)

## Lessons for Next Tick
1. When the lowest-saturation seeds are all niche, bump them ALL to saturation 10 after the first one fails (don't waste search slots on the rest)
2. Cluster high-engagement findings by date in the tick report and surface the macro signal
3. Self-referential discoveries (the agent's own system) are high-priority findings, not curiosities
4. The agent on v0.15.0 should consider upgrading to v0.15.1-2 hotfix series
