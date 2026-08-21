---
name: api-admin-key-shortcut
description: Allow PU_ADMIN_KEY to authenticate for search/end-user API endpoints (not just admin routes) with unlimited tier
tags: [fastapi, auth, api-design, saas]
last_updated: 2026-04-24
---

# API Admin Key Shortcut Pattern

## Context
When building a SaaS API with FastAPI, you often have an `PU_ADMIN_KEY` env var for admin-only routes (stats, key management). But developers expect to also use it for search/end-user endpoints during development/testing.

## The Problem
`authenticate()` only checks the database for API keys. The `PU_ADMIN_KEY` from config only gates `/admin/*` routes. This means `api-key: admin-dev` returns 401 "Invalid or missing API key" on search endpoints.

## The Fix

### 1. Allow PU_ADMIN_KEY in authenticate()

In `remainder_api/app.py`, inside `authenticate()`:

```python
def authenticate(request: Request, query_key: str | None = None) -> dict[str, Any]:
    effective_key = extract_api_key(request, query_key)
    if not effective_key:
        raise HTTPException(401, "Invalid or missing API key")
    # Allow PU_ADMIN_KEY as a shortcut for admin-tier search access
    if effective_key == settings.pu_admin_key:
        return {
            "key": settings.pu_admin_key,
            "tier": "admin",
            "status": "active",
            "requests_used": 0,
            "requests_limit": -1,
            "label": "admin",
        }
    with db_session(settings) as conn:
        row = get_api_key(conn, effective_key)
        ...
```

### 2. Add admin tier limits

In `config.py`:

```python
TIER_LIMITS: dict[str, dict[str, int | str]] = {
    "free": {"daily": 5, "monthly": 150, "rate": "5/day", "cache_ttl": 3600},
    "pro": {"daily": 500, "monthly": 5000, "rate": "100/min", "cache_ttl": 900},
    "business": {"daily": 5000, "monthly": 50000, "rate": "1000/min", "cache_ttl": 300},
    "admin": {"daily": 999999, "monthly": 9999999, "rate": "unlimited", "cache_ttl": 60},
}
```

### 3. Skip rate limit checks for admin tier

In `assert_usage_allowed()`:

```python
def assert_usage_allowed(conn, *, key_row: dict[str, Any], fingerprint: str):
    tier = key_row.get("tier", "free")
    # Admin tier has no rate limits
    if tier == "admin":
        return key_row, 0
    ...
```

### 4. Use api-key header (not Bearer) for admin key

`Authorization: Bearer admin-dev` does NOT work with this pattern — it only works with `api-key: admin-dev` (or `?key=admin-dev`). The Bearer token flow uses the regular API key extractor which only checks DB.

If you want Bearer to also work, update `extract_api_key()` to check for the admin key prefix:

```python
def extract_api_key(request: Request, query_key: str | None = None) -> str | None:
    for header in ("api-key", "x-api-key"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    ...
```

## Verification

```bash
# Admin key works for search
curl -H "api-key: admin-dev" "https://api.example.com/v1/search?q=test"

# Should return tier: admin, no 429s
```

## Pitfalls
- `requests_limit: -1` in the admin row would cause `if used >= -1` to always be true → use early return for tier=="admin" instead
- Don't put the admin key in `PU_API_KEYS` env var (it's separate from the DB key list)
- JWT secret is NOT the same as admin API key — JWT is for session tokens, `PU_ADMIN_KEY` is for direct API access
