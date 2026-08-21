---
name: production-podman-debug
title: Production Podman Debug
description: Systematic approach to debugging production podman deployments behind Cloudflare tunnels. Covers HTTP error classification (522/502/503/500), DNS verification, pod/container health inspection, cloudflared tunnel diagnostics, nginx config analysis, application logs, and end-to-end HTTP validation with correct Host headers.
triggers: user reports HTTP error on Cloudflare-proxied service; podman pod appears down; cloudflared tunnel connection issues; "check whats up with" related queries; bridge M08 500 in architect dashboard
---

# Production Podman Debug — methodology

Systematic approach for debugging mazemaker-prod (Hetzner) or similar podman + Cloudflare tunnel deployments.

## ⚠️ NON-NEGOTIABLE: Read the handbook FIRST

**Read HANDBOOK.md before ANY action.** The user has made this an explicit
expectation — failing to do so will cause frustration and corrections.

Path: `/home/alca/projects/mazemaker-v2-stack/backend/docs/HANDBOOK.md`

Covers: topology, hosts, DNS routing, secrets, deploy, ops playbook, troubleshooting, security model. This is the canonical reference.

**What this means concretely:**
- Do NOT ask the user "does Hetzner have a GPU?" or "where is the repo cloned?"
  — the handbook answers these in §2 (Hosts & Services) and §4 (Deploy-Prozeduren).
- Do NOT propose SCP/transfer workflows without checking if the handbook has
  a standard deploy flow.
- When the user says "lies das Handbuch!" or "LIES DAS HANDBUCH!", STOP
  proposing and READ the handbook immediately.
- After reading, if the handbook doesn't answer the question, THEN you can
  investigate. But the handbook is always the starting point.

**If the user references a specific tool/pattern** (e.g. "wie Claude-CODE es machte",
"per mosh", "build-all-locked.sh") and you haven't read the handbook, read it first
before responding — they're telling you the answer is in there.

## Step 1: Classify the error from outside

```
curl -sI "https://<hostname>"
curl -s -o /dev/null -w "HTTP %{http_code}\n" "https://<hostname>"
```

Common Cloudflare status codes:
- **522**: Origin connection timeout — tunnel not routing the hostname, origin not responding on expected port, or **typo in the hostname**

### Concrete example: `architecht vs architect`

During the 2026-05-29 outage, the user reported `architecht.mazemaker.dev`
returning 500/522. The tunnel ingress only had `architect.mazemaker.dev`
(correct spelling), so the typo'd hostname fell through to the catch-all and
Cloudflare returned 522 — making it look like the origin was down.

The fix was just using the correct URL. No infrastructure change needed.

**Lesson: when the user reports `SOMETHING.mazemaker.dev` returning 5xx,
first verify the spelling against the tunnel ingress config before checking
any infrastructure.**

See Step 6 for how to read the ingress config from the cloudflared container log.
- **502**: Bad gateway — origin returned something unparseable
- **503**: Service unavailable — overloaded or explicitly down
- **520**: Generic origin error — app crash at the proxy target
- **500**: Application error — check backend logs
- **530**: DNS resolution error inside the tunnel

### How wildcard DNS causes false positives

Cloudflare's zone proxy catches **all subdomains** at the edge (even nonexistent ones) when a wildcard DNS record exists (`*.mazemaker.dev`). This means:

- A **typo hostname** (e.g. `architecht` with extra 't') resolves to Cloudflare IPs
- But no tunnel ingress rule matches → cloudflared returns 404 → Cloudflare surfaces as **522**
- The result looks like the origin is down, but the issue is just the hostname spelling

**Procedure to distinguish typo from real outage:**
1. Check DNS record exists: `dig +short <hostname>`
2. If it resolves to `188.114.96.*` or `188.114.97.*` (Cloudflare proxied IPs), check the DNS type: `dig <hostname> CNAME +short`
3. If no CNAME to `.cfargotunnel.com`, it's either a typo or an unconfigured subdomain
4. Verify against the DNS record list in the handbook (§2.2) or via Cloudflare API

