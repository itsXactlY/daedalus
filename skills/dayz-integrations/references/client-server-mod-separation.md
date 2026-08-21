# Client-Server Mod Separation — Clean Client Deploy Pattern

**Purpose:** Deploy a DayZ client with ONLY the mods the launcher actually uses — no server mods, no unused workshop downloads, no garbage.

## The Problem

Typical DayZ mod folders (`/games/DayZ/Mods/`) contain 60+ folders:
- Client mods (needed by launcher)
- Server mods (`*_Server` suffix, `@BreachingChargeCodelocks_Server`, etc.)
- Workshop IDs (numeric folders like `3649957186`)
- Deprecated/experimental mods (`@Apocalypse`, `@Apocalypse_Server`)
- Unused mods from old configurations

Shipping all of this to players wastes bandwidth, disk space, and creates confusion.

## Solution: `moddata/` Folder with Curated Mod List

Create a clean client folder structure:

```
/games/Apocalyps/                 # Clean client deploy
├── DayZ_x64.exe                  # Verified SHA512
├── *.dll                         # Required DLLs
├── Addons/, BattlEye/, dta/, etc. # Vanilla game data
└── moddata/                      # ONLY the 36 mods the launcher uses
    ├── @CF
    ├── @Dabs Framework
    ├── @Dogtags
    ├── ... (36 total)
    └── 3649957186                # Workshop IDs without @ prefix
```

## Single Source of Truth: Launcher's `ModFolders` Array

The C# launcher defines **exactly** which mods are needed:

```csharp
// Launcher.cs — THIS IS THE AUTHORITY
readonly string[] ModFolders = {
    "@CF", "@Dabs Framework", "@Dogtags", "@CarCover", "@BodyBags",
    "@Code Lock", "@DrugsPlus", "@TruckFixV2", "@MuchCarKey",
    "@BuilderItems", "@MuchFramework", "@MuchStuffPack", "@MuchStuffPackFix",
    "@VPPAdminTools", "@Breachingcharge", "@BaseBuildingPlus",
    "@Wilmas BBP Item Drop Fix", "@Care Packages V2", "@RaG_Vehicle_Pack",
    "@Nehr_Pickup_Lada", "@VPPNotifications", "@VirtualGarageFull",
    "@MaharlikaPH_Boats", "@Forward Operator Gear", "@MMG - Mightys Military Gear",
    "@Cl0ud's Military Gear", "@WindstridesClothingPack",
    "@Uncuepas Civilian Clothing", "@CannabisPlus Experimental", "@A6",
    "@Autostack", "@Heli", "@VanillaPPMap", "@munghard",
    "@Inventory Move Sounds", "@bedrespawn", "3649957186", "3649959402"
};
```

**If it's not in this array, it doesn't ship.** No exceptions.

## Build Script (One-Time, Run on Linux Build Machine)

```bash
#!/bin/bash
# build_apocalyps_client.sh — run from /games/DayZ/

APOCALYPS="/home/alca/games/Apocalyps"
MODDATA="$APOCALYPS/moddata"
SOURCE_MODS="/home/alca/games/DayZ/Mods"

mkdir -p "$MODDATA"

# Copy clean vanilla client (DayZ install without mods)
rsync -a --exclude='Mods' --exclude='Server' --exclude='Installer' \
  --exclude='masterplan*' --exclude='Launcher_Build' \
  --exclude='__pycache__' --exclude='*.sh' --exclude='*.bak' \
  --exclude='!START.sh*' --exclude='windowsdesktop-runtime-*.exe' \
  --exclude='config.json' --exclude='DayZLauncher.*' \
  /home/alca/games/DayZ/Client/ "$APOCALYPS/"

# Remove launcher artifacts copied from Client/
rm -f "$APOCALYPS/DayZLauncher."*
rm -f "$APOCALYPS/dayz.gproj" "$APOCALYPS/installscript.vdf"
rm -f "$APOCALYPS/steam_appid.txt" "$APOCALYPS/windowsdesktop-runtime-*.exe"

# Copy ONLY the curated mods from source Mods/
cd "$SOURCE_MODS"
cp -r \
  "@CF" "@Dabs Framework" "@Dogtags" "@CarCover" "@BodyBags" \
  "@Code Lock" "@DrugsPlus" "@TruckFixV2" "@MuchCarKey" \
  "@BuilderItems" "@MuchFramework" "@MuchStuffPack" "@MuchStuffPackFix" \
  "@VPPAdminTools" "@Breachingcharge" "@BaseBuildingPlus" \
  "@Wilmas BBP Item Drop Fix" "@Care Packages V2" "@RaG_Vehicle_Pack" \
  "@Nehr_Pickup_Lada" "@VPPNotifications" "@VirtualGarageFull" \
  "@MaharlikaPH_Boats" "@Forward Operator Gear" "@MMG - Mightys Military Gear" \
  "@Cl0ud's Military Gear" "@WindstridesClothingPack" \
  "@Uncuepas Civilian Clothing" "@CannabisPlus Experimental" "@A6" \
  "@Autostack" "@Heli" "@VanillaPPMap" "@munghard" \
  "@Inventory Move Sounds" "@bedrespawn" \
  "3649957186" "3649959402" \
  "$MODDATA/"
```

