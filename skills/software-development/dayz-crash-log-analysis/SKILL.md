---
name: dayz-crash-log-analysis
description: Diagnose DayZ crashes from log files by extracting source from deployed PBO binaries and tracing mod call chains.
category: software-development
---

# DayZ Crash Log Analysis

Diagnose DayZ client/server crashes AND server-side failures (loot not spawning,
CE economy init errors, mission failing to load) from `.log` / `.RPT` files,
PBO-deployed mod sources, and Wine/Proton SEH exceptions.

## When to use
- User shares a DayZ crash log with SEH exceptions, stack traces, or access violations
- User reports the server "starts but loot is 0 / client can't connect / mission broken"
- Need to trace a crash through mod chains (VPPAdminTools -> BaseBuildingPlus -> VanillaPPMap etc.)
- Need to find the source line referenced in a crash from a deployed PBO
- Need to debug Central Economy (CE) types.xml / cfgeconomycore.xml / storage_1 loot

## READ THE WHOLE LOG — DO NOT GREP-SNIP
This is the #1 failure mode on this user's DayZ sessions. When the user pastes a
`.RPT` or says "lies das ganze file", they mean it literally:
- `read_file` the full RPT (it can be 12000+ lines / 1.5MB). Grep-only views
  MISS the one line that proves root cause (e.g. `[CE][CoreData] :: 0 root classes`
  or `[CE][TypeSetup] :: 885 classes setuped...` near line 3570, or
  `Player connect enabled` / `Mission geladen` near the end).
- If you already grepped a snippet and the user erupts ("LES DEN GANZEN ERROR!
  ALLES!"), STOP and `read_file` the entire file before another word.
- For CE/loot issues specifically, see `references/dayz-ce-economy-debugging.md` —
  it has the confirmed DayZ 1.28 loader rules and a working-vs-broken diff.

## Workflow

### 1. Parse the crash log
- `Class:` and `Function:` tell you which mod class/method crashed
- Stack trace shows the mod chain (e.g., `VPPAdminTools -> BaseBuildingPlus -> VanillaPPMap`)
- SEH exception code: `0xC0000005` = access violation, `0x80000101` = Wine-translated SIGSEGV

### 2. Find source code -- check in order
1. **Deployed PBO binary** (`/home/alca/games/DayZ/Mods/@<Mod>/addons/*.pbo`) -- the actual running code
2. **Workspace source** (`/home/alca/apogrps/`, `/home/alca/apogrps_qwen/`, `/home/alca/.hermes/your-workspace/apogrps/`) -- may differ from deployed
3. **Temp build output** (`~/.local/share/Steam/steamapps/compatdata/221100/pfx/.../Temp/`) -- intermediate build files

**Important**: Line numbers in crash logs match the DEPLOYED PBO, not workspace source. Always extract from PBO first.

### 3. Extract source from PBO binary
PBOs contain uncompressed script source. Extract with text scanning:

```python
pbo_path = '/home/alca/games/DayZ/Mods/@VanillaPPMap/addons/VanillaPPMap.pbo'
with open(pbo_path, 'rb') as f:
    data = f.read()
# Find class by name
idx = data.find(b'class VPPMapMenu extends')
# Extract until next class or marker
source = data[idx:end].decode('ascii', errors='replace')
```

For finding layout files inside PBOs:
```python
# Layout files are stored as readable text
idx = data.find(b'FrameWidgetClass VPPNoBuildAdminUI')
```

### 4. Understand the call chain
DayZ mod chain: multiple mods override the same methods (MissionGameplay::OnUpdate). The crash shows which mod in the chain was executing. Key patterns:
- `EnterScriptedMenu()` -> engine calls `Init()` on the menu class
- `ShowScriptedMenu()` -> calls `OnShow()`
- `OnUpdate()` runs every frame; if it re-creates menus, Init() can be called from OnUpdate context

### 5. Common crash causes on Linux/Proton
- **0x80000101**: Wine/Proton translated SIGSEGV -- native C++ crash in engine code (widget allocation, D3D calls)
- Complex widget trees in layouts can trigger Proton edge cases
- Clear shader cache: `rm -rf ~/.local/share/Steam/steamapps/shadercache/221100/`
- Check Proton version (Proton-GE handles DayZ UI better)

### 6. Fix approaches
- Add null/layout-exists guards around CreateWidgets calls
- Wrap complex UI initialization in try-catch patterns
- Simplify widget tree depth in .layout files
- Update Proton version or GPU drivers

## File locations
- Client mods: `/home/alca/games/DayZ/Mods/@<Mod>/addons/`
- Workshop PBOs: `~/.local/share/Steam/steamapps/workshop/content/221100/`
- Workspace source: `/home/alca/apogrps/` (main) or `/home/alca/apogrps_qwen/` (Qwen branch)
- Server: `/home/alca/games/DayZ/Server/`
- Proton prefix: `~/.local/share/Steam/steamapps/compatdata/221100/pfx/`

## CE / loot debugging (non-crash server failures)

The dominant DayZ server failure on this host is NOT a crash — it's the Central
Economy failing to load loot. Server boots, client connects, but 0 items spawn
or only vanilla items appear. The confirmed DayZ 1.28 loader rules, symptom→
root-cause table, and the working-vs-broken mission diff that resolved a 2-hour
Apocalyps3nd session are in `references/dayz-ce-economy-debugging.md`. Load it
the moment the user says "loot spawnt nicht" / "NULL LOOT" / "0 root classes".

## Pitfalls
- Multiple copies of source exist with DIFFERENT code (apogrps vs apogrps_qwen vs hermes workspace vs PBO)
- Line numbers in crash logs = deployed PBO source, NOT workspace source
- PBO may contain source that was formatted/changed during packing (different whitespace, removed comments)
- Wine exception codes don't map directly to Windows NTSTATUS codes
- **Grep-snipping the RPT hides the root-cause line. Read the whole file (see top of this skill).**
