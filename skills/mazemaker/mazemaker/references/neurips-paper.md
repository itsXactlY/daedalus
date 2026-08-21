# Mazemaker NeurIPS Paper Reference

## Paper Structure (NeurIPS Format)

Location: `/home/alca/papers/mazemaker-os/paper/main.tex`

### Key Sections
1. **Title**: "Mazemaker: An Operating System for Cognition"
2. **Abstract**: 5-sentence formula (Farquhar) covering contribution, biological inspiration, achievement, corpus statistics, validation
3. **Figure 1**: Kernel architecture diagram (TikZ) showing Applications → Mazemaker Kernel → Hardware Abstraction
4. **Introduction**: OS analogy framework positioning Mazemaker as first cognition OS
5. **Methods**: 5 definitions (Memory Formation, Dream Consolidation, Spreading Activation, Conflict Supersession, Federation) + Algorithm 1
6. **Experiments**: LongMemEval-S (R@10=1.00), DAE (perfect R@5), Ablation table
7. **Related Work**: Associative memory, knowledge graphs, sleep-inspired ML, federated learning
8. **Limitations**: Scale, evaluation scope, compute overhead, security
9. **Broader Impact**: Agent autonomy, privacy, resource efficiency, distributed intelligence

### Benchmark Results

From memory recall (LongMemEval-S, 2026-05):

| Metric | Value |
|--------|-------|
| R@1 | 0.710 |
| R@5 | 0.935 |
| R@10 | **1.000** (perfect recovery) |
| MRR | 0.807 |
| p50 latency | 44.6 ms |
| p95 latency | 72.7 ms |

### Corpus Statistics

| Component | Count |
|-----------|-------|
| Memories | 204,403 |
| Graph connections | 51,449 |
| Embedding dimension | 1024 (BGE-M3) |
| Dream phases | NREM/REM/Insight |

### The OS Framing (from memory id=518385)

Mazemaker as an operating system for cognition:

```
┌─────────────────────────────────────────┐
│   YOUR AGENTS (claude, cursor, hermes)  │  ← processes
├─────────────────────────────────────────┤
│             MAZEMAKER KERNEL            │
│   memory mgmt       (consolidation)     │
│   filesystem        (knowledge graph)   │
│   scheduler         (dream cycles)      │
│   IPC               (federation)        │
│   audit             (activation trace)  │
└─────────────────────────────────────────┘
```

Each line on the right has a direct OS analog. The kernel manages the memory of the processes (agents). The filesystem is the corpus. The scheduler runs the dream cycle while the system is idle.

### HTML Preview

For quick viewing without LaTeX compilation: `/home/alca/papers/mazemaker-os/paper/paper.html`

### Citation Format

For papers, use the NeurIPS 2025 template with:
- `neurips.sty` (conference style)
- `extra_pkgs.tex` (microtype, booktabs, tikz, algorithm2e, cleveref)
- Vector figures only (PDF or TikZ)
- Double-blind: no author names, anonymous acknowledgments

### Session Memory IDs

- OS framing: id=518385, id=518383
- LongMemEval-S results: id=533435
- Benchmark invariants: id=532750
- DAE smoke test: id=533442
- Hop-2 progression: id=184890