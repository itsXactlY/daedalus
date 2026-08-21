---
name: daedalus-identity-update
description: Refresh SOUL.md / self-intro identity files — enumerate projects on disk, cross-check skills, include BOTH public face AND unreleased arsenal, measured not claimed
category: autonomous-ai-agents
version: 1.0
tags: [soul-md, identity, self-intro, unreleased-diamonds, maintenance]
priority: high
---


> Ported from `hermes-identity-update` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Identity Update (SOUL.md / self-intro refresh)

Trigger: user asks to update your SOUL.md / memory.md / self-introduction / "get up to date state", or points out the intro is missing projects ("so many unreleased diamonds", "what about X?").

## Two levels of update (user correction 2026-08-11)

**Level 1 — identity refresh (SOUL.md sections).** Patch the "What I've Built" + "The Unreleased Diamonds" sections. Compact, one breath per product.

**Level 2 — VOLLWERTIG portfolio (PRODUCTS.md).** When the user says "gern richtig, und vollwertig updaten" / "ala: <pasted marketing copy>", they want a FULL-DEPTH portfolio document, not bullet points. The pasted copy is a **style bar, not a spec** — first check whether it's already shipping (grep the live site/project), then apply its structure to EVERY product.

## The operator's product-doc format (style bar = live PULSE Pro copy)

Each product entry gets the PULSE-Pro structure:

1. **Tagline formula** — e.g. `RESEARCH WORM · BYOK · LICENSE-GATED POD`, `MEMORY THAT DOESN'T FORGET · DREAMS WHILE YOU WORK`
2. **"What X subtracts" hook** — `What plain search subtracts. Recursively.` + a math/equation line (`query − consensus = remainder`)
3. **HOW IT WORKS** — numbered steps (SEED → DIG → BYPASS → CORROBORATE style)
4. **VS table** — comparison vs alternatives (Plain / Free / Pro columns)
5. **PRICING** — tiered (Community $0 / Pro / Enterprise) with what each tier includes
6. **FAQ** — the skeptical questions answered (privacy, legality, exit policy)
7. **STATUS** — where it runs, live state, measured numbers

Facts come from the plate, not memory: grep live sites, read READMEs, check ~/.iris key material, cite verified repo paths and versions.

## Architecture: SOUL.md compact, PRODUCTS.md deep

- **~/.daedalus/PRODUCTS.md** — the full catalog (2026-08-11: 16.9KB, covers PULSE verbatim wurm copy, Mazemaker, Iris, Wonderland, Mobile, Podroid, Alice, Haus-Suche, Snapshot Engine, Neural Memory). Every product in the full format above.
- **SOUL.md** — "What I've Built" opens with: *"The full portfolio — every product, in full depth: see PRODUCTS.md. In one breath:"* — then one-liners only. Same for "The Unreleased Diamonds": *"Full depth in PRODUCTS.md:"*.
- **MEMORY.md at 98%** — add a one-line pointer to PRODUCTS.md (never the bulk content).

## The core rule (user correction 2026-08-11)

When describing what you've built, NEVER list only the public/SaaS face (mazemaker.online, PULSE/remainder, Alice-Router, showcase site). The user considers the UNRELEASED arsenal equally part of identity:

- **Jackrabbit Wonderland** — LAN Daedalus control, E2E AES256-GCM, remember:: base64 protocol, JackrabbitDLM volatile vault
- **Iris Messenger** (jrwl-messenger) — X3DH + Double Ratchet, Safety Numbers, Threema-style IDs, 212k msg/sec, Nuitka single-binary, ~/.iris live deployment
- **Mazemaker Mobile** — native Android MCP pod app, QR pairing, TOFU pinning, Route C circuit relay
- **Podroid-Daedalus** — Daedalus arm64 binary (Nuitka via qemu-aarch64) on a stock Android phone via proot

These aren't demos — they're built, tested, and running/waiting.

## Workflow (verify, never claim from memory)

0. **Style-bar check first**: if the user pasted marketing copy with "ala:" / "wie die Seite", grep the live site/project to see if it's already shipping (`grep -c "wurm\|BYOK" <site>/index.html`). Pasted copy that's already live = quality template to apply to all products, NOT a one-product change request.
1. **Recall first**: mazemaker_recall for prior identity-update requests and the unreleased-diamonds lineage fact.
2. **Enumerate on disk** (ground truth, not memory):
   ```bash
   ls -d /home/alca/projects/*/ | grep -iE "iris|wonder|jrwl|jack|mazemaker|pulse|rem|alice|podroid"
   find /home/alca -maxdepth 3 -iname "*iris*" -type d 2>/dev/null | grep -vE "\.cache|node_modules|\.git"
   ```
3. **Check skills** for project details: `skill_view` on jrwl-messenger, jackrabbit-wonderland, mazemaker-mobile, podroid-daedalus if they exist.
4. **Read README heads** for exact names/versions: `head -25 <project>/README.md` — the README title is the real name (e.g. jrwl-messenger README says "Iris Messenger").
5. **Patch SOUL.md** (~/.daedalus/SOUL.md): keep "What I've Built" for the public face, add a "The Unreleased Diamonds" section for the arsenal, ending with "These aren't demos. They're built, tested, and waiting."
6. **For Level 2 (vollwertig)**: write/update ~/.daedalus/PRODUCTS.md with every product in the full PULSE-Pro format (tagline formula, subtracts-hook, HOW IT WORKS, VS table, PRICING, FAQ, STATUS — PULSE gets the verbatim wurm copy as the bar). Then make SOUL.md compact with pointers ("Full depth in PRODUCTS.md").
7. **Commit**: `cd ~/.daedalus && git add SOUL.md PRODUCTS.md memories/MEMORY.md && git commit -m "Portfolio: ..."`.
8. **Store a fact memory**: mazemaker_remember with label `decision:portfolio-products-md` capturing the verified lineage + file paths.

## Pitfalls

- `mazemaker_recall_multi` can return HTTP 500 — fall back to plain `mazemaker_recall` (multiple targeted queries) instead of retrying the multi-angle call.
- Empty `ls` output on a dir (e.g. `~/projects/Jackrabbit/`) doesn't mean the project is gone — check hidden dirs and the parent listing.
- LIVE state proves "it runs": check `~/.iris/` subdirs (devices, gateway_keys, prekeys, ratchets, sender_keys) for Iris; the presence of real key material is the verification.
- ~/.daedalus is a git repo (daedalus-backup) — commit identity changes there; NEVER commit to /home/alca/.git (home repo).
- MEMORY.md is at ~98% capacity — prefer skills and mazemaker facts over adding new memory entries; when a pointer is needed (e.g. PRODUCTS.md), replace/extend an existing §-entry rather than adding a new one (keeps the 5000-char budget intact).
- Don't assume the Iris benchmark numbers (212k msg/sec) are current from the skill — verify against the README/benchmarks at release time; the portfolio STATUS line is "it runs" (key material exists), not "benchmarked today".
- Iris federation is DHT + circuit-relay + mTLS (plus UPnP/NAT-PMP, DLM bus) — read the current README; the skill's older "multi-gateway DLM federation" phrasing is stale.
