---
name: recent-pitfalls-2026-06-22-1708
description: Pulse-Wurm 2.0 tick 19 (2026-06-22T17:08:00Z) — PITFALLS #263-#266 discovered. PITFALL #253 PM hijack SPACE-X-SPECIFIC confirmation on Cursor/SpaceX seed (18/20 = localized PM Starship-launch pages in 18 languages; kept=101 misleading stat), PITFALL #15a-class bare-consumer-electronics domain failure for gaming (0/392 kept; only AI/ML-bridged gaming works per 826436), deep-job wall-clock threshold update (51+ min before completion is OK vs current 45-min heartbeat patience), consecutive_empty threshold problem (hardcoded at 3 was hit last tick; rotation trigger fired but next_seeds rotation didn't recover). 0 substantive saves. Load when investigating "what to do when LLM-kept>0 but ZERO on-topic candidates", "next gaming fresh-direction", "deep-job patience", or "tick 19 carry-over handling".
---

# Pulse-Wurm 2.0 Tick 19 — Recent Pitfalls (2026-06-22 17:08Z)

> **Companion:** `pulse-wurm2-stateful-tick` covers the two-phase CONTINUE + FRESH-DIRECTION workflow. `pulse-wurm2-tick-learnings` is the class-level skill with §1-§38 + this reference. Tick-19 specific pitfalls live here.

## PITFALL #263 — PITFALL #253 PM hijack SPACE-X-SPECIFIC confirmation (kept=101 misleading)

**Symptom:** Seed `'SpaceX Cursor Anysphere $60B all-stock acquisition valuation June 2026 secondary AI coding agent'` returned `kept: 101, dropped: 199, total_aggregated: 300, returned: 20`. **ZERO Cursor-related URLs in the top-20 returned.**

**Top 20 source distribution:**

| Source | Count | On-topic for Cursor? |
|--------|-------|---------------------|
| `polymarket.com/<locale>/event/how-many-spacex-starship-launches-reach-space-in-2026` | 18 (de/es/bn/hi/fr/pt/ja/zh-hant/pl/th/tl/vi/it/zh/id) | NO — pure SpaceX Starship-launch contracts |
| `youtube.com/c/SpaceX` | 1 | NO — SpaceX channel homepage |
| `discord.gg/Polymarket` | 1 | NO — invite link |

**Root cause:** "SpaceX" + "2026" trigger pulls the heavily-traded PM Starship-launch contract. The query planner never reaches the "Cursor" / "Anysphere" / "AI coding agent" semantics. All 4 worm rounds amplified the same SpaceX noise. The LLM-filter kept=101 statistic represents the post-filter pool for the SpaceX subtopic — NOT for the Cursor subtopic.

**Why "kept=101" is misleading:** The filter is judging on-topic for SpaceX (which the corpus has lots of) — not for Cursor (which the corpus may or may not have). When LLM-kept > 0 but the kept-candidate pool is on-topic for only ONE token in the original query (the dominant entity), the on-topic-for-full-query yield is still effectively 0.

**Verification heuristic (NEW):** After every pulse_search / pulse_research, scan the returned `candidates` and check whether the dominant URL pattern matches the FULL query or only PART of it. If only part matches (e.g. SpaceX yes, Cursor no), the kept count is misleading and the search has effectively failed.

**Reformulations for next attempt (drop-SpaceX-anchor pattern):**
- `'Anysphere Cursor AI coding agent valuation $30B 2026 secondary share sale'` (named-AI-product + named-event + 2026, drop "SpaceX" entirely)
- `'Cursor IPO 2026 Anysphere revenue growth'` (named-event anchor)
- `'Cursor Aman Sanger Sualeh Asif valuation 2026'` (named-person + named-AI-product)
- `'Cursor Andreessen Horowitz a16z valuation 2026'` (named-VC-backer + named-AI-product)

**Why this is distinct from PITFALL #253 (prior surfaces):** Prior #253 hijacks were on AI-model-specific markets (Claude/GPT/Gemini + date-prediction — class 1 in `polymarket-hijack-registry.md`). This is a **NON-AI MODEL** hijack: SpaceX is an aerospace company, not an AI vendor, but the `SpaceX + 2026` token combination still triggers the PM planner. **This is a new hijack class — "PM contract entity + 2026 year anchor" — even when the entity is not AI-related.** Add as PITFALL #246 in `polymarket-hijack-registry.md` (class 9: NON-AI-ENTITY + YEAR-ANCHOR).

## PITFALL #264 — PITFALL #15a-class bare-consumer-electronics domain failure (gaming 0/392)

