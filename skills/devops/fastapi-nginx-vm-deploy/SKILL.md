---
name: fastapi-nginx-vm-deploy
category: devops
description: Deploy FastAPI + nginx onto a running jack-in-a-box VM via SSH — non-Docker, systemd-backed, with SSL
version: 1.0.0
tags: [fastapi, nginx, vm, systemd, ssl, deploy, jack-in-a-box]
---

# FastAPI + nginx VM Deploy (Non-Docker)

Deploy a FastAPI app behind nginx on a running jack-in-a-box VM via SSH. No Docker. systemd for persistence.

## When to Use

- VM has no Docker installed
- jack-in-a-box is already running on the VM (has PULSE, etc.)
- Want direct Python + nginx deployment (faster, simpler than Docker)

## SSH Connection

```bash
ssh -p 2222 -i ~/.ssh/jiab_test testuser@localhost
```

Or add to `~/.ssh/config`:
```
Host vm
    HostName localhost
    Port 2222
    IdentityFile ~/.ssh/jiab_test
    User testuser
```

## Step-by-Step

### 1. Install nginx + certbot (one-time)

```bash
sudo apt-get update && sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx && sudo systemctl start nginx
```

### 2. Create Python venv

Debian 12 is externally-managed — can't pip install system-wide:

```bash
python3 -m venv /home/testuser/venv
/home/testuser/venv/bin/pip install --upgrade pip
/home/testuser/venv/bin/pip install fastapi==0.109.2 uvicorn[standard]==0.27.1 slowapi==0.1.9 stripe==7.12.0 pydantic==2.6.1 pydantic-settings==2.1.0 python-dotenv==1.0.1 httpx==0.26.0
```

### 3. Copy API Code

```bash
# From local machine to VM
cat ~/projects/pulse-cloud/api/main.py | ssh -p 2222 -i ~/.ssh/jiab_test testuser@localhost "cat > /home/testuser/remainder-api/main.py"
```

Or with scp:
```bash
scp -P 2222 -i ~/.ssh/jiab_test ~/projects/pulse-cloud/api/main.py testuser@localhost:/home/testuser/remainder-api/
```

### 4. nginx Config

```bash
sudo tee /etc/nginx/sites-available/YOUR_DOMAIN > /dev/null << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN;

    client_max_body_size 1M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/YOUR_DOMAIN /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # REMOVE DEFAULT SITE — it blocks!
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Environment + Data Dirs

```bash
mkdir -p /home/testuser/remainder-api/data

cat > /home/testuser/remainder-api/.env << 'EOF'
STRIPE_WEBHOOK_SECRET=whsec_dev
STRIPE_SECRET_KEY=sk_test_dev
STRIPE_PUBLISHABLE_KEY=pk_test_dev
STRIPE_PRICE_FREE=price_free
STRIPE_PRICE_PRO=price_pro
STRIPE_PRICE_BUSINESS=price_business
PU_API_KEYS=pu_test_abc123:free
PU_JWT_SECRET=dev-secret-change-in-prod
PU_ADMIN_KEY=admin-dev
PU_PULSE_SCRIPT=/home/testuser/jack-in-a-box/pulse/scripts/pulse.py
PU_HOST=0.0.0.0
PU_PORT=8000
EOF
```

### 6. systemd Service

```bash
sudo tee /etc/systemd/system/remainder-api.service > /dev/null << 'EOF'
[Unit]
Description=Remainder API (FastAPI + PULSE)
After=network.target

[Service]
Type=simple
User=testuser
WorkingDirectory=/home/testuser/remainder-api
ExecStart=/home/testuser/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=/home/testuser/remainder-api/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable remainder-api
sudo systemctl start remainder-api
```

### 7. SSL — Only if ports 80/443 are open

**Check if ports are reachable from outside:**
```bash
# From OUTSIDE the network (not from the VM):
nc -zv -w 3 YOUR_PUBLIC_IP 80
nc -zv -w 3 YOUR_PUBLIC_IP 443
```

**If ports are BLOCKED (ISP firewall / NAT):** → Use Cloudflare Tunnel (below).

**If ports are OPEN:** → Use certbot:
```bash
# Get public IP
curl -s ifconfig.me

