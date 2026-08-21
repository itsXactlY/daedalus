---
name: dayz-loot-economy
description: >
  Build, audit, and repair DayZ Central Economy loot systems from scratch:
  types.xml tier architecture, the 4 spawn pillars (cfgspawnabletypes /
  cfgrandompresets / cfgeventgroups / events.xml + cfgeconomycore),
  mapgroupproto usage-zone wiring, and the exclusive-Underground-T4 fix.
  Use when the user wants to (re)build loot, rebalance tiers, add items,
  cover all modpacks, or make custom zones actually spawn in-game.
  Triggers: "loot rebuild", "tier 1-4 neu bauen", "alle mods durchgehen",
  "loot economy", "spawn pillars", "Underground zone fehlt", "types.xml
  von scratch", "mapgroupproto", "Central Economy", or any DayZ loot
  distribution task broader than a single item edit.
---

# DayZ Loot-Economy Build & Audit

Class-level skill for constructing DayZ Central Economy loot from scratch
and repairing spawn-zone wiring. Born from the Apocalyps3nd T1-T4 rebuild
(2026-07-16/17) where the user demanded FULL coverage of every modpack and
caught a silent T4-spawn bug that would have flooded every house with
endgame loot.

## 0. OPERATOR PREFERENCES (embedded from session)

- **FULL COVERAGE, NOT NARROW SCOPE.** When the user says "loot" they mean
  the WHOLE economy — all 4 spawn pillars, every tier, AND every modpack on
  disk (MuchStuffPack, BaseBuildingPlus, DrugsPlus, Boats, Garage, CodeLock,
  etc.), not just the headline items (A6 weapons). If you scope to "weapons
  only" the user will say "nein, sämtlichen loot context" / "für ALLE
  möglichen items! jedes modpack!". Default to a complete inventory sweep
  first (see references/inventory-technique.md), then build.
- **"weniger ist mehr" — curated over padded.** The user explicitly rejected
  mass-duplication (100 jacket variants). Build a CURATED set of modded items
  with a consistent prefix (e.g. `APX_*`), each replacing a Vanilla/modded
  counterpart 1:1. Quality of items > quantity. Target ~100-120 curated items
  for a full T1-T4 rebuild, not 5000.
- **Isolated build, live untouched until approval.** Build into a separate
  mod folder (e.g. `@Apocalyps3nd_Loot`) and never edit the live
  `Server/mpmissions/.../db/types.xml` or `mapgroupproto.xml` without an
  explicit approval gate + backup.
- **SINGLE SOURCE OF TRUTH — MANDATORY.** The user's explicit correction
  "nichts steuert es, diese zu renamen" (nothing governs renaming the class
  names) means: NEVER hand-edit generated XML. All classnames + tiers + usages
  live in ONE manifest JSON (`APX_MANIFEST_FULL.json`). A generator script
  (`generate_apx_full.py`) builds ALL 7 XMLs from it. Rename = edit manifest +
  re-run generator. No manual XML edits, ever. This also makes "total audit
  von vorn" trivial: regenerate, then audit.
- **FULL INVENTORY, not curated subset (reconciling "weniger ist mehr").**
  The user first wanted a curated ~100-120 `APX_*` set, then flipped to "für
  ALLE möglichen items! jedes modpack!" → the build must cover EVERY item from
  EVERY mod on disk. Resolution: the manifest is seeded from the LIVE
  `Server/.../db/types.xml` (all 5252 items across all mods: A6_*, FOG_*,
  BBP_*, etc.), re-balanced in tier distribution, and `@Apocalyps3nd_Loot`
  becomes the MASTER LOOT OVERLAY (controls distribution, not redefinition).
  "Weniger ist mehr" applies to NOT duplicating vanilla 1:1 with padded
  variants — but coverage must be TOTAL. When in doubt, sweep the disk first.

## 1. The 4 Spawn Pillars (how loot is born)

1. **STATIC LOOT** — `cfgspawnabletypes.xml`: items hang off world objects
   (wrecks, houses, helis) via `<attachments chance>` / `<item chance>`.
2. **RANDOM PRESETS** — `cfgrandompresets.xml`: 2-stage weighted
   (cargo `chance` × item `chance`, ONLY 1 item/spawn).
3. **EVENT GROUPS** — `cfgeventgroups.xml`: fixed nests with exact child
   coordinates (`x/z/a/y`) + `lootmax`/`lootmin`.