**After correct spelling is confirmed**, proceed to tunnel diagnostics.

First check: **Is the hostname spelt correctly?** A typo (architecht vs architect) produces 522 because no tunnel ingress rule matches — Cloudflare catches it at the edge but can't route anywhere.

## Step 2: Check DNS records via Cloudflare API

Zone ID for mazemaker.dev: `141dee23c0faba069a5af96672188859`
Token on mazemaker-prod: `cat /home/mazemaker/.cloudflare.api`

```bash
TOK=$(ssh mazemaker-prod "cat /home/mazemaker/.cloudflare.api" 2>/dev/null | tail -1)
curl -s -H "Authorization: Bearer *** "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=<hostname>"
```

A proxied CNAME to `*.cfargotunnel.com` = tunnel handles it. No record = hostname doesn't exist in DNS.

## Step 3: Connect to the prod machine

### Primary (stable connection): mosh

Mosh handles network flakiness (roaming, sleep/wake, IP changes) without
dropping the session. Use this as the default, not SSH.

```bash
mosh mazemaker-prod
```

Mosh must be installed on both ends (verified: both desk and Hetzner have it).
Mosh first establishes an SSH connection to authenticate, then switches to UDP.

### Fallback: SSH (stable network only)

Use SSH only when mosh is unavailable or you need to run a one-shot command
without an interactive session:

```bash
ssh mazemaker-prod
```

SSH config (in ~/.ssh/config):
```
Host mazemaker-prod
  HostName 89.167.114.125
  Port 47777
  User root
  IdentityFile ~/.ssh/mazemaker-prod
  IdentitiesOnly yes
```

### Running one-shot commands (no interactive session needed)
```bash
# Via SSH (simple, reliable for single commands)
ssh mazemaker-prod '<command>'

# Via mosh (for long-running commands on flaky connections)
mosh mazemaker-prod -- <command>
```

## Step 4: Check podman pods (as mazemaker user)

### Primary method (su -)

```bash
ssh mazemaker-prod "su - mazemaker -c 'podman pod ls'"
ssh mazemaker-prod "su - mazemaker -c 'podman ps -a --pod'"
```

All pods should show **Running**, all containers **Up**. Uptime comparison (hours vs days) can reveal recent crashes/restarts.

### Fallback: Overlay filesystem access (when su/sudo is blocked)

When `su - mazemaker -c` is unavailable (permission denied, DBUS session missing), read container state directly from the overlay filesystem:

```bash
# List all containers
ssh mazemaker-prod "cat /home/mazemaker/.local/share/containers/storage/overlay-containers/containers.json"
# Infra containers only (network/pod namespaces)

ssh mazemaker-prod "cat /home/mazemaker/.local/share/containers/storage/overlay-containers/volatile-containers.json"
# Application containers with image names, status, creation time
```

Each entry has: `id`, `names[]`, `image` (sha256), `image-name` (human-readable), `created` timestamp. Parse with `python3 -m json.tool` or `jq`.

```bash
# Quick enumeration of all containers with names
ssh mazemaker-prod 'python3 -c "
import json
with open(\"/home/mazemaker/.local/share/containers/storage/overlay-containers/volatile-containers.json\") as f:
    for c in json.load(f):
        print(c[\"names\"][0].ljust(40), c.get(\"metadata\",{}).get(\"image-name\",\"?\"))
"'
```

### Read container logs from overlay filesystem

When podman exec is unusable (root → user mismatch), read logs directly:

```bash
CONTAINER_ID=$(ssh mazemaker-prod 'python3 -c "
import json
with open(\"/home/mazemaker/.local/share/containers/storage/overlay-containers/volatile-containers.json\") as f:
    for c in json.load(f):
        if \"systemd-mazemaker-v2-cloudflared\" in c[\"names\"]:
            print(c[\"id\"])
            break
"')

ssh mazemaker-prod "cat /home/mazemaker/.local/share/containers/storage/overlay-containers/$CONTAINER_ID/userdata/ctr.log | tail -30"
```

