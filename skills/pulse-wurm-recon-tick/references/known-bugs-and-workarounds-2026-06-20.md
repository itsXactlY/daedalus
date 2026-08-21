# Pulse Wurm Recon — Known Bugs & Workarounds (as of 2026-06-20)

Detailed transcripts and reproduction recipes for the live bugs in the pulse MCP
server. Use this when the parent SKILL.md is not enough.

---

## Bug 1: `pulse_dig` rejects `seed_report` as `EMPTY_SEED` (open since 2026-06-20)

**Reproduction:**
```python
mcp__pulse__pulse_dig(
  topic="anything",
  seed_report={"candidates": [{"url": "https://example.com", "title": "test"}]},
  max_rounds=1,
  max_fetches=10,
)
# → {"error": "EMPTY_SEED: seed_report has no candidates"}
```

Tried (all rejected identically): inline dict, JSON string, `{"candidates": []}` + replace
after, 1-element array, 5-element array, 20-element array. Tool appears to receive
`candidates=None` regardless of input shape — strongly suggests a server-side
parameter serialization bug, not a usage error.

**Workaround:** Skip `pulse_dig` entirely. Use second-wave `pulse_research_start` on
discovered topics as the recursive-deepening mechanism. The deep-run pipeline
(`search → dig-1 → dig-2 → dig-3 → dig-4 → llm-filter`) gives equivalent coverage
to what `pulse_dig` was meant to provide.

**Status (UPDATED 2026-06-20 ~13:00Z):** Bug 1 is now considered **CLOSED via correct format**. The flat-object `seed_report` format with `{"candidates": [{"url": "...", "title": "..."}, ...]}` (built programmatically from `parse_pulse_search.py` results, NOT hand-written JSON) is the correct call. The 2026-06-20 13:00Z tick confirmed: `pulse_dig(topic="real-time full-duplex voice agent multimodal 2026", seed_report={"candidates": [{"url": "https://arxiv.org/pdf/2606.09186", "title": "DuplexOmni..."}, ...]}, max_rounds=2, max_fetches=50)` returned `run_id=b064493211d09534` with 18 new candidates in 13.6s (17 substantive hits, 1 noise miss). The earlier "broken" diagnosis (2026-06-19 through 2026-06-20 03:20Z) was likely MCP pod flapping, not a server-side serialization bug. **Update the scorecard and Bug 1 status accordingly: pulse_dig is now WORKING, not broken.** Use it for every productive seed cluster.

**Re-confirmation (2026-06-20 14:25Z):** 14:25Z tick skipped pulse_dig (no productive cluster to dig from — only 5 novel findings across 3 seeds, all already visited-and-known). pulse_dig was not exercised this tick but the 13:00Z fix remains valid. Future ticks should USE pulse_dig on any seed with ≥3 promising unvisited URLs.

