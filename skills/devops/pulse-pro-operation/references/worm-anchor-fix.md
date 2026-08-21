# Wurm Anchor-Filter — the fix for seed-drift / off-topic results

## Symptom
`/research` (wurm) returns 400+ candidates but they are off-topic: Reddit
relationship drama, Arxiv "Ti"=Titan metallurgy papers, Polymarket GPU-price
bets, Google sign-in pages. dig rounds show healthy growth (+80/round) so the
crawler works — it is just digging the WRONG hole.

## Root cause
The WormCrawler (`scripts/lib/worm.py`) follows href links from seed pages with
no topic lock. The Search phase feeds junk seeds (heuristic matched "Ti" → Titan
metallurgy; a `w3.org` host allow-list → "XHTML namespace"). Off-topic seeds
breed off-topic children.

## The fix (3 filter points + strict host list)
Three places must enforce the topic anchor — guarding only the children is NOT
enough; the roots (search results) must be filtered too.

1. **`WormCrawler.__init__`** gets `topic_anchor: str`. Build two sets:
   - `_anchor_kw` = topic tokens len>=4 minus stopwords, PLUS bigrams of
     adjacent non-stopword tokens (e.g. "gpu instancing", "scene graph").
   - `_anchor_hosts` = STRICT list — only WebGL/GPU-specific doc/repo hosts:
     `developer.mozilla.org, threejs.org, three.js, webglfundamentals.org,
     webgpu.com, khronos.org, docs.gl, gamedev.net, shadertoy.com, pixijs.com,
     babylonjs.com, playcanvas.com, web.dev, developer.chrome.com,
     gpuweb.github.io`.

2. **`_harvest_urls`** (in worm.py): after building `unique`, drop any URL whose
   target fails `_is_on_topic(u.url, u.url)`.

3. **`_fetch_round`** (in worm.py): AFTER a page is fetched (has title/body),
   reject it if `_is_on_topic(title+description+body[:4000], url)` is False —
   before it can be appended as a candidate / next-round seed.

4. **`crawl()`** (in worm.py): BEFORE setting `frontier`, filter the INITIAL
   `seed_candidates` the same way (title+snippet+url). This is the missing v1
   step — without it, junky search results seed the whole dig.

5. **`pod/pulse_pod/app.py`** `research()` / `_research_impl()`: a PRE-WORM
   anchor-filter right after the Search phase (before the Wurm loop). Same
   `_anchor_kw` / `_anchor_hosts` logic. Emits a `{"phase":"anchor-filter",
   "dropped":N,"kept":M}` phase so you can see it working in the job status.

`_is_on_topic(text, url)`: True if url host ∈ `_anchor_hosts`, OR any
anchor_kw (word or bigram) is a substring of `text.lower()`.

## Host allow-list WARNING
Do NOT put generic hosts (`arxiv.org`, `github.com`, `w3.org`,
`stackoverflow.com`) in `_anchor_hosts`. They bypass the text check, so
"Titan metallurgy" papers and "XHTML namespace" slip through. Keep the list to
WebGL/GPU-specific hosts ONLY.

## Verification
A good run shows: `anchor-filter` phase (dropped 40 kept 20), then dig-1..6 each
+50..+90, final candidates from threejs.org / webgpu.com /
developer.mozilla.org — NOT Reddit / Arxiv-Ti.
