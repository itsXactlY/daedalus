# Mazemaker MCP Full Diagnostic Sweep

Run this systematic sweep through all available Mazemaker MCP tools when the operator says "use mazemaker to its full extent", "full diagnostic", "update everything in mazemaker", or when you need a complete health picture before making decisions.

## Sequence (in order)

### 1. Health Check — always first
```python
mcp__mazemaker__mazemaker_health()
```
Returns: corpus stats (memories, connections), dream sessions & totals, AFE facts count, DAE vectorized count & coverage.

### 2. Stats — quick snapshot
```python
mcp__mazemaker__mazemaker_stats()
```
Returns: embedding backend, fingerprint, retrieval mode, HNSW status, dimension lock. Use to confirm embedding infrastructure is healthy.

### 3. Graph — connectivity overview
```python
mcp__mazemaker__mazemaker_graph(limit=10)
```
Returns: total nodes & edges, top weighted edges. Read the edge types (bridge, cluster, supersedes) to understand what the graph is doing.

### 4. Dream Control — daemon status
```python
mcp__mazemaker__mazemaker_dream_control(action='status')
```
Returns: whether dream engine is running, external daemon or in-pod. If external, check via `ps aux | grep dream_worker`.

### 5. Dream Config — cadence knobs
```python
mcp__mazemaker__mazemaker_dream_config(action='get')
```
Returns: external_daemon flag, current config if in-pod is active.

### 6. Dream Stats — consolidation totals
```python
mcp__mazemaker__mazemaker_dream_stats()
```
Returns: sessions, total_processed, total_strengthened, total_pruned, total_bridges, total_insights, insight_types breakdown (bridge vs cluster).

### 7. Browse — most recent memories
```python
mcp__mazemaker__mazemaker_browse(limit=10)
```
Returns: most recently created memories by created_at DESC. Good for verifying that auto-saves are landing and recent session turns are being ingested into the sponge.

### 8. AFE Facts — atomic fact extraction completeness
```python
mcp__mazemaker__mazemaker_afe_facts(limit=5)
```
Returns: recent AFE-extracted atomic facts. Check that recent sessions have produced meaningful extracted facts (not just raw turn text).

### 9. Think — graph traversal from key memory
```python
mcp__mazemaker__mazemaker_think(memory_id=<id>, depth=3)
```
Pick a memory that should be well-connected (e.g. a canonical fact, a decision). If think returns 0 connected nodes, the memory graph isn't wiring — this is a signal that needs attention.

### 10. Ablation — channel health matrix
```python
mcp__mazemaker__mazemaker_ablate(
    channels=["semantic","fts","colbert","temporal","salience"],
    k=5,
    queries=["your domain relevant query 1", "query 2", ...]
)
```
Returns: per-channel result matrix. All channels should return nearly identical top hits (scores within 0.005 of each other). A channel that returns different results or much lower scores may be broken or misconfigured.

### 11. Diagnose — typed-miss detection
```python
mcp__mazemaker__mazemaker_diagnose(question_type="factual", sample_size=20, top_k_threshold=5)
mcp__mazemaker__mazemaker_diagnose(question_type="temporal", sample_size=20, top_k_threshold=5)
```
Returns: sampled/missed counts. On the live running corpus this returns 0 missed for both types if the corpus is well-covered. The bench-tier gold-rubric detection runs from benchmarks/targeted_rebake/find_typed_misses.py, not from MCP.

### 12. Try dream phases (may be skipped)
```python
mcp__mazemaker__mazemaker_dream(phase='all')  # or nrem, rem, insight, dae, afe, supersedes, synthesize
```
When an external dream_worker.py daemon owns consolidation, all in-pod phases return `skipped`. Don't retry — check daemon status with `ps aux | grep dream_worker` instead.

## Interpretation Cheat Sheet

| Metric | Healthy Range | What to Watch |
|--------|--------------|---------------|
| DAE Coverage | >0.95 (95%) | Below 0.90 means many memories lack graph-augmented embeddings |
| Dream daemon | Running | Check CPU usage (should be >0%, typically 50-85%) |
| Supersedes count | Any | Empty log = no conflicts; small count = recent conflicts resolved |
| Think connectivity | >0 edges on key memories | 0 edges = memory never wired into graph (paper memories commonly affected) |
| Ablation scores | All channels ±0.005 | Divergence >0.01 signals a channel issue |
| Dream stats growth | Positive trend | Compare vs previous session stats |

## Reporting Format

```
**Corpus:** X memories, Y connections, Z AFE facts
**DAE Coverage:** X%
**Dream Engine:** Running/External/Stopped — CPU X%
**Graph:** Top edges at weight X — edge types: bridge/cluster
**Ablation:** All 5 channels matched within 0.005 — healthy
**Diagnose:** 0 typed misses (factual + temporal)
**Think:** Memory id=X has Y connections — key decisions well-wired
**Dream Stats:** X sessions, Y processed, Z strengthened, W pruned, V bridges
```
