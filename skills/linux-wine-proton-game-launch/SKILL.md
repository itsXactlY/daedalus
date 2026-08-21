---
name: linux-wine-proton-game-launch
description: Set up Windows-only games on Linux via Faugus-launcher, Steam Proton (umu-launcher), or raw Wine. Covers identifying the active Wine/Proton prefix, finding the game's settings.json (often TWO copies, only one is load-bearing), EAC/BattlEye runtime injection via PROTON_EAC_RUNTIME, Wine URL handler registration for in-game "continue in browser" prompts, and FUSE-PSD-safe Chrome wrappers when xdg-open launches a browser that crashes on a FUSE overlay. Triggers when a user reports a Windows-only game with anti-cheat errors, plugin load failures, browser prompts that don't open a browser, settings that "don't take effect", Faugus-launcher / Proton / Wine prefix / .reg / winebrowser.exe mentions, or `Transport endpoint is not connected (107)` from a Chrome launch.
---

# Linux Wine/Proton Game Launch

Class-level skill for getting a Windows-only game running on Linux through Faugus-launcher, Steam Proton (umu-launcher / Proton-CachyOS), or raw Wine. The recurring trap: **the game reads its state from inside the active Wine/Proton prefix, NOT from the native Linux path**. Editing the wrong file appears to take but the game never sees it.

## When to load

Any of these signals:
- User reports a Windows-only game with: anti-cheat (EAC/BE) errors, "plugin load failed" dialogs, "continue in browser" prompt with no browser opening, settings/config not persisting
- User mentions Faugus-launcher, umu-launcher, Proton (any flavor), Wine prefix, `winereg`, `winebrowser.exe`, EAC, BattlEye
- User wants to play a Steam game on Linux and the AppID matters (compatdata path)
- User gets `Transport endpoint is not connected (107)` from a Chrome launch
- `xdg-open` opens a browser but it crashes immediately with FUSE-overlay-related errors

## Workflow

### 1. Identify the active launch mechanism FIRST

Probe before touching any file:

```bash
pgrep -af "faugus-launcher|umu-run|wine|proton" | head
faugus-launcher list 2>&1 | grep -E "WINEPREFIX|PROTON_EAC"
ls /home/alca/Faugus/*/version 2>/dev/null
ls ~/.local/share/Steam/steamapps/compatdata/ 2>/dev/null
```

| Launcher | Active prefix | Notes |
|---|---|---|
| **Faugus-launcher** | `WINEPREFIX=/home/alca/Faugus/<profile>` (often `default`) | User often has multiple profiles |
| **Steam Proton** | `~/.local/share/Steam/steamapps/compatdata/<AppID>/pfx/` | AppID is the directory name |
| **Raw Wine** | `WINEPREFIX=...` or `~/.wine` | User-set, sometimes stale |
| **umu-launcher / GE-Proton** | umu-managed, often under `~/.local/share/Steam/...` | Check `~/.config/umu/...` |

### 2. Find the settings.json (or equivalent config)

ALWAYS search BOTH the active prefix path AND the native Linux mirror:

```bash
find $WINEPREFIX/drive_c -name "settings.json" 2>/dev/null
find $HOME -name "settings.json" -path "*<game-name>*" 2>/dev/null
diff <prefix-path>/settings.json <native-mirror>/settings.json
```

If they differ, the prefix is the source of truth. Mirror edits are placebos. If both must stay in sync (game overwrites both), edit both.

### 3. Anti-cheat (EAC / BattlEye)

Faugus and umu auto-inject AC runtime via env vars:
- `PROTON_EAC_RUNTIME` — Linux EAC `.so` (e.g. `~/.config/faugus-launcher/components/eac/v2/lib64/`)
- `PROTON_BATTLEYE_RUNTIME` — same for BattlEye

Verify the component is installed:
```bash
ls -la ~/.config/faugus-launcher/components/eac/v2/lib64/
ls $WINEPREFIX/drive_c/users/steamuser/AppData/Roaming/EasyAntiCheat/ 2>/dev/null
```

