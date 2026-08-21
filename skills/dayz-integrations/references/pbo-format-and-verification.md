# PBO File Format and Verification

When verifying whether a packed `.pbo` actually contains the source files you
expect (after a build, after a mod rename, after outsourcing to a new host),
the binary PBO format has non-obvious details that will silently mislead you
if you don't know them. This reference documents the format and a minimal
Python parser.

## Format (DayZ PBO)

```
Offset  Content
------  ----------------------------------------------------------------
  0     0x00            prefix byte
  1-4   "sreV"          4-byte signature
  5-20  16 × 0x00       padding (the dayz-dev_tools writer leaves 16 zeros)
21+     properties block — sequence of (key\0value\0); terminated by
        empty key (a lone \0). 1 property in PBOs from dayz_dev_tools:
        dayz-dev-tools = v1.10.dev0 - https://dayz-dev-tools.readthedocs.io/
+       file table — sequence of (filename\0 + 4 bytes mime + 4×uint32);
        terminated by empty filename (a lone \0). Each uint32 is
        (original_size, reserved, time_stamp, data_size). The 4-byte
        mime is a literal 4 bytes, not a uint32.
+       data blocks (concatenated file data, each followed by 4-byte
        checksum)
```

## CRITICAL: paths use BACKSLASH, not forward slash

The PBO stores paths with backslashes (Windows convention):

- CORRECT: `scripts\5_Mission\missionGameplay.c`
- WRONG: `scripts/5_Mission/missionGameplay.c` (forward slash) — WILL NOT MATCH

**This bit me hard in practice:** I wrote a PBO inspector that checked for
`scripts/5_Mission/missionGameplay.c` and got "not found", then reported
"all my .c files are missing from the PBO". In fact the PBO had all 90
.c scripts — they were just stored with backslash paths. A simple forward
vs. backward slash mistake produced a false negative that nearly led me
to rebuild the mod from scratch.

When checking for a file in a PBO, check BOTH slash styles, or normalize
the path you expect to the PBO's style.

## CRITICAL: duplicate PBOs in the same `@mod/addons/` cause SILENT conflict

If you rename your mod (e.g. `VanillaPPMap.pbo` → `Apocalypse.pbo`) but
forget to remove the old PBO from `@VanillaPPMap/addons/`, the engine
reads BOTH. Symptoms:

- The RPT log goes silent after C++ config init, with no `Apocalypse` or
  `VPPGroups` mentions (looks like the new mod was never loaded)
- No fatal error — DayZ doesn't say "duplicate CfgPatches"
- EnforceScript compile (if it gets there) produces spurious errors

**Fix:** always check for and remove old PBOs after a mod rename:

```bash
ls -la /path/to/Mods/@YourMod/addons/   # look for unexpected *.pbo
mv /path/to/Mods/@YourMod/addons/OldName.pbo{,.OLD_bak}
# restart server, verify RPT now shows new mod's CfgBase updates
```

## Packing pitfall: `pbo <output.pbo>` with no source dir = empty PBO

The `pbo` tool's positional arguments are: `pbo <output.pbo> [files...]`.
If you call `pbo Apocalypse.pbo` (no source directory, no files), the tool
silently creates a 21-byte EMPTY PBO containing only the header.

**This is destructive.** I did exactly this in a debugging session when I
tried to "inspect" a PBO with the wrong tool invocation, and it
overwrote my carefully built `Apocalypse.pbo` with a useless empty file.
Recovery: rebuild from the source directory.

**Always use the canonical pack form:**

```bash
# CORRECT — read from a source directory using -C and -P
pbo -C /home/alca/MyMod -P "**" /path/to/Mods/@MyMod/addons/MyMod.pbo

# WRONG — no source, creates an empty 21-byte PBO that overwrites the target
pbo /path/to/Mods/@MyMod/addons/MyMod.pbo

# WRONG — same problem, just slower
pbo /path/to/Mods/@MyMod/addons/MyMod.pbo -C /home/alca/MyMod -P "**"
```

## Minimal Python parser (proves what a PBO actually contains)

