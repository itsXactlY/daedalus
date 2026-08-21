---
name: dayz-integrations
version: 1.2.0
category: dayz
description: Complete DayZ integration guide — compilation debugging, RPC routing, client-server mod separation, LBMaster admin layout, HUD widget patterns, and crash analysis.
tags: [dayz, debugging, compilation, rpc, client-server, lbmaster, admin, hud, layout]
---

# DayZ Integrations — Complete Guide

## Compilation Debug Workflow

### When to Use
- DayZ mod fails to compile with "Can't compile Mission script module!" errors
- EnforceScript syntax errors in .c files or .layout files
- Missing function references or undefined method errors
- Layout syntax issues causing UI initialization failures

### Step 1: Extract Error Details from Crash Log
```bash
# Look for specific error messages in the crash log
grep -A5 -B5 "Can't compile" ~/games/DayZ/Server/profile/crash_*.log
# Extract file, line number, and error type
# Example: VanillaPPMap/scripts/5_Mission/gui\vppmapmenu.c(105): Broken expression (missing ';'?)
```

### Step 2: Initial Assessment & Quick Fixes
Check for these common EnforceScript issues:
- **GetType() on custom classes**: Does not exist — remove. (But `Object.GetType()` on `EntityAI`/`ItemBase` IS valid — see `enforce-script-syntax` skill.)
- **Layout keywords**: vextpos → vexactpos (DayZ-specific syntax)
- **Missing semicolons**: Check lines before/after reported error
- **Invalid widget types**: MapWidgetPointer doesn't exist - use proper widget casting

### Step 3: Systematic File Inspection
```bash
# Check layout file syntax
grep -n "vextpos" /path/to/mod/GUI/Layouts/*.layout

# Check for missing functions referenced elsewhere
grep -r "RefreshGroupUI\|SetMapNeedsUpdate" /path/to/mod/scripts/

# Check for invalid widget declarations
grep -n "MapWidgetPointer\|CreateWidget.*MapWidget" /path/to/mod/scripts/5_Mission/gui/*.c
```

### Step 4: Safe Fix Application Procedure
To avoid corrupting files during editing (LEARNED FROM EXPERIENCE):

**A. Backup Original**
```bash
cp file.c file.c.backup
```

**B. Apply Fixes Individually**
1. **Layout syntax**: `sed -i 's/vextpos/vexactpos/g' file.layout`
2. **GetType() on custom classes only**: `sed -i 's/\.GetType()//g' file.c` (do NOT strip on EntityAI/ItemBase/Object subclasses)
3. **Remove invalid widget code**: Delete blocks creating non-existent widgets
4. **Add missing functions**: Insert before first major function after Init()

**C. Safe Function Addition Method**
Instead of risky line-number insertion that can corrupt files:
```bash
# Find reliable anchor point (e.g., EditMarkerVisibility function)
LINE_BEFORE_EDIT=$(grep -n "EditMarkerVisibility" file.c | cut -d: -f1)
INSERT_POINT=$((LINE_BEFORE_EDIT - 1))

# Insert missing functions safely
sed -i "${INSERT_POINT}i\\
\\
    void RefreshGroupUI() {\\
        if (m_GroupMenu) m_GroupMenu.RefreshGroupData();\\
        if (m_GroupAdmin) m_GroupAdmin.Refresh();\\
        if (m_AdminHandler) m_AdminHandler.LoadSettingsToUI(VPPClientManager.GetInstance().GetServerSettings());\\
    }\\
\\
    void SetMapNeedsUpdate(bool state) {\\
        m_MapNeedsUpdate = state;\\
    }" file.c
```

**D. File Reconstruction Method (when sed gets complex)**
For complex insertions that keep corrupting:
```bash
# 1. Get everything BEFORE the insertion point
head -n $INSERT_POINT file.c > /tmp/part1.c

# 2. Add the new content
cat >> /tmp/part1.c << 'EOF'

    void RefreshGroupUI() {
        if (m_GroupMenu) m_GroupMenu.RefreshGroupData();
        if (m_GroupAdmin) m_GroupAdmin.Refresh();
        if (m_AdminHandler) m_AdminHandler.LoadSettingsToUI(VPPClientManager.GetInstance().GetServerSettings());
    }

    void SetMapNeedsUpdate(bool state) {
        m_MapNeedsUpdate = state;
    }
EOF

# 3. Add everything AFTER the insertion point
tail -n +$INSERT_POINT file.c >> /tmp/part1.c

# 4. Replace original
mv /tmp/part1.c file.c
```

