---
name: cloudflare-tunnel-vm-deploy
description: Deploy a service behind NAT to the internet using Cloudflare Tunnel — no port forwarding needed
---

# Cloudflare Tunnel VM Deployment

## Context
VM sits behind NAT (private IP 10.0.2.15, public IP 91.55.216.166). ISP blocks inbound 80/443. Cloudflare Tunnel creates an outbound connection from VM to Cloudflare, no port forwarding needed.

## Prerequisites
- Cloudflare Zero Trust account
- Domain added to Cloudflare (NS pointing to Cloudflare nameservers)
- SSH access to VM

## Setup Steps

### 1. Install cloudflared on VM
```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install cloudflared
```

### 2. Create tunnel in Cloudflare Dashboard
```
Zero Trust → Networks → Tunnels → Create tunnel → Cloudflared
```
Name it (e.g. `remainder.online`), save. Cloudflare shows a **Tunnel Token** (long hex string, NOT the Access API token).

**IMPORTANT:** The Tunnel Token is different from Cloudflare Access/Zero Trust API tokens. It's a dedicated tunnel credential starting with `eyJh...` or similar base64.

### 3. Get the Tunnel Token
After creating the tunnel, click on it → Configuration or Connector tab → look for "Show token" or a command like:
```bash
cloudflared service install <TUNNEL_TOKEN>
```
Copy the token (64+ char hex/base64 string).

### 4. Connect VM to tunnel
```bash
cloudflared service install "<TUNNEL_TOKEN>"
```
If the token has encoding issues over SSH, try:
```bash
TOKEN='<token>'
cloudflared service install "$TOKEN"
```

### 5. Route domain to tunnel
In Cloudflare Dashboard → DNS → delete any existing A/AAAA records for the domain → then in the tunnel config, set the Public Hostname:
- Subdomain: `remainder.online` (or `@` for bare domain)
- Service: `HTTPS` → `http://localhost:18000`

### 6. Verify
```bash
curl -s -H 'Host: remainder.online' http://localhost:18000/health
```

## Common Issues

### "invalid character 'ß'" error
- Usually means wrong token type. The Tunnel Token is NOT the Cloudflare API token from Access/Zero Trust
- Or encoding issue with SSH — try with single-quoted variable

### "Provided Tunnel token is not valid"
- Wrong token format. Tunnel tokens are typically base64-like strings from Cloudflare dashboard
- Try: `cloudflared tunnel run --token "<TOKEN>"` (foreground test first)

### DNS "A/CNAME record already exists"
- Go to Cloudflare DNS settings and delete existing records for the domain first, then create the tunnel routing

### Port 80/443 blocked by ISP
- This is expected and why you use Cloudflare Tunnel (outbound connection only)
- No port forwarding needed

### Error 1033 "Cloudflare Tunnel error — unable to resolve"
- Tunnel is connected but NO ROUTE configured
- Cause: You have DNS records but missing the Public Hostname route in tunnel config
- Fix: Zero Trust → Networks → Tunnels → your tunnel → Public hostname → Add hostname: remainder.online, Type: HTTP, URL: localhost:18000

### Error 403 "Access denied" / "Cloudflare Access"
- Cause: Creating a tunnel via dashboard AUTO-CREATES an Access App that blocks traffic
- Fix: Zero Trust → Access → Applications → DELETE all entries for your domain

### DNS CNAME alone is NOT sufficient
- You need TWO things:
  1. DNS CNAME: `@` → `<tunnel_id>.cfargotunnel.com` (Proxy ON)
  2. Tunnel Public Hostname route: remainder.online → http://localhost:18000
- Without #2, Error 1033 occurs even if DNS resolves

## Complete Clean Setup Workflow
1. Zero Trust → Networks → Tunnels → Create tunnel → Cloudflared
2. Copy tunnel token (starts `eyJhIjoiYz...`)
3. cloudflared service install on VM
4. Configure ingress in /etc/cloudflared/config.yml
5. **DELETE any Access App** for your domain (Zero Trust → Access → Applications)
6. Add Public Hostname route in tunnel config (not just DNS)
7. Add DNS CNAME if not auto-created

### /etc/cloudflared/config.yml example
```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: remainder.online
    service: http://localhost:18000
  - hostname: "*.remainder.online"
    service: http://localhost:18000
  - service: http_status:404
```

## Rate Limiting Behind Cloudflare Tunnel
When behind Cloudflare Tunnel, all requests appear to come from Cloudflare IPs. Use `CF-Connecting-IP` header for real client IP:

```python
from fastapi import Request
from slowapi.util import get_remote_address

def get_real_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    xff = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if xff:
        return xff
    return get_remote_address(request)
```

## DNS CNAME Alone Is NOT Sufficient
Error 1033 "Cloudflare Tunnel error — unable to resolve" = tunnel connected but NO ROUTE.

You need TWO things:
1. **DNS CNAME**: `@` → `<tunnel_id>.cfargotunnel.com` (Proxy ON) — tells Cloudflare where to route
2. **Public Hostname route**: remainder.online → http://localhost:18000 — tells the tunnel where to deliver

Without #2: DNS resolves but tunnel doesn't know to deliver traffic to your service.

## Cloudflare Access vs Tunnel — CRITICAL
These are SEPARATE products with SEPARATE credentials:
- **Cloudflare Access** (uses API tokens like `cfut_...`) = OAuth/SSO layer that BLOCKS traffic
- **Cloudflare Tunnel** (uses tunnel tokens like `eyJhIjoi...`) = proxy that FORWARDS traffic

When you create a tunnel via Zero Trust dashboard, it often AUTO-CREATES an Access App. This Access App INTERCEPTS traffic before the tunnel can route it, causing 403 errors.

**Fix**: Zero Trust → Access → Applications → DELETE all entries for your domain.

## Complete Clean Setup Workflow
1. Zero Trust → Networks → Tunnels → Create tunnel → Cloudflared
2. Copy tunnel token (starts `eyJhIjoiYz...`)
3. cloudflared service install on VM
4. Configure ingress in /etc/cloudflared/config.yml
5. **DELETE any Access App** for your domain (Zero Trust → Access → Applications)
6. Add Public Hostname route in tunnel config (not just DNS)
7. Add DNS CNAME if not auto-created

## Key Distinction
**Cloudflare Access** = Authentication/OAuth layer for apps (uses API tokens)  
**Cloudflare Tunnel** = Reverse proxy that connects your server to Cloudflare (uses tunnel tokens)

These are separate products with separate credential types.
