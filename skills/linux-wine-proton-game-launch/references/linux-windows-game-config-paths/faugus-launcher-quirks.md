# Faugus-launcher quirks

Faugus-launcher is a Linux launcher that runs Windows games under
Proton/UMU with managed Wine prefixes per profile. It is one of the most
common setups for running non-Steam Windows games on Linux.

## Prefix layout

```
~/Faugus/                              # Faugus home
└── default/                           # default profile
    ├── .faugus.lock                   # per-profile lock
    ├── pfx.lock                       # active Wine prefix lock
    ├── tracked_files                  # paths Faugus considers "managed"
    ├── .update-timestamp              # last Faugus self-update
    ├── config_info                    # profile config snapshot
    ├── version                        # Faugus version
    ├── system.reg                     # Wine registry
    ├── user.reg                       # Wine registry
    ├── userdef.reg                    # user-defined registry tweaks
    └── drive_c/                       # the Wine C:\ drive
        ├── users/steamuser/
        │   ├── Documents/
        │   ├── AppData/
        │   │   ├── Local/
        │   │   ├── LocalLow/
        │   │   └── Roaming/
        │   ├── Desktop/
        │   └── ... (full Windows user profile skeleton)
        ├── Program Files/
        ├── Program Files (x86)/
        ├── ProgramData/
        └── windows/                    # Wine-internal Windows install
```

The default Wine user is `steamuser`, not your Linux username. So
`<prefix>/drive_c/users/steamuser/...` is where game configs and saves live
for almost all Faugus games.

## Environment Faugus exports

When you run a game via Faugus, these are set (verifiable with
`faugus-launcher --help` or by inspecting `/proc/<pid>/environ`):

```
WINEPREFIX=/home/<user>/Faugus/default
PROTONPATH=Proton-CachyOS Latest
PROTON_EAC_RUNTIME=/home/<user>/.config/faugus-launcher/components/eac
PROTON_BATTLEYE_RUNTIME=/home/<user>/.config/faugus-launcher/components/be
PROTONFIXES_DISABLE=1
```

`PROTON_EAC_RUNTIME` and `PROTON_BATTLEYE_RUNTIME` point at the Faugus
component directories where the native Linux `.so` files for Easy
Anti-Cheat and BattlEye live. Faugus mounts these into the prefix
automatically; you do not need to copy `.so` files into
`drive_c/windows/system32/`.

## EAC component

Faugus bundles the EAC runtime in two versions: v1 (legacy) and v2
(current). v2 is what most modern games use.

```
~/.config/faugus-launcher/components/eac/
└── v2/
    ├── lib64/
    │   ├── easyanticheat.so            # Linux native
    │   ├── easyanticheat.dll           # Windows DLL
    │   ├── easyanticheat_x64.so
    │   └── easyanticheat_x64.dll
    └── lib32/
        ├── easyanticheat_x86.so
        └── easyanticheat_x86.dll
```

## `tracked_files`

`~/Faugus/default/tracked_files` lists paths Faugus considers "managed"
in the prefix. Files outside this list may be ignored or overwritten on
the next Faugus sync. If your game config keeps reverting, check whether
the file is in `tracked_files`. If it's not, you have two options:

1. Move the config to a path Faugus tracks.
2. Add it to `tracked_files` (one path per line).

## The Documents path inside Faugus

The game's view of "Documents" is
`<prefix>/drive_c/users/steamuser/Documents/`. On the host filesystem this
is at `/home/<user>/Faugus/default/drive_c/users/steamuser/Documents/`.

`/home/<user>/Dokumente/` (German Linux `~/Documents`) is a HOST-SIDE
folder. The game does NOT read from it. A file that exists in both is
NOT a symlink — they are two independent files. If you edit the host
side, nothing happens in-game.

## What Faugus manages vs. what it doesn't

Faugus manages:
- The prefix structure (`drive_c/`, registry)
- EAC and BattlEye runtime injection
- Proton version selection
- Some launcher integration

Faugus does NOT manage:
- The game's INI / settings files inside the prefix
- Game saves
- The game's own EAC bootstrapper config
  (`<Game>/Data/EasyAntiCheat/Settings.json`)

So the EAC `Settings.json` (the one with `productid`, `sandboxid`, etc.)
is under the game's own data directory inside the prefix and is the
GAME DEVELOPER's configuration, not Faugus's. The user does not normally
edit it — but if the developer shipped a stale one, that's where you'd
look.

## Reset behavior

`faugus-launcher --reset` (or the GUI's reset button) WIPES
`~/Faugus/default/drive_c/`. Anything in there that's not under
`tracked_files` and not in the game install gets deleted. Back up:

- `<prefix>/drive_c/users/steamuser/Documents/<GameName>/`
- `<prefix>/drive_c/users/steamuser/AppData/Roaming/<GameName>/`
- `<prefix>/drive_c/users/steamuser/AppData/Roaming/EasyAntiCheat/`
  (this regenerates from productid on next run, so usually safe to wipe)
