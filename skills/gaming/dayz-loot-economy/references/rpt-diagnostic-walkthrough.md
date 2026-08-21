# DayZ Server RPT — Full Diagnostic Walkthrough (proven, 2026-07-18)

When the server boots but loot is empty / client cannot connect, the server RPT
(`Server/profile/DayZServer_x64_*.RPT`, newest first via `ls -lt`) is the ONLY
source of truth. Read it END TO END — do not grep-excerpt. This is the walkthrough
of a real failing run and the exact lines that revealed the root cause.

## The file is LARGE (1.5 MB, ~13k lines) — read in chunks

```
ls -lt /home/alca/games/DayZ/Server/profile/*.RPT | head -1   # newest
# read_file offset=1 limit=500        # head (mod load, config warnings)
# search_files pattern='\[CE\]|ZERO root|classes setuped|Player connect enabled|will be ignored'
#   -> gives line numbers of the CE-Init block
# read_file offset=<CE-block-start> limit=320   # READ THE FULL BLOCK
# read_file offset=<file-end-300> limit=300     # tail (mission init, connect result)
```

## What each CE-Init line means (real example, broken run)

```
3571| [CE][Hive] :: Initializing OFFLINE
3574| [CE][CoreData] :: 0 root classes, 0 defaults, 0 updaters...   # <-- ROOT CAUSE
3575| !!! [CE][CoreData] :: ZERO root classes - SPAWN WILL NOT WORK
3614| [CE][TypeSetup] :: 0 classes setuped...                         # 0 = types.xml NOT loaded
3616| [CE][RegisterConfig] :: 1 config classes registered
3630| !!! [CE][LoadPrototype] 327 Errors during XML parse...
3667| [CE][offlineDB] :: Loaded 2 dynamic events 0 total types.
3668| Type 'A6_AR15_Carbine' will be ignored. (Type does not exist)  # symptom, NOT cause
```

The `0 root classes` at line 3574 is the smoking gun. Everything after it
(885 classes, Type does not exist, NULL loot) is a CONSEQUENCE. Fixating on
line 3668 ("Type does not exist") wasted the whole session — those warnings are
because 0 types loaded, not because the types are missing.

## The TWO fixes that actually worked (in order)

1. **cfgeconomycore.xml format** (`db/ce/cfgeconomycore.xml` — DayZ reads THIS first):
   Broken: `<economy><rootclasses><class .../></rootclasses>`
   Correct: `<economycore><classes><rootclass name="..."/></classes><defaults>...</defaults>`
   After fix: `8 root classes, 18 defaults` (not 0).

2. **File location** — types.xml / events.xml / messages.xml / globals.xml / economy.xml
   MUST be in the MISSION ROOT, not `db/`. After copying db/types.xml -> ./types.xml:
   `[CE][TypeSetup] :: 5252 classes setuped...` (not 885, not 0).

## Success signature (expect after both fixes)

```
[CE][CoreData] :: 8 root classes, 18 defaults, 0 updaters...
[CE][TypeSetup] :: 5252 classes setuped...
[CE][offlineDB] :: Loaded 2 dynamic events N total types.   # N > 0
[DynEvent] "APX_WeaponCache" setup OK                       # NOT "setup is invalid"
...
Player connect enabled
Mission geladen.
```

If `Player connect enabled` / `Mission geladen` are ABSENT, the server is still
hanging in mission init (CE died) — client cannot connect until those appear.

## Red herrings that burned turns (do NOT chase)

- `Type 'X' does not exist` for mods not in the active MOD_LIST → harmless.
- `events.bin` / `types.bin` cache shadow → secondary; only relevant AFTER
  root-class + location are fixed and loot is STILL wrong.
- `<files>` tag in cfgeconomycore.xml → dead end; DayZ auto-loads from root.
- `DEBUG_TEST_USAGE` Unknown → from another mod's injected types; harmless.
- env/ XML missing (`wendigo_territories_chernarus.xml` etc.) → logged, no crash,
  no loot impact (those creatures just don't spawn).
