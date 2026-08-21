# Error Classification Patterns (2026-06-11)

When analyzing ~/.daedalus/logs/errors.log, classify errors by source to identify root cause:

## MCP Connection Errors
- Pattern: `MCP server 'X' failed initial connection after 3 attempts`
- Check: Is the configured port listening?
- Command: `ss -tlnp | grep <port>` or `curl -s http://127.0.0.1:<port>/health`
- Fix: Disable offline servers via `daedalus config set mcp_servers.<name>.enabled false`

### Example (BTQuant)
- 730 errors: Port 8910 configured but not running
- Solution: Disabled btquant MCP server (service offline)

## Background Review Denials (Security Guardrails)
- Pattern: `Background review denied non-whitelisted tool: <tool>`
- Config: `approvals.cron_mode: deny`
- **User preference (2026-06-11)**: User rejected `deny` mode - changed to `allow`
- Tools blocked: read_file, mcp__mazemaker__mazemaker_remember, patch, todo

## Discord API Errors
- Pattern: `Discord API error (404): Unknown Channel` / error code 10003
- Cause: Channel deleted, moved, or bot lacks access
- Fix: Delete cron job or update channel ID in job config

## Rate Limit Errors
- Pattern: `Rate limit exceeded` / HTTP 429
- Cause: Free tier model limits (poolside/laguna-m.1:free)
- Fix: Upgrade model tier or add backoff logic

## Error Source Breakdown Command
```bash
# Count by source
grep -E 'mcp.*failed|background.*denied|discord.*404|rate.*limit' errors.log | \
  awk '{print $NF}' | sort | uniq -c | sort -nr
```