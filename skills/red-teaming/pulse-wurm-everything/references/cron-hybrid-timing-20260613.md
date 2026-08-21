# Cron Tick Hybrid Timing Patterns - Session 2026-06-13

## Observed Job Timing

| Job Topic | Candidates | Dig-1 Growth | Dig-2 Growth | Status | Time Elapsed |
|-----------|------------|--------------|--------------|--------|--------------|
| quantum computing breakthrough energy teleportation 2026 | 156 agg | 180% (72) | 61% (44) | ✅ complete | 468s |
| AI hardware chip architecture NVIDIA AMD Intel quantum | 160 agg | 155% (62) | 94% (58) | ✅ complete | 473s |
| cryptography zero-knowledge proofs blockchain privacy protocols | 185 agg | 197% (79) | 85% (67) | ✅ complete | 459s |

## Key Patterns

### MCP Timeout Behavior
- All pulse tools subject to 120s MCP timeout
- Jobs with `llm_filter=true` almost always hit timeout due to sequential phases:
  1. search-start
  2. search (fetch candidates)
  3. dig-1 (follow links)
  4. dig-2 (follow more links)
  5. llm-filter (reduce candidates)

### Hybrid Strategy That Works
```
# Step 1: Start async deep jobs (non-blocking)
pulse_research_start(topic, depth='deep', lookback_days=45, max_fetches=200, max_wurm_rounds=2)

# Step 2: Immediately get quick results while deep jobs run
pulse_search(topic, llm_filter_top_n=20, lookback_days=60, max_per_round=30)

# Step 3: Poll for deep job completion
pulse_research_status(job_id)  # Every 60s
pulse_research_result(job_id)  # When state='done'
```

### What Actually Works for Cron Ticks
1. **Don't block on deep jobs** - they take 460+ seconds (7+ minutes)
2. **Use pulse_search as fallback** - gets immediate cached + live results
3. **Keep candidate count low** (llm_filter_top_n=20) to avoid overwhelming output
4. **Multiple source queries increase timeout risk** - 8+ subqueries can exceed 120s
5. **Jobs persist across ticks** - can harvest results on subsequent runs

### Dig Quality Signals (High-Value URLs)
From lineage analysis, these URL patterns yield substantive content:
- `polymarket.com/event/deepseek-confirmed-to-have-used-banned-nvidia-chips` - prediction markets with engagement
- `r/CryptoMoonShots/comments/1rcefcb/` - recent privacy protocol discussion (Feb 2026)
- `r/ergonauts/comments/mye6xh/faq` - community engagement (357 score)
- `arxiv.org/pdf/` - direct PDF research papers
- `dev.to/` - technical articles with tags

### Low-Value URL Patterns (Skip These)
- `/tos`, `/privacy`, `/terms` - generic legal pages
- Language variants `/es/`, `/fr/`, `/de/`, `/zh-hant/` - no new content
- Navigation pages `/tech`, `/finance`, `/crypto` - index pages
- Social media aggregates without specific engagement

### Actual Findings Example
From crypto/ZKP research, these topics surfaced:
- BlackBox cross-chain confidentiality protocol (avoids privacy-tax tradeoffs)
- CKBuilders ZK grassroots developer initiative (65+ young builders)
- Sigma and Lelantus privacy protocols (next-gen Monero alternatives)
- ChainCash elastic peer-to-peer money protocol
- LITHOS Protocol decentralized PoW mining pool