4. **DYNAMIC EVENTS** — `events.xml` + `cfgeconomycore.xml`: spawns around
   the player (`<position>player</position>`), driven by `nominal/min/max/
   lifetime/saferadius/distanceradius` and `dyn_radius`/`dyn_dmin`/`dyn_dmax`.

Reference: `references/loot-economy-architecture.md` (full pillar breakdown
+ the 4-Säulen audit checklist).

## 2. types.xml Tier Model

Each `<type>` carries: `nominal/min/lifetime/restock/quant/cost/flags/
category/value(TierX)/usage(Zone)`.
- T1=Coast/Town (starter), T2=Village/Farm/Hunting, T3=Police/Military,
  T4=Underground_* ONLY, T5=rarest Underground_Sevorgrad.
- **Hard invariants (from masterplan):** every weapon needs a consistent
  Ammo+Mag chain (NO orphaned ammo); starters = survival + light
  self-defense, no power combos; T1-T5 logically separated; no prod file
  without backup/diff/validator.

## 3. THE UNDERGROUND-T4 EXCLUSIVITY TRAP (critical pitfall)

**Symptom:** you set T4 items' `<usage name="Underground_Sevorgrad"/>` and
expect them only in the bunker. They don't — they spawn at 473 houses/sheds
that have `Underground_*` as a usage ANNEX (bound to Town/Village/Industrial/
Military). Game-breaking flood.

**Root cause:** DayZ matches loot to groups by `<usage>` TAG, not by group
name. The live `mapgroupproto.xml` knows `Underground_*` only as annex tags
on ordinary buildings; there are NO groups that are EXCLUSIVELY
`Underground_*`.

**Fix (do this, not the naive binding):**
1. Build a `mapgroupproto_<mod>_Underground_T4.xml` extension with groups
   named `APX_Underground_<Zone>` that carry ONLY `<usage name="APX_Underground_<Zone>"/>`
   (no Town/Village/Industrial/Military), 8 loot-points, `lootmax=6`.
2. Inject into live `mapgroupproto.xml` (before `</prototype>`), WITH BACKUP.
3. Bind T4 items in types.xml to `APX_Underground_*` (not `Underground_*`).
   Now T4 spawns EXCLUSIVELY in the 7 real zones.

Full recipe + verification regex: `references/underground-t4-exclusive-fix.md`.

## 4. Deterministic Build Pattern (prefer over subagents)

For structured XML game-data (types.xml, mapgroupproto, presets): generate
with `execute_code` (Python + `xml.etree` + `minidom`), NOT delegate_task
subagents. Free-tier models time out at 600s on large XML authoring; Python
writes 100+ items in <1s and is auditable.

Workflow:
1. `execute_code` inventory sweep (all mods → unique item count, categories,
   tiers, usages) — see `scripts/inventory_sweep.py`.
2. `execute_code` item generation (curated set, closed weapon chains).
3. `execute_code` audit loop (well-formed, orphaned-ammo, T4-underground-only,
   coast-escalation, dangling-distribution-refs) — see `scripts/loot_audit.py`.
4. Inject mapgroupproto extension (with backup).
5. Re-audit.

## 5. Audit Checklist (run after every build)

- [ ] all XMLs well-formed (`xml.etree.ElementTree.parse`)
- [ ] 0 orphaned ammo (every weapon has Ammo+Mag in SAME tier)
- [ ] T4 items: 100% `APX_Underground_*` (never plain `Underground_*`)
- [ ] Coast/Town escalation: 0 (no Tier3/4 at Coast/Town)
- [ ] distribution references: 0 dangling `APX_*` (every referenced classname
      exists in types.xml)
- [ ] backup exists before any live-map edit
- [ ] **CACHE INTEGRITY (before declaring "loot broken"):** if loot is missing
      after a types.xml/events.xml edit, check `storage_1/data/types.bin` (and
      `events.bin`) mtime vs the source xml. If the `.bin` is newer/stale, rename
      it (see §6) so DayZ rebuilds from the xml. `Restoring file types.bin` in the
      RPT = cache is shadowing your edit.
- [ ] **RED HERRING gate:** `Type does not exist` warnings for mods NOT in the
      active MOD_LIST are harmless — do not add mods or edit types.xml to silence
      them. Confirm the missing type's supplying mod with `ls -d Mods/@X` first.

## 6. CE `Unknown usage` / `cfglimitsdefinition.xml` Debugging (CRITICAL, learned 2026-07-18)

