---
name: qemu-vm-testing
description: How to test installers in a QEMU VM with cloud-init, SSH, and snapshot/restore
category: devops
version: 1.0
tags: [qemu, vm, testing, cloud-init, snapshot, installer, kvm]
---

# QEMU VM Testing for Installers

Test installers in a lightweight Debian 12 VM with snapshot/restore for rapid iteration.

## Setup (one-time, ~850MB)

```bash
mkdir ~/vm-test && cd ~/vm-test

# Download Debian 12 cloud image (generic, has cloud-init built in)
wget -O debian-12-generic-amd64.qcow2 \
  "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2"

# Create COW overlay (sparse, uses almost no space initially)
qemu-img create -f qcow2 -b debian-12-generic-amd64.qcow2 -F qcow2 jack-test.qcow2 20G
qemu-img snapshot -c "clean" jack-test.qcow2
```

## Cloud-Init (SSH Key + Packages)

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/jiab_test -N "" -q

# user-data (use ssh_authorized_keys, NOT chpasswd)
cat > user-data << EOF
#cloud-config
hostname: jack-test
users:
  - name: testuser
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    groups: sudo
    lock_passwd: false
    ssh_authorized_keys:
      - $(cat ~/.ssh/jiab_test.pub)
packages: [git, python3, python3-pip, python3-venv, sudo]
runcmd:
  - echo "VM READY" > /tmp/vm-ready
ssh_pwauth: false
EOF

echo "instance-id: jack-test-001" > meta-data
echo "local-hostname: jack-test" >> meta-data

# Create ISO
genisoimage -output cloud-init.iso -volid cidata -joliet -rock user-data meta-data
```

## Boot

```bash
qemu-system-x86_64 \
  -m 2G -smp 2 -enable-kvm -cpu host \
  -hda jack-test.qcow2 \
  -cdrom cloud-init.iso \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-pci,netdev=net0 \
  -nographic -serial mon:stdio
```

## Connect

```bash
ssh -i ~/.ssh/jiab_test -p 2222 testuser@localhost
```

## Snapshot/Restore Cycle

```bash
# Take snapshot (VM must be OFF)
qemu-img snapshot -c "after-install" jack-test.qcow2

# Restore to snapshot
qemu-img snapshot -a clean jack-test.qcow2

# List snapshots
qemu-img snapshot -l jack-test.qcow2
```

## SCP Files Into VM

```bash
scp -i ~/.ssh/jiab_test -P 2222 file.sh testuser@localhost:/tmp/
```

## Pitfalls

0. **2GB RAM NOT enough for ML workloads** — FastEmbed model download (~500MB) OOM kills at 2GB. Use 4GB+ for anything with model downloads. Use 2GB only for pure stdlib work.
1. **Use generic image, NOT nocloud** — nocloud doesn't have cloud-init built in
2. **SSH key via ssh_authorized_keys** — chpasswd + ssh_askpass doesn't work without GUI
3. **genisoimage OR mkisofs** — need one of them for cloud-init ISO
4. **NoCloud ISO filenames must be exact** — the ISO root must contain `user-data` and `meta-data`. If your source files have custom names (e.g. `user-data-clean-2c2g`), put them in a seed dir with exact basenames or use graft points. Symptom when wrong: VM boots but SSH key is not injected → `Permission denied (publickey)`.
5. **Port conflicts** — check `ss -tlnp` before booting, use different hostfwd ports
5. **Can't snapshot while VM running** — must shutdown first
6. **KVM needed** — check `/dev/kvm` exists, `kvm_amd` or `kvm_intel` loaded
7. **~850MB base image + installed data** — COW overlay grows with writes
8. **GTK display doesn't work in some envs** — use `-nographic -serial mon:stdio` always
9. **Old QEMU processes become zombies** — `pkill -9 -f qemu-system` to clean up
10. **Changing user-data requires new ISO + new disk** — recreate both
11. **Multiple QEMU instances on same disk** — COW write lock prevents concurrent access
12. **2GB RAM minimum** for installer testing, check `free -h` before starting
13. **`-cpu host` REQUIRED for NumPy 2.x** — without it, QEMU emulates generic CPU lacking x86_v2 instructions. Error: `RuntimeError: NumPy was built with baseline optimizations: (X86_V2) but your machine doesn't support: (X86_V2).` Always use `-cpu host` with `-enable-kvm`.
14. **Debian 12 externally managed** — `pip install` fails with PEP 668. Use venv or `--break-system-packages`.
15. **Cloud-init takes 60-90s** — packages install on first boot. Don't assume SSH is ready immediately.
16. **Kilo.ai API** — free model is `kilo-auto/free` (reasoning model, content in reasoning field with low max_tokens). Other models require credits.
17. **Port mapping for services** — if host ports are taken, map different host ports: `hostfwd=tcp::9080-:8080,hostfwd=tcp::9373-:37373`
18. **JackrabbitDLM needs /home/JackrabbitDLM directory** — create with `sudo mkdir -p /home/JackrabbitDLM && sudo chown user:user /home/JackrabbitDLM`
19. **DLMLocker requires `Host` (capital H)** not `host` — and `Put()`/`Get()` not `Store()`/`Retrieve()`
20. **DLM data is VOLATILE** — exists only while Lock held. `Get()` returns NoData after `Unlock()`. Design accordingly (keep lock for session duration).
21. **hermes_cli module not found** — needs `export PYTHONPATH=~/jack-in-a-box/hermes-agent` before running `python3 -m hermes_cli.main`
22. **Hermes hardcoded default model** — `AIAgent.__init__` defaults to `anthropic/claude-opus-4.6`. Config `default_model` doesn't override in interactive mode. Must pass `-m model` explicitly.
23. **Kilo.ai provider mapping** — `kilo` maps to `kilocode` via `_PROVIDER_ALIASES` in `hermes_cli/auth.py`. Custom provider names are rejected. Use `provider: kilo` in config.
24. **Reasoning models** — `kilo-auto/free` puts response in `reasoning` field. `content` may be null for short prompts. Use `max_tokens` >= 100 to get actual content.

