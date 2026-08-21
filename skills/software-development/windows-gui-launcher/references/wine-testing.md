# Wine Testing for WinExe GUI Launchers

## Why Wine Test?
- Validates GUI launches cleanly on Linux before Windows deploy
- Catches `Console.*` crashes (Wine doesn't support console in WinExe)
- Verifies `UseShellExecute=true` works for process spawning

## Smoke Test (CI-Friendly)
```bash
cd /deploy/folder
timeout 5 wine Launcher.exe 2>&1 || true
```
- Exit 0 = GUI staged successfully (Wine created window)
- `timeout` prevents hang on modal dialogs
- Output shows `fixme:winediag` (harmless Wine diagnostics)

## Interactive Test (Manual)
```bash
wine Launcher.exe
# Opens actual window — click, type, test
```

## Headless CI (Xvfb)
```bash
xvfb-run -a timeout 10 wine Launcher.exe 2>&1
```

## Common Failures & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Crash on startup | `Console.ReadKey/ReadLine/WriteLine` in WinExe | **Remove ALL Console.* calls** — use `MessageBox`, `Label`, `TextBox` |
| "mscoree.dll not found" | Not self-contained | Use `--self-contained true` in publish |
| Process.Start fails | `UseShellExecute = false` (default) | Set `UseShellExecute = true` |
| File dialogs crash | Wine missing file dialog impl | `winetricks comdlg32` or use `OpenFileDialog` fallback |
| High DPI blurry | DPI awareness missing | `<ApplicationManifest>` or `Application.SetHighDpiMode` |

## DayZ Launcher Specific Test
```bash
cd /home/alca/games/DayZ/Client
timeout 3 wine DayZLauncher.exe 2>&1
# Expected: fixme:winediag lines only, exit code 0
# If crash: check for any Console.* in source
```

## Debug Wine Output
```bash
WINEDEBUG=+all wine Launcher.exe 2>&1 | head -100
# Filter: WINEDEBUG=+winforms,+shell,+process
```

## Wine Version Notes
- Wine 8.0+ / Wine-Staging 8+ recommended
- WinForms largely functional; WPF needs more work
- `winetricks dotnet48` only needed for framework-dependent (not self-contained)