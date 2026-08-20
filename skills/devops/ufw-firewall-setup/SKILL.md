---
name: ufw-firewall-setup
description: UFW firewall setup with SSH-safety-first approach for Arch and Debian systems
category: devops
---

# UFW Firewall Setup

## Critical Warning

**NEVER enable ufw without an SSH allow rule first.** If you do, you will lock yourself out of the server. This is the #1 pitfall.

## Platform Differences

### Arch Linux
- ufw is NOT installed by default
- Install with: `pacman -S ufw`

### Debian/Ubuntu
- ufw is typically available but may need install: `apt install ufw`

## Workflow (Order Matters)

### Step 1: Check Status
```bash
ufw status verbose
```

### Step 2: Whitelist IPs BEFORE Enabling

**SSH - LAN only (allow BEFORE enable):**
```bash
ufw allow from 192.168.0.0/24 to any port 22
ufw allow from 192.168.122.0/24 to any port 22
```

**Ollama API (port 11434) - specific IPs:**
```bash
ufw allow from <OLLAMA_CLIENT_IP> to any port 11434
```

### Step 3: Enable Firewall
```bash
ufw enable
```

### Step 4: Verify
```bash
ufw status numbered
```

## Standard Rules

| Service | Port | Source | Notes |
|---------|------|--------|-------|
| SSH | 22 | 192.168.0.0/24 | LAN only |
| SSH | 22 | 192.168.122.0/24 | LAN only (libvirt) |
| Ollama | 11434 | Whitelisted IPs | API access |

## Common Commands

```bash
# Disable firewall (emergency unlock)
ufw disable

# Delete a rule by number
ufw delete <NUMBER>

# Reset all rules
ufw reset

# Default policies
ufw default deny incoming
ufw default allow outgoing
```

## Pitfalls

1. **Enabling without SSH rule = locked out.** Always add SSH allow first.
2. **Arch users:** ufw service must be enabled: `systemctl enable --now ufw`
3. **Rule order:** More specific rules should come before general ones.
4. **Testing:** Always test SSH connection in a NEW terminal before closing your current session after enabling ufw.
