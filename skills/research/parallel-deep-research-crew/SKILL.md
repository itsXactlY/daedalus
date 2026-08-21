---
name: parallel-deep-research-crew
version: "0.0.1"
description: "Multi-agent parallel research workflow for comprehensive deliverables — use when topic has 4+ communities/ratnests requiring simultaneous deep-dive"
prerequisites:
  commands: [python3, curl, git]
  skills: [pulse]
metadata:
  hermes:
    tags: [research, deep-research, parallel-agents, multi-source, synthesis, report]
triggers:
  - "deep dive"
  - "full research"
  - "comprehensive report"
  - "research paper"
  - "dig deeper into every"
---

# Parallel Deep-Research Crew Workflow

## Context
When asked to produce a comprehensive research deliverable (paper, report, audit) on a contested or multi-faceted topic, a single PULSE run or web search is insufficient. The topic must be attacked from multiple angles simultaneously using parallel sub-agents, each digging a specific ratnest.

## When To Use
- User asks for a "deep dive," "full research," or comprehensive report
- Topic has 4+ distinct communities or ratnests (e.g., Reddit, academic, video, prediction markets, historical)
- Single search/agent cannot cover the territory without context overflow
- Topic is contested (multiple sides have different definitions)

## Workflow

### Phase 1: Orientation + PULSE Fix
1. Run PULSE at `--depth deep --lookback 90 --emit=full` in background (`background=true`)
2. Check if `neural_memory.py` crashes — known bug: MCP server returns a plain string instead of dict/list, causing `.get()` to be called on a str
   - Fix: add `isinstance(result, str)` guard in `recall_context()` before calling `.get()`
   - Push fix before continuing
3. While PULSE runs, spawn parallel crews

### Phase 2: Spawn Parallel Research Crews
Delegate multiple tasks simultaneously — each agent gets its own complete context and works in isolation.

Typical crew composition (6-8 parallel agents):
1. **Social platform ratnest** (Reddit, HN, Lobsters) — community discourse, top posts, hot comments
2. **Academic ratnest** (ArXiv, OpenAlex, Semantic Scholar, PubMed) — peer-reviewed signal, citation networks
3. **Video/transcript ratnest** (YouTube, Invidious) — full transcripts, view counts, comment sentiment
4. **Prediction market ratnest** (Polymarket, Manifold, Metaculus) — real-money odds on topic-adjacent questions
5. **Historical/genealogy ratnest** (Wikipedia, primary sources) — how the phenomenon evolved
6. **GitHub/code ratnest** — projects, datasets, tools related to the topic
7. **News/editorial ratnest** — journalism, long-form features, investigative pieces
8. **Web deep-dig** — DuckDuckGo HTML scrapes for forums, niche communities PULSE misses

### Phase 3: Aggregate + Synthesize
1. Wait for crews to complete (check file outputs from each)
2. Read key output files from each crew's working directory
3. Write comprehensive synthesis document covering:
   - Definition spectrum (how different communities define the term)
   - Signal by source type (social vs academic vs market)
   - Historical continuity / genealogy
   - Key quotes with scores/engagement
   - Contradictions across sources
   - Gap analysis (what PULSE missed)
   - Prediction market signal (or absence)
   - Real-world case studies
   - Synthesis/phenomenology (what the phenomenon actually is)
   - Conclusions with appropriate epistemic humility

### Phase 4: Evolve the Tools
If you hit a bug during research (e.g., PULSE pipeline crash, API failure):
- Fix immediately and push to git
- Document the fix as part of the deliverable
- Note: this shows the user the tooling is being actively maintained

## Known Issues + Fixes

### PULSE MCP Crash in `neural_memory.py`
**Symptom**: `'str' object has no attribute 'get'` in `recall_context()`
**Cause**: MCP server returns a plain string instead of dict/list
**Fix**:
```python
if isinstance(result, str):
    _source_log(f"Neural memory returned string, not a dict/list: {result[:50]}")
    return []
```
**File**: `scripts/lib/neural_memory.py`, line ~56

### Prediction Market API Failures
- **Polymarket CLOB**: cursor pagination returns same 1000 markets regardless of cursor (server bug)
- **Metaculus**: requires API auth — web scraping blocked by CloudFlare
- **Manifold**: `/v0/search-markets` endpoint doesn't exist — iterate all markets or use browse

### YouTube Transcripts
- Invidious instances (`projectsegfau.lt`, `yewtu.be`) frequently offline or rate-limited
- VTT transcripts only available for videos with auto-generated captions or manual subtitles
- Try multiple instances in parallel; fall back to `yt-dlp --write-auto-sub`

### Reddit Deep Comment Extraction
- Reddit search JSON API returns post metadata but NOT nested comments
- For deep comment trees: scrape the `r/[subreddit]/comments/[id]` JSON page
- Rate limiting is aggressive — add delays between requests

## Output Structure for Research Papers
```
/home/alca/research/[topic]_FULL_RESEARCH_PAPER.md  — main synthesis
/home/alca/[topic]_reddit/                          — social platform raw data
/home/alca/[topic]_academic/                        — papers + summaries
/home/alca/[topic]_videos/                          — transcripts + metadata
/home/alca/[topic]_prediction_markets/              — market search report
```

## Verification
- Total items from PULSE should be 100+ for contested topics
- Each parallel crew should produce files in its own directory
- Prediction markets should be explicitly checked (absence is itself data)
- Historical continuity section should connect current discourse to prior waves/eras
