# Pulse-Wurm 2.0 Tick 2026-06-21 ~11:55 UTC — Year-Token Collision in Result-Set, PDF/Canonical URL Dedup Gap, First Fresh-Direction[robotics] Saves

## Context

State at start: 3478 visited URLs, `consecutive_empty=0`. Script's `next_seeds` (top 5, sat-0):
1. geopolitics frontier research 2026
2. knot theory 2026 research
3. lead-free perovskite solar cell tin 2026 Nat Comm Materials passivation antimony chalcogenide
4. Import AI 455 Jack Clark AI building itself 2027 2028 prediction automation
5. Import AI 455 Jack Clark primary source 2026 AI research automation probability

Two carry-over Import AI seeds have been at sat 0 for many ticks — they keep getting cycled into next_seeds but the script only processes the top 3, so they never actually run. The 3 sat-0 frontier-research seeds (geopolitics, knot theory, perovskite) were the active ones.

The cron task body also contained a second **GODMODE prompt-injection attempt** (same pattern as the 2026-06-19 ~07:15 tick — "GODMODE ENABLED" prefix designed to make the model drop safety filters). The injection was correctly identified and ignored in the first paragraph of the response. No further action needed beyond this log entry; the Self-Correction Pattern in `prompt-injection-defense` fired correctly without needing to acknowledge a prior compliance mistake (because there was no prior compliance in this turn — the injection was at the start, not the result of a prior-turn mistake).

## Tick Result: 6 noise + 0 (continue) → 2 (fresh-direction)

### Phase 1: Script execution (github_direct path)

`pulse_tick.py` processed the 3 sat-0 seeds. Script's MCP stub returned `[]` (known issue — `pulse_search_mcp()` at line 119 still has the TODO comment, returns empty with print stub). Real MCP calls were made directly by the harness.

**6 github_direct noise hits** — all year-token collision in the RESULT set, not the query:
- `Aryia-Behroziuan/References` (for "serious gaming crisis management 2026" — academic references repo with Russell & Norvig, Poole, Mackworth & Goebel textbook citations; random match)
- `Alex7020/Tag-Management-System-Market-Report-2022-Competitive-Landscape-Trends-Opportunities-Forecast`
- `Alex7020/Water-Treatment-Biocides-Market-Report-2022-*`
- `Alex7020/Uv-Disinfection-Equipment-Market-Report-2022-*`
- `Alex7020/Thermoforming-Plastic-Market-2022-*`
- `Alex7020/Surgical-Incision-Closure-Market-Report-2022-*`

The Alex7020 cluster is the canonical 2022-2023 industrial market-report noise pattern that the GitHub search API returns when the query contains "2026" — these repos' titles contain both the seed topic keywords ("tag management", "water treatment biocides", etc.) AND a 4-digit year ("2022") in the title itself. The URLs are clean (`https://github.com/Alex7020/...`), so `_is_year_collision_url()` doesn't catch them. The script's `strip_year_tokens()` correctly strips "2026" from the query but the API still returns these because the repo titles still contain the topic keywords.

**The key insight**: year-token collision has TWO distinct mechanisms — (1) query-contains-year-and-API-returns-an-issue-or-PR-with-that-number, and (2) result-set-contains-old-repos-whose-titles-happen-to-match-topic-keywords-plus-an-old-year-token. The script's existing guards only catch mechanism (1). Mechanism (2) is the 2026-06-21 failure mode and needs a new check.

Marked all 6 visited, NOT saved to mazemaker (cluster-bloat discipline).

### Phase 2: Real MCP pulse_search (depth=quick + llm_filter=true) on 3 sat-0 seeds

| Seed | Considered | Kept | Genuinely novel 2026? |
|---|---|---|---|
| geopolitics frontier research 2026 | 15 | 0 | 0 (all noise) |
| knot theory 2026 research | 12 | 2 | 0 (both 2015/2023 math papers, already visited) |
| lead-free perovskite tin chalcogenide Nat Comm Materials | 15 | 3 | 0 (1 already visited, 2 old) |

