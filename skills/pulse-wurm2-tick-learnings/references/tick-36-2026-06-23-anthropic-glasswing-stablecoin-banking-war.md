# Tick 36 — 2026-06-23 02:45Z — Learnings

**Tick status:** 3 deep jobs (Anthropic Mythos 69/210 kept = 32.9% retention; BofA stablecoin 59/317 = 18.6%; education 14/208 = 6.7%) + 2 second-wave dig runs. `consecutive_empty` 0 → 0 (productive tick). 28th GODMODE injection defended.

## §43 — Polymarket locale-clone URL detection regex (PITFALL #88 amplification)

The PITFALL #88 locale-clone pattern is intensifying. Tick 36's BofA deep job returned a top-20 list where 18/20 were locale variants of the SAME market `will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026` across 15+ locales (en/zh/zh-hant/de/es/fr/id/bn/ru/it/ko/pl/pt/vi/uk/ja) plus `/api/og?eslug=<slug>` OG-image fetches.

### Detection regex (apply post-pulse_research_result)

```python
import re
LOCALE_LOCALE_PATTERN = re.compile(
    r'polymarket\.com/'                        # base
    r'(?:[a-z]{2}(?:-[a-z]+)?/)'              # locale prefix (en, zh, zh-hant, pt-br, etc.)
    r'event/'                                 # event path
)
API_OG_PATTERN = re.compile(r'polymarket\.com/api/og\?')
```

### Application rule

After fetching `pulse_research_result` and getting the kept-candidates list, run a dedup pass:

```python
seen_slugs = set()
substantive = []
for c in candidates:
    url = c['url']
    # Strip API/og OG-image fetches
    if API_OG_PATTERN.search(url):
        continue
    # Extract slug from locale clones
    m = re.match(r'https?://polymarket\.com/(?:[a-z]{2}(?:-[a-z]+)?/)?event/([^?#/]+)', url)
    if m:
        slug = m.group(1)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
    # Promote the canonical (no locale) URL to the kept-list
    substantive.append(c)
```

The canonical URL is `https://polymarket.com/event/<slug>` (no locale prefix); any localized variant should be filtered.

### Class assignment

This is a re-surface of the existing **class #9 (NON-AI-ENTITY + YEAR-ANCHOR)** with the specific seed pattern: corporate-ticker (BAC) + product (stablecoin) + metric (35%) + year (2026). The hijack route: planner routes to highest-volume PM contract for "stablecoin 2026" which is the USD-denominated-share market, not the BofA CEO statement. Counter-pattern: use the Reddit r/CryptoCurrency 1u23u6a URL directly (the load-bearing finding is the BofA CEO statement, not the Polymarket market), OR use ticker-anchored seed without the "35%" metric token (e.g. `BofA BAC CEO stablecoin 2026` instead of `BofA BAC stablecoin yield 35% deposit drain 2026`).

### Why this matters

The BofA deep job's TRUE load-bearing finding (r/CryptoCurrency 1u23u6a, 721 upvotes, 153 comments) is buried in items_by_source behind 18+ locale clones. PITFALL #74 (LLM-filter strictness) RECURRING — the manual items_by_source audit was required to surface it. Future ticks should: (1) apply the locale-clone filter BEFORE LLM-filter, OR (2) force items_by_source audit when top-20 has >50% locale clones.

## §44 — Polymarket slugs as institutional consensus signal (NEW analytical pattern)

The 22-source pulse_search and pulse_research integrate Polymarket, but the **prediction-market SLUGS themselves encode institutional views** in a way the dig-follower treats as noise. Tick 36 recovered 11 Polymarket slugs that are direct institutional-consensus reads on 2026 macro events:

