# Pulse-Wurm 2.0 Implementation Details — 2026-06-17

## Core Architecture

Pulse-Wurm 2.0 is a stateful reconnaissance loop that actively seeks what it DOESN'T know through graph-guided exploration.

### State Management
- State file: `~/.hermes/loops/pulse-wurm2/pulse_state.json`
- Tracks: visited URLs, saturation scores, consecutive empty ticks
- Uses saturation scoring to prioritize under-explored topics

### Discovery Pipeline

```
1. pulse_search(depth='deep') → candidate URLs
2. Check visited_urls → skip known URLs
3. pulse_dig(max_rounds=2, max_fetches=150) → deep crawl
4. Filter for novel topics (not in mazemaker in last 48h)
5. mazemaker_remember(label='discovery:pulse-wurm-YYYYMMDD_<hash>')
6. Update state: append URLs, increment scores, rotate seeds
```

## Content Fetching Fallbacks (2026-06-17)

When primary tools fail, use this decision tree:

1. **Browser tools first** - Works even when direct HTTP is blocked
2. **Direct API calls** - e.g., arXiv API via urllib for scholarly papers
3. **PDF extraction** - pdftotext or pikepdf for paper content
4. **Web archive fallback** - archive.org for blocked sources

## Result Parsing Pattern (2026-06-17)

Pulse search returns results wrapped in nested JSON:
```json
{"result": "{\"status\": 200, \"body\": {\"ranked_candidates\": [...]}}
```

**Parse pattern:**
```python
outer = json.loads(response)
inner = json.loads(outer['result'])
candidates = inner['body']['ranked_candidates']
```

## Key Discoveries from 2026-06-17

### Critical MCP RCE Vulnerability
- Ox Security: "The Mother of All AI Supply Chains"
- Enables Arbitrary Command Execution on vulnerable MCP servers
- NSA issued 17-page MCP security guidance (May 2026)

### Autonomous AI Agents 2026
- VoltAgent/awesome-ai-agent-papers (1,422★): 2026 research papers
- detour (146★): Satellite debris avoidance agents
- RExBench (8★): Coding agents implementing AI research

## Saturation Score Progression

Track saturation per seed topic (count of successful discoveries):

| Topic | Previous | Current | Delta |
|-------|----------|---------|-------|
| MCP protocol security | 14 | 29 | +15 |
| autonomous AI agents 2026 | 15 | 27 | +12 |
| VLLM framework vulnerabilities | 17 | 17 | 0 |
| Claude Code MCP integration | 18 | 18 | 0 |

## Next Seed Rotation (Low Saturation Priority)

1. VLLM inference optimization (saturation: 5)
2. Agent Skills for Large Language Models (saturation: 11)
3. RL-Jailbreaking (saturation: 11)
4. VLLM framework vulnerabilities (saturation: 17)
5. Claude Code MCP integration (saturation: 18)

## Triple-Memory Enrichment Pattern

Each discovery spawns:
1. **discovery entry** - Initial finding
2. **fact entry** - Core insight with context
3. **decision entry** - Linked actions and follow-ups