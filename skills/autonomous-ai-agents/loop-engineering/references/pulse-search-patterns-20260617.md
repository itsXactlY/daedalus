# Pulse Search Patterns — 2026-06-17

## Timeout Handling

`pulse_search(depth='deep')` has a 120s timeout and may fail with `TimeoutError`.

**Fallback chain:**
1. `pulse_search(depth='deep')` — primary, most comprehensive
2. `pulse_search(depth='quick')` — faster, less comprehensive (use max_per_round=20-30)
3. `pulse_research(depth='default')` — final fallback, synchronous

## Result Parsing

Results are wrapped in nested JSON:

```json
{
  "result": "{\"status\": 200, \"body\": {\"ranked_candidates\": [...], \"items_by_source\": {...}}}"
}
```

**Parse pattern:**
```python
outer = json.loads(response)
inner = json.loads(outer['result'])
candidates = inner['body']['ranked_candidates']
```

## Candidate Extraction

Each candidate in `ranked_candidates` contains:
- `url` — the discovered URL
- `title` — headline
- `snippet` — brief summary
- `source` — origin (github, reddit, arxiv, etc.)
- `final_score` — relevance ranking

Drill into `source_items[]` for full item details including `body`, `author`, `published_at`.

## URL Deduplication

Always check against `visited_urls` from state before digging:
- Skip already-visited URLs to prevent retry loops
- Some sources (Reddit, certain sites) block automated access — mark visited to prevent repeated failures

## Saturation Score Progression (2026-06-17)

Track saturation per seed topic (count of successful discoveries):
- Priority seeds: lowest saturation topics first
- When saturation reaches 10+, consider rotating to fresh topics
- Example progression: MCP security vulnerability analysis (3→4), Claude Code leak (5→6), Production MCP (7→8)

## Key Discoveries from This Tick (2026-06-17)

| Topic | URL | Finding |
|-------|-----|---------|
| MCP Security | github.com/andrasfe/vulnicheck | Python vulnerability scanner for MCP servers |
| MCP Security | github.com/laozhudetui/MCP_Scanner | Rust-based enterprise MCP security scanner |
| MCP Security | github.com/plutosecurity/MCPwnfluence | Dedicated security scanner for MCP servers |
| MCP Security | reddit.com/r/AZURE/... | NSA MCP security guidance (May 2026) |
| MCP Security | reddit.com/r/mcp/... | Community scan of 15,923 MCP servers |
| Production MCP | github.com/alexeymasalykin/ai-assistant-eduflow | Production multi-agent AI with 84% test coverage |
| Benchmarks | arxiv.org/abs/2508.14704v1 | MCP-Universe benchmark for LLMs |

## Recent Discovery (2026-06-17 19:15)

| Topic | URL | Finding |
|-------|-----|---------|
| Agent Skills for Large Language Models | github.com/xp13910818313/pencil-skills | Pencil Skills guide LLMs to use Agent Skills for effective UI design with Pencil MCP. Modular framework for extending Claude's capabilities through community-developed skills. |

## Saturation Score Updates

| Topic | Previous Score | New Score |
|-------|----------------|-----------|
| Agent Skills for Large Language Models | 22 | 32 |
| VLLM inference optimization | 12 | 12 |
| RL-Jailbreaking | 21 | 21 |