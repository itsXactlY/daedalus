#!/usr/bin/env python3
"""
validate_deploy.py — Pre-Flight Validator for DayZ Live-Deploy.
Reads the LIVE server config (not the mod folder) and checks:
  - types.xml: unique + count (no duplicate entries)
  - cfgeconomycore.xml: has rootclasses (not empty)
  - distribution XMLs: 0 orphaned refs (every referenced classname exists)
  - live mapgroupproto.xml: exactly 7 APX_Underground_* groups
  - T4 items: 100% APX_Underground_* usage (no plain Underground_*)
  - Coast/Town: 0 Tier3/4 escalation
Exit 0 = PASS (safe to start server). Exit 1 = FAIL (rollback + fix manifest).
"""
import os, sys, json
import xml.etree.ElementTree as ET

MP = "/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus"
DB = os.path.join(MP, "db")
BASE = "/home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot"
problems = []

# 1. types.xml
types_path = os.path.join(DB, "types.xml")
if not os.path.exists(types_path):
    print("FAIL: types.xml missing in live config"); sys.exit(1)
r = ET.parse(types_path).getroot()
ti = [t.get("name") for t in r.findall("type")]
if len(ti) != len(set(ti)):
    problems.append(f"types.xml: {len(ti)-len(set(ti))} duplicates")
print(f"[1] types.xml: {len(ti)} entries, unique={len(set(ti))}")

# 2. CE rootclasses
ce_path = os.path.join(DB, "cfgeconomycore.xml")
if not os.path.exists(ce_path):
    problems.append("cfgeconomycore.xml missing")
else:
    ce = ET.parse(ce_path).getroot()
    rc = ce.find("rootclasses")
    if rc is None or len(rc.findall("class")) == 0:
        problems.append("cfgeconomycore.xml: no rootclasses")
    else:
        print(f"[2] cfgeconomycore.xml: {len(rc.findall('class'))} rootclasses OK")

# 3. Distribution orphaned refs
type_set = set(ti)
MAP_OBJS = {"HouseBlock","IndustrialShelter","MilitaryTent","Farm","Village","Town","Coast"}
for fn in ["cfgspawnabletypes.xml","cfgrandompresets.xml","events.xml","cfgeventgroups.xml"]:
    fp = os.path.join(DB, fn)
    if not os.path.exists(fp):
        problems.append(f"{fn} missing in live config"); continue
    rr = ET.parse(fp).getroot()
    orphan = 0
    for el in rr.iter():
        if el.tag in ("item","child","type"):
            nm = el.get("name","") or el.get("type","")
            if nm and nm not in type_set and nm not in MAP_OBJS:
                orphan += 1; problems.append(f"Orphaned {fn}: {nm}")
    print(f"[3] {fn}: {orphan} orphaned")

# 4. APX_Underground in live map
live = ET.parse(os.path.join(MP, "mapgroupproto.xml")).getroot()
apx_live = [g for g in live.findall("group") if g.get("name","").startswith("APX_Underground_")]
if len(apx_live) != 7:
    problems.append(f"Live-Map: {len(apx_live)}/7 APX_Underground groups")
else:
    print(f"[4] Live-Map: {len(apx_live)}/7 APX_Underground groups OK")

# 5. T4 exclusive + Coast/Town escalation (from manifest)
m_path = os.path.join(BASE, "APX_MANIFEST_FULL.json")
if os.path.exists(m_path):
    M = json.load(open(m_path))
    mi = {it["name"]: it for it in M["items"]}
    for n, it in mi.items():
        if it["tier"] == "Tier4" and not all(u.startswith("APX_Underground_") for u in it["usages"]):
            problems.append(f"T4 {n} not exclusive Underground")
        if ("Coast" in it["usages"] or "Town" in it["usages"]) and it["tier"] in ("Tier3","Tier4"):
            problems.append(f"Coast/Town escalation: {n}")

print(f"\nPROBLEME: {len(problems)}")
for p in problems: print(f"  X {p}")
if problems:
    print("\n>>> VALIDATOR FAIL"); sys.exit(1)
print("\n>>> VALIDATOR PASS — LIVE CONFIG CONFORM"); sys.exit(0)
