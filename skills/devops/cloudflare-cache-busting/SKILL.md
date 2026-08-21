---
name: cloudflare-cache-busting
description: How to bust Cloudflare cache after updating static site files — query params don't work, renaming files does.
---

# Cloudflare Cache Busting for Static Sites

## Problem
After updating files on a Cloudflare-proxied origin server, CF keeps serving old cached versions. The `cf-cache-status: HIT` header confirms CF is caching.

## What DOES NOT Work
- Adding `?v=timestamp` or `?v=2` query params to asset URLs
- Cloudflare ignores query strings for static asset caching by default
- Purging via Cloudflare dashboard UI requires API token (often not available)
- `curl -x PURGE` won't work without CF API credentials

## What DOES Work

### Option 1: Rename Files (BEST)
Rename the static asset file so CF sees it as a new resource:
```
styles.css → styles.v2.css
app.js → app.v2.js
```
Update HTML references accordingly. CF will cache the new URL as a fresh resource.

### Option 2: Cloudflare API Purge (requires API token)
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://domain.com/styles.css","https://domain.com/app.js"]}'
```

## Diagnostic Headers
```bash
curl -sI 'https://domain.com/asset.css' | grep -E 'cf-cache|content-length|etag|last-modified'
```
- `cf-cache-status: HIT` = cached, will serve old content
- `cf-cache-status: DYNAMIC` = not cached, always fresh from origin

## Prevention
For development: set Cache-Control headers on origin to `no-cache` or `max-age=0` during updates, or use option 1 rename strategy as standard deployment practice.
