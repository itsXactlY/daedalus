# Anthropic Frontier Model Snapshot — 2026-06-20

This reference captures the Anthropic / Mythos / Claude Opus 4.8 / Project Glasswing / $65B raise story. Use as the canonical knowledge bank for any future Anthropic-related query, and as the source of truth for future Mythos / Opus / Glasswing dig seed formulation.

**Latest update: 2026-06-20 22:23Z** — added Mythos benchmarks, pricing, 11 named Glasswing partners, 10K critical bugs specifics (CVE-2026-4747, OpenBSD 27yr), Mythos US Gov market resolution, and the "Mythos is general-purpose (NOT cybersecurity-trained)" confirmation. See the 22:23Z section at the bottom.

## Headline facts (as of 2026-06-20 21:05Z)

| Fact | Source | Date |
|---|---|---|
| Anthropic raised $65B at $965B valuation | Fortune | 2026-05-29 |
| Mythos promised "wide release in coming weeks" | Fortune raise announcement | 2026-05-29 |
| Claude Opus 4.8 released | Fortune raise announcement | 2026-05-29 |
| Mythos data leak reveals existence | Fortune | 2026-03-26 |
| Anthropic: "step change in capabilities" (re: Mythos) | Fortune leak-response story | 2026-03-26 |
| Mythos preview shown to security teams | TechCrunch | 2026-04-07 |
| 10,000 critical bugs found in pre-release testing | TechTimes | 2026-05-24 |
| Anthropic Fable 5 + Mythos 5 US takedown | ETVBharat / Indian News Network | 2026-06-13 |
| Anthropic: Fable 5 takedown is "misunderstanding, working to restore" | Indian News Network | 2026-06-13 |
| Anthropic engineers sent to Washington for Fable 5 deal | TechTimes | 2026-06-15 |
| Anthropic Fable 5 refunds issued | Forbes | 2026-06-14 |
| Anthropic IPO probability (Polymarket) | "Will Anthropic or OpenAI IPO first" market | 76% Yes |
| Mythos Polymarket markets (8+) | "claude-mythos-released-by", "will-anthropic-provide-mythos-to-the-us-government-by-june-30", "best-math-ai-model-end-of-june", etc. | Active 2026 |
| Mythos = ONLY Q2-Q3 2026 frontier release with active tradable PM markets | Cross-market comparison | Confirmed 21:05Z |
| Project Glasswing = Anthropic's pre-release cybersecurity program | aiposthub.com | 2026-04 (Glasswing active) |
| Claude Opus 4.7 (predecessor) | theaitrack.com | Pre-2026 |
| "Capybara Tier" (community label for Mythos API tier) | lushbinary.com dev guide | Informal, NOT Anthropic official |

## Headline facts added 2026-06-20 22:23Z