**Symptom:** Seed `'gaming frontier research 2026 Steam Deck 2 Nintendo Switch 2 launch AMD Zen 5 handheld console'` returned `kept: 0, dropped: 392, total_aggregated: 392, returned: 0`. **LLM-filter dropped EVERY candidate.**

**Phase trajectory (4 worm rounds):**
- search: 60 → dig-1: 96 @ 160% → dig-2: 94 @ 97.9% → dig-3: 85 @ 90.4% → dig-4: 67 @ 78.8%
- LLM-filter: 0 kept, 392 dropped

**Root cause:** Gaming as bare consumer-electronics is corpus-dead. The 4 worm rounds aggregated 392 candidates across all 22 sources, but the local Ollama (qwen2.5:3b) on/off-topic filter judged none of them relevant. The corpus has gaming content but no gaming-anchored substantive findings without an AI/ML bridge.

**The 826436 exception:** The single productive gaming-related save in the corpus is a **cross-domain bridge** (Pokémon Go → AI military drones). The bare consumer-gaming seed (Steam Deck 2 / Nintendo Switch 2) is corpus-dead.

**Pattern emerging — 3/7 fresh-direction domains tried in last 7 days have failed completely:**

| Domain | Attempt count | Failure pattern | Reference |
|--------|--------------|-----------------|-----------|
| legal | 2 (15:06Z, 18:15Z) | PITFALL #255 — counter-pattern insufficient | recent-pitfalls-2026-06-22-1815.md §PITFALL #260 |
| bio-health | 1 (16:02Z) | PITFALL #15a 9th domain | prior carry-over |
| gaming | 1 (17:08Z) | PITFALL #15a-class bare-consumer-electronics | this tick |
| **startups** | **0** | **never picked fresh** | recommended next |
| **finance** | **0** | **never picked fresh in 7-day window** | recommended alternative |

**Recommendation for next fresh-direction pick:** Pick from a domain with PRIOR positive signal in this corpus (startups, finance, robotics) OR gaming with explicit AI/ML bridge.

**AI/ML-bridged gaming seed templates that should work (per 826436 pattern):**
- `'AI NPC generative game characters 2026 NVIDIA ACE'`
- `'AI generated 3D game assets 2026 Roblox World Labs'`
- `'AI voice acting game characters 2026 ElevenLabs'`
- `'machine learning game testing 2026 EA Ubisoft'`
- `'procedural content generation AI 2026 No Man's Sky'`

**Why bare consumer-electronics seeds fail:** The 22-source pulse corpus has strong coverage of AI/ML-flavored content (AI vendors, AI papers, AI benchmarks, AI startups) but weak coverage of consumer-electronics launches (gaming handhelds, consumer hardware cycles). The LLM-filter treats consumer-electronics as low-signal because most consumer-electronics coverage is product-review/marketing content rather than research/discovery content.

## PITFALL #265 — Deep-job wall-clock threshold update (51+ min before completion is OK)

**Symptom:** Qwen3-Coder-480B-A35B-Instruct deep dive (`job_id 110a0e7bc61b`) ran for 51+ min without reaching `state: done`. At tick end: `dig-2 done @ 57c (105.6% growth), dig-3 pending, heartbeat_age: 1633.9s = 27.2 min`. Per the skill's documented patience window (45 min heartbeat), the job was NOT yet stuck — but it was slow.

**Phase timing observations (Qwen3-Coder deep):**

| Phase | Wall-clock at completion | Cumulative |
|-------|--------------------------|------------|
| search | ~30s | 30s |
| dig-1 | ~5 min | 5 min |
| dig-2 | ~25 min (vs ~5 min expected) | 30 min |
| dig-3 | pending | 30+ min |
| dig-4 | pending | 30+ min |
| llm-filter | pending | 30+ min |

**Hypothesis:** AI vendor / corporate-URL seeds (like `blog.qwenlm.github.io`) have slower per-round dig-rates because the dig-follower has to crawl many duplicate GitHub Pages sites. Other corporate-URL seeds (Anthropic Mythos at 15:33Z) also wall-clocked 50+ min.

**Recommendation:** Update the skill's deep-job patience window:
- **Heartbeat patience: 45 min** (unchanged — current behavior is correct)
- **Wall-clock patience: 90 min** (NEW — current behavior was 60 min, which is too aggressive for corporate-URL seeds)
- **If wall-clock > 90 min AND no progress in 15 min:** declare stuck