### Step 5: Verification Checklist
After each fix round:
- [ ] No `GetType()` on custom classes (Object subclasses are OK)
- [ ] No `vextpos` in layout files (only `vexactpos`)
- [ ] No `MapWidgetPointer` or invalid `CreateWidget` usage
- [ ] Missing functions present and correctly formatted
- [ ] Braces balanced (check with IDE or manual inspection)
- [ ] PBOs build without errors
- [ ] Server progresses past script compilation

### Step 6: Build & Test
```bash
# Build PBOs
./build_and_start_vanillappmap.sh

# Check for success indicators:
# - "✓ Client PBO gebaut"
# - "✓ Server PBO gebaut"
# - "Starte DayZServer_x64..."
# - "fsync: up and running."

# Verify PBOs created
ls -lh ~/games/DayZ/Mods/@VanillaPPMap/addons/VanillaPPMap.pbo
ls -lh ~/games/DayZ/Mods/@VanillaPPMap_Server/addons/VanillaPPMap_Server.pbo
```

### Common Pitfalls & Solutions
- **File corruption during editing**: Always work from git backup or make backups before sed operations. Learned this the hard way when multiple sed commands corrupted the file structure.
- **Misplaced function insertion**: Use anchor points (like `EditMarkerVisibility`) instead of line numbers to avoid putting code in wrong locations.
- **Missing braces**: Verify each added function has proper opening/closing braces - unbalanced braces cause cascade errors.
- **Layout vs script confusion**: Layout files use different syntax (.layout) than script files (.c) - don't mix them up.
- **Assuming missing functions**: Always verify functions are actually referenced before adding them - don't guess.
- **Iterative fixing**: Fix one error at a time - fixing early errors often reveals later ones that were masked.

### Recovery Strategy
If file becomes corrupted during editing:
```bash
# Reset to known good state
git checkout HEAD -- path/to/mod/GUI/Layouts/VPPMapMenu.layout
git checkout HEAD -- path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c

# Then re-apply fixes carefully one by one
```

### Verification Commands
```bash
# Check fixes are applied
! grep -q vextpos /path/to/mod/GUI/Layouts/VPPMapMenu.layout && echo "✅ Layout fixed"
! grep -q GetType /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ GetType removed"
! grep -q MapWidgetPointer /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ Widget fix"
grep -q "RefreshGroupUI" /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ Function 1"
grep -q "SetMapNeedsUpdate" /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ Function 2"
```

### Expected Outcome
- Server progresses past "Can't compile Mission script module!" error
- PBOs build successfully without compilation errors
- Server reaches fsync initialization stage
- Map functionality works when client connects and presses 'M'

### Compilation Fix Workflow

## When to Use
Use this workflow when a DayZ mod fails to compile and prevents server startup, showing errors like:
- "Can't compile \"Mission\" script module!"
- "Undefined function 'X'"
- "Broken expression"
- "Missing ';'"
- Invalid layout keywords
- Class/method not found errors


<!-- moved to references/moved-sections.md: ## Workflow Steps -->

## DayZ-Specific Notes
- **VPPMaps**: Root size is `1 1`, quadrants use `0.49 0.46`
- **Fonts**: Use Chat/PuristaMedium/PuristaBold outside VPPAdminTools
- **Layout textures**: Use forward slashes
- **GUI Separation**: UIScriptedMenu for open/close, plain widgets+VPPHUDManager for always-visible
- **Admin Checks**: VPPAdminTools GetPermissionManager() can return NULL - need fallback

### Example Fix Sequence
For errors like:
1. `GetType()` on custom class → Remove it (skip if on `EntityAI`/`ItemBase`)
2. `vextpos` in layout → Change to `vexactpos`
3. `MapWidgetPointer` → Remove manual widget creation
4. `Undefined function RefreshGroupUI` → Restore function
5. `Undefined function SetMapNeedsUpdate` → Add function

## Fix Undefined Methods

### Problem
When developing DayZ mods with Enforce Script, accessing undefined methods on custom classes results in compilation errors. Commonly occurs when classes have private member variables but lack corresponding public getter/setter methods.

### Detection
- Compiler error: "Undefined function 'ClassName.MethodName'"
- Error occurs when trying to access methods like `IsMenuOpen()`, `GetVariable()` on custom classes
- The class typically has the backing private member variable but lacks the accessor methods
- Multiple files may attempt to call the same missing method

### Solution
1. Locate the class definition that's missing the method
2. Verify the backing private member variable exists
3. Add the missing getter and/or setter methods to the class
4. For boolean flags: add `GetFlagName()` returning the variable and `SetFlagName(bool)` setting it
5. Place methods near the end of the class definition before the closing brace

### Example Fix
For a class with `private bool m_IsMenuOpen;` missing `IsMenuOpen()`:
```c
bool IsMenuOpen() {
    return m_IsMenuOpen;
}

void SetMenuOpen(bool state) {
    m_IsMenuOpen = state;
}
```