**Symptom:** Server RPT floods with `[CE] :: Unknown usage: 'Tier3'`, `'Tier4'`,
`'APX_Underground_Lopatino'`, etc. — sometimes hundreds of repeats at startup. The
loot for those usages is SILENTLY dropped (never spawns).

**Two files, one wins.** DayZ parses usage validity from:
- `cfglimitsdefinition.xml` (BASIS — this is what actually counts; the engine reads it)
- `cfglimitsdefinitionuser.xml` (USER override/append — often IGNORED or appended
  without replacing basis entries, so editing it alone does NOT fix Unknown-usage)

**Root cause pattern (the one that bit us):** `types.xml` references usages by a
NAME that does NOT exist as a `<usage>` in the basis file. Two common mismatch shapes:
1. **Prefix mismatch** — types.xml uses `<usage name="APX_Underground_Lopatino"/>`
   but the basis defines `<usage name="Underground_Lopatino"/>` (no `APX_` prefix).
   The names must match EXACTLY.
2. **`<value>` vs `<usage>`** — basis has `<value name="Tier3"/>` under `<valueflags>`
   (an ALIAS GROUP for combining usages), but types.xml uses `Tier3` as a standalone
   `<usage name="Tier3"/>`. A `<value>` is NOT a valid usage name; it must also appear
   as `<usage name="Tier3"/>` under `<usageflags>`.

**How to confirm which file wins (do NOT guess):** grep the running RPT for the
UN-prefixed name. If `Underground_Lopatino` (no APX_) is NOT in the Unknown list but
`APX_Underground_Lopatino` IS, the basis is being read and only the prefix is wrong →
fix the basis. If BOTH are Unknown, the user-file is overriding the basis entirely.

**Correct fix (the one that worked):**
Edit the BASIS `cfglimitsdefinition.xml` `<usageflags>` section — add the EXACT
names types.xml uses as `<usage name="X"/>` entries:
```xml
<!-- must match types.xml usage names EXACTLY -->
<usage name="APX_Underground_Lopatino"/>
<usage name="APX_Underground_Sobor"/>
<usage name="APX_Underground_Sevorgrad"/>
<usage name="APX_Underground_SeaPlatform"/>
<usage name="APX_Underground_Ocean"/>
<usage name="APX_Underground_Skalisty"/>
<usage name="APX_Underground_OilRig"/>
<usage name="Tier1"/>
<usage name="Tier2"/>
<usage name="Tier3"/>
<usage name="Tier4"/>
```
Do NOT waste a turn editing `cfglimitsdefinitionuser.xml` — it does not override the
basis for usage validity in this build.

**THE DEPLOY SCRIPT IS THE LAWFUL PATH — DO NOT HAND-PATCH THE LIVE TREE (learned the hard way, 2026-07-18).** There is a working deploy at `/home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot/deploy_live.py` that does backup + merge + validate against the LIVE `Server/mpmissions/dayzOffline.chernarusplus/` for ALL loot XMLs (types/events/cfgspawnabletypes/cfgeventgroups/cfgrandompresets/ce/cfgeconomycore). ~6 iterations were wasted this session hand-editing files directly in the live `mpmissions/.../db/` tree, producing stale/partial XMLs and a broken `cfgeventspawns.xml` (a `<event name="Loot"/></event>` mismatch tag from a bad merge). The correct workflow when the user says "fix the loot / deploy" is: edit the MOD SOURCE (`@Apocalyps3nd_Loot/*.xml` + `cfgeventspawns.xml`), THEN `cd /home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot && python3 deploy_live.py`. The script prints `DEPLOY SUCCESS` / problem count. If it crashes on validate, read the exception (usually a malformed XML you introduced in the MOD source) — fix the SOURCE, re-run, never hand-edit the deployed copy. The deploy script must also copy `cfgeventspawns.xml` (see DynEvent note below) — verify step 7 merges it, and if not, add a merge block for it (the vanilla file has `<eventposdef>` wrapping `<event name="X"><pos x/z/a/></event>` pairs). Full recipe in `references/deploy-live-script.md`.

