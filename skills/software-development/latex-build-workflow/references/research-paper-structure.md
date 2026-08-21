# Research Paper Structure Templates

Two formats used by this operator: NeurIPS (conference, detailed) and arXiv (preprint, concise).

## NeurIPS Paper Layout (~8–10 pages)

```
Abstract — 5-sentence formula
1. Introduction
   - The wound (e.g. "context windows are coffins")
   - What prior work misses (RAG, MemGPT, NTM)
   - Your three contributions (formation over retrieval, autonomous consolidation, ratio-weapon evidence)
   - Paper roadmap

2. Architecture
   - Seven-phase pipeline with TikZ figure
   - Each phase: 1-2 paragraphs
   - Dream Engine sub-phases (NREM/Supersedes/REM/Insight/AFE/DAE)
   - Retrieval fusion (RRF, 8 channels)
   - GPU acceleration

3. Negative Controls ← CENTRAL EVIDENCE
   - Protocol principle: "if you can't make it drop, it's a coincidence"
   - Table: 6 controls with values
   - Each control: 1 paragraph explaining what it proves

4. Benchmark Results
   - Inception Bench (100k needle)
   - LongMemEval (oracle + S with ColBERT)
   - Four-era progression (iter00→100)
   - Hindsight re-evaluation (188/200 = 94%)
   - Systematic benchmark defects (int truncation, rubric defects, judge variance, friendly partitioning)

5. Live Production Evidence
   - Full stats table (memories, connections, dream totals, latency)
   - Deployment context

6. Adversarial Audit
   - 8-round GPT-5.5 progression table
   - v2 NO → v8 UNCONDITIONAL YES

7. Related Work
   - External memory (NTM, DNC)
   - RAG and GraphRAG
   - LLM memory (MemGPT, MemWalker)
   - Complementary Learning Systems
   - Spreading activation
   - Federated learning

8. Limitations
   - Storage tiers (Free/Lifetime vs Pro)
   - Dream engine overhead
   - Judge sensitivity
   - Federation maturity
   - LLM dependency

9. Conclusion
   - Thesis restatement
   - Link to code + reproduction

Appendix
   - Hyperparameters
   - Reproduction commands
```

## arXiv Paper Layout (~4–6 pages)

```
Abstract — concise version
1. Introduction — Rhythm Principle (Cognition = Memory ⊗ Rhythm)
2. Mazemaker: Seven-Phase Formation
   - Sponge → AFE → Embedding → Dream → Synthesis → Re-formation → Federation
3. Negative Controls — 6 controls table
4. Hindsight Re-evaluation — 188/200 = 94%
5. Four-Era Progression — iter00→100
6. What Did NOT Work — rolled-back interventions
7. Reproduction
```

## Evidence Table Template

```latex
\begin{tabular}{lccc}
\toprule
Capability & Control & Mazemaker & $\Delta$ \\
\midrule
Hop-2 graph reasoning   & 0.00 & \textbf{1.00} & +1.00 \\
Shuffled edges          & --   & 1.00$\to$\textbf{0.27} & collapse \\
Post-dream synthesis    & 0.00 & \textbf{0.43} & +0.43 \\
Conflict supersession   & 0.03 & 0.33           & +0.30 \\
Cross-session continuity& 0.06 & \textbf{0.62} & +0.56 \\
Lean vs skynet ($n=200$)& 0.42 & \textbf{0.60} & +0.18 \\
\bottomrule
\end{tabular}
```

## Storage Tier Language

| Wrong | Right |
|---|---|
| "SQLite supports ~1M memories; Postgres required beyond" | "The public engine uses SQLite (Free for Lifetime under dual license). Pro/Team/Enterprise deployments scale with PostgreSQL + pgvector" |
| "SQLite (production), Postgres (scale)" | "SQLite (Free for Lifetime, dual license), PostgreSQL + pgvector (Pro/Team/Enterprise)" |

## Data Gathering Recipe (for Mazemaker papers)

Before writing, call in order:

1. `mazemaker_stats` / `mazemaker_health` — live corpus numbers
2. `mazemaker_recall` for benchmark facts, architecture facts, positioning facts
3. `mazemaker_think` on key fact IDs to find connected evidence
4. `mazemaker_graph` for edge structure
5. `mazemaker_dream_stats` for consolidation totals

## Algorithm Blocks

Always include at least one algorithm block (Dream Engine cycle, retrieval fusion). Use `algorithm` + `algpseudocode` packages. Example structure:

- **Alg 1:** Dream Engine Cycle (NREM strengthen/prune → Supersedes → REM bridge → Insight → AFE/DAE)
- **Alg 2:** Eight-Channel Retrieval with RRF Fusion
- Keep algorithms short (8–15 lines), focused on the novel mechanism

## Visual Figures

Include at minimum:

- **Architecture figure** (TikZ) — the seven-phase pipeline with Dream Engine sub-phases
- **Negative controls bar chart** (pgfplots) — control vs Mazemaker values as grouped bars
- **Progression chart** (pgfplots) — R@5 over iterations with retrieval ceiling annotation
- Each figure must have a descriptive caption that is self-contained (readable without the paper body)

## Formal Definitions Section

Place right before or at the start of the Architecture section. Define in order:

1. Memory tuple $(d, e, s, t, c, l)$
2. Knowledge Graph $(\mathcal{M}, \mathcal{E}, w)$
3. Dream-Augmented Embedding (DAE) — $e'_i = \alpha e_i + (1-\alpha)\sum\beta_{ij}e_j$
4. Personalized PageRank (PPR) — $\mathbf{p} = (1-\alpha)\mathbf{Ap} + \alpha\mathbf{e}$
5. Reciprocal Rank Fusion (RRF) — $\text{RRF}(m) = \sum \frac{1}{k + r_c(m)}$
6. Supersession — conflict detection condition + revision chain

## Implementation Stack Table

Include in Limitations or Appendix. Two-column table: Component | Technology. Covers:

- Graph engine (CUDA cuSPARSE, Cython bindings)
- Embedding (BGE-M3 ONNX, ColBERT PyTorch)
- Storage (SQLite Free/Lifetime, PG+pgvector for scale)
- Dream daemon (Python standalone, Unix socket IPC)
- Federation (JRWL over X3DH)

## Qualitative Recall Trace

Include one concrete recall trace in the Evaluation section. Step-by-step:

1. User query → BGE-M3 embedding → 25 initial candidates
2. Semantic miss (top result is close but not the answer)
3. PPR graph traversal from top candidate → follows edges → finds correct session
4. ColBERT@1.5 rerank promotes the correct answer to rank 1
5. RRF fusion produces the final score and answer

This makes the architecture concrete for reviewers.

## Complete Paper Checklist

Before submitting, verify:

- [ ] All 6 negative controls present with values
- [ ] At least 1 algorithm block
- [ ] At least 3 figures (architecture, controls, progression)
- [ ] Formal definitions section
- [ ] Comparison table (Mazemaker vs alternatives)
- [ ] Qualitative recall trace
- [ ] Implementation stack table
- [ ] Reproduction commands
- [ ] Total pages within venue limit (NeurIPS: 8, arXiv: no limit)
- [ ] No `error:` or `!` in compilation output
- [ ] Storage tier language uses licensing model (Free/Lifetime, not just "production/scale")
- [ ] All references resolve (no "undefined citation" warnings)
