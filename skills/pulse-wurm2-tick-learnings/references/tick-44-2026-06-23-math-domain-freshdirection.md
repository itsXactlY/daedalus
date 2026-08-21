# Tick 44 — 2026-06-23 — math domain fresh-direction breakthrough

## TL;DR

5 mazemaker discoveries persisted (IDs 826702–826706). 3 fresh-direction math papers + 2 continue-phase ChatGPT academic papers. The `math` domain (count=0 in last 50 mazemaker memories) was opened for the first time in Pulse-Wurm 2.0 history.

## Key learnings (apply to every tick from now on)

### 1. **`pulse_tick.py` STUB-BYPASS** — `python3 ~/.hermes/loops/pulse-wurm2/pulse_tick.py` is unreliable for actual discovery

The `pulse_tick.py` script has a STUB `pulse_search_mcp` function (lines 108–130) that:
- Prints `[MCP] pulse_search_mcp stub called for: <query>`
- Returns `[]` always
- Has a `TODO` comment saying the real MCP call needs to be wired in

Running the script produces 0 discoveries per tick and increments `consecutive_empty` even though the real MCP works.

**Workaround pattern** (use this every tick until pulse_search_mcp is wired):
1. Skip `python3 ~/.hermes/loops/pulse-wurm2/pulse_tick.py`
2. Read pulse_state.json directly (`json.load`) to get next_seeds, visited_urls, saturation
3. Call `mcp__pulse__pulse_search` directly per the cron preamble §1–§6
4. Update pulse_state.json directly with `json.dump` after persisting discoveries

### 2. **Stub-tick state corruption pattern**

The stub-script wrote `consecutive_empty: 0 → 1` to disk at 07:00. The real-MCP tick at 07:12 then overrode with `consecutive_empty: 1 → 0` (reset by ChatGPT 2-save). Net effect: state was correct AFTER the real tick. If the real tick had been all-noise, the stub's increment would have fired the 3-consecutive-empty rotation trigger prematurely.

**Lesson**: Always overwritestate.json with corrected values from the real tick, even if it conflicts with the stub's earlier save. The real tick is authoritative.

### 3. **Math domain fresh-direction success pattern**

- mazemaker browse returned `math: count=0` (lowest of 24-domain-pool)
- Alphabetically-first under-represented NOT in next_seeds[:5] → math wins
- Seed: `math frontier research 2026` (literal §6a formula)
- `pulse_search(depth='quick', llm_filter=true)` returned 10/15 LLM-kept
- 3 SUBSTANTIVE FRESH 2026 academic papers saved (arxiv 2606.10799 + zenodo Zeta Zoo FST + arxiv 2606.05080 AutoLab)
- All 3 had `local_relevance >= 0.13` AND `freshness > 30` AND were open-access OpenAlex/Zenodo records

**Replicable template**: For ANY low-coverage domain (count ≤ 1 in last 50), the literal `"<domain> frontier research 2026"` seed is productive because:
- arXiv/OpenAlex subqueries return substantive academic papers
- "frontier research" is broad enough to capture multiple sub-angles
- 2026 anchor filters to in-window papers

### 4. **items_by_source mining pattern (academic papers)**

LLM-filter (`llm_filter=true`) frequently DROPS fresh academic papers as off-topic, but `items_by_source` retains them with full relevance metadata.

Concrete examples this tick (ChatGPT seed):
- LLM-filter kept 6/15, all from reddit/lobsters (off-topic social)
- items_by_source had 6 SUBSTANTIVE 2026 academic papers (loc 0.094–0.155, fresh 3–80)
- 2 of those (nature.com African universities + Liberty University workplace) saved with salience 0.4

**Action**: After pulse_search, ALWAYS check items_by_source for fresh academic papers at loc >= 0.1 even when LLM-filter dropped them.

### 5. **Cluster-bloat §26 — 3-separate-saves pattern**

