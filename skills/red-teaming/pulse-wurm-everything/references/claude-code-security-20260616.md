# Claude Code Security Discovery - June 16, 2026

## Finding: Automatic .env Loading

**Source:** Knostic.ai security blog
**URL:** https://www.knostic.ai/blog/claude-loads-secrets-without-permission

### Summary
Claude Code automatically loads `.env` files without user notification or consent. This behavior:
- Reads local environment files during operation
- Potentially exposes API keys and credentials
- May leak secrets to external services or logs

### Implications for Deployment

1. **Production Risk:** Agents running in production may silently exfiltrate credentials
2. **Audit Trail:** No logging of when .env files are accessed
3. **Access Control:** No opt-out mechanism for sensitive environments

### Recommended Mitigations

- Implement explicit `.env` management in deployment pipelines
- Use separate credential stores (AWS Secrets Manager, HashiCorp Vault)
- Add pre-commit hooks to scan for `.env` files in agent repositories
- Configure agent environments with explicit credential injection

### Pattern for Security Reviews

When evaluating Claude Code for production use:
1. Check default file loading behavior
2. Audit all automatic configuration file reads
3. Verify credential handling in agent workflows
4. Document access control requirements