EAC bootstrapper logs: `<prefix>/drive_c/users/steamuser/AppData/Roaming/EasyAntiCheat/<productid>/<deploymentid>/anticheatlauncher.log`

If the log shows `Anti-cheat service disabled on backend` and `result code: 511` — server-side, not your problem. The launcher still exits 0 and the game runs in null-client mode (no online AC). The user can still play unless the game server enforces AC.

### 4. Game-side "anticheat plugin" loading (NGMP-style)

Some games (C&C Generals Online, others using NGMP) have a SECOND AC layer: a plugin loader that reads `plugins.anticheat` from `settings.json` and tries to `LoadLibrary("plugins/<value>.dll")` from the game working dir.

- Empty value → `plugins//.dll` → Error 126 (ERROR_MOD_NOT_FOUND)
- Correct value: the plugin's folder name, e.g. `"easyanticheat"` → `plugins/easyanticheat.dll`
- Plugin DLL ships with the game in `<game>/Data/plugins/<name>/<name>.dll`

The setting lives in the prefix's `Documents/` path, not the game's install dir:
```bash
grep -A1 "\"plugins\"" <prefix>/drive_c/users/steamuser/Documents/.../settings.json
```

### 5. Wine URL / browser handling

Games that show "continue in browser" or similar need Wine to know how to open URLs. Wine's `http`/`https` shell\open\command is often empty. Probe and fix:

```bash
WINEPREFIX=$PREFIX $WINE reg query "HKCR\http\shell\open\command"
WINEPREFIX=$PREFIX $WINE reg query "HKCR\https\shell\open\command"

# If empty or wrong:
WINEPREFIX=$PREFIX $WINE reg add "HKCR\http\shell\open\command" /ve /d '"C:\windows\system32\winebrowser.exe" "%1"' /f
WINEPREFIX=$PREFIX $WINE reg add "HKCR\https\shell\open\command" /ve /d '"C:\windows\system32\winebrowser.exe" "%1"' /f
```

`$WINE` is the actual wine binary, NOT a generic system `wine`:
- Faugus/Proton-CachyOS: `/home/alca/.local/share/Steam/compatibilitytools.d/Proton-CachyOS Latest/files/bin/wine`
- Steam Proton: `<Steam root>/steamapps/common/Proton X.Y/files/bin/wine`

`winebrowser.exe` calls `xdg-open` on the host.

### 6. Host browser: xdg-mime + isolated Firedragon wrapper (NEVER chrome on alca's machine)

**HARD RULE — DO NOT INSTALL OR TOUCH CHROME.** See the `never-touch-chrome-alca-machine` skill (security category). On alca's Garuda box, the operator uses Firedragon (`/usr/bin/firedragon`) exclusively. Any "FUSE-PSD-safe Chrome wrapper" pattern in old skill revisions is OBSOLETE AND FORBIDDEN — it crashed the operator's Chrome profile on 2026-05-22 and 2026-06-21.

If `xdg-open` opens a browser that crashes (FUSE overlay `Transport endpoint is not connected (107)`, or anything else), the fix is **NEVER to make Chrome work**. The fix is a Firedragon wrapper with an isolated profile.

1. Create `~/.local/bin/wine-browser` (or `<purpose>-browser`):
   ```bash
   #!/bin/bash
   PROFILE="/tmp/wine-browser-iso"
   mkdir -p "$PROFILE"
   exec /usr/bin/firedragon --profile "$PROFILE" --new-instance --no-remote "$@"
   ```
   `chmod +x` it. The `/tmp/...-iso` profile means the wrapper never touches `/home/alca/.firedragon/*`. `--new-instance --no-remote` keeps the user's running Firedragon untouched. NEVER add `pkill` — the user has Firedragon open with live state.
2. Create `~/.local/share/applications/wine-browser.desktop`:
   ```ini
   [Desktop Entry]
   Version=1.0
   Name=Wine Browser (Firedragon isolated)
   Exec=/home/alca/.local/bin/wine-browser %U
   Terminal=false
   Type=Application
   Icon=firedragon
   Categories=Network;WebBrowser;
   MimeType=text/html;text/xml;application/xhtml+xml;application/xml;application/rss+xml;application/rdf+xml;image/gif;image/jpeg;image/png;x-scheme-handler/http;x-scheme-handler/https;x-scheme-handler/ftp;video/webm;
   StartupNotify=true
   ```
3. **THE GOTCHA: edit `~/.config/mimeapps.list` by hand** (see Pitfalls — `xdg-mime default` is not enough):
   ```bash
   # In [Added Associations] AND [Default Applications] sections, for each line:
   #   x-scheme-handler/http
   #   x-scheme-handler/https
   #   x-scheme-handler/about
   #   x-scheme-handler/unknown
   #   text/html
   # Remove every `google-chrome.desktop` and `chrome-wrapper.desktop` reference.
   # Put `wine-browser.desktop` as the FIRST entry.
   # Then also: xdg-settings set default-web-browser wine-browser.desktop
   ```
4. Verify with: `xdg-mime query default x-scheme-handler/https` — must print `wine-browser.desktop`, NOT `google-chrome.desktop`.

This satisfies the Hard Rule: Firedragon only, isolated profile, never touches the user's real Firedragon or Chrome.

### 8. Dedicated / headless game SERVER under Proton (no Steam app)

Some games ship a server binary that is NOT a Steam app (e.g. DayZ
`DayZServer_x64.exe`). Launch it through the SAME prefix your client uses —
never裸 `/usr/bin/wine`, which crashes differently from GE-Proton.

Pattern (Faugus-managed GE-Proton, verified 2026-07-17):
```bash
export WINEPREFIX="/home/alca/Faugus/default"
export PROTONPATH="Proton-GE Latest"
export STEAM_COMPAT_DATA_PATH="$WINEPREFIX"
export PROTONFIXES_DISABLE=1
export PROTON_USE_WOW64=1
export WINEDLLOVERRIDES="d3d11=n,b;dxgi=n,b"
export WINEDEBUG=-all
/home/alca/.local/share/faugus-launcher/umu-run \
    DayZServer_x64.exe -config=serverDZ.cfg -port=2302 \
    -mod="Z:\\path\\to\\@ModA;Z:\\path\\to\\@ModB" \
    -nosound -noPause -noLauncher >> server_startup.log 2>&1 &
```
Get the live `WINEPREFIX`/`PROTONPATH` from `faugus-launcher list` (env vars
section) — do NOT hardcode; the user may have multiple profiles.

**PITFALL — invariant CPU crash that survives ALL Wine/Proton configs.**
If the server segfaults identically across裸 wine / vanilla-only mods /
`-noLauncher`+software / DXVK override / GE-Proton, the fault is in the GAME
BINARY vs your CPU, NOT the launcher. Diagnose: read the `.RPT` crash log, find
`Exception code: C0000005` + `Fault address: <hex>` + `Fault code bytes: <hex>`.
Disassemble the bytes (e.g. `48 3B 11` = `CMP RAX,[RCX]`; `48 8D 4A 08` =
`LEA RCX,[RDX+8]` = NULL-`this` vtable call). If the fault OFFSET is identical
across 5 configs, it is a CPU/engine incompat (e.g. DayZ 1.28 server binary
segfaults on AMD Zen2 / Ryzen 3800X but the client boots). Fix = run on a
newer-CPU host, use an older binary, or QEMU-emulate. Do NOT keep swapping
Wine/Proton versions — the offset is invariant. This trap cost a full session
of "fix the loot build" before the binary/CPU root cause was found.

After each fix, ask the user to:
1. **Fully quit** the game (kill wine/proton processes — minimize is not enough; old log files persist otherwise)
2. Restart via the launcher
3. Try the failing action
4. Read the **fresh** log (check timestamp — old logs from previous runs are a recurring source of confusion)

