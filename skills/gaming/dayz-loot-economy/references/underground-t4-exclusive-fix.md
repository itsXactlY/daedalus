# Underground-T4 Exclusivity Fix (DayZ mapgroupproto)

## The trap
Setting T4 items to `<usage name="Underground_Sevorgrad"/>` does NOT make them
spawn only in the bunker. DayZ matches loot to map groups by the `<usage>`
TAG, and the live `Server/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml`
knows `Underground_*` ONLY as an annex tag on ~473 ordinary buildings
(`Land_Shed_*`, `Land_HouseBlock_*`, `Land_Garage_Small`) that are ALSO bound
to Town/Village/Industrial/Farm. So T4 would flood every house.

The real `Land_Underground_Storage_*` / `Land_Bunker*` groups exist but are
bound to `Military` (lootmax=10) — they spawn Military-tier, not T4-exclusive.

## The fix (verified 2026-07-17)

### Step 1 — Extension file
`mapgroupproto_<mod>_Underground_T4.xml`:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<prototype>
    <group name="APX_Underground_Lopatino" lootmax="6">
        <usage name="APX_Underground_Lopatino" />
        <container name="lootFloor" lootmax="6">
            <point pos="6011.0 152.0 8448.0" range="1" height="1" />
            <!-- 8 points total, offset ±2m around an anchor coord -->
        </container>
    </group>
    <!-- repeat for Sobor, Sevorgrad, SeaPlatform, Ocean, Skalisty, OilRig -->
</prototype>
```
Anchor coords (Chernarus): Lopatino ~(6011,152,8448), Sobor ~(3886,150,10175),
Sevorgrad ~(3818,148,10130), SeaPlatform ~(7350,140,11200), Ocean ~(4200,138,9200),
Skalisty ~(5250,145,12650), OilRig ~(7350,142,9000). Real bunker geometry can be
lifted from `full_coords/Bunker-Koslova.xml` / `Berenzino_Underground_Island_NK.xml`
(static wall/floor objects, NOT loot groups — use as position anchors only).

### Step 2 — Inject into live map (WITH BACKUP)
```python
import re, shutil, os
MP = "/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus"
LIVE = os.path.join(MP, "mapgroupproto.xml")
BACKUP = os.path.join(MP, "backups", "mapgroupproto_pre_apocalyps3nd_underground.xml")
shutil.copy2(LIVE, BACKUP)                       # INVARIANT: backup first
ext = open(EXT_PATH).read()
ext_groups = re.search(r"<prototype>(.*)</prototype>", ext, re.DOTALL).group(1)
live = open(LIVE).read()
merged = live.replace("</prototype>", ext_groups + "\n</prototype>")
open(LIVE,"w").write(merged)
import xml.etree.ElementTree as ET; ET.parse(LIVE)   # validate well-formed
```

### Step 3 — Bind types.xml T4 to APX_Underground_*
For every `<type>` with `<value name="Tier4"/>`, rewrite each `<usage>` that
starts with `Underground_` (and not `APX_`) to `APX_` + same name.

### Step 4 — Verify
```python
groups = re.findall(r'<group[^>]*name="([^"]*)"[^>]*>(.*?)</group>', merged, re.DOTALL)
apx = [(n,b) for n,b in groups if n.startswith("APX_Underground_")]
# each must have ONLY APX_Underground_* usages, 8 points, lootmax=6
# T4 usages in types.xml must == set of APX_Underground_* usages in map
```
Expect: `>>> T4 spawn EXKLUSIV in APX_Underground_* Zonen: True`.

## Why this matters
Without the `APX_` prefix indirection, T4 loot lands on 473 houses = economy
break. The prefix makes the usage tag EXCLUSIVE to your custom groups.
