---
name: pulse-cloud-api-integration
description: PULSE v4 API integration for pulse-cloud — output format, parsing, result counting, and deployment quirks.
tags: [pulse, fastapi, api, search, social-search]
---

# PULSE Cloud API Integration

## PULSE v4 Output Format

PULSE v4 outputs structured JSON with these top-level keys:
- `clusters` — array of result clusters
- `ranked_candidates` — flat array of ranked result IDs
- `items_by_source` — dict of source → array of items
- `errors_by_source` — dict of source → error messages
- `generated_at` — ISO timestamp
- `query_plan` — routing info
- `topic`, `warnings`, `range_from`, `range_to`

**Important:** v4 does NOT use `items` as top-level key (v3 did).

## API Parsing (main.py)

```python
async def run_pulse(q: str, depth: str = "default", sources: str = None) -> dict:
    # PULSE v4 outputs clusters + ranked_candidates + items_by_source
    try:
        data = _json.loads(output.strip())
        if isinstance(data, dict):
            if "clusters" in data or "ranked_candidates" in data or "items_by_source" in data:
                return data
    except:
        pass
    # fallback: multiple JSON lines
    ...
```

## Result Counting

Old code: `result_count = result.get("result_count", 0)` — WRONG for v4

Correct: `result_count = len(result.get("ranked_candidates", []))`

## CLI Invocation

```bash
python3 /path/to/pulse/scripts/pulse.py "AI news" \
  --emit=json --no-progress --no-store \
  --depth=quick  # or deep, default
```

PULSE path on VM: `/home/testuser/jack-in-a-box/pulse/scripts/pulse.py`

## Environment Variables (main.py)

```bash
PU_API_KEYS=pu_test_abc123:free,pu_xxx:pro
PU_JWT_SECRET=production-secret
PU_ADMIN_KEY=admin-secret
PU_PULSE_SCRIPT=/home/testuser/jack-in-a-box/pulse/scripts/pulse.py
PU_HOST=0.0.0.0
PU_PORT=18000
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxx
STRIPE_PRICE_PRO=price_xxx
STRIPE_PRICE_BUSINESS=price_xxx
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Health check |
| GET | /sources | API key | List sources |
| GET | /search | API key | Run search |
| POST | /webhook/stripe | Stripe sig | Stripe events |
| GET | /admin/stats | admin-key header | Usage stats |
| GET | /admin/keys | admin-key header | List keys |
| GET | /docs | None | Swagger UI |

## Auth Headers

- API key: `api-key: pu_test_abc123` (FastAPI converts `api_key` to `api-key`)
- Admin key: `admin-key: admin-dev`

## Rate Limiting

Free: 10/min via slowapi (keyed by CF-Connecting-IP behind Cloudflare)
Monthly DB limit: 100 requests (tracked in sqlite)

## Deployment Path

VM: `/home/testuser/remainder-api/main.py`
Venv: `/home/testuser/venv/` (python3 -m venv)
Systemd: `/etc/systemd/system/remainder-api.service`
Port: `18000`
Domain path: Cloudflare Tunnel → nginx on `localhost:80` → FastAPI on `127.0.0.1:18000`

## Production State (2026-04-24)

Repo: `~/projects/pulse-saas` (remote: `git@github.com:itsXactlY/pulse-saas.git`).

Backend is modular now:
- `api/main.py` — ASGI entrypoint only
- `api/remainder_api/app.py` — FastAPI app factory and routes
- `api/remainder_api/db.py` — SQLite WAL schema, migrations, usage, cache
- `api/remainder_api/pulse.py` — PULSE subprocess runner + robust v4 parser
- `api/remainder_api/auth.py` — api-key/Bearer/query auth, fingerprints, BYOK headers
- `api/remainder_api/config.py` — settings, source registry, tier limits

Current endpoints:
- `/v1/search` and legacy `/search`
- `/v1/sources` and legacy `/sources`
- `/v1/keys/free`, `/v1/keys/me`
- `/v1/billing/checkout`
- `/v1/webhooks/stripe`, `/webhook/stripe`, `/webhook`
- `/admin/stats`, `/admin/keys`

Auth accepts `api-key`, `X-API-Key`, `Authorization: Bearer`, or `?key=`. Public demo key `demo` is seeded automatically if `PU_ENABLE_DEMO_KEY=true`.

Important migration pitfall: legacy `pulse_cloud.db` may have `search_log` without `fingerprint`; run schema migrations BEFORE creating indexes. Regression test: `tests/test_db_migration.py`.

Verification commands:
```bash
cd ~/projects/pulse-saas
~/.hermes/hermes-agent/venv/bin/python -m pytest tests -q
bash scripts/smoke-local.sh
bash scripts/deploy-vm.sh
curl -fsS https://remainder.online/health
curl -fsS 'https://remainder.online/v1/search?q=rust+vs+go+performance&depth=quick&key=demo'
```

## Local Development Server (not VM)

When the user asks to start REMAINDER/PULSE SaaS locally, run the API on `127.0.0.1:18000` and serve the static website through a tiny local proxy on `127.0.0.1:18080`. Do not point the browser at the static files directly because `app.v3.js` uses `window.location.origin`; without a proxy, `/v1/*` will not reach FastAPI.

Prereq checks:
```bash
python3 - <<'PY'
import socket
for port in (18000, 18080):
    s=socket.socket(); s.settimeout(0.2)
    try:
        s.connect(('127.0.0.1', port)); print(f'{port}: busy')
    except Exception:
        print(f'{port}: free')
    finally:
        s.close()
PY
```

Start API in background from `~/projects/pulse-saas/api`:
```bash
PU_DB_PATH=/tmp/remainder-local.sqlite3 \
PU_API_KEYS=demo:free \
PU_PUBLIC_DEMO_KEY=demo \
PU_ENABLE_DEMO_KEY=true \
PU_ADMIN_KEY=admin-local \
PU_PULSE_SCRIPT=~/projects/pulse/scripts/pulse.py \
PU_PULSE_PYTHON=python3 \
PU_PULSE_TIMEOUT_SECONDS=120 \
PU_CACHE_TTL_SECONDS=900 \
PU_CORS_ORIGINS='*' \
~/.hermes/hermes-agent/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 18000
```

Serve/proxy the website on `18080`. Create a small Python `ThreadingHTTPServer` that serves `~/projects/pulse-saas/website` and proxies API prefixes (`/v1/`, `/search`, `/sources`, `/health`, `/keys`, `/docs`, `/openapi.json`, `/webhook`, `/admin`) to `http://127.0.0.1:18000$request_uri`. In Hermes, start it as a background process so the user can open:

```text
http://127.0.0.1:18080
```

Local verification:
```bash
curl -fsS http://127.0.0.1:18000/health
curl -fsS http://127.0.0.1:18080/health
curl -fsS 'http://127.0.0.1:18080/v1/sources?key=demo'
curl -fsS --max-time 120 'http://127.0.0.1:18080/v1/search?q=rust+vs+go+performance&depth=quick&key=demo'
```

Notes:
- Hermes venv may not have `stripe`; API import path is safe because `stripe` is imported lazily only when billing endpoints/webhooks need it.
- Local DB: `/tmp/remainder-local.sqlite3`.
- Stop via Hermes `process kill <session_id>` for the API and proxy background processes.
