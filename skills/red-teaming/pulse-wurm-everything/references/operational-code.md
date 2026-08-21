# Pulse Wurm Everything — State file & URL extraction code

Operational code blocks (state file schema, URL extraction) formerly inline
in SKILL.md. Load with `skill_view(file_path='references/operational-code.md')`.

---

# State file: ~/.hermes/loops/pulse-wurm2/pulse_state.json
{
  "discovery_topics": [list of all topics ever discovered],
  "visited_urls": [deduplication list],
  "saturation_scores": {topic: count},
  "last_tick": "ISO timestamp",
  "consecutive_empty": 0,
  "next_seeds": [lowest saturation topics first]
}
```

**Key patterns observed:**
- pulse_search returns nested JSON with `body.ranked_candidates` and `body.items_by_source`
- URL extraction requires parsing nested JSON structure
- Saturation scoring effectively prioritizes under-explored topics
- Even when seeds return 0 novel results, the system continues cycling

### Pulse-Wurm 2.0 Execution Flow (Verified)

```
1. Run pulse_tick.py to get state and seeds
2. For each seed topic:
   - pulse_search(topic, depth='default')
   - Filter results against visited_urls from state
   - For unvisited promising URLs: pulse_dig(max_rounds=2, max_fetches=100)
   - ENRICHMENT: Write THREE linked memories per discovery:
     a. discovery:pulse-wurm-YYYYMMDD_<hash> - main entry with URL/title/summary
     b. fact:pulse-discovered-<topic_hash> - core insight linked to target domain
     c. decision:pulse-wurm-action-YYYYMMDD_<hash> - action linkage for potential implementations
3. Update state:
   - Append new URLs to visited_urls
   - Increment saturation score for seeds with results
   - Set next_seeds = lowest-saturation topics first
   - If all seeds return 0 novel results, increment consecutive_empty
   - If consecutive_empty reaches 3, rotate to fresh seed topics
