# DayZ Launcher - Mod Path Double-Backslash Bug

## Symptom
DayZ shows "Cannot open file" for mod paths like `X:\games\Apocalyps\\moddata\@BuilderItemsPack\data\`.
The double backslash `\\` between `Apocalyps` and `moddata` causes DayZ to fail to open the mod directory.

## Root Cause
The C++ launcher used `snprintf(modsBase, sizeof(modsBase), "%s\\\\%s", launcherDir, MODS_DIR)` in an earlier version.

`GetModuleFileNameA` returns the full path to the EXE including filename.
After `strrchr` strips the filename, `launcherDir` has NO trailing backslash.
The format `%s\\%s` then produced:
- `X:\games\Apocalyps` + `\` + `moddata` 
- BUT the shell-escaped `\\\\` in the format string became `\\` (double backslash) in the output

## Fix
Use `snprintf(modsBase, sizeof(modsBase), "%s\\%s", launcherDir, MODS_DIR)`.
Since `launcherDir` has no trailing backslash and C string escaping turns `\\` into a single `\`, this produces exactly one backslash separator: `X:\games\Apocalyps\moddata`.

## Verification
```
strings Launcher.exe | grep moddata
# Should show single backslash paths in context
```

## Note
The `buildModString()` function also joins `modsBase + "\\" + findData.cFileName` for individual mod subdirectories. This is correct — it produces `X:\games\Apocalyps\moddata\@CF` with single backslashes throughout.