### Prevention
- When adding private member variables that need external access, immediately add corresponding getter/setter methods
- Use consistent naming: `GetVariableName()` and `SetVariableName(type)`
- Review all files that instantiate the class to ensure they use the proper accessors
- Consider creating a template for common UI menu classes that need open/close state tracking

### Verification
- Recompile the mod to ensure no more undefined function errors
- Verify all call sites now work correctly
- Test the functionality that was previously broken due to the missing access

### Enhanced Fix Approach

### Phase 1: Discovery and Verification
1. **Identify the error location**: Note the file and line number from the compiler error
2. **Check filename casing**: DayZ file references may have different casing than expected (e.g., ClientManager.c vs clientmanager.c)
3. **Locate the class definition**: Find the class that's missing the method
4. **Verify member variable exists**: Confirm the backing private member variable is present
5. **Check all call sites**: Search for all occurrences of the missing method call to understand scope

### Phase 2: Apply DayZ Enforce Script Patterns
Following the `dayz-enforce-script-fix-undefined-methods` skill:
1. **Getter method**: For `private bool m_IsMenuOpen;` add `bool IsMenuOpen() { return m_IsMenuOpen; }`
2. **Setter method**: For `private bool m_IsMenuOpen;` add `void SetMenuOpen(bool state) { m_IsMenuOpen = state; }`
3. **Placement**: Add methods near the end of the class before the closing brace
4. **Naming convention**: Use `GetVariableName()` and `SetVariableName(type)` pattern

### Phase 3: Constraint Compliance Verification
Verify the fix adheres to DayZ Enforce Script constraints:
- ✅ **No switch statements**: Replace with if/else chains
- ✅ **No ternary operators**: Replace with if/else
- ✅ **No array literals**: Use `ref array<T>` + Insert/Get/Set/.Count()
- ✅ **Proper foreach**: Avoid `foreach(key, value : map)` syntax
- ✅ **Function-level variable scope**: No redeclaring variables in nested blocks
- ✅ **Widget event handlers**: Proper `bool OnClick(Widget, int, int, int)` signatures

### Phase 4: Duplication Prevention
After applying the fix:
1. **Check for duplicates**: Search the file to ensure methods weren't accidentally duplicated
2. **Validate placement**: Ensure methods are in the correct location (after other methods, before closing brace)
3. **Verify naming consistency**: Confirm method names match the expected getter/setter pattern

### Phase 5: Multi-Call Site Validation
Test that all call sites now work:
1. **ClientManager.c**: `mapMenu.IsMenuOpen()` calls
2. **missionGameplay.c**: `m_VPPMapMenu.IsMenuOpen()` calls
3. **Any other files**: Search for additional usages of the method
4. **Setter usage**: Verify `SetMenuOpen(bool)` calls work if applicable

---

## Layout Crash Debug

**Trigger**: DayZ crashes with `SEH exception 0x80000101` in `CreateWidgets()` or during widget init, especially when layout braces appear balanced.

## Diagnosis Steps

1. **Check binary layout file** — read as bytes, check for BOM, null bytes, encoding issues
2. **Verify braces match** — `{` count must equal `}` count
3. **Check `size` + `hexactsize` pairs** — the #1 hidden cause of crashes:
   - `hexactsize 1` means EXACT PIXEL size — value is in pixels, not relative 0-1
   - Large pixel values (e.g., `size 1104 25`) with `hexactsize 1` can overflow the parent container and crash `CreateWidgets`
   - **Fix**: Either reduce the pixel value to screen width (≤980 for typical 1080p), OR change to `hexactsize 0` + `size 1 25` (relative width)
4. **Check `hexactpos`** — same principle, exact pixel positioning can place widgets off-screen

## Common Pitfalls

| Pattern | Problem | Fix |
|---------|---------|-----|
| `size 1104 25 hexactsize 1` | 1104px wide exceeds container | `size 1 25 hexactsize 0` |
| `size 1920 1080 hexactsize 1` | Full screen exact pixels | `size 1 1 hexactsize 0` |
| `.edds` referenced but only `.png` exists | Missing texture file | Change path to actual format |
| Non-existent font in `font` attribute | Crash on widget init | Replace with valid DayZ font |
| Brace count mismatch | Structural corruption | Rebuild from backup |

## Font-Related Crashes

Non-existent fonts cause **SEH exception 0x80000101** on startup when the engine tries to create text widgets. Common culprits from VPPAdminTools/other mods:

| Bad Font | DayZ Replacement |
|----------|-----------------|
| `gui/fonts/sdf_MetronBook72` | `gui/fonts/Chat` |
| `gui/fonts/sdf_MetronLight24` | `gui/fonts/PuristaMedium` |
| `gui/fonts/sdf_MetronBold16` | `gui/fonts/PuristaBold` |

**Scan command**: `grep -r "sdf_Metron" GUI/Layouts/` then bulk-replace with sed or script. These fonts are from VPPAdminTools - if that mod isn't loaded, the references break.

## Key Insight

A layout file can be **structurally valid** (braces balanced, no corruption) but still crash the engine if **pixel dimensions exceed container bounds** or **referenced textures don't exist**. Always verify `hexactsize` values against screen dimensions and texture file existence.

### Exact size overflow
`size 1104 25` with `hexactsize 1` causes engine crash on containers > screen width.
Fix: Use relative `size 1 25` with `hexactsize 0`.

### Texture path format
Layout files use backslash separators: `imageTexture "VanillaPPMap\\GUI\\Compass_slim.png"`
Must match actual file (`.png` not `.edds` unless EDDS file exists).
Always check `*.edds` files exist before referencing them.

### Widget not found crashes
`FindWidget()` returns null → crash at method call.
Always use `FindAnyWidget()` for name-based lookup, never `FindWidget()`.
Always null-check before calling methods on result.

### onChange per keystroke
DayZ fires `OnChanged` per keystroke on edit boxes, not on submit.
Guard with `if (finished)` for edit-box + slider sync to avoid infinite loops.

---

## HUD Init & Timing

## When to initialize HUD widgets

**Never** create HUD widgets in the `MissionGameplay` constructor or via `CallLater` with short delays. During construction, the loading screen is still active, the world isn't spawned, and `GetGame().GetPlayer()` returns null. Widgets that query settings, register with managers, or access the world will hang or crash the connection handshake — causing infinite loading.

**Correct pattern:** Override `OnInit()` and defer with a short CallLater:

```enforce
override void OnInit() {
    super.OnInit();
    GetGame().GetCallQueue(CALL_CATEGORY_GUI).CallLater(this.InitializeHUDWidgets, 1000, false);
}
```

This fires after the world is fully loaded and the player exists.

## WidgetEventHandler API — correct calls

Widget events MUST use the specific typed registration methods. Generic `Register()` does not work for button clicks.

```enforce
// CORRECT — button click handler
WidgetEventHandler.GetInstance().RegisterOnClick(widget, this, "OnButtonClicked");

// WRONG — these don't exist or have wrong signatures
WidgetEventHandler.GetInstance().RegisterOnButton(...);  // DOES NOT EXIST
WidgetEventHandler.GetInstance().Register(widget, ...);  // doesn't register click
```

Handler signature — must be `bool` return type, NOT `void`:
```enforce
bool OnButtonClicked(Widget w, int x, int y, int button) {
    Print("clicked: " + w.GetName());
    return true;  // consume event
}
```

**Do NOT call `super.OnClick()`** unless the class you're extending overrides `OnClick` with the exact same 5-param signature. `ScriptedWidgetEventHandler` has `void OnClick(Widget w)` — calling `super.OnClick(w,x,y,button)` will crash.

## Enforce Script variable scoping

Enforce Script uses **function-level** variable scope. Declaring the same variable name twice in different `if` blocks within the same function is a compile error:

```enforce
// WRONG — 'year' declared twice
void UpdateInfo() {
    if (m_ServerTime) {
        int year, month, day, hour, minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
    if (m_InGameTime) {
        int year, month, day, hour, minute;  // ERROR: Multiple declaration
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
}
```

### Pitfall: duplicates across inserted blocks in long OnUpdate()

When patching a long `OnUpdate()` (e.g. `missionGameplay.c`) by inserting multiple
new code blocks, do NOT reuse variable names that already appear further down
in the same function. The original `bool mapOpen = m_VPPMapMenu && m_VPPMapMenu.IsMenuOpen();`
declared near the bottom will collide with a new `bool mapOpen` you add near the
top — Enforce Script does function-level scope checks, not block scope.

**Fix:** rename your new variable to something specific (e.g. `mapOwnedByUI`,
`isMapMenuOpen`).

