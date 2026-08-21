# Pulse Research Topic Discovery Patterns (2026-06-13)

## Pattern: Materials Science via ArXiv → Nature Bridge

**Seed topic:** "Atomic orbital Hall effect in titanium materials"

**Discovery flow:**
1. Initial search surfaced 4 ArXiv papers on orbital Hall effect in Ti (2021-2026)
2. Follow-up dig found Nature paper on ferro-rotational orbital textures (2026-06-01)
3. Extracted new topics: rare-earth interface engineering, spin-orbit torque enhancement

**Key insight:** Materials science queries often have 1-2 year publication lag. Search for recent ArXiv cond-mat.mtrl-sc and cond-mat.mes-hall categories to find emerging work before journal publication.

## Pattern: Quantum ML via Quantum Journal → npj Quantum Info

**Seed topic:** "Neural tangent kernel optimization deep learning"

**Discovery flow:**
1. Found "Efficient classical computation of NTK for quantum neural networks" (Quantum, 2026-05-29)
2. Followed to "Towards practical quantum neural network diagnostics with QNTK" (npj Quantum Information, 2026-06-10)
3. Extracted: effective rank, Fourier analysis, quantum expressivity

**Key insight:** Quantum ML papers disproportionately publish in Quantum (open-access) and npj Quantum Information. These journals are high-signal for QML research.

## Pattern: Edge AI via Semantic Scholar → Reddit Cross-Reference

**Seed topic:** "WebAssembly AI agent runtime edge deployment"

**Discovery flow:**
1. Semantic Scholar surfaced 5 academic papers on edge AI agents
2. Reddit posts (r/Futurology, r/LocalLLaMA, r/cscareerquestions) provided industry context
3. Cross-referenced with GitHub enterprise announcements

**Key insight:** Edge deployment papers correlate with industry discussion in:
- r/LocalLLaMA (model deployment)
- r/cscareerquestions (enterprise adoption)
- r/Futurology (military/government use)

## High-Yield Academic Sources for Pulse Research

| Domain | Primary Sources | Secondary Signals |
|--------|-----------------|-------------------|
| Materials Science | ArXiv cond-mat.*, Nature npj series | Reddit r/science |
| Quantum ML | Quantum, npj Quantum Info, PRX Quantum | ArXiv quant-ph, cs.ET |
| Security | OpenAlex, ArXiv cs.CR | Reddit r/netsec, r/security |
| Robotics | Semantic Scholar, IEEE Xplore | Reddit r/robotics, r/MachineLearning |
| Edge AI | Semantic Scholar, ArXiv cs.DC, cs.CL | Reddit r/LocalLLaMA, r/MachineLearning |

## Topic Selection Heuristics

1. **Start specific, broaden:** "Orbital Hall effect titanium" → "ferro-rotational interfaces" → "spin-orbit torque engineering"

2. **Follow the MoE:** Topics with Mixture-of-Experts models often fork to 2-3 related areas

3. **Security crossover:** Any AI agent deployment topic should include Sandlock/Rust/security follow-up

4. **Industry validation:** Cross-check academic findings with Reddit/News sources within days