The log path is: `<STORAGE>/overlay-containers/<ID>/userdata/ctr.log`

This works because all container logs are stored as shared files — no podman exec needed.

## Step 5: Check system health

```bash
ssh mazemaker-prod "df -h / | tail -1; free -h | head -2; uptime"
```

Warning thresholds: disk >80%, memory >90%, load >4.0 on a 4-core box.

**Hetzner root partition is 38 GB total** — fills easily with stale image
tarballs. A full disk (100%) causes nginx to fail writing access logs,
the API to crash on DB writes, and Cloudflare to surface 522/502/500
depending on the failing component.

Common space hog: stale GPU tarballs in `/tmp` (can accumulate 18+ GB).
Clean with:
```bash
ssh mazemaker-prod 'rm -fv /tmp/*.tar /tmp/*.tgz'
# Verify: should show ~19 GB free
ssh mazemaker-prod 'df -h /'
```

Check this FIRST when getting 5xx from any mazemaker.dev subdomain —
before checking nginx config, before podman logs. A full disk explains
every 5xx at once.

## Step 6: Check cloudflared tunnel health

The mazemaker-v2 tunnel uses **TUNNEL_TOKEN** (no local config.yml). Ingress rules are managed from Cloudflare Zero Trust dashboard.

### Primary: container logs via podman

```bash
ssh mazemaker-prod "su - mazemaker -c 'podman logs systemd-mazemaker-v2-cloudflared --tail 30'"
```

### Fallback: overlay log file (when su - is unavailable)

```bash
# Find the cloudflared container ID
CF_ID=$(ssh mazemaker-prod 'python3 -c "
import json
with open(\"/home/mazemaker/.local/share/containers/storage/overlay-containers/volatile-containers.json\") as f:
    for c in json.load(f):
        if \"cloudflared\" in c.get(\"names\",[])[0]:
            print(c[\"id\"])
            break
"')

ssh mazemaker-prod "cat /home/mazemaker/.local/share/containers/storage/overlay-containers/$CF_ID/userdata/ctr.log | tail -50"
```

### Read the ingress config from log output

The cloudflared container logs the **full ingress config** on startup as a JSON message:

```
INF Updated to new configuration config="{...}" version=N
```

Extract and format it:

```bash
ssh mazemaker-prod "cat /home/mazemaker/.local/share/containers/storage/overlay-containers/$CF_ID/userdata/ctr.log | grep 'Updated to new configuration' | python3 -c \"
import sys, json
for line in sys.stdin:
    if 'Updated to new configuration' in line:
        start = line.index('{')
        # Find the second opening brace (double-escaped inner JSON)
        end = line.rindex('}')
        data = json.loads(line[start:end+1])
        for rule in data.get('ingress', []):
            host = rule.get('hostname', '*')
            svc = rule.get('service', '?')
            print(f'  {host:35s} → {svc}')
\"'
```

This is more reliable than trying to `cat /etc/cloudflared/config.yml` inside the container — the cloudflared image is Alpine-stripped and has no `cat` binary.

Common patterns:
- QUIC stream timeouts every ~2 min on Hetzner = idle disconnect, auto-reconnects. Noise, not failure.
- "Connection terminated" + reconnect pair = expected on Hetzner.
- Persistent registration failure = tunnel token expired/revoked.

Inspect container:
```bash
ssh mazemaker-prod "su - mazemaker -c 'podman inspect systemd-mazemaker-v2-cloudflared'"
```

Look for CMD: `tunnel --no-autoupdate run`, TUNNEL_TOKEN env var.

## Step 7: Check nginx config

```bash
ssh mazemaker-prod "cat /home/mazemaker/mazemaker-v2-pod/nginx/mazemaker-v2.conf"
```