**CRITICAL — MERGE vs REPLACE in deploy_live.py (the trap that cost ~10 restarts, 2026-07-18).** `backup_and_copy(..., merge=True)` is SAFE ONLY for `cfgspawnabletypes.xml` (additive item types, no baseline to lose). For ALL THREE of these it DESTROYS the Vanilla baseline and must be REPLACE:
  - `events.xml` MERGE: if the live file is already corrupted (only APX events, Vanilla gone), merge skips the APX (already "present") → file ends with only 2 events → RPT shows `Loaded 2 dynamic events` + APX "setup is invalid". The MOD `events.xml` MUST contain all 61 events (59 Vanilla + 2 APX) and be deployed as REPLACE.
  - `cfgeventspawns.xml` MERGE: emits malformed `<event name="Loot"/></event>` self-closing tag + drops 4 of 5 `<pos>` per APX event. Must be REPLACE with a MOD source holding the full `<eventposdef>`.
  - `cfglimitsdefinition.xml` MERGE: can drop/duplicate `<usageflags>` blocks → Unknown-usage persists. Must be REPLACE.
  - `types.xml` MOD source was APX-only (5252 types, NO vanilla Bandage/M4A1) → 113 "Type does not exist" + server loads only ~480 prototypes. The live types.xml MUST be UNION(Vanilla base, APX types) — see `references/deploy-merge-vs-replace-pitfalls.md` for the union recipe and the RPT verification (Bandage count ≥1, Type-does-not-exist ≈0).
Full detail + corrected deploy shape: `references/deploy-merge-vs-replace-pitfalls.md`.

**DynEvent "failed to determine spawner type" / "setup is invalid" (PROVEN CORRECT FORMAT, 2026-07-18):**
if `[DynEvent] "APX_WeaponCache" will be ignored :: failed to determine spawner type!`
OR `[CE][DE] DynamicEvent "APX_WeaponCache" setup is invalid, event will be disabled.`
appears, the `<event>` block in `events.xml` has the WRONG structure. TWO mistakes
were both tried and BOTH FAILED (even after a clean restart reading the new file):

  ❌ WRONG ATTEMPT 1 — comma-separated `<children>` + a `<spawn type="Loot" />` tag:
  ```xml
  <event name="APX_WeaponCache" nominal="20" ...>
    <spawn type="Loot" />
    <children>A6_AR15_Standard,A6_AK101,A6_AK105,...</children>
  </event>
  ```
  → still "setup is invalid". The `<spawn>` tag is NOT how DayZ 1.28 picks a spawner
  type, and comma-separated `<children>` is not the child syntax.

  ✅ CORRECT DayZ 1.28 format — explicit `<position>`, `<limit>`, `<flags>`, and
  `<children>` built from `<child>` elements (one per item, each with lootmin/max +
  min/max + type):
  ```xml
  <event name="APX_WeaponCache" nominal="20" min="10" max="30" lifetime="1800"
        restock="0" saferadius="100" distanceradius="150" limit="5" active="1">
    <position>fixed</position>
    <limit>mixed</limit>
    <flags deletable="0" init_random="0" remove_damaged="1"/>
    <children>
      <child lootmin="1" lootmax="3" min="1" max="3" type="A6_AR15_Standard"/>
      <child lootmin="1" lootmax="3" min="1" max="3" type="A6_AK101"/>
      <!-- ...one <child> per item, NOT comma-separated... -->
    </children>
  </event>
  ```
  - `<position>fixed</position>` → positions come from `cfgeventspawns.xml` (see below).
    `<position>random</position>` ALSO WORKS ONLY IF DayZ has valid random spawn points,
    which it does NOT for custom APX events without either `cfgeventspawns.xml` entries OR a
    built-in random pool — so `<position>fixed</position>` + `cfgeventspawns.xml` is the
    RELIABLE path. This was PROVEN: 6 restarts with malformed `<children>` / `<spawn>` tag /
    `<position>random</position>` all still printed "setup is invalid"; only the
    `<position>fixed</position>` + `<child>`-tags + `cfgeventspawns.xml` combo cleared it.
  - `<limit>mixed</limit>` + `<flags .../>` mirror the vanilla `VehicleHeliSpawn` shape.
  - Each item is its OWN `<child lootmin=.. lootmax=.. min=.. max=.. type="X"/>` — NOT a
    comma string, NOT a single `<spawn>` tag.
  - DO NOT add a `<spawn type="Loot"/>` tag — it does nothing useful in 1.28 and the
    event still reads as invalid. The spawner type is derived from the event structure,
    not a `<spawn>` element.

  **THE MISSING HALF — `cfgeventspawns.xml` (this is what the session missed for 6 restarts):** For `<position>fixed</position>` events, the actual map coordinates MUST live in `cfgeventspawns.xml` (mission root, NOT `db/`), as `<eventposdef>` wrapping one `<event name="APX_WeaponCache">` with one-or-more `<pos x=".." z=".." a=".."/>` children. If this file is MISSING or the APX `<event>` block is absent, DayZ cannot place the event → still "setup is invalid". The vanilla `VehicleHeliSpawn` works BECAUSE its `<pos>` entries exist in `cfgeventspawns.xml`. Correct shape:
  ```xml
  <?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
  <eventposdef>
    <event name="APX_WeaponCache">
      <pos x="7435.18" z="5785.13" a="0" />
      <pos x="4531.45" z="10251.34" a="0" />
      <!-- ...several spawn points... -->
    </event>
    <event name="APX_MedCache">
      <pos x="2201.77" z="8043.91" a="0" />
      <!-- ... -->
    </event>
  </eventposdef>
  ```
  This file is NOT auto-generated by `deploy_live.py` historically — you must add a merge/copy step for it (see `references/deploy-live-script.md`), or the APX events will keep failing even with perfect `events.xml`.

