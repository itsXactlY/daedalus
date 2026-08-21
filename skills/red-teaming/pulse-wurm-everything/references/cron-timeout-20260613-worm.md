# Cron Tick Patterns for MCP Timeout Recovery - 2026-06-13

## Critical Session Findings

### MCP Timeout Hard Limit
- All pulse tools have **120s hard timeout** including `pulse_research_start` and `pulse_dig`
- This affects ALL pulse operations, including async job initiation
- During MCP cooldown/backoff periods (observed ~43-60s), ALL calls fail with "auto-retry available in ~43s" messages

### pulse_dig Timeout Risk
- `pulse_dig` timed out even with `max_fetches=200` and `max_rounds=2`
- **Recommendation:** Skip manual `pulse_dig` calls during cron ticks when MCP is under load
- Let the built-in wurm rounds in `pulse_research` handle the deep crawling instead

### Hybrid Cron Strategy (Proven)
```
1. Run pulse_search(topic, depth='default', lookback_days=90) for quick results
2. On timeout: continue with next topic - DON'T retry during same tick
3. Extract URLs from pulse_search results for lineage inspection
4. Use pulse_lineage(run_id) to get deep edges instead of pulse_dig
```

### pulse_lineage vs pulse_dig
- **pulse_lineage** (used after pulse_dig completes) returns structured edge data without timeout risk
- **pulse_dig** performs the deep crawl but can timeout during execution
- Better pattern: Run pulse_search, identify candidate URLs, let async jobs crawl them, poll lineage on next tick

### LLM Filter Yield Patterns (This Session)
- Quick searches with `llm_filter=true`: kept 5-7 of 15-30 candidates (30-50% retention)
- Very high yield when topic crosses multiple strong communities (Reddit + ArXiv + GitHub)
- Low yield when topic is narrow or dominated by one source type

### dig Quality Signals
- **High quality**: GitHub repos with direct README content, ArXiv paper abstracts
- **Low quality**: Generic landing pages, dashboard URLs, RSS feed boilerplate
- **Edge count indicator**: 100+ edges suggests deep traversal; <20 edges suggests shallow results

### Observed Topic Patterns That Worked Well
1. **Security + AI overlap**: "AI security threats 2026" - crossed Reddit, ArXiv, GitHub, Lobsters
2. **Quantum + verification**: "quantum error correction codes 2026" - surfaced RL-discovered codes, Dev.to papers
3. **Specific entities**: Topics naming specific projects (Pyison, QECLab) yielded better deep paths

### Dig Lineage Analysis
This session's lineage inspection revealed valuable downstream connections:
- Original article URL → GitHub repos → Security Lab cross-links
- Original article URL → Wayback archive versions → Related blog posts
- Original article URL → Mastodon/X posts → Researcher profiles

These connections would have been missed without lineage analysis.

### Recovery Pattern for Cron Ticks
```
# When pulse_research_start times out:
1. Immediately run pulse_search with depth='default' on same topic
2. Save discovered topics to file for next tick
3. Check pod health: pulse_health (should return 200 OK)
4. Wait for next tick (~15 min) and check pulse_research_status on previous job IDs
```

### File Output for Persistence
- Save report to `~/.hermes/pulse-wurm-report-YYYY-MM-DD.md`
- Save next topics to `~/.hermes/pulse-wurm-next-topics.json` with `discovered_topics` array
- This allows next tick to pick up where this one left off