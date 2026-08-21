# Full Multi-Mod Inventory Sweep (DayZ)

When the user says "alle mods durchgehen" / "jedes modpack", do NOT guess.
Sweep the disk deterministically.

## Method (execute_code, tolerant parser)
Vanilla + mod XML is often malformed for strict parsers (multiple roots,
HTML-comment residue in BBP_types.xml / newtypes.xml). Use a regex-tolerant
extractor instead of `ET.parse`:

```python
import os, glob, re
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

MODS = "/home/alca/games/DayZ/Mods"
def parse_tolerant(path):
    with open(path, errors="ignore") as f: c = f.read()
    blocks = re.findall(r"<type\b[^>]*>.*?</type>|<type\b[^>]*/>", c, re.DOTALL)
    out = []
    for b in blocks:
        m = re.search(r'name="([^"]+)"', b)
        if not m: continue
        cat = None
        cm = re.search(r'<category\b[^>]*name="([^"]+)"', b)
        if cm: cat = cm.group(1)
        out.append((m.group(1), cat))
    return out

sources = set()
for pat in ["types.xml","*types.xml","*spawnabletypes*.xml"]:
    sources |= set(glob.glob(os.path.join(MODS,"@*","**",pat), recursive=True))
    sources |= set(glob.glob(os.path.join(MODS,"@*",pat)))
sources = [s for s in sources if "@Apocalyps3nd_Loot" not in s]  # exclude our build
sources = [s for s in sources if re.search(r"(types|spawnable|loot|ce|economy)",
                                            os.path.basename(s), re.I)]

mod_stats = defaultdict(int)
all_items = defaultdict(set)
cat_counter = Counter()
for f in sources:
    mod = f.split("@")[1].split("/")[0]
    for name, cat in parse_tolerant(f):
        mod_stats[mod] += 1
        all_items[name].add(mod)
        if cat: cat_counter[cat] += 1
```

## What this reveals (Apocalyps3nd case)
590 unique items over 10 mods: MuchStuffPack 304, Forward Operator Gear 92,
BaseBuildingPlus 81, DrugsPlus 44, BanditAi 31, MaharlikaPH_Boats 23,
CJ187-LootChest 20, VirtualGarage 3, CodeLock 1, TJSscreen 1, Wendigo 1.
Categories: tools 102, clothes 71, containers 27, food 6, weapons 2.

## Coverage gap analysis
Compare plate categories/mods vs your curated build (APX_*). Missing categories
(e.g. `containers`) and uncovered mod-areas (Boats, BaseBuilding, Drugs,
Lock/Screen, Garage) become the extension set. Build APX_* equivalents for each
so the rebuild covers EVERYTHING, not just weapons.

## Notes
- BanditAi / Wendigo items are SERVER AI, not loot — do not replicate as APX_ loot.
- Trader currency (MoneyRuble) and Banking (AdvancedBanking) are economy systems,
  not spawnable loot classes — note but don't duplicate.
- Save raw inventory as JSON (`MOD_INVENTORY_FULL.json`) for later diffing.