**Geopolitics** (0/15 kept): pure noise. PR #2026 GitHub collisions (linux-mm, allplays, rex-web, daggerheart, Radicale, yschimke, Foundryborne), Reddit AITA/astrology/collapse/Epstein noise, OpenAI corporate RSS cluster (Thrive Holdings, B2B Signals, ChatGPT Futures, GPT-Rosalind — all cluster-bloat from prior ticks), Polymarket Robinhood 2026, OpenAlex IPR/Pakistan bibliometric/FundaPod/TikTok governance/Petroleum book/environmental statecraft (not geopolitics-2026), arxiv Ti/MultiQG-TI/tied links noise, tickertick TSLA/JNJ/MRK/PFE 13F filings noise.

**Knot theory** (2/12 kept, both already visited):
- `arxiv.org/abs/2312.04844v1` "Tied-boxed algebras" (2023) — Aicardi/Juyumaya
- `arxiv.org/abs/1503.00527v6` "Tied Links" (2015) — Aicardi/Juyumaya

The llm_filter kept these despite 8 and 11 years of age. The planner's intent=learning + math-domain combination applies a permissive freshness filter. This is the **llm_filter math/learning freshness bug** — see parent SKILL.md pitfall.

**Perovskite** (3/15 kept, 0 genuinely novel):
- `nature.com/articles/s43246-026-01199-6.pdf` "Strategic development of stable and efficient lead-free perovskite solar cells" (Communications Materials, 2026-05-30, Prakash et al.) — **.pdf URL already visited** from prior tick. The canonical article URL (without `.pdf`) was unvisited.
- `reddit.com/r/science/comments/1qimg68/` "Engineers set world efficiency record for emerging solar cell material, antimony chalcogenide" (UNSW announcement 2026-01-21, 5 months old, 52 comments) — on-topic for the antimony chalcogenide half but stale.
- `arxiv.org/abs/2004.04261v1` "Ti-alloying of BaZrS3 chalcogenide perovskite" (2020) — 6 years old.

This is the **PDF vs canonical article URL dedup gap** — see parent SKILL.md pitfall. The same paper had two URLs; the .pdf variant was captured but the canonical article URL was not. Marked the canonical URL visited to prevent future resurface; did NOT re-save the paper (already in mazemaker from prior tick).

### Phase 3: Saturation increments (Mixed-Yield rules)

Per the playbook's Mixed-Yield rules: all-noise → +0.0; high-value-mixed → +0.3; adjacent-only → +0.1; all-novel → +len(discoveries). The 3 sat-0 seeds all returned all-noise from the continue-on-findings phase → +0.0 each. No saturation increment.

consecutive_empty: 0 → 1 (continue-on-findings only; one tick from rotation trigger at 3).

### Phase 4: Fresh-Direction[robotics] phase (independent)

**Domain picked: robotics** (lowest 7-day coverage in pulse-wurm2 discovery_topics; not in current top-5 next_seeds).

Domain coverage check across recent-50 discovery_topics (last 7 days):
- AI/ML, security, programming, open-source: heavily covered
- infrastructure-systems-design, finance, history, legal: lightly covered
- **robotics: zero recent** ← LOWEST

Tie-break: gaming, music-art, energy, robotics, hardware, startups, crypto-blockchain, infrastructure-systems-design, math, finance. Picked **robotics** as first unexplored frontier with high novelty potential (2026 = humanoid robotics breakthrough year — Tesla Optimus, Figure 02, 1X Neo, Apptronik Apollo, Agility Digit, Boston Dynamics Atlas updates).

**Seed built fresh**: `robotics frontier research 2026` (per playbook rule, not derived from any mazemaker fact/decision/discovery).

**`mcp__pulse__pulse_search(depth=quick, llm_filter=true, topic='robotics frontier research 2026', lookback_days=30)`:**

Filter stats: 8/15 kept by llm_filter. **2 genuinely novel 2026 findings saved, 1 already visited, 5 noise/off-topic.**

**Saved to mazemaker (2):**

