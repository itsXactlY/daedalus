# DayZ Launcher in C++ (Native Windows, MinGW)

Minimal Win32 GUI launcher for DayZ built on Linux with MinGW. No .NET runtime dependency.

## Build
x86_64-w64-mingw32-g++ -o Launcher.exe launcher.cpp -mwindows -static -static-libgcc -static-libstdc++ -lkernel32 -luser32 -lshell32 -lshlwapi

## Key Design Decisions
- SERVER_HOST and SERVER_PORT are hardcoded #define constants — not editable in GUI, not in config.json
- Server label shows playtest.mazemaker.online:2302 (hardcoded, matches server DNS)
- Only user-editable field: Player Name (saved to config.json)
- Uses ShellExecuteExA to launch playtest.exe with -connect, -port, -name, -mod args
- Working directory set to dayz.exe's parent so relative mod paths resolve
- PathRemoveFileSpecA used for directory stripping — requires -lshlwapi link flag
- Falls back to manual strrchr implementation if shlwapi not available

## Lessons from DayZ Session (2026-07-29)
- C# .NET launcher with partial config.json (missing ServerHost/ServerPort keys) silently defaults to localhost → never connects
- config.json MUST contain every key the launcher reads, not just user-editable ones
- Native C++ launcher avoids Wine/.NET issues entirely