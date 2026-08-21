# Deploy: MERGE vs REPLACE — the baseline-destruction traps (2026-07-18 session)

When `deploy_live.py` used `merge=True` on events.xml / cfgeventspawns.xml /
cfglimitsdefinition.xml, it PRODUCED THREE separate broken states that cost
~10 restart iterations to find. The lawful deploy path is REPLACE for these
three files, NOT merge.

## Trap 1 — `events.xml` MERGE deletes the Vanilla events

`backup_and_copy(..., merge=True)` on events.xml only ADDS events whose name is
not already present. If the live `db/events.xml` was ALREADY corrupted (only the
2 APX events, Vanilla 59 gone — which is exactly what happened mid-session), the
merge sees "APX_WeaponCache already exists" and SKIPS it, leaving the file with
only 2 events.

RPT signature that proves it:
```
[CE][offlineDB] :: Loaded 2 dynamic events 20 total types.
```
2 events = only the APX ones. Vanilla Loot/VehicleHeliSpawn/etc. are GONE.
DayZ then reports `DynamicEvent "APX_WeaponCache" setup is invalid` because the
event stands alone without the rest of the economy context it expects.

FIX: events.xml must be REPLACE (full file). The MOD source `events.xml` must
itself contain ALL 61 events (59 Vanilla from `Server_backup/.../db/events.xml`
+ 2 APX). Do NOT rely on merge to preserve Vanilla.

## Trap 2 — `cfgeventspawns.xml` MERGE produces malformed tags

`merge=True` on cfgeventspawns.xml concatenated the Vanilla `<eventposdef>` block
with the APX block but the merge logic emitted a broken self-closing tag:
```
<event name="Loot"/></event>
```
→ XML parses but DayZ's spawner reader chokes. Also: only 1 `<pos>` survived per
APX event (the merge dropped 4 of 5 positions). RPT still shows APX invalid.

FIX: cfgeventspawns.xml must be REPLACE. The MOD source `cfgeventspawns.xml`
contains the FULL `<eventposdef>` (Vanilla + APX). Verify after deploy:
```
grep -c "<pos " cfgeventspawns.xml        # expect 10 for 2 APX events (5 each)
grep -A6 'name="APX_WeaponCache"' cfgeventspawns.xml | grep -c "<pos "
```

## Trap 3 — types.xml must UNION Vanilla + Mod (not Mod-only)

The shipped `@Apocalyps3nd_Loot/types.xml` was 5252 APX-only types. It had NO
Vanilla items (Bandage=0, Matches=0, M4A1=0). Result: 113 `Type does not exist`
warnings and the server loads only ~480 prototypes.

DayZ needs BOTH: the full Vanilla item set AND the mod items. A types.xml that
is mod-items-only is incomplete.

FIX: build the live types.xml as UNION(Vanilla base, APX types). The Vanilla base
must be the REAL DayZ Vanilla (from `scripts.pbo` — a BI-PBO, `sreV` magic, needs
a PBO extractor; `7z` cannot read it). The session used
`/home/alca/apogrps_qwen/Colorful-UI-Pro-main/Missions/Custom/dayzOffline.Esseker/db/types.xml`
(1491 types, has Bandage/M4A1) as a stopgap base, but that is only ~1491 types and
STILL misses items like `BandanaMask_BlackPattern` — so 113 "Type does not exist"
persisted. The correct base is the full Vanilla from scripts.pbo.

Union recipe (Python):
```python
import xml.etree.ElementTree as ET
vanilla = ET.parse(VANILLA_TYPES).getroot()   # full DayZ vanilla
apx     = ET.parse(APX_TYPES).getroot()       # mod types
seen = set(); merged = ET.Element("types")
for t in vanilla.findall("type"):
    if t.get("name") not in seen:
        merged.append(t); seen.add(t.get("name"))
for t in apx.findall("type"):
    if t.get("name") not in seen:
        merged.append(t); seen.add(t.get("name"))
ET.indent(merged); ET.ElementTree(merged).write(OUT, ...)
```
After deploy, VERIFY: `grep -c 'name="Bandage"' types.xml` must be >=1 and the
RPT `Type does not exist` count must be ~0 (only truly-excluded-mod items may
remain — those are the harmless red herring from section 6, not a real gap).

## The corrected deploy_live.py shape (what worked at end of session)

```python
backup_and_copy(src/"types.xml",           dst/"db/types.xml")            # REPLACE
backup_and_copy(src/"events.xml",          dst/"db/events.xml")           # REPLACE (full 61)
backup_and_copy(src/"cfgeventspawns.xml", dst/"cfgeventspawns.xml")      # REPLACE (full)
backup_and_copy(src/"cfglimitsdefinition.xml", dst/"cfglimitsdefinition.xml")  # REPLACE
backup_and_copy(src/"cfgspawnabletypes.xml", dst/"cfgspawnabletypes.xml", merge=True)  # MERGE OK here
backup_and_copy(src/"ce/cfgeconomycore.xml", dst/"db/ce/cfgeconomycore.xml")  # REPLACE
```
cfgspawnabletypes.xml MERGE is safe (additive item types, no baseline to lose).
Everything else: REPLACE with a MOD source that already contains the full file.
