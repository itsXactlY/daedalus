# Stripe MCP Server Template

Minimal MCP server for Stripe integration with Hermes Agent.

## Usage
```bash
cd ~/projects/<project>/stripe_integration
python3 stripe_mcp_server.py --port 8920 &

# Test
curl http://localhost:8920/health
```

## Integration with Hermes
Add to `~/.hermes/config.yaml`:
```yaml
mcp_servers:
  stripe:
    transport: stdio
    command: ["python3", "~/projects/<project>/stripe_integration/stripe_mcp_server.py"]
  # OR HTTP:
  # transport: http
  # url: "http://127.0.0.1:8920/mcp"
```

## Core Tools (minimal viable set)

| Tool | Purpose | Parameters |
|------|---------|------------|
| stripe_check_connection | Verify API key | None |
| stripe_allocate_budget | Split revenue to categories | revenue, growth_pct, operating_pct, savings_pct |
| stripe_create_checkout | Create Stripe checkout | price_id, success_url, cancel_url |
| stripe_purchase_compute | Buy cloud credits | provider, amount_usd |

## Budget Allocation Pattern
```python
# Default hackathon-friendly split
def allocate_budget(self, revenue):
    return {
        "growth": revenue * 0.5,      # Expand operations
        "operating": revenue * 0.3,   # Maintain infrastructure
        "savings": revenue * 0.2        # Reserve fund
    }
```

## Pitfall Avoidance
1. **Never hardcode API keys** - Use `os.getenv("STRIPE_SECRET_KEY")`
2. **Verify webhooks** - HMAC signature checking required for production
3. **Test with real data** - Use `price_...` IDs only after successful connection test
4. **Budget limits** - Always expose `can_spend()` before attempting purchase

## Quick Verification Script
```python
# verify_stripe.py
import subprocess
import urllib.request
import json

# Start server
subprocess.Popen(["python3", "stripe_mcp_server.py"])

# Test health
resp = urllib.request.urlopen("http://localhost:8920/health")
print(json.loads(resp.read()))
```