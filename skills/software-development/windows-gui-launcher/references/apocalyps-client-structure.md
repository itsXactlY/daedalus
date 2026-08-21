# Apocalyps Client Structure — Clean Deploy Layout

```
/home/alca/games/Apocalyps/                    # CLEAN CLIENT (deploy this to Windows)
├── DayZ_x64.exe                              # Main executable (SHA512 verified)
├── amd_ags_x64.dll
├── steam_api64.dll
├── steamclient64.dll
├── CrashReporter.exe
├── DayZ_BE.exe
├── DayZDiag_x64.exe
├── Addons/                                   # Vanilla game data
├── BattlEye/                                 # Anti-cheat
├── dta/                                      # Core game data
├── dbg/                                      # Debug symbols
├── nondebug/
├── sakhal/
├── steam_settings/
├── moddata/                                  # ONLY 36 curated client mods
│   ├── @CF
│   ├── @Dabs Framework
│   ├── @Dogtags
│   ├── @CarCover
│   ├── @BodyBags
│   ├── @Code Lock
│   ├── @DrugsPlus
│   ├── @TruckFixV2
│   ├── @MuchCarKey
│   ├── @BuilderItems
│   ├── @MuchFramework
│   ├── @MuchStuffPack
│   ├── @MuchStuffPackFix
│   ├── @VPPAdminTools
│   ├── @Breachingcharge
│   ├── @BaseBuildingPlus
│   ├── @Wilmas BBP Item Drop Fix
│   ├── @Care Packages V2
│   ├── @RaG_Vehicle_Pack
│   ├── @Nehr_Pickup_Lada
│   ├── @VPPNotifications
│   ├── @VirtualGarageFull
│   ├── @MaharlikaPH_Boats
│   ├── @Forward Operator Gear
│   ├── @MMG - Mightys Military Gear
│   ├── @Cl0ud's Military Gear
│   ├── @WindstridesClothingPack
│   ├── @Uncuepas Civilian Clothing
│   ├── @CannabisPlus Experimental
│   ├── @A6
│   ├── @Autostack
│   ├── @Heli
│   ├── @VanillaPPMap
│   ├── @munghard
│   ├── @Inventory Move Sounds
│   ├── @bedrespawn
│   ├── 3649957186                            # Workshop ID (no @ prefix)
│   └── 3649959402
└── (NO launcher files, NO config.json, NO Server/, NO Installer/, NO masterplan/, NO .sh scripts)
```

## Garbage Removed (Intentionally NOT in Apocalyps/)

| Removed | Reason |
|---------|--------|
| `DayZLauncher.*` | Launcher lives at `/games/`, not in game folder |
| `config.json` | Created by launcher at runtime beside launcher exe |
| `dayz.gproj`, `installscript.vdf`, `steam_appid.txt` | Steam/IDE artifacts |
| `windowsdesktop-runtime-*.exe` | Runtime installer (not needed — self-contained deploy or framework-dependent) |
| `launcher.sh`, `!START.sh*` | Linux shell scripts (useless on Windows) |
| `Server/` folder | Dedicated server files — client doesn't need them |
| `Installer/` | Installer artifacts |
| `masterplan/`, `masterplan_out/` | Planning docs |
| `__pycache__/` | Python cache |

## Moddata Folder Rules

1. **Exact match to `ModFolders` array in Launcher.cs** — 36 items, case-sensitive
2. **No server-only mods** — Nothing ending in `_Server`
3. **No deprecated/experimental** — No `@Apocalypse`, `@Apocalypse_Server`, `@AdvancedBanking V2`, etc.
4. **Workshop IDs as-is** — Numeric folders (`3649957186`) copied directly from source Mods/
5. **Case preserved** — `@munghard` (lowercase) matches source, not `@Munghard`

## Build Command (One-Liner)

```bash
cd /home/alca/games/DayZ/Mods && cp -r \
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
  3649957186 3649959402 \
  /home/alca/games/Apocalyps/moddata/
```

## Verify

```bash
# Count must be 36
ls -1 /home/alca/games/Apocalyps/moddata/ | wc -l
# → 36

# Cross-check with launcher source
grep -o '"@[^"]*"' /home/alca/games/Launcher_Build/Launcher.cs | sort | uniq
# Should match exactly the 34 @-prefixed folders above

# Workshop IDs
grep -o '"364995[0-9]*"' /home/alca/games/Launcher_Build/Launcher.cs | sort
# → "3649957186", "3649959402"
```

## Windows Deploy

Copy entire `/home/alca/games/` to Windows:

```
Z:\games\
├── DayZLauncher.exe          # Launcher (with deps)
├── DayZLauncher.dll
├── DayZLauncher.deps.json
├── DayZLauncher.runtimeconfig.json
└── Apocalyps\                # Clean client
    ├── DayZ_x64.exe
    ├── *.dll
    ├── Addons\
    ├── BattlEye\
    ├── dta\
    ├── moddata\              # 36 mods only
    └── ...
```

Run `Z:\games\DayZLauncher.exe` — it resolves `..\Apocalyps\DayZ_x64.exe` and `..\Apocalyps\moddata\` automatically.