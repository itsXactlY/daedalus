# Easy Anti-Cheat under Wine/Proton

## Where things live

```
<prefix>/drive_c/<game install>/
├── <game>.exe                                  # the game binary
├── EAC_LaunchGeneralsOnline.exe                # EAC bootstrapper (game-specific name)
├── EasyAntiCheat/
│   ├── Settings.json                           # EAC product/sandbox/deployment config
│   ├── Certificates/
│   │   ├── base.bin
│   │   ├── base.cer
│   │   └── runtime.conf
│   ├── Licenses/
│   └── SplashScreen.png
└── (other game files)

<prefix>/drive_c/users/<user>/AppData/Roaming/EasyAntiCheat/
└── <productid>/
    └── <deploymentid>/
        └── anticheatlauncher.log               # the detailed EAC bootstrapper log
```

The `<productid>` and `<deploymentid>` come from
`<game>/EasyAntiCheat/Settings.json`. They're a unique key per game per
deployment.

## The two log files pattern

Most EAC-protected games running through their own launcher-style
architecture will have TWO log files for the AC layer:

1. **In-game AC log** at
   `<prefix>/drive_c/users/<user>/Documents/<GameName>/<sub>/<game_ac>.log`
   This is what the GAME wrote. It logs the AC plugin loader step
   (e.g. "Attempting to load plugin from plugins/easyanticheat.dll",
   "Failed to load (126)").

2. **EAC bootstrapper log** at
   `<prefix>/drive_c/users/<user>/AppData/Roaming/EasyAntiCheat/<productid>/<deploymentid>/anticheatlauncher.log`
   This is what EAC wrote independently. It logs the bootstrapper
   connection, module download, and exit status.

These two logs are INDEPENDENT. They have separate mtimes, separate
truncation, separate rotation. When debugging, ALWAYS check both:

- If the in-game log shows a plugin load failure → the game's settings
  have a wrong `anticheat` value.
- If the bootstrapper log shows a CDN/auth failure → EAC's connection
  to Epic's backend failed.
- If only one has entries, the other subsystem never ran.

## Settings.json structure (game side)

The game-side `EasyAntiCheat/Settings.json` looks like:

```json
{
  "title": "GameName",
  "executable": "GameBinary.exe",
  "productid": "<32-hex-char-id>",
  "sandboxid": "<32-hex-char-id>",
  "deploymentid": "<32-hex-char-id>",
  "requested_splash": "EasyAntiCheat/SplashScreen.png",
  "wait_for_game_process_exit": "false",
  "hide_bootstrapper": "false",
  "hide_gui": "false"
}
```

The user does NOT normally edit this. If a game shipped with a wrong
productid/sandboxid, the game developer fixes it. The user only edits
the game-side `settings.json` (different file, in the game's user data
directory) to enable the AC plugin loader.

## In-game AC plugin loader (e.g. NGMP pattern)

Some games (e.g. C&C Generals Online using NGMP) have a SECOND AC
layer — a plugin loader inside the game client. The relevant setting
is typically:

```json
{
  "plugins": {
    "anticheat": "easyanticheat"   // or "goanticheat", or "" to disable
  }
}
```

The loader builds the plugin path as `plugins/<value>.dll` (or
`plugins/<value>dll` — varies by game). If the value is empty:

- `plugins/.dll` or `plugins//.dll` in the log
- Error 126 (ERROR_MOD_NOT_FOUND) in the log
- An error dialog like "Failed to load the AntiCheat plugin from path:
  plugins//dll"

The fix: set `anticheat` to the name of the plugin subdirectory under
the game's `plugins/` folder. For the R2P Edition of Generals Zero
Hour, that name is `easyanticheat`. The actual DLL is
`<game>/Data/plugins/easyanticheat/easyanticheat.dll`.

## Common EAC bootstrapper log lines and what they mean

| Log line                                                         | Meaning                                                                                      |
|------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| `Loaded the following settings .json file: 'X:\...Settings.json'`| EAC bootstrapper read its own config successfully.                                           |
| `System name: 'linux64_32'`                                      | EAC detected it's running under Wine/Proton on Linux. Both 32 and 64 bit modules are used.   |
| `Loader component initialized.`                                  | The native .so loaded.                                                                       |
| `Connecting to URL: https://modules-cdn.eac-prod.on.epicgames.com/...` | EAC is contacting Epic's CDN for its module.                                            |
| `Connect result: No error (0) Response Code: 200`                | Network OK, EAC backend reachable.                                                           |
| `Anti-cheat service disabled on backend.`                        | **Server-side** config: the developer has the EAC service disabled for this product/deployment. Not a local problem. |
| `Could not reach the Easy Anti-Cheat CDN, launching with null client, result code: 511.` | The 200 came back but the payload said "no module to load". Result code 511 is the "null client" outcome. |
| `Launcher finished with: 301, 'Easy Anti-Cheat erfolgreich im Spiel geladen'.` | Localized success message (German here). The launcher is HAPPY — the game can proceed.   |
| `Successfully initialized the Easy Anti-Cheat module, waiting for game window to become visible.` | EAC is now monitoring the game process.                                                  |
| `Unlocking the launch lock, allowing next game to launch to take place.` | EAC released its launcher lock so the game can start.                                       |
| `Terminating with: 0.`                                           | Clean EAC exit.                                                                              |

## What "Anti-cheat service disabled on backend" actually means

This is NOT an error. It means the game developer told Epic's EAC
backend to NOT require EAC for this game (at least for this productid
+ sandboxid + deploymentid combination). Reasons:

- Game is in a testing/development phase and EAC is off
- Game is free-to-play and the dev doesn't want to pay for EAC
- The dev is using a different AC for this deployment

The local EAC bootstrapper will still load, the native `.so` will still
inject, but the cheat-detection server-side checks are not happening.
For the player, the experience is identical: the game launches, the
lobby works, the matchmaking works. The only difference is no
server-side cheat detection.

If the game's online services ENFORCE "EAC required to connect" (some
do, most don't), the player will get kicked at lobby/connect time. If
they don't enforce, the game just works.

## "Result code: 511" in the bootstrapper log

Result code 511 means "null client" — EAC started, tried to fetch its
module, got back "disabled", and decided to launch without an active
AC module. The 301 exit code from the launcher ("successfully loaded")
is the OUTER wrap confirming the bootstrapper process itself finished
cleanly. Inner module status (511) is independent.

## Re-running the bootstrapper

If you change `EasyAntiCheat/Settings.json` and want EAC to pick up
the new productid/deploymentid, you need to delete the cached state
under `AppData/Roaming/EasyAntiCheat/<productid>/`. EAC stores a copy
of its last successful bootstrap there and may skip re-fetching.

## EAC runtime injection — what NOT to do

Common mistakes when debugging EAC on Linux:

- Copying `easyanticheat.dll` into the game's directory
  → already there, EAC finds it. Duplicates cause weird load-order bugs.
- Copying `easyanticheat.so` into `drive_c/windows/system32/`
  → not how it works. Proton injects the `.so` from
  `PROTON_EAC_RUNTIME`, not from the prefix.
- Editing the registry to set `HKLM\Software\EasyAntiCheat` paths
  → also not how it works. The runtime injection is environment-driven.
- Disabling EAC by deleting `EasyAntiCheat/Settings.json`
  → the bootstrapper will fail to start, the game will refuse to
  launch. Worse outcome than "disabled on backend".

The cleanest "disable EAC" path: leave the bootstrapper config alone,
set the in-game `anticheat` value to empty or another plugin name. The
bootstrapper still runs, the game still launches, you just don't load
the AC plugin inside the game.