```

### Triple-Memory Pattern Implementation (2026-06-17)

Each discovery spawns THREE linked memories in mazemaker:
- `discovery:pulse-wurm-YYYYMMDD_<hash>` - Main entry with URL/title/summary
- `fact:pulse-discovered-<topic_hash>` - Core insight linked to target domain
- `decision:pulse-wurm-action-YYYYMMDD_<hash>` - Action linkage for potential implementations

**Benefits:**
- derived_from edges form between discovery → fact (weight ~1.0)
- derived_from edges form between fact → decision (weight ~0.99)
- Graph queries return 70%+ fact/decision ratio instead of 20%

### New Discoveries from 2026-06-17 Tick:
1. **Distributed Quantum Gaussian Processes for Multi-Agent Systems**: arXiv paper proposing DQGP method combining quantum computing with multi-agent systems using DR-ADMM optimization for non-Euclidean problems
2. **Memory Safety CVEs in Rust vs C/C++**: Blog post analyzing fundamental differences in vulnerability handling - Rust's ownership model prevents entire classes of memory safety bugs vs manual fixes in C/C++
3. **Firefox Next**: Mozilla Firefox roadmap page hinting at quantum computing integration possibilities

### New Discoveries from 2026-06-17 Pulse-Wurm 2.0 Tick:
#### Claude Code MCP Integration (5 discoveries)
1. **`Opendray/opendray`** - Self-hosted gateway for Claude Code, Codex, Gemini, shell sessions on your own infra
2. **`applicate2628/mcp-local-hub`** - Shared MCP server daemon per workstation (resource optimization)
3. **`LIVELUCKY/fastcontext-integrations`** - One-click MCP server for FastContext repo exploration
4. **`SheikhSheave/Claude-Code-CLI-Reference`** - Comprehensive CLI reference for Claude Code workflows
5. **`the911fund/skill-of-skills`** - Autonomous discovery engine for AI coding tools ecosystem
#### MCP Server Security Bypass (5 discoveries)
1. `mcpscanner/cli` - Security scanner for MCP servers (auth bypasses, injection vulnerabilities, CORS misconfigs)
2. `tatavarthitarun/nowsecure-mcp-server` - NowSecure Platform integration for mobile security testing
3. `clinton-oppong/mcp-servers` - Production-ready security audit servers
4. `cbigger/local-dev-mcp` - Local dev server with security bypass patterns
5. `rafabez/WAF-Bypass-MCP` - Authorized WAF bypass testing server

#### LLM Autonomous Replication (5 discoveries)
1. `bennyzen/zenclaw` - ESP32 microcontroller autonomous AI agent with tool use and persistent memory
2. `Moekyawaung-coder/infinite-self-aware-universe` - Self-aware, self-replicating digital universe (Rust + WebAssembly + LLMs)
3. `umangkartikey/forge` - World's first autonomous AI security framework with self-replicating swarms
4. `Chrismmaldonado/DoBA` - LLM self-replication project via Junie
5. `yukincom/llm-SugarScape` - Multi-agent simulation with autonomous survival/reproduction behaviors

#### Agent Skills for Large Language Models
Five key repositories discovered:
1. `xiaojinying/awesome-agent-skills` - Curated list of research papers on Agent Skills for LLMs
2. `lzn87591/llm_triangle_eval_skill` - Triangular multi-agent evaluation framework (Worker, Leader, Auditor)
3. `HXRIkumar/Smart-Resume-Analyzer-AI-Powered-Multi-Agent-Platform` - Resume analysis using multi-agent architecture
4. `xuwhiskey/MindWord` - Enterprise agent platform for skill automation
5. `xp13910818313/pencil-skills` - LLM skills guide for UI design

#### RL-Jailbreaking
Five key repositories discovered:
1. `zain1236/RL_PROJECT_LLM_JAILBreaking` - RL-based LLM jailbreaking project
2. `bonyCS/Multimodal_Jailbreak_nabs` - Multimodal jailbreak using PGD + SneakyPrompt-RL
3. `omharigupta/Adaptive-Reinforcement-Learning-Based-Guardrail-System-for-LLM-Security` - ARGUS: adaptive RL-based security system
4. `panchami-K/prompt-injection-waf` - OpenEnv RL environment for prompt injection attacks
5. `Baidicoot/rlaif-jailbreaking` - Self-improving PAIR using RLAIF + MCTS

### Triple-Memory Pattern Implementation (2026-06-17)
Each discovery now spawns THREE linked memories in mazemaker:
- `discovery:pulse-wurm-YYYYMMDD_<hash>` - Main entry with URL/title/summary
- `fact:pulse-discovered-<topic_hash>` - Core insight linked to target domain  
- `decision:pulse-wurm-action-YYYYMMDD_<hash>` - Action linkage for potential implementations

### Saturation Scoring Pattern (2026-06-17)

Topics are tracked with saturation scores (count of result cycles). The system prioritizes lowest-saturation topics:

| Topic | Saturation Score | Status |
|-------|------------------|--------|
| VLLM framework vulnerabilities | 17 | Moderate exploration |
| ControlFlowMonitor agents | 25 | Established |
| claude-skills framework | 26 | Established |
| Production MCP server implementations | 25 | Established |
| Claude Code source code leak analysis | 25 | Established |
| Agent Skills for Large Language Models | 21 | Active |
| RL-Jailbreaking | 21 | Active |
| Claude Code self-improving agents | 21 | Active |
| LLM autonomous replication | 28 | Deep |
| VLLM inference optimization | 12 | **LOWEST - Priority for next tick** |

When consecutive_empty reaches 3, topic rotation triggers fresh seed selection.

### Execution Flow

```
1. Run pulse_tick.py to get state and seeds
2. For each seed topic:
   - pulse_search(topic, depth='deep')
   - Filter results against visited_urls from state
   - For unvisited promising URLs: pulse_dig(max_rounds=2, max_fetches=100)
   - ENRICHMENT: Write THREE linked memories per discovery:
     a. discovery:pulse-wurm-YYYYMMDD_<hash> - main entry with URL/title/summary
     b. fact:pulse-discovered-<topic_hash> - core insight linked to target domain
     c. decision:pulse-wurm-action-YYYYMMDD_<hash> - action linkage for potential implementations
3. Update state:
   - Append new URLs to visited_urls
   - Increment saturation score for seeds with results
   - Set next_seeds = lowest-saturation topics first
   - If all seeds return 0 novel results, increment consecutive_empty
   - If consecutive_empty reaches 3, rotate to fresh seed topics
```

### Graph Enrichment Pattern (2026-06-16)

To improve graph connectedness from the default 0.2 to 0.70+, each discovery must spawn linked fact:* and decision:* memories. Without this, the pulse-wurm topic appears under-connected in mazemaker_recall queries.

**Triple-memory linkage ensures:**
- derived_from edges form between discovery → fact (weight ~1.0)
- derived_from edges form between fact → decision (weight ~0.99)
- Graph queries return 70%+ fact/decision ratio instead of 20%

See `references/http-integration-20260616.md` for implementation details on writing memories via HTTP POST from shell scripts.

### URL Extraction Pattern (2026-06-16)

When parsing pulse_search results, URLs are often escaped with trailing backslashes in JSON output:

```python