## Launcher Path Resolution

Launcher at `/games/DayZLauncher.exe` finds game and mods via relative paths:

```csharp
readonly string DayzExe = Path.GetFullPath(Path.Combine(
    AppDomain.CurrentDomain.BaseDirectory, @"..\Apocalyps\DayZ_x64.exe"));

readonly string ModsBase = Path.GetFullPath(Path.Combine(
    AppDomain.CurrentDomain.BaseDirectory, @"..\Apocalyps\moddata"));

// Build -mod= string with FULL PATHS
var modPaths = new List<string>();
foreach (string folder in ModFolders)
{
    string fullPath = Path.Combine(ModsBase, folder);
    if (Directory.Exists(fullPath) || File.Exists(fullPath))
        modPaths.Add(fullPath);
}
string modString = string.Join(";", modPaths);
// Result: -mod="Z:\games\Apocalyps\moddata\@CF;Z:\games\Apocalyps\moddata\@Dabs Framework;..."
```

## Mod Classification Rules

| Mod Pattern | Goes to `moddata/` | Notes |
|-------------|-------------------|-------|
| `@Name` (in `ModFolders`) | ✅ YES | Client mod used by launcher |
| `@Name_Server` | ❌ NO | Server-only, never client |
| `@Name` (NOT in `ModFolders`) | ❌ NO | Unused/old/deprecated |
| `1234567890` (workshop ID, in `ModFolders`) | ✅ YES | Numeric folder = workshop mod |
| `1234567890` (workshop ID, NOT in `ModFolders`) | ❌ NO | Unused workshop download |

## Verification Checklist

Before zipping `/games/Apocalyps/` for Windows deploy:

- [ ] `moddata/` contains exactly 36 items (count: `ls -1 moddata/ | wc -l`)
- [ ] Every item in `moddata/` appears in `Launcher.cs ModFolders` array
- [ ] Every item in `ModFolders` array exists in `moddata/` (case-sensitive match)
- [ ] No `*_Server` folders in `moddata/`
- [ ] No `@Apocalypse`, `@Apocalypse_Server` in `moddata/`
- [ ] `DayZ_x64.exe` SHA512 matches launcher's `ExpectedSha512` constant
- [ ] `DayZLauncher.exe` + deps in `/games/` (beside `Apocalyps/`)
- [ ] Total folder size reasonable (< 20 GB for typical mod set)

## Why This Works

1. **Launcher = Authority** — Mod list lives in compiled code, not a loose config file players can edit
2. **Build = Filter** — Build script copies ONLY what's in the array
3. **Deploy = Clean** — Windows gets a folder with zero ambiguity
4. **Integrity = Verified** — SHA512 check ensures exe wasn't corrupted in transit
5. **Portable** — Relative paths (`..\Apocalyps\`) mean the whole `games/` folder works anywhere on Windows

## Related

- `references/apocalyps-client-structure.md` — Full folder layout and garbage removal list
- `references/apocalyps-launcher-external.cs` — Complete launcher source with external game/moddata paths
- `references/dayz-launcher-build.md` — Build and Wine test commands