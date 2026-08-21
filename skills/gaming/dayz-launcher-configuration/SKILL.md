---
name: dayz-launcher-configuration
description: "Fix DayZ launcher server connection, exename, and mod path issues"
trigger: "DayZ launcher not connecting to playtest.mazemaker.online or mods not loading or exe not found"
---

## When to use

Use this skill when the DayZ launcher fails to connect to the playtest server or mods are not being picked up from the moddata/ folder. This covers:
- Launcher connecting to localhost instead of playtest.mazemaker.online
- Missing ServerHost/ServerPort in config.json
- Mod paths with double backslashes causing DayZ to fail opening files
- Choosing between C# .NET launcher vs native C++ launcher
- Launcher fails to find DayZ executable (wrong DAYZ_EXE_NAME)
- Mods not auto-discovered from moddata/ subfolder

## Steps

1. Check config.json in both `/home/alca/games/Apocalyps/config.json` and `/home/alca/games/DayZ/Client/config.json` for `ServerHost` and `ServerPort` keys. If missing, add `"ServerHost": "playtest.mazemaker.online"` and `"ServerPort": "2302"`. **Note**: the launcher's `saveConfig()` only writes `PlayerName` — it does NOT preserve ServerHost/ServerPort. These must be set manually after first launch, or set the launcher to hardcode them (which it does).
2. Build the C++ launcher from source:
   ```
   cd /home/alca/games/Launcher_Build
   x86_64-w64-mingw32-g++ -o launcher.exe launcher.cpp -mwindows -static -static-libgcc -static-libstdc++ -lkernel32 -luser32 -lshell32 -lshlwapi
   ```
   Source is 144 lines at `/home/alca/games/Launcher_Build/launcher.cpp`.
3. Deploy to the directory with `moddata/` (Apocalyps/):
   ```
   cp launcher.exe /home/alca/games/Apocalyps/Launcher.exe
   ln -sf /home/alca/games/Apocalyps/Launcher.exe /home/alca/games/DayZ/Client/launcher.exe
   ```
   The DayZ/Client/ launcher.sh points at this symlink. The Apocalyps/ launcher.sh points directly at Launcher.exe. Both resolve through Proton.
4. Verify binary strings: `strings /home/alca/games/Apocalyps/Launcher.exe | grep -E "DayZ_x64|playtest\.mazemaker|2302|moddata"`
5. Reboot DayZ on Windows.

## Pitfalls

- **DO NOT use the C# .NET launcher** (`DayZLauncher.exe` from `Launcher_Build/` built with `dotnet publish`). It requires Wine/.NET runtime and has had multiple issues. The C++ launcher is native Windows, no Wine needed. This is explicitly the user's preference ("C# IS OBSOLETE FFS").
- **DAYZ_EXE_NAME must be `DayZ_x64.exe`** — this is the exe in DayZ/Client/ AND the renamed copy in Apocalyps/ (both are identical, 17MB). Do NOT use `playtest.exe` as the exe name. The C++ launcher hardcodes `DayZ_x64.exe` as the exe to launch.
- **Launcher must live where `moddata/` exists.** It uses `GetModuleFileNameA` + `strrchr` to find its own dir, then appends `\moddata`. Deploying to DayZ/Client/ without a `moddata/` there means no mods are auto-discovered. The primary install for mods is `Apocalyps/moddata/`. Deploy to Apocalyps/ as Launcher.exe and symlink to DayZ/Client/launcher.exe.
- **Mod path must use single backslashes.**
- **Do NOT use double backslashes** in the mod path format string — DayZ on Windows cannot parse `\\` separators in the `-mod=` argument and will crash with "Cannot open file" for any mod.
- **Mod scanning** uses `FindFirstFileA`/`FindNextFileA` on the `moddata/` subdir to enumerate subdirectories and build a semicolon-delimited Windows path string for the `-mod=` flag. Each mod folder in `moddata/` is automatically discovered and included.
- **Old layout**: the C# launcher was at `Launcher_Build/Launcher.cs` (162K). This is deprecated. The working launcher is the C++ binary at `Apocalyps/Launcher.exe` — a 144-line source file that compiles to a minimal ~280KB PE32+ x86-64 binary.
The C++ launcher has a simple Win32 dialog with a Player Name input field and a PLAY button. No config.json reading at launch time — the server and exe name are hardcoded in the source.

## Reference
See `references/mod-path-double-backslash.md` for the detailed bug analysis of the double-backslash mod path issue.

## DayZ Launcher Rebuild (C++ Native)

The DayZ launcher on Linux must be a **C++ native Windows binary** compiled with mingw, NOT a C#/.NET build. The .NET launcher requires Wine/.NET runtime and has had multiple issues.

### Build command
```
cd /home/alca/games/Launcher_Build
x86_64-w64-mingw32-g++ -o launcher.exe launcher.cpp -mwindows -static -static-libgcc -static-libstdc++ -lkernel32 -luser32 -lshell32 -lshlwapi
```

### Deploy
Copy to the DayZ install directory that contains `moddata/`:
```
cp launcher.exe /home/alca/games/Apocalyps/Launcher.exe
ln -sf /home/alca/games/Apocalyps/Launcher.exe /home/alca/games/DayZ/Client/launcher.exe
```
The launcher resolves mods relative to its own directory via `GetModuleFileNameA` + `moddata/` subfolder. So it must live where `moddata/` exists.

### Verify
```
strings launcher.exe | grep -E "DayZ_x64|playtest\.mazemaker|2302|moddata"
```
Must show: `playtest.mazemaker.online`, `DayZ_x64.exe`, `moddata`, and correct `-connect` / `-port` / `-name` args.

### Pitfall: C# .NET launcher is dead
`Launcher.cs` in Launcher_Build/ used to point at `..\Apocalyps\playtest.exe` (wrong exe name — does not exist) and had a SHA512 placeholder `SET_AFTER_COMPUTE`. Do not use the .NET path. Use the C++ native launcher.

## Related skills
- `dayz-integrations` — for general DayZ mod development, server setup, and crash analysis
- `enforce-script-syntax` — for EnforceScript-specific rules