## Port Mapping
| Host | VM | Service |
|------|----|---------|
| 2222 | 22 | SSH |
| 9080 | 8080 | Gateway |
| 9373 | 37373 | DLM |

## Persistent Autostart with User systemd

Use this when a QEMU VM should survive sessions and come back after host reboot without root-level service setup. This is better than leaving an ad-hoc terminal QEMU process running.

### Pattern

1. Create a start script that:
   - Uses the real active disk image, not stale helper names (`jack-freeze-test.qcow2`, not old `jack-test.qcow2`)
   - Uses `flock` to avoid duplicate starts
   - Adopts an already-running QEMU process for the same disk instead of starting a second instance
   - Writes a PID file under the VM directory
   - Refuses to start if host-forwarded ports are already occupied
   - Uses `-daemonize`, `-pidfile`, `-display none`, and `-D <logfile>`

2. Create a stop script that:
   - Reads the PID file or finds QEMU by disk path
   - Tries graceful guest shutdown over SSH first (`sudo systemctl poweroff`)
   - Falls back to `TERM`, then `KILL`
   - Removes stale PID files

3. Create a user systemd unit:

```ini
[Unit]
Description=jack-freeze-test QEMU VM
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=forking
WorkingDirectory=~/vm-test
PIDFile=~/vm-test/jack-freeze-test.pid
ExecStart=~/vm-test/start-jack-freeze-test.sh
ExecStop=~/vm-test/stop-jack-freeze-test.sh
Restart=on-failure
RestartSec=10
TimeoutStartSec=120
TimeoutStopSec=120
KillMode=process

[Install]
WantedBy=default.target
```

4. Enable user-systemd persistence:

```bash
systemctl --user daemon-reload
systemctl --user enable jack-freeze-test.service
loginctl enable-linger "$USER"   # if not already enabled; requires privileges/polkit
systemctl --user start jack-freeze-test.service
```

### Example QEMU command for low-memory production test VM

```bash
qemu-system-x86_64 \
  -enable-kvm \
  -cpu host \
  -m 1024M \
  -smp 2 \
  -hda ~/vm-test/jack-freeze-test.qcow2 \
  -cdrom ~/vm-test/cloud-init.iso \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-pci,netdev=net0 \
  -display none \
  -daemonize \
  -pidfile ~/vm-test/jack-freeze-test.pid \
  -D ~/vm-test/jack-freeze-test.qemu.log
```

### Verification after restart

```bash
systemctl --user is-enabled jack-freeze-test.service
systemctl --user is-active jack-freeze-test.service
ps -eo pid,ppid,stat,etime,cmd | grep -E '[q]emu-system.*jack-freeze-test'
ss -tlnp | grep ':2222'
ssh -p 2222 -i ~/.ssh/jiab_test -o BatchMode=yes testuser@localhost '
  free -h
  nproc
  systemctl --failed --no-pager
  for s in ssh nginx remainder-api cloudflared; do systemctl is-active "$s" 2>/dev/null || true; done
  curl -fsS --max-time 10 http://127.0.0.1/health
  curl -fsS --max-time 10 http://127.0.0.1:18000/health
'
```

