# DayZ Modded Server Deployment on Linux + Proton (via Non-Interactive SSH)

Class-level recipe for deploying a DayZ modded server (client mod + server mod pair) on a Linux host that has Steam + Proton installed. Designed for a non-interactive workflow: agent does the work via `ssh tpad '<cmd>'` or similar, with no TTY allocation.

## Why this is a class

Many DayZ modding setups use a Windows host. Running the server on Linux + Proton is a real workflow (used on Steam Deck, dedicated Linux servers, headless boxes). It hits non-obvious pitfalls (no `exec` in start script, venv shebangs, RPT goes silent on idle, UDP vs TCP port confusion) that the standard `dayz-integrations` SKILL.md doesn't cover.

## Prerequisites on the target host

- Steam + the actual DayZ game installed (run once via Steam, even if you only need the server)
- Proton Experimental: `~/.local/share/Steam/steamapps/common/Proton - Experimental/proton`
- Steam compatdata created by Steam: `~/.local/share/Steam/steamapps/compatdata/221100`
- A DayZServer installer archive. Recommended: the 1.6 GB ZIP from a known-good release. The pre-extracted 14+ GB `tar.zst` is much slower to verify and uses too much disk.
- ~10 GB free disk (4 GB for the vanilla server + your mod source + the DayZ client install)
- 8 GB+ RAM recommended (the engine preloads heavily during addon init)

## Build tool: `dayz_dev_tools` (the `pbo` packager)

This is a custom Python venv, not a pip package. The local venv is at `/home/alca/projects/.btq/`. The `bin/pbo` script imports from `dayz_dev_tools.pbo`.

To install on a fresh target host, two options:

**Option A: rsync the whole venv (fast, ~3.4 GB)**

```bash
rsync -a /home/alca/projects/.btq/ tpad:/home/alca/.btq-tpad/
ssh tpad 'sed -i "s|/home/alca/projects/.btq/bin/python3|/home/alca/.btq-tpad/bin/python3|" /home/alca/.btq-tpad/bin/pbo /home/alca/.btq-tpad/bin/pip*'
ssh tpad '/home/alca/.btq-tpad/bin/pbo --version'  # expect: 1.10.dev0
```

**Why the shebang fix:** `bin/pbo` and `bin/pip*` are absolute-shebang Python scripts. rsync copies the shebang verbatim, so they point at the source machine's venv. After moving, the shebangs are dangling.

**Option B: fresh venv + pip install (clean, but dayz_dev_tools is NOT on PyPI)**

Doesn't work as of 2026-06. The package is sourced from a local path on the build host.

## Source code: rsync from workspace to target

```bash
# On local:
rsync -a /home/alca/apogrps_qwen/Apocalypse/ /home/alca/apogrps_qwen/VanillaPPMap_Server/ \
        tpad:/home/alca/
```

Keep the mod source as two separate top-level dirs (one for client, one for server) on the target. The build script then packs each into its own PBO.

## DayZ server install: from ZIP, not 14 GB tar.zst

The 1.6 GB ZIP extracts to ~4 GB. The 14.3 GB `tar.zst` is tempting (pre-extracted) but:

- Takes 10+ minutes just to LIST (each zstdcat|tar tf is slow over NAS)
- Uses 14+ GB extracted, eats into your free disk budget
- Harder to verify before extracting (you can't peek at the contents cheaply)

Use the ZIP. Extract to the server root on the target:

```bash
ssh tpad 'unzip -q /mnt/nas/spiele/DayZServer_1_28_161_464.zip -d /home/alca/games/Dayz/Server/'
```

## Config files: rsync from local, skip `addons/`

The ZIP gives you a default `serverDZ.cfg`, `profile/`, and `mpmissions/`. Override with the local server's user-config versions:

```bash
rsync -av --exclude='addons/' --exclude='*.log' --exclude='*.RPT' --exclude='*.ADM' --exclude='*.mdmp' --exclude='storage_*' \
    /home/alca/games/DayZ/Server/ tpad:/home/alca/games/Dayz/Server/
```

- **Skip `addons/`**: you have vanilla addons from the ZIP, and your mod will be packed separately into `@VanillaPPMap/addons/Apocalypse.pbo` and `@VanillaPPMap_Server/addons/VanillaPPMap_Server.pbo`.
- **Skip `*.log` / `*.RPT` / `*.ADM` / `*.mdmp`**: avoids polluting the new server with old logs.
- **Skip `storage_*`**: these are persistence files. Don't copy them — the new server should generate fresh persistence on first run.

## Start script: no `exec`, parameterize paths

See `templates/start_dayz_server.sh` for the full template. The two critical things:

1. **No `exec` at the end.** If you want to `nohup ./start.sh & disown` the start script so the SSH session can return, the script must end naturally. An `exec` replaces the shell with the DayZ process, which works in foreground but not with backgrounding.
2. **Mod path is `Z:\\home\\alca\\games\\Dayz\\Mods\\...` in Wine notation.** Proton/Wine maps the host's `/` to `Z:\\`. The mod list in `-mod=` and `-servermod=` flags must use Z:\\ paths, separated by `;` (Wine's path separator, not `:`).

Run it:
```bash
ssh tpad 'cd /home/alca && nohup ./start_dayz_server_tpad.sh > /tmp/dayz-server.log 2>&1 & disown'
```

## Server liveness check (3-step recipe)

The #1 confusion: "is the server hung, or just waiting?" DayZ writes C++ init lines to RPT, then goes silent while it waits for the first player connection. The RPT file mtime can stop updating for 10+ minutes on a healthy server with no clients.

**Critical: identify the right PID.** Under Proton the visible python/proton parent process is NOT the DayZ server — it's a launcher. The actual `DayZServer_x64.exe` runs as a Wine child and its FDs are not visible from `/proc/<proton_pid>/fd/`. Use `pgrep` to find the right PID:

```bash
# Get the REAL DayZServer PID (not the proton parent)
DAYZ_PID=$(pgrep -f "DayZServer_x64.exe" | head -1)

# 1. Process alive
ps -p $DAYZ_PID -o pid,pcpu,pmem,etime,cmd
# expect: small %CPU (often 0.0-3%), but process is still there

# 2. UDP game port listening
bash -c "echo > /dev/udp/127.0.0.1/2302"
# expect: exit 0 (open)
# TCP 2302 is normally REFUSED — DayZ uses TCP only for RCon on a different port

# 3. Mod PBOs are open in the DayZServer_x64.exe process FD table
ls -la /proc/$DAYZ_PID/fd/ | grep -E "Apocalypse.pbo|VanillaPPMap.pbo"
# expect: the PBO files show up as open file descriptors
# If you accidentally check /proc/<proton_pid>/fd/ you'll see only 3 FDs (/dev/null + stdout+stderr to your log file) — that's the launcher, not the server
```

If all three are true, the server is up and waiting. Don't keep checking the RPT — it'll stay silent until a player connects or an admin action fires.

### RCon and auto-mission-start: do NOT expect either to work

DayZ Dedicated Server has **no headless mission-start** option. The mission only loads on first player connection — verified against the local RPT pattern:

```
[local server, 9:58:34 server start]   → 110 RPT lines, then silence
[local server, 10:27:31 player "Rene" connects] → MISSION RECEIVED → GAME LOADED
[local server, 10:28:03] → Termination successfully completed
```

The 29-minute gap between server start and first connect is the server **waiting for a player**. Mission init only fires on connect. The script_*.log file (EnforceScript compile output) doesn't exist until then.

**RCon attempts that all time out (verified 2026-06-20):**

| Protocol | What | Result |
|----------|------|--------|
| `enableRCon=1; rconPassword=...` in serverDZ.cfg | Config flag | Not honored — no RCon listener appears |
| TCP port 2302/2303/2304/27015/27036 | DayZ RCon | Connection refused (all) |
| UDP `0xFF\xFF\xFF\xFF rcon <pwd> <cmd>` | Source-Engine RCon | Timeout |
| UDP `0x01 <password>\x00` | BattlEye RCon | Timeout |
| `BattlEye=1;` + RCon setup | Proper BE RCon | May work, but is a separate config block. Still doesn't help mission-start. |

The ONLY ways to trigger mission load:

1. **Real DayZ client connects** to `<server-ip>:2302` (UDP) — the player's connect handshake triggers the mission. This is the real path.
2. **Write a Python fake client** that does the Source-Engine A2S handshake + `connect` packet. DayZ's local server accepts non-Steam connections (Rene's `76561197970340352` is a fake hash), so this is technically possible but ~150 lines of code that has to defeat challenge-response. Non-trivial.
3. **DayZ headless client mode** (`DayZ_x64.exe -client`) — requires a real Steam session on the host. Same net result as option 1.

Don't try to "fix" this. If the user wants mission-load verification, give them a real client.

### `pkill` gotcha: don't `pkill -f start_dayz_server_tpad.sh`

The pattern `start_dayz_server_tpad.sh` is the shell command you're typing RIGHT NOW in the SSH session. If you run `pkill -f start_dayz`, it kills your own SSH command's grep parent (or the bash process running this very script), and your subsequent commands return 255 / Connection reset.

**Always use a more specific pattern:**

```bash
# BAD: kills the SSH process running pkill
pkill -f "start_dayz_server_tpad"

# GOOD: targets only the actual server binary
pkill -f "DayZServer_x64.exe"

# Also good: targeted by process group, not pattern
pkill -P $(pgrep -f "DayZServer_x64.exe" | head -1)
```

If you DID kill the SSH session by mistake, the next `ssh tpad '<cmd>'` will return exit 255 with "Connection reset" — just reconnect, the DayZ server isn't affected.

## Process tree under Proton (what's normal)

When running under Proton, the process tree looks like this (from `ps -auxf`):

```
bash ./start_dayz_server_tpad.sh        # parent script
└── python3 .../proton run DayZServer   # proton launcher
    └── c:\windows\system32\steam.exe    # Steam client inside Wine
        └── wineserver                   # Wine server
            └── DayZServer_x64.exe        # actual game server
```

All of these are normal. If `steam.exe` and `wineserver` show up transiently then disappear during init, that's also normal — they're not persistent.

## Common pitfalls

- **The `@Apocalypse` folder is NOT a magic name.** DayZ loads mods by folder name matching the `-mod=` flag. If the user has been calling their mod `@Apocalypse` but the server's `serverDZ.cfg` mod list still says `@VanillaPPMap`, the PBO needs to live in `@VanillaPPMap/addons/Apocalypse.pbo`, not `@Apocalypse/addons/Apocalypse.pbo`. Check the server config, not the source folder name.
- **The build script writes `mod.cpp` to `/home/alca/games/DayZ/Mods/mod.cpp` (parent of all mods), not into each `@Mod/` folder.** DayZ's launcher looks for `mod.cpp` inside each mod folder. If the build script's `mod.cpp` write isn't reaching the right place, the mod shows up correctly in-game but doesn't display metadata in the launcher.
- **Disk pressure.** With DayZ + Steam + 200+ mods, expect 5–10 GB of free space at all times. The 14.3 GB pre-extracted server tarball is overkill — use the 1.6 GB ZIP.
- **Proton path is `Proton - Experimental` with a SPACE.** Always quote the path: `"/home/alca/.local/share/Steam/steamapps/common/Proton - Experimental/proton"`.
- **`disown` after `nohup ... &` is required** for the parent shell (the SSH session) to exit without taking the DayZ process down with it.
- **TPAD/local path case difference.** TPAD uses `/home/alca/games/Dayz/` (lowercase `z`) while the local workstation uses `/home/alca/games/DayZ/` (uppercase `Z`). Linux paths are case-sensitive, so `rsync`, `ls`, and shell expansions WILL silently miss files when the case is wrong. Always `ssh tpad 'ls /home/alca/games/DayZ/...'` to verify the exact path on the remote before assuming the same case. Build scripts that hard-code one case will silently fail when run on the other host — parameterize via env var or config.
- **Steam compatdata dir may not exist on a fresh client install.** If you launch DayZ directly through Proton (bypassing Steam's own launcher), Proton tries to create `pfx.lock` in `~/.local/share/Steam/steamapps/compatdata/221100/`, but the parent dir doesn't exist (Steam only creates it when it launches the game itself). The crash looks like `FileNotFoundError: [Errno 2] /home/alca/.local/share/Steam/steamapps/compatdata/221100/pfx.lock` in the proton Python traceback. Fix: `mkdir -p ~/.local/share/Steam/steamapps/compatdata/221100/` BEFORE the first DayZ launch. (The full Wine prefix is still lazy-initialized by DayZ on first run, so this mkdir alone is enough to get past the lockfile creation step.) Same applies to any other Steam app you launch via Proton directly without going through Steam first.

## Related skills

- `dayz-integrations` (parent): PBO build, RPC routing, mod structure
- `enforce-script-syntax`: language rules
- `dayz-client-server-mod-separation`: client mod vs server mod boundaries
