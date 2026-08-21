# CE cache → NULL loot: diagnosis + fix (Apocalyps3nd, 2026-07-18)

Companion to SKILL.md §6 (cache traps) and §5 (audit checklist). Session-specific
recipe for the "server boots, player connects, map has NO loot" failure.

## Symptom
- Server RPT: `SteamGameServer_Init SUCCESS`, mission loads, player reaches
  `WaitPreloadCamLoginState` → in-game, no crash.
- Client RPT: clean (no SCRIPT E).
- But: walking the map finds zero loot. `CE][LoadMap "Group" :: loaded 30599
  groups, groups failed: 6049` is normal-ish; the killer is the cache.

## The two cache layers (both in storage_1/data/)
| File | Shadows | Symptom if stale |
|------|---------|------------------|
| `types.bin` (+ `.001`/`.002` rollbacks) | `db/types.xml` | NULL / wrong loot across the map |
| `events.bin` | `db/events.xml` | DynEvents (APX_WeaponCache etc.) ignored: `failed to determine spawner type` |

## Diagnostic commands (run on the live mission dir)
```bash
M=.../mpmissions/dayzOffline.chernarusplus
# 1. Is the cache shadowing the xml? (bin newer than xml = stale shadow)
stat -c '%y' "$M/storage_1/data/types.bin"   # cache
stat -c '%y' "$M/db/types.xml"               # source (17. Jul here)
stat -c '%y' "$M/storage_1"                  # wipe time — bin mtime must be AFTER this
# 2. RPT signature — "Restoring" = cache wins, not the xml
grep -E "TypeSetup|Restoring file|Type does not exist" "$M/../../profile/"*.RPT | head
# 3. Is the xml even good? (5252 types, all nominal>0, usages present)
grep -c "<type name=" "$M/db/types.xml"
grep -c "<nominal>0</nominal>" "$M/db/types.xml"   # expect 0
grep -c "<usage" "$M/db/types.xml"                  # expect >10k
# 4. Red-herring check: which mod would supply a "Type does not exist" item?
ls -d /home/alca/games/DayZ/Mods/@WendigoCreature   # present but NOT in MOD_LIST = harmless
```

## Fix (rename, reversible — user blocked unprompted `rm`)
```bash
D="$M/storage_1/data"
TS=$(date +%H%M%S)
mv "$D/types.bin"  "$D/types.bin.bak_$TS"
mv "$D/types.001"  "$D/types.001.bak_$TS"
mv "$D/types.002"  "$D/types.002.bak_$TS"
# leave every OTHER file in storage_1/data/ (vehicle/zombie/building state) alone
```
Restart server (user does the kill — agent `kill` rips its own terminal, see §11).
DayZ rebuilds `types.bin` from the good `types.xml` → loot spawns.

## Confirmed NOT the cause (hypotheses we burned turns on — skip them)
- `cfgeconomycore.xml` lacking a `<files>` block — NORMAL on every DayZ config;
  DayZ loads CE files via default paths + `cfgenvironment.xml`.
- `Type does not exist` for `@WendigoCreature` / `@AJs Creatures V2` /
  `@AmmunitionExpansion` items — harmless when those mods are intentionally
  absent from the active MOD_LIST. User: "es LIEGT NICHT AN DEN 3 ADDONS! AT ALL!".
- `events.xml` `<spawn type="Loot"/>` missing — real for DynEvents, but DynEvents
  are only 2 caches; they are NOT why the whole map is empty. Fix types.bin FIRST.

## Verification after restart
- RPT no longer shows `Restoring file types.bin` as the only load (or the rebuilt
  bin now matches the xml).
- Player reports actual loot on the ground.
- `Type does not exist` count is unchanged (harmless) — do not re-chase.
