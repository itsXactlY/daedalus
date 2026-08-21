# Discovery flow: find the authoritative config file

When a user says "I edited `<path>` but the game doesn't pick it up" or "the
game reads from somewhere else", follow this script. Each step is a concrete
shell command; chain them.

## 0. Ask / identify the launcher

If the user did not say, infer from context:

- The game is in `~/games/<Game Name>/` and they mention a launcher exe
  → Faugus-launcher (most likely if Faugus is installed) or plain Wine
- The game is in `~/.local/share/Steam/steamapps/common/`
  → Steam with Proton
- The user mentions `bottles`, `lutris`, `heroic`, `bottles-cli`
  → corresponding launcher
- The user says "I just double-click the .exe" / "wine ./game.exe"
  → plain Wine, prefix is wherever `WINEPREFIX` points (default `~/.wine`)

## 1. Find the running process and its prefix

If the game is currently running:

```bash
# Find the Wine process for the game
ps -eo pid,comm,args | grep -E "wine|proton|exe" | grep -i <game-name-or-bin>

# Then find its WINEPREFIX from its environment
tr '\0' '\n' < /proc/<pid>/environ | grep -E "^(WINEPREFIX|STEAM_COMPAT|PROTON)"
```

If the game is not running, fall back to inspecting the launcher's config
(recipe per-launcher below).

## 2. Per-launcher prefix location

### Faugus-launcher
```bash
# Active profile prefix
PREFIX="${HOME}/Faugus/default"
ls -d "$PREFIX"

# All profiles
ls "${HOME}/Faugus/"

# Games configured (the .faugus config per game)
ls -la "$PREFIX"/../config 2>/dev/null
find "${HOME}/.config/faugus-launcher" -maxdepth 2 -name "*.yaml" -o -name "*.json"
```

### Steam Proton
```bash
# Find the Steam appid for the game (use Steam store URL or library view)
APPID=XXXXXX
ls -d "$HOME/.local/share/Steam/steamapps/compatdata/${APPID}/pfx"
# Or scan:
find "$HOME/.local/share/Steam/steamapps/compatdata" -name "system.reg" -printf "%h\n"
```

### Plain Wine
```bash
echo "WINEPREFIX=${WINEPREFIX:-$HOME/.wine}"
ls -d "${WINEPREFIX:-$HOME/.wine}"
```

### Lutris
```bash
# Per-game config
find "$HOME/.local/share/lutris/games" -name "*.yml" | head
cat "$HOME/.local/share/lutris/games/<game>.yml" 2>/dev/null | grep -E "wine_prefix|prefix"
```

### Bottles
```bash
ls "$HOME/.local/share/bottles/bottles/"  # one directory per bottle
```

## 3. Find the game's config file INSIDE the prefix

Once you have the prefix, the game config lives at Wine paths translated to
host. Use the most common mappings:

```bash
PREFIX="$HOME/Faugus/default"   # adjust to your case
USER="steamuser"                # adjust to your case (steamuser, $USER, etc.)

# Documents
find "$PREFIX/drive_c/users/$USER/Documents" -name "settings.json" 2>/dev/null
# AppData/Roaming
find "$PREFIX/drive_c/users/$USER/AppData/Roaming" -name "settings.json" 2>/dev/null
# GameData
find "$PREFIX/drive_c/users/$USER/Documents" -name "*.ini" 2>/dev/null
```

For German-localized Linux hosts, ALSO check if a host mirror exists at
`$HOME/Dokumente/...` — that is the host's localized `~/Documents`, not what
the game reads.

## 4. Compare to find which is authoritative

```bash
# Stat both candidates
stat -c '%Y %n' "$PREFIX/drive_c/users/$USER/Documents/Game/settings.json" \
                "$HOME/Dokumente/Game/settings.json" \
                "$HOME/Documents/Game/settings.json"

# The one with the most recent mtime AND that the game process could have
# written is authoritative. The game process can ONLY write inside the
# prefix, so the prefix one is by definition the live one.
```

## 5. Confirm the game is reading the prefix file

If the game has its own log, check that it references the prefix path, not
a host path. For example, if the game logs "loaded config from
`C:\users\steamuser\Documents\...`" — that maps to the prefix path on the
host, NOT `~/Dokumente/...`.

## Quick reference: when the user says "edited X but it doesn't work"

1. Find the launcher and prefix (steps 1-2).
2. Compute the equivalent prefix path of the file the user edited.
3. If the user edited a HOST path that has a PREFIX equivalent, the edit
   was ineffective. Re-apply the edit to the PREFIX path.
4. If the user edited a PREFIX path but the file keeps reverting, the game
   overwrites on shutdown — edit, then verify mtime AFTER a clean shutdown.
5. If the file is being read at all but a value is wrong (e.g. a key
   ignored), check the game's docs or check for a schema version mismatch
   — that's a different problem.

## Common false leads

- A file in `$HOME/Dokumente/` or `$HOME/Documents/` that LOOKS like the
  game config. It's a host mirror, not the live one.
- A `.reg` file inside the prefix that mentions a Documents path. The
  `Personal` shell folder points to the prefix's Documents, which on the
  host filesystem lives at `<prefix>/drive_c/users/<user>/Documents/`.
  This is NOT `$HOME/Documents`.
- A symlink `My Documents -> Documents` inside the prefix. It points to
  the prefix's Documents, not the host's.
- An `IniFile` path from a Windows game log that includes
  `C:\users\...\AppData\Roaming\...`. Translate via the prefix, not via
  any host folder.
