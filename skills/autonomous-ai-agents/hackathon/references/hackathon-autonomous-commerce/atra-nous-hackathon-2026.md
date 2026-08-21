# ATRA - Nous Research Hackathon 2026

## Live Infrastructure Status

| Endpoint | Status | Notes |
|----------|--------|-------|
| Mazemaker MCP | `http://127.0.0.1:8765/health` | Online (205,679 memories) |
| BTQuant MCP | `http://127.0.0.1:8910/health` | Offline (needs startup) |
| Mazemaker API | `https://api.mazemaker.dev/v1/health` | Production |
| Remainder API | `https://api.remainder.online/health` | Production |

## Stripe Integration (Existing)

The Stripe billing infrastructure already exists in mazemaker-v2-stack:
- `backend/server/billing.py` - Stripe Checkout, Portal, Webhooks
- `/stripe/webhook/pulse` - Webhook endpoint at remainder.online
- Price IDs configured for existing products

**No new billing endpoint needed** - bridge to existing.

## Budget Allocation Pattern

```python
# Standard split for hackathon demos
BUDGET_SPLIT = {
    "growth": 0.50,    # Scale infrastructure
    "operating": 0.30, # API credits, data
    "savings": 0.20    # Reserve fund
}

# Example triggers
AUTO_PURCHASE_THRESHOLD = 1000  # $1k+ profit triggers compute buy
TIER_THRESHOLDS = {
    "modal_gpu": 25.0,      # $25/month
    "openrouter_100k": 10.0, # $10/100k tokens
    "cloudflare_workers": 5.0  # $5/month base
}
```

## Demo Script (Verified Working)

```bash
cd /home/alca/projects/atra
python3 demo/demo_runner.py
```

Output shows $1,247.33 PnL → $623.66/$374.20/$249.47 allocation.

## Cloudflare Worker Deployment

```bash
cd /home/alca/projects/atra/cloudflare_worker
# Ensure wrangler installed
npm install -g wrangler
# Login (requires CF account)
wrangler login
# Deploy
wrangler deploy
```

Worker creates budget DO at: `https://attra-worker.mazemaker.dev/pnl`