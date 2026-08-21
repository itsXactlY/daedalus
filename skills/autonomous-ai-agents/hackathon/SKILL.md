---
name: hackathon
description: |
  End-to-end hackathon execution on Hermes Agent — both building an earning/spending/
  operating business (trading + Stripe + Cloudflare Workers) AND the submission pipeline
  (demo video, asset prep, platform formatting). Use when the user is in or about to enter
  a Hermes Agent hackathon and needs either the build pattern or the deliverable pipeline.
---

# Hackathon

Class-level skill for Hermes Agent hackathons. The original narrow skills
`hackathon-autonomous-commerce` (build pattern) and `hackathon-submission-pipeline`
(deliverables) are absorbed as the two phases below; their support files live under
`references/<source>/`.

## Phase 1 — Build an autonomous business (absorbed from `hackathon-autonomous-commerce`)

Pattern: agents that **earn** (trading), **spend** (Stripe), and **operate** (Cloudflare
Workers). Wire the three capabilities together so the agent can run a self-contained
loop: take in capital, transact, and report.

- `references/hackathon-autonomous-commerce/atra-nous-hackathon-2026.md` — past build
  notes / architecture for the Atra×Nous hackathon.
- `references/hackathon-autonomous-commerce/stripe-skills-implementation.md` — how the
  Stripe spend side was implemented as skills.

## Phase 2 — Submission pipeline (absorbed from `hackathon-submission-pipeline`)

Produce the deliverables a competition expects:

1. **Demo video** — scripted walkthrough, captured headless, edited to length.
2. **Asset preparation** — landing page, README, screenshots, architecture diagram.
3. **Platform submission formatting** — match the host's required structure/metadata.

- `references/hackathon-submission-pipeline/nemotron-stripe-hackathon-june2026.md` —
  Nemotron/Stripe hackathon submission notes.
- `references/hackathon-submission-pipeline/mazemaker-hackathon-submission-2026-06.md` —
  Mazemaker submission notes.
- `templates/hackathon-submission-pipeline/stripe-mcp-server.py` — starter Stripe MCP
  server used in submissions.
- `scripts/hackathon-submission-pipeline/verify_stripe_integration.py` — pre-submit
  integration check.

## See also

- `autonomous-ai-agents/loop-engineering` — the loop pattern these businesses run on.
- `creative/cinematic-html-trailer` — for the demo video itself.
