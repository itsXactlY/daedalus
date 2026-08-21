---
name: jack-in-a-box
category: devops
description: All-in-one Hermes ecosystem installer - one command to deploy the complete stack
version: 1.0.3
tags: [installer, hermes, neural-memory, pulse, crypto, devops, stack]
---

# JACK-IN-A-BOX
The Hermes Stack - Everything springs to life from a single command.

## Overview
Standalone all-in-one installer that clones, installs, and wires together the complete Hermes ecosystem into a working system.

## Components (5)
| Component | Repository | Purpose |
|-----------|-----------|---------|
| Hermes Agent | itsXactlY/hermes-agent (dev/unified) | Autonomous AI agent framework |
| Neural Memory | itsXactlY/neural-memory | Local semantic memory with knowledge graph |
| PULSE | itsXactlY/pulse-hermes | Autonomous social search (15+ sources) |
| Jackrabbit Wonderland | itsXactlY/Jackrabbit-wonderland | AES256-GCM encrypted sessions |
| JackrabbitDLM | rapmd73/JackrabbitDLM | Volatile key vault (port 37373) |

## Installation Modes

### Full Stack
```bash
git clone https://github.com/itsXactlY/jack-in-a-box.git
cd jack-in-a-box
bash install.sh
```

### Lite Mode (no crypto)
```bash
bash install.sh --lite
```

### Specific Components
```bash
bash install.sh --components hermes,neural,pulse
bash install.sh --components hermes,pulse
```

### Verify Installation
```bash
bash install.sh --check
```

## Directory Structure
```
~/jack-in-a-box/
├── hermes-agent/           # Hermes Agent (itsXactlY fork)
│   ├── venv/               # Python virtual environment
│   └── plugins/memory/mazemaker/  # Neural Memory plugin
├── neural-memory/          # Neural Memory (source)
├── pulse/                  # PULSE search engine
├── jackrabbit-wonderland/  # Crypto layer
└── launch.sh               # Quick launcher
```

## Other Locations
- ~/.hermes/                # Hermes config & data
- ~/.hermes/skills/         # Skills directory
- ~/.config/jack-in-a-box/  # Jack-in-a-box config
- /home/JackrabbitDLM/      # DLM volatile vault
- /opt/hermes-crypto/       # JRWL deployed files

## Services (if DLM + crypto installed)
```bash
sudo systemctl start jackrabbit-dlm@$USER
sudo systemctl start hermes-gateway@$USER
```

## Quick Commands After Install
```bash
jack-in-a-box              # Launch everything
hermes                     # Start hermes CLI
pulse "AI video tools"     # Run PULSE search
```

## Troubleshooting

### DLM won't start
```bash
ss -tlnp | grep 37373
cd /home/JackrabbitDLM && python3 JackrabbitDLM 0.0.0.0 37373
```

### Neural Memory (v2 — symlink-based installer)
```bash
# Jack-in-a-box runs: cd neural-memory && bash install.sh install
# The installer auto-detects hermes-agent at:
#   ~/.hermes/hermes-agent, ~/jack-in-a-box/hermes-agent, ~/hermes-agent, etc.
# Creates SYMLINKS from python/ → hermes-agent/plugins/memory/mazemaker/
# Installs deps (numpy, fastembed) automatically
# --hash-backend for low-RAM systems (<3GB)
```

### Neural Memory not discovered
```bash
# Check symlinks (should point to neural-memory/python/)
ls -la ~/.hermes/hermes-agent/plugins/memory/mazemaker/__init__.py
# If broken, re-run:
cd ~/jack-in-a-box/neural-memory && bash install.sh install
```

### PULSE not found
```bash
ls -la ~/.hermes/skills/devops/pulse
cd ~/jack-in-a-box/pulse && bash install.sh
```

### Gateway not reachable
```bash
systemctl status jackrabbit-dlm@$USER
systemctl status hermes-gateway@$USER
sudo nft list ruleset | grep 8080
```

## Requirements
- Python 3.10+
- git
- Linux (tested on Garuda/Arch)
- sudo access (for DLM + crypto services only)

## Philosophy
The human built the floor. The agent builds the rest.
Jack-in-a-Box is a foundation - four systems wired together that should evolve autonomously.

## Known Issues (v1.0.3 → Fixed in v1.0.4)

