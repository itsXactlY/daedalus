# Stripe Skills Implementation

## Files Created

- `/home/alca/projects/atra/stripe_integration/StonEMM_Server.py` - MCP Server on port 8920
- `/home/alca/projects/atra/stripe_integration/spend_manager.py` - Budget allocation logic
- `/home/alca/projects/atra/bridge/trading_to_stripe.py` - Bridge logic

## MCP Tools Provided

| Tool | Description | Parameters |
|------|-------------|------------|
| stripe_check_connection | Verify Stripe API connection | none |
| stripe_list_products | List available products | limit: int |
| stripe_create_checkout | Create checkout session | price_id, success_url, cancel_url, mode |
| stripe_allocate_budget | Allocate PnL to categories | revenue, growth_pct, operating_pct, savings_pct |
| stripe_purchase_compute | Purchase compute credits | provider, amount_usd |

## Integration with Existing Billing

The mazemaker-v2-stack already has:
- `backend/server/billing.py` with full Stripe integration
- HMAC-verified webhook at `/stripe/webhook`
- Tier system (free/payg/pro/enterprise)

This MCP server wraps those capabilities for Hermes agents.

## Budget Allocation Function

```python
def allocate_budget(revenue: float) -> Dict[str, float]:
    return {
        "growth": revenue * 0.50,    # Scale
        "operating": revenue * 0.30, # Operate
        "savings": revenue * 0.20    # Reserve
    }
```

## Vendor Catalog

```python
VENDORS = {
    "cloudflare_workers": {"cost": 5.0, "category": "compute"},
    "modal_gpu": {"cost": 25.0, "category": "compute"},  
    "openrouter_credits": {"cost": 10.0, "category": "ai_models"}
}
```

## Startup Command

```bash
cd /home/alca/projects/atra/stripe_integration
python3 StonEMM_Server.py --port 8920 &
curl http://localhost:8920/health
```