# Mazemaker Hackathon Submission — June 2026

**Event:** Hermes Agent Accelerated Business Hackathon (Nous Research × NVIDIA × Stripe)
**Theme:** Agents that can earn, spend, and run real operations at any scale
**Judges:** Nous Research, NVIDIA, Stripe
**Criteria:** usefulness, viability, presentation
**Deadline:** EOD Tuesday June 30, 2026
**Video:** ~90s (87.7s), 4K, `~/comic/v4/capture/mazemaker-submission-final-4k.mp4`

## Submission strategy

### The core angle: "Submit the company, not a demo"

We didn't build a demo for this hackathon. We submitted the company — a live, Stripe-billed multi-tier SaaS built end-to-end through Hermes, before the Stripe Skills existed.

This is the strongest differentiator from other submissions. State it in the first paragraph.

### Sponsor alignment

Each sponsor must see their contribution called out explicitly:

| Sponsor | What to mention | How Mazemaker uses it |
|---|---|---|
| **Nous Research** | Hermes Agent | 1,036 commits · 7 repos · 10 weeks · one agent. Entire company built through Hermes. NemoClaw + OPENCLAW in the MCP hub. |
| **NVIDIA** | NemoClaw, Nemotron | NemoClaw for safe agent operations. Local-first = your GPU, not cloud rent. Runs at 270M params on a Raspberry Pi. MCP hub with NEMOCLAW + OPENCLAW. |
| **Stripe** | Stripe Skills, Billing Meters | Stripe integration built from docs in early May — weeks before Stripe Skills existed. Metered usage, customer portal, feature gates. |

### The earn/spend/run framework

Organize the submission around the hackathon theme:

- **Earns** — live Stripe-billed multi-tier SaaS with Billing Meters API
- **Spends** — NemoClaw for safe agent execution, your GPU not cloud rent
- **Runs** — C++/Cython/CUDA 1024-d engine, Android (Podroid: Nuitka binary sandboxed inside QEMU VM inside APK). Agents don't die when the conversation ends.

## Canonical facts (from Mazemaker memory, DO NOT change)

Use these exact numbers and phrasing:

- **Positioning:** "An operating system for artificial minds." NOT "memory add-on," "vector database," "memory toy," or "recall engine."
- **Core thesis:** "Memory is not retrieval. Memory is formation." NOT "Memory is not retrieval. Memory is retrieval."
- **LongMemEval-S:** R@10 = 0.90 (NOT 1.00 — 1.00 is the hop-2 value)
- **Hop-2:** 0.00 → 1.00 (perfect score on A→B→C edge chains)
- **Shuffled edges:** 1.00 → 0.27 (graph traversal is load-bearing)
- **Post-dream synthesis:** 0.00 → 0.43
- **Conflict supersession:** 0.03 → 0.33
- **Cross-session continuity:** 0.06 → 0.62
- **Tiny model:** gemma3:270m scores 18/20 at 270M params, runs on Raspberry Pi
- **Audit:** 8-round adversarial audit, every prompt+verdict committed in the repo
- **Motto:** "If you can't make the number drop on demand, you don't have evidence — you have a coincidence."

## Paper reference

The paper ("Mazemaker: A Layered Memory Architecture with Empirically Observed Bottleneck Migration") is at `/home/alca/papers/mazemaker-os/paper/main.pdf`. Author: "Single EU Operator". NeurIPS format. Link to `paper.html` (rendered) in the submission — don't attach the PDF.

## Pitfalls encountered

- **Truncation artifacts:** Copying text from a truncated terminal preview clips words ("crystallize" → "cr", "federation" → "federatio", "coincidence" → "coin"). Always check for this before finalising.
- **Over-discussing options:** When the user asks for a submission text, produce the best version immediately. Do not present multiple options or ask "should I cut X?" — just deliver. Ask for revisions after delivery if needed.
- **Wrong positioning from old drafts:** The user's own draft may still use old framing (e.g. "memory toy/recall"). Load Mazemaker canonical facts first before editing.
