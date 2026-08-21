# Fresh-Direction Discovery Patterns — Updated 2026-06-22

Distilled from running the 6-hour pulse-wurm-2.0 cron tick across ~30+ fresh-direction attempts in the last 48 hours. Update this file as new patterns emerge.

## Pattern: Literal-Formula Failure Mode (PITFALL #15a, confirmed 16+ times)

**What fails:** bare `<domain> frontier research 2026` literal formula (e.g. `climate frontier research 2026`, `physics frontier research 2026`, `history frontier research 2026`, `philosophy frontier research 2026`, `energy frontier research 2026`, etc.).

**Why it fails:** The `pulse` planner's `intent` classifier tends to route abstract-academic framings to either:
- **arxiv Ti-noise cluster** (PITFALL #250): MultiQG-TI, 3M-TI, Tied Links/Monoids, NLTE Ti~I — same papers re-surface across any seed with "Ti" or "tied" in the routing path
- **"frontier" sub-channel routing bug**: arxiv returns California Frontier AI Policy 2506.17303 + Snowmass Intensity Frontier 1310.6964 + HST Frontier Fields 1605.06567 for any seed with "frontier" in it. The word "frontier" routes to the named-Frontier surveys cluster, not the abstract-frontier cluster the operator intended.
- **openalex weight too low**: when intent=person_research or news_tracking, the openalex sub-channel weight is below 0.83 and the planner doesn't fire it.

**Failed domains (16+, do not retry literal formula for these without a proper-noun bridge):**
climate, infrastructure-systems-design, legal, physics, bio-health, crypto-blockchain, energy, philosophy, history, geopolitics, robotics, finance, gaming, education, startups, science.

## Pattern: Concrete Proper-Noun Bridge (PITFALL #15a-update-2, the WORKING path)

**What works:** `<concrete proper-noun> + named-action + 2026` — e.g. `Figure 02 Apptronik Apollo 1X Technologies humanoid robot 2026 deployment` (robotics), `Steam AI game asset policy 2026 game studio union strike` (gaming), `CVE-2026 Linux kernel vulnerability disclosure Q2 2026` (security), `CFO AI playbook Indian business 2026` (finance via dev.to), `Chevron-Microsoft West Texas natural gas PPA 2026` (energy × AI), `AlphaFold 3 Isomorphic Labs Eli Lilly Novartis drug discovery 2026` (bio-health).

**Why it works:** proper-noun anchors route through named-entity sub-channels (openalex, dev.to, sem_scholar) where the planner's lexical model has higher-precision topical disambiguation. The 2026 anchor keeps freshness tight.

**Rule of thumb:** if you cannot name a specific vendor, program, paper, CVE, or named-actor in the seed, reformulate until you can. "Frontier research" + abstract domain is too generic.

## Pattern: Reddit High-Engagement Convergence (NEW 2026-06-22, energy success)

**First literal-formula SUCCESS in 16+ attempts:** `energy frontier research 2026` → 3/13 LLM-kept → 1 substantive novel save (mazemaker id 826471).

**The productive channel was REDDIT (weight 1.31 in source_weights), not arxiv.** The save was r/wallstreetbets `1tmek9l` "The Capex Unwind Thesis 2027 - 2028" (engagement 383/208, loc_rel 0.374, freshness 0) — high-engagement community analysis drawing historical analogy between AI infra capex 2026 and railroads 1880s / telecom fiber 2000. Bridges finance × energy × AI × 2026-2028 horizon.

**Generalization:** when literal formula fails on arxiv/openalex but the domain has a high-engagement reddit community, the reddit sub-channel can be productive even for non-AI/ML domains. Detection signal: reddit source_weight > 1.2 in query_plan.source_weights AND the topic is one with active community discussion (wallstreetbets for finance+energy, singularity for AI/tech, futurology for frontier-science).

**Caveat:** This is one data point. Don't over-generalize. The other 15+ domain failures showed reddit also falling to political/business-event-track cluster-bloat (PITFALL #241). The energy success likely worked because the productive post was a finance-analysis post (well-defined r/wallstreetbets genre) rather than a vague frontier-research post.

**Predictive heuristic for future literal-formula attempts:**
- If the domain has a high-engagement topical subreddit (wallstreetbets, singularity, futurology, askscience, machinelearning, sysadmin) AND the planner weights reddit > 1.2 → reddit can succeed.
- If the domain has no community (pure academic, e.g. pure mathematics, classical philology) → even reddit will not save it; pivot to proper-noun bridge immediately.

## Pattern: Financial-Event-Track Cluster-Bloat (PITFALL #241, confirmed 2026-06-22 BlackRock IBIT)

**Symptom:** Seeds like `BlackRock IBIT spot Bitcoin ETF institutional inflows 2026` or `BlackRock ETHA ETF Q1 2026 AUM inflows` return 4/15 LLM-kept candidates, all of which are crypto-news Reddit posts (r/Bitcoin, r/CryptoCurrencyTrading, r/RWATimes, r/YouHodler_Official) re-reporting market flows.

**Why this is a category mismatch:** ETF-inflow/exchange-flow/AUM-reporting seeds are financial-event-track, not research-track. The openalex/arxiv sub-channels return 0 because no academic paper tracks ETF flows. The reddit sub-channel returns the marketing/news posts, but those don't add new knowledge — they rephrase publicly available SoSoValue / 13F data.

**Detection signal:** A seed's keywords resolve to (vendor name OR ticker) + (financial-flow-event) + (year) AND no research-y signal (model name, method name, benchmark). Openalex returning 0 is the canonical signal.

**Discipline:** Mark all 6+ Reddit URLs visited only. Do not save to mazemaker. The cluster is already-saturated noise. Bump seed saturation to 4+ on first 0-novel tick to break the re-pick loop (do not wait for 3 consecutive empties — these seeds are never productive via research channels).

**Real retired seeds (bump to sat 4+):**
- `BlackRock IBIT spot Bitcoin ETF institutional inflows 2026`
- `BlackRock ETHA ETF Q1 2026 AUM inflows`
- `Microsoft Three Mile Island restart nuclear 2026 hyperscaler` (energy-event-track, not research)
- `OpenAI Stargate Michigan 1GW approval Abu Dhabi Iran threat June 2026` (event-track)

## Pattern: Carry-Over Operator-Override Saturation (NEW 2026-06-22)

**Symptom:** After multiple operator-override rotations (per §23 of cron-tick-playbook.md) where sat-0 seeds are popped and fresh sat-0 candidates rotated in, the new sat-0 pool itself becomes exhausted across 2-3 ticks but is not auto-rotated because consecutive_empty doesn't reach 3.

**Real case 2026-06-22 18:00Z tick:** next_seeds[:5] = [Microsoft TMI, BlackRock ETHA, James Hansen, BlackRock IBIT, Cursor SpaceX] — all sat=0, all exhausted in 3+ prior ticks, but rotation only triggers at consecutive_empty=3.

**Workaround:** when next_seeds is observed to have 3+ carry-over sat-0 candidates that have all been processed 2+ times with 0/15 LLM-kept in the prior 24h, manually bump them to sat=4 (next-lowest pool + 2) and rotate in fresh research-track sat-0 candidates. Don't wait for the script's hard-coded rotation trigger — it can lag 1-2 ticks behind the actual saturation.

**Recommended rotation pool when this happens:** canonical research-track seeds (MCP security best practices, LLM agent sandboxing, agent failure recovery self-correction, VLM multimodal visual prompt injection 2026, Linux kernel CVE 2026 patch rollout distro advisories). All are confirmed productive per recent cron history.

## Pattern: Cross-Domain Bridge via Named AI/ML HEAD (PITFALL #15a-update-2 variant)

**What works:** for under-represented non-AI/ML domains, prefix a concrete AI/ML term to bridge into the productive research sub-channels. Examples:
- `GPT-5 Khan Academy classroom tutor deployment K-12 student outcomes 2026` (education)
- `AlphaFold 3 Isomorphic Labs Eli Lilly Novartis drug discovery 2026` (bio-health)
- `Steam AI game asset policy 2026 game studio union strike` (gaming)
- `Figure 02 Apptronik Apollo 1X Technologies humanoid robot 2026 deployment` (robotics)

**Why it works:** the AI/ML anchor triggers openalex/sem_scholar sub-channel routing (intent=product_research or person_research) which the planner can ground against. The non-AI/ML domain content survives in items_by_source even when ranked_candidates is empty.

**When NOT to use:** when the seed is already overloaded with named-entity anchors (3+ proper nouns). The bridge becomes redundant and the noise clusters (Ti-arxiv, /pull/2026) dominate the budget.

## Decision Tree for Fresh-Direction Pick

1. If a domain has been picked in the last 7 days of state['discovery_topics'] → skip.
2. Alphabetical tie-break among the remaining un-picked domains.
3. If the picked domain is in the literal-formula failure list (16+) → use concrete proper-noun reformulation per PITFALL #15a-update-2.
4. If the picked domain is in the financial-event-track retired list → skip and pick the next alphabetical domain.
5. Build the seed and run pulse_search(depth='quick', lookback_days=30).
6. If 0/15 LLM-kept → mark visited only, leave saturation at 0, move on.
7. If 1+ on-topic novel → save to mazemaker with salience=0.5 (fresh-direction tier).

## Channel Weights Reference (from `query_plan.source_weights`)

When the productive channel for a given seed is unclear, check the source_weights dict. Heuristic:
- `reddit > 1.2` → high-engagement community content likely
- `openalex > 1.0` → academic paper content likely (rarely works for non-AI/ML)
- `arxiv > 1.0` → paper content (often Ti-noise cluster, low yield)
- `rss > 0.8` → engineering blog / OpenAI index / simonwillison / pragmaticengineer — RESCUE CHANNEL when academic sub-channels return 0
- `sem_scholar > 0.8` → academic papers via Semantic Scholar, often more selective than arxiv
- `devto > 0.8` → dev.to tutorial posts, productive for infrastructure/finance/internationalization
