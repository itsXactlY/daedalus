---
name: jack-in-a-box-hermes-integration
description: "[Legacy Hermes stack - its gateway still runs on this host] How jack-in-a-box installer integrates with the Hermes agent harness"
category: devops
version: 1.0
tags: [jack-in-a-box, installer, hermes, integration, deployment, harness]
priority: high
---

# Jack-in-a-Box → Hermes Integration

How the all-in-one installer wires into the Hermes agent harness.

## The Stack Jack-in-a-Box Deploys

```
jack-in-a-box (installer)
    |
    +---> hermes-agent (dev/unified branch)
    |         +---> Neural Memory plugin
    |         +---> PULSE skill
    |         +---> Skills directory (~/.hermes/skills/)
    |
    +---> neural-memory (standalone)
    |
    +---> pulse-hermes (standalone)
    |
    +---> Jackrabbit Wonderland (crypto layer)
              +---> JackrabbitDLM (key vault)
```

## Integration Points

### 1. Plugin Installation
Jack-in-a-Box copies plugins to `~/.hermes/plugins/`:
- `plugins/memory/mazemaker/` — Neural Memory
- `plugins/crypto/` — Wonderland crypto plugin (if not --lite)

### 2. Skill Installation
PULSE SKILL.md copied to `~/.hermes/skills/devops/pulse/SKILL.md`
Other skills from the projects installed similarly.

### 3. Config Integration
Jack-in-a-Box patches `~/.hermes/config.yaml` to enable:
- Neural memory provider
- PULSE skill activation
- Crypto plugin hooks

### 4. Service Wiring
- DLM vault on port 37373
- LAN gateway on port 8080
- Gateway PID file at `~/.hermes/gateway.pid`

## Install Modes

| Mode | Components | Command |
|------|-----------|---------|
| Full | Everything | `bash install.sh` |
| Lite | hermes + neural + pulse (no crypto) | `bash install.sh --lite` |
| Selective | Choose | `bash install.sh --components hermes,neural,pulse` |

## Pitfalls
- Install script clones repos — ensure git is configured for itsxactly
- DLM needs separate install path (`/home/JackrabbitDLM`) — also needs `psutil`
- Crypto plugin needs `pip install pycryptodome` for AES256
- After install, restart hermes gateway to pick up new plugins
- **python-dotenv** must be installed before requirements.txt (hermes_cli needs it at import)
- **PYTHONPATH** must be set in launcher for hermes_cli module discovery
- **openai SDK** is required for API calls (not in requirements.txt by default)
- **NumPy 2.x requires x86_v2** — VMs without `-cpu host` will crash on FastEmbed import
- **Kilo.ai free model**: use `kilo-auto/free` not `deepseek-ai/deepseek-r1:free` (402 on paid)
- **.env formatting**: comments on same line as content get mangled by heredoc — keep on separate lines
- **Default model**: hardcoded `anthropic/claude-opus-4.6` overrides config.yaml — must pass `--model` explicitly or fix config hierarchy

## VM Testing (Debian 12, KVM)
Tested on QEMU VM with 2GB RAM, 2 cores, KVM acceleration:
- Base image: `debian-12-generic-amd64.qcow2` (424MB, cloud-init built-in)
- COW overlay: `qemu-img create -f qcow2 -b base.qcow2 -F qcow2 disk.qcow2 20G`
- Snapshots: `qemu-img snapshot -c "name" disk.qcow2`
- SSH via cloud-init with injected ed25519 key
- Total disk: 2.6GB (base + installed data)
- **Must use `-cpu host`** for NumPy/FastEmbed compatibility

## Verified Stack
- REST API → kilo-auto/free → "Hi"
- Hermes CLI chat → works
- DLM → port 37373 → alphabet soup encoding
- Gateway → /status → DLM online, AES256-GCM
- Desktop → VM communication → Gateway + DLM reachable
- Snapshot/Restore cycle → clean → install → working → repeat