Verify:
- `server_name` matches the DNS hostname
- Root path exists with expected files
- `proxy_pass` targets correct internal port
- No default `return 444` block catching the request

## Step 8: Check application logs

```bash
ssh mazemaker-prod "su - mazemaker -c 'podman logs systemd-mazemaker-v2-api --tail 50'"
```

Grep for 5xx, tracebacks, ERROR/CRITICAL. Healthy API shows 200/201/204 only.

## Step 9: Verify nginx → app routing (inside pod)

IMPORTANT: Must use correct Host header to match the nginx server block, otherwise the default server returns 444 (empty reply).

```bash
# API health via nginx proxy
curl -s -H "Host: api.mazemaker.dev" http://127.0.0.1:8083/api/health

# Architect SPA via nginx
curl -s -H "Host: architect.mazemaker.dev" -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8083/
```

## Step 10: Verify from outside

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" "https://<hostname>"
curl -s "https://api.mazemaker.dev/api/health"
```

## Step 11: Debug customer-side components (bridge / M08 HERMES panel)

Architect M08 shows session/config data via the bridge running at 127.0.0.1:8769. The bridge is a Nuitka --onefile binary — does NOT run on Hetzner.

**Architecture:**
```text
Browser → architect.mazemaker.dev (Hetzner nginx, SPA + API proxy)
       ↳ 302 → /public/index.html  serves the SPA
       ↳ /api/* → proxy_pass to v2-api:8000
       ↳ static files from /home/mazemaker/mazemaker-v2-pod/architect/src/
```

Full end-to-end SPA verification (follows redirect chain):

```bash
# Step 1: DNS resolution
dig +short architect.mazemaker.dev

# Step 2: External curl follows redirect (302 → /public/index.html → 200)
curl -sL -o /dev/null -w "Final: HTTP %{http_code} | %{url_effective}\n" https://architect.mazemaker.dev/
# Expected: Final: HTTP 200 | https://architect.mazemaker.dev/public/index.html

# Step 3: Verify SPA content (first 5 lines)
curl -s https://architect.mazemaker.dev/public/index.html | head -5
# Should show: <!doctype html>, title: THE ARCHITECT

# Step 4: Verify script/css references relative to nginx root
curl -sI https://architect.mazemaker.dev/src/style.css
# Expected: 200 (versioned via ?v=<hash>)
```

### Container naming conventions (desk vs Hetzner v2)

| Component | Desk (quadlet pod) | Hetzner v2 (kubernetes/pod) |
|-----------|-------------------|---------------------------|
| Cloudflared | — (not needed) | `systemd-mazemaker-v2-cloudflared` |
| API | `systemd-mazemaker-mcp` (8000) | `systemd-mazemaker-v2-api` |
| Nginx | — | `systemd-mazemaker-v2-nginx` |
| Bridge | `mazemaker-hermes-bridge` (:8769) | — (not on Hetzner) |
| DB | `systemd-mazemaker-pgvector` (:8765) | — (Hetzner v2 uses a different db) |
| Dream worker | `systemd-mazemaker-dream-worker` | — (runs locally) |
| Wonderland | `systemd-mazemaker-wonderland` | — (runs locally) |
| License | `systemd-mazemaker-license-client` | — (runs locally) |
| Embedding | `systemd-mazemaker-embedding-worker` | — (runs locally) |

Hetzner v2 is a **separate deployment** running FastAPI + nginx behind the Cloudflare tunnel. The desk mazemaker pod runs the full neural-memory stack (MCP, wonderland, pgvector, dream worker, etc.) — those are NOT replicated on Hetzner. The bridge exists only on the desk (it talks to the local Hermes installation).

**Check if bridge is healthy:**
```bash
systemctl --user status mazemaker-hermes-bridge.service
curl -s http://127.0.0.1:8769/hermes/mcp | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok'))"
# Expected: True
```

**Common 500 on /hermes/mcp** (RESOLVED commit e4e0be4): Missing `pyyaml` in Nuitka builder's pip install. Fix: add `pyyaml` to `bin/build-host-binaries.sh`, rebuild via `bash bin/build-host-binaries.sh`, deploy the new binary. See `references/bridge-hermes-mcp-500-2026-05-29.md` for full RCA.

**Systemd unit:** `/home/alca/.config/systemd/user/mazemaker-hermes-bridge.service`
Listens on 127.0.0.1:8769. Installed only when `hermes` binary detected on host.

## Step 12: Verify Hermes memory provider (auto:turn saves)

The `memory.provider: mazemaker` config now has a matching plugin at `~/.hermes/plugins/mazemaker/`. It saves every turn as an auto:turn memory via the local wonderland pod.

**Check if it's working:**
```bash
ls ~/.hermes/plugins/mazemaker/__init__.py                         # plugin file exists
hermes config get memory.provider                                   # should be "mazemaker"
grep -c "auto:turn" ~/.hermes/hermes-agent/agent/log               # turns being saved?
# Or via mazemaker_browse(label_prefix='auto:turn') to see recent
```

**Architecture:**
```yaml
memory.provider: mazemaker  → load_memory_provider("mazemaker")
                              → finds ~/.hermes/plugins/mazemaker/
                              → MazemakerMemoryProvider activated
                              → sync_turn(user, asst) called after every turn
                              → POST to 127.0.0.1:8765/tools/call
                              → label: auto:turn:<session>:<hex_ts>
```

**If auto:turn memories are stale (>1 day):** Two possible causes:

**Cause A — Plugin missing:** `~/.hermes/plugins/mazemaker/__init__.py` doesn't exist.
Copy from backend repo `client/hermes-plugins/mazemaker-memory-provider/__init__.py`.
Restart Hermes session.

**Cause B — `sync_turn` silently failing:** The plugin file exists but the
`sync_turn` signature may lack `**kwargs`. The MemoryManager passes
`session_id=session_id` as a keyword argument — without `**kwargs` Python
raises TypeError, caught silently, never retried. Check:
```bash
grep -i "sync_turn.*failed\|unexpected keyword argument" ~/.hermes/logs/agent.log
```
If the only mazemaker log line is the "provider ready" message, this is
the cause. Fix: add `**kwargs` to the `sync_turn` signature in
`~/.hermes/plugins/mazemaker/__init__.py` and restart Hermes.

**Source:** backend repo `client/hermes-plugins/mazemaker-memory-provider/` (commit 9721d64). Shipped via install.sh to `~/.hermes/plugins/mazemaker/`. Bundled in source.tar.gz. Exempted from the .py publish gate.

## After completing all diagnostics

Save key findings to mazemaker memory. The user expects this. Use `mazemaker_remember` with a curated label like `bug:<tag>` or `ops:<phase>`.

## Multi-machine deploy pattern

When a fix needs deploying to multiple targets, the pipeline is:
```
desk (build + test) → tpad (scp + test) → repo (commit + push) → Hetzner (pull + install-backend.sh)
```

All machines currently running this stack: desk, tpad, mazemaker-prod (Hetzner).

## Pitfalls

- **Always read HANDBOOK.md first** — the user expects full awareness of the
  topology, deployment model, DNS routing, and ops playbook before any action.
  Path: `/home/alca/projects/mazemaker-v2-stack/backend/docs/HANDBOOK.md`
- **"Empty reply from server"** when curling nginx:PORT → you're hitting the default server. Add the correct Host header.
- **522 on nonexistent hostname** → check spelling. Cloudflare zone proxy catches all subdomains at the edge, returns 522 when no tunnel can route.
- **cloudflared QUIC timeouts on Hetzner** → idle disconnects, not tunnel failures. Auto-reconnects within seconds.
- **`curl http://127.0.0.1:8000` from host fails** → port 8000 is pod-internal. Route through published port 8083 with Host header, or exec into the container.
- **cloudflared images are minimal** (no cat, ls, env, ss inside). Use `podman exec` or `podman inspect` (which runs on the host, parsing the config) instead of interactive shell tools inside the container.
- **TUNNEL_TOKEN has no local ingress config** → ingress managed via Cloudflare Zero Trust dashboard or API, NOT via local config.yml.
- **`cloudflared tunnel info` requires cert.pem** → fails with TUNNEL_TOKEN. Use `podman logs` to check tunnel state instead.
- **`su - mazemaker -c '...'`** needed when running as root — mazemaker runs rootless podman. sudo won't inherit the user's DBUS session.
- **No DNS record + wildcard + Cloudflare proxy = 522** (not NXDOMAIN). Check spelling before debugging infrastructure.
- **The bridge is NOT on Hetzner** — bridge 500s are local-machine issues. Don't look at production logs.
- **Nuitka binaries silently lack system deps** — if the builder container's pip install line is missing a package like pyyaml, the compiled binary doesn't have it and there's no compile-time error. Always verify against a test endpoint.
- **Do NOT replace Nuitka binaries by hand** — always rebuild via `build-host-binaries.sh`. The binary is the sealed distribution artifact. Copying a Python script over the binary defeats the purpose.
- **Nuitka-compiled binaries change .py paths to .so** — after lockdown/Nuitka compilation, Python files become `.cpython-3XX-*.so` files. The directory structure may also flatten (e.g. `/app/core/dream_worker.py` → `/app/dream_worker.cpython-311-x86_64-linux-gnu.so`). Always check: `podman run --rm <image> find /app -name "dream*" -o -name "<pattern>*"`. Then import via `python3 -c "import sys; sys.path.insert(0, '/app'); import <module>; <module>.main()"` instead of `python -u /path/to/old.py`.
- **Nuitka preserves argparse CLI** — the compiled .so still has the original `sys.argv` argument parsing. Set `sys.argv` before calling `module.main()`. Do NOT pass flags as command-line arguments to `python3 -c`.
- **GPU device lines in Quadlets cause errors on non-GPU machines** — if a machine has no NVIDIA GPU, `AddDevice=nvidia.com/gpu=all` in a Quadlet prevents the container from starting. Strip it: `sed -i '/AddDevice=nvidia/d' ~/.config/containers/systemd/<container>.container`. The install.sh normally handles this, but pre-existing Quadlets may need manual fix.
- **Dream worker Nuitka path crash** — see `references/dream-worker-nuitka-path-2026-05-29.md` for full RCA.
- **Disk full on Hetzner causes 5xx** — Hetzner root partition is only 38 GB.
  Stale GPU tarballs from failed push attempts fill /tmp to 18 GB+. Check
  `ssh mazemaker-prod 'df -h /'` before assuming an app-level error. Clean
  stale tarballs with `ssh mazemaker-prod 'rm -fv /tmp/*.tar /tmp/*.tgz'`.
  After cleanup the VM typically has 19 GB free — enough for normal operation.
- **`sudo -u mazemaker -H` causes \"cannot chdir to /root\"** — `-H` sets
  HOME but doesn't change the CWD. When root's CWD is /root and the
  mazemaker user can't read it, `-H` fails. Use instead:
  `sudo -u mazemaker -s /bin/bash -c "cd /home/mazemaker && <cmd>"`.
  `su - mazemaker -c '<cmd>'` also works (it starts a login shell in the
  target user's home directory).
- **Save findings to mazemaker memory** after completing diagnostics. The user expects `mazemaker_remember` with curated labels (`bug:`, `ops:`, `decision:`).
- **Hermes memory provider only activates on new sessions** — a session started
  before the plugin was installed won't pick it up mid-session. Must start a
  new Hermes session.

## Verification

- All pods Running (mazemaker-v2, mazemaker-registry, remainder)
- All containers "Up" with restart count ≤ 1
- External curl returns expected code (200/302/401)
- API health returns `{"status":"ok"}`
- No 5xx in last 200 lines of API logs
