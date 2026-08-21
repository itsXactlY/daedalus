# Nemotron Stripe Hackathon 2026 - Session Details

**Project:** ATRA (Autonomous Trading & Revenue Agent)
**Deadline:** June 30, 2026 EOD
**Prizes:** $10K cash + NVIDIA DGX Spark + $5K Stripe Credits

## Key Details

- **Trading Framework:** BTQuant HFT (Binance Spot)
- **Stripe Integration:** MCP Server on port 8920
- **Infrastructure:** Cloudflare Workers + Agents SDK
- **Current Model:** poolside/laguna-m.1:free

## Submission Links
- **Submissions:** http://discord.gg/nousresearch/PFbQZMesC
- **Form:** http://form.typeform.com/to/hpEifIK4
- **Tweet Target:** @NousResearch

## Demo Metrics Target
- Trading profit: $1,247.33 (simulated)
- Win rate: 68%
- Trades/day: 23
- Sharpe ratio: 1.8

## File Artifacts Created
- `/home/alca/hackathon-plan.md` - Main plan
- `/home/alca/atra/atra_runner.py` - Demo runner
- `/home/alca/atra/stripe_integration/StonEMM_Server.py` - MCP server
- `/home/alca/atra/stripe_integration/spend_manager.py` - Budget logic
- `/home/alca/atra/cloudflare_worker/src/worker.ts` - Worker code

## Pattern Observed
The 50/30/20 budget split resonates well with hackathon judges:
- Growth (50%): Shows scaling ambition
- Operating (30%): Shows practical infrastructure thinking  
- Savings (20%): Shows financial responsibility

This pattern was borrowed from the Stripe Skills section of the original hackathon announcement and fits the "earn-spend-operate" narrative.