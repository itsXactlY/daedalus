# MCP Protocol for Android Integration

## Wonderland SSE Endpoint
`http://localhost:8765/sse` - Local only, no auth needed

## JSON-RPC Format
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "mazemaker_recall",
    "arguments": {"query": "...", "limit": 20}
  }
}
```

## Available Tools (2026)
| Tool | Purpose | Key Params |
|------|---------|-----------|
| mazemaker_recall | Semantic search | query, limit |
| mazemaker_remember | Store memory | content, label, embedding_b64 |
| mazemaker_think | Graph traversal | memory_id, depth |
| mazemaker_graph | Knowledge graph | limit |
| mazemaker_stats | Counts/statistics | - |
| mazemaker_dream | Dream cycle | phase (all/nrem/rem/insight) |
| mazemaker_dream_stats | Last cycle | - |
| mazemaker_prune | Decay edges | threshold, dry_run |
| mazemaker_browse | Recent memories | limit, label_prefix |

## Encryption Notes
- Vault key derived via HKDF(license_jwt.vault_secret, device_fingerprint)
- AES-256 encrypts content before storage
- Public label prefixes skip encryption: skill:, decision:, bug:, auto:, public:, fact:, derived:, dream:, commit:, project: