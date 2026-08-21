#!/usr/bin/env python3
"""DayZ loot build audit loop — runs after every build.
Checks: well-formed XML, orphaned ammo (broken weapon chains), T4 exclusive
to APX_Underground_*, no Coast/Town escalation, no dangling distribution refs.
Usage: python3 loot_audit.py [MOD_DIR]
Exits non-zero on FAIL (CI-friendly).
"""
import os, sys
import xml.etree.ElementTree as ET

BASE = sys.argv[1] if len(sys.argv) > 1 else "/home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot"
problems = []

# 1. Load types
root = ET.parse(os.path.join(BASE, "types.xml")).getroot()
items = {t.get("name"): t for t in root.findall("type")}

# tier map
tiers = {}
for n, t in items.items():
    v = t.find("value")
    tiers[n] = v.get("name") if v is not None else None

# 2. Orphaned ammo: every ammo must have a mag in same tier
for n, t in items.items():
    c = t.find("category")
    if c is not None and c.get("name") == "ammo":
        cal = n.replace("APX_Ammo_", "")
        tier = tiers[n]
        mag_ok = any(cal in m and tiers.get(m) == tier for m in items if "Mag" in m)
        if not mag_ok:
            problems.append(f"orphaned ammo: {n}")

# 3. T4 must be APX_Underground_* only
for n, t in items.items():
    if tiers[n] == "Tier4":
        usages = [u.get("name") for u in t.findall("usage")]
        if any(not u.startswith("APX_Underground_") for u in usages):
            problems.append(f"T4 not exclusive APX_Underground: {n}")

# 4. Coast/Town escalation
for n, t in items.items():
    usages = [u.get("name") for u in t.findall("usage")]
    tv = tiers[n]
    if ("Coast" in usages or "Town" in usages) and tv in ("Tier3", "Tier4"):
        problems.append(f"coast escalation: {n} ({tv})")

# 5. well-formed all xmls
for f in ["types.xml", "cfgspawnabletypes.xml", "cfgrandompresets.xml",
          "events.xml", "cfgeventgroups.xml", "ce/cfgeconomycore.xml",
          "mapgroupproto_Underground_T4.xml"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        try:
            ET.parse(p)
        except Exception as e:
            problems.append(f"parse fail {f}: {e}")

# 6. dangling distribution refs (APX_ only)
for f in ["cfgspawnabletypes.xml", "cfgrandompresets.xml", "events.xml", "cfgeventgroups.xml"]:
    p = os.path.join(BASE, f)
    if not os.path.exists(p):
        continue
    r = ET.parse(p).getroot()
    for el in r.iter():
        if el.tag in ("item", "child"):
            nm = el.get("name", "") or el.get("type", "")
            if nm.startswith("APX_") and nm not in items:
                problems.append(f"dangling {f}: {nm}")

total = len(items)
tcount = {}
for n, tv in tiers.items():
    tcount[tv] = tcount.get(tv, 0) + 1
print(f"FULL AUDIT: {total} items | Tiers: {tcount} | problems={len(problems)}")
for p in problems[:30]:
    print("  -", p)
if problems:
    print(">>> FULL AUDIT FAIL")
    sys.exit(1)
print(">>> FULL AUDIT PASS")
