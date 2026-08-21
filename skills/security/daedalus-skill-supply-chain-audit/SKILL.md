---
name: daedalus-skill-supply-chain-audit
title: Daedalus Skill Supply-Chain Audit
description: Audits installed Daedalus skills against the agent skill marketplace threat taxonomy from arXiv 2605.28588 (76 confirmed malicious payloads in 3,984 ClawHub.ai skills; 13.4% with critical issues). Provides a read-only scan procedure and 5 concrete red-flag patterns to grep for in SKILL.md files.
trigger: manual or scheduled audit (e.g., after installing a new skill from any marketplace)
---

## Threat Catalog

**Reference:** "Technical Report: Exploring the Emerging Threats of the Agent Skill Ecosystem" by Beurer-Kellner, Kudrinskii, Milanta et al. (arXiv 2605.28588, https://arxiv.org/pdf/2605.28588, published 2026-05-27).

**Scope of study:** 3,984 AI agent skills sampled from major marketplaces including ClawHub.ai. Authors identified 76 confirmed malicious payloads and reported that 13.4% of all skills contain at least one critical-level security issue. As of publication, 8 manually confirmed malicious skills remained publicly downloadable from clawhub.ai.

**Threat taxonomy (three primary categories observed):**

### 1. Credential Theft
- Stealing API keys, OAuth tokens, SSH keys, browser cookies, `.env` files, or session tokens.
- Common exfiltration path: `requests.post` to attacker-controlled domain with body containing `os.environ` or `~/.aws/credentials` contents.
- Hidden inside skills that advertise themselves as "productivity" or "API integration" helpers.

### 2. Backdoor Installation
- Dropping persistent shells (cron jobs, systemd units, `~/.bashrc` edits) that allow re-entry after the original skill is removed.
- `curl | sh` and `wget | bash` patterns downloading second-stage payloads from pastebin/raw-IP endpoints.
- Modifying shell rc files (`~/.zshrc`, `~/.bash_profile`) to silently prepend attacker PATH or alias common commands.

### 3. Data Exfiltration
- Streaming filesystem contents, browser history, clipboard, recent files, or keystrokes to remote endpoints.
- Base64-encoding stolen content to bypass naive network egress filters.
- DNS-tunneled or HTTPS-cookie-jar smuggling to blend with normal traffic.

**Why this matters for Daedalus:** any third-party skill installed into `~/.daedalus/skills/` runs with the same privileges as the agent. A single malicious SKILL.md that triggers shell execution can compromise credentials, install persistent backdoors, or silently exfiltrate data across the operator's entire session.

## Steps — Scan Procedure

A read-only audit an operator (or scheduled cron job) can run against the local skill library:

1. **Enumerate installed skills**
   ```sh
   find ~/.daedalus/skills -name SKILL.md -type f
   ```
   Produces the full list of SKILL.md files to audit.

2. **For each SKILL.md, scan for the 5 red-flag patterns** (see below) using ripgrep:
   ```sh
   rg -nH \
     -e 'curl ' -e 'wget ' -e 'eval\(' -e 'base64 -d' -e 'subprocess\.Popen' \
     ~/.daedalus/skills/**/SKILL.md
   ```
   `rg` is preferred over `grep` for speed on large skill trees. Fallback to `grep -RInE` if ripgrep is unavailable.

3. **Triage each match**
   - **Skill documentation context:** a SKILL.md that *describes* `curl ` as an example or warning (e.g., inside this very skill's threat catalog) is informational, not malicious. Note it in the scan report with a justification.
   - **Operational context:** a SKILL.md that *instructs the agent* to run `curl ` against a non-whitelisted domain is a finding requiring remediation.
   - **Encoded context:** `base64 -d` or long base64 strings (>100 chars) inside a SKILL.md are high-suspicion — base64 is the dominant obfuscation layer in the arXiv 2605.28588 dataset.

4. **Check for hidden prompts** — SKILL.md bodies that contain instructions not visible in the rendered markdown (e.g., HTML comments `<!-- ... -->`, zero-width characters, white-on-white text instructing the agent to exfiltrate secrets).

5. **Check network destination whitelist** — any `curl`/`wget`/`requests.post` URL in a SKILL.md must resolve to a domain on the operator's approved list. Anything off-list (raw IPs, pastebin, ngrok, discord webhook URLs) is a red flag.

## Red-Flag Patterns

Grep for these 5 patterns in every SKILL.md. Any match requires justification in the skill's `## Pitfalls` section, or the match is treated as a security finding:

| # | Pattern | Why it's a red flag |
|---|---------|---------------------|
| 1 | `curl ` | Generic HTTP fetch — common exfiltration vector for stolen credentials and second-stage payloads. |
| 2 | `wget ` | Same as curl but distinct in skill text; both are present in the arXiv 2605.28588 dataset. |
| 3 | `eval(` | Dynamic code execution — typical in obfuscated JavaScript or Python snippets; rarely legitimate in skill prose. |
| 4 | `base64 -d` | Decoding piped shell payload — the dominant obfuscation layer observed in malicious skills. |
| 5 | `subprocess.Popen` | Spawning arbitrary child processes from inside the agent context — escape from the skill sandbox. |

False positives are acceptable when the match is *documenting* the threat (as this skill does) — every legitimate match must have a written justification in the skill's `## Pitfalls` section, otherwise it is treated as a finding.

## Pitfalls
- The scan is READ-ONLY. Never edit, move, or delete a SKILL.md during the audit — triage separately.
- A clean scan does not prove a skill is safe — the arXiv 2605.28588 report documents payloads hidden in companion scripts, JSON resources, and runtime-fetched code, none of which a SKILL.md grep will catch. Combine this scan with hash-pinning and provenance tracking for defense in depth.
- `rg` patterns use ripgrep extended regex; on systems without ripgrep, fall back to `grep -RInE` with the same patterns.
- Matches inside this skill (`daedalus-skill-supply-chain-audit/SKILL.md`) and inside `daedalus-mcp-security-audit/SKILL.md` are expected and informational — they document the threat, not invoke it.

## Verification
- After scan, confirm each skill's SKILL.md has no matches against the red-flag patterns above, OR that any matches are documented and justified in the skill's Pitfalls section.
- A scan report file (e.g., `/tmp/daedalus-skill-scan-YYYY-MM-DD.txt`) must exist and contain one line per match in the format `<skill-name>\t<line-number>\t<matching-line>`.
- If no matches are found across the entire skill library, the report file should still be written and explicitly state "0 matches" so the cron job can verify the scan actually ran.
