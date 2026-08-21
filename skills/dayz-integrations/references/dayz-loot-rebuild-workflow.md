# DayZ Loot Rebuild Workflow (T1–T4 from scratch)

Condensed technique bank from the Apocalyps3nd loot rebuild (2026-07-16).
Companion to `dayz-weapons-loot-knowledge.md` (which has the tier/zone maps + invariants).
This file covers the BUILD + AUDIT procedure, not the loot lore.

## The 4 Spawn Pillars (every loot item lives in exactly one)

1. **STATIC LOOT** — `cfgspawnabletypes.xml`
   Items attached to world objects. `<type name="House_1"><attachments chance="0.40"><item name="APX_Cloth_Jacket_Olive" chance="0.20"/></attachments></type>`
   `chance` on `<attachments>` = spawn probability of the slot; `chance` on `<item>` = which item if slot fires (weighted random, ONE item per spawn).
2. **RANDOM PRESETS** — `cfgrandompresets.xml`
   `<cargo chance="0.20" name="apx_foodT1"><item name="APX_Food_CannedBeans" chance="0.12"/></cargo>`
   2-stage weighted: cargo-chance × item-chance. ONE item per spawn.
3. **EVENT GROUPS** — `cfgeventgroups.xml`
   Static loot nests at fixed coords: `<group name="APX_Train_Cherno"><child type="Land_Container_1Aoh_DE" lootmax="5" lootmin="2" x="0" z="0" a="90.0" y="2.05"/>`
   `x/z/a/y` = offset + yaw/pitch. `lootmax/min` = item count range.
   NOTE: `<child type="...">` is EITHER a world object (Container/Wagon — Vanilla, NOT in types.xml)
   OR a loot drop (APX_-prefixed — MUST be in types.xml).
4. **DYNAMIC EVENTS** — `events.xml` (steered by `ce/cfgeconomycore.xml` dyn_* defaults)
   `<event name="APX_WeaponCache"><nominal>20</nominal><min>5</min><max>30</max><lifetime>3600</lifetime>
   <restock>0</restock><saferadius>50</saferadius><distanceradius>25</distanceradius>
   <flags deletable="0" init_random="1" remove_damaged="1"/><position>player</position>
   <limit>custom</limit><active>1</active><children><child type="APX_AK74" lootmax="4" lootmin="1" max="3" min="1"/></children></event>`
   `cfgeconomycore.xml` rootclasses: DefaultWeapon/DefaultMagazine/Inventory_Base/SurvivorBase(act=character)/
   DZ_LightAI(act=character)/CarScript(act=car)/BoatScript(act=car).
   dyn defaults: dyn_radius=30, dyn_smin=0, dyn_smax=0, dyn_dmin=1, dyn_dmax=5.

## APX_* Naming Convention (used for the rebuild)

| Type | Pattern | Example |
|------|---------|---------|
| Weapon | `APX_<Familie><Kaliber>` | `APX_AK545`, `APX_MP9` |
| Magazine | `APX_Mag_<Caliber>_<Rnd>` | `APX_Mag_545x39_30` |
| Ammo | `APX_Ammo_<Caliber>` | `APX_Ammo_545x39` |
| Attachment | `APX_<Slot>_<Waffe>` | `APX_Optic_AK545` |
| Civilian/Food/Tools | `APX_<Kategorie>_<Name>` | `APX_Food_CannedBeans` |

CRITICAL: Mag name MUST contain the caliber string (`APX_Mag_545x39_30` not `APX_Mag_AK74_30`)
so the dangling/orphan audit (below) can match mag↔ammo by caliber substring.

## types.xml Entry Shape

