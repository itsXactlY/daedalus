# DayZ CE (Central Economy) — Loot / types.xml / cfgeconomycore Debugging

Condensed knowledge bank from a multi-hour Apocalyps3nd server debugging session
(2026-07-18). The failure class: server starts, client can connect, but **loot
does not spawn** (0 items) or spawns only vanilla items while all mod items
report "Type does not exist". Below are the loader rules DayZ 1.28 actually
uses, confirmed by diffing a working mission against a broken one.

## Symptom → root-cause map

| RPT symptom | Root cause |
|---|---|
| `[CE][CoreData] :: 0 root classes ... ZERO root classes - SPAWN WILL NOT WORK` | `cfgeconomycore.xml` uses wrong root element: `<economy>` / `<rootclasses><class>` instead of `<economycore>` / `<classes><rootclass>`. DayZ 1.28 parses 0 classes. |
| `[CE][TypeSetup] :: 885 classes setuped...` (not ~5252) | Main `types.xml` not loaded. Only the ~885 hardcoded vanilla types exist. Mod types (A6_*, APX_*) missing. |
| `Type 'A6_AR15_Standard' will be ignored. (Type does not exist)` | types.xml loaded but the specific type is absent (typo, or the type lives in a `ce/types/*.xml` fragment that isn't referenced). |
| `[CE][DE][GROUPS] :: Skipping pos with invalid type 'TacticalHelmet_Olive'` | A `cfgeventgroups.xml` / `mapgroupproto.xml` group references an item defined by a MOD that is NOT registered in any loaded `types.xml`. Non-fatal — only that spawn pos is skipped. |
| `DynamicEvent "APX_WeaponCache" setup is invalid, event will be disabled` | `events.xml` event node has no spawner type. DayZ 1.28 requires the spawner type to be determinable. Non-fatal — event just won't trigger. |
| `!!! [CE][LoadPrototype] 327 Errors during XML parse...` | A prototype/mapgroup XML has malformed entries. Usually cosmetic unless it zeroes all prototypes. |

## DayZ 1.28 CE loader rules (CONFIRMED)

1. **`cfgeconomycore.xml` root element MUST be `<economycore>`**, not `<economy>`.
   - Root classes block: `<classes><rootclass name="DefaultWeapon" />...</classes>`
     — NOT `<rootclasses><class name="..."/></rootclasses>`.
   - A working example uses 8 rootclass entries:
     `DefaultWeapon, DefaultMagazine, Inventory_Base, HouseNoDestruct,
     SurvivorBase, DZ_LightAI, CarScript, BoatScript`.

2. **`types.xml` location:** DayZ loads the main `types.xml` from
   `mpmissions/<mission>/db/types.xml` (NOT the mission root, NOT `ce/`).
   If you only have it in the root, CE reads 0/885 classes.

3. **Mod type fragments** (e.g. A6 weapon pack) are loaded via
   `<ce folder="ce/types">` blocks inside `cfgeconomycore.xml`:
   ```xml
   <ce folder="ce/types">
     <file name="A6_Assault_Rifle.xml" type="types" />
   </ce>
   <ce folder="ce/spawnabletypes">
     <file name="A6_Weapons_Assault_Rifle_SpawnableTypes.xml" type="spawnabletypes" />
   </ce>
   ```
   These files MUST exist at `mpmissions/<mission>/ce/types/*.xml` and
   `ce/spawnabletypes/*.xml`. If the `<ce folder>` block references files that
   don't exist, those types silently don't load.

4. **Storage path:** `mpmissions/<mission>/storage_1/data/*.bin`.
   - On a fresh/empty storage, DayZ prints `Empty storage folder, reinitializing`
     and builds loot fresh from the resolved types table.
   - If `storage_1/data/*.bin` are present but 0-byte / `valid:NO`, DayZ restores
     them and spawns 0 items. **Wipe `storage_1/data/*.bin` (move to .bak, never
     `rm` — user blocks deletes) to force a fresh loot build.**
   - `types.bin` being large (350KB+) is GOOD. `dynamic_*.bin` at 49 bytes = empty.

5. **`cfgenvironment.xml`** references `env/*.xml` files. If missing:
   `[ERROR][XML] :: load [...] failed` — non-fatal, just no wendigo/underground spawns.

## The working-vs-broken diff that solved it

Broken mission was missing:
- `ce/types/` directory (19 A6 XML fragments) → all A6 weapons "Type does not exist"
- `<ce folder="ce/types">` + `<ce folder="ce/spawnabletypes">` blocks in cfgeconomycore.xml
- `db/types.xml` (types.xml had been placed in root instead of db/)

Fix = copy `ce/` tree + `db/types.xml` + GOOD `cfgeconomycore.xml` from the
working mission. After that: `TypeSetup :: 5252 classes setuped...` and loot spawns.

## Diagnostic procedure (do this BEFORE patching)

1. Read the FULL RPT, not grep snippets. The CE init block is ~lines 3570–3700;
   the storage-load and "Player connect enabled / Mission geladen" lines are near
   the end. Grep-only views miss the class count that proves the root cause.
2. Check `[CE][CoreData] :: N root classes` — must be 8, not 0.
3. Check `[CE][TypeSetup] :: N classes setuped...` — must be ~5252, not 885.
4. Check `types.xml` exists at `db/types.xml` AND `ce/types/*.xml` exist.
5. Check `cfgeconomycore.xml` root element is `<economycore>` with `<classes><rootclass>`.
6. Only after ALL of the above, decide what to patch. One change at a time.

## File map (this server)

- Mission: `/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus/`
- CE config root: `cfgeconomycore.xml`
- Types: `db/types.xml` (main), `ce/types/*.xml` (mod fragments)
- Events: `db/events.xml`
- Storage: `storage_1/data/*.bin`
- Server RPTs: `/home/alca/games/DayZ/Server/profile/DayZServer_x64_*.RPT`
- Working reference: the mission dir that boots correctly — diff against it, don't reinvent
