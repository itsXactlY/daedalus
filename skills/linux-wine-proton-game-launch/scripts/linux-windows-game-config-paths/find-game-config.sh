#!/usr/bin/env bash
# find-game-config.sh
#
# Diagnose which Wine/Proton/Faugus/Steam prefix a Windows game is using
# and where its authoritative config file lives. Prints candidate paths
# for both the prefix (authoritative) and any host-side mirror (decoy).
#
# Usage:
#   ./find-game-config.sh <game-name-substring> [filename-substring]
#
# Examples:
#   ./find-game-config.sh "Generals" "settings.json"
#   ./find-game-config.sh "DayZ" "DayZ.cfg"
#   ./find-game-config.sh "Stardew"   # searches all .json and .ini
#
# Exit code is 0 if a prefix candidate was found, 1 if not.

set -uo pipefail

GAME_SUB="${1:-}"
FILE_SUB="${2:-}"
if [[ -z "$GAME_SUB" ]]; then
  echo "usage: $0 <game-name-substring> [filename-substring]" >&2
  exit 2
fi

# File-name grep pattern. If user didn't pass one, match common config types.
if [[ -n "$FILE_SUB" ]]; then
  NAME_GLOB="*${FILE_SUB}*"
else
  NAME_GLOB="*.json"
fi

# -- Discover candidate prefix roots -----------------------------------------
declare -a PREFIXES
PREFIXES=()

# Faugus-launcher
if [[ -d "$HOME/Faugus" ]]; then
  while IFS= read -r p; do
    [[ -d "$p/drive_c" ]] && PREFIXES+=("$p")
  done < <(find "$HOME/Faugus" -mindepth 1 -maxdepth 2 -type d \
            \( -name "pfx" -o -name "drive_c" \) -printf "%h\n" 2>/dev/null)
fi

# Steam Proton
if [[ -d "$HOME/.local/share/Steam/steamapps/compatdata" ]]; then
  while IFS= read -r p; do
    [[ -d "$p/pfx/drive_c" ]] && PREFIXES+=("$p/pfx")
  done < <(find "$HOME/.local/share/Steam/steamapps/compatdata" \
            -mindepth 1 -maxdepth 1 -type d 2>/dev/null)
fi

# Plain Wine
[[ -d "$HOME/.wine/drive_c" ]] && PREFIXES+=("$HOME/.wine")

# Bottles
if [[ -d "$HOME/.local/share/bottles/bottles" ]]; then
  while IFS= read -r p; do
    [[ -d "$p/drive_c" ]] && PREFIXES+=("$p")
  done < <(find "$HOME/.local/share/bottles/bottles" \
            -mindepth 1 -maxdepth 1 -type d 2>/dev/null)
fi

if [[ ${#PREFIXES[@]} -eq 0 ]]; then
  echo "no Wine prefix discovered under common locations" >&2
  echo "checked: ~/Faugus, ~/.local/share/Steam/steamapps/compatdata, ~/.wine, ~/.local/share/bottles/bottles" >&2
  exit 1
fi

# -- For each prefix, search for files matching the game + filename ---------
printf '%-12s %-12s %-30s %s\n' "PREFIX" "MTIME" "USER" "PATH"
printf '%-12s %-12s %-30s %s\n' "------" "-----" "----" "----"

found_any=0
for prefix in "${PREFIXES[@]}"; do
  # Iterate Wine users in this prefix
  for user_dir in "$prefix/drive_c/users"/*/; do
    [[ -d "$user_dir" ]] || continue
    user="$(basename "$user_dir")"
    # Search under Documents and AppData/Roaming for the game + filename
    while IFS= read -r f; do
      mtime="$(stat -c '%y' "$f" 2>/dev/null | cut -d. -f1)"
      mtime_short="$(stat -c '%Y' "$f" 2>/dev/null | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M' 2>/dev/null)"
      prefix_short="$(basename "$(dirname "$(dirname "$prefix")")")/$(basename "$prefix")"
      printf '%-12s %-12s %-30s %s\n' "$prefix_short" "$mtime_short" "$user" "$f"
      found_any=1
    done < <(find "$user_dir/Documents" "$user_dir/AppData/Roaming" \
              -iname "$NAME_GLOB" -path "*${GAME_SUB}*" 2>/dev/null)
  done
done

if [[ $found_any -eq 0 ]]; then
  echo
  echo "(no config files matched under any prefix's Documents/AppData)"
  echo "hint: the file might be in a different Wine folder. Try:"
  echo "  find ${PREFIXES[0]}/drive_c -iname '*${GAME_SUB}*' -type f | head -20"
fi

# -- Compare with host-side mirror -----------------------------------------
echo
echo "--- HOST-SIDE MIRRORS (NOT authoritative, do not edit) ---"
for host_dir in "$HOME/Dokumente" "$HOME/Documents" "$HOME/.local/share/Steam/steamapps/common"; do
  [[ -d "$host_dir" ]] || continue
  while IFS= read -r f; do
    mtime_short="$(stat -c '%Y' "$f" 2>/dev/null | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M' 2>/dev/null)"
    printf '%-12s %s\n' "$mtime_short" "$f"
  done < <(find "$host_dir" -iname "$NAME_GLOB" -path "*${GAME_SUB}*" 2>/dev/null)
done

exit 0