void UpdateInfo() {
    int year, month, day, hour, minute;
    if (m_ServerTime) {
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
    if (m_InGameTime) {
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
}
```

## File corruption recovery

If a file gets corrupted (e.g. triple column numbering like `1|     1|     1|class` caused by a bad `write_file`), don't try to patch it. Just:

```bash
cd /path/to/mod && git checkout -- path/to/file.ext
```

Then use small targeted `sed -i '/PATTERN/d'` commands or targeted `patch` with unique surrounding context instead of rewriting the entire file.

## Frame Throttling: don't use GetTickTime() for modulo-N

**Pitfall:** When you need a "do this every Nth frame" pattern in `OnUpdate()`,
the obvious `GetGame().GetTickTime()` approach is broken:

```enforce
// BAD — cast rarely lands on exact multiples of N
int frame = GetGame().GetTickTime() * 1000;  // float, not multiple of 3/10
bool isTick3 = ((frame - (frame / 3) * 3) == 0);  // rarely true
bool isTick10 = ((frame - (frame / 10) * 10) == 0);
```

`GetTickTime()` returns a `float` whose product with 1000 only sometimes
equals an exact multiple of 3 or 10. `isTick3` and `isTick10` fire
inconsistently — your throttled updates will lag or fire at wrong cadence.

**Correct pattern:** a monotonic `int` counter on the class:

```enforce
private int m_TickCounter = 0;

override void OnUpdate(float timeslice) {
    m_TickCounter++;
    bool isTick3  = ((m_TickCounter - (m_TickCounter / 3)  * 3)  == 0);
    bool isTick10 = ((m_TickCounter - (m_TickCounter / 10) * 10) == 0);

    if (isTick3) {
        // expensive map / marker update
    }
}
```

**Overflow guard:** `int` wraps at ~2.1B. At 60 FPS that's ~414 days, but if
you ever call this on a server with a long uptime or in a tight loop, wrap
explicitly to be safe:

```enforce
m_TickCounter++;
if (m_TickCounter > 100000) m_TickCounter = 0;  // keep bounded
```

Same pattern for per-widget frame counters (chat fade, compass update, etc.).
Wrap at 100k — modulo check works the same with any non-zero base.


<!-- moved to references/moved-sections.md: ## Keybind Wiring Pattern (CfgInputActions → script) -->


<!-- moved to references/moved-sections.md: ## See Also -->


<!-- moved to references/moved-sections.md: ## Related Skills -->

## Per-Player Rate Limiting (webhook / RPC / event spam)

When a server-side manager fires webhooks (Discord, custom HTTP, log files,
etc.) for game events (group created, member joined, marker placed, chat
message), naive rate limiting by `eventType` alone lets one player spam
any event type.

**Correct pattern** — key the rate-limit map by `(playerId, eventType)`:

```enforce
private ref map<string, int> m_RateLimits;
private static const int RATE_LIMIT_MS = 5000;

void Fire(string eventName, map<string, string> payload) {
    // ... config / URL checks ...

    int now = GetGame().GetTime();
    int lastFired;
    string playerId = "";
    if (payload && payload.Contains("Player Id"))  payload.Find("Player Id", playerId);
    else if (payload && payload.Contains("Steam Id")) payload.Find("Steam Id", playerId);

    // Per-player throttle: same player can't fire the same event too often
    string perPlayerKey = playerId + ":" + eventName;
    if (playerId != "" && m_RateLimits.Find(perPlayerKey, lastFired)) {
        if ((now - lastFired) < RATE_LIMIT_MS) return;
    }

    // Optional global safety net: no event fires more than once per RATE_LIMIT_MS
    string eventKey = "global:" + eventName;
    if (m_RateLimits.Find(eventKey, lastFired)) {
        if ((now - lastFired) < RATE_LIMIT_MS) return;
    }

    if (playerId != "") m_RateLimits.Set(perPlayerKey, now);
    m_RateLimits.Set(eventKey, now);

    // ... actually fire the webhook ...
}
```

The "Player Id" / "Steam Id" key lookup is convention — pick whichever your
event payload uses and document it. If no playerId is in the payload (system
events), fall through to the global throttle only.

## Legacy Mod Migration Sweep (banned-constructs audit)

When picking up a merged or ported mod, run a sweep for the 4 most common
Enforce Script violations *before* trying to compile. One merged codebase
routinely surfaces 10-20 of these in a single pass:

```bash
# 1. switch statements
grep -rEn '^\s*switch\s*\(' scripts/ | wc -l

# 2. int[] / string[] bracket literals
grep -rEn '\b(int|string)\s*\[' scripts/ | wc -l

# 3. ternary ?: in code (not comments)
grep -rEn '\?[^?:].*:' scripts/ | grep -v '//' | grep -v '/\*' | wc -l

# 4. GetType() on custom classes (NOT on Object subclasses)
grep -rn '\.GetType()' scripts/ | wc -l   # review each match manually
```

For each `switch` statement, convert to an `if/else` chain. For each
`int[]` / `string[]` literal, convert to `ref array<T>` with `Insert/Get/Set`.
For each ternary, expand to `if/else`. For `GetType()` matches, only remove
those on custom script classes (anything inheriting from `Object` like
`EntityAI`/`ItemBase`/`PlayerBase` is fine).

**Mechanical batch approach for switch → if/else:**

```bash
# Find all switch sites
grep -rEn '^\s*switch\s*\(' scripts/

# Read each, manually patch with `patch` tool — too varied for sed
# Keep the brace count balanced after each conversion
```

A single mod can have 10-15 switch statements in critical UI files
(chat widget, admin pages, role-color lookups, marker visibility cycle).
All must be converted. The `patch` tool with unique surrounding context
keeps the changes safe and reviewable.

---

## Crash Log Analysis

### When to use
- User shares a DayZ crash log with SEH exceptions, stack traces, or access violations
- Need to trace a crash through mod chains (VPPAdminTools -> BaseBuildingPlus -> VanillaPPMap etc.)
- Need to find the source line referenced in a crash from a deployed PBO


<!-- moved to references/moved-sections.md: ## Workflow -->


<!-- moved to references/moved-sections.md: ## Common crash causes on Linux/Proton (Wine) -->


<!-- moved to references/moved-sections.md: ## Server Liveness: Silent RPT Log ≠ Server Hanging -->

## DO NOT SELF-ASSEMBLE A SERVER START SCRIPT (hard rule, 2026-07-17)

The operator's project has ITS OWN build+start entrypoint. For the Apocalypse/VanillaPPMap
work the canonical file is:

- **`/home/alca/apogrps_qwen/Apocalypse/build_and_start.sh`** — builds `@Apocalypse` +
  `@Apocalypse_Server` PBOs from `apogrps_qwen/Apocalypse/` and starts the server via
  `Proton - Experimental` + `STEAM_COMPAT_DATA_PATH=compatdata/221100`.
- The mission SCRIPTS live in **`/home/alca/apogrps_qwen/Apocalypse/scripts/4_World/`** —
  NOT in the deployed `dayzOffline.chernarusplus` mission folder. When a crash log says
  `Apocalypse/scripts/4_World/vppwebhookmanager.c(99)`, the source is there.
- `!START_Server_debug.bat` (in `games/DayZ/Server/`) is the minimal 5-mod debug launcher.

**NEVER write your own `start_server*.sh` / `*.sh` launcher** that re-derives mod lists or
proton paths. The operator explicitly said "darüber starten, und sonst gar nicht!" — i.e. use the
project's script, not a freshly-assembled one. Self-assembled scripts crashed with the wrong
Proton flavor and wrong prefix, wasting a full session. If you must launch, call the EXISTING
`build_and_start.sh` (bash build_and_start.sh) in the background and poll its log — do not
reproduce its logic.

**"Nimm proton wo da ist!"** — use the Proton build that is ALREADY on disk, do not invent one.
On this box the installed builds are `Proton 10.0`, `Proton - Experimental`, `Proton BattlEye
Runtime`. `build_and_start.sh` uses `Proton - Experimental` (path
`~/.local/share/Steam/steamapps/common/Proton - Experimental/proton`) + `compatdata/221100`.
Note: umu can fall back to `Proton-GE Latest` even when you pass `- Experimental` — check the
startup log for `Running 'Proton-GE Latest'` vs `Running 'Proton - Experimental'`; if it fell
back, the prefix/env is mismatched. Never assume a Proton name; read what's installed first.

**SOURCE OF TRUTH — JUNK TREES ARE OFF-LIMITS (learned 2026-07-18, operator rage-quit):**
`/home/alca/apogrps/VanillaPPMap`, `/home/alca/apogrps/VanillaPPMap_Server`, and any
`rc.sh`/`build_and_start_vanillappmap.sh` that point at them are **DEAD JUNK** from an earlier
rewrite. The ONLY real mod source is **`/home/alca/apogrps_qwen/Apocalypse/`** (single combined
tree: 3_Game + 4_World + 5_Mission, one `Apocalypse.pbo`). If the user says "the mod folder is
X and ONLY that", BELIEVE them on turn one — do NOT grep/read/patch the junk trees, do NOT run a
compile-check script that builds from them. An agent spent many turns patching the junk tree
(`ComboBoxWidget`→`XComboBoxWidget`, etc.) while the real `Apocalypse/` tree sat untouched and the
server kept loading the junk-built pbo. The moment you are told the canonical path, `cd` to it and
stay there. Verify with `find <canonical>/scripts -name "*.c"` before any edit.

**THE SERVER MODULE COMPILE DEAD-END (do not re-chase it):** A "Can't compile World script
module! Unknown type 'VPPGroup'" error from a `VanillaPPMap_Server/scripts/4_World/` path is an
ARTIFACT of the JUNK tree (it has 4_World managers but no 3_Game). The real `Apocalypse/` tree has
everything in one pbo and compiles clean once the junk pbo is replaced. If you see that error,
check which pbo the server actually loaded — it is almost certainly the junk-built one, not the
real `Apocalypse.pbo`.



A complete recipe for deploying + running a DayZ modded server on a Linux host with Steam + Proton, started via a non-interactive SSH session.

**Supporting files in this skill:**
- `references/linux-proton-server-deploy.md` — full deploy recipe (prerequisites, build tool, source rsync, server install from ZIP, config rsync, start script, 3-step liveness check, process tree, pitfalls)
- `references/pbo-format-and-verification.md` — PBO binary format (21-byte header, backslash paths, file table structure) + Python parser for verifying a deployed PBO actually contains the expected files
- `templates/start_dayz_server.sh` — reusable start script template (parameterized paths, no `exec` for nohup backgrounding, full mod list with Z:\\ Wine paths)

**Key gotchas that aren't obvious** (see reference doc for full detail):
- `dayz_dev_tools` venv has absolute shebangs in `bin/pbo` and `bin/pip*` — when you rsync the venv to a new machine, `sed -i` the shebangs to the new prefix.
- DayZ server start script must NOT end with `exec` if you want to background it via `nohup ... &` — the parent script needs to exit cleanly so the DayZ process becomes an orphan adopted by init.
- `scriptDebug` and `dologs` flags only affect what gets written to RPT/ADM, not stdout.
- The DayZ server process tree under Proton looks like: `bash` → `proton` → `steam.exe` → `wineserver` → `DayZServer_x64.exe`. All alive = normal.
- **Silent RPT log is NOT a hang.** DayZ writes C++ init to RPT, then goes silent waiting for player connections. See the liveness-check section in this SKILL.md (above) for the 3-step recipe.
- **Use the right PID for the FD check.** Under Proton, the `python3 .../proton` parent has only 3 FDs visible (`/dev/null` + stdout+stderr). The actual DayZ server FDs are visible only from the `DayZServer_x64.exe` PID. Get it with `pgrep -f "DayZServer_x64.exe"`.
- **`pkill -f start_dayz_*` will kill your own SSH command.** The pattern matches the very script you're running. Use `pkill -f "DayZServer_x64.exe"` instead, or `pkill -P $(pgrep -f "DayZServer_x64.exe" | head -1)` for process-group targeting.
- **DayZ has no headless mission-start.** RCon (DayZ native, Source-Engine, BattlEye) all time out and don't trigger mission load. The only paths are: real client connect, fake client in Python, or headless client mode. Don't waste cycles on RCon workarounds.
- **Duplicate PBOs in the same `@mod/addons/` cause a SILENT conflict.** If you rename a mod (`OldName.pbo` → `NewName.pbo`) but forget to remove the old PBO from the mod folder, DayZ reads both. Symptoms: silent RPT after C++ config init, no mention of either mod's name, no fatal error. Always check `ls @YourMod/addons/` after a mod rename.
- **PBO paths use BACKSLASH, not forward slash.** A path check like `"scripts/5_Mission/missionGameplay.c"` will return "not found" in a PBO inspector even when the file IS there (stored as `scripts\5_Mission\missionGameplay.c`). When verifying PBO contents, check both slash styles.


<!-- moved to references/moved-sections.md: ## Related Skills -->

## LBMaster Groups Integration

> Based on integrating LBMaster Advanced Groups (122 classes, 150 .c files, 43 layouts) into VanillaPPMap codebase.

## Context
We do NOT copy-paste LBMaster code. We **port functionally** while preserving our A+++ patterns.
LBMaster uses `LBMenuBase` + `LBGroupPage` tab system, `LBLayoutManager.CreateWidgets()`, `LBConfigLoader<T>`, modded vanilla classes.
We use `UIScriptedMenu` + `ScriptedWidgetEventHandler`, `CreateWidgets()` directly, event-based config management.

## Step 1: Audit + ADR

Map every LBMaster class to our architecture:
```
LBMaster class → Our approach: ADOPT (copy), ADAPT (port with our patterns), or SKIP
```

Create `ADR_LBMASTER_SYSTEMS.md` with class-by-class mapping, execution order, and decision rationale.

Key LBMaster classes to audit:
- **LBGroupUI** (map menu shell, 648 lines) → Port as VPPGroupMapMenu (ScriptedWidgetEventHandler)
- **LBGroupPage** (base + 6 subclasses) → Port as VPPGroupPage with same lifecycle
- **LBGroup** (661 lines data model) → Port as VPPGroup with same WriteToCtx/ReadFromCtx
- **13 Admin pages** → Wire into existing VPPAdminMenuShell as new tabs
- **Chat system** → Keep our VPPChatWidget, adopt LBMaster's GridSpacer 4-col layout
- **Marker system** → Enhance our existing marker pool, add LBMaster types
- **14 Config classes** → Port event system, use our singleton pattern

## Step 2: PRD + Ralph Loop

Create `prd.json` with 12 stories in dependency order:
1. Audit + ADR
2. Config system (foundational)
3. Data models + RPC
4. Menu shell (VPPGroupMapMenu)
5. Page subclasses
6. Layout files
7. Marker system
8. Chat system
9. Admin pages
10. Mission lifecycle wiring
11. Final integration

No codex/claude-code on server? Use delegate_task with 50 iterations, then manually integrate the output.

## Step 3: Autonomous Execution

Spawn subagent with full context:
- LBMaster reference at `/path/to/LBMaster/LBmaster_Groups/scripts/`
- Target codebase at `/path/to/VanillaPPMap/scripts/`
- ADR with class mapping
- PRD with story list
- Enforce Script syntax rules

Key instruction: **"Never break existing A+++ code — only add new files/classes or update incrementally. Prefix all new classes with VPPGroup."**

## Step 4: Manual Integration (Post-Subagent)

After subagent creates files, verify and wire:

### 4a: Wire menu into VPPMapMenu
```c
// In VPPMapMenu member vars
private ref VPPGroupMapMenu m_GroupMapMenu;

// In Init()
if (!m_GroupMapMenu) m_GroupMapMenu = new VPPGroupMapMenu(this, m_PanelClan);

// In RefreshGroupUI()
if (m_GroupMapMenu) m_GroupMapMenu.RefreshGroupData();
```

### 4b: Wire RPC handler in missionGameplay
```c
// In MissionGameplay constructor
if (GetGame().IsClient() || !GetGame().IsMultiplayer()) {
    VPPGroupRPCHandler.Get();
}
```

### 4c: Wire admin pages into VPPAdminMenuShell
Add new tabs to PAGE_LAYOUTS and PAGE_NAMES arrays:
```c
"VanillaPPMap/GUI/Layouts/Menu/AdminGroups.layout",
// ... etc
```

### 4d: Fix layout naming if mismatched
LBMaster GetLayoutName() returns "Map Page 0 0" but files may be "page_0_0_default.layout". Fix:
```c
string GetLayoutName() { return "page_" + pageID + "_" + pageSubID + "_default"; }
```

## Step 5: Syntax Audit

Run before committing:
```bash
# Check for forbidden patterns in all new .c files
grep -rn '\?.*:' path/to/new/code | grep -v '//'    # No ternary
grep -rn '^\s*switch' path/to/new/code               # No switch
grep -rn 'int\[' path/to/new/code                     # No int[]
grep -rn 'string\[' path/to/new/code                  # No string[]

# Check cross-module (3_Game must not reference 5_Mission)
grep -rn '5_Mission_class_names' path/to/3_Game/      # Should be 0
```

## Dependency Graph (Critical!)

```
Config (3_Game) → Data Models (3_Game) → Menu Shell (5_Mission) → Pages (5_Mission)
                                                                      ↓
                                                             Admin Pages (5_Mission)
                                                                      ↓
                                               Chat + Markers + RPC Handlers (5_Mission)
                                                                      ↓
                                              MissionGameplay wiring (OnCreate + OnInit)
```

**DO NOT port pages before menu shell. DO NOT wire mission before RPC exists.**

## Pitfalls

1. **Layout naming mismatch**: Ensure `GetLayoutName()` matches actual `.layout` filenames exactly
2. **Double RPC registration**: New VPPGroupRPCHandler may register RPCs already handled by missionGameplay handlers. Use `VPPGroupRPCHandler.Get()` as a parallel system, not a replacement.
3. **Cross-module violations**: 3_Game CANNOT reference 5_Mission classes. Keep data models in 3_Game, UI in 5_Mission.
4. **Constructor HUD init**: Never create widgets in MissionGameplay constructor — defer to OnUpdate or CallLater from OnInit.
5. **Backwards compatibility**: Keep old GroupMenuUI alongside new VPPGroupMapMenu during transition period.

---


<!-- moved to references/moved-sections.md: ## LBmaster Admin Menu Layout Architecture -->


<!-- moved to references/moved-sections.md: ## Client-Server Mod Separation -->


<!-- moved to references/moved-sections.md: ## Related Skills -->


<!-- moved to references/moved-sections.md: ## Mazemaker DayZ Topic Sweep (research workflow) -->


<!-- moved to references/moved-sections.md: ## Prerequisites -->


<!-- moved to references/moved-sections.md: ## Loot Rebuild Workflow (T1–T4 from scratch) -->


<!-- moved to references/moved-sections.md: ## Supporting Reference Files -->
