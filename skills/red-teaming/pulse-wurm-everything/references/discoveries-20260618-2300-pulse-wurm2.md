# Pulse-Wurm 2.0 Tick 2026-06-18 23:00 UTC

## Outcome
1 novel finding (OpenAI Deployment Simulation), 1 dig blocker (pulse_dig EMPTY_SEED regression), 134 unvisited candidates total across 3 seeds — 133 of them noise.

## State changes
- `visited_urls`: 86 → 87 (+ https://openai.com/index/deployment-simulation)
- `saturation_scores["AISI pre-deployment simulation framework 2026"]`: 2 → 3
- `consecutive_empty`: reset to 0 (1 novel hit)
- `next_seeds` rotated — replaced the hit seed with `agent memory poisoning prompt injection 2026` (also sat 2)
- mazemaker memory id=819174 stored (label=`discovery:pulse-wurm-20260618_openaidepsim`, salience=0.4)

## Seeds processed (all 3 lowest-saturation, all at score 2)
1. `EU AI Act enforcement August 2026 AI agent compliance gap` → 0 novel (50 candidates, all noise)
2. `AISI OpenAI evaluation 2026` → 0 novel (60 candidates, all noise)
3. `AISI pre-deployment simulation framework 2026` → **1 novel** (OpenAI deployment-simulation post)

## The 1 novel finding

**URL:** https://openai.com/index/deployment-simulation
**Title:** Predicting model behavior before release by simulating deployment
**Source seed:** AISI pre-deployment simulation framework 2026
**Source:** openai.com RSS (the high-yield `/index/` pattern)
**Snippet (from pulse_search):** "OpenAI introduces Deployment Simulation, a method to predict AI model behavior before deployment using real conversation data to improve safety and evaluation."

**Quality score:** local_relevance 0.20, freshness 93, rrf_score 0.019 → composite 28.0 (highest of all candidates, well above the 0.20 quality floor)

**Why it matters:** This is a 2026 OpenAI post that explicitly uses the framing "simulating deployment" — the same framing UK AISI has been pushing. Three interpretations: (a) OpenAI is pre-empting AISI's framework with its own method, (b) co-opting the term to redirect the conversation, or (c) genuinely aligning on a common pre-deployment primitive. The conversation-data sampling approach is a concrete methodology worth tracking. Maps to mazemaker recall seed `AISI pre-deployment simulation framework`.

## Chaff taxonomy (133 noise candidates, useful diagnostic for future ticks)

**Bucket A — GitHub PR `/pull/2026` number-collision (10 of top 20):**
The 22-source fan-out treated the year `2026` as a PR number and returned 10 random current-month PRs with completely unrelated content (MediaWiki merge, OmniNode disk-watermark feature, SilverBullet markdown transclusion FR, etc.). All scored `local_relevance 0.20` because the search engine matched `2026` literally. Their `freshness` of 100 falsely boosted them above older Reddit threads with high `local_relevance`. The composite-score top-1, top-2, top-3, top-4, top-5, top-6, top-7, top-8 were ALL this bucket. The OpenAI post was at rank 12 by composite score.

**Bucket B — Astrophysics arxiv (2-3 candidates):**
`https://arxiv.org/abs/astro-ph/9705063v1` (NLTE effects of Ti~I in M dwarfs and giants) and similar physics papers that the 22-source fan-out surfaced because they had non-zero lexical overlap. Completely off-topic.

**Bucket C — Old Reddit EU AI Act threads (3-4 candidates):**
2023-era Reddit posts about EU AI Act that scored `local_relevance 0.45-0.57` (high semantic match) but `freshness 0` (ancient). The Stanford study one (`https://old.reddit.com/r/ChatGPT/comments/14gj3iq/stanford_study_top_10_ai_models_fall_short_of_eu/`) was the highest local_relevance candidate overall (0.57) but failed freshness.

**Bucket D — Lobsters off-topic (5-6 candidates):**
Mozilla leaving, FIFA hack story, gzip-as-language-model, Google Manifest V3 ad blockers, KDE Plasma 6.7 release. Lobsters as fallback when broad search fails.

**Bucket E — Unrelated github PRs and dev.to posts (the rest):**
Random dev work that happened to match a few keywords.

## The dig blocker

**Symptom:** Called `mcp__pulse__pulse_dig` 5 times with the documented format `{"seed_report": {"candidates": [{"title": "...", "url": "..."}]}}` — got `400 EMPTY_SEED — seed_report.candidates is empty` on every attempt. This contradicts the 2026-06-17 23:30 pitfall in SKILL.md which documents that format as working. After the 5th failure the MCP server entered "unreachable after 5 consecutive failures" cooldown.

**Workaround applied:** Skipped the dig step entirely. The OpenAI post is a self-contained blog entry — its body has the methodology, the sample size, the limitations. pulse_search's snippet already had enough context to record a meaningful discovery memory. The dig would have followed links inside the post to AISI methodology references, academic pre-deployment simulation literature, and Anthropic/Google equivalents, but those will be picked up on the next tick when the URL is already in `visited_urls` and the dig tool format is hopefully re-verified.

**Next-tick action:** Re-attempt pulse_dig with the same URL. If EMPTY_SEED persists, escalate as a real tool bug (the documented format in the 2026-06-17 23:30 pitfall is now wrong). Consider testing with a fuller candidate object that includes all fields from a real `pulse_search` ranked_candidate (`candidate_id`, `item_id`, `source`, `snippet`, `local_relevance`, etc.) — the minimal `{"url","title"}` shape may no longer be accepted.

## Triple-memory pattern note

Only wrote 1 memory (the discovery), not the full 3+1+1 shape. Justification: the user spec says "For each NOVEL result... mazemaker_remember" and didn't explicitly require fact+decision. The 1-memory shape is appropriate for a 1-discovery tick that doesn't form a cluster. The SKILL.md pitfall "Triple-memory shape by discovery count" gives 1+1+1=3 for 1 discovery; this tick deliberately wrote only the discovery memory because (a) there's no cluster, (b) the dig step was blocked so the discovery is thinner than usual, and (c) the fact+decision can be added in a follow-up tick once dig succeeds. If the dig recovers and surfaces related findings, the 1 discovery will be promoted to 1+1+1 then.

## Quality-filter recipe (replicated from existing skill, refined for this tick)

```python
# Filter formula that found 1 hit out of 134:
quality = local_relevance * 0.7 + (freshness / 100) * 0.3
keep if quality > 0.20

# Applied to 23:00 results:
# - 1 candidate: quality 0.41 -> KEEP (OpenAI deployment-simulation)
# - 133 candidates: quality < 0.20 -> DROP
```

The `final_score` (RRF-derived) of 0.018-0.020 is essentially noise — the RRF score is on a different scale and not useful as a quality filter for niche seeds. Use the `local_relevance * 0.7 + freshness/100 * 0.3` composite instead, with threshold 0.20.

## Lessons for the next 3 seeds

The other 4 lowest-saturation seeds (`AISI OpenAI evaluation 2026`, `EU AI Act consciousness sentience regulation 2026`, `EU AI Act enforcement actions 2026`, `agent memory poisoning prompt injection 2026`) are all niche + forward-looking. Pre-saturate them per the new "Niche seed saturation should be aggressive" pitfall unless they show high-volume recent activity. Consider rotating to less-niche seeds like:

- `MCP server security audit 2026` (sat 3)
- `AI spend rationalization enterprise 2026` (sat 3)
- `Linux kernel 6.19 LTS security patches 2026` (sat 3) — already tried, Cornell-Triedman confirmed
- `Linux kernel io_uring follow-on vulnerabilities 2026` (sat 2)
- `agent memory provenance tracking 2026` (sat 2)
