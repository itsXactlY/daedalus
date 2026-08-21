#!/usr/bin/env bash
# start_dayz_server.sh — DayZ modded server starter for Linux + Proton.
#
# Designed to be backgrounded via:
#     nohup ./start_dayz_server.sh > /tmp/dayz-server.log 2>&1 & disown
#
# Customise the path constants below for your setup, then run.
# IMPORTANT: do NOT add `exec` to the final proton call — you need the
# parent script to exit cleanly so the DayZ process becomes an orphan
# adopted by init, surviving SSH session teardown.

set -euo pipefail

# === Path constants (edit these for your host) ===
readonly SRC_CLIENT="/home/alca/Apocalypse"                          # client mod source
readonly SRC_SERVER="/home/alca/VanillaPPMap_Server"                # server mod source
readonly MODS_ROOT="/home/alca/games/Dayz/Mods"                      # parent of all @Mod folders
readonly DEST_CLIENT="$MODS_ROOT/@VanillaPPMap/addons"               # client PBO target
readonly DEST_SERVER="$MODS_ROOT/@VanillaPPMap_Server/addons"        # server PBO target
readonly SERVER_DIR="/home/alca/games/Dayz/Server"                   # DayZ server install root
readonly SERVER_BINARY="$SERVER_DIR/DayZServer_x64.exe"
readonly CONFIG_FILE="$SERVER_DIR/serverDZ.cfg"
readonly PROFILES_FOLDER="$SERVER_DIR/profile"

# === Build tool (the dayz_dev_tools venv) ===
readonly VENV="/home/alca/.btq-tpad"

# === Proton + Steam ===
readonly STEAM_COMPAT_DATA_PATH="/home/alca/.local/share/Steam/steamapps/compatdata/221100"
readonly STEAM_INSTALL_PATH="/home/alca/.local/share/Steam/"
readonly PROTON_PATH="/home/alca/.local/share/Steam/steamapps/common/Proton - Experimental/proton"

# === Wine Z: notation (Proton maps / to Z:) ===
readonly MODS_FOLDER_WIN='Z:\home\alca\games\Dayz\Mods'
readonly CONFIG_FILE_WIN='Z:\home\alca\games\Dayz\Server\serverDZ.cfg'
readonly PROFILES_FOLDER_WIN='Z:\home\alca\games\Dayz\Server\profile'

# === Client mod list ===
# One entry per @Mod folder under $MODS_ROOT. Order matters for load priority.
readonly MOD_LIST=(
  "@CF"
  "@Dabs Framework"
  "@VanillaPPMap"   # your merged mod (renamed as needed; the @-folder name is what matters)
  # add more here
)

# === Server-only mods (loaded only on the dedicated server) ===
readonly SERVER_MOD_LIST=(
  "@VanillaPPMap_Server"
  "@BuilderLoader"
  # add more here
)

log()  { echo "$(date '+%H:%M:%S') | $*"; }

# === Step 1: Pack the mod PBOs from the latest source ===
log "=== Build PBOs from source ==="
mkdir -p "$DEST_CLIENT" "$DEST_SERVER"
rm -f "$DEST_CLIENT/Apocalypse.pbo" "$DEST_SERVER/VanillaPPMap_Server.pbo"

"$VENV/bin/pbo" -C "$SRC_CLIENT" -P "**" "$DEST_CLIENT/Apocalypse.pbo"           2>&1 | tail -3
"$VENV/bin/pbo" -C "$SRC_SERVER" -P "**" "$DEST_SERVER/VanillaPPMap_Server.pbo"  2>&1 | tail -3
log "✓ PBOs built"

# === Step 2: Wipe old logs for a clean startup trace ===
log "=== Wipe old logs ==="
find "$PROFILES_FOLDER" -type f \( -name "*.log" -o -name "*.RPT" -o -name "*.ADM" -o -name "*.mdmp" \) -delete 2>/dev/null || true
log "✓ Logs cleaned"

# === Step 3: Kill any running DayZ server (idempotent) ===
log "=== Kill any old server ==="
if pgrep -f "DayZServer_x64.exe" > /dev/null 2>&1; then
  pkill -f "DayZServer_x64.exe" || true
  log "✓ Old DayZServer killed"
  sleep 3
else
  log "  (no running server)"
fi

# === Step 4: Build Wine-path mod strings (Z:\...;Z:\...) ===
MOD_STRING=""
for m in "${MOD_LIST[@]}"; do
  p="${MODS_FOLDER_WIN}\\${m}"
  [[ -z "$MOD_STRING" ]] && MOD_STRING="$p" || MOD_STRING+=";$p"
done

SERVER_MOD_STRING=""
for sm in "${SERVER_MOD_LIST[@]}"; do
  sp="${MODS_FOLDER_WIN}\\${sm}"
  [[ -z "$SERVER_MOD_STRING" ]] && SERVER_MOD_STRING="$sp" || SERVER_MOD_STRING+=";$sp"
done

log "Mods: $MOD_STRING"
log "Server Mods: $SERVER_MOD_STRING"
log "Starting DayZServer_x64..."

export STEAM_COMPAT_DATA_PATH
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_INSTALL_PATH"

cd "$SERVER_DIR"
# NOTE: no `exec` — see header comment for why.
"$PROTON_PATH" run "$SERVER_BINARY" \
  -server \
  -config="$CONFIG_FILE_WIN" \
  -port=2302 \
  -profiles="$PROFILES_FOLDER_WIN" \
  -mod="$MOD_STRING" \
  -servermod="$SERVER_MOD_STRING" \
  -logs \
  -dologs \
  -adminlog \
  -netlog \
  -scriptDebug
