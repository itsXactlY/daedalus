# Reviewer Criteria Checklist

Checklist derived from a simulated NeurIPS-style review.
Use this when self-reviewing any academic paper before submission.

## 1. Claims must match evidence

For EVERY strong claim in the paper, fill in:

| Claim | Evidence provided | Evidence gap? | Fix |
|---|---|---|---|

If any row has an evidence gap, the claim must be weakened or the gap filled.

## 2. Anthropomorphic language audit

Search the paper for these terms and replace:

- [ ] "dreams" (unless clearly scoped as "consolidation that strengthens and prunes edges")
- [ ] "cognition" / "artificial cognition" → "persistent memory" / "layered memory architecture"
- [ ] "first operating system" → "a system for" / "an architecture that"
- [ ] "impossible" / "cannot possibly" → "cannot be answered by [precise mechanism] alone"
- [ ] "proof" → "evidence consistent with" / "supports the hypothesis that"
- [ ] "unconditional acceptance" (from LLM audit) → move to appendix as "development context"

## 3. Head-to-head comparison check

Does the paper compare against EXTERNAL systems (not just ablated versions of itself)?

- [ ] At least one empirical baseline on an identical benchmark (RAG, GraphRAG, MemGPT, etc.)
- [ ] If none exists, say so explicitly in Limitations: "We have not evaluated against external baselines."
- [ ] Architectural comparison table as fallback (capabilities matrix)

## 4. Statistical rigor

- [ ] Confidence intervals or noise estimates for all main metrics
- [ ] Per-question-type breakdowns with n values
- [ ] Disclosed failed experiments (at least 3)
- [ ] Rollback/discipline section if iterative optimization

## 5. Benchmark methodology

- [ ] Deterministic benchmark (or seed-locked for reproducibility)
- [ ] Versioned corpus (SHA-256 or equivalent)
- [ ] One-command reproduction script
- [ ] Public artifacts (dump, configs, result JSONs)

## 6. What reviewers will flag immediately

- "First" claims → require exhaustive related work survey
- "Cognition" → requires justification the paper cannot provide experimentally
- LLM audit as evidence → LLMs are not peer reviewers
- Anthropomorphic consolidation → describe what the algorithm actually does
- Production stats as superiority proof → ops numbers don't establish task improvement
- Internal benchmarks without external validation → "unknown benchmark" problem

## 7. Paper structure for systems papers (not ML papers)

For a systems-oriented venue or archiving:

1. **Experimental methodology** — this is the real contribution, not the architecture
2. **Iteration history** with negative results and rollbacks
3. **Bottleneck migration** as the central empirical finding
4. **Negative controls** as the proof mechanism
5. **Architecture** — shorter, framed as "the system that enabled the findings"
6. **Comparison** — external baselines if available
7. **Limitations** — including ALL comparisons NOT done
8. **Appendix** — gory technical details
