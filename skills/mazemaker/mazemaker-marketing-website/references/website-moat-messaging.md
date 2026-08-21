# Website Moat Messaging — the three underrated pillars (grounded in live site copy)

All of this is ALREADY WRITTEN in the site. Pull it verbatim; never re-invent or
embroider the claims.

## Pillar 1 — Sandboxed Alpine-native Hermes on an unrooted phone

Source: `app/index.html` (Mazemaker for Android). The single most underrated fact —
no competitor ships a real Linux agent on a stock phone.

- "Mazemaker boots a genuine **Alpine Linux VM on a stock, unrooted Android phone** —
  no root, no custom recovery, no cloud — and runs a full **Hermes agent** inside it."
- "Native, not a webview. A real Linux VM — hardware-accelerated (pKVM/AVF) where the
  silicon allows, emulated elsewhere."
- "Wired to your memory ... over the same token + TLS + AES gateway."
- "Nothing baked in. The on-device pod mints its own access key at first boot; you
  paste it once. No secret ships in the download." (verified: no hardcoded IP/key).
- App = "your pod in your pocket" — thin encrypted client: recall, dream, think,
  graph, engine console (14 screens). Pro benefit.
- Phone-as-pod architecture (see `phone-as-pod` skill): sandbox-in-a-sandbox threat
  model — substrate A = QEMU VM (Pegasus-grade), substrate B = proot + native ELF
  (user-trusted).

Competitor positioning jab: "They play in sandboxes. We run an entire Linux sandbox,
inside another sandbox, on a phone, encrypted at rest — native, local-first, with
receipts."

## Pillar 2 — AES at-rest terminology (scattered across pages, unify it)

Source: `architect/index.html`, `architecture.html`, `pandoras-box.html`,
`privacy/index.html`.

- **AES-256-GCM** vault (the actual cipher).
- Wonderland container **AES-encrypts memory content at the storage boundary**.
- Encrypted **at rest** under a key derived from your **install fingerprint** via
  **HKDF(JWT, hardware-fingerprint)** — the key **never touches disk**.
- **Ed25519 JWT** for the gateway.
- **DLM vault + JRWL X3DH key agreement** — end-to-end between peers ("AES-256-GCM
  transparent").
- **Selective encryption** (the elegant part): public-label-prefix list —
  `skill:`, `auto:`, `decision:`, `bug:`, `ops:`, `reference:`, `invariant:`,
  `commit:`, `project:`, `signal:`, `feedback:`, `index:`, `public:` skip AES so
  embeddings stay semantic; `private:` and un-prefixed = AES at rest. Enforced at the
  wonderland boundary; engine never handles ciphertext directly.
- Rootless Podman pod. MCP/SSE on loopback. "No outbound network calls during recall."
- The intimacy argument (verbatim from FAQ): "Because memory is the most intimate data
  class a coding agent will ever touch — every preference, every fix, every name,
  every file path you mentioned three weeks ago. Centralising it is the obvious play
  for a surveillance business model. We're explicitly not that."

## Pillar 3 — Benchmark wins against named competitors (all verified/real)

Source: `comparison/index.html`, `architecture.html`, trailer receipts.

- **Hindsight: 188/200 = 94.0%** (VERIFIED; they published "not viable", ran on
  Mazemaker).
- **EverMemOS: 48.7 vs 44.6** mean (VERIFIED, 51.5 w/ budget answerer).
- **LongMemEval-S 500q** (hybrid + ColBERT @ 1.5): R@1 = **0.8574**, R@5 = **0.9787**,
  R@10 = **0.9894**, MRR = **0.9114**, p50 = **56.9 ms**.
- **100-iteration loop** on LongMemEval-oracle 500q (25,000-mem haystack): R@5 =
  **0.8426** (iter95), R@10 = **0.9000** (iter97), R@1 = 0.6255, MRR = 0.7124, ssu
  R@10 = **1.0000**; **total API spend $0.10**.
- **Hop-2 reasoning**: R@10 **0.00 → 1.00** — "vector databases cannot do this by
  construction."
- **Negative controls**: shuffle the edges → 1.00 → 0.27 — "every claim collapses on
  demand. Evidence, not vibes."
- **270M params on a Raspberry Pi**: 18/20 = 90% (gemma3:270m).
- **Dream synthesis lift**: pre-dream R@10 0.00 → post-dream 0.43 (measured).
- **Conflict supersession**: stale fact wins 60% without → live dominates 0.03 → 0.33
  with.
- **8 rounds adversarial review** (GPT-5.5 auditor): v2 "NO — lexical leakage" →
  v8 "UNCONDITIONAL YES".
- **Cross-session continuity**: raw cosine 0.46 → 0.06 under distractors; Mazemaker
  holds 0.62. "Not a 30% improvement. A phase change."
- godbench-oracle 500q: R@5 = 0.8043.

## The one-sentence story (verbatim)

> "Your agents die every conversation. Mazemaker keeps them alive — with **evidence,
> not vibes.**"

Plus the OS-reframe line: "This is not memory. Memory is a database. This is an
operating system for AI agents."

## Numbers-crosscheck

Every figure above is duplicated in the live site copy and the trailer receipts. If
you intend to quote one in a rebuild, cross-check it against `comparison/index.html`
(and the `mazemaker-ops` template `numbers-crosscheck.md`) before publishing — the
operator runs a numbers-live-from-graph discipline.
