# deploy_live.py — the lawful DayZ loot deploy path (Apocalyps3nd)

Source: `/home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot/deploy_live.py`
Runs from: `cd /home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot && python3 deploy_live.py`

## What it does
Backs up + merges + validates ALL loot XMLs into the LIVE mission:
`Server/mpmissions/dayzOffline.chernarusplus/` (and its `db/`, `db/ce/`).
Output on success: `DEPLOY SUCCESS` + per-file counts (types/events/cfgspawnabletypes/
cfgeventgroups/cfgrandompresets/cfgeconomycore) + problem count (should be 0).

## The trap that wasted ~6 iterations (2026-07-18)
Agent hand-edited XMLs DIRECTLY in the live `mpmissions/.../db/` tree instead of editing
the mod source + running the deploy. Result: stale partial XMLs, a broken
`cfgeventspawns.xml` (`<event name="Loot"/></event>` mismatch tag from a bad merge), and
APX events that stayed "invalid" across 6 restarts.

## Correct flow
1. Edit the MOD SOURCE files in `@Apocalyps3nd_Loot/`:
   - `events.xml` (APX `<event>` blocks: `<position>fixed</position>` + `<child>` tags)
   - `cfgspawnabletypes.xml` (`<type>` not `<item>`)
   - `cfgeventgroups.xml`, `cfgrandompresets.xml`
   - `ce/cfgeconomycore.xml` (`<economycore>/<classes>/<rootclass>`)
   - `cfgeventspawns.xml` (NEW — `<eventposdef>` with `<event name="APX_X"><pos x/z/a/></event>`)
2. `cd /home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot && python3 deploy_live.py`
3. If it crashes on validate -> the exception names the malformed XML in the MOD SOURCE.
   Fix the SOURCE, re-run. NEVER hand-edit the deployed `mpmissions/` copy.
4. Restart server (safe kill per SKILL.md 11). Wait >=15 min. Measure `dynamic_*.bin`
   byte count (SKILL.md 14), not the boot-line `dynamic groups: 0`.

## REQUIRED: cfgeventspawns.xml merge step
The deploy script as-shipped did NOT copy `cfgeventspawns.xml`. Without it, APX
`<position>fixed</position>` events cannot place -> "setup is invalid" forever.
Add a merge block to `deploy_live.py` (after the cfgeconomycore copy) that merges the
mod `cfgeventspawns.xml` into the live one — merging, NOT overwriting, so the vanilla
`VehicleHeliSpawn` / `VehicleOffroadHatchback` entries survive:

```python
# 7. cfgeventspawns.xml (MERGE into live, preserve vanilla events)
import re
live_spawns = os.path.join(DST, "cfgeventspawns.xml")
mod_spawns   = os.path.join(SRC, "cfgeventspawns.xml")
if os.path.exists(mod_spawns):
    if os.path.exists(live_spawns):
        backup_and_copy(live_spawns, live_spawns + ".bak_" + ts)
        live_txt = open(live_spawns, encoding="utf-8").read()
        mod_txt  = open(mod_spawns, encoding="utf-8").read()
        for m in re.finditer(r'<event name="([^"]+)">.*?</event>', mod_txt, re.DOTALL):
            name = m.group(1)
            if f'name="{name}"' not in live_txt:
                live_txt = live_txt.replace("</eventposdef>",
                                            m.group(0) + "\n</eventposdef>")
        open(live_spawns, "w", encoding="utf-8").write(live_txt)
    else:
        backup_and_copy(mod_spawns, live_spawns)
```

After deploy, verify:
- `grep -c "APX_WeaponCache" Server/mpmissions/dayzOffline.chernarusplus/cfgeventspawns.xml` >= 1
- `python3 -c "import xml.etree.ElementTree as ET; ET.parse('<path>')"` on BOTH
  `cfgeventspawns.xml` and `db/events.xml` prints VALID (no `ParseError: mismatched tag`).
