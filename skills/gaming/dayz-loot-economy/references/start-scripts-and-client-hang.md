# DayZ start scripts + client hang debugging (Apocalyps3nd, 2026-07-18)

## Working unified start scripts (43-mod list, client==server)

### Server: `/home/alca/games/DayZ/Server/start_server_apx_unified.sh`
- `DAYZ_SERVER=/home/alca/games/DayZ/Server/DayZServer_x64.exe` (absolute)
- `cd "$(dirname "$0")"` right after `set -euo pipefail` (before `ensure_exists`)
- 43 client mods + 4 servermods: `@Apocalypse_Server;@BuilderLoader;@CarCoveraLca;@EditorLoader`
- Proton compatdata 221100, `Proton - Experimental`

### Client: `/home/alca/games/DayZ/Client/!START.sh`
- `DAYZ_CLIENT=/home/alca/games/DayZ/Client/DayZ_x64.exe` (absolute)
- `SERVER_IP=192.168.0.2` (local; 192.168.0.242 was TPAD, wrong host)
- DXVK REQUIRED: `export PROTON_USE_DXVK=1; export WINEDLLOVERRIDES="d3d11=n,b;dxgi=n,b"`
- DayZ.cfg dialog suppress REQUIRED: append `disableNaDialog=1; disableServerInfo=1;`

## Client hang — two modes
| Mode | Symptom | Fix |
| A: modded dialog | Hangs at "GROUP"/modded-version dialog | DayZ.cfg disableNaDialog=1; disableServerInfo=1; |
| B: PreloadCam | Login ok -> WaitPreloadCamLoginState -> ~2min -> terminate, RPT ~24 lines no error | PROTON_USE_DXVK=1 + WINEDLLOVERRIDES d3d11/dxgi |

Client RPT: `.../compatdata/221100/pfx/.../AppData/Local/DayZ/DayZ_x64_*.RPT`
Server RPT: `Server/profile/DayZServer_x64_*.RPT` (different file).

## Process-kill terminal trap
`pkill`/`kill` on DayZ from agent shell kills the agent terminal (shared Proton tree).
Use: `(setsid bash -c 'for p in $(pgrep -f "DayZServer_x64.exe"); do kill -9 "$p"; done' >/dev/null 2>&1 &)`
Or let user close on-screen.

## Success criteria (NOT port-bind)
Server: `grep -c "SCRIPT    (E)" Server/profile/script_*.log` == 0 + "Failed to load mission" absent + "SteamGameServer_Init SUCCESS".
Port binds during load BEFORE mission module compiles = zombie window, not stable.
