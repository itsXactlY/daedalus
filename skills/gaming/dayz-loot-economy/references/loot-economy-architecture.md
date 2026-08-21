# DayZ Central Economy — 4 Spawn Pillars (architecture)

Extracted from live server config (Apocalyps3nd rebuild, 2026-07-16).

## Pillar 1 — STATIC LOOT (cfgspawnabletypes.xml)
Items hang off world objects. Structure:
```xml
<type name="Land_HouseBlock_1F1">
  <attachment class="HouseDoor" lootmax="1" />
  <attachments chance="0.3">
    <item name="APX_Food_Can" chance="0.5" />
    <item name="APX_Cloth_Shirt" chance="0.3" />
  </attachments>
</type>
```
`chance` is per-attachment weighting; only 1 item per attachment slot.

## Pillar 2 — RANDOM PRESETS (cfgrandompresets.xml)
2-stage weighted. cargo `chance` selects the preset, item `chance` selects
the item INSIDE (only 1 item/spawn):
```xml
<randompresets>
  <presets chance="0.15">
    <preset name="foodHermit">
      <item name="APX_Food_Tuna" chance="0.11" />
      <item name="APX_Food_Beans" chance="0.09" />
    </preset>
  </presets>
</randompresets>
```

## Pillar 3 — EVENT GROUPS (cfgeventgroups.xml)
Fixed loot nests with absolute child coordinates:
```xml
<event name="APX_Train_Cherno">
  <posistion> 1234 56 7890 </posistion>   <!-- note: BI typo 'posistion' -->
  <child lootmax="6" lootmin="3" nominal="6">
    <child type="Land_Container" pos="0 0 0" />
    <child type="APX_T4_SVD" pos="1 0 0" a="90" />
  </child>
</event>
```
`Land_Container` etc. are world objects (containers), NOT loot — exclude from
dangling-ref checks.

## Pillar 4 — DYNAMIC EVENTS (events.xml + cfgeconomycore.xml)
Spawns around the player; respawn-controlled:
```xml
<event name="APX_WeaponCache">
  <nominal>8</nominal><min>4</min><max>12</max>
  <lifetime>1800</lifetime>
  <saferadius>100</saferadius><distanceradius>300</distanceradius>
  <position>player</position>
  <children>
    <child lootmax="6">
      <item name="APX_T3_AK101" chance="1" />
    </child>
  </children>
</event>
```
`cfgeconomycore.xml` defaults: `dyn_radius=30`, `dyn_smin=0`, `dyn_smax=0`,
`dyn_dmin=1`, `dyn_dmax=5`, rootclasses `DefaultWeapon/Magazine/Inventory_Base/
SurvivorBase/DZ_LightAI/CarScript/BoatScript`.

## Modal delivery systems (separate from spawn pillars)
Care Packages V2 (airdrop, Military pkg), CJ187-LootChest, @Trader (MoneyRuble
1-100, SINGLELINE comments ONLY — `/* */` multiline crashes server),
SpawnerBubaku (zombie JSON, triggerdelay 3600s), ExpansionMod-Market,
BaseBuildingPlus (Workbench/Blueprint/BuildPermit crafted-only), MuchStuffPack.

## Audit (Säulen)
- cfgspawnabletypes: every `<item>` classname exists in types.xml
- cfgrandompresets: every preset item exists in types.xml
- cfgeventgroups: every `<child type="APX_*">` exists; `Land_*` containers exempt
- events.xml: every `<item>` exists; `<position>player</position>` valid
- cfgeconomycore: rootclasses present, dyn_* defaults sane
