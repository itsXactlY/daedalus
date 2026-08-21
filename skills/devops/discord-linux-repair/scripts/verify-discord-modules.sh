#!/usr/bin/env bash
# verify-discord-modules.sh — probe a Discord Linux payload for unresolved
# module requires (the root cause of Electron MODULE_NOT_FOUND launch crashes).
#
# For every module under APP_DIR/modules/<name>-1/<name>/ it greps bare
# require('x') calls and tries to resolve each external (non-core) specifier
# with `node -e require(...)`. Prints OK / FAIL per specifier and a summary.
#
# Usage: verify-discord-modules.sh [APP_DIR]
#   APP_DIR defaults to $HOME/.config/discord/app-1.0.146
#
# Exit code: 0 if all external requires resolve, 1 if any FAIL.
set -u
APP_DIR="${1:-$HOME/.config/discord/app-1.0.146}"
MODULES_DIR="$APP_DIR/modules"
[ -d "$MODULES_DIR" ] || { echo "No modules dir at $MODULES_DIR" >&2; exit 2; }

fail=0
while IFS= read -r pkg; do
  moddir=$(dirname "$pkg")
  reqs=$(grep -rhoE "require\('([^.][^']*)'\)" "$moddir" 2>/dev/null \
         | sed -E "s/require\('([^']*)'\)/\1/" | sort -u)
  [ -z "$reqs" ] && continue
  for spec in $reqs; do
    # skip Node core modules (accurate check via node itself)
    is_core=$(node -e "process.stdout.write(require('module').builtinModules.includes(process.argv[1])?'1':'0')" "$spec" 2>/dev/null)
    [ "$is_core" = "1" ] && continue
    # try resolving from the module dir (mirrors Electron's module resolution)
    out=$(cd "$moddir" && node -e "try{require(process.argv[1]);process.stdout.write('OK')}catch(e){process.stdout.write('FAIL:'+e.code)}" "$spec" 2>/dev/null)
    if [ "$out" = "OK" ]; then
      echo "OK    $spec  ($(basename "$moddir"))"
    else
      echo "FAIL  $spec  ($(basename "$moddir"))  [$out]"
      fail=1
    fi
  done
done < <(find "$MODULES_DIR" -maxdepth 3 -name package.json)

echo "----"
if [ "$fail" -eq 0 ]; then
  echo "All external module requires resolve."
else
  echo "Some requires FAILED — payload is incomplete, re-download needed."
fi
exit $fail
