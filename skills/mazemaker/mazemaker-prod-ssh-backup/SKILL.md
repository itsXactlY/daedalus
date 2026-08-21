---
name: mazemaker-prod-ssh-backup
description: SSH emergency backup for mazemaker-prod — restore from any machine
---

# mazemaker-prod SSH Emergency Backup

## Backup File
`~/backups/mazemaker-prod-ssh-backup-20260503.tar.gz` (6.2 KB)
Also: `/tmp/mazemaker-prod-ssh-backup-20260503.tar.gz`

## Server Details
- **Host:** mazemaker-prod / AlmaLinux 10 / 89.167.114.125
- **SSH Port:** 47777
- **SSH User:** root
- **SSH Key:** `~/.ssh/mazemaker-prod` (ed25519)

## Backup Contents
```
ssh/
  local/
    mazemaker-prod      # private key
    config              # SSH config (Host mazemaker-prod)
    known_hosts         # server host keys (ed25519, rsa, ecdsa)
  remote/
    server-ssh.tar.gz   # server-side: host keys + sshd_config + authorized_keys
restore.sh              # one-time restore script
README.md               # full instructions
```

## Restoring on Any Machine
```bash
tar xzf mazemaker-prod-ssh-backup-*.tar.gz
cd mazemaker-prod-ssh-backup-*/
./restore.sh --dry-run   # preview
./restore.sh             # restore
ssh mazemaker-prod
```

## restore.sh Behaviour
- Installs `~/.ssh/mazemaker-prod` (mode 600)
- Appends to `~/.ssh/config` (merges, no overwrite of existing)
- Merges host keys into `~/.ssh/known_hosts` (skips duplicates)
- Existing `mazemaker-prod` entries NOT overwritten

## Server-Side Recovery
```bash
# On server, as root:
tar xzf ssh/remote/server-ssh.tar.gz -C /
systemctl restart sshd
```

## Created
2026-05-03. Server untouched — read-only operations only.