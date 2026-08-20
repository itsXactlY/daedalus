#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# daedalus-backup-sync — Hourly backup of ~/.daedalus/ to private GitHub repo
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

DAEDALUS_DIR="$HOME/.daedalus"
LOG_FILE="$DAEDALUS_DIR/logs/backup-sync.log"

# Ensure SSH can find the key in cron context
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new"

mkdir -p "$DAEDALUS_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

cd "$DAEDALUS_DIR"

# Stage all changes (respecting .gitignore)
git add -A 2>/dev/null

# Check if there's anything to commit
if git diff --cached --quiet 2>/dev/null; then
    log "No changes detected, skipping."
    exit 0
fi

# Commit with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
CHANGED=$(git diff --cached --stat | tail -1)
git commit -m "auto-backup: $TIMESTAMP" --quiet 2>/dev/null
log "Committed: $CHANGED"

# Push to remote
if git push origin main 2>>"$LOG_FILE"; then
    log "Push successful."
else
    log "Push FAILED — will retry next run."
    exit 1
fi
