# Fresh-Direction Picker — Spec for Permanent Pulse-Wurm Diversification

**Status**: Active 2026-06-21. Operator-decreed pattern; runs on EVERY pulse-wurm cron tick, independent of continue-on-findings work.

**Trigger**: Any agent running a pulse-wurm cron tick (pulse-wurm-2 `f908a03e5655` or pulse-wurm-everything `d60932b331b4`) MUST execute this picker AFTER the standard continue-on-findings phase. The fresh-direction phase is not a diagnostic — it is a permanent, parallel, independent dig.

## Why this exists

The earlier playbook had only REACTIVE patterns that fired after saturation was detected:

- **Fresh-Angle Test** (same cluster, new angle) — only when 3 saturated seeds all return 0
- **Fresh-Cluster Pivot** (different cluster entirely) — only when the same-cluster angle also fails
- **Rotation pool** (script's hard-coded fallback) — only when `consecutive_empty >= 3`

By the time saturation is detected, the loop has been mining the same cluster for hours and the unexplored domain space keeps shrinking. The operator's preference (2026-06-21 decree): the loop must reach into one unseen direction EVERY tick, regardless of saturation status. The continue-on-findings work and the fresh-direction work run in parallel.

## The algorithm (deterministic, agent-agnostic)

**Input**: a `mazemaker` corpus with `discovery:pulse-wurm-*` memories.

**Steps**:

1. **Domain pool** (24 entries, fixed):
   ```
   AI/ML, open-source, security, science, programming, hardware,
   crypto-blockchain, bio-health, space, physics, math, robotics,
   legal, finance, energy, climate, philosophy, history,
   geopolitics, music-art, gaming, education, startups,
   infrastructure-systems-design
   ```

2. **Recall recent discoveries**:
   ```python
   recent = mazemaker_recall(query='discovery:pulse-wurm-*', limit=50)
   recent_topics = [m['content'][:200] for m in recent]  # first 200 chars each
   ```

3. **Keyword-map each topic to a domain** (substring match, case-insensitive):
   ```
   AI/ML        → {agent, llm, model, ai, ml, neural, gpt, claude, gemini, transformer}
   security     → {attack, defense, vuln, cve, exploit, sandbox, malware, redteam}
   bio-health   → {biology, protein, genomic, medical, health, disease, drug, clinical}
   space        → {spacex, nasa, satellite, orbit, launch, starlink, asteroid}
   physics      → {quantum, particle, nuclear, relativity, condensed matter}
   math         → {topology, algebra, manifold, category theory, monoid}
   robotics     → {robot, manipulation, locomotion, humanoid, actuator}
   crypto-blockchain → {bitcoin, ethereum, defi, nft, token, blockchain, layer2}
   hardware     → {gpu, tpu, chip, asic, fpga, semiconductor, lithography}
   programming  → {compiler, language, runtime, type system, garbage collect}
   open-source  → {github, repo, library, framework, dependency, license}
   science      → {experiment, observation, dataset, paper, peer review}
   legal        → {court, ruling, regulation, lawsuit, compliance, liability}
   finance      → {market, trading, earnings, valuation, hedge, fund, etf}
   energy       → {solar, wind, fusion, fission, battery, grid, hydrogen}
   climate      → {emissions, warming, carbon, ice, sea level, methane}
   philosophy   → {consciousness, ethics, epistemology, mind, value}
   history      → {archaeology, archive, primary source, manuscript, era}
   geopolitics  → {sanction, treaty, alliance, conflict, sovereignty, taiwan, china}
   music-art    → {composition, album, visual, gallery, installation, exhibition}
   gaming       → {game, console, player, mechanic, indie, mmo, esports}
   education    → {curriculum, pedagogy, student, university, k-12, mooc}
   startups     → {founder, seed, series a, ipo, exit, accelerator, y combinator}
   infrastructure-systems-design → {distributed, consensus, replication, queue, cache, observability}
   ```

4. **Count domain coverage**: For each domain, count how many of the recent-50 topics map to it via the keyword set.

5. **Pick the lowest-coverage domain** that is:
   - NOT already in `state['next_seeds']` (top 5) — those are continue-on-findings candidates, not fresh
   - NOT a direct cluster-adjacent to the current productive cluster (e.g. if continue-on-findings is on agent security, fresh must NOT be on security adjacent topics)

6. **Tiebreak**: alphabetically-first under-represented domain.

7. **Generate the seed**: `<picked_domain> frontier research 2026`
   - Examples: `robotics frontier research 2026`, `geopolitics frontier research 2026`, `energy frontier research 2026`, `philosophy frontier research 2026`
   - DO NOT derive the seed text from any existing mazemaker fact/decision/discovery
   - The seed template is the SAME for every tick; what changes is which domain gets picked

8. **Execute the dig** (≤30s budget):
   ```python
   result = pulse_search(depth='quick', topic=seed, lookback_days=30)
   # unwrap: outer.result → inner.body.ranked_candidates + items_by_source
   # filter unvisited AND topical-relevance > 0.05
   # if any promising URL: pulse_dig(max_rounds=2, max_fetches=50,
   #                                  seed={"candidates": [{"url": u, "title": t}, ...]})
   ```

9. **Persist on-topic novel URLs**:
   ```python
   mazemaker_remember(
       label=f'discovery:pulse-wurm-{YYYYMMDD}_freshdir-{8charhash}',
       salience=0.5,  # higher than continue-on-findings' 0.4 — fresh > deep
       content=f"topic: {topic}\nURL: {url}\nsummary: {summary}\n"
               f"fresh_direction_seed: {seed}\npicked_domain: {domain}\n"
               f"findings: {findings}",
   )
   ```

10. **Update state** (do NOT touch `consecutive_empty`):
    ```python
    state['visited_urls'].extend([u for u in unvisited if u is on-topic or high-score-noise])
    state['discovery_topics'].append(
        f"FRESH-DIRECTION[{domain} seed='{seed}']: {K} candidates, {N} on-topic novel saved, {M} noise suppressed"
    )
    if novel_count > 0:
        state['saturation_scores'][seed] = 1
    # else: leave at 0 so next tick re-tries
    ```

## Salience semantics

- `0.4` = continue-on-findings (deepens an existing cluster)
- `0.5` = fresh-direction (expands the graph into a new domain)

This salience split is how DECIDE/MEASURE phases can distinguish "the loop is deepening what it has" from "the loop is reaching into new territory". When tri-state-measure computes comprehension drift, it can weight fresh-direction discoveries higher because they have a higher marginal value for corpus coverage.

## State isolation principle

The fresh-direction phase does NOT touch:

- `state['consecutive_empty']` — saturation tracking stays clean per phase
- `state['next_seeds']` (top 5) — those are the continue-on-findings candidates; fresh-direction picks explicitly EXCLUDE them

The fresh-direction phase DOES touch:

- `state['visited_urls']` — append on-topic + high-score-noise URLs (suppress resurface)
- `state['discovery_topics']` — append narrative with `FRESH-DIRECTION[<domain>]: ...` prefix
- `state['saturation_scores']` — init `<seed>` to 1 (or 0 if no novel)

## Failure modes to avoid

1. **Don't pick a domain adjacent to the current productive cluster** — even if keyword coverage is low, cluster adjacency pollutes the fresh-direction. Sanity-check the picked domain against the most recent 3 tick narratives.

2. **Don't pick "AI/ML" as a default fallback** — AI/ML is almost always the highest-coverage domain. The picker MUST find a lower-coverage domain. If every domain has ≥3 mentions, the corpus is genuinely saturated — write a tick note saying so, but still pick the lowest.

3. **Don't skip the fresh-direction phase because continue-on-findings already yielded**. The operator explicitly wants BOTH every tick.

4. **Don't derive the seed from any existing memory** — fresh direction means fresh. The seed template is fixed; only the domain picker varies.

5. **Don't exceed 30s** on the fresh-direction phase. pulse_search is 5-15s; pulse_dig is 10-20s. Total ≤30s. If pulse_search times out, skip persistence and move on — the continue-on-findings work still stands.

## Verification

After implementing, verify by:
- Loading `pulse_state.json` after a few ticks — `discovery_topics` should show `FRESH-DIRECTION[<domain> seed='<seed>']: K candidates, N on-topic novel saved, M noise suppressed` narratives
- Running `mazemaker_recall(query='discovery:pulse-wurm-..._freshdir-', limit=20)` — should return discoveries with salience 0.5 and varied domains
- Checking that the 24-domain pool is hit at least once each over a week of `*/15` ticks (assuming normal saturation patterns)

## Companion docs

- `cron-tick-playbook.md` "Mandatory Fresh-Direction Dig — Runs Every Tick (2026-06-21)" section — the in-context playbook version
- Memory id 825291 — `decision:pulse-wurm-fresh-direction-mandatory-2026-06-21` — the original decision record
- Cronjob prompts:
  - `pulse-wurm-2` (id `f908a03e5655`) — Step 6 in the prompt
  - `pulse-wurm-everything` (id `d60932b331b4`) — PHASE B in the prompt