Verification: after restart, RPT must show NO `"APX_WeaponCache" will be ignored :: failed to determine spawner type` line (a clean boot simply omits it — there is no explicit "setup OK" line for valid events; absence of the warning IS the success signal). The cache note (events.bin) still applies — if you edited events.xml/cfgeventspawns.xml and it STILL shows invalid after a correct-format restart, the `events.bin` in `storage_1/data/` is shadowing it (see §6 cache trap). Rename it (reversible), restart, verify.

**THE `types.bin` CACHE OVERRIDE TRAP — THE REAL "NULL LOOT" ROOT CAUSE (bit us, 2026-07-18):**
If the server boots, CE init runs, but the MAP HAS NO LOOT, the prime suspect is
`storage_1/data/types.bin` shadowing `db/types.xml`. This is SEPARATE from and more
common than the `events.bin` trap above.

Diagnostic signature in the server RPT (read `Server/profile/DayZServer_x64_*.RPT`):
```
[CE][TypeSetup] :: 885 classes setuped...        # 885 = vanilla item classes, NOT 5252
[CE][Storage] Restoring file "...storage_1\data\types.bin".   # <-- "Restoring" = CACHE WINS
```
`Restoring file types.bin` means DayZ loaded the cached BINARY, not the freshly-edited
`types.xml`. Even if `db/types.xml` is perfect (5252 `<type>` entries, all `nominal>0`,
15177 `<usage>` flags present), the loot comes from the bin. If the bin was built from a
stale/wrong `types.xml` (e.g. the live-deploy xml differs from what you now see, or the
wipe did not regenerate it), the map spawns nothing.

**Confirm cache-vs-xml via mtime (do NOT guess):**
```
stat -c '%y' storage_1/data/types.bin     # cache
stat -c '%y' db/types.xml                 # source
# If types.bin is NEWER than types.xml AND the loot is wrong → the bin is stale shadow.
# Also confirm a fresh wipe really wrote the bin: storage_1 dir mtime should be ~start time,
# and types.bin mtime should be AFTER that (DayZ rebuilds it on boot).
```
If `types.xml` is correct but `types.bin` is wrong/stale → the bin is the problem.

**Fix (reversible — RENAME, do NOT `rm`):** rename the cache files so DayZ is forced to
rebuild from `types.xml` on next boot. Renaming (not deleting) keeps a fallback:
```bash
D=.../dayzOffline.chernarusplus/storage_1/data
mv "$D/types.bin"  "$D/types.bin.bak_$(date +%H%M%S)"
mv "$D/types.001"  "$D/types.001.bak_$(date +%H%M%S)"   # also the .001/.002 rollbacks
mv "$D/types.002"  "$D/types.002.bak_$(date +%H%M%S)"
# leave storage_1/data/* OTHER files (vehicles/zombies/buildings state) alone
```
Then restart the server. DayZ rebuilds `types.bin` from the (good) `types.xml` → loot spawns.
User explicitly blocked an unprompted `rm` of these — always rename + get approval, or
rename without deleting (reversible) and tell the user where the `.bak` lives.

