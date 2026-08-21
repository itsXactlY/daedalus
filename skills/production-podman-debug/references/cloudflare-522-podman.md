# Cloudflare 522 — session diagnosis 2026-05-29

## The report

User said "architecht.mazemaker.dev reports 500". Investigation found:

1. **Spelling mismatch**: `architecht` (with extra 't') has no DNS record.
2. **Correct hostname** `architect.mazemaker.dev` has a CNAME → `903d316a-91ae-4b11-b02c-23edc84648fd.cfargotunnel.com` (proxied).
3. External curl to the typo returned **522** (not 500 — Cloudflare origin timeout), not 500.
4. External curl to the correct hostname returned **302** → SPA served correctly.

## Wildcard DNS mechanism

`*.mazemaker.dev` has a wildcard A record pointing to Cloudflare proxied IPs (188.114.96.3, 188.114.97.3). This means:

- **Any** subdomain resolves to Cloudflare (even typos like architecht, foo12345, randomgarbage)
- Cloudflare edge catches the request and tries to route it through the tunnel
- If no tunnel ingress rule matches the hostname → cloudflared returns 404 → Cloudflare shows **522**

Without the wildcard, a typo subdomain would return DNS NXDOMAIN. The wildcard makes typos LOOK like real hostnames with connectivity issues.

## Diagnosis procedure

```bash
# 1. Does the hostname resolve?
dig +short architecht.mazemaker.dev
# → 188.114.96.3 (Cloudflare edge — hostname exists in wildcard, but likely no record)

# 2. Check for the actual DNS record (CNAME to tunnel)
dig CNAME +short architect.mazemaker.dev
# → 903d316a-91ae-4b11-b02c-23edc84648fd.cfargotunnel.com (actual record)

# 3. Verify via Cloudflare API
TOK=$(ssh mazemaker-prod "cat /home/mazemaker/.cloudflare.api" 2>/dev/null | tail -1)
ZONE="141dee23c0faba069a5af96672188859"

# architect (correct) → has record
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=architect.mazemaker.dev"
# -> Result: CNAME to cfargotunnel.com, proxied=true

# architecht (typo) → no record
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=architecht.mazemaker.dev"
# -> Result: empty array
```

## Key diagnostics (session)

### DNS verification

ZONE ID: `141dee23c0faba069a5af96672188859`
CF token at: `/home/mazemaker/.cloudflare.api` (two lines: cfut_ user token, cfat_ API token)

Note: The cfut_ token has USER token scope (zones:read, tokens:verify) but NOT DNS:read scope — use the cfat_ token for DNS operations, or use the Global API Key from the handbook:

```
X-Auth-Email: alca@angels-electric.com
X-Auth-Key: c6e7ed1cab2000878075debf9485655e35ad8
```

(Note: The Global API Key in the handbook may be redacted — verify before relying on it.)

### DNS records for mazemaker.dev (key ones)

| Type | Name | Target | Proxied |
|------|------|--------|---------|
| CNAME | architect.mazemaker.dev | 903d316a-...cfargotunnel.com | yes |
| CNAME | api.mazemaker.dev | (tunnel UUID).cfargotunnel.com | yes |
| CNAME | mazemaker.dev | mazemaker-dev.pages.dev | yes |
| A | *.mazemaker.dev | 188.114.96.3 + 188.114.97.3 | yes (wildcard) |

### Cloudflared QUIC timeouts

The mazemaker-v2 tunnel cycles through QUIC stream timeouts approximately every 2 minutes:

```
ERR failed to accept incoming stream requests
error="failed to accept QUIC stream: timeout: no recent network activity"
WRN failed to serve tunnel connection
INF Retrying connection in up to 1s
INF Registered tunnel connection (location=fra03 protocol=quic)
```

This is a Hetzner network characteristic — idle QUIC connections get dropped by intermediate infrastructure. The tunnel auto-reconnects within seconds and service is unaffected. It's log noise, not a failure.

Resolution options (if desired):
- Add `keepAliveConnections: 100` and `keepAliveTimeout: 90s` to the tunnel ingress config (already set on the registry tunnel, which does NOT exhibit this issue)

### Cloudflared config model

- **mazemaker-v2 tunnel**: Uses `TUNNEL_TOKEN` (token-based auth). No local config.yml. Ingress rules managed via Cloudflare Zero Trust dashboard.
- **mazemaker-registry tunnel**: Uses credentials.json + config.yml in `/home/mazemaker/mazemaker-registry-pod/cloudflared/`. Has explicit ingress rules for `registry.mazemaker.dev` with timeout bumps.

### Container commands that worked

```bash
# Pod status
su - mazemaker -c 'podman pod ls'
su - mazemaker -c 'podman ps -a --pod'

# Container logs
su - mazemaker -c 'podman logs systemd-mazemaker-v2-cloudflared --tail 30'
su - mazemaker -c 'podman logs systemd-mazemaker-v2-api --tail 50'

# Container inspect (for CMD, env, mounts)
su - mazemaker -c 'podman inspect systemd-mazemaker-v2-cloudflared'

# DNS resolution check
dig +short architect.mazemaker.dev
```

### Commands that do NOT work in cloudflared containers

The cloudflared image is Alpine-based and stripped:
- `cat`, `ls`, `env`, `ss` — not found inside the container
- `cloudflared tunnel info` — requires cert.pem, not present with TUNNEL_TOKEN
- Reading config via `podman exec systemd-mazemaker-v2-cloudflared cat /etc/cloudflared/config.yml` — fails because cat doesn't exist

### Working around cloudflared's minimal image

```bash
# Read a file from cloudflared: use podman cp
podman cp systemd-mazemaker-v2-cloudflared:/etc/cloudflared/config.yml /tmp/cf-config.yml

# Or check the config outside the container — it's at ~/mazemaker-registry-pod/cloudflared/config.yml
# (only for registry tunnel; mazemaker-v2 uses TUNNEL_TOKEN, no local config)
```

## Why this wasn't a pod issue

The pods were all running (mazemaker-v2 9d, remainder 3w, registry 45h). All 11 containers "Up". No 500 errors in API logs. Server resources fine (28% disk, 980Mi/3.5Gi RAM, load 0.12). The 522 was a routing issue caused by a typo hostname, not a pod failure.
