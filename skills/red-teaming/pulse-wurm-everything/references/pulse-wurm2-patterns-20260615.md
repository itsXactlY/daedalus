# Pulse-Wurm 2.0 Execution Patterns (2026-06-15)

## Key Observations from Live Execution

### MCP Tool Response Structures

**pulse_dig results structure:**
```json
{
  "body": {
    "candidates": [...],  // NOT ranked_candidates
    "run_id": "...",
    "rounds_completed": 2
  }
}
```

**pulse_search results structure:**
```json
{
  "result": "{\"body\": {\"ranked_candidates\": [...]}, ...}"
}
```

### URL Extraction Patterns

**From pulse_search JSON:**
```python
data = json.loads(content)
result = json.loads(data['result'])
candidates = result['body']['ranked_candidates']
urls = [c['url'] for c in candidates if 'url' in c]
```

**From pulse_dig JSON:**
```python
candidates = result['body']['candidates']  # NOT ranked_candidates
```

### State File Operations

**Reading state:**
```python
with open('/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json') as f:
    state = json.load(f)
visited_urls = state.get('visited_urls', [])
saturation_scores = state.get('saturation_scores', {})
```

**Updating state:**
```python
state['visited_urls'] = visited_urls
state['saturation_scores'] = saturation_scores
state['last_tick'] = datetime.now().isoformat()
state['next_seeds'] = sorted_topics[:5]
```

### Saturation-Based Topic Rotation

**Algorithm:**
1. Collect all topics with their saturation scores
2. Sort by score ascending (lowest first)
3. Select top 5 for next_seeds
4. Topics with score 5 are prioritized over score 17+

**Observed scores after 2026-06-15:**
- Claude Code deployment: 5
- MCP protocol: 5
- AI self-improvement: 7
- multi-agent eval: 17
- AI loop engineering: 17
- Codex CLI: 21

### Discovery Label Format

`discovery:pulse-wurm-YYYYMMDD_<hash>`

Where hash is first 8 chars of MD5(URL).

### Source Filtering for Relevant Results

**High-value sources:**
- arxiv.org/abs/ (research papers)
- github.com/openai (OpenAI repos)
- openai.com/index/ (OpenAI research)

**Filter pattern:**
```python
if any(x in url.lower() for x in ['arxiv.org', 'github.com/openai', 'openai.com/index']):
    # Process as relevant finding
```

### Discovery Content Structure

```markdown
Topic: <seed_topic>
URL: <url>
Title: <title>
Source: <source>
Summary: <snippet[:500]>
Finding: <analysis of significance>
```