Two log files in two paths is the most common "I checked the log but it still shows the old error" trap. Always tell the user which log is active and where to find it.

## DayZ CLIENT hangs at "You are playing a modded version" dialog (Proton)

**Symptom:** DayZ client (`DayZ_x64.exe`) under Steam Proton launches, shows the
"*You are playing a modded version of the game, which may change gameplay...*"
dialog (often overlaid by a mod's own activation dialog, e.g. the Groups addon
"GROUP" window), and never proceeds. Headless/auto-start never dismisses it, so the
client sits there forever. Player never reaches the server.

**Root cause:** `DayZ.cfg` lacks `disableNaDialog` / `disableServerInfo`. DayZ shows
the modded-version dialog on EVERY launch when those flags are absent, and an
unattended start has no one to click "OK".

**Fix (verified 2026-07-18):** append two flags to the client `DayZ.cfg` inside the
Proton prefix. The load-bearing path is NOT the native Linux path — it is inside the
prefix `Documents/DayZ/`:
```
PREFIX=/home/alca/.local/share/Steam/steamapps/compatdata/221100/pfx
CFG="$PREFIX/drive_c/users/steamuser/Documents/DayZ/DayZ.cfg"
cp "$CFG" "${CFG}.bak_$(date +%H%M%S)"
printf 'disableNaDialog=1;\r\ndisableServerInfo=1;\r\n' >> "$CFG"
```
Use CRLF (`\r\n`) to match DayZ's cfg format. After restart the dialog is suppressed and
the client connects normally (verified: Player "Rene" joined, all login states passed).

**PITFALL — killing the client rips the agent's own terminal down.** The DayZ client
was launched from a shell that shares the process tree with the agent (the START.sh
was a child of the agent session). Any `pkill -f DayZ_x64.exe` or `kill <pid>` issued
from the agent's own shell ALSO kills the agent's terminal (exit code -15/-9 from
signal propagation through the shared tree). This also hit `pkill -f DayZServer_x64.exe`
the same way. **Correct kill pattern:** issue it in a DETACHED subshell so the signal
does not propagate back into the agent shell:
```bash
(setsid bash -c 'for p in $(pgrep -f "DayZ_x64"); do kill -9 "$p" 2>/dev/null; done' >/dev/null 2>&1 &)
echo "kill issued in detached subshell"
```
Or simply let the user close it on-screen (Alt+F4 / window close) — preferred when the
dialog is visible and dismissable. Do NOT use bare `pkill`/`kill` from the agent shell
against Proton-launched DayZ processes.

**Note:** the Groups-addon "GROUP" overlay dialog is a SEPARATE mod permission dialog
that rides on top of the DayZ modded-version dialog. If it persists AFTER
`disableNaDialog` is set, the Groups mod itself needs a permission/activation config —
that is a mod issue, not the DayZ.cfg flag. In the Apocalyps3nd case the DayZ flag alone
was sufficient because the "GROUP" text was just the underlying modded dialog's backdrop.

## Pitfalls