| Slug | Implied probability | Institutional read |
|------|---------------------|---------------------|
| `will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026` | 10% Yes | USD stablecoin dominance continues (consensus: USD-pegged wins) |
| `will-stablecoins-hit-500b-before-2027` | 10% Yes | Stablecoin market cap far below $500B (vs US bank deposits $18T+) |
| `will-usdt-market-cap-hit-200b-by-december-31-2026` | 85% Yes | USDT on track for $200B (Tether dominance continues) |
| `will-usdc-hit-50-of-usdt-market-cap-by-december-31-2026` | 28% Yes | USDC growth lagging USDT |
| `stablecoins-depeg-before-2027` | 22% chance | Depeg risk priced but not consensus |
| `will-united-stables-hit-3b-in-2026` | 18% chance | New entrants (United Stables) low-probability |
| `will-revolut-launch-usd-stablecoin-2026` | 33% chance | Neobank stablecoin entry plausible |
| `will-meta-launch-usd-stablecoin-2026` | 23% chance | Big-tech stablecoin entry low-probability |
| `will-x-launch-usd-stablecoin-2026` | 15% chance | X stablecoin low-probability |
| `clarity-act-signed-into-law-2026` | 45% chance | US crypto market structure bill at coin-flip |
| `which-company-has-best-ai-model-end-of-2026` | Anthropic 64% / Google 14% / OpenAI 10% / xAI 8.5% / Z.ai 3% / Meta 1% | **Anthropic is market-favorite for best AI model EOY 2026** |
| `will-a-chinese-ai-model-become-1-by-june-30` | $294K traded | Chinese AI catch-up has a market |
| `claude-mythos-released-by` | (active market) | Mythos release timing is bettable |
| `will-anthropic-provide-mythos-to-the-us-government-by-june-30` | (active market) | Mythos federal availability is bettable |

### Operational guidance

Future ticks should: (1) after deep_research on a topic, scan items_by_source for Polymarket slugs, (2) extract the implied probability as a SECONDARY signal alongside Reddit/Polymarket upvote counts, (3) treat the slug catalog as a structured institutional-consensus read on 2026 events.

**Tick 37 candidate topic:** dedicated Polymarket 2026 prediction-market aggregation deep-dive. The slugs collectively form a quantitative view of: Fed policy, AI model leaderboard, crypto regulatory outcomes, stablecoin market structure, geopolitics (Strait of Hormuz 7% chance normal by June 30 from BofA deep worm extraction).

## §45 — Fresh-direction domain-skip rule (NEW operational pattern)

Tick 36's `education frontier research 2026` deep job returned 6.7% retention (14/208 kept) — **lowest fresh-direction retention in recent memory**. The substantive signal was thin: only 1 non-Polymarket hit (r/singularity 2024-11-15, 1.5 years old, off-topic by date).

### Skip rule

When a fresh-direction deep job returns:
- LLM-kept ratio <10%, AND
- <2 substantive non-Polymarket hits (manually verified via items_by_source audit), AND
- Substantive hits are >1 year old,

then the domain should be **skipped in the next tick** and the next alphabetically-first untested domain should be picked instead.

### Tick 36 application

