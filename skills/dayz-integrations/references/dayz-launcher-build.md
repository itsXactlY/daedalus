# DayZ Windows Launcher Build Guide

> Updated 2026-07-28. Covers building a simple Windows .exe launcher for DayZ on a Linux host (C# .NET 10 cross-compile).

## Quick Start

```bash
cd /home/alca/games/DayZ/Launcher_Build
dotnet publish -c Release -r win-x64
# Output: bin/Release/net10.0-windows/win-x64/publish/DayZLauncher.exe
```

## Architecture

- **C# .NET 10** WinExe app (Launcher.cs + Launcher.csproj)
- **Target**: `net10.0-windows` with `EnableWindowsTargeting=true` (required for cross-compile on Linux)
- **Output**: PE32+ x64 exe — a real Windows binary, not a Linux ELF
- **Config**: `config.json` next to the exe (portable, human-readable JSON)

## Config (config.json)

```json
{
  "PlayerName": "Player",
  "ServerHost": "192.168.0.169",
  "ServerPort": "2302",
  "DayzRoot": "C:\\Games\\DayZ",
  "DayzExe": "DayZ_x64.exe",
  "Mods": ["@CF", "@A6", "..."]
}
```

`DayzRoot` is an ABSOLUTE Windows path to your DayZ install directory (where `DayZ_x64.exe` lives). This is REQUIRED — the launcher does NOT derive it from the exe location.

## Usage

| Mode | Command |
|------|---------|
| Launch (uses config.json) | `DayZLauncher.exe` |
| Create config + launch | `DayZLauncher.exe "PlayerName" "server.ip" "2302" "C:\\Games\\DayZ"` |

CLI args (positional): `<playername> <serverhost> <serverport> <dayzroot>`
- Creates or replaces config.json and then launches DayZ.
- `DayzRoot` (4th arg) is required — the launcher exits immediately if `DayzRoot` is empty or not set in config.json.

## Key Design Decisions

1. No registry dependency — config.json next to exe works on any Windows install
2. No Python/bash — native Windows exe, no runtime dependencies beyond what .NET includes
3. `DayzRoot` is explicit in config.json — NOT derived from exe location. This is a critical fix from an earlier broken version that tried `GetParent(exeDir)` which pointed at the build output directory, not the DayZ install folder
4. Mod list stored in config.json as string array — empty by default, user fills in (baked from !START.sh initially)
5. Headless — no Console.ReadKey()/Console.ReadLine()/Console.WriteLine (crashes under Wine, see Pitfall below)
6. UseShellExecute=true for clean process spawn on Windows/Wine
7. `SaveConfig()` is called when CLI args create a fresh config, so the user's settings persist

## Pitfall: Wine + WinExe + Console Input = Crash

Console.ReadKey() / Console.ReadLine() / any Console output inside a WinExe under Wine crashes with an unhandled access violation
in kernelbase → coreclr → System.Console. Wine does not allocate a console handle
for GUI apps by default, so .NET's Console class has no valid handle.

Fix: Make the launcher headless. No interactive prompts at runtime. Config is set via
CLI args or edited manually in config.json. No Console.* calls at all — not even error messages to stderr.

## Pitfall: ENABLE_WINDOWS_TARGETING

When building on Linux for Windows target, MSBuild needs <EnableWindowsTargeting>true</EnableWindowsTargeting> in the .csproj. Without it: NETSDK1100 error.

## Build Command

Use `dotnet publish -r win-x64` NOT `dotnet build` when cross-compiling from Linux. `dotnet build` produces
a Linux ELF binary or IL-only DLL depending on OutputType; `dotnet publish -r win-x64` produces
the real PE32+ Windows executable.

## Source Location

- Source: /home/alca/games/DayZ/Launcher_Build/Launcher.cs
- Project: /home/alca/games/DayZ/Launcher_Build/Launcher.csproj