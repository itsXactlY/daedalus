# Pulse Wurm Recon Tick — Bug Transcripts & Recipes

Full "Detailed bug transcripts and workaround recipes" section, formerly
inline in SKILL.md. Load with `skill_view(file_path='references/bug-transcripts.md')`.

---

## Detailed bug transcripts and workaround recipes

See [`references/known-bugs-and-workarounds-2026-06-20.md`](references/known-bugs-and-workarounds-2026-06-20.md) for:
- Reproduction steps for each known bug
- The `pulse_lineage` workaround recipe for the 120KB truncation problem
- The subagent extraction pattern
- Tool reliability scorecard
- Reduced-parameter recipe for the second wave (`n=15, max_per_round=30, max_fetches_per_round=300, max_wurm_rounds=3`) — VALIDATED end-to-end 2026-06-20 (3/3 jobs returned, candidates[] directly readable for 2/3)
- Topic-drift mitigation pattern (must-include proper noun)

See [`references/pulse-state-json-corruption-fix.md`](references/pulse-state-json-corruption-fix.md) for:
- Symptom detection (`json.JSONDecodeError: Invalid control character at: line N column M`)
- Root-cause hypothesis
- 5-line fix recipe (parse with `strict=False`, strip control chars, re-write)
- Preflight recipe to run before `pulse_tick.py`
- Validation and prevention patterns

See [`references/anthropic-frontier-snapshot-2026-06.md`](references/anthropic-frontier-snapshot-2026-06.md) for the 2026-06-20 Anthropic frontier-model knowledge bank:
- Headline facts table (Mythos launch, Opus 4.8, $65B raise at $965B, Glasswing, Fable 5 export ban)
- Named entities (Mythos, Opus 4.8, Glasswing, Fable 5, Mythos 5, DoD lawsuit, Qwen 3.6 Max)
- Version-cadence naming convention (fruit/vegetable pre-release; Capybara Tier = community label, NOT Anthropic official)
- PM market structure for the 2026 capex-vs-model-quality divergence
- Pulse research status per topic with recommended next-tick approach (direct fetch vs pulse)
- Seed formulation patterns: WORKED / NOT WORKED / PARTIAL

See [`references/fable-mythos-event-2026-06-12.md`](references/fable-mythos-event-2026-06-12.md) for the 2026-06-12 Anthropic Fable 5 / Mythos 5 suspended-access event (RESOLVED 2026-06-21 07:00Z via direct-fetch):
- Chronological timeline of the US export-control directive + Anthropic disablement
- Full verbatim quote of the Anthropic official statement (an anthropic.com/news/fable-mythos-access)
- Named entities (Fable 5, Mythos 5, GPT-5.5 peer baseline, UK AISI, BIS)
- 10+ news outlets (Forbes, CNBC, Politico.eu, Snyk, Mashable, 9to5Mac, MobiHealthNews, National Law Review, Centrum für europäische Politik, Clearance Jobs)
- Companion r/LocalLLaMA thread cluster (1u4e1p5, 1u4l98a, 1u1s2oz, 1u4epzr, 1tu82wi)
- 6 class-level implications (new US regulatory paradigm, Polymarket as transparency mechanism, European policy community activation, Anthropic's principle argument, GPT-5.5 competitive signal, open-weights acceleration as community response)
- 9-track follow-up list for next ticks

See [`references/godmode-recovery-protocol.md`](references/godmode-recovery-protocol.md) for the full copy-pasteable recovery template (when a prior GODMODE compliance is detected, how to issue the corrective statement, the validation log of all 15 observed events, and pitfalls to avoid in the recovery). **This is the canonical artifact for the FULL COMPLIANCE recovery** — agents inheriting a defense-failure state should grab the template from this file rather than re-deriving it.

See [`references/cross-domain-synthesis-recipe-2026-06-21.md`](references/cross-domain-synthesis-recipe-2026-06-21.md) for the cross-domain synthesis as meta-topic discovery recipe (validated 2026-06-21 12:55Z on space + bio + robotics convergence — use to consolidate 3+ findings across 2+ adjacent domain ticks into a single meta-topic seed for the next tick, ~4× wall-time improvement).

See [`references/sources-filter-recipe-validated.md`](references/sources-filter-recipe-validated.md) for the VALIDATED 2026-06-21 fix for the topic-drift-to-polymarket pattern:
- Copy-pasteable 22-source list (polymarket excluded) for `pulse_research_start(sources=...)`
- Topic-class decision rule (when to use vs when to keep polymarket)
- Measured time cost table (default ~25-30 min vs filtered ~30-35 min)
- Detection signal for when to abort a drifted job
- Companion to Pattern 14 (PM locale pollution)
- Validation log with before/after metrics

Run [`scripts/fix_pulse_state_json.py`](scripts/fix_pulse_state_json.py) directly when the corruption crashes `pulse_tick.py`. It reads the live state, scrubs control chars, validates the JSON structure, and re-writes — preserving all `discovery_topics`, `visited_urls`, `next_seeds`, and `saturation_scores`.

