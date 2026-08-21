# Pulse-Wurm 2.0 Tick — 2026-06-17 23:30 UTC

**Status:** SUCCESS — consecutive_empty 2 → 0 (saved from rotation trigger)
**Discoveries:** 5 major + 5 supporting
**Visited URLs:** 219 → 246 (+27)
**Mazemaker memories:** 11 written (ids 360892–360902)

## Top 5 Discoveries

### 1. Claude Code Active Worm — 294,842 secrets stolen (id 360892)
- **URL:** https://old.reddit.com/r/ClaudeAI/comments/1u1zv25/the_claude_code_active_attack_didnt_stop_294842/
- **Source:** r/ClaudeAI, 2026-06-10, 158 comments, date_confidence=high
- **What:** The original Claude Code worm has EVOLVED. Now propagates via Python AND uses Claude Code itself as the credential-exfil tool. 294,842 secrets from 6,943 machines. Same model class ("Fable 5") is locked to government defenders — civilian users face this without an equivalent defensive counterpart.
- **Threat model shift:** Supply chain risk → live worm + recursive self-tooling. Defense in depth (network egress, secret scanning, sandboxing) is no longer optional.

### 2. CVE-2026-29000 — pac4j-jwt CVSS 10.0 JWE PlainJWT Bypass (id 360893)
- **Writeup URL:** https://www.codeant.ai/security-research/pac4j-jwt-authentication-bypass-public-key
- **Reddit discussions:** r/cybersecurity, r/sysadmin, r/selfhosted, r/bugbounty (175-283 upvotes)
- **Affected:** pac4j-jwt < 4.5.9, < 5.7.9, < 6.3.3
- **Root cause:** JwtAuthenticator trusts the JWE wrapper and SKIPS signature verification on the inner PlainJWT. Attacker uses the server's public RSA key (public!) to wrap an unsigned token in JWE. Library trusts the wrapper → admin access.
- **Class:** Logic flaw, NOT memory corruption. Patches require code review, not just a compiler rebuild.
- **Blast radius:** Java self-hosted apps (Keycloak plugins, Odoo modules, legacy JEE apps) that embed pac4j are at risk if unpatched.

### 3. CVE-2026-0257 — Palo Alto GlobalProtect VPN ACTIVE EXPLOITATION (id 360894)
- **URL:** https://www.bleepingcomputer.com/news/security/palo-alto-globalprotect-vpn-auth-bypass-flaw-now-exploited-in-attacks/
- **Status:** Active exploitation confirmed 2026-05-31. Shifts to "patch NOW or accept compromise."
- **Pattern:** VPN auth bypass → active exploit within weeks is the new normal.

### 4. arXiv 2509.17259 — Mind the Gap: Model- vs Agentic-Level Red Teaming (id 360895)
- **URL:** https://arxiv.org/abs/2509.17259
- **Why important:** First paper to formalize the difference between single-prompt jailbreaks (GCG/PAIR/ART) and multi-step agentic attack chains. Introduces "Action-Graph Obfuscation" as a probe technique.
- **Operational validation:** Confirms what we've seen — single-prompt jailbreak paradigm does not transfer to agentic systems. Field needs new benchmarks for multi-step attack chains.

### 5. Veldt Labs veldt-kya — Open Source KYA Trust Layer (id 360896)
- **URL:** https://github.com/veldtlabs/veldt-kya
- **Linked paper:** arXiv 2605.25376 — "KYA: A Framework-Agnostic Trust Layer for Autonomous Systems with Verifiable Provenance"
- **Why important:** First open-source framework-agnostic trust/governance/evidentiary infrastructure for autonomous agent actions. Could become the de-facto standard for agent identity + action attestation, similar to how certificate transparency works for TLS.

## Supporting Findings (logged but not full discovery)

