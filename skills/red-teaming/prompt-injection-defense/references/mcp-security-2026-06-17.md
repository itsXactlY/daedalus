# MCP Security Vulnerabilities — 2026-06-17

## Critical RCE Vulnerability in Anthropic MCP Implementation

### Ox Security Discovery
- **Title**: "The Mother of All AI Supply Chains: Critical, Systemic Vulnerability at the Core of Anthropic's MCP"
- **URL**: https://www.ox.security/blog/the-mother-of-all-ai-supply-chains-critical-systemic-vulnerability-at-the-core-of-the-mcp/
- **Severity**: CRITICAL
- **Impact**: Arbitrary Command Execution (RCE) on any system running vulnerable MCP servers

### Attack Vector
The vulnerability enables attackers to execute arbitrary commands on client systems through malicious MCP servers. This affects all MCP integrations including Hermes agents.

## Additional Security Findings

### 1. Anthropic MCP Git Server Vulnerabilities
- **Issue**: 3 critical vulnerabilities
- **Impact**: Unauthorized file access and remote code execution
- **Action Required**: Immediate audit of all MCP Git server integrations

### 2. NSA MCP Security Guidance (May 2026)
- **Document**: 17-page Cybersecurity Information Sheet
- **Key Finding**: Attack paths are "weirder than standard API vulnerabilities"
- **Source**: Reddit r/AZURE discussion

### 3. Community Security Scanning
- **Scope**: 15,923 MCP servers scanned for vulnerabilities
- **Source**: Reddit r/mcp community effort

## New Security Tools

| Tool | Stars | Language | Purpose |
|------|-------|----------|---------|
| agentshield | 884 | TypeScript | AI agent security scanner for MCP servers |
| SecureMCP | 140 | Go | Security auditing tool for MCP misconfigurations |
| mcp-shodan | 137 | TypeScript | CVE/CPE vulnerability intelligence lookup |
| mcp-watch | 132 | TypeScript | Comprehensive MCP server security scanner |
| hexstrike-ai | 9,670 | Python | Cybersecurity tools for AI agents (150+ tools) |

## Security Implications for Hermes Agents

1. **Supply Chain Risk**: MCP servers are now a critical attack surface
2. **Infrastructure Dependency**: VLLM framework vulnerabilities affect MCP servers as critical infrastructure
3. **Multi-Agent Risk**: Systems with root access capabilities represent unprecedented risk vectors

## Recommended Actions

1. **Audit**: Check all Hermes-MCP server connections against the 7 identified security patterns
2. **Implement**: Add runtime skill audit capability for MCP skill verification
3. **Monitor**: Set up alerts for new MCP security research papers
4. **Deploy**: Consider using new security tools (agentshield, SecureMCP, mcp-watch)

## References

- arXiv:2605.22333 - First measurement study of authentication security in real-world MCP servers
- arXiv:2606.04769 - Description-code inconsistency security implications
- arXiv:2605.24069 - MCP poisoning attacks benchmark for LLM agents
- arXiv:2606.11671 - Runtime skill audit techniques
- arXiv:2606.02302 - SeClaw spec-driven security evaluation