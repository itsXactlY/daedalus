# Pulse-Wurm 2.0 Implementation Details

## Execution Summary (2026-06-15)

### Seeds Processed
1. `multi-agent evaluation frameworks`
2. `AI agent self-improvement techniques`
3. `Claude Code agent deployment patterns`

### Results
- 10 novel discoveries found (arXiv papers, GitHub repos, OpenAI research)
- 34 new URLs added to visited list (expanded from 60 to 94)
- Saturation scores updated for multi-agent evaluation frameworks (+7) and AI agent self-improvement techniques (+3)

### New Discoveries
| Source | URL | Topic |
|--------|-----|-------|
| arXiv | https://arxiv.org/abs/1703.04908 | Emergence of Grounded Compositional Language in Multi-Agent Populations |
| arXiv | https://arxiv.org/abs/1909.07528 | Emergent Tool Use From Multi-Agent Autocurricula |
| GitHub | https://github.com/openai/multi-agent-emergence-environments | Environment generation code for multi-agent research |
| GitHub | https://github.com/openai/mujoco-worldgen | Automatic object XML generation for Mujoco |
| OpenAI | https://openai.com/index/consensus | Consensus: AI research assistant using GPT-5 |
| OpenAI | https://openai.com/index/emergent-tool-use | Emergent tool use from multi-agent interaction |
| OpenAI | https://openai.com/index/emergence-of-grounded-compositional-language-in-multi-agent-populations | Multi-agent language emergence research |

## Working Implementation Pattern (2026-06-15)

### Key Workflow Steps

1. **Run pulse_tick.py** to get state and seeds
   - Returns JSON with saturation scores, seeds_for_this_tick, and state file location

2. **Execute pulse_search** for each seed topic
   - Use `depth='deep'` with `max_fetches_per_round=100`
   - Results saved to temp files for URL extraction

3. **Extract and filter URLs**
   ```python
   # Parse JSON results, extract URLs
   # Filter against visited_urls from state
   # Sort by relevance score (rrf_score)
   ```

4. **Run pulse_dig** on unvisited promising URLs
   - Use `max_rounds=2, max_fetches=100`
   - Filter results for github, reddit, hackernews, arxiv sources

5. **Update state file**
   - Append new URLs to visited_urls
   - Increment saturation scores
   - Set next_seeds = lowest-saturation topics first

### Observed Patterns

- **MCP server reliability**: pulse_dig returns candidates in `body['candidates']` not `body['ranked_candidates']`
- **URL extraction**: Use regex `https?://[^\s"]+` or parse JSON structure
- **State file**: JSON format with `visited_urls`, `saturation_scores`, `next_seeds` arrays
- **Saturation-based rotation**: Topics with score 5 get priority over score 17+

### Next Seeds (Lowest Saturation)
1. Claude Code agent deployment patterns (5)
2. MCP protocol server development (5)
3. AI agent self-improvement techniques (7)
4. multi-agent evaluation frameworks (17)
5. AI agent loop engineering automation systems (17)

## Execution Checklist

- [x] Run pulse_tick.py to get state and seeds
- [x] Execute pulse_search for each seed (depth='deep' for thoroughness)
- [x] Filter results against visited_urls from state
- [x] Run pulse_dig on unvisited promising URLs (max_rounds=2, max_fetches=100)
- [x] Save novel findings to mazemaker with salience=0.4
- [x] Update state file with new URLs and saturation scores

## Tool Configuration Notes

- pulse_search: Use `llm_filter=false` to avoid aggressive filtering
- pulse_dig: Filter results for github, reddit, hackernews, arxiv sources
- pulse_remember: Label format `discovery:pulse-wurm-YYYYMMDD_<hash>`
- pulse_dig: Candidates are in `body['candidates']`, not `body['ranked_candidates']}`