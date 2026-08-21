# Dotnet Publish Commands for Windows GUI Launchers

## Standard Self-Contained (Win-x64)
```bash
cd /path/to/project
dotnet publish -c Release -r win-x64 --self-contained true
# Output: bin/Release/net10.0-windows/win-x64/publish/
```

## With Trimming (Smaller Exe, .NET 8+)
```bash
dotnet publish -c Release -r win-x64 --self-contained true \
  -p:PublishTrimmed=true \
  -p:TrimMode=partial \
  -p:SuppressTrimAnalysisWarnings=true
```

## Single-File Bundle (One .exe, .NET 6+)
```bash
dotnet publish -c Release -r win-x64 --self-contained true \
  -p:PublishSingleFile=true \
  -p:IncludeNativeLibrariesForSelfExtract=true \
  -p:EnableCompressionInSingleFile=true
```
⚠️ Single-file extracts to temp on first run — slower startup, but convenient for distribution.

## ReadyToRun (Faster Startup)
```bash
dotnet publish -c Release -r win-x64 --self-contained true \
  -p:PublishReadyToRun=true
```

## Full Optimized (Recommended for Production)
```bash
dotnet publish -c Release -r win-x64 --self-contained true \
  -p:PublishTrimmed=true \
  -p:TrimMode=partial \
  -p:PublishReadyToRun=true \
  -p:PublishSingleFile=false
```

## Cross-Platform Matrix
| Target | RID | Command |
|--------|-----|---------|
| Windows x64 | `win-x64` | `dotnet publish -r win-x64` |
| Windows x86 | `win-x86` | `dotnet publish -r win-x86` |
| Windows ARM64 | `win-arm64` | `dotnet publish -r win-arm64` |
| Linux x64 | `linux-x64` | `dotnet publish -r linux-x64` |
| macOS x64 | `osx-x64` | `dotnet publish -r osx-x64` |
| macOS ARM64 | `osx-arm64` | `dotnet publish -r osx-arm64` |

## Verify Output
```bash
file bin/Release/net10.0-windows/win-x64/publish/Launcher.exe
# → PE32+ executable (GUI) x86-64

ls -la bin/Release/net10.0-windows/win-x64/publish/
# Launcher.exe  Launcher.dll  Launcher.deps.json  Launcher.runtimeconfig.json
```

## Deploy Checklist (Copy to Target Folder)
- [ ] `Launcher.exe`
- [ ] `Launcher.dll`
- [ ] `Launcher.deps.json`
- [ ] `Launcher.runtimeconfig.json`
- [ ] `DayZ_x64.exe` (game executable)
- [ ] `Mods/` folder with all `@ModName` directories
- [ ] `config.json` (optional, auto-created on first save)

## Wine Test
```bash
cd /target/folder
timeout 3 wine Launcher.exe 2>&1
# Expect: fixme:winediag lines only, exit code 0
```