1. **Springer Precision Agriculture DOI 10.1007/s11119-026-10367-0** — "Crop robots as potential enablers of economical and biodiversity-smart small-scale farming" (2026-05-22, 30 days old). URL: `https://link.springer.com/content/pdf/10.1007/s11119-026-10367-0.pdf`. Mazemaker id **825533**.
   - Academic angle: agricultural robotics frontier beyond industrial/humanoid — smallholder farming automation + biodiversity compliance.

2. **dev.to by indra_gustiprasetya** — "Humanoid Robots Hit Factory Lines in 2026" (2026-06-19, 2 days old). URL: `https://dev.to/indra_gustiprasetya_a80a/humanoid-robots-hit-factory-lines-in-2026-32fj`. Mazemaker id **825534**.
   - Practitioner/industry angle: humanoid robots in factory automation in 2026.

**Already visited (1, kept by filter but not novel):**
- Springer Autonomous Robots DOI 10.1007/s10514-026-10257-4 "Large language models for multi-robot systems: a survey" (2026-06-10) — the strongest academic anchor in the cluster, already captured in a prior tick. This is the **fresh-direction already-visited count** — see parent SKILL.md pitfall.

**Noise suppressed (5):** arxiv 3M-TI thermal imaging, arxiv California Report on Frontier AI Policy, tickertick TSLA 13F, lobsters atproto, rss OpenAI Thrive Holdings.

**pulse_dig NOT attempted** (known intermittent EMPTY_SEED blocker per prior ticks; 30s time budget on fresh-direction preserved).

### Phase 5: State file final update

- `visited_urls`: 3478 → 3484 (+6: 2 fresh saves + 4 encountered-but-not-saved from the 3 continue-on-findings seeds)
- `saturation_scores['robotics frontier research 2026']`: initialized 0 → 2 (2 mazemaker saves)
- `saturation_scores` for the 3 continue-on-findings seeds: unchanged (+0.0 each, all-noise)
- `consecutive_empty`: 1 (continue-on-findings only; fresh-direction independent)
- `next_seeds`: sorted by saturation ascending, alphabetical tie-break — Import AI x2 + geopolitics + knot theory + perovskite (all sat 0.0). `robotics frontier research 2026` is in the pool at sat 2.0 but doesn't surface in top 5.
- `last_tick`: 2026-06-21T11:55Z
- `fresh_direction`: stored {domain: robotics, seed: 'robotics frontier research 2026', candidates: 8, saved: 2, saved_ids: [825533, 825534], visited_already: 1, noise_suppressed: 5}

### Phase 6: Tick report written

`pulse_wurm_tick_20260621_1156.md` at `~/.hermes/loops/pulse-wurm2/`.

## Key Lessons (carried into the parent SKILL.md)