- **Two-path settings.json trap**: native Linux mirror often exists from an earlier Wine install; only the active prefix is read. Always `diff` and edit the prefix file. Mirror is for cross-launcher consistency, not authority.
- **Wine reg add needs WINEPREFIX set** to the same prefix the launcher uses. Wrong WINEPREFIX → either silent write to wrong prefix or lock error.
- **Faugus profile name ≠ "default"**: Faugus supports multiple profiles under `~/.Faugus/<profile>/`. Check which profile owns the game before editing.
- **Wine's `ntsync: up and running` and CPU topology errors are benign** noise from wine-11.0 on cachyos/other kernels. Ignore.
- **EAC "Anti-cheat service disabled on backend"**: not your bug. The game's EAC team chose not to enforce server-side validation. Local plugin still loads in null-client mode.
- **The "Anticheat Error" dialog with `plugins//dll`**: empty value + dropped dot in the format string is a code artifact, not a real path. Fix: set `plugins.anticheat` to a non-empty plugin name.
- **wine-browser.desktop won't override system default if MIME type doesn't match**: copy the full `MimeType=` line from the system `/usr/share/applications/firedragon.desktop` and append the user's MIME handlers.
- **Don't recommend `firefox` or `chromium`** without first checking they're installed. The user may only have one browser and a custom wrapper for it.
- **THE mimeapps.list TWO-SECTION GOTCHA (CRITICAL)**: `xdg-mime default <x>.desktop <mime>` writes to `[Added Associations]` in `~/.config/mimeapps.list`. But `xdg-mime query default <mime>` reads from `[Default Applications]`. If `[Default Applications]` already has a different value, `xdg-mime default` is a NO-OP for query purposes. Solution: edit `~/.config/mimeapps.list` BY HAND and put the new entry in BOTH sections. For chrome cleanup, also remove any `chrome-wrapper.desktop` references from BOTH sections (deleting the .desktop file does NOT remove the mimeapps entry).
- **NEVER install or touch Chrome on alca's machine.** See `never-touch-chrome-alca-machine` (security category). The hard rule fires on ANY xdg-default edit, .desktop file create/modify, mime type change, browser launcher, or chrome-profile-touching operation. Skipping the rule crashes the operator's live Chrome session.

## Quick probes

```bash
# What's actually running?
pgrep -af "wine|umu|proton|faugus"

# Where is the active prefix?
echo "$WINEPREFIX"
ls -la /home/alca/Faugus/*/system.reg 2>/dev/null
cat /home/alca/Faugus/default/version 2>/dev/null  # Proton flavor

# What URLs is the game trying to open?
strings <game>.exe | grep -E "https?://.*login" | head

# What FUSE overlays are mounted?
mount | grep "fuse-overlayfs" | head

# Which settings.json is the active one?
find $WINEPREFIX/drive_c -name "settings.json" 2>/dev/null
```

## Companion deep-dive: finding the authoritative config file

The full companion write-up on locating the load-bearing config file (the
"two settings files" trap) was absorbed from `linux-windows-game-config-paths`.
It covers per-launcher prefix discovery, the Windows-path → prefix-path mapping
table, distinguishing the authoritative prefix file from a host mirror, and
per-launcher EAC/BattlEye log locations. Reachable support:

- `references/linux-windows-game-config-paths/discovery-flow.md` — walkthrough from "edit didn't take" to "found the right file", with shell one-liners per launcher.
- `references/linux-windows-game-config-paths/faugus-launcher-quirks.md` — Faugus prefix layout, env vars, EAC/BE component path, tracked_files.
- `references/linux-windows-game-config-paths/eac-under-proton.md` — EAC under Wine/Proton: bootstrapper config, product/sandbox/deployment IDs, `result code: 511`, reading `anticheatlauncher.log`.
- `scripts/linux-windows-game-config-paths/find-game-config.sh` — diagnostic: pass a game-name + optional filename substring, scans Faugus / Steam Proton / plain Wine / Bottles prefixes, prints candidate config paths with mtimes and host-side mirrors so you can see at a glance which file is authoritative. Run it FIRST when the user reports "I edited X but the game doesn't pick it up".

## References

- `references/generals-online-faunus.md` — concrete reproduction: C&C Generals Zero Hour R2P Edition via Faugus + Proton-CachyOS, with the exact EAC product IDs, registry commands, and the Firedragon-isolated wine-browser wrapper (NOT a chrome-wrapper).
- `references/mimeapps-list-two-section-gotcha.md` — technical detail of the `xdg-mime default` vs `xdg-mime query default` mismatch and the recipe for hand-editing `~/.config/mimeapps.list`.
- Cross-reference: `security/never-touch-chrome-alca-machine` — the operator's hard rule on browser-touching.
