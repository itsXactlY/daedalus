#!/usr/bin/env python3
"""
generate_apx_full.py — MANIFEST -> 7 XMLs (Single Source of Truth builder)
Reads APX_MANIFEST_FULL.json and generates ALL loot XMLs for @Apocalyps3nd_Loot.
NEVER hand-edit the generated XMLs. Rename = edit manifest + re-run this.

Outputs:
  types.xml              (all items, re-balanced tiers + APX_Underground usages)
  ce/cfgeconomycore.xml  (rootclasses)
  mapgroupproto_Underground_T4.xml (7 exclusive T4 zones)
  cfgspawnabletypes.xml  (object attachments)
  cfgrandompresets.xml   (tier-weighted cargo)
  events.xml             (dynamic caches)
  cfgeventgroups.xml     (train wreck)
"""
import json, os
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

BASE = "/home/alca/games/DayZ/Mods/@Apocalyps3nd_Loot"

def pretty(root):
    return '\n'.join([l for l in minidom.parseString(tostring(root)).toprettyxml(indent='  ').split('\n') if l.strip()])

M = json.load(open(os.path.join(BASE, "APX_MANIFEST_FULL.json")))
items = M["items"]

# === 1. TYPES.XML ===
types = Element("types")
for it in items:
    t = SubElement(types, "type", name=it["name"])
    SubElement(t, "nominal").text = str({"Tier1":10,"Tier2":8,"Tier3":6,"Tier4":4}[it["tier"]])
    SubElement(t, "min").text = str({"Tier1":5,"Tier2":4,"Tier3":3,"Tier4":2}[it["tier"]])
    SubElement(t, "restock").text = "0"
    SubElement(t, "lifetime").text = str({"Tier1":14400,"Tier2":10800,"Tier3":7200,"Tier4":3600}[it["tier"]])
    SubElement(t, "quantmin").text = "-1"
    SubElement(t, "quantmax").text = "-1"
    SubElement(t, "cost").text = str({"Tier1":100,"Tier2":316,"Tier3":1000,"Tier4":3162}[it["tier"]])
    SubElement(t, "flags", deleted="0", init_inventory="0", no_drop="0")
    SubElement(t, "category", name=it["cat"])
    SubElement(t, "usage", name=it["tier"])
    for u in it["usages"]:
        SubElement(t, "usage", name=u)
    if it["cat"] == "tools":
        SubElement(t, "value", name=it["tier"], type="0")
print(f"[1/7] types.xml: {len(items)} items")

# === 2. CE ===
ce = Element("economy")
rootcls = SubElement(ce, "rootclasses", default="Inventory_Base")
for rc in ["DefaultWeapon","Magazine","Inventory_Base","SurvivorBase","DZ_LightAI","CarScript","BoatScript"]:
    SubElement(rootcls, "class", name=rc)
SubElement(ce, "dynamic", dyn_radius="30", dyn_smin="0", dyn_smax="-1", dyn_dmin="1", dyn_dmax="5")
os.makedirs(os.path.join(BASE,"ce"), exist_ok=True)
with open(os.path.join(BASE,"ce","cfgeconomycore.xml"),"w") as f:
    f.write(pretty(ce))
print(f"[2/7] cfgeconomycore.xml: 7 rootclasses")

# === 3. MAPGROUPPROTO EXTENSION ===
ext = Element("mapgroupproto")
for z in ["Lopatino","Sobor","Sevorgrad","SeaPlatform","Ocean","Skalisty","OilRig"]:
    g = SubElement(ext, "group", name=f"APX_Underground_{z}", lootmax="6")
    SubElement(g, "usage", name=f"APX_Underground_{z}")
    for i in range(8):
        SubElement(g, "pos", x=str(4000+i*20), y="140", z=str(9000+i*15), a="0")
        SubElement(SubElement(g, "cargo"), "item", name=f"APX_Underground_{z}_Loot", chance="1.0", max="6")
with open(os.path.join(BASE,"mapgroupproto_Underground_T4.xml"),"w") as f:
    f.write(pretty(ext))
print(f"[3/7] mapgroupproto_Underground_T4.xml: 7 zones")

# === 4. CFGSPAWNABLETYPES ===
spawn = Element("spawnabletypes")
obj_map = {"HouseBlock":["clothes","food","tools"],"IndustrialShelter":["tools","containers"],
           "MilitaryTent":["weapons","ammo","magazine"],"Farm":["food","tools"],"Village":["clothes","food"]}
for obj, cats in obj_map.items():
    st = SubElement(spawn, "type", name=obj)
    att = SubElement(st, "attachments", chance="0.3")
    for cat in cats:
        for ci in [it["name"] for it in items if it["cat"]==cat and it["tier"] in ("Tier1","Tier2")][:10]:
            SubElement(att, "item", chance="0.1", name=ci)
print(f"[4/7] cfgspawnabletypes.xml: {len(obj_map)} objects")

# === 5. CFGRANDOMPRESETS ===
presets = Element("randompresets")
for tier in ["Tier1","Tier2","Tier3","Tier4"]:
    rp = SubElement(presets, "randompreset", name=f"APX_{tier}_Cargo")
    cargo = SubElement(rp, "cargo", chance="0.2")
    for ti in [it["name"] for it in items if it["tier"]==tier][:20]:
        SubElement(cargo, "item", chance="0.05", name=ti)
print(f"[5/7] cfgrandompresets.xml: 4 tier-presets")

# === 6. EVENTS ===
events = Element("events")
for name, child_list, tier in [("APX_WeaponCache",["weapons","ammo","magazine"],"Tier3"),
                                ("APX_MedCache",["medicine","food"],"Tier1")]:
    ev = SubElement(events, "event", name=name, nominal="20", min="10", max="30", lifetime="1800",
                    restock="0", saferadius="100", distanceradius="150", limit="5", active="1")
    children = [it["name"] for it in items if it["cat"] in child_list and it["tier"]==tier][:10]
    SubElement(ev, "children").text = ",".join(children)
print(f"[6/7] events.xml: 2 events")

# === 7. CFGEVENTGROUPS ===
groups = Element("eventgroups")
g = SubElement(groups, "group", name="APX_Train_Cherno")
for cx,cy,cz in [(4120,140,9270),(4125,140,9275),(4115,140,9265)]:
    eg = SubElement(g, "event", pos=f"{cx} {cy} {cz}", init_random="1", max="3", min="1")
    for wi in [it["name"] for it in items if it["tier"]=="Tier4" and it["cat"]=="weapons"][:3]:
        SubElement(eg, "child", type="Item", name=wi, lootmax="1")
print(f"[7/7] cfgeventgroups.xml: APX_Train_Cherno")

for fn, root in [("types.xml",types),("cfgspawnabletypes.xml",spawn),("cfgrandompresets.xml",presets),
                 ("events.xml",events),("cfgeventgroups.xml",groups)]:
    with open(os.path.join(BASE,fn),"w") as f:
        f.write(pretty(root))

print("\n>>> ALL XMLs GENERATED FROM MANIFEST")
