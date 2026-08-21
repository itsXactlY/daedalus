---
name: pulse-source-debugging
version: "0.0.1"
description: "Debug why PULSE returns 0 items from Reddit or wrong results from ArXiv, and which sources work reliably for tech topics."
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [pulse, debugging, reddit, arxiv, github, research]
    related_skills: [pulse]
---

# PULSE Source Debugging

## Problem Patterns

### 1. Reddit Returns 0 Items (Most Common)
**Symptom**: `python3 scripts/pulse.py "query" --sources reddit --depth deep` returns 0 items despite query being relevant.

**Diagnosis steps**:
```bash
# Check if the Reddit endpoint is accessible directly
curl -s -A "pulse-hermes/3.0" \
  "https://www.reddit.com/search.json?q=YOUR+QUERY&sort=relevance&t=month&limit=5"

# If curl fails too, Reddit is blocking the requests (anti-bot)
```

**Known failing topics**: TTS/speech synthesis, local AI models, some niche tech
**Root cause**: Reddit increasingly blocks unauthenticated requests; the public JSON endpoint returns empty or anti-bot HTML for certain queries.

**Workaround**: Use `--sources github,hackernews` instead. GitHub is the most reliable source for technical topics.

### 2. ArXiv Returns Irrelevant Results
**Symptom**: ArXiv returns math/physics papers instead of CS/ML papers for your query.

**Example**: Query "ChatTTS voice" returned arithmetics papers. Query "TTS benchmark" returned physics papers.

**Root cause**: ArXiv's free Atom API is returning results from unexpected categories when the query is ambiguous.

**Workaround**: Add specific category filters to your query:
```bash
# Good: specific model name or technique
python3 scripts/pulse.py "ChatTTS" --sources arxiv --depth deep
python3 scripts/pulse.py "fish-speech S2-Pro" --sources arxiv --depth deep

# Bad: generic terms that match cross-discipline literature
python3 scripts/pulse.py "TTS benchmark" --sources arxiv --depth deep
```

### 3. Multiple Sources Return 0 Items
**Diagnosis**: Run with `--diagnose` flag first to see which sources are actually available/working.

## Reliable Source Combos by Topic

| Topic | Best Sources | Backup |
|-------|-------------|--------|
| Open source AI models | github, hackernews | reddit (may return 0) |
| TTS / Voice | github, hackernews | arxiv with specific model name |
| Academic ML research | arxiv (with specific query) | github |
| News / Trending | reddit, hackernews | news (requires API key) |
| Code / Dev Tools | github, hackernews | reddit |

### 4. Specialized ML / Technical Research Returns 0 Across All Sources
**Symptom**: Query for specific ML algorithms, vector indexing, or academic papers returns 0 from ALL sources, including arxiv, github, openalex, sem_scholar.

**Examples that failed:** "HNSW FAISS ScaNN vector index PyTorch benchmark", "Mamba state space model language modeling", "DeepSeek MLA attention architecture", "Sparse attention subquadratic transformer memory", "approximate nearest neighbor search algorithm"

**Root cause:** PULSE is designed for social/trending/engagement-based research. It scores by Reddit upvotes, HN points, etc. Specialized ML topics that don't generate social engagement return nothing because:
- ArXiv Atom API returns cross-discipline results when query is broad
- GitHub search misses unrepo-specific algorithm names
- HN/Reddit only surface what has active discussion
- Academic sources (openalex, sem_scholar) require exact title/author matching

**When this happens:**
- ArXiv returns: 0 items (even with `--lookback 365`)
- GitHub returns: 0 items
- HN returns: 0 items
- Reddit returns: 0 items OR generic unrelated threads
- openalex/sem_scholar: returns unrelated cross-discipline papers

**Workaround**: For specialized ML/algorithm research, use direct methods instead:
```bash
# Direct ArXiv search via their Atom API
curl "http://export.arxiv.org/api/query?search_query=all:YOUR+KEYWORD&max_results=20&sortBy=submittedDate"

# Use a specialized ML research agent (delegate to sub-agent with web browsing)
# Or use MemoryAgentBench setup for memory system benchmarking

# For specific algorithm names, try GitHub search directly
curl -s "https://api.github.com/search/repositories?q=ALGO_NAME+in:name,readme"
```

**Reliable Source Combos by Topic**

| Topic | Best Sources | Backup |
|-------|-------------|--------|
| Open source AI models | github, hackernews | reddit (may return 0) |
| TTS / Voice | github, hackernews | arxiv with specific model name |
| Academic ML research (broad) | arxiv (with specific query) | github |
| **Specialized ML algorithms (HNSW, FAISS, Mamba, MLA)** | **Direct ArXiv API or dedicated research agent** | **github with exact name** |
| News / Trending | reddit, hackernews | news (requires API key) |
| Code / Dev Tools | github, hackernews | reddit |
| Vector indexing / ANN search | direct web search | github (specific repo) |

## Quick Debug Workflow

```bash
# 1. Test GitHub (most reliable)
python3 scripts/pulse.py "YOUR QUERY" --sources github --depth deep --emit=json 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('items_by_source',{}).get('github',[])), 'GitHub items')"

# 2. Test HN if GitHub is thin
python3 scripts/pulse.py "YOUR QUERY" --sources hackernews --depth deep

# 3. Only use Reddit/GitHub together if both are returning results individually
# Don't trust combined source queries when individual sources return 0
```

## Verification

After any change to source modules, verify the source actually returns data before relying on it:
```bash
python3 scripts/pulse.py --sources SOURCE_NAME --depth quick --emit=json 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items_by_source',{}).get('SOURCE_NAME',[]); print(len(items), 'items')"
```