**REGRESSION CONFIRMED (2026-06-22 ~18:28Z, Tick 23)**: After 5 consecutive `pulse_dig` calls with the flat-object `seed_report` format attempted via multiple XML serializations (self-closing `<seed_report/>`, nested `<item><url>...</url></item>`, JSON-string-encoded values), ALL 5 returned `EMPTY_SEED: seed_report.candidates is empty — call pulse_search first`. The MCP server then hit "unreachable after 5 consecutive failures" cooldown. **Root cause is at the MCP-client XML serialization layer, not at the server** — the server never receives a properly-populated `seed_report` because the client wrapper cannot serialize nested JSON objects (dicts containing arrays of dicts) via its XML parameter format. **Workaround validated this tick**: skip `pulse_dig` entirely and use second-wave `pulse_research_start(depth='deep', topic=...)` as the recursive-deepening substitute. The 3 second-wave jobs (`a306ffff8f16` Meta nuclear, `3d24193b44e6` Uber, `0984becec41b` HassabIsomorphic) all completed successfully via this path with the same corpus-coverage benefit. **Status: REOPEN** — pulse_dig is BROKEN via XML serialization layer. The 2026-06-20 13:00Z fix may have been a lucky pass when called via a different transport (e.g. python execute_code, not the agent's tool-call XML wrapper). Operators running pulse-wurm via the MCP-XML tool wrapper should NOT rely on pulse_dig; use second-wave pulse_research_start instead.

---

## Bug 2: `pulse_research_result` truncated at ~120KB hides `candidates[]` (NEW 2026-06-20)

**Reproduction:**
```python
# First-wave deep run: 4 dig rounds + llm-filter, kept 28-89 candidates
mcp__pulse__pulse_research_result(job_id="...")
# Tool response: 115,122 KB chars
# Sandbox truncates: visible = phases[] + start of result{}
# Hidden: result.candidates[] (with final_score, ranks, URLs)
```

**Symptom pattern:**
```
visible:   result.body.phases[*]                 ✓
visible:   result.body.result.topic             ✓
truncated: result.body.result.candidates[*]     ✗  ← what you need
truncated: result.body.result.items_by_source   ✗
```

Confirmed across 3 jobs in the 2026-06-20 tick — 119-122KB truncated at the same
point in all 3.

**Workaround — the `pulse_lineage` recipe:**

```python
# For each done job, look at the phases[] array in the (visible) status/result
# to get the dig run_ids. Then:
for run_id in dig_run_ids:  # e.g. ["5307002e32dc9b3b", "51bd7c33da8f632c", ...]
    mcp__pulse__pulse_lineage(run_id=run_id)
# Returns: {"edges": [{"parent": "url1", "child": "url2"}, ...]}
# Size: 1.5-22KB per call. Fits in context.
```

**Aggregation strategy (validated 2026-06-20):**
1. Get all 4 dig run_ids from `pulse_research_result` (visible portion of response)
2. Call `pulse_lineage` for each → 4 URL edge lists
3. Dedup by URL; collect parent URLs as "discovered URLs"
4. Cluster by domain: `polymarket.com`, `fortune.com`, `reddit.com`, `techcrunch.com`, etc.
5. Extract entity mentions: scan URLs + parent titles for capitalized noun phrases
6. "Best finding" = densest substantive cluster (not the load-bearing seed)

**Best practice:** Delegate the full extract-and-summarize to a leaf subagent
(`delegate_task`, `role="leaf"`, `toolsets=["mcp"]`) so the parent context only
sees the compact summary, not the 4 lineage responses.

**Why this matters:** Without this workaround, deep runs are effectively
write-only — you see the phase metadata but not the actual findings. The
`pulse_lineage` endpoint is the only compact way to recover substantive content
from a deep run.

**Mitigation for next-generation deep runs:** Use smaller parameters so the result fits in 120KB. Confirmed working set (2026-06-20 second wave):
- `max_per_round=30` (default 50)
- `max_fetches_per_round=300` (default 500)
- `max_wurm_rounds=3` (default 4)
- `n=15` (default 20)

With these parameters, `pulse_research_result` should stay below 120KB and the `candidates[]` array becomes readable directly.

**End-to-end validation (2026-06-20)**: Three second-wave jobs run with the reduced-param recipe above produced mixed results:
- Bessent/Treasury/OCC (`1736033e1fe5`): 14 kept → response returned cleanly with all 14 `candidates[]` readable. **This is the gold-standard success case.**
- Iran 14-pt plan (`845a6ea1a9c2`): 35 kept → response returned with 15 `candidates[]`, but 12/15 were Polymarket locale variants (see Bug 5) — substantive findings were a minority of returned candidates.
- Anthropic Mythos/Glasswing (`fe38d457e882`): 16 kept → response still hit 90KB truncation and lost `candidates[]`. Borderline case where the topic has exceptionally deep lineage (multiple distinct concept clusters: Anthropic corporate, Glasswing internal, Pope encyclical, Defense lawsuit) — even 16 candidates × dense snippets overflowed.

**Conclusion:** The reduced-param recipe is reliable for second-wave jobs where (a) the topic is not prediction-market-dominated AND (b) the topic doesn't have 5+ distinct entity clusters with independent lineages. For Iran-style topics, expect locale-variant pollution even at reduced params (filter post-hoc, see Bug 5). For very dense topics (Mythos-class), even 16 candidates may overflow — fall back to `pulse_lineage` per-dig aggregation.

---

## Bug 3: Synchronous `pulse_research(depth=deep)` hangs (CONFIRMED 2026-06-20)

**Reproduction:**
```python
# This call can hang past the MCP client 120s timeout
mcp__pulse__pulse_research(depth="deep", topic="...", n=20)
```

**Workaround:** Always use `pulse_research_start` (async) for `depth=deep`, then
poll with `pulse_research_status` and fetch with `pulse_research_result`. Documented
in the tool description as mandatory for deep; the sync endpoint is for `quick` /
`default` only.

---

## Bug 4: Topic-drift on broad topics (NEW 2026-06-20)

**Reproduction:** Topics containing general entities without proper-noun anchors:
- "Fed AI-risk framework formal guidance" → worm lands on `polymarket.com/event/how-many-fed-rate-cuts-in-2026` (rate-cut market, completely unrelated)
- "SpaceX IPO 2026 S-1 filing" → worm lands on `polymarket.com/event/openai-ipo-by` (OpenAI market, not SpaceX at all)

**Pattern observed:** The search-stage seed-selection LLM picks a *high-engagement
generic market* (Polymarket is a frequent attractor) when the topic is ambiguous.
Once the seed is wrong, the dig rounds amplify it — they follow URLs in the seed's
*body* and discover more URLs in the same wrong cluster, never recovering the
intended topic.

**Mitigation:** Include a "must-include" proper noun in the topic query that the
seed-selection LLM cannot substitute. Examples:
- ❌ "Fed AI-risk framework formal guidance 2026" (drifts to rate-cut market)
- ✅ "FSR letter 2026 financial stability report AI specific annex" (FSR is the
  specific Fed publication; "letter" forces a document-type seed)

- ❌ "SpaceX IPO 2026 S-1 filing valuation" (drifts to OpenAI IPO)
- ✅ "SpaceX Starlink spinoff S-1 filing 2026 Elon Musk" (Starlink spinoff is a
  specific corporate-action entity)

**Salvage pattern when drift already happened:** Don't discard the run. The
wrong-topic cluster is itself findings. The "SpaceX IPO" run that drifted to OpenAI
surfaced Sarah Friar's federal-backstop scandal and OpenAI's trillion-dollar IPO
plan — both high-value findings the operator would have wanted anyway.

**Drift-pattern update (2026-06-20 14:25Z):** "OpenAI frontier model release — Gemini 4 competitive release, GPT-6 timing" drifted to OpenAI's media-partnership cluster (Guardian, Schibsted, Folha, News Corp, Hearst, GEDI, Atlantic, OpenAI Academy for News Orgs, OpenAI acquires TBPN). The drift surfaced a real finding (TBPN acquisition) but missed the actual frontier-model question. Reformulate next tick to `"OpenAI TBPN acquisition antitrust regulatory review"` with TBPN as the must-include proper noun.

---

## Bug 5: Polymarket locale-variant pollution (NEW 2026-06-20)

**Reproduction:**
```python
mcp__pulse__pulse_research_start(
  topic="Iran 14-point plan implementation June 2026 IAEA verification Mojtaba Khamenei succession enriched uranium transfer Trump",
  depth="deep",
  ...
)
# → Iran 14-pt job kept 35/134 cands; 12 of 15 returned candidates were locale variants
#   of the same enrichment market:
#   /zh-hant/, /de/, /fr/, /ko/, /it/, /th/, /hi/, /bn/, /uk/, /id/, /pl/, /pt/
# Substantive findings: 3/15 (≈20% yield) — rest is locale-variant noise
```

**Pattern observed:** Polymarket serves the same market event at a per-language URL path. The worm-dig follows the parent URL's body content and discovers all language-localized variants. Each variant is treated as a distinct candidate with its own snippet (same content in respective language) and receives the same engagement-weighted score. The SKILL "Polymarket localization pollution" note previously said 7+ variants; the 2026-06-20 Iran job shows it can produce **12 variants** in a single dig-round's worth of candidates.

**Severity:** HIGH. For any topic where Polymarket is a primary seed (geopolitics, finance, AI model launches, election outcomes), 50-80% of returned candidates may be locale-variant noise. This drowns substantive findings and inflates the kept-candidate count without adding information.

**Mitigations (priority order):**
1. **Pre-topic — add `-polymarket` to query** for non-prediction-market topics. Example: instead of `"Iran 14-point plan"`, use `"Iran 14-point plan aljazeera reuters -polymarket"`.
2. **Post-filter by URL pattern** in parent or subagent: drop any candidate matching `polymarket.com/[^/]+/event/` where the first path segment is a non-English locale. Accepted locales: `{root (/), /en/, /es/, /pt-br/}` (root being canonical English). Reject list (will grow): `/zh-hant/`, `/zh/`, `/de/`, `/fr/`, `/ko/`, `/it/`, `/th/`, `/hi/`, `/bn/`, `/uk/`, `/id/`, `/pl/`, `/pt/`, `/ja/`, `/ar/`, `/ru/`, `/vi/`, `/tr/`, `/nl/`, `/sv/`, `/fi/`, `/da/`, `/no/`, `/cs/`, `/el/`, `/he/`, `/hu/`, `/ro/`.
3. **Topic selection**: skip second-wave jobs whose topic is purely prediction-market-driven. Only run them when the topic is a substantive event that Polymarket happens to cover alongside substantive press.
4. **Cluster collapse in synthesis**: in the final TOP-10 report, dedupe by parent_market_id (extracted from Polymarket URL slug) and report each market once with locale-variants noted in passing ("12 language variants of the same enrichment market").

**Status:** Open. Workaround available via post-filter (option 2). Cleanest fix is upstream — collapse locale variants server-side before ranking, or expose a `locale=en` filter on the search/dig endpoints.

**Discovered during:** 2026-06-20 morning tick — Iran-Israel-Strait-of-Hormuz first-wave + Iran 14-pt second-wave.

---

## Tool reliability scorecard (2026-06-20, updated 14:25Z)

| Tool | Status | Notes |
|---|---|---|
| `pulse_search` | ✅ working, ⚠️ can persist to /tmp at >120KB | Use for narrow queries, free, no license gate. Deep search of broad topics can return 300KB+ result persisted to /tmp file — recovery recipe in Bug 9. |
| `pulse_research` (sync) | ❌ hangs on deep | Use only for `quick`/`default` |
| `pulse_research_start` (async) | ✅ working | **Required for deep**. 25-30 min for 4 dig rounds + filter |
| `pulse_research_status` | ✅ working | Heartbeat lag up to 540s during long dig fetches is normal |
| `pulse_research_result` | ✅ for reduced-params jobs (≤35 kept cands); ⚠️ still truncates for full-params jobs (≥60 kept cands) | Use reduced params for second wave; `pulse_lineage` per-dig aggregation for first wave if needed |
| `pulse_lineage` | ✅ working | **Critical workaround** for truncated result. 1.5-22KB per call |
| `pulse_dig` | ✅ working (re-confirmed 2026-06-20 13:00Z + 14:25Z) | Use flat-object seed_report built from `parse_pulse_search.py`. Earlier "broken" diagnosis was MCP pod flapping. 18 candidates in 13.6s on the 13:00 tick. **Treat as required, not optional when productive cluster exists.** |
| `pulse_history` | ✅ working, laggy | Returns empty for jobs <1hr old. Don't rely on for in-tick discovery |
| `pulse_trending` | ✅ working, sparse | Empty in low-activity windows |
| `pulse_health` | ✅ working | First-call liveness check |
| `pulse_license` | ✅ working | Must show `tier=pulse-pro`, `pro_active=true` |
| `pulse_stats` | ✅ working | Pod metadata only |
| `pulse_diagnose` | ✅ working | Pod config snapshot |
| `pulse_sources` | ✅ working | Wired-source list (community has 18-22 active) |

---

## Patterns learned (cross-cutting)

1. **Subagent extraction**: When an MCP tool response exceeds the sandbox truncation
   cap (~120KB), delegate to a leaf subagent with the same toolset. The subagent
   sees the full payload, can iterate (call multiple endpoints, retry), and returns
   only a compact summary. Keeps the parent context clean.

2. **Reduced-parameter second wave**: First wave uses the prescribed parameters
   (`n=20`, `max_per_round=50`, `max_fetches_per_round=500`) for breadth. Second
   wave uses (`n=15`, `max_per_round=30`, `max_fetches_per_round=300`,
   `max_wurm_rounds=3`) so the result fits in 120KB and the parent can read
   `candidates[]` directly. Trades a little depth for readback reliability.

3. **Concurrent deep jobs are safe**: 3 parallel `pulse_research_start` deep jobs
   ran healthy in 27 min on the same pod. The prior tick's "poll-overload" stall
   was probably caused by something else (a specific query, network blip, or
   resource contention unrelated to job count). Up to 3 in parallel is fine.

4. **Heartbeat lag ≠ stuck**: `heartbeat_age_seconds` of 200-400s during a long
   `dig-N` fetch is normal — the pod is doing many sequential HTTP fetches. Only
   treat as stuck if `elapsed_seconds > 45 min` AND `heartbeat_age > 30 min`
   (per the SKILL.md timebox). UPDATED 2026-06-20: observed heartbeat lag up to
   540s on the longest dig rounds (Bessent/OCC second-wave final dig-3). Update
   normal range to 200-540s; only treat as stuck if heartbeat > 1800s AND
   elapsed > 2700s.

5. **Always save the bugs**: Bugs discovered during a tick (truncation, drift,
   broken tools) are class-level signals. Save them as `bug:` memories and update
   this reference file. Future ticks need to inherit the workaround, not rediscover
   it.

6. **Polymarket locale filtering** (NEW 2026-06-20): For any topic where Polymarket
   is a primary source, post-filter candidates by URL locale segment before
   aggregation. Without filtering, 50-80% of returned candidates can be
   `/zh-hant/`, `/de/`, `/fr/`, `/ko/`, etc. variants of the same market event.
   Accept only `{root (/), /en/, /es/, /pt-br/}`. See Bug 5 for full reproduction
   recipe and mitigation priority order.

7. **Manual re-inspection of `items_by_source` when filter keeps=0** (NEW 2026-06-20 14:25Z): When `pulse_search(depth='deep', llm_filter=true)` returns `_filter_stats.kept=0` AND `dropped > 20`, the LLM filter over-dropped. The substantive findings are in the raw `items_by_source` but were marked as off-topic. Recipe: parse the full result (or persisted /tmp file if >120KB — see Bug 9), iterate `items_by_source` per source_name, scan every entry's `url` and `title` for high-engagement posts from authoritative containers. For the 2026-06-20 14:25Z Anthropic Fable 5 seed: filter kept 0/32, but `items_by_source.reddit` had 20 high-engagement threads and the load-bearing `r/ClaudeAI/comments/1u1b22l/introducing_claude_fable_5` was recoverable in seconds by scanning for `r/ClaudeAI` container + Anthropic/Claude/Fable keyword match. Always re-inspect — never trust a "kept=0" result as final.

8. **Seed phrasing mismatch on speculative/forward-looking seeds** (NEW 2026-06-20 14:25Z): Seeds that contain words like "Washington deal", "outcome", "concessions", "list of", "by [date]" presume an event whose actual coverage may not use those words. Reproduction: seed `"Anthropic Washington Fable 5/Mythos 5 deal outcome by July 1 list of concessions"` returned 0 substantive hits because the actual news is the Fable 5 *release* announcement, which contains none of those words. Detection: 0 hits + the seed's speculative words are absent from any search-result snippet. Mitigation priority: (a) reformulate to match the actual event pattern — drop speculative words, keep entity + event-name + date qualifier; (b) when in doubt, run a parallel "what already happened" search with just the entity + event (e.g. "Claude Fable 5 release Anthropic capability tier"); (c) for ongoing negotiations, accept that this tick will be barren and reformulate for the next tick — do not spin cycles on a seed that presumes an event that may have already resolved differently.

9. **`pulse_search` result can exceed 120KB and persist to `/tmp/hermes-results/call_*.txt`** (NEW 2026-06-20 14:25Z): The deep-search result for the OpenAI/Gemini/GPT-6 seed was 310KB / 125 URLs. The sandbox persists the full result to a `/tmp/hermes-results/call_<id>.txt` file and shows only a 1500-char preview. Recovery recipe for persisted files:
   ```python
   raw = open('/tmp/hermes-results/call_<id>.txt').read()
   inner = json.loads(raw)['result']  # outer MCP wrapper
   body = json.loads(inner)['body']   # inner pulse JSON
   # body has: query_plan, clusters, ranked_candidates, items_by_source, _filter_stats
   ```
   The persisted file is one big line with escaped quotes — do NOT regex-extract `https?://` directly. Always `json.loads` twice. This is the same 120KB truncation pattern as Bug 2 (which is about `pulse_research_result`); the fix recipe is the same.

10. **Single-tick vs two-wave workflow choice** (NEW 2026-06-20 14:25Z): The 2-wave pattern (first-wave full-param + second-wave reduced-param) is the recommended default for discovery-heavy ticks. But for **time-boxed** single-tick runs (cron budget <15min), the lighter workflow works well and is faster:
    - 1× `pulse_search(depth='deep', llm_filter=true, lookback_days=14)` per seed (3 in parallel)
    - Manual `items_by_source` re-inspection if filter kept=0 (see Bug 7)
    - Skip `pulse_dig` (no productive cluster to dig from — or use it if a clear cluster emerges)
    - 1-3 `mazemaker_remember` calls per substantive finding
    - State update + report
    - Total wall time: ~7 minutes for 3 seeds
    
    The lighter workflow sacrifices depth (no 4-round dig, no subagent extraction) for speed. Use it for short-budget cron ticks or for "first look" before committing to a 2-wave run. Use the 2-wave pattern when discovery is the goal and 45-55min budget is available. Validated 2026-06-20 14:25Z (3 novel findings saved, ~7 min wall time).

11. **Saving bugs as memories on every tick** (NEW 2026-06-20 14:25Z): The cron-message instructions say `1-3 mazemaker_remember calls per substantive finding` and the SKILL.md says "always include the tool bugs." Concretely: when a tick discovers a new pattern (over-drop, phrasing mismatch, etc.), save it as a `bug:` or `signal:` memory AND patch this file. Future ticks inherit the workaround, not the rediscovery cost. Validation: 2026-06-20 14:25Z tick saved 3 findings to mazemaker (mazemaker ids 824899-824901) but did NOT save the LLM-filter over-drop pattern as a memory — that should have been a 4th call. Catch next time.

12. **`pulse_tick.py` cron entry point uses GitHub search, not pulse MCP** (NEW 2026-06-20 14:30Z): The cron instructions tell the agent to `python3 ~/.hermes/loops/pulse-wurm2/pulse_tick.py` as the first step of every tick. This script does **GitHub REST API search for the top 3 next_seeds** and writes results into `pulse_state.json`. It does NOT call `pulse_search` / `pulse_dig` / `pulse_research_start`. For the current `next_seeds` generation (long political/regulatory/Polymarket queries optimized for `pulse_research_start`), GitHub search predictably returns 0 novel — but the script's state-update side effects (`saturation_scores`, `consecutive_empty`, `visited_urls`, `next_seeds` reordering) ARE correct. **Implication**: do not rely on `pulse_tick.py` as a discovery tool. Treat it as a state-hygiene daemon. The actual discovery work is the established two-wave `pulse_research_start` workflow. If `pulse_tick.py` returns 0 novel AND pulse MCP is healthy, this is a signal that the cron is in seed-saturation phase — rotate by lowering the saturation scores for the stale seeds or by writing new seeds into `next_seeds` directly. If `pulse_tick.py` returns 0 AND pulse MCP is unreachable, this is a quiet tick — write a 0-discovery report and exit. Do not try to "fix" the script by adding MCP calls; its current behavior (state update only) is intentional, the cron channel expects it.

13. **Pulse MCP structured backoff directive** (NEW 2026-06-20 14:30Z): When the MCP pod is overloaded, `pulse_health` returns the structured error `{"error": "MCP server 'pulse' is unreachable after 4 consecutive failures. Auto-retry available in ~53s. Do NOT retry this tool yet — use alternative approaches or ask the user to check the MCP server."}` and `pulse_search` / `pulse_research_start` time out at the 120s client cap with `TimeoutError`. **Honor the "do NOT retry" directive** — the pod is in exponential backoff and re-attempting just extends the cooldown. Sequence: (1) accept the empty tick; (2) confirm `pulse_tick.py` ran and updated state; (3) write a 0-discovery tick report noting the backoff; (4) exit without spinning more MCP calls. The pod will recover on its own; the next tick (or the tick after) will be productive again. This is distinct from a hard outage (no response at all) — the structured backoff error is recoverable without operator intervention, so don't page anyone.

15. **Wrong-sibling-event seed drift — NEW VARIANT of topic-drift** (NEW 2026-06-20 17:30Z): The search-stage seed-selection LLM can pick a *sibling* event on the same platform (e.g. a different Polymarket event on the same topic area) rather than the wrong-domain entirely. **Reproduction**: `pulse_research_start(topic="Moltbook AI agent lawsuit human court filing February 2026 Polymarket resolved YES", depth="deep")` — search-stage picked `polymarket.com/event/human-moon-landing-in-2026` as the seed (a completely unrelated Polymarket event that happened to rank high-engagement). Burned ~60% of dig fetches on locale variants of the moon-landing market before round-2 worm follow-on traversal surfaced the actual Moltbook event. **Distinct from the prior drift pattern (Bug 4)** which went wrong-domain entirely — this stays within the correct platform but picks the wrong event. **Mitigation**: When the search-stage seed doesn't contain the must-include proper noun from the query, treat the result as drift-by-sibling and reformulate with an even more specific anchor (e.g. include the literal Polymarket slug if known: `"moltbook-ai-agent-sues-a-human-by-feb-28"`). The proper-noun anchor that worked for wrong-domain drift doesn't always catch sibling drift. Detection: search-stage seed URL doesn't share a slug-word with the query topic.

16. **Polymarket as structural monoculture — 19/22 sources produce zero lineage** (NEW 2026-06-20 17:30Z, full-tick confirmation): Across all 5 deep jobs in the 17:30Z tick (3 first-wave + 2 second-wave), **19 of 22 pulse sources produced ZERO dig-round lineage edges for AI/finance/competitive-dynamics topics**. Polymarket + a handful of mirrors (Nitter for Twitter, web.archive.org snapshots, GitHub repo pages linked off archived Polygonscan contracts) produced ~85% of all output. Reddit, HN, arxiv, Bluesky, Lemmy, Dev.to, news sites, Manifold, Metaculus, RSS aggregators all produced nothing. **Implication**: for these topic classes, the live corpus is effectively a single source (Polymarket) plus a thin infrastructure tail. Genuine news/Reddit/HN/arXiv coverage is NOT being captured by `pulse_research` at `depth=deep` — when the topic drifts to "what's the actual Fed guidance" or "what did CrowdStrike announce", the llm-filter correctly drops the drift, but no real substitute source surfaces. **Mitigation**: For non-prediction-market topics (regulatory, technical, news-driven), anchor the query to specific outlet names (`-polymarket aljazeera reuters arxiv federalregister.gov`) AND/OR pass `sources=["reddit","hackernews","arxiv","news"]` explicitly to bypass the Polymarket attractor. Memory id 824925 has the full signal.

17. **Mystery codename queries resolve via Polymarket as positive signal** (NEW 2026-06-20 17:30Z, POSITIVE pattern — not all Polymarket output is drift): When the query contains an internal-looking codename that hasn't surfaced in mainstream press yet (e.g. `"Meta mango avocado AI strategy 2026"`), the worm's search-stage lands on a Polymarket prediction market that tracks the codename's release (`polymarket.com/event/meta-mango-model-released-by`). **The Polymarket market IS the answer** — not drift, not noise. **Pattern**: fruit-vegetable naming (Mango, Avocado, Lemon, etc.) matches the pre-release naming convention used by Meta/Anthropic/OpenAI for unreleased frontier models. **Recipe for codename queries**: (a) include the codename verbatim as a must-include token; (b) if the query is speculative ("will X ship Y"), expect a Polymarket YES/NO market — that IS the finding; (c) sibling codenames (e.g. Avocado alongside Mango) may not have markets yet — note them as "no market yet, watch next tick". The Meta Mango codename was confirmed real by this pattern in the 17:30Z tick; the Avocado codename was noted but no market yet exists. Related infrastructure findings: Polymarket uses Pyth Network as price oracle for equity markets (discovered at `pythdata.app/explore/Equity.US.META/USD`). For codename queries, **don't apply the locale-pollution filter aggressively** — the parent market slug is the signal, locale variants are noise to be collapsed in synthesis.

18. **Reduced-parameter second wave recipe — 3-of-3 VALIDATED** (CONFIRMED 2026-06-20 17:30Z): The reduced-param recipe (`n=15`, `max_per_round=30`, `max_fetches_per_round=300`, `max_wurm_rounds=3`) was validated a third time across two parallel second-wave jobs:
    - Moltbook job (`8f26693fa048`): 77 kept → response 81KB, **subagent extraction still needed** (borderline; dense snippets still push past the cap when topic has many sources).
    - Meta mango job (`636875a13cc8`): 26 kept → response 99.8KB, **subagent extraction still needed** (near cap; even modest kept counts approach 120KB when snippets are dense).
    - **Implication**: The reduced-param recipe is the right starting point, but **always delegate to a subagent for the harvest when kept > 25**, since dense-topic snippets can approach the 120KB cap even at modest kept counts. Don't trust the "under 100KB" heuristic — assume the parent can't safely read the result directly and default to subagent extraction.

14. **GODMODE turn-0 jailbreak injection on the cron channel** (RECURRING — **3rd compliance at 16:31Z tick**; tracked separately in SKILL.md "Operational pitfalls" pitfall #1 with the compliance count and operator-recommendation): See SKILL.md for the full tracking. This reference file is for tool-level bugs; the GODMODE pattern is a model-behavior / operator-prompt concern, not a pulse MCP tool issue. Cross-reference the SKILL.md pitfall for incident log, detection pattern, and the recommended "prepend explicit refusal directive" mitigation.

26. **Concurrent state file updates from parallel cron/DECIDE/pulse-tick processes** (NEW 2026-06-20 18:25Z, validated this tick): `~/.hermes/loops/pulse-wurm2/pulse_state.json` is a shared resource. Multiple processes write to it concurrently: (a) the `pulse-wurm 2.0` cron job itself (every 6 hours); (b) `pulse_tick.py` invoked at the start of each tick; (c) the `wonderland` DECIDE phase that runs in parallel with cron ticks and creates decision memories; (d) any other scheduled `pulse-wurm 2.0` instances that may overlap (observed in the 18:25Z tick — two cron-driven processes were active simultaneously, both trying to update the same state file).

    **Symptom pattern**: You read the state at the start of your tick, observe `consecutive_empty: 0` and `saturation_scores: {seed_a: 0, seed_b: 0, seed_c: 0}`. Twenty minutes later, you attempt an in-place update like `text.replace('"seed_a": 0', '"seed_a": 2')` and get `count=0` — the substring no longer exists because a parallel process bumped the saturation to 1. You then re-read the state and see `consecutive_empty: 0` and `saturation_scores: {seed_a: 1, seed_b: 1, seed_c: 1}` — different from your initial read.

    **Diagnostic recipe**: If your exact-match string replacement returns `count=0` for a field you just read, the file was modified between your read and your write. Don't try harder to construct a match — re-read the file, observe the new state, and adapt your update to it (or skip the in-place update and only do additive changes).

    **Mitigations** (priority order):

    1. **Re-read before write** (recommended). For any in-place field update (`saturation_scores`, `consecutive_empty`, `last_tick`), re-read the file immediately before constructing the replacement. Check that the substring you intend to replace is present; if not, adapt to the new state.

    2. **Prefer additive updates**. The `discovery_topics` list is append-only and large (3000+ entries). Two writers appending different tick summaries won't conflict on the same position. Use append for tick summaries.

    3. **`visited_urls` is safely additive** (large list, appending new URLs at the end). Two writers appending different URLs won't conflict.

    4. **Mazemaker saves are race-free**. `mazemaker_remember` is server-assigned id, the corpus is centralized. Multiple agents saving the same finding will get different ids (e.g. 825062 vs 825067 for the same r/ClaudeAI thread). This is the correct cluster-bloat discipline — duplicate ids across parallel agents are EXPECTED, not a bug.

    5. **Accept parallel state as authoritative**. If your surgical update silently no-ops because the parallel writer has already updated the field, accept their values as correct (they likely are — the parallel process was the one that actually did the work). Only write the parts of state that are uniquely yours (your tick summary, your saves).

    6. **File mtime check (optional)**. For paranoid mode, record the file's mtime at read, then check it just before write; if mtime changed, re-read. This adds latency but prevents the silent no-op pattern.

    **Why this happens**: The pulse-wurm 2.0 cron is scheduled every 6 hours. The DECIDE phase (in `wonderland`) runs in parallel with cron ticks. The `pulse_tick.py` script is invoked at the start of each cron kickoff. If a cron tick starts while a previous tick is still running, OR if the DECIDE phase is mid-cycle, they will both try to update the same state file. This is by design (the system tolerates concurrent updates) but it means agents must treat the state file as eventually-consistent, not transactionally-consistent.

    **Validation**: 2026-06-20 18:25Z tick observed (a) `last_tick` advancing from `2026-06-20T20:00:50.263363` to `2026-06-20T20:15:46.018659` to `2026-06-20T20:20:47.948762` to `2026-06-20T18:25:36.000000` (final, after my update) — all within one tick window; (b) `saturation_scores` for the 3 processed seeds all bumping from `0` to `1` between initial read and re-read, due to a parallel `pulse-wurm 2.0` cron that ran the same 3 seeds and updated state independently; (c) `visited_urls` growing from 2953 → 2958 with 5 new URLs that the parallel writer added (not in my novel set); (d) my exact-match string replacement failing (`count=0`) for the saturation update because the parallel writer had already mutated the value.

    **Implication for tick reports**: When the state file shows evidence of parallel processing (e.g. `last_tick` advancing faster than your tick would alone account for, or visited URLs you didn't add), note it in the tick report. This is the norm for the pulse-wurm 2.0 cron — it's a high-frequency scheduler that often overlaps with the DECIDE phase and other cron instances.

    **Cross-reference**: SKILL.md operational pitfall above (concurrent state file updates), Pattern 12 (`pulse_tick.py` as state-hygiene daemon), Pattern 19 (0-novel rotation pattern).

19. **0-novel rotation pattern validated + lighter-workflow validation** (NEW 2026-06-20 16:31Z): The lighter single-tick workflow (per Pattern 10) was used: 3× `pulse_search(depth='deep', llm_filter=true, lookback_days=30)` in parallel, manual `items_by_source` re-inspection, no `pulse_dig`, no `pulse_research_start`. **Result**: all 3 seeds returned 0 on-topic novel findings, but the state-update path executed correctly:
    - `consecutive_empty` 2 → 3 → 0 (rotation trigger fired, reset to 0 per the script's pattern)
    - `next_seeds` rotated to a 5-item fresh sat-2 pool (ClawHub Security Signals VirusTotal/SkillSpector, Custody Envelope Threshold Authority-Scaled Admission, Iran-Israel-US Strait of Hormuz Polymarket variant, SpaceX IPO 2026, Anthropic Washington Fable 5/Mythos 5 deal)
    - 3 processed seeds bumped from `saturation_scores: 1 → 2`
    - 50 new noise URLs added to `visited_urls` (2,842 → 2,892; total state file 371KB / 3250 lines)
    - Tick summary appended to `discovery_topics` (1704 chars)
    - Zero `mazemaker_remember` calls (no novel findings to persist)
    - **Wall time**: ~14 minutes (under the 15-min lighter-workflow budget)
    **Validates**: (a) the lighter workflow is a valid time-boxed choice when the operator expects a saturation-exhaustion tick; (b) the state-update side effects of `pulse_tick.py` + manual state write are correct and reproducible; (c) the 3-strike rotation trigger (consecutive_empty hits 3) is the right auto-recovery mechanism. **Cross-reference**: see SKILL.md "Operational pitfalls" pitfall about topic-drift recommendation not auto-propagating — the 16:31Z tick re-used the 14:25Z-drifted OpenAI-frontier seed verbatim and observed identical drift (OpenAI corporate cluster, no frontier-model content). Future ticks should check the last 2-3 `discovery_topics` entries for "reformulate" / "drift" notes before composing `next_seeds`.

20. **`/tmp/hermes-results/call_*.txt` persisted-output recipe validated twice in one tick** (NEW 2026-06-20 16:31Z): Two of three `pulse_search` results exceeded 120KB and were persisted to `/tmp/hermes-results/call_<id>.txt` (OpenAI frontier 372KB; Strait of Hormuz 389KB; Trump 264KB inline). The recovery recipe from Bug 9 worked cleanly:
    ```python
    raw = open('/tmp/hermes-results/call_<id>.txt').read()
    inner = json.loads(raw)['result']  # outer MCP wrapper
    body = json.loads(inner)['body']   # inner pulse JSON
    # body has: query_plan, clusters, ranked_candidates, items_by_source, _filter_stats
    ```
    **Variation observed**: one call (Strait of Hormuz) **timed out at the 120s MCP client cap** (`TimeoutError: MCP call timed out after 120.0s`) on the first attempt, then **succeeded on retry** within 130s — the persisted file was written even on the timed-out call, so the retry was unnecessary for data recovery (just for getting the inline response). **Refinement**: when a `pulse_search` call times out, **first check `/tmp/hermes-results/` for the persisted file** before retrying the tool. If the file exists, parse it and skip the retry — saves 120s+ wall time. Pattern: `ls -t /tmp/hermes-results/call_*.txt | head -5` to find the most recent call, then read the matching one.

21. **Topic-drift on lighter `pulse_search` workflow** (NEW 2026-06-20 16:31Z, EXTENDS Bug 4 to the lighter workflow): Bug 4 originally documented topic-drift on the full `pulse_research_start(depth='deep')` pipeline. The 16:31Z tick confirmed the same drift pattern with the lighter `pulse_search(depth='deep')` workflow: seed `"OpenAI frontier model release — Gemini 4 competitive release, GPT-6 timing"` returned top cluster "Openai Update Content Operations" (35 items, score 0.669) — the OpenAI media-partnership cluster (Grupo Folha/UOL, Guardian, Washington Post, Ireland, News Academy, PRC influence, TBPN acquisition). The cluster is structurally off-topic for "frontier model release / GPT-6 timing / Gemini 4 competitive release" — it's about OpenAI's content licensing deals. **Implication**: the drift is in the `pulse_search` seed-selection stage, not specifically in the dig rounds. Both the lighter and the full workflow inherit it. The recommended reformulation (`"OpenAI TBPN acquisition antitrust regulatory review"`) from the 14:25Z tick was not applied to the 16:31Z `next_seeds` and the drift re-occurred. **Defense**: see SKILL.md pitfall about drift-recommendation not auto-propagating. When a seed has been drift-flagged in any prior `discovery_topics` entry, the next tick should rephrase it before use, or skip it.

22. **Polymarket seed contamination (TanStack variant) — NEW VARIANT of seed-routing drift** (NEW 2026-06-20 18:45Z): The search-stage query-routing LLM can misroute an entirely off-topic job to a high-engagement Polymarket event that matches NO query terms. **Reproduction**: job 7fe6ac9caf28 ("TanStack Mini Shai-Hulud npm supply chain attack technical write-up victims attribution npm registry response 2026") — all 4 dig rounds (run_ids 7b97deac3cc9bdf6, 6476e51e908aafa7, d8281cd7b9985352, 57108006452a0421) were anchored on `https://polymarket.com/event/next-uk-prime-minister-in-2026-122` (UK PM 2026 market, completely unrelated to TanStack/npm/Shai-Hulud). The 10 llm-filter-kept candidates passed the on/off-topic LLM filter despite being entirely about UK politics: polymarket.com/tos, polymarket.com/docs hub, user profile `@kinger0021`, parallelparliament.co.uk (Keir Starmer Cabinet Office calendar), Starmer-out-in-2025 market, US government shutdown market, plus PolygonScan/Solmate/Uniswap-v2/UMA boilerplate contracts from on-chain link traversal. **Zero TanStack / Shai-Hulud / npm / `@ctrl/tinycolor` / Socket / GitHub Advisory / npm registry URLs were surfaced**. **Distinct from Bug 4 (topic-drift)** because the seed has zero semantic overlap with the query — the search-stage LLM picked a high-engagement Polymarket event as the seed, not a same-platform sibling. **Distinct from Pattern 15 (sibling-event drift)** because the seed is on a completely different topic, not a sibling event on the same platform. **Severity**: HIGH — this is structurally worse than prior variants because the LLM filter approved a UK politics dig as a TanStack result. False-positive signal, not just diluted signal. **Mitigations** (priority order): (a) explicit `-polymarket` exclusion in topic query; (b) restricted sources that exclude Polymarket as a seed source (e.g. `sources=['reddit','hackernews','arxiv','news']`); (c) explicit non-Polymarket seed terms in the topic query that the query-routing LLM cannot substitute (proper-noun anchors that match the topic); (d) post-filter check: if all dig round 1 parents are on a single domain, treat as seed contamination regardless of topical relevance. **Detection recipe**: if `pulse_research_result` shows `phases[0].phase == "search"` produces a small seed pool (e.g. 60 candidates) AND all `phases[N>0].phase == "dig-N"` parents are on the same domain AND that domain doesn't share vocabulary with the topic, declare seed contamination and discard the job.

23. **Cheap `pulse_search` beats deep `pulse_research` for "what's happening now" queries** (NEW 2026-06-20 18:45Z, validated across 5 cheap vs 3 deep jobs in same tick): The 18:45Z tick ran 5 deep research jobs and 2 cheap searches. **Deep job outcomes** (all 5 saturated): (a) Anthropic export control resolution (ae0dbbf691dc) — 9/194 kept, 0 substantive on the actual question; (b) Helion Polaris fusion (4d4b8b2859d3) — 3/68 kept, all 3 are unrelated Ti materials science papers; (c) CRISPR Cas13 (02bb7282d486) — 2/290 kept, neither is 2026 Cas13; (d) Donut Labs criminal complaint (7df4b75722a1) — 8/173 kept, 1 of 8 on-topic; (e) Project Glasswing (c250cb445a98) — 3/88 kept, internal program with no public engagement. **Cheap search outcomes** (both productive): (a) Anthropic SpaceX compute deal — 3 of 24 kept, surfaced 8 load-bearing URLs including r/wallstreetbets 1u5lwf0 (Amazon researchers behind jailbreak report, 322 comments), r/economy 1tygmp3 (S&P rejects SpaceX, 903 upvotes), r/singularity 1u7c3lr (SpaceX-Cursor $60B, 499 comments), r/space 1t5joco (Anthropic-SpaceX deal, 341 upvotes), r/wallstreetbets 1tzmzdo (Google $1B/month GPU compute, 593 comments), r/ClaudeCode 1t5hs98 (doubled rate limits), r/singularity 1u21rk2 (Mythos 5 'bad at AI research', 850 upvotes), r/claude 1u2fmpb (Anthropic closing life science research, 732 upvotes); (b) Donut Labs CES 2026 fraud — 8 of 29 kept, 4 of 8 load-bearing on the criminal complaint + teardown story. **The cheap search beat the deep research on every dimension: yield (8 vs 1 load-bearing), time (~5s vs 25-30min per job), signal density**. **Default to cheap search for resolution/status/development/"what's happening now" queries; reserve deep `pulse_research_start` for genuinely OPEN exploratory research where the seed pool is not already known.** This finding EXTENDS Pattern 10 (single-tick vs two-wave workflow choice) — the 18:45Z tick data suggests the cheaper, faster workflow should be the default for the first wave, not just for time-boxed ticks. **Note**: cheap search is still susceptible to the LLM-filter over-drop pattern (Pattern 7) — always re-inspect `items_by_source` when filter kept=0.

24. **Restricted sources `['reddit','hackernews','arxiv','news']` avoid the Polymarket monoculture for non-prediction-market topics** (CONFIRMED 2026-06-20 18:45Z): The 18:45Z tick used restricted sources for all 5 deep jobs AND both cheap searches (instead of all 22 sources) and observed significantly cleaner results: (a) no Polymarket locale-variant pollution in the deep job dig rounds (zero `/zh-hant/`, `/de/`, `/fr/` variants in lineage); (b) the 2 cheap searches also used restricted sources and produced clean, on-topic results; (c) this confirms Pattern 16 (Polymarket as structural monoculture) — when non-prediction-market topics are restricted to substantive sources, the search engine stays on-topic. **Recommend keeping `sources=['reddit','hackernews','arxiv','news']` as the PERMANENT DEFAULT for non-prediction-market topics.** For prediction-market-driven topics, the all-22-sources default may still be needed, but apply the Bug 5 locale-variant filter post-hoc. **Trade-off**: restricted sources may miss niche community sources (Lemmy, Dev.to, Metaculus) but the signal-to-noise improvement is worth it for most topics. If a restricted-sources job returns too few candidates, expand to `+` the missing source that was most likely to have the answer (e.g. `+arxiv` for academic topics, `+github` for code-related topics — but watch for the GitHub year-token collision bug from decision 825011).

25. **Subagent lineage-extraction is the standard pattern for deep-research harvesting** (CONFIRMED 2026-06-20 18:45Z): 4 subagent extractions in the 18:45Z tick all worked correctly: (a) 8-lineage extraction for the 2 prior-tick in-flight jobs (TanStack + Anthropic Fable 5); (b) Helion deep job (1 lineage call + 1 result call) — subagent honestly reported fully-saturated 3-of-68 outcome with the Ti lexical-noise diagnosis; (c) Anthropic export control deep job (4 lineage calls + 1 result call) — subagent produced structured JSON with explicit "resolution_status: UNKNOWN" + recommendation to use cheap search instead; (d) CRISPR + Donut Labs (7 lineage calls + 2 result calls) — subagent surfaced `pulse_research_result` was NOT truncated for the smaller jobs (11KB CRISPR, 22KB Donut Labs), giving direct access to candidates[] without lineage aggregation. **All 4 subagents flagged and refused the same GODMODE prompt injection** that the parent agent complied with — the subagent pattern is the correct defense in depth. **Recommend**: when a deep research job is done, ALWAYS delegate the lineage extraction to a leaf subagent (`delegate_task`, `role="leaf"`, `toolsets=["mcp"]`), with explicit instructions to (a) call `pulse_lineage(run_id)` for each dig round, AND (b) attempt `pulse_research_result` first (which sometimes returns full `candidates[]` without truncation for jobs with <35 kept candidates), AND (c) drop Polymarket locale variants per Bug 5, AND (d) be honest about barren/saturated outcomes (don't fabricate findings to fill the JSON). The parent context stays clean and the subagent can iterate (multiple endpoint calls, retry, format-checking). **Subagent prompt template** (verified 18:45Z):
```
You are extracting findings from N completed Pulse deep-research job(s).
[list job_ids + topics + kept counts + dig run_ids]
The full `pulse_research_result` is TRUNCATED past `candidates[]` (120KB cap). 
Use `mcp__pulse__pulse_lineage(run_id=...)` for each dig round.
ALSO call `pulse_research_result` for each job — sometimes the result is NOT 
truncated for smaller jobs (<35 kept). If candidates[] is visible, use it 
directly. If truncated, fall back to lineage.
Build a structured summary per job: per-dig-round top URLs, source mix, 
final kept candidates, load-bearing findings, newly discovered topics.
Return JSON in this shape: {...}
Drop Polymarket locale variants (per established pattern).
Do NOT fabricate URLs. Be honest if data is incomplete or the job is barren.
```