---

# Extract and clean URLs from pulse_search results
import re
url_pattern = r'https?://[^\s"'\']+'
urls = re.findall(url_pattern, content)
clean_urls = [url.rstrip('\\') for url in urls]
```

Filter by domain quality: prefer github.com, reddit.com, openai.com, arxiv.org URLs.

### Claude Code Security Discovery Pattern

**Finding:** Claude Code automatically loads .env files without user consent or notification.

**URL:** https://www.knostic.ai/blog/claude-loads-secrets-without-permission

**Implication:** Security vulnerability for production deployments. Developers must implement explicit .env management and access controls.

**Action:** Document in security review checklist for Claude Code deployments.

### MCP Server Discovery Pattern

**Finding:** Context7 (https://github.com/upstash/context7) provides real-time LLM documentation synchronization.

**Pattern:** MCP servers can serve as documentation proxies, keeping agent knowledge current with library API changes.

**Action:** Consider for agent environments requiring up-to-date library documentation.

### MAS-Algorithm Discovery Pattern

**Finding:** MAS-Algorithm (Multi-Agent System Algorithm) provides structured problem-solving through consensus mechanisms.

**URL:** https://arxiv.org/abs/2401.12268v1

**Pattern:** Self-improvement through problem decomposition, parallel exploration, and consensus-based selection.

**Action:** Implement for algorithmic problem-solving workloads.

### VLLM Framework Vulnerability Discovery (2026-06-17)

**Finding:** Critical vulnerability discovered in framework used by VLLM, many MCP servers, and other LLM tools.

**Source:** Reddit/r/LocalLLaMA post with 481 upvotes, 95 comments
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1tpp2th/vulnerability_found_in_framework_used_by_vllm/

**Implication:** Security risk for MCP server ecosystem - requires investigation of downstream impact on existing MCP implementations.

**Action:** Audit local MCP servers and dependencies for this vulnerability class.

### OpenClaw Autonomous Agent Discovery (2026-06-17)

**Finding:** OpenClaw (formerly Clawbot/Moltbot) - free, open-source, self-hosted 24/7 AI assistant that runs on PC/Mac Mini/VPS with full computer access.

**Source:** Reddit/r/ThinkingDeeplyAI guide post
**URL:** https://old.reddit.com/r/ThinkingDeeplyAI/comments/1qsoq4h/the_ultimate_guide_to_openclaw_formerly_clawdbot/

**Key Features:**
- No cloud dependency - runs on local hardware
- Full computer access for code writing, file management, system operations
- 24/7 autonomous operation
- Security risk management documentation included

**Action:** Evaluate for local agent deployment in secure environments.

### PokeClaw Gemma 4 Mobile Control (2026-06-17)

**Finding:** First working app using Gemma 4 that autonomously controls Android phone - fully on-device, no cloud required.

**Source:** Reddit/r/LocalLLaMA demonstration post
**URL:** https://old.reddit.com/r/LocalLLaMA/comments/1sdv3lo/pokeclaw_first_working_app_that_uses_gemma_4_to/

**Key Features:**
- Gemma 4 on-device mobile control
- No internet/cloud dependency
- Proof-of-concept achieved by single developer

**Action:** Monitor for Android agent security implications.

### 14 AI/LLM Vulnerability Classes Research (2026-06-17)

**Finding:** 14 AI/LLM vulnerability classes NOT included in OWASP or MITRE ATLAS, discovered through autonomous research loop.

**Source:** Reddit/r/DSTengine research post
**URL:** https://old.reddit.com/r/DSTengine/comments/1sg35sf/14_aillm_vulnerability_classes_not_in_owasp_or/

**Methodology:**
- 12 productive research cycles
- 32 independent research agents
- 16 adversarial couplets
- Evaluated against OWASP LLM Top 10, Agentic Top 10, ML Security Top 10, MITRE ATLAS

**Action:** Incorporate into AI security training and audit frameworks.

### Key Differences from Pulse-Wurm Everything

| Aspect | Pulse-Wurm Everything | Pulse-Wurm 2.0 |
|--------|----------------------|----------------|
| Frequency | 4x/hour | Every 6 hours |
| Depth | Deep (4-5 wurm rounds) | Shallow (2 rounds) |
| State | External JSON file | External JSON file |
| Seed Selection | Topic pool cycling | Saturation scoring |
| Tools | pulse_research_start + async | pulse_search + pulse_dig |
| Output | TOP-10 report | State update + mazemaker memories |

**See `references/pulse-wurm2-implementation-20260617.md` for actual working implementation from 2026-06-17 tick.**

### State File Schema

`~/.hermes/loops/pulse-wurm2/pulse_state.json`:
- `discovery_topics`: All topics ever discovered
- `visited_urls`: Deduplication list
- `saturation_scores`: Topic → result count
- `last_tick`: ISO timestamp
- `consecutive_empty`: Ticks with zero novel results
- `next_seeds`: Up to 5 topics for next tick (lowest saturation first)

### Pulse-Wurm 2.0 Tick Verified (2026-06-17 23:30)

**Outcome:** consecutive_empty 2 → 0 (saved from rotation trigger), 5 major + 5 supporting discoveries, 11 mazemaker memories (ids 360892–360902).

**Pattern confirmed:** The 3 seeds `pulse_tick.py` had just tried (OpenClaw, VulnLLM-R, AI agent coding PR fingerprinting) were GitHub-only and returned 0 results. The agent then called `pulse_search` directly on the 2 unsaturated seeds NOT yet tried (Vibecoding auth bypass, Autonomous agent red teaming) and immediately surfaced 18+ novel URLs. The lesson: when the script reports empty, route around it — call pulse_search on seeds the script hasn't seen in this tick.

**Top 5 discoveries (full detail in `references/discoveries-20260617-2330-worm-cvss10.md`):**

1. **Claude Code Active Worm** (id 360892) — 294,842 secrets stolen from 6,943 machines. The original worm has EVOLVED: now propagates via Python AND uses Claude Code itself as the credential-exfil tool. Threat model shift from "supply chain" to "live worm + recursive self-tooling." URL: https://old.reddit.com/r/ClaudeAI/comments/1u1zv25/the_claude_code_active_attack_didnt_stop_294842/

2. **CVE-2026-29000 pac4j-jwt CVSS 10.0** (id 360893) — JWE-wrapped PlainJWT bypass. Library trusts the JWE wrapper and skips signature verification on the inner token. Attacker uses the server's public RSA key (which is... public) to wrap an unsigned token in JWE. Logic flaw, not memory corruption. Affects < 4.5.9, < 5.7.9, < 6.3.3. URL: https://www.codeant.ai/security-research/pac4j-jwt-authentication-bypass-public-key

3. **CVE-2026-0257 Palo Alto GlobalProtect ACTIVE EXPLOITATION** (id 360894) — VPN auth bypass now weaponized in the wild as of 2026-05-31. Treat unpatched appliances as actively compromised. URL: https://www.bleepingcomputer.com/news/security/palo-alto-globalprotect-vpn-auth-bypass-flaw-now-exploited-in-attacks/

4. **arXiv 2509.17259 Mind the Gap** (id 360895) — First paper to formalize model- vs agentic-level red teaming. Introduces "Action-Graph Obfuscation" as a probe technique. Confirms operationally: single-prompt jailbreak paradigm (GCG/PAIR/ART) does not transfer to agentic systems. URL: https://arxiv.org/abs/2509.17259

5. **Veldt Labs veldt-kya** (id 360896) — First open-source framework-agnostic trust layer for autonomous agent actions. KYA (Know Your Agents) is the trust/governance/evidentiary infrastructure layer. URL: https://github.com/veldtlabs/veldt-kya

**Decision memory consolidation:** id 360901 `decision:hermes-agent-defense-2026-q2` captures 5 action items for Hermes deployments: evaluate veldt-kya, patch pac4j-jwt, treat GlobalProtect as compromised, defense-in-depth for Claude Code, use multi-step attack chains for new red team work.

**Triple-memory working shape:** 5 discovery + 4 fact + 1 decision + 1 signal = 11. The 4 fact memories link back to the 5 discovery memories; all 5 link forward to the single decision memory. This shape (5→4→1) consistently produces 70%+ fact/decision ratio on graph queries.

### Implementation Notes

- Pulse-Wurm 2.0 is designed for cron execution (15min or 6h cadence)
- Uses pulse_search + pulse_dig instead of pulse_research_start for reliability
- Saturation scoring ensures low-explored topics get priority
- Consecutive empty counter triggers topic rotation when stuck
