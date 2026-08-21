# Pulse Recon Patterns Observed (2026-06-13 through 2026-06-14)

## High-Value Source Combinations

| Source Pair | Why Valuable | Example Pattern |
|-------------|--------------|-----------------|
| Reddit + ArXiv | Community discussion + Academic papers | LocalLLaMA subreddit -> arxiv.org papers |
| Polymarket + YouTube | Prediction markets + Primary sources | SpaceX Starship market -> youtube.com/c/SpaceX |
| Lobsters + RSS | Tech commentary + Official announcements | Workplace LLM posts -> openai.com/index |

## Dig Lineage Quality Signals

When reviewing `pulse_dig` lineage output, prioritize URLs that:

1. **Lead to primary sources:**
   - `github.com` repos from Reddit self-hosted discussions
   - `arxiv.org/abs/` from Polymarket tech events  
   - `youtube.com/c/CHANNEL` from SpaceX/Polymarket
   - `openai.com/index/*` - Product/security announcements

2. **Skip generic navigation:**
   - `/tos`, `/privacy`, `/careers` - Polymarket boilerplate
   - Language variants `/es/`, `/fr/`, `/de/` - Duplicate content
   - `/api/og`, `/api/*` endpoints - Metadata, not content

3. **High engagement markers:**
   - Reddit posts with `num_comments > 500` and `score > 100`
   - ArXiv papers with `citations > 0` (from metadata)
   - Lobsters posts with `comments > 20`
   - RSS/OAI feed items with recent publication dates

## Search-to-Dig Workflow

```
pulse_search(topic, use_cache=true)  # Fast 5-10s
  -> ranked_candidates[0:5] with high relevance + engagement
  -> pulse_dig(topic, seed_report=specific_urls, max_rounds=3)
  -> Extract new topics from child URLs containing actual content
```

## Hybrid Sync-Async Workflow (Cron Ticks)

For cron jobs that must produce output within time window:

```
# Start async deep jobs for background processing
pulse_research_start(topic, depth='deep', lookback_days=45, max_fetches=200, max_wurm_rounds=2)

# While jobs run, immediately get quick results
pulse_search(topic, llm_filter_top_n=20, lookback_days=60, max_per_round=30)

# Poll async status periodically (every 60s)
pulse_research_status(job_id)

# On timeout: continue with other work, jobs persist in background
pulse_research_result(job_id)  # Get results when ready
```

## Topic Discovery Patterns

Topics that surfaced in dig lineage worth following:

- **Security + AI:** kevlar-benchmark, CyberGym-E2E, GPT-5.4-Cyber
- **AI Psychology:** Workplace LLM delusion, ChatGPT psychoanalysis, gaslighting
- **Hardware + Low-Power:** 60fps E-Ink monitors, Modos Flow
- **Legal + AI:** Google AI Overviews liability, Moltbook lawsuit
- **Supply Chain:** AUR infostealer attacks, Anubis comment system
- **Scientific Benchmarks:** FrontierScience, HealthBench evaluation frameworks

## Session 2026-06-13 Additional Patterns

### ArXiv Category Correlation
- **cs.CL + cs.AI** - Computational Linguistics reasoning papers (high relevance for AI agents)
- **quant-ph** - Quantum physics theory papers (experimental/cutting edge)
- **cs.RO** - Robotics papers (sim2real, manipulation, vision-language integration)
- **cs.CR + cs.IR** - Cybersecurity + Information Retrieval (threat intel, TI feeds)

### Reddit Community Signals
- **r/cybersecurity** - Security frameworks, GitHub repos, low engagement (16 score, 5 comments) but high technical value
- **r/ArtificialInteligence** - Robotics breakthroughs, viral content (755 score, 149 comments)
- **r/ClaudeAI** - Agent discussions, source code leaks, community feedback on bugs

### Topic Depth Patterns Observed
- Topics with specific paper mentions (arXiv URLs) yield higher-value dig results
- Topics with "framework" or "protocol" in the query surface code repositories
- Topics with legal/regulatory angle surface from Lobsters + news sources
- Topics mixing technical + social angles (AI+legal, quantum+computing) show multi-source diversity

### MCP Recovery Pattern
When heartbeat_age_seconds > 100s on a running job:
1. Job may be stuck in dig phase - let it continue async
2. Immediately switch to pulse_search for alternative quick results
3. Check status on next tick - jobs often complete after extended periods
4. Jobs with high growth_pct (>70%) in dig-1 typically complete successfully

### Cron Tick LLM Filter Notes (2026-06-13)
- Deep jobs with llm_filter=true kept 11-118 candidates (expected filtering)
- Some topics return very few results (60fps E-ink kept only 1 of 265)
- Low yield may indicate topic is too narrow or novelty has faded - broaden query or use broader time window

### pulse_dig Timeout Risk (2026-06-13)
- `mcp__pulse__pulse_dig` has 120s hard MCP timeout
- During MCP backoff periods, skip manual dig calls entirely
- Let wurm rounds in pulse_research handle deep crawling
- Error: "MCP call timed out after 120.0s" - indicates server under load, not topic unavailability

## Session 2026-06-14 New Patterns

### pulse_search LLM Filter Behavior
- `llm_filter=true` can be overly aggressive - 0/24 candidates passed in test on "multi-agent evaluation frameworks"
- Solution: Use `llm_filter=false` or `llm_filter_top_n=20` to preserve candidates
- `depth='deep'` times out after 120s - use `depth='default'` for cron reliability
- `depth='default'` completes in ~15s with good candidate coverage

### pulse_dig Result Filtering (2026-06-14)
- Results can be 400KB+ JSON requiring post-processing
- Generic web pages dominate (GitHub nav, Play Store, career pages, privacy policies)
- Filter by source: prefer github, reddit, hackernews, arxiv, lobsters, rss
- Skip web.archive.org, itunes.apple.com, play.google.com (navigation/meta pages)
- Filter by title length: skip titles under 10 characters

### pulse_remember for Discoveries (2026-06-14)
- Label format: `discovery:pulse-wurm-YYYYMMDD_<hash>` (e.g., `discovery:pulse-wurm-20260614-cfmultiagent`)
- Content should include: topic, URL, summary, source seed, findings
- Salience value: 0.4 for discovery memories

### Key Discoveries (2026-06-14)
| Memory ID | Topic | URL | Summary |
|-----------|-------|-----|---------|
| 708485 | Claude Code deployment | github.com/Logos-Flux/cloudflare-multiagent | Multi-agent AI platform on Cloudflare Workers (v0.1.x public preview) |
| 708486 | Agent orchestration | github.com/moazbuilds/CodeMachine-CLI | Open-source CLI orchestrating AI coding agents into repeatable workflows |
| 708487 | Multi-agent evaluation | github.com/carrollr01/agent-adoption-research | Scheduled Claude Code routine mining X, Reddit, HN for SMB deployment case studies |