When 3 academic papers in the same fresh-direction seed have DISTINCT sub-angles, save them as 3 separate mazemaker memories rather than consolidating. Examples from this tick:
- arxiv 2606.10799: LLM-tool-for-math (proof verification)
- zenodo Zeta Zoo: pure-math theory (Functional Stability Theory)
- arxiv 2606.05080: AI-research benchmark (AutoLab)

These are 3 different sub-angles → 3 separate saves (IDs 826702, 826703, 826704). Past log precedent: tick 41 Anthropic Mythos cluster (2 separate saves), tick 43 bio-health (2 separate saves).

### 6. **High-citation fresh paper pattern (zenodo FST 16 citations in 10 days)**

The zenodo Zeta Zoo paper had **16 citations in 10 days** — unusually high velocity for a pure-math preprint. This is the kind of signal that future ticks should mine: papers with citation counts > 10 within their first 2 weeks are breakthrough candidates.

## State changes this tick

- visited_urls: 5,264 → 5,294 (+30)
- consecutive_empty: 1 → 0 (ChatGPT cluster 2-save reset)
- saturation_scores:
  - ChatGPT market share: 0 → 0.6 (+0.6 high-value mixed per §51)
  - math frontier research 2026: 0 → 1 (initialized per §6d fresh-direction first-tick)
  - ASML + Mythos SEC Form D: unchanged at 0 (2nd consecutive 0-novel — bump to 5 will fire if next tick is also 0)
- next_seeds rotated to 5 lowest-saturation deduplicated: ASML / Mythos SEC Form D / bio-health / robotics / Anthropic Mythos $965B valuation
- channel_stats.mcp_channel += 4 (3 continue + 1 fresh-direction)

## Pitfalls confirmed

- **PITFALL #250** (Ti-cluster arxiv noise): appeared in ASML + Mythos SEC Form D + math seeds (NLTE Ti~I + MultiQG-TI + 3M-TI + Ti/Zr/Ti + Tied Links + Harmonic-to-anharmonic TI + Tied Monoids)
- **PITFALL #250** (lobsters programming noise): ASML seed (Wigglegram + Chesterton + Drawing Tablet + Codeberg + Nix relocatable + p99 autocomplete)
- **PITFALL #24** (single-timeout): no timeouts this tick
- **PITFALL #NEW (proposed)** (pulse_tick.py stub-script returns []): see section 1 above

## mazemaker IDs

| ID | URL | Phase | Salience |
|---|---|---|---|
| 826702 | arxiv.org/pdf/2606.10799 (Yifeng Sun, LLM math-proof verification) | fresh-direction math | 0.5 |
| 826703 | doi.org/10.5281/zenodo.19673226 (Zeta Zoo FST, Lukas Geiger) | fresh-direction math | 0.5 |
| 826704 | arxiv.org/pdf/2606.05080 (AutoLab, Zhangchen Xu et al.) | fresh-direction math | 0.5 |
| 826705 | nature.com/articles/s41599-026-07713-y (ChatGPT African universities) | continue ChatGPT | 0.4 |
| 826706 | digitalcommons.liberty.edu/9671 (ChatGPT workplace acceptance) | continue ChatGPT | 0.4 |

## Next-tick priorities

1. **ASML** (sat=0.0) — 2nd consecutive 0-novel. Bump to sat=5 if next tick is also 0-novel.
2. **Mythos SEC Form D $65B raise** (sat=0.0) — 2nd consecutive 0-novel. Same trigger.
3. **bio-health frontier research** (sat=0.0) — last productive in tick 43. Try reformulated: `"GLP-1 receptor agonist 2026 clinical trial semaglutide tirzepatide retatrutide obesity"`.
4. **robotics frontier research** (sat=0.0) — never processed. Candidate for fresh-direction phase.
5. **math frontier research 2026** (sat=1.0) — follow-up seed: `"Lean 4 mathlib proof 2026 IMO Putnam formal verification"` or `"FrontierMath open problems benchmark 2026 Epoch AI"`.