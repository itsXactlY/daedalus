---
name: windows-gui-launcher
category: software-development
description: Build native Windows GUI launchers (WinForms/WPF) from Linux using .NET cross-compilation, with integrity verification, config persistence, and Wine testing.
---

# Windows GUI Launcher Development

Build native Windows GUI launchers (WinForms/WPF) from Linux using .NET cross-compilation, with integrity verification, config persistence, and Wine testing.

## Trigger Conditions
- Need a Windows `.exe` GUI (not console) for game/app launching
- Building on Linux, targeting Windows (cross-compile)
- Require file integrity checks (SHA256/SHA512) before launch
- Need persistent config (player name, server, settings) saved beside exe
- Want to test under Wine before Windows deployment

## Core Pattern

### 1. Project Setup (WinExe, .NET 10+)
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net10.0-windows</TargetFramework>
    <UseWindowsForms>true</UseWindowsForms>
    <EnableWindowsTargeting>true</EnableWindowsTargeting>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
```
- `WinExe` = no console window on Windows
- `EnableWindowsTargeting` = cross-compile from Linux
- `UseWindowsForms` = WinForms GUI (simpler deps than WPF)

### 2. SHA512 Integrity Check (Non-Negotiable)
```csharp
const string ExpectedHash = "51c49fb7e2f0cb2fd93821684c27bc8dcea29498c5b9740ed1105ed1ebb1c319c13e795b384c3ea91f483ff89da9e588cb1e07bc6666628d74b0f6be7dc9cdc1";

static bool VerifySha512(string path, string expected)
{
    using var sha = SHA512.Create();
    using var fs = File.OpenRead(path);
    var hash = Convert.ToHexString(sha.ComputeHash(fs)).ToLowerInvariant();
    return hash == expected.ToLowerInvariant();
}
```
- Hardcode expected hash as `const string` (not config) — integrity is non-negotiable
- Fail launch with clear message if mismatch

### 3. Config Persistence (JSON beside exe)
```csharp
static string ConfigPath => Path.Combine(
    AppContext.BaseDirectory, "config.json");

class Config { public string PlayerName = ""; public string ServerHost = "playtest.mazemaker.online"; public int ServerPort = 2302; }

void Load() { if (File.Exists(ConfigPath)) config = JsonSerializer.Deserialize<Config>(File.ReadAllText(ConfigPath)) ?? new Config(); }
void Save() { File.WriteAllText(ConfigPath, JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true })); }
```
- `AppContext.BaseDirectory` = folder containing the running exe
- Auto-create on first save, load on startup
- Write ALL keys the launcher reads — do NOT omit keys just because they are hardcoded in source; the launcher reads more than the GUI shows

### 4. Launch Target Process (UseShellExecute)
```csharp
var psi = new ProcessStartInfo
{
    FileName = "DayZ_x64.exe",
    Arguments = $"-connect={host} -port={port} -name=\"{name}\" -mod=@mod1;@mod2;...",
    WorkingDirectory = dayzRoot,
    UseShellExecute = true  // Critical: respects file associations, elevation, Wine
};
Process.Start(psi);
```
- `UseShellExecute = true` works correctly under Wine
- Quote player name (spaces in names)
- Mod list as semicolon-separated `-mod=@a;@b;@c`
- Launcher exits after spawn (fire-and-forget)

### 5. Build & Deploy (Self-Contained)
```bash
cd /path/to/project
dotnet publish -c Release -r win-x64 --self-contained true
# Output: bin/Release/net10.0-windows/win-x64/publish/
# Copy exe + .dll + .deps.json + .runtimeconfig.json to target folder
```

### 6. Wine Test (Smoke Test)
```bash
cd /target/folder
timeout 3 wine Launcher.exe 2>&1
# Expect: fixme:winediag lines only, exit code 0
# No Console.ReadKey/ReadLine/WriteLine in WinExe — crashes Wine
```

## Config Must Include All Fields (Lesson DayZ)
The Windows launcher reads config.json at launch time — if a field the launcher needs is **missing**, it **does not fail loudly**. Instead it silently falls back to a wrong default (localhost / 127.0.0.1). This is a **first-class deployment pitfall**:

| Mistake | Symptom | Fix |
|---------|---------|-----|
| config.json missing ServerHost/ServerPort | Launcher uses last default (localhost), never connects | Always write ALL fields in config.json — never remove keys even if they are hardcoded in the launcher source. The JSON schema must contain them explicitly. |
| Old launcher version deployed alongside new config | Mismatch between launcher binary and config shape | Delete old launcher before deploying new one; or make launcher refuse to start if config schema is wrong |

**Rule:** `config.json` written by the builder must contain every key the launcher reads. A "minimal" config with only user-editable keys is a bug — the launcher reads more than the GUI shows.

## C++ Alternative
.NET C# launchers from Linux are fragile for Windows deployment (Wine dependency, .NET runtime requirement, single-file publish trimming issues). For simple game launchers, a **native C++ Win32 GUI** built with MinGW (`x86_64-w64-mingw32-g++`) is a viable alternative:

```bash
x86_64-w64-mingw32-g++ -o Launcher.exe launcher.cpp \
  -mwindows -static -static-libgcc -static-libstdc++ \
  -lkernel32 -luser32 -lshell32 -lshlwapi