```python
import struct

def parse_pbo(path):
    """Returns (properties, file_names, size_bytes)."""
    with open(path, "rb") as f:
        data = f.read()
    pos = 21  # skip 0x00 + "sreV" + 16 zero bytes
    def readz(p):
        e = data.find(b"\x00", p)
        return (data[p:e].decode("ascii", errors="replace"), e + 1) if e >= 0 else (None, p)
    props = []
    # 1. Properties (key\0value\0 ... until empty key)
    while pos < len(data):
        key, pos = readz(pos)
        if key is None or not key: break
        value, pos = readz(pos)
        if value is None: break
        props.append((key, value))
    # 2. File table (filename\0 + 4 bytes mime + 4×uint32, until empty name)
    file_names = []
    while pos < len(data):
        name, pos = readz(pos)
        if name is None or not name: break
        if pos + 20 > len(data): break
        pos += 4 + 16  # skip 4 mime + 4 uint32s
        file_names.append(name)
    return props, file_names, len(data)

# Usage
props, files, size = parse_pbo("/path/to/Apocalypse.pbo")
print(f"Size: {size}  Files: {len(files)}")
print(f"Properties: {[(k,v) for k,v in props]}")
print(f"First 5 files: {files[:5]}")
print(f"scripts/ count: {sum(1 for f in files if chr(92) in f and 'scripts' in f)}")
print(f".c count: {sum(1 for f in files if f.endswith('.c'))}")

# When checking for a file, try both slash styles
target = "scripts/5_Mission/missionGameplay.c"
target_bs = target.replace("/", chr(92))  # backslash
found = (target in files) or (target_bs in files)
print(f"missionGameplay.c present: {found}")
```

## Direct string-search fallback (no parser needed)

If the parser above feels heavy, you can verify a specific code change is
in the PBO with a simple `grep -c`:

```bash
PBO="/path/to/Apocalypse.pbo"

# Verify my new keybind code is in the PBO (binary, treat as text)
grep -c "UAApocalypseToggleCompass" "$PBO"
# expect: 5 (one for each occurrence in missionGameplay.c + comments)

# Verify all my fixes are in
for term in "ToggleCompass" "SendTacticalPing" "m_TickCounter" "perPlayerKey" "SanitizePath"; do
    count=$(grep -c "$term" "$PBO")
    echo "  $count × $term"
done

# Verify banned syntax is GONE (should all be 0)
for term in "switch (newTab" "switch (m_VisibleState" "switch (member.roleName" "int d\\[ \\] ="; do
    count=$(grep -c "$term" "$PBO")
    echo "  $count × $term (should be 0)"
done
```

This is faster than parsing and works for "is my code present" verification.
The only catch: the file table uses backslash paths but the data blocks
contain raw C source which uses forward slashes — so `grep` for code
content works fine, only path checks need the backslash awareness.

## Workflow: verify a deployed PBO is correct

```bash
# 1. Check size is non-trivial (empty PBO is exactly 21 bytes)
PBO="/home/alca/games/Dayz/Mods/@VanillaPPMap/addons/Apocalypse.pbo"
size=$(stat -c %s "$PBO")
[ "$size" -gt 1000 ] && echo "PBO size OK: $size bytes" || echo "PBO TOO SMALL: $size bytes (empty?)"

# 2. Verify a handful of code strings are present
for term in "UAApocalypseToggleCompass" "ToggleCompass" "m_TickCounter" "missionGameplay"; do
    grep -q "$term" "$PBO" && echo "  OK $term" || echo "  NO $term MISSING"
done

# 3. Verify banned syntax is gone
for term in "switch (newTab" "switch (m_VisibleState" "switch (member.roleName" "switch (visibleState" "switch (buttonIndex" "switch (m_Action" "switch (channel)" "int d\\[ \\] ="; do
    count=$(grep -c "$term" "$PBO")
    [ "$count" -gt 0 ] && echo "  BAD FOUND $count × $term (should be 0!)" || true
done

# 4. Parse and confirm key files are present (both slash styles)
python3 -c "
import struct
with open('$PBO', 'rb') as f: data = f.read()
pos = 21
def readz(p):
    e = data.find(b'\x00', p)
    return (data[p:e].decode('ascii', errors='replace'), e+1) if e >= 0 else (None, p)
props = []
while pos < len(data):
    k, pos = readz(pos)
    if not k: break
    v, pos = readz(pos)
    if v is None: break
    props.append((k, v))
files = []
while pos < len(data):
    n, pos = readz(pos)
    if not n: break
    if pos + 20 > len(data): break
    pos += 20
    files.append(n)
checks = ['config.cpp', 'scripts/5_Mission/missionGameplay.c']
for c in checks:
    bs = c.replace('/', chr(92))
    print(f'  {\"OK\" if (c in files) or (bs in files) else \"NO\"} {c}')
print(f'Total: {len(files)} files, {sum(1 for f in files if f.endswith(\".c\"))} .c')
"
```

If all checks pass, the PBO is correctly built. If something is missing,
rebuild: `pbo -C /source/mod -P "**" /path/to/Apocalypse.pbo`
