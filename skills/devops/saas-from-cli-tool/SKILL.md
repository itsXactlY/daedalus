---
name: saas-from-cli-tool
version: "0.0.1"
description: "Turn any CLI tool into a monetized cloud API — FastAPI wrapper, Stripe billing, nginx frontend, Docker/systemd deployment, and source-available commercial licensing."
prerequisites:
  commands: [python3, nginx, docker, stripe CLI]
metadata:
  hermes:
    tags: [fastapi, stripe, nginx, docker, systemd, saas, api-gateway, billing, monetization, commercial-license]
    related_skills: [pulse]
    requires:
      env:
        - STRIPE_SECRET_KEY
        - STRIPE_WEBHOOK_SECRET
        - PU_API_KEYS
        - PU_ADMIN_KEY
argument-hint: 'build saas api from cli tool, monetize cli tool as service'
homepage: ~/projects/pulse-cloud
license: Commercial
---

# SaaS-from-CLI-Tool Pattern

> The pattern: take any working CLI tool → wrap in FastAPI → add API key auth + rate limiting → connect Stripe for billing → deploy with nginx + systemd/Docker.

Use when: You have a CLI tool that works, users want to pay for access, and you want to run it as a hosted API.

## Architecture

```
Customer Request (curl / SDK)
    ↓
Cloudflare (SSL, CDN, DDoS protection)
    ↓
nginx (TLS termination, rate limit zones, security headers)
    ↓
FastAPI (Auth, Rate Limiting, Stripe Webhook, CLI Runner)
    ↓
Your CLI Tool (subprocess call)
    ↓
SQLite (cache, usage tracking)
```

## Directory Structure

```
project-cloud/
├── api/
│   ├── main.py          # FastAPI app
│   ├── requirements.txt
│   └── .env.example
├── nginx/
│   └── api.conf         # TLS, rate limits, security headers
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── data/            # SQLite DB
├── systemd/
│   └── api.service      # Systemd unit
├── scripts/
│   ├── deploy.sh        # Full server deploy
│   └── setup-stripe.sh  # Create Stripe products
├── docs/
│   └── api.md           # API reference
├── LICENSE              # Commercial/source-available license
└── README.md
```

## Core FastAPI Pattern

### API Key Auth + Rate Limiting

```python
from fastapi import FastAPI, HTTPException, Header
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sqlite3

DB_PATH = "pulse_cloud.db"

limiter = Limiter(key_func=get_remote_address)

def parse_api_key(api_key: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key = ?", (api_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
```

### Stripe Webhook Handler

```python
from fastapi import Request
import stripe

stripe.api_key = settings.stripe_secret_key

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    
    # Handle: customer.subscription.created/deleted
    if event["type"] == "customer.subscription.created":
        customer_id = event["data"]["object"]["customer"]
        price_id = event["data"]["object"]["items"]["data"][0]["price"]["id"]
        tier = "pro" if price_id == settings.stripe_price_pro else "business"
        # Create API key for customer...
```

### Run CLI Tool as Subprocess

```python
import asyncio, json

async def run_cli(q: str, depth: str = "default") -> dict:
    cmd = [
        "python3", settings.cli_script_path, q,
        "--emit=json", "--no-progress"
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        return {"error": stderr.decode()[:500]}
    
    # Parse JSON output from CLI
    for line in reversed(stdout.decode().strip().split("\n")):
        try:
            return json.loads(line)
        except:
            continue
    return {"error": "No parseable output"}
```

## Stripe Products Setup

```bash
# Install Stripe CLI
curl https://raw.githubusercontent.com/stripe/stripe-cli/master/install.sh | bash
stripe login

# Create products and prices
stripe products create --name="SaaS Tool Free" --description="100 calls/month"
stripe products create --name="SaaS Tool Pro" --description="5000 calls/month"
stripe prices create --product="price_xxx" --unit-amount=1900 --currency=eur --recurring[interval]=month
stripe prices create --product="price_yyy" --unit-amount=7900 --currency=eur --recurring[interval]=month
```

## nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Rate limit zones
    limit_req_zone $binary_remote_addr zone=free:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=pro:10m rate=100r/m;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Commercial License Pattern

For turning open code into a monetizable product:

```
PROJECT COMMERCIAL LICENSE v1.0

GRANTED RIGHTS:
- Personal/non-commercial use: PERMITTED
- Running as internal service (not redistributed): PERMITTED
- Contributing to open source: PERMITTED under CLA

PROHIBITED WITHOUT COMMERCIAL LICENSE:
- Redistributing as commercial product/service
- Offering as SaaS/API to third parties
- Incorporating into commercial product

TIERS:
- Startups (< €100K ARR): €49/month
- SMBs: €199/month
- Enterprises: Custom

CONTACT: commercial@yourdomain.com
```

## Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
    volumes:
      - /path/to/your/cli-tool:/tool:ro
      - ./data:/app/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/api.conf:/etc/nginx/conf.d/api.conf:ro
      - ./ssl:/etc/letsencrypt:ro
    depends_on:
      - api
```

## Deployment Checklist

| Step | Command/Action | Notes |
|------|---------------|-------|
| 1. Stripe Products | `./scripts/setup-stripe.sh` | Run locally |
| 2. Clone repo | `git clone` on server | |
| 3. Install deps | `pip install -r api/requirements.txt` | Use venv |
| 4. Configure .env | `cp .env.example .env` + fill keys | |
| 5. SSL cert | `certbot --nginx -d api.domain.com` | Needs DNS |
| 6. systemd | `sudo cp systemd/api.service /etc/systemd/system/` | |
| 7. Start | `sudo systemctl enable --now api` | |
| 8. Stripe webhook | `stripe listen --forward-to localhost:8000/webhook/stripe` | Local dev only |

## Key Files to Create

1. `api/main.py` — FastAPI with auth, routes, CLI runner
2. `api/requirements.txt` — fastapi, uvicorn, slowapi, stripe, pydantic
3. `nginx/api.conf` — TLS, rate zones, security headers
4. `docker/docker-compose.yml` — API + nginx
5. `systemd/api.service` — User=www-data, venv, restart=always
6. `scripts/setup-stripe.sh` — Creates products/prices via Stripe CLI
7. `scripts/deploy.sh` — Full server bootstrap
8. `LICENSE` — Commercial license text
9. `docs/api.md` — API reference

## Common Pitfalls

- **Subprocess timeout**: Set `asyncio.wait_for(proc.communicate(), timeout=60)` or CLI hangs kill your worker
- **SQLite locking**: Use WAL mode for concurrent reads
- **Stripe webhook idempotency**: Store `event_id` in DB and skip already-processed events
- **Rate limit reset**: Rate limit state is per-worker unless using Redis — acceptable for MVP
- **CLI path**: Use absolute paths in Docker/systemd (env vars), not relative

## See Also

- FastAPI: https://fastapi.tiangolo.com
- SlowAPI (rate limiting): https://github.com/laurentS/slowapi
- Stripe CLI: https://stripe.com/docs/stripe-cli
- Certbot: https://certbot.eff.org
