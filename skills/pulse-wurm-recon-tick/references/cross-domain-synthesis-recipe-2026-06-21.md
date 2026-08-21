---
name: pulse-wurm-recon-tick/references/cross-domain-synthesis-recipe-2026-06-21.md
description: Cross-domain synthesis as meta-topic discovery — recipe for consolidating findings across adjacent ticks into a single meta-topic seed (validated on space + bio + robotics convergence 2026-06-21)
---

# Cross-Domain Synthesis as Meta-Topic Discovery

## Pattern (VALIDATED 2026-06-21 12:55Z tick)

When 2+ adjacent ticks each find a cluster of papers that share a common substrate (e.g. biology, AI research lifecycle, photonic systems), consolidate the findings into a SINGLE meta-topic for the next tick rather than re-mining each domain separately.

## Real case (2026-06-21 12:55Z tick)

4 papers across 3 ticks converged on "biology as engineering substrate":

| Domain | Tick | Paper | Substrate Angle |
|---|---|---|---|
| space | 2026-06-21 12:55Z | Marine extremophiles for sustainable space exploration (Race, Frontiers Astronomy 2026-06-19, doi 10.3389/fspas.2026.1868905) | Extremophiles → space habitats |
| space | 2026-06-21 12:55Z | Biological design strategies for space biology (Subramanian/Palmer, ECCWS 2026-06-15, doi 10.34190/eccws.25.1.4896) | Biological principles → closed-loop life support |
| bio | 2026-06-21 12:55Z | Artificial Tripartite Intelligence bio-inspired Physical AI (Choi/Park/Kim, ACM 10.1145/3745756.3809242, 2026-05-29) | Bio-inspired sensor-first AI |
| robotics | 2026-06-21 04:24Z (carry-over) | ConstrainedMimic humanoid whole-body control (Morton/Mohnot/Pavone, Stanford, arxiv 2606.00374, 2026-05-29) | Bio-mechanics for humanoid control |

All four treat biological evolution as an engineering design space. The synthesis identified "physical AI frontier 2026" as the natural consolidation meta-topic for the next tick — a single pulse_research call would surface all 4 substrate angles simultaneously instead of 3-4 separate domain queries.

## Recipe

1. **At end of synthesis**, scan the 11+ substantive findings for SHARED SUBSTRATES:
   - Common problem statements (e.g. "sustainable hostile environments")
   - Common methodological primitives (e.g. "biology as engineering design space")
   - Shared named entities (e.g. multiple papers citing the same dataset or method)
2. **If 3+ findings from 2+ different domain ticks share a substrate**, write the meta-topic as a single seed for the next tick's PHASE A or PHASE B.
3. **In `discovered_topics_for_next_tick`**, add a `try pulse_research on <meta-topic>` entry that explicitly cites the source findings by mazemaker id.
4. **The meta-topic seed should NOT have a domain prefix** (e.g. NOT "robotics physical AI" or "bio physical AI") — leave it as `"physical AI frontier research 2026"` so pulse can route across all sub-channels (openalex + reddit + arxiv).

## Detection signal

End-of-tick synthesis with 3+ findings sharing a methodological primitive → candidate for meta-topic consolidation.

## Anti-pattern

Re-mining each domain separately without consolidation — wastes cron budget on 4 separate `pulse_research` calls when 1 meta-topic call would surface all 4 substrate angles.

## Expected yield improvement

A meta-topic call like "physical AI frontier research 2026" is expected to surface:
- Bio-inspired robotics papers (from openalex sub-channel — proven productive on robotics tick 2026-06-21 04:24Z)
- Space biology + closed-loop life support (from space tick 2026-06-21 12:55Z)
- Bio-inspired Physical AI architectures (from bio tick 2026-06-21 12:55Z)
- Bio-mechanics for humanoid control (from robotics tick 2026-06-21 04:24Z)

All 4 substrate angles in a single ~25 min deep call vs 4 × 25 min = 100 min in separate domain calls. ~4× wall-time improvement on next-tick coverage of the same conceptual surface.

## Companion recipes

- See SKILL.md "openalex sub-channel is productive" pitfall — confirms openalex is the productive sub-channel for physical AI / bio-inspired engineering topics
- See SKILL.md "Concrete-reformulation + llm_filter=false + pulse_dig pipeline" pitfall — alternative when meta-topic seed is over-mature
- See SKILL.md "Confirmation pass" pitfall — recognize when meta-topic returns duplicates from prior domain ticks