# Run certbot (domain must already point to this IP)
sudo certbot --nginx -d YOUR_DOMAIN
```

### 8. Cloudflare Tunnel (when ISP blocks 80/443)

When the ISP or router blocks inbound 80/443, Cloudflare Tunnel provides an outbound-only connection that works through NAT.

**Prerequisites:**
- Cloudflare account with remainder.online added
- Cloudflare Dashboard: Zero Trust → Networks → Tunnels → Create tunnel

**On the VM — install cloudflared:**
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Create tunnel via dashboard, get the token, then:
cloudflared service install YOUR_TUNNEL_TOKEN
```

**Alternative — quick test without service:**
```bash
# Tunnel to cloudflared daemon (for testing)
cloudflared tunnel --url http://localhost:8000
# Shows a cloudflared.net URL — temporary, for testing only
```

**Then route the tunnel domain in Cloudflare Dashboard:**
- Tunnel UUID routes `remainder.online` → `localhost:8000`
- Or use `cloudflared config route` with ingress rules

**Verify:**
```bash
curl -H 'Host: remainder.online' http://localhost:8000/health
```

## Troubleshooting

### "404 Not Found" from nginx
```bash
# Check which sites are enabled
ls /etc/nginx/sites-enabled/
# Remove default if it exists (blocks everything)
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### API Key auth fails with "Invalid or missing API key"
FastAPI converts `api_key` parameter to `api-key` header. Use:
```bash
curl -H 'api-key: pu_test_abc123' 'http://localhost/search?q=test'
# NOT: curl -H 'X-API-Key: pu_test_abc123'
```

### PULSE script path on jack-in-a-box VM
```
/home/testuser/jack-in-a-box/pulse/scripts/pulse.py
```

### Check service status
```bash
sudo systemctl status remainder-api
journalctl -u remainder-api -f
```

### Get public IP of VM
```bash
curl -s ifconfig.me
```

### VM is behind NAT (common with ISPs)

If `curl -s ifconfig.me` returns a public IP but external access fails:
- VM private IP (e.g., `10.0.2.15`) is behind NAT
- Public IP is the router, not the VM itself
- Router must forward 80/443 to the VM — OR use Cloudflare Tunnel

**Symptoms:**
- `nc -zv YOUR_PUBLIC_IP 80` times out
- `curl http://YOUR_PUBLIC_IP` works from inside VM but not outside
- nginx + API run fine locally

**Solution:** Use Cloudflare Tunnel (Section 8 above). No router config needed.
```bash
curl -s ifconfig.me
```

## Key VM Details (Current Setup)

- IP: 91.55.216.166
- SSH: `ssh -p 2222 -i ~/.ssh/jiab_test testuser@localhost`
- SCP uses uppercase port flag: `scp -P 2222 -i ~/.ssh/jiab_test ...` (`-p` is preserve mode and will fail/misread `2222` as a file)
- PULSE: `/home/testuser/jack-in-a-box/pulse/`
- API code: `/home/testuser/remainder-api/`
- Website: `/home/testuser/remainder-website/`
- venv: `/home/testuser/venv/`
- Service: `remainder-api.service`
- Current REMAINDER API port: `18000` (not 8000). Cloudflare Tunnel routes to nginx on `localhost:80`; nginx proxies `/v1/`, `/search`, `/sources`, `/health`, `/keys`, `/docs`, `/admin`, `/webhook` to `127.0.0.1:18000`.
- Deploy script path: `~/projects/pulse-saas/scripts/deploy-vm.sh`. It uses tar+scp because rsync was missing on the VM and waits for `/health`, not just `systemctl is-active` (uvicorn may be active before socket is accepting).
- Static website deploy must be immutable: clear `/home/testuser/remainder-website` before extracting the new tarball. Tar overlay alone leaves deleted assets publicly reachable (e.g. old `styles.v3.css` at root even after moving v3 to `/old/version3/`). Preserve API `.env`/DB by only clearing the website directory, not `/home/testuser/remainder-api`.