```

- Statically linked → no DLL dependencies beside Windows system DLLs
- Single PE32+ exe, 12MB with CRT included
- No .NET runtime needed on target Windows
- Uses Win32 `DialogBoxParam` for simple forms — no external UI framework
- Path manipulation uses manual `strrchr` + null-termination instead of `PathRemoveFileSpecA` (which may not link without `-lshlwapi`)

Pitfall: `PathRemoveFileSpecA` / `PathAppendA` require `shlwapi.lib` — either link `-lshlwapi` or implement manually with `strrchr`. Manual implementation is more portable.

## Pitfalls
| Issue | Cause | Fix |
|-------|-------|-----|
| Wine crash on startup | `Console.*` calls in WinExe | Remove ALL Console I/O; use MessageBox or status label |
| Nullable warning CS8622 | `EventHandler` expects `object? sender` | Add `#nullable disable` on handler or use `object? sender` |
| SHA512 mismatch | Wrong hash or modified exe | Recompute with `sha512sum DayZ_x64.exe` and update const |
| Config not saving | Writing to install dir (no perms) | Use `AppContext.BaseDirectory` (user-writable beside exe) |
| Mods not loading | Wrong `-mod` format | Semicolon-separated, `@` prefix per mod folder name |
| Launcher hangs | `Process.WaitForExit()` | Fire-and-forget; launcher closes after `Process.Start()` |
| Self-contained single-file publish fails | WinForms trimming unsupported | Use framework-dependent (`--self-contained false`) or skip `-p:PublishSingleFile=true` |
| Placeholder text submits as real name | "John Doe" stays in textbox | Clear on Enter/focus, restore on Leave if empty; validate & reject blocked names |
| Config saves blocked name | Save runs before validation | Only call `SaveConfig()` after successful validation |

## Verification Checklist
- [ ] `file Launcher.exe` → `PE32+ executable (GUI) x86-64`
- [ ] `sha512sum DayZ_x64.exe` matches hardcoded const
- [ ] `wine Launcher.exe` → opens GUI, no crash, exit code 0
- [ ] Enter name → Save → Config.json created beside exe
- [ ] Click CONNECT → DayZ launches with correct args (verify in DayZ logs)
- [ ] Launcher exits cleanly after spawn

## References
- `references/dayz-launcher-example.cs` — Complete DayZ launcher source (C# version, legacy)
- `references/launcher.cpp` — C++ native MinGW Win32 GUI launcher (no .NET dependency)
- `references/placeholder-validation-pattern.cs` — Placeholder text behavior + blocked-name validation (John Doe / player)
- `references/launcher.csproj` — Minimal WinExe csproj with Nullable/WindowsTargeting
- `references/build-commands.md` — Dotnet publish commands for common targets
- `references/wine-testing.md` — Wine smoke test patterns for WinExe