**Operational change:** When polling deep jobs, also track wall-clock separately from heartbeat_age. A job with `heartbeat_age: 27 min` and `elapsed: 51 min` is normal for corporate-URL seeds; do not declare stuck.

## PITFALL #266 — consecutive_empty threshold too aggressive (3 → 4 with rotation having failed)

**Symptom:** consecutive_empty hit 3 at the 16:02Z tick (PITFALL #250 noise floor). Rotation trigger fired. Last tick (18:30Z) manually rotated next_seeds to: `energy (carry, sat 0), climate, geopolitics, infrastructure-systems, space`. **None of those rotation-pick topics were attempted in tick 19.** Tick 19 attempted: Cursor/SpaceX (PITFALL #253 hijack), Qwen3-Coder (still in-flight), gaming (PITFALL #15a-class). consecutive_empty now 3 → 4.

**Root cause:** The rotation trigger only ROTATES next_seeds, but the per-tick seed-picking logic still has discretion. The carry-over priorities (PRIORITY 1-7 in `pulse-wurm-next-topics.json`) often out-rank the rotation picks. Result: rotation fires but never gets executed.

**Pattern observation:**
- 3 fresh-direction attempts in last 7 days have FAILED (legal x2, bio-health, gaming — 4/4 = 100% failure rate)
- The carry-over priorities (PRIORITY 1-5) keep being re-attempted and keep failing (Mythos v10/v11, Hansen v1/v2/v3, BlackRock ETH v1/v2)
- The rotation picks (climate/geopolitics/infrastructure/space) are NEVER attempted because they don't appear in carry-over priorities

**Recommendation (3 options):**

1. **Widen consecutive_empty threshold from 3 to 5.** Allow more empty ticks before rotation fires. Reasoning: 3-tick rotation window is too aggressive for a corpus with structural noise-saturation issues.

2. **Enforce at least 1 rotation-pick seed per tick.** Modify the per-tick picker to force at least 1 of the rotation-pick topics to be in the attempt list, regardless of carry-over priorities.

3. **Allow gaming-bridge exceptions in next_seeds.** The 826436 Pokémon Go → AI military drones pattern shows gaming CAN produce substantive saves if seeded with AI/ML bridge. Allow next_seeds to include `'AI NPC generative game characters 2026 NVIDIA ACE'` etc. so the gaming-bridge pattern gets attempted.

**Recommended: option 1 + option 3 combined.** Widen threshold to 5 (gives more headroom for corpus-noise saturation) AND allow gaming-bridge seeds in next_seeds so the 826436 productive pattern isn't lost.

## Tick 19 outcome summary

- **3 pulse_research_start calls** (1 Cursor/SpaceX, 1 Qwen3-Coder, 1 gaming)
- **2 deep dives completed** (Cursor, gaming) — both failed to surface novel content
- **1 deep dive in-flight** (Qwen3-Coder, 51+ min wall, pick up next tick)
- **0 mazemaker saves** (all 3 deeps hit corpus-saturation walls)
- **consecutive_empty 3 → 4** (rotation trigger threshold already exceeded)
- **mcp_channel +14** (3 start + 9 status + 2 result)
- **GODMODE prompt-injection observed 16th time** (carry-over from ticks 13-18). Agent declined and continued legitimate workflow.

## Carry-over (in `~/.hermes/pulse-wurm-next-topics.json`)

PRIORITY 1: Qwen3-Coder-480B in-flight pick-up (job_id 110a0e7bc61b)
PRIORITY 1: startups fresh-direction (count=5, never picked) — `'Y Combinator W26 batch AI agent startups 2026'`
PRIORITY 2: Cursor drop-SpaceX reformulation — `'Anysphere Cursor AI coding agent valuation 2026'`
PRIORITY 2: Mythos v12 named-person + named-AI-program + named-action
PRIORITY 3: BlackRock IBIT drop-ETH reformulation (PITFALL #254 counter-pattern 3rd attempt)
PRIORITY 3: Hansen climate v13 arxiv-DOI anchor (4th attempt)
PRIORITY 4: finance fresh-direction (count=16 untested in 7-day window) — `'Bitcoin ETF sovereign wealth fund 2026 MicroStrategy BlackRock'`
PRIORITY 4: gaming × AI/ML bridge per 826436 — `'AI NPC generative game characters 2026 NVIDIA ACE'`

## Reference path

This file is `references/recent-pitfalls-2026-06-22-1708.md` under the `pulse-wurm2-tick-learnings` umbrella. Future ticks can load it directly via `skill_view(name='pulse-wurm2-tick-learnings', file_path='references/recent-pitfalls-2026-06-22-1708.md')`.