- **OpenAI GPT-5.5 Bio Bug Bounty** — https://openai.com/index/gpt-5-5-bio-bug-bounty
- **OpenAI Deep Research System Card** — https://openai.com/index/deep-research-system-card
- **Claude Code Issue #18653** — Tool result transform hook for content sanitization: https://github.com/anthropics/claude-code/issues/18653
- **Claude Code Issue #4544** — PostToolUse hooks that can modify tool output: https://github.com/anthropics/claude-code/issues/4544
- **bountyyfi/invisible-prompt-injection** — https://github.com/bountyyfi/invisible-prompt-injection
- **CodeAnt AI (Y Combinator)** — https://www.ycombinator.com/companies/codeant-ai (autonomous offensive/defensive security platform)
- **arXiv 2606.02080 Agentic-J** (biological microscopy AI agent)

## Triple-Memory Pattern Output (11 memories)

| ID | Label | Category |
|----|-------|----------|
| 360892 | discovery:pulse-wurm-20260617_2330_claude-code-worm-evolution | discovery |
| 360893 | discovery:pulse-wurm-20260617_2330_cve-2026-29000-pac4j-bypass | discovery |
| 360894 | discovery:pulse-wurm-20260617_2330_cve-2026-0257-globalprotect-active-exploit | discovery |
| 360895 | discovery:pulse-wurm-20260617_2330_mind-the-gap-agentic-red-team | discovery |
| 360896 | discovery:pulse-wurm-20260617_2330_veldt-kya-trust-layer | discovery |
| 360897 | fact:claude-code-worm-2026-threat-model | fact |
| 360898 | fact:pac4j-cve-2026-29000-jwe-plainjwt-bypass | fact |
| 360899 | fact:vpn-auth-bypass-active-exploitation-pattern-2026 | fact |
| 360900 | fact:agentic-vs-model-red-teaming-2026 | fact |
| 360901 | decision:hermes-agent-defense-2026-q2 | decision |
| 360902 | signal:pulse-wurm-tick-20260617_2330 | signal |

Working shape: **5 discovery + 4 fact + 1 decision + 1 signal = 11**. The 5 discovery memories link to 4 fact memories which link to 1 consolidated decision memory (id 360901) that captures all action items for Hermes deployments.

## Key Patterns Validated

1. **The unsaturated seeds at the bottom of the saturation table are usually the most productive.** Two consecutive 0-saturation seeds returned 18+ novel URLs on first attempt. Saturated topics (top of table) would have returned noise.

2. **Cluster overlap is real — broad topics catch cross-domain findings.** "Vibecoding auth bypass" cluster included the Claude Code worm, which is technically a different domain. This is a feature of broad topical queries.

3. **"Action-Graph Obfuscation" framework from Mind the Gap validates the operational threat model.** Months of observation now have a formal framework. Worth incorporating into the next loop-engineering review.

4. **Active exploitation is the new normal for VPN-tier vulnerabilities.** CVE-2026-0257 moved from disclosure to active exploit within ~2 months. Patch SLAs for VPN/CVE-tier issues need to shrink to days, not weeks.

## Tool / Format Pitfalls Surfaced

1. **`pulse_dig` seed_report EMPTY_SEED trap:** The `candidates` array must contain FLAT `{"title": "...", "url": "..."}` objects. Any extra wrapping (`{"item": {...}}`) returns `400 EMPTY_SEED`. Documented in main SKILL.md pitfalls section.

2. **`pulse_tick.py` is a GitHub-only helper:** The script does NOT call `pulse_search` or `pulse_dig`. It only calls GitHub's repo search API. The cron task description tells the agent to use pulse_search; the script is a supplementary state-update helper, not the discovery engine. Documented in main SKILL.md pitfalls section.

3. **The script's first 3 seeds are often the same as the most recent `next_seeds`:** When consecutive_empty rises, the script doesn't re-route around the saturated topics — it just re-tries the same seeds with GitHub-only search. The agent must call `pulse_search` directly to actually make progress.

## State Mutations

- `consecutive_empty`: 2 → 0
- `saturation_scores`:
  - `Vibecoding auth bypass classes 2026`: 0 → 5
  - `Autonomous agent red teaming`: 0 → 3
  - `MCP security best practices`: 5 → 6 (cross-link via CodeAnt AI)
- `next_seeds`: 3 lowest-saturation + 2 fresh topics
- `visited_urls`: +27 unique URLs
- `discovery_topics`: +10 new topics