**`cfgeconomycore.xml` FORMAT — THE BROKEN vs CORRECT DISTINCTION (override the old note).**
The OLD note claimed the bare `<economy><rootclasses/>` format was "normal — NOT the bug"
and that adding `<files>` was a dead end. That note was WRONG for this host's final state.
The bare `<economy>/<rootclasses>/<class>` format produces `0 root classes` and kills CE
entirely. The CORRECT DayZ 1.28 format is `<economycore>/<classes>/<rootclass>` — see the
FILE-LOCATION + FORMAT TRAP section above for the exact correct XML and the diagnostic
sequence. **If the RPT shows `0 root classes` or `885 classes` (vanilla only), the
cfgeconomycore.xml format IS the bug — rewrite it to `<economycore>/<classes>/<rootclass>`.**
Do NOT add a `<files>` tag (that part of the old note holds: DayZ auto-loads types.xml from
the mission root by default path) — but DO fix the rootclass format. There are TWO copies
(mission root + `db/ce/`); DayZ reads `db/ce/cfgeconomycore.xml` FIRST, so fix that one.

**RED HERRING — "Type does not exist" for intentionally-excluded mods:** the RPT may show
dozens of `Type 'Wendigo_Fur' will be ignored. (Type does not exist)` for items from mods
that are NOT in the active MOD_LIST (e.g. `@WendigoCreature`, `@AJs Creatures V2`,
`@AmmunitionExpansion` referenced by a types.xml built for a different mod set). The user
explicitly stated "es LIEGT NICHT AN DEN 3 ADDONS! AT ALL!" — these warnings are HARMLESS
when the mod is intentionally absent. Do NOT chase them and do NOT add those mods to the
list just to silence the warnings. The real NULL-loot cause is the `types.bin` cache above,
not the missing mods. (Verify which mod would supply a missing type with
`ls -d /home/alca/games/DayZ/Mods/@ModName` before assuming a gap.)

**THE FILE-LOCATION + FORMAT TRAP — THE REAL "NULL LOOT + NO CLIENT CONNECT" ROOT CAUSE (2026-07-18, FINAL, PROVEN).**

After chasing types.bin cache, events.bin cache, `<files>` tags, and excluded-mod red herrings, the ACTUAL blockers were TWO AND BOTH WERE IN THE CONFIG FILES THEMSELVES, not in cache:

**Blocker A — files in the wrong directory.** DayZ 1.28 loads `types.xml`, `events.xml`, `messages.xml`, `globals.xml`, `economy.xml`, `cfgspawnabletypes.xml`, `cfglimitsdefinition.xml` from the **MISSION ROOT** (`dayzOffline.chernarusplus/`), NOT from `db/`. If they sit only in `db/`, DayZ never reads them → only the 885 vanilla classes load → NULL loot → server hangs the mission init → **client cannot connect**.

```bash
# DayZ 1.28 reads THESE from the mission root:
dayzOffline.chernarusplus/
  types.xml            # <-- MUST be here (5252 types), NOT db/types.xml
  events.xml
  messages.xml
  globals.xml
  economy.xml
  cfgspawnabletypes.xml
  cfglimitsdefinition.xml
  cfgeconomycore.xml
```

**Blocker B — WRONG `cfgeconomycore.xml` FORMAT.** This is the subtle one. The broken format that produces `0 root classes` / `885 classes` is:

```xml
<!-- BROKEN — DayZ 1.28 does NOT parse this; results in 0 root classes -->
<economy>
  <rootclasses default="Inventory_Base">
    <class name="DefaultWeapon"/>
    ...
  </rootclasses>
  <dynamic dyn_radius="30" .../>
</economy>
```

The CORRECT DayZ 1.28 format is:

```xml
<!-- CORRECT — DayZ parses this; 8 root classes, loads all 5252 types -->
<economycore>
  <classes>
    <rootclass name="DefaultWeapon" />
    <rootclass name="DefaultMagazine" />
    <rootclass name="Inventory_Base" />
    <rootclass name="HouseNoDestruct" reportMemoryLOD="no" />
    <rootclass name="SurvivorBase" act="character" reportMemoryLOD="no" />
    <rootclass name="DZ_LightAI" act="character" reportMemoryLOD="no" />
    <rootclass name="CarScript" act="car" reportMemoryLOD="no" />
    <rootclass name="BoatScript" act="car" reportMemoryLOD="no" />
  </classes>
  <defaults>
    <default name="dyn_radius" value="30" />
    <default name="dyn_smin" value="0" />
    <default name="dyn_smax" value="0" />
    <default name="dyn_dmin" value="1" />
    <default name="dyn_dmax" value="5" />
  </defaults>
</economycore>
```