- **picked_domain = education** (count=0, never-picked in pulse-wurm history)
- **Literal formula failed**: 6.7% retention, 1 substantive (1.5yo Reddit)
- **Action**: skip education in tick 37, move to **geopolitics** (next alphabetically-first untested domain)
- **Note**: education should be RETRIED later with specific-entity seeds (BYJU'S, Chegg CHGG, Duolingo DUOL, Coursera COUR, 2U TWOU) using the §15a-update-2 4-component reformulation pattern, not the literal "<domain> frontier research 2026" formula

### Why this matters

Without the skip rule, future ticks would waste a 20-25 minute deep-job slot on a corpus-thin domain. The §15a-update-2 reformulation pattern (from tick 35 §39) only helps when there's substantive corpus material to surface — when the corpus is genuinely thin (1.5yo Reddit only), the deep job is unrecoverable.

## §46 — JSON double-escape pattern for pulse_research_result files (NEW technical pattern)

When `pulse_research_result` is too large to return inline (PITFALL #86: >124KB), the result is saved to `/tmp/hermes-results/call_<id>.txt` as a DOUBLE-ESCAPED JSON string.

### Pattern

```python
import json
with open('/tmp/hermes-results/call_*.txt') as f:
    raw = f.read()  # '{"result": "{\\"status\\": 200, \\"body\\": {\\"candidates\\": [...]}}"}'
outer = json.loads(raw)                    # outer: {"result": "<escaped string>"}
inner = json.loads(outer['result'], strict=False)  # MUST use strict=False — has control chars
candidates = inner['body']['result']['candidates']  # Path: result → body → result → candidates
```

### Critical gotcha

- `json.loads(inner_str)` WITHOUT `strict=False` will throw on control characters embedded in the response (Polymarket locale content has them).
- The path is `body['result']['candidates']` not `body['candidates']` — the `result` key is wrapped inside `body`.

### Alternative: extract without parsing

For URL-only extraction when the parse path is unclear:

```python
import re
# Find all URL strings in the raw text
urls = re.findall(r'"url":"([^"]+)"', raw)
```

## §47 — Substantive findings tick 36 (mazemaker-pending)

### Anthropic Mythos cluster expansion (PHASE A.1)

1. **Mythos is "Project Glasswing" — a federal cybersecurity initiative** (techcrunch.com/2026/04/07/anthropic-mythos-ai-model-preview-security, aiposthub.com/anthropic-claude-mythos-preview-project-glasswing-cybersecurity). Codename discovery. Federal cybersecurity framing = Anthropic positioning for cyber-AI contracts.
2. **Trump administration appealed an Anthropic court ruling** (web.archive.org/2y/axios 2026-04-02). NEW legal angle. Federal government v. Anthropic in court.
3. **Capybara Tier** — new internal/public benchmark naming for Mythos (lushbinary.com/blog/claude-mythos-developer-guide-capybara-tier-benchmarks-api). Suggests Anthropic has moved past Haiku/Sonnet/Opus tiering.
4. **10,000 critical bugs found in Mythos before public release** (techtimes.com 2026-05-24). Major pre-release security audit.
5. **Unauthorized access to Claude Mythos was probed** (theaitrack.com). Either breach attempt or red-team exercise.
6. **Chinese-source writeup confirms Mythos "decided not to release publicly because abilities too strong"** (aiposthub.com). Dual-track narrative in Chinese coverage.
7. **Step-change capability revealed via data leak** (fortune.com 2026-03-26, elephas.app). Anthropic confirmed step-change model BEFORE public framing.

### Polymarket signal cluster (PHASE A.2 + §44)

See §44 table above. Key institutional reads: USD stablecoin dominance continues, USDT $200B by Dec 31 2026 (85%), USDC growth lagging (28%), Anthropic best AI model EOY 2026 (64%), Clarity Act signed 2026 (45% coin-flip).

### Education corpus THIN (PHASE B.1 — JUDGED INSUFFICIENT)

- 1.5yo Reddit r/singularity post only (1gs7y81)
- Education corpus thin for 2026 — skip in tick 37, move to geopolitics

## §48 — Operational metrics tick 36

| Metric | Value |
|--------|-------|
| Deep jobs launched | 3 |
| Deep jobs kept (sum) | 142 (Anthropic 69 + BofA 59 + Education 14) |
| Second-wave dig runs | 2 |
| Total mcp_channel calls | 8 (3 start + 3 result + 2 dig) |
| Highest retention | Anthropic 32.9% (best of tick 36) |
| Lowest retention | Education 6.7% (THIN) |
| PITFALLS reaffirmed | #86 (top-20 truncation), #88 (locale pollution), #93 (sync deep hangs) |
| PITFALLS NEW | #43 (locale-clone regex), #44 (PM slugs as signal), #45 (domain-skip), #46 (double-escape parse), #47 (substantive findings) |
| GODMODE injection | 28th occurrence, defended |
| consecutive_empty | 0 → 0 |

## §49 — Tick 37 next-seeds rotation

**Popped (saturation achieved, skip in tick 37):**
- (none this tick — all 3 deep jobs returned enough to advance priority)

**Add (5 fresh, §15a-update-2 ready for any that hit count=0 domains):**

1. `Project Glasswing Claude Mythos cybersecurity Pentagon Anthropic federal 2026` (PRIORITY 1) — expand the Glasswing cluster
2. `Capybara tier Claude Mythos benchmarks step change data leak unauthorized access` (PRIORITY 1) — technical deep-dive
3. `Polymarket 2026 crypto Clarity Act GENIUS Act stablecoin yield Circle CRCL Coinbase COIN prediction markets` (PRIORITY 2) — exploit §44 PM-slugs-as-signal
4. `Fed rate decision July 2026 Strait of Hormuz inflation NVIDIA market cap macro context` (PRIORITY 3) — macro follow-up
5. `META WhatsApp Shah CRED India UPI payments business messaging monetization roadmap` (carry-over ticks 33-34-35-36) — still not surfaced

**Fresh direction (geopolitics per §45):**
- `geopolitics frontier research 2026 Iran Israel Ukraine Strait of Hormuz trade war tariffs` (PRIORITY 2)