| Bug | Symptom | Fix |
|-----|---------|-----|
| DLM systempackages | `pip install` fails on Debian 12 (externally-managed Python) | Added `--break-system-packages` for DLM deps (psutil) install step |
| `--components` arg parsing | Components not recognized | SKIP_NEXT pattern instead of `shift` in case |
| DLM systemd hardcoded path | Service fails on non-default install | `$DLM_DIR` + expandable heredoc (no single quotes) |
| sentence-transformers dep | Wrong embedding library installed | `fastembed` (what we actually use) |
| Skill link name | Points to wrong skill dir | `jackrabbit-wonderland` not `hermes-crypto` |
| Error silencing | Sub-installer failures invisible | Removed `2>/dev/null` from bash calls |
| pip missing | Fresh install fails | `python3 -m ensurepip --upgrade` fallback |
| Hardcoded pip | venv activation breaks pip path | `$PIP` variable everywhere |
| No neural memory config | Memory provider not set | Added `memory.provider: neural` to default config |
| Low-RAM neural backend drift | On 2GB VM, Jack-in-a-Box default config says `embedding_backend: fastembed`; Neural installer auto-selects hash but older installer skipped config update if `provider: neural` already existed. Runtime then fails: `fastembed not installed`. | Neural `install.sh` must always update `memory.neural.embedding_backend` (hash when <3GB RAM), even when provider is already neural. Manual fix: set `~/.hermes/config.yaml` → `memory.neural.embedding_backend: hash`. |
| No .env template | User doesn't know what keys to set | Created `.env` with chmod 600 |
| Default model | Hermes uses claude-opus-4.6 (paid) | Launcher auto `chat -m kilo-auto/free` |
| Provider name | Custom provider names rejected | Must use `kilo` (maps to `kilocode` via alias) |
| .env formatting | Comments merged onto same lines | Fixed heredoc line breaks |
| python-dotenv missing | Hermes CLI crashes on import | Pre-install in deps step |
| PYTHONPATH missing | `hermes_cli` module not found | Export in launcher before exec |

## Kilo.ai Provider (Free Tier)

Hermes code has `kilocode` as registered provider. Aliases: `kilo` → `kilocode`, `kilo-code` → `kilocode`.

```
Config:
  model:
    provider: kilo              # maps to kilocode
    base_url: https://api.kilo.ai/api/gateway
    api_key: <JWT_TOKEN>
    default_model: kilo-auto/free

Env: KILOCODE_API_KEY=<JWT_TOKEN>
```

**Free model**: `kilo-auto/free` — only free-tier model. Everything else needs credits.
**Reasoning model**: Response in `reasoning` field first. `content` may be null for short prompts. Use `max_tokens` >= 100.

**Launcher default**: When no args passed, auto-launch `chat -m kilo-auto/free` for free-tier users. When args passed, pass through unchanged.

## VM Testing Pattern (QEMU)

Reusable for testing installers on fresh systems:

```bash
# 1. Download base image (~400MB)
wget -O debian.qcow2 "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2"

# 2. Create COW disk (sparse, ~200KB initially)
qemu-img create -f qcow2 -b debian.qcow2 -F qcow2 vm.qcow2 20G
qemu-img snapshot -c "clean" vm.qcow2

# 3. Cloud-init for SSH access
genisoimage -output cloud-init.iso -volid cidata user-data meta-data

# 4. Boot with KVM + host CPU passthrough (required for NumPy 2.x)
qemu-system-x86_64 -m 2G -smp 2 -enable-kvm -cpu host \
  -hda vm.qcow2 -cdrom cloud-init.iso \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-pci,netdev=net0 -nographic -serial mon:stdio

# 5. Snapshot after working state
qemu-img snapshot -c "working" vm.qcow2

# 6. Restore to test again
qemu-img snapshot -a clean vm.qcow2
```

**Key learnings**:
- `-cpu host` required — NumPy 2.x needs x86_v2, QEMU default CPU doesn't support it
- COW disk uses almost no space until VM writes data
- SSH key injection via cloud-init `ssh_authorized_keys` — no password prompts
- Port conflicts: check `ss -tlnp` before booting
- Total disk: ~2.6GB (base image + installed data in COW overlay)

## Pitfalls (v1.0.3)
- systemd heredoc with `'DLMSVC'` (single quotes) does NOT expand variables — use `DLMSVC` (no quotes)
- Fresh Arch/Debian installs may not have pip — always run ensurepip first
- `shift` inside a `for arg` loop shifts the loop variable, not the positional params
- Sub-installer errors hidden by `2>/dev/null` make debugging impossible on fresh installs
- DLM needs `/home/JackrabbitDLM/DLMLocker.py` — create dir + copy before starting DLM
- DLM data is VOLATILE — exists only while Lock held, gone on Unlock
- Debian 12 externally-managed Python — can't pip install system-wide without `--break-system-packages`
- Launcher must handle both no-args (default to chat) and args (pass through) cases