The two tags that MUST be right: `<economycore>` (not `<economy>`), `<classes>`+`<rootclass>` (not `<rootclasses>`+`<class>`). If the file uses the broken format, the RPT shows:
```
[CE][CoreData] :: 0 root classes, 0 defaults, 0 updaters...   # or "8 root classes" but with 0 types
!!! [CE][CoreData] :: ZERO root classes - SPAWN WILL NOT WORK
[CE][TypeSetup] :: 0 classes setuped...   (or 885 — vanilla only)
```

**THERE ARE TWO cfgeconomycore.xml files — DayZ reads the one in `db/ce/` first.** On this host both existed:
- `dayzOffline.chernarusplus/cfgeconomycore.xml` (mission root)
- `dayzOffline.chernarusplus/db/ce/cfgeconomycore.xml`  ← **this is the one DayZ actually consumes**

If the `db/ce/cfgeconomycore.xml` has the BROKEN `<economy>/<rootclasses>` format (406 bytes, default from the mod), it OVERRIDES the root one and CE dies with 0/8 root classes. **Fix BOTH** to the correct `<economycore>/<classes>/<rootclass>` format.

**Diagnostic sequence when loot is empty / client cannot connect — DO THIS, in order:**
1. Read the FULL server RPT (see §14 — do NOT grep-excerpt). Find `[CE][TypeSetup] :: N classes`.
   - N == 885 (or 0) and types.xml is 5252 → files are in the wrong place OR cfgeconomycore format is broken. Go to step 2+3.
   - N == 5252 → files loaded fine; problem is cache (§6) or usage (§6).
2. **Location check:** `ls dayzOffline.chernarusplus/types.xml` — if MISSING, `cp db/types.xml ./types.xml` (and events.xml, messages.xml, globals.xml, economy.xml). DayZ reads these from the ROOT.
3. **Format check:** `head -12 db/ce/cfgeconomycore.xml` — if it starts `<economy>` or has `<rootclasses>`, it is BROKEN. Rewrite to the CORRECT format above (both root + db/ce/ copies).
4. If present + correct format but loot still empty → `storage_1/data/types.bin` shadowing? (§6 cache trap) — rename the bin.
5. `Unknown usage` flood → `cfglimitsdefinition.xml` basis (§6).
6. `Type does not exist` for excluded mods → red herring, ignore (§6).

**THE `<files>` TAG HYPOTHESIS WAS A DEAD END — DO NOT ADD IT.** DayZ auto-loads `types.xml`/`events.xml` from the mission root by default path; you do NOT register them via `<files>` in cfgeconomycore.xml. Adding `<files>` does nothing and can break parsing. Fix location (step 2) + format (step 3), not `<files>`.

**Verification after fix:** restart server, read the FULL RPT, expect:
```
[CE][CoreData] :: 8 root classes, 18 defaults, 0 updaters...
[CE][TypeSetup] :: 5252 classes setuped...   # NOT 885, NOT 0
[CE][offlineDB] :: Loaded 2 dynamic events N total types.   # N > 0
[DynEvent] "APX_WeaponCache" setup OK   # NOT "setup is invalid"
```
And the client connects.

**THE `events.bin` CACHE OVERRIDE TRAP (bit us — XML edit appeared to do nothing):**
DayZ caches the DynEvent config in `mpmissions/dayzOffline.chernarusplus/storage_1/data/events.bin`.
If `events.bin` exists, the server loads the CACHED binary, NOT your freshly-edited
`events.xml`. Symptom: you add `<spawn type="Loot"/>` to `events.xml`, restart, and
STILL get `failed to determine spawner type` — because the cache won.

**Fix:** delete `events.bin` (ONLY that file, not the whole storage dir) so DayZ
re-parses `events.xml` on next boot:
```
rm -f .../storage_1/data/events.bin
```
This is a CACHE DELETE — needs EXPLICIT USER APPROVAL before running (the user blocked
an unprompted `rm` of it). Same pattern applies to other CE configs cached as `.bin`
(types.bin, cfgspawnabletypes.bin, etc.) — if an XML edit "does nothing", the
corresponding `.bin` in `storage_1/data/` is shadowing it. Delete the specific `.bin`,
restart, verify. Do NOT delete the entire `storage_1/data/` (that wipes all live loot
state — vehicles, zombies, buildings).

**Verification:** restart server, grep RPT for `Unknown usage:`. Expect ZERO
`APX_Underground_*` / `Tier*` Unknown lines. (Note: `DEBUG_TEST_USAGE` Unknown lines
may persist if they come from another mod's injected types.xml — those are harmless
unless you intend to spawn items with that usage.)


