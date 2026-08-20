---
name: research-paper-delivery
description: Deliver complete NeurIPS/arXiv/ICML research papers with all standard sections — never ask the user what to include. Triggered when producing or revising an academic paper.
---

# Research Paper Delivery Protocol

## Core rule
Deliver ALL standard academic sections FROM THE START. Never ask "soll ich X hinzufügen?"
The user expects full NeurIPS/arXiv quality on first delivery.

## Scientific claims must match evidence — this is THE critical skill

The most common rejection reason at top venues is not bad engineering — it's a gap between what the paper CLAIMS and what the experiments DEMONSTRATE. Every claim in the paper must have a measurable, falsifiable, reproducible result directly behind it.

### Claim-evidence mapping table

For EVERY strong claim in the paper, ask: "If a reviewer says 'prove it', what tool output or benchmark number do I point to?"

| Type of claim | Acceptable wording | Rejected wording | Why |
|---|---|---|---|
| Architecture novelty | "We describe a layered memory architecture" | "First operating system for artificial cognition" | "First" requires exhaustive survey you haven't done |
| Mechanism effect | "Hop-2 retrieval lifts from 0.00 to 1.00 with graph edges vs. cosine alone" | "Impossible with vector search" | Hybrid retrieval can do multi-hop; your implementation does it differently |
| Consolidation | "Post-dream synthesis: 0.00→0.43 R@10" | "The dream engine dreams the answers" | Anthropomorphic framing triggers reviewer suspicion |
| System positioning | "On LongMemEval-oracle, retrieval tuning saturated at 0.7404 before formation broke the ceiling" | "Memory is formation, not retrieval" | The second is philosophy; the first is evidence |
| Audit/validation | "The negative controls survived adversarial scrutiny (shuffled edges: 1.00→0.27)" | "GPT-5.5 unconditional acceptance" | LLMs are not peer reviewers; move to appendix as dev context |

### Never use anthropomorphic or marketing language for scientific claims

Terms that trigger reviewer rejection:
- "Dreams the answers" → use "post-consolidation synthesis"
- "First operating system for [anything]" → use "a layered architecture for..."
- "Artificial cognition" / "autonomous cognition" → use "persistent memory system"
- "Impossible" / "provably cannot" → use "cannot be answered by [specific mechanism] alone"
- "Skynet" / "ratio weapon" / project-branded jargon → use descriptive names ("full 8-channel preset")
- "Proof" → use "evidence" or "consistent with"

The tone should be descriptive ("we observed that..."), not declarative ("we prove that...").

### The bottleneck migration contribution — strongest framing found

The 100-iteration loop revealed that the LIMITING FACTOR MOVES between stages as each is optimised:
- Retrieval tuning saturates → formation becomes the bottleneck
- Formation optimised → rerank knobs that previously regressed now pay out
- Rerank optimised → top-K sharpness becomes the limiting factor

This is the strongest scientific finding because it is:
1. **Measurable** — R@5 changes systematically per era
2. **Falsifiable** — another system could show different migration
3. **Generalizable** — any layered memory architecture exhibits this
4. **Novel** — no prior work documents this phenomenon

Lead the paper with this finding, not with the architecture description.

## Required sections (every NeurIPS paper):
1. **Algorithm pseudocode** — Dream Engine cycle, retrieval fusion, etc. Use `algorithm` + `algpseudocode` packages.
2. **Comparison table** — system vs. all relevant prior work across capability dimensions
3. **Formal definitions** — mathematical formulation of all core objects (memory tuple, graph, embedding, RRF, PPR, etc.)
4. **Implementation/systems details** — hardware stack, key optimizations, CUDA/PyTorch stack, storage
5. **Qualitative examples** — real trace of the system in action, step by step
6. **Result visualizations** — use tikz + pgfplots for bar charts, line plots. Don't rely solely on tables.

## Tikz pitfalls (found 2026-06-28):
- Do NOT use `\node[layer, fit={...}]` with `minimum width`/`minimum height` — this creates overlapping boxes
- Use explicit `\draw[dashed, rounded corners] (x1,y1) rectangle (x2,y2)` instead of fit
- Do NOT use `fill=gray!8` on dashed layer boxes — it makes everything look "layered into one"

## Related skills
- `long-form-deliverable-production`

## Support files
- `references/reviewer-criteria-checklist.md` — self-review checklist: claim-evidence mapping, anthropomorphic language audit, head-to-head comparison requirements, statistical rigor, and paper structure for systems papers
