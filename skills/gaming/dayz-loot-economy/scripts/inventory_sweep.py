#!/usr/bin/env python3
"""DayZ multi-mod inventory sweep — deterministic, tolerant parser.
Scans all @Mods types*.xml / *spawnabletypes*.xml, reports unique item
count per mod, categories, tiers, usages. Excludes the build mod itself.
Usage: python3 inventory_sweep.py [MODS_DIR]
"""
import os, glob, re, sys, json
from collections import defaultdict, Counter

MODS = sys.argv[1] if len(sys.argv) > 1 else "/home/alca/games/DayZ/Mods"
BUILD_MOD = "@Apocalyps3nd_Loot"

def parse_tolerant(path):
    with open(path, errors="ignore") as f:
        c = f.read()
    blocks = re.findall(r"<type\b[^>]*>.*?</type>|<type\b[^>]*/>", c, re.DOTALL)
    out = []
    for b in blocks:
        m = re.search(r'name="([^"]+)"', b)
        if not m:
            continue
        cat = None
        cm = re.search(r'<category\b[^>]*name="([^"]+)"', b)
        if cm:
            cat = cm.group(1)
        tier = re.findall(r'<value\b[^>]*name="(Tier\d)"', b)
        usage = re.findall(r'<usage\b[^>]*name="([^"]+)"', b)
        out.append((m.group(1), cat, tier, usage))
    return out

sources = set()
for pat in ["types.xml", "*types.xml", "*spawnabletypes*.xml"]:
    sources |= set(glob.glob(os.path.join(MODS, "@*", "**", pat), recursive=True))
    sources |= set(glob.glob(os.path.join(MODS, "@*", pat)))
sources = [s for s in sources if BUILD_MOD not in s]
sources = [s for s in sources if re.search(r"(types|spawnable|loot|ce|economy)",
                                            os.path.basename(s), re.I)]

mod_stats = defaultdict(int)
all_items = defaultdict(set)
cat_counter, tier_counter, usage_counter = Counter(), Counter(), Counter()
for f in sources:
    mod = f.split("@")[1].split("/")[0]
    for name, cat, tier, usage in parse_tolerant(f):
        mod_stats[mod] += 1
        all_items[name].add(mod)
        if cat:
            cat_counter[cat] += 1
        for t in tier:
            tier_counter[t] += 1
        for u in usage:
            usage_counter[u] += 1

print(f"Sources: {len(sources)} | Unique items: {len(all_items)}")
print("Mod breakdown:")
for mod, c in sorted(mod_stats.items(), key=lambda x: -x[1]):
    print(f"  {mod:30s} {c}")
print("Categories:", dict(cat_counter))
print("Tiers:", dict(sorted(tier_counter.items())))
print("Top usages:", dict(usage_counter.most_common(12)))

out = {
    "total_unique": len(all_items),
    "mods": dict(mod_stats),
    "categories": dict(cat_counter),
    "tiers": dict(tier_counter),
    "usages": dict(usage_counter),
}
with open(os.path.join(os.path.dirname(__file__), "MOD_INVENTORY_FULL.json"), "w") as fp:
    json.dump(out, fp, indent=2)
print("Saved MOD_INVENTORY_FULL.json")