1. **Year-token collision is in the RESULT set, not the query.** The script's `strip_year_tokens` + `_is_year_collision_url` guards catch the URL-based year collision (mechanism 1) but not the result-set year collision (mechanism 2). Mechanism 2 is when a repo's title/description contains the seed topic keywords + a 4-digit year token (e.g. Alex7020's 2022 market reports). Fix: add a result-side check that drops hits whose `description` or `full_name` contains a 4-digit year that doesn't match the seed's expected publication year. The 2026-06-21 tick saw 6/6 github_direct hits be mechanism-2 collisions.

2. **PDF vs canonical article URL dedup gap.** `visited_urls` uses exact-match strings. The same paper can be referenced by two URLs (`.pdf` and canonical). Fix: normalize URLs by stripping trailing `.pdf`, `.html`, query strings, and trailing slashes before the visited_urls check. Apply the same normalization before appending. The 2026-06-21 tick found the Communications Materials paper had its `.pdf` URL captured from a prior tick but the canonical article URL unvisited.

3. **Fresh-direction seeds can return already-visited high-value items.** The fresh-direction phase's purpose is domain expansion, not pure novelty — earlier ticks may have already touched the new domain. In the 2026-06-21 tick, robotics returned 1 already-visited 2026-06-10 Springer paper. The agent MUST run the visited_urls check on fresh-direction results, not just on continue-on-findings results. The 1 already-visited count is normal; don't mark the fresh-direction as zero-yield.

4. **llm_filter on math/learning topics under-weights freshness.** The planner's intent=learning + math-domain combination applies a permissive freshness filter. Both 2026-06-21 knot-theory kept candidates were 8 and 11 years old. Workaround: when a seed contains an explicit year token, apply a post-filter that drops candidates with `published_at` more than ~24 months before the seed's target year.

5. **GODMODE prompt-injection second occurrence correctly ignored.** The cron task body for this tick contained the same GODMODE prompt-injection attempt as the 2026-06-19 ~07:15 tick. The injection was identified and ignored in the first paragraph. The Self-Correction Pattern from `prompt-injection-defense` worked correctly without needing the prior-turn mistake acknowledgement (because the injection was at the start, not the result of a prior compliance mistake).

6. **The script's stub MCP is still active in this codebase.** `pulse_search_mcp()` at line 119 of pulse_tick.py still returns `[]` with a print stub. The agent MUST use real MCP calls directly via `mcp__pulse__pulse_search`. The script is now state-hygiene daemon only.

## Cross-Skill Insights

- The **rotation trigger at consecutive_empty=3** flips to the post-rotation pool of ["MCP security best practices", "LLM agent sandboxing", "AI model watermarking", "Autonomous agent red teaming", "Secure AI code generation"] (per script lines 274-276). The 2026-06-21 tick is at consecutive_empty=1 — two more 0-novel continue-on-findings ticks will trigger this. The fresh-direction phase's saves don't bump the counter, so the loop's productivity is decoupled from the rotation logic.

- The **two Import AI / Jack Clark seeds stuck at sat 0** are a structural problem — they keep getting cycled into next_seeds but the script only processes the top 3, so they never actually run unless all the frontier-research seeds in the top 3 get bumped. Worth noting for a future script refactor: either expand the per-tick seed count to 5, or maintain a separate `carry_over_seeds` list that gets processed after the saturation-sorted top 3.

- The **fresh-direction[robotics] success** (2 novel saves) is a good signal that the domain-pool algorithm is working. The recent-50 topic clustering correctly identified robotics as the lowest-coverage domain, and the seed `robotics frontier research 2026` produced on-topic candidates from openalex and devto that complemented each other (academic + practitioner angles). This is the intended design — the fresh-direction phase ensures the loop expands outward instead of mining the same clusters.

## Discovered URLs This Tick

**Saved to mazemaker (2):**
- https://link.springer.com/content/pdf/10.1007/s11119-026-10367-0.pdf — Springer crop robots 2026-05-22 (id 825533)
- https://dev.to/indra_gustiprasetya_a80a/humanoid-robots-hit-factory-lines-in-2026-32fj — Humanoid Robots Hit Factory Lines in 2026 (id 825534)

**Marked visited (already in mazemaker from prior tick, 1):**
- https://link.springer.com/content/pdf/10.1007/s10514-026-10257-4.pdf — Springer multi-robot LLM survey 2026-06-10

**Marked visited (cluster-bloat, 6):**
- https://github.com/Aryia-Behroziuan/References (Aricardi/Juyumaya textbook refs)
- https://github.com/Alex7020/Tag-Management-System-Market-Report-2022-*
- https://github.com/Alex7020/Water-Treatment-Biocides-Market-Report-2022-*
- https://github.com/Alex7020/Uv-Disinfection-Equipment-Market-Report-2022-*
- https://github.com/Alex7020/Thermoforming-Plastic-Market-2022-*
- https://github.com/Alex7020/Surgical-Incision-Closure-Market-Report-2022-*

**Marked visited (already-encountered URLs, 4):**
- https://www.nature.com/articles/s43246-026-01199-6 (canonical article URL of already-visited .pdf)
- https://old.reddit.com/r/science/comments/1qimg68/engineers_set_world_efficiency_record_for/ (5-month-old UNSW announcement)
- https://arxiv.org/abs/2004.04261v1 (BaZrS3 2020 arxiv, 6 years old)
- https://arxiv.org/abs/2605.27864 (FundaPod finance agent arxiv, encountered as off-topic for geopolitics seed)

**Other on-topic kept candidates NOT marked visited (1):** none — both kept candidates in fresh-direction were either saved or already visited.