<!-- moved to references/moved-sections.md: ## 9. SOURCE-OF-TRUTH + BLIND-ACTION PITFALLS (learned 2026-07-18, hard corrections) -->


<!-- moved to references/moved-sections.md: ## 10. DayZ CLIENT under Proton — boot/hang debugging (learned 2026-07-18) -->

## 11. Process-kill terminal trap (DayZ under Proton)

`pkill -f DayZServer_x64.exe` / `kill <pid>` from the agent shell KILLS THE AGENT'S
OWN TERMINAL (exit -15 / -9). The DayZ process was launched from a shell in the same
process tree (via `bash start_script.sh` or a prior agent `terminal` call), so killing
it signals the whole tree including the Hermes shell.

SAFE alternatives:
- Detached subshell: `(setsid bash -c 'for p in $(pgrep -f "DayZServer_x64.exe"); do kill -9 "$p"; done' >/dev/null 2>&1 &)` — isolated PGID, does not reach the agent shell.
- Or let the user close it on-screen (Alt+F4 / window close) — cleanest.
- `process` tool `kill` only works if the process was started by THIS agent's
  `terminal(background=true)` AND is still tracked; a Proton-respawned child is NOT.

Also: `bash script.sh` with `set -euo pipefail` + a RELATIVE `DAYZ_CLIENT="DayZ_x64.exe"`
fails when launched from a non-client cwd (e.g. a `setsid` detached subshell). Use
ABSOLUTE paths for `DAYZ_CLIENT`/`DAYZ_SERVER` AND `cd "$(dirname "$0")"` right after
`set -euo pipefail` (BEFORE the `ensure_exists` checks), or the script dies with
"not found at DayZ_x64.exe" / "server config not found".


<!-- moved to references/moved-sections.md: ## 12. Unified client/server start scripts (working pattern, 2026-07-18) -->

## 8. Live Deploy + Operations — CORRECTION (2026-07-18)

The earlier Zen2-crash narrative in §8 is OUTDATED for THIS host's current config.
In this session the server booted SUCCESSFULLY under **Proton - Experimental**
(compatdata 221100) on the local box — `SteamGameServer_Init SUCCESS`, mission loaded,
player connected. The actual blockers that WERE real (and got fixed) were:
1. Wrong source tree built (junk `VanillaPPMap` instead of `Apocalypse`) — see §9.
2. Missing script types in the CLIENT 5_Mission tree: `ComboBoxWidget`→`XComboBoxWidget`,
   and a method body with NO signature (`Respawn.c` `Update()` block) — see §13.
3. CE `Unknown usage` + DynEvent spawner — see §6.

So: do NOT assume the server "can't boot due to Zen2". Isolate by booting the real
tree under Proton - Experimental and reading the actual RPT. The boot is SLOW (minutes)
but that is normal, not a crash.


<!-- moved to references/moved-sections.md: ## 14. THE "dynamic groups: 0" RED HERRING + ASYNC LOOT SPAWN WINDOW (PROVEN 2026-07-18) -->

## 13. Script compile blockers (Enforce-Script, DayZ 1.28)

When `Can't compile "Mission" script module!` appears:
- **Widget type renames:** Vanilla renamed `ComboBoxWidget` → `XComboBoxWidget`.
  Grep all `*.c` client GUI files for `\bComboBoxWidget\b` and replace with
  `XComboBoxWidget`. `PanelWidget` is NOT a vanilla class — cast panels to generic
  `Widget` (only the TYPE usage, NOT `PanelWidgetClass` in `.layout` files, which is
  the correct layout class name and must stay).
- **Method body without signature:** a `{` block with `super.Method(args);` but no
  `override void Method(...)` header = "Unexpected scope" / "Syntax error". Find the
  class (`modded class X extends UIScriptedMenu`), add the missing
  `override void Update(float timeslice) {` before the orphan block.
- Verify with the REAL criterion: `grep -c "SCRIPT    (E)"` on the fresh
  `Server/profile/script_*.log` must be 0 AND "Failed to load mission scripts" absent.
  Port-bind is NOT success (zombie window during load).



After build, run `scripts/loot_audit.py` against the mod folder. Expect
`>>> FULL AUDIT PASS`. Then confirm the 7 `APX_Underground_*` groups exist
in live `mapgroupproto.xml` (exclusive=True).


<!-- moved to references/moved-sections.md: ## 8. Live Deploy + Operations (DayZ Server under Wine/Linux) -->


<!-- moved to references/moved-sections.md: ## Linked files -->