If the service is behind Cloudflare Tunnel, also verify externally:

```bash
curl -fsS --max-time 20 https://remainder.online/health
```

### Autostart Pitfalls

- Existing helper scripts may be stale and point at old image names (`jack-test.qcow2`). Inspect and update before trusting them.
- If QEMU was already running manually, stop it cleanly before validating the service, otherwise systemd may only adopt state indirectly.
- `systemctl --user enable` alone only starts on user manager startup. For boot-without-login, `loginctl enable-linger USER` must be active.
- Verify guest-visible RAM/CPU from inside the VM (`free -h`, `nproc`), not just the host QEMU command line.
- For production-ish stacks, verify both local guest health and public tunnel health before declaring done.

## Jack-in-a-Box v1.0.3 Production Results

Tested on fresh Debian 12 (KVM, 2GB RAM, -cpu host):

```
Installer:     bash install.sh --lite -> ALL SYSTEMS GO
Config:        provider: kilo, model: kilo-auto/free
Hermes CLI:    chat -m kilo-auto/free -q 'Say hi' -> works
REST API:      kilo-auto/free -> works
PULSE:         'Bitcoin halving' -> 6 Reddit results
Neural Memory: remember + recall -> 2 results
DLM:           port 37373, alphabet soup encoding
Gateway:       port 8080, DLM online, AES256-GCM
Desktop -> VM: Gateway + DLM reachable
```

Snapshots: clean, lite-installed-working, hermes-working, full-stack-working

### Critical Fixes in v1.0.0 -> v1.0.3
1. --components arg parsing (SKIP_NEXT pattern)
2. DLM systemd hardcoded path (expandierbar heredoc)
3. sentence-transformers -> fastembed
4. Don't swallow installer errors (2>/dev/null removed)
5. pip ensurepip fallback for fresh installs
6. Config: kilo provider + kilo-auto/free model
7. Launcher: auto chat -m kilo-auto/free when no args
8. .env: KILOCODE_API_KEY (not ANTHROPIC)
9. PYTHONPATH in launcher for hermes_cli discovery
10. python-dotenv pre-install for hermes deps

### Known Remaining Issues
- `--model` flag is per-command, not global (must use `hermes chat -m model`)
- Neural Memory `recall()` API doesn't accept `limit` keyword
- FastEmbed model download is ~500MB, times out in VM (non-critical)
- DLM data is VOLATILE — exists only while Lock held
- `kilo-auto/free` is a reasoning model — `content` may be null for short prompts

## SSH After Snapshot Restore (2026-04-21)

Host key changes on every clean snapshot restore. Must remove old key before SSH works:
```bash
ssh-keygen -R "[localhost]:2222" 2>/dev/null
# Then use StrictHostKeyChecking=accept-new for first connection
ssh -o StrictHostKeyChecking=accept-new -i ~/.ssh/jiab_test -p 2222 testuser@localhost
```

## Cloud-init apt Lock (2026-04-21)

Cloud-init installs packages on first boot. If you try `apt-get install` too early, you get lock errors. Wait:
```bash
ssh user@vm 'while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done; echo FREE'
```

## hermes-agent Deps Install Gotcha (2026-04-21)

`pip install -r requirements.txt --quiet 2>/dev/null` swallows errors. After jack-in-a-box install, some deps may be missing. Verify and install manually:
```bash
source ~/jack-in-a-box/hermes-agent/venv/bin/activate
pip install openai fire python-dotenv anthropic prompt_toolkit pyyaml rich jinja2 pyjwt debugpy tenacity
```

For hermes-agent imports, set PYTHONPATH:
```bash
export PYTHONPATH="$HOME/jack-in-a-box/hermes-agent:${PYTHONPATH:-}"
```

## Jack-in-a-Box v1.0.4 (2026-04-21) — Neural Memory Integration

Fresh VM test results (Debian 12, 4GB RAM, KVM):
```
Hermes Agent:        AIAgent OK, 63 tools
Neural Memory:       4 tools (neural_remember/recall/think/graph)
Tool Routing:        handle_function_call → memory_manager (FIXED)
PULSE:               11 sources active
Upside-Down Tests:   180/180 PASS
```

### Critical Fixes Applied
1. **Tool routing**: `model_tools.py handle_function_call()` now checks memory manager before registry dispatch
2. **GPU engine isolation**: GPU recall only loads with default db_path (prevents production data leak)
3. **Embedder injection**: NeuralMemory accepts `embedder=` param (avoids double FastEmbed load)
4. **__init__.py sync**: `get_config()` not `_load_config()` (hermes-plugin must match hermes-agent)
5. **Root check**: `id -u` → exit 1 in all installers
