---
name: hermes-private-backup-repo
description: "[Legacy Hermes stack - its gateway still runs on this host] Set up a private GitHub backup repo for ~/.hermes/ with hourly cron — code, config, skills backup"
category: devops
---

# Hermes Private Backup Repo

Full backup of `~/.hermes/` (code, config, skills, plugins) to a private GitHub repo with hourly cron sync.

## Prerequisites

- GitHub SSH key configured (`ssh -T git@github.com`)
- `gh` CLI authenticated (`gh auth login`)

## Setup Steps

### 1. Initialize git in ~/.hermes/

```bash
cd ~/.hermes
git init
git branch -M main
```

### 2. Create .gitignore (critical!)

`~/.hermes/` is ~31GB. Exclude regenerable/transient files:

```gitignore
# Virtual environments (regenerable)
venv/
.venv/
__pycache__/
*.pyc

# Submodules (own remotes)
hermes-agent/
tinker-atropos/

# Node (regenerable)
node_modules/

# Transient / Runtime
.snapshots/
logs/
pastes/
images/
sessions/

# Large binaries (not code)
state.db
state.db-shm
state.db-wal
.hermes_history
models_dev_cache.json
skills.tar.gz
checkpoints/

# Build artifacts
hermes_agent.egg-info/

# IDE
.vscode/
.direnv/
.pytest_cache/

# Private keys
*.ppk
*.pem

# Misc transient
auth.lock
.update_check
.worktrees/
mini-swe-agent/
```

**What's included:** skills/ (CRITICAL), config.yaml, .env, SOUL.md, all tools/, gateway/, cron/, plugins/, agent/, hermes_cli/, scripts/, memories/, tests/, all .md files, website/, docs/

**What's excluded:** ~22GB of regenerable venv, 12GB snapshots, 5.4GB checkpoints, session data, logs

### 3. Create private repo

```bash
gh repo create itsXactlY/hermes-backup --private --description "Full backup of ~/.hermes/"
git remote add origin git@github.com:itsXactlY/hermes-backup.git
git add -A
git commit -m "initial: hermes-backup — code, config, skills, plugins"
git push -u origin main
```

### 4. Create sync script

`~/.hermes/scripts/hermes-backup-sync.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

HERMES_DIR="$HOME/.hermes"
LOG_FILE="$HERMES_DIR/logs/backup-sync.log"

# CRITICAL: SSH key not available in cron context — must be explicit
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new"

mkdir -p "$HERMES_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

cd "$HERMES_DIR"

git add -A 2>/dev/null

if git diff --cached --quiet 2>/dev/null; then
    log "No changes detected, skipping."
    exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
CHANGED=$(git diff --cached --stat | tail -1)
git commit -m "auto-backup: $TIMESTAMP" --quiet 2>/dev/null
log "Committed: $CHANGED"

# CRITICAL: branch is "main" not "master"
if git push origin main 2>>"$LOG_FILE"; then
    log "Push successful."
else
    log "Push FAILED — will retry next run."
    exit 1
fi
```

```bash
chmod +x ~/.hermes/scripts/hermes-backup-sync.sh
```

### 5. Install cron (Arch Linux)

```bash
sudo pacman -S --noconfirm cronie
sudo systemctl enable --now cronie
```

### 6. Set up hourly crontab

```bash
(crontab -l 2>/dev/null || true; echo "0 * * * * $HOME/.hermes/scripts/hermes-backup-sync.sh >> $HOME/.hermes/logs/backup-sync.log 2>&1") | crontab -
```

## Pitfalls

1. **Arch has no crontab** — `cronie` package must be installed explicitly
2. **SSH key invisible in cron** — `GIT_SSH_COMMAND` with explicit `-i` required, otherwise push fails silently
3. **master vs main** — `git init` creates `master` but GitHub repos default to `main`. Must `git branch -M main` BEFORE first push. Sync script must push to `main` not `master`
4. **hermes-agent/ is its own repo** — must exclude it from backup (has its own remote at itsXactlY/hermes-agent)
5. **31GB directory** — without proper .gitignore, git add will timeout on .snapshots (12GB) and checkpoints (5.4GB)

## Verify

```bash
# Check cron is running
systemctl is-active cronie

# Check crontab
crontab -l

# Manual test
~/.hermes/scripts/hermes-backup-sync.sh

# Check log
tail -3 ~/.hermes/logs/backup-sync.log

# Check remote
gh repo view itsXactlY/hermes-backup --json name,visibility
```