```xml
<type name="APX_Pistol_9mm">
  <nominal>40</nominal><min>20</min><lifetime>14400</lifetime><restock>3600</restock>
  <quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>
  <flags count_in_cargo="1" count_in_hoarder="1" count_in_map="1" count_in_player="1" crafted="0" deloot="0"/>
  <category name="weapons"/><usage name="Coast"/><value name="Tier1"/>
</type>
```
- `nominal` = target count on map; `lifetime` seconds (14400=4h, 3888000=45d for Underground); `restock` seconds (0=never)
- `<usage>` = ZONE (Coast/Town/Village/Farm/Hunting/Police/Military/Underground_*)
- `<value name="TierN"/>` = rarity tier

## USER DIRECTIVE (first-class, do not violate)

"weniger ist mehr! modded items > vanilla item(s). KEINE 100 Duplikate der selben Jacke."
→ Build CURATED sets. Each APX_ item replaces a Vanilla pendant 1:1. NO fill-spam, NO 100× jacket.
Quality over quantity. The rebuild produced 92 curated items replacing 5332 Vanilla — that is the target ratio.

## Audit-Loop Pattern (run after generation, BEFORE deploy)

Three checks, all must pass:

**A. well-formed** — `ET.parse()` on every XML (or `xmllint --noout`).

**B. orphaned ammo** — every `APX_Ammo_<cal>` must have `APX_Mag_<cal>_*` in the SAME tier.
```python
for name,(ty,tag) in all_types.items():
    if "Ammo" not in name: continue
    cal = name.split("APX_Ammo_")[1]
    mags_same = [n for n in all_types if "Mag" in n and f"Mag_{cal}" in n and all_types[n][1]==tag]
    if not mags_same: problems.append(f"{name} ({tag}): no Mag_{cal} in same tier")
```

**C. dangling distribution refs** — every APX_-prefixed class referenced in cfgspawnabletypes /
cfgrandompresets / events / cfgeventgroups must exist in types.xml. Vanilla world objects
(Land_Container, Land_Train_Wagon) in cfgeventgroups are LEGIT — only APX_ children must resolve.
```python
defined = {ty.get("name") for f in ["types_T1.xml",...] for ty in ET.parse(f).getroot().findall("type")}
# only flag APX_-prefixed refs that are missing
```

**D. tier/zone invariants** — T4 usage MUST be 100% `Underground_*`. Coast/Town usage must NEVER
carry Tier3/Tier4. (See `dayz-weapons-loot-knowledge.md` INVARIANTEN for the full hard list.)

**E. balance** — target distribution T1≈40% T2≈25% T3≈20% T4≈15%. Old economy was broken
(T3=24 items, T5=682). Warn if any tier drifts >15% from target.

## Technique: execute_code > agent swarm for deterministic XML

delegate_task with Free-Tier models (e.g. nvidia/nemotron-3-*) TIMES OUT at 600s on a 60–90-item
XML write — the model is too slow for one-shot file generation. Do NOT burn days on agent crews
for deterministic config generation. Instead:

- Generate types_*.xml + distribution XMLs with `execute_code` (Python + `xml.etree` + `minidom`
  for pretty-print). 0.2s, fully reproducible, you control every value.
- Run the audit-loop in the SAME or a follow-up `execute_code` call.
- The "multi-agent crew with audit loops" framing is fine as a MASTERPLAN, but the actual build
  step should be deterministic code, not slow subagents. Reserve delegate_task for genuinely
  reasoning-heavy parallel subtasks (not mechanical XML emission).

Pitfall: `minidom.parseString(...).toprettyxml()` emits its OWN `<?xml ...?>` on line 1. If you
prepend a manual `<?xml ...?>` you get "XML declaration not at start of entity" parse error on reload.
Fix: strip blank lines only, do NOT add a second declaration.

## Merge + Deploy Gate

- Merge types_T1..T4.xml → types.xml (one `<types>` root) only after Phase audits pass.
- Build into an ISOLATED mod folder (`@Apocalyps3nd_Loot/`) — never write live server types during
  a multi-week build. Live deploy = copy + backup + diff + validator + user approval (INVARIANTEN.md).
- VANGUARD hook: PBO-whitelist must know `@Apocalyps3nd_Loot` as a SIGNED mod before it goes live.
