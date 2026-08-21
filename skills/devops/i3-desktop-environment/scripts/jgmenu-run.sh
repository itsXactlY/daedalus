#!/usr/bin/env bash
# jgmenu_run — hardened launcher for i3 right-click desktop menu.
#
# Why this exists (and why a bare `exec jgmenu` is not enough):
#   1. Multiple jgmenu instances launched simultaneously (click-spam, picom
#      reload, i3 restart) → they fight for pointer focus, menu disappears.
#   2. jgmenu started before i3 fully loads after reload → daemon dies silently.
#   3. Stale lock files / X resources after sleep/resume → first click denied.
#
# This script:
#   • Kills any existing jgmenu --simple instance (idempotent reopen)
#   • Verifies config exists; warns if missing (no silent fallback)
#   • Logs every invocation to ~/.cache/jgmenu.log for debugging
#   • exec's jgmenu so the process replaces the script (clean signal handling)

set -u

LOG="$HOME/.cache/jgmenu.log"
mkdir -p "$(dirname "$LOG")"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >> "$LOG"; }

log "right-click: pid=$$ args=$*"

# Kill stale instances. Only kill our own (--simple mode), leave any
# user-launched jgmenu alone.
pkill -f "jgmenu --simple" 2>/dev/null
sleep 0.05

# Make sure jgmenu is installed
if ! command -v jgmenu >/dev/null 2>&1; then
    log "ERROR: jgmenu not installed"
    notify-send -u critical "jgmenu missing" "Run: sudo pacman -S jgmenu"
    exit 1
fi

# Verify config exists; fall back gracefully if not
if [[ ! -f "$HOME/.config/jgmenu/jgmenurc" ]]; then
    log "WARN: jgmenurc missing, using built-in defaults"
fi

# Launch the menu. exec replaces this shell so signals go to jgmenu directly.
exec jgmenu \
    --config-file="$HOME/.config/jgmenu/jgmenurc" \
    --csv-importer="cat \"$HOME/.config/jgmenu/append.csv\"" \
    --simple
