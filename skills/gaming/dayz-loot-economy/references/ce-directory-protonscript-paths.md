# The `ce/` Directory Location Trap (Linux → Proton path mapping)

## The symptom

Server boots, CE init runs (`[CE][Hive] :: Initializing OFFLINE` → `Init sequence finished` → `Player connect enabled`), player connects, but the MAP HAS ZERO LOOT. No crash, no obvious error — just empty.

The RPT shows only:
```
[CE][TypeSetup] :: 885 classes setuped...
[CE][Storage] Restoring file "...storage_1\data\types.bin".
```
`grep -c "types.xml" Server/profile/*.RPT` returns **0** — DayZ never even attempted to open a types.xml.

`885 classes` = the DayZ-internal item C++ classes (ItemBase, Weapon_Base, …). The 5252 Mod `<type>` entries in `db/types.xml` never entered the economy. So nothing spawns.

## Why it happens on this host

DayZ under Proton maps Windows paths through the `Z:` drive. The engine resolves CE config paths as:
```
DZ\worlds\chernarusplus\ce\types\types.xml   →  <mission>/ce/types/types.xml
DZ\worlds\chernarusplus\ce\env\*.xml          →  <mission>/ce/env/*.xml
```
It looks in the **mission-root `ce/`** directory. It does NOT scan `db/`.

If the configs were placed in `db/` (or `db/ce/`) — which is where many hand-built / copied missions put them — DayZ never finds them. The earlier error `File "DZ\worlds\chernarusplus\ce\env/wendigo_territories_chernarus.xml" does not exist` was the SAME class of bug: the `env/` XMLs were in `db/ce/env/` or missing, not in `ce/env/`.

This is a PATH-RESOLUTION problem, not a content problem. The `types.xml` can be 100% valid (5252 types, all `nominal>0`, 15177 `<usage>` flags) and it still won't load if it's in the wrong directory.

## The correct layout

```
dayzOffline.chernarusplus/
├── ce/
│   ├── types/
│   │   ├── types.xml                 ← MASTER types (5252 entries)
│   │   ├── A6_Ammo.xml               ← per-mod FRAGMENTS (merged as siblings)
│   │   ├── A6_Assault_Rifle.xml
│   │   └── ...
│   ├── spawnabletypes/
│   │   └── cfgspawnabletypes.xml
│   ├── env/
│   │   ├── cattle_territories.xml
│   │   ├── randomized_aj_creatures.xml
│   │   └── ...
│   ├── events.xml
│   └── cfgeconomycore.xml
├── db/
│   ├── types.xml                     ← COPY SOURCE (if present here, it's wrong location)
│   ├── events.xml
│   └── ...
└── storage_1/                        ← runtime cache (types.bin etc.)
```

`ce/types/` may ALREADY contain per-mod fragment files (`A6_*.xml`). Those are additional type defs DayZ merges. The MASTER `types.xml` belongs in `ce/types/types.xml`; the fragments stay as siblings. Do not delete the fragments.

## Verification before fixing (do not guess)

```bash
M=/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus
ls "$M/ce/types/types.xml" 2>/dev/null || echo "MISSING: ce/types/types.xml"
find "$M" -name types.xml          # reveals db/types.xml but NOT ce/types/types.xml
find "$M" -maxdepth 2 -type d -name ce   # shows both db/ce AND root ce/
```

## Fix (reversible — copy, keep originals until verified)

```bash
M=/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus
cp "$M/db/types.xml"              "$M/ce/types/types.xml"
cp "$M/db/cfgspawnabletypes.xml" "$M/ce/spawnabletypes/cfgspawnabletypes.xml"
cp "$M/db/events.xml"            "$M/ce/events.xml"
cp "$M/db/cfgeconomycore.xml"   "$M/ce/cfgeconomycore.xml"
```

Then restart the server. Expect `[CE][TypeSetup] :: N classes` with **N >> 885** (the 5252 mod types now load) and loot on the map.

## What this is NOT

- NOT the `types.bin` cache trap (§6). The cache trap produces a DIFFERENT signature: DayZ DOES load a types.xml (so `types.xml` appears in RPT context) but the cached `.bin` shadows an edit. Here DayZ never loads ANY types.xml (grep count 0).
- NOT the `cfgeconomycore.xml <files>` tag. Adding `<files>` to cfgeconomycore.xml does NOT fix this — DayZ auto-loads `ce/types/types.xml` via default path; the `<files>` block is a red herring on this host.
- NOT excluded-mod "Type does not exist" warnings. Those are harmless when the mod is intentionally absent.

## Diagnosis order for empty loot

1. `ce/types/types.xml` present at mission-root `ce/`? → if missing, fix LOCATION first (this trap).
2. Present but still empty → `types.bin` cache shadowing a newer `types.xml`? → rename the bin (§6).
3. `Unknown usage` flood → `cfglimitsdefinition.xml` basis (§6).
4. `Type does not exist` for intentionally-excluded mods → ignore (red herring).