| Fact | Source | Date |
|---|---|---|
| Mythos benchmark: 93.9% SWE-bench Verified | Lushbinary developer guide | 2026-04-08 |
| Mythos benchmark: 77.8% SWE-bench Pro | Lushbinary developer guide | 2026-04-08 |
| Mythos benchmark: 94.6% GPQA Diamond | Lushbinary developer guide | 2026-04-08 |
| Mythos pricing: $25/M input tokens, $125/M output tokens | aiposthub.com (Chinese coverage of Glasswing) | 2026-04-09 |
| Mythos = general-purpose model, NOT cybersecurity-trained (per Anthropic) | TechCrunch, Anthropic | 2026-04-07 |
| Project Glasswing 11 named partners: AWS, Apple, Broadcom, Cisco, CrowdStrike, Google, JPMorganChase, Linux Foundation, Microsoft, NVIDIA, Palo Alto Networks | TechCrunch | 2026-04-07 |
| Glasswing: 40+ extended-access organizations beyond the 11 named | TechCrunch | 2026-04-07 |
| Glasswing funding: $100M model usage credits + $4M direct donations to OSS security orgs | aiposthub.com | 2026-04-09 |
| Mythos Preview distribution: Claude API, Amazon Bedrock, Google Cloud Vertex AI, Microsoft Foundry | aiposthub.com | 2026-04-09 |
| CVE-2026-4747: FreeBSD 17-year-old RCE, exploitable via NFS server (full system control without auth) | Anthropic Frontier Red Team tech report | 2026-05-22 |
| OpenBSD 27-year-old vulnerability (server hijack via a few bytes) | Anthropic Frontier Red Team tech report | 2026-05-22 |
| 10K+ high/critical vulns found by Mythos in first month across ~50 orgs | TechTimes, Anthropic May 22 update | 2026-05-24 |
| 99%+ of bugs found have NOT been publicly disclosed (patches haven't shipped) | Anthropic Frontier Red Team tech report | 2026-05-22 |
| Mythos US Government access resolved YES at all 3 Polymarket strike dates (Apr 30, May 31, Jun 30) | Polymarket "will-anthropic-provide-mythos-to-the-us-government-by-june-30" | 2026-06-20 |
| Anthropic IPO Closing Market Cap Polymarket: $645K single-market / $1.7M cumulative volume | Polymarket "anthropic-ipo-closing-market-cap" | 2026-06-20 |
| "Will Anthropic or OpenAI IPO first?" market: Anthropic 76% Yes | Polymarket | 2026-06-20 |
| Anthropic IPO = PM-only signal, ZERO SEC EDGAR direct coverage of S-1 filing | 22:23Z tick pulse_research | 2026-06-20 |

## Key named entities

- **Claude Mythos** — Anthropic's most powerful AI model. Existence revealed via data leak Mar 26 2026. Wide release promised "in coming weeks" as of May 29 2026 raise announcement. Capybara Tier = community label for the API tier, not official Anthropic term. **NEW 22:23Z**: Position 4th tier above Opus (Haiku/Sonnet/Opus/Capybara). Benchmarks: 93.9% SWE-bench Verified, 77.8% SWE-bench Pro, 94.6% GPQA Diamond. Pricing: $25/$125 per M tokens. Distribution: Claude API, Bedrock, Vertex AI, Foundry.
- **Claude Opus 4.8** — Released alongside the May 29 2026 raise announcement. Distinct from Mythos — the Opus line continues in parallel with the Mythos line. Anthropic shipping both tier-up (Mythos) and version-bump (Opus 4.8) for the API surface.
- **Project Glasswing** — Anthropic's named pre-release cybersecurity / bug bounty program. **NEW 22:23Z**: 11 named partner organizations (AWS, Apple, Broadcom, Cisco, CrowdStrike, Google, JPMorganChase, Linux Foundation, Microsoft, NVIDIA, Palo Alto Networks) + 40+ extended access. $100M model usage credits + $4M direct donations to OSS security orgs. Operative vehicle behind "10,000 critical bugs found" TechTimes May 24 figure. First Anthropic model released after a dedicated pre-release security program.
- **Mythos Preview = general-purpose (NOT cybersecurity-trained)** — Per Anthropic, Mythos's security capability is emergent from scale-driven reasoning and agentic coding, not from a security-specific training objective. Distinguishing it from prior AI security tools that assist human analysts. Mythos identified bugs autonomously — no human in the loop. This is the first time since OpenAI's 2019 GPT-2 staged release that a frontier lab voluntarily restricted a model's general availability for safety reasons.
- **Glasswing CVE examples** (per Anthropic Frontier Red Team tech report): CVE-2026-4747 (FreeBSD 17-year-old RCE, full system control without auth via NFS) + OpenBSD 27-year-old server hijack vulnerability. 99%+ of bugs found have not been publicly disclosed because patches haven't shipped.
- **Claude Fable 5** — Paired with Mythos 5 in the US export ban. Refunds issued. Anthropic claims "misunderstanding" and is negotiating restoration. Polymarket "Claude Fable 5 restored for US customers by July 1" at 69% Yes / $1M volume.
- **Claude Mythos 5** — Second model in the export-ban story, paired with Fable 5. Less covered than Fable 5 specifically.
- **Anthropic Defense Department lawsuit** — theaitrack.com headline. Specifics unknown; need pacer.gov / courtlistener.com lookup.
- **Alibaba Qwen 3.6 Max** — theaitrack.com preview mention. Competing frontier model. Worth a pulse query next tick.
- **Anthropic IPO S-1** — Not yet filed as of 2026-06-20. Polymarket pricing the timing at 76% Anthropic-first vs OpenAI. S-1 will appear on SEC EDGAR with a new CIK when filed. Direct fetch SEC EDGAR full-text search for "Anthropic" weekly.

## Version cadence naming convention (multi-lab)

Pre-release frontier model codenames follow a fruit/vegetable naming convention across labs:
- Anthropic: `Fable 5`, `Mythos 5` (pre-release); `Opus 4.7`, `Opus 4.8` (production releases); `Capybara` (community label for Mythos API tier)
- Meta: `Mango`, `Avocado` (unreleased, per Yahoo Finance article)

"Capybara Tier" is an INFORMAL COMMUNITY LABEL for the Mythos API tier (per lushbinary.com dev guide), NOT an official Anthropic term. Anthropic has not publicly named Glasswing on anthropic.com/news — the program is in press-coverage scope only.

## OpenAI parallel

- **OpenAI GPT-5.5 Cyber** — parallel pre-release cybersecurity program using vetted security teams (theaitrack.com). Structural analog to Glasswing.
- **OpenAI GPT-6** — NO dedicated Polymarket market. Implied late 2026 / 2027 release.
- **OpenAI social network launch** — Speculation-only as of 21:05Z. ZERO direct news URLs in 70 kept / 327 candidates. PM cluster is the only signal. 2-6 week PM lead indicator pattern.

## PM market structure (capex vs model quality divergence)

- "Best AI model end of 2026": Anthropic 64%, Google 15%, OpenAI 11%, xAI 7.2%, Meta 2%
- "Best AI model end of June": Anthropic leading
- "Best math AI model end of June": Anthropic leading
- "Third best AI model end of July": Anthropic / OpenAI / xAI contested
- "Will Anthropic provide Mythos to US gov by June 30": **RESOLVED YES at all 3 strikes (Apr 30, May 31, Jun 30)**, $247K vol
- "Anthropic vs OpenAI higher valuation Dec 31": Active market
- "Will Anthropic or OpenAI IPO first": Anthropic 76% Yes, $172K vol
- "Anthropic IPO Closing Market Cap": $645K single-market / $1.7M cumulative vol (es locale shows higher)
- "Claude Mythos released by...": $880K vol, 3.25M cumulative across strikes

Market interpretation: Anthropic is winning the 2026 capex-vs-model-quality divergence — Polymarket bets Anthropic will have the best model while OpenAI dominates the IPO/raise market.

## Pulse research status per topic

| Topic | Pulse verdict | Recommended next-tick approach |
|---|---|---|
| Mythos launch date | Direct fetch anthropic.com/news — no PM cluster can resolve the actual release date | Direct fetch (pulse is wrong tool) |
| Anthropic raise terms | Direct fetch Fortune May 29 article body — lineage didn't surface terms | Direct fetch Fortune URL |
| Glasswing partners | Internal-program saturation (Pattern 27); 13/151 kept | Direct fetch anthropic.com if exists; aiposthub.com is the only authoritative aggregator |
| **NEW 22:23Z**: Mythos benchmarks + pricing | Surfaced via reduced-param second-wave | Now confirmed; future ticks use direct fetch (lushbinary, aiposthub) |
| **NEW 22:23Z**: Glasswing 11 named partners | Surfaced via TechCrunch via Mythos cluster | Now confirmed; future ticks use direct fetch (each partner newsroom) |
| **NEW 22:23Z**: Mythos US Gov access | Polymarket-only signal, $247K vol, resolved YES at all 3 strikes | Track for July 31 strike resolution |
| **NEW 22:23Z**: Anthropic IPO S-1 filing | PM-only signal, ZERO SEC EDGAR coverage (Pattern 27) | Direct fetch SEC EDGAR full-text search weekly |
| GPT-6 release | No PM markets exist; speculation-only | Wait for news; check OpenAI blog directly |
| Gemini 4 release | No PM markets exist; speculation-only | Wait for news; check Google I/O recap |
| Meta Mango/Avocado | 60% PM locale noise per Pattern 14 | Direct fetch Yahoo Finance + sec.gov EDGAR |
| Defense Dept lawsuit | Direct fetch pacer.gov / courtlistener.com | Direct fetch (pulse wrong tool) |
| Wide.ai (widelai.com) | New lab; surfaced via LushBinary footer only | Direct fetch widelai.com |

## Seed formulation patterns (for future Anthropic queries)

WORKED:
- "Anthropic 65 billion dollar raise 965 billion valuation Mythos Claude Opus 4.8 launch" → 52/151 kept (best second-wave job, direct fetch terms still needed)
- "Anthropic Claude Fable 5 export control lifted restored US customers July 2026" → 42/252 kept (excellent, 19 unique domains)
- **NEW 22:23Z**: "Anthropic Mythos step change Fortune exclusive + 10K critical bugs pre-release security + Glasswing program" → 19/141 kept, 6 substantive editorial pieces surfaced (Fortune + TechCrunch + TechTimes + Elephas + Lushbinary + aiposthub) — STRONGEST editorial cluster via reduced-param second wave
- **NEW 22:23Z**: "Anthropic Mythos release timing + OpenAI GPT-6 frontier model race 2026 Polymarket leaderboard Anthropic 64%" → 77/210 kept (36.7%), surfaced Fortune + TechTimes + 5 PM sibling markets

NOT WORKED:
- "Anthropic Project Glasswing cybersecurity Mythos pre-release bug bounty program" → 13/151 kept (internal-program saturation, only 1 direct URL found)
- **NEW 22:23Z**: "Anthropic IPO S-1 filing SEC EDGAR closing market cap $645K Polymarket 2026" → 37/165 kept (22.4%) but ZERO SEC EDGAR direct coverage — PM-only signal
- **NEW 22:23Z**: "AST SpaceMobile 2026 launch cadence + carrier partnership signings + 3-LEO constellation competitive landscape" → 2/292 kept (0.7%) — Pattern 27 null result, only 5+ year old r/wallstreetbets DDs

PARTIAL:
- "OpenAI social network consumer product launch 2026 Twitter competitor ChatGPT" → 70/327 kept but ZERO news URLs (speculation-only, all PM cluster)
- "Anthropic Mythos release vs OpenAI GPT-6 Gemini 4 frontier model benchmark 2026 leader" → 50/211 kept, Mythos-dominated (GPT-6/Gemini 4 don't surface in PM or news)
- **NEW 22:23Z**: "xAI Grok 5 Grok 6 release cadence + Colossus compute capacity + market share trajectory 2026 Polymarket 7.2%" → 57/200 kept (28.2%) but only 6 substantive after PM filter — AI lab with thin editorial substrate

For FUTURE ticks on Anthropic:
- Direct fetch anthropic.com/news first for any Mythos/Opus release announcement
- Direct fetch Fortune + Bloomberg + TechCrunch for any raise/funding/M&A story
- Skip pulse for internal programs (Glasswing-style) — direct fetch only
- Use PM category pages (polymarket.com/predictions/anthropic, polymarket.com/predictions/dario-amodei) as primary seeds for speculation-only topics
- **NEW 22:23Z**: For "step change" / "10K bugs" / "11 partners" anchor queries on specific numbers, the reduced-param second wave reliably surfaces the editorial cluster — this is now the recommended pattern for editorial-deep-dive queries where prior first-wave surfaced a known-good Polymarket seed

## PM locale filter recipe (RESOLVED 2026-06-20 22:23Z)

Apply the regex post-filter BEFORE treating any `pulse_research_result` candidates as substantive findings:

```python
import re
POLY_LOCALE_DROP = re.compile(r'https?://polymarket\.com/([a-z]{2}(?:-[a-z]+)?)/')
KEEP_LOCALES = {'en', 'es', 'pt-br'}
def is_polymarket_locale_noise(url):
    m = POLY_LOCALE_DROP.match(url)
    return bool(m and m.group(1) not in KEEP_LOCALES)
# candidates = [c for c in candidates if not is_polymarket_locale_noise(c['url'])]
```

Validated across 5 jobs on 2026-06-20 22:23Z tick. See SKILL.md Pattern 14 entry for full validation.
