# MCP Timeout Recovery Patterns - Observed June 2026

## Timeout Behavior
- MCP pulse tools have a **120 second timeout** for synchronous calls
- After 3 consecutive timeouts, the MCP server enters auto-retry backoff (~45-60s)
- During backoff, tool calls return: `"auto-retry available in ~43s"` message
- `pulse_health` and `pulse_quota` continue to respond during backoff

## Recovery Strategies

### Strategy 1: Hybrid Quick + Async
When deep research times out:
1. Fall back to `pulse_search(topic, use_llm=false, llm_filter=false)` - completes in 10-20s
2. Simultaneously launch `pulse_research_start(topic, depth='deep')` for background processing
3. Process quick results while deep job runs
4. On next tick, poll status of async jobs

### Strategy 2: Cache + Fallback Pattern
When MCP is in backoff:
1. Run `pulse_search(use_cache=true)` to get cached results quickly
2. Wait for backoff to expire (check via `pulse_health` returning "ok")
3. Resume normal deep research workflow

### Strategy 3: Direct REST Fallback
For sources like arXiv, HackerNews:
```bash
curl -s "https://export.arxiv.org/api/query?query=quantum+computing&start=0&max_results=10"
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json" | head -20
```
These bypass MCP entirely and return in <5s.

## Large Result Handling
When `pulse_search` returns >200KB of JSON:
- Result is saved to `/tmp/hermes-results/chatcmpl-tool-*.txt`
- Content is double-encoded: `codecs.decode(content, 'unicode_escape')` required
- Use regex to extract URLs and titles from JSON string:
  ```python
  urls = re.findall(r'https?://[^"'\'\]\s]{10,300}', content)
  titles = re.findall(r'"title":\s*"([^"]{20,200})"', content)
  ```

## Job Status Polling Pattern
```python
# For jobs that may still be running
status = pulse_research_status(job_id="...")
# Returns: state="running" or "done"
# Poll every 60s for long-running jobs
# heartbeat_age_seconds > 90s indicates stale job
```

## mazemaker MCP Fallback (2026-06-18 06:00)

`mcp__mazemaker__mazemaker_remember` and `mcp__mazemaker__mazemaker_health` can enter a
multi-minute unreachable state — error reads "MCP server 'mazemaker' unreachable after
8+ consecutive failures, auto-retry available in ~58s". When this happens mid-tick:

1. **Do not block on retries** — the tool-loop warning fires after 2 identical failures
2. Write pending discoveries to `~/.hermes/loops/pulse-wurm2/discoveries_YYYYMMDD_pulse-wurm.json`
   with full records: `label`, `content`, `url`, `source_seed`, `quality`
3. Also append topic strings to `state.discovery_topics` as a name-only backup
4. Let the next tick (6h later) retry the `mazemaker_remember` calls when the MCP server
   has recovered
5. Verify recovery via `mcp__mazemaker__mazemaker_health` — only attempt writes when it
   returns a healthy status (NOT the unreachable error)

The pulse_state.json state file is durable across ticks, so the fallback discoveries
are not lost — they just wait for the next mazemaker write window.

## Quality Signals for Results
- **Keep:** URLs ending in `.pdf`, `.org/abs/`, article paths with substance
- **Skip:** Language variants (`/es/`, `/fr/`, `/de/`), `/tos`, `/privacy`, nav pages
- **High-value:** Reddit posts with high engagement (score>500), arXiv papers with recent dates
- **Verify:** `pulse_health` returns `{"status": "ok"}` before proceeding

## Pulse Search Parameters for Reliability
For cron ticks that must complete:
```python
pulse_search(topic, 
    depth='quick',           # Faster than deep
    use_llm=False,           # Skip query planning
    llm_filter=False,        # Skip final filtering
    use_cache=True,          # Use cached if available
    lookback_days=30,        # Narrower date range
    n=15)                    # Smaller result set
```

## Resource Consumption
Deep research with wurm mode is expensive:
- Each dig phase can add 500-800 URLs
- LLM filter reduces by 90% (keeps only most relevant)
- Total candidates can reach 150+ over 4-5 dig rounds
- Time investment: 15-30 minutes for quick jobs, 30-120 for deep jobs