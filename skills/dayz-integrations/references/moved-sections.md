# DayZ Integrations — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Workflow Steps

### 1. Log-First Investigation
- Examine the latest crash log in `~/games/DayZ/Server/profile/`
- Identify the specific error messages, file names, and line numbers
- Look for patterns: multiple errors often indicate related issues

#### Commands:
```bash
# Get latest crash log
ls -lt ~/games/DayZ/Server/profile/ | grep log | head -1

# Examine specific error
grep -A5 -B5 "Broken expression\|Undefined function" ~/games/DayZ/Server/profile/crash_*.log
```

### 2. Systematic Error-by-Error Fixing
Address each compiler error in the order they appear, as later errors may be caused by earlier ones.

#### Common Fix Patterns:
- **GetType() on custom classes**: Remove (doesn't exist). Leave alone if it's on an `EntityAI`/`ItemBase`/`Object` subclass — those ARE valid.
- **Invalid layout keywords**: Fix `vextpos` → `vexactpos`, check all layout syntax
- **Missing functions**: Check if function existed in original git version, restore if missing
- **Invalid widget creation**: Remove attempts to CreateWidget MapWidgets - use layout-defined widgets only
- **Pointer errors**: Remove invalid pointer types like `MapWidgetPointer`

#### Verification After Each Fix:
```bash
# Check fix was applied correctly
grep -n "GetType()" file.c   # Should return nothing
grep -n "vextpos" file.layout # Should return nothing
grep -n "MapWidgetPointer" file.c # Should return nothing
```

### 3. Build Verification
After applying fixes, test that the mod builds successfully.

#### Commands:
```bash
# From mod working directory
./build_and_start_vanillappmap.sh  # Or your mod's build script

# Check PBOs were created
ls -la @ModName/addons/ModName.pbo
ls -la @ModName_Server/addons/ModName_Server.pbo
```

### 4. Iterative Refinement
If build succeeds but server still fails to start:
- Check new crash log for next set of errors
- Repeat from Step 1
- Common pattern: fixing compilation errors reveals runtime initialization issues

#### Signs of Progress:
- Server gets further in startup (check log timestamps)
- Different error messages appear
- PBOs build without compilation errors
- Server reaches "fsync: up and running" or similar initialization message

### 5. Principle Application (DayZ Enforce Script)
Throughout the process, apply these principles:
- **Existing infra first**: Use layout-defined widgets, don't create manually
- **No ternary operators**: Use if/else instead
- **Proper array handling**: Use ref array<T> + Insert/Get/Set, not int[] syntax
- **No switch statements**: Use if/else chains
- **No {} literals**: Construct objects properly

## Keybind Wiring Pattern (CfgInputActions → script)

When you declare a `CfgInputAction` in `config.cpp` and bind keys to it in
`data/modded_Inputs.xml`, the player sees the action and key in the options
menu, BUT pressing the key does nothing unless script-side `LocalPress()`
handlers are added. This is a recurring "keybinds lost after merge" bug.

**The fix** is in `MissionGameplay::OnUpdate()` (or wherever you poll input):

```enforce
override void OnUpdate(float timeslice) {
    super.OnUpdate(timeslice);
    if (!GetGame().GetPlayer()) return;

    UAInput input = null;
    if (GetUApi()) input = GetUApi().GetInputByName("UAYourActionName");

    if (input && input.LocalPress()) {
        // dispatch to manager or widget
    }
}
```

**Always check 4 things** for every keybind you wire:

1. **Get the input** — `GetUApi().GetInputByName("UAYourActionName")` returns
   `null` if the action isn't declared in `config.cpp`/`modded_Inputs.xml`.
   Guard with `if (input)`.
2. **Poll on press, not on hold** — use `.LocalPress()` not `.LocalValue()`.
   `.LocalPress()` fires once on key down.
3. **Suppress during UI focus** — call `input.Supress()` when chat input is
   open, when a `UIScriptedMenu` is open, etc. Otherwise the player's typed
   character fires the keybind.
4. **Dispatch to a manager or widget method**, not inline logic. The handler
   in `OnUpdate` should be 1-3 lines that call into a dedicated method.
   Keeps the per-frame work cheap and the test surface small.

**For Toggle-style keybinds** (show/hide compass, player list, etc.) add
`Toggle*` methods to a central manager (e.g. `VPPHUDManager.ToggleCompass()`)
that flip the setting, save it, and update the live widget. Don't toggle
the widget directly — the settings struct and the JSON file are the source
of truth and need to know about the new state.

**For Delete-marker style keybinds** that fire when no UI is open, the
handler needs a target. Track the most-recently-opened marker UID in
a static field on the client manager (`m_LastEditedMarkerUID`); the popup
or edit dialog sets it on open. The Delete keybind reads it.

**Audit command** — to find which CfgInputActions are declared but not
**Audit command** — to find which CfgInputActions are declared but not wired in script:

```bash
# Actions declared in config.cpp
grep -E "class UA[A-Z]" config.cpp

# Actions wired in script (GetInputByName)
grep -rE 'GetInputByName\("UA[A-Z]' scripts/
```

The diff between these two sets is your list of dead keybinds.

## See Also
- `references/dayz-launcher-build.md` — building a Windows .exe DayZ launcher from a Linux host (C# .NET cross-compile)

## Related Skills

**Pitfall:** A central `HUDManager` singleton with a `RegisterWidget(name, w)`
method is the standard pattern for syncing settings sliders to live widgets.
**Every HUD widget must explicitly call `RegisterWidget()` after init**,
otherwise the manager's lookup for that name returns `null` and the settings
slider is a silent no-op.

```enforce
// In MissionGameplay::InitializeHUDWidgets():
m_PlayerListWidget = new VPPPlayerListWidget();
Widget playerListRoot = m_PlayerListWidget.Init();
if (playerListRoot) {
    m_PlayerListWidget.Show(settings.PlayerlistEnabled);
    VPPHUDManager.Get().RegisterWidget("PlayerList", playerListRoot);  // <- CRITICAL
}
```

Common bug shape: developer adds the new widget, forgets the RegisterWidget
call, then the user reports "the position slider for X doesn't work". The
slider DOES call `VPPHUDManager.Get().SetWidgetPos("X", ...)` — the manager
just has `m_XRoot == null` and silently no-ops.

**Audit command** — to find unregistered widgets:

```bash
# Manager supports these names
grep -E 'if \(name == "' scripts/.../VPPHUDManager.c

# Widgets that call RegisterWidget
grep -rn 'RegisterWidget\("' scripts/

# Every widget Init() that should also call RegisterWidget — compare manually
grep -rnE 'm_\w+Widget = new \w+Widget\(\)' scripts/
```

The intersection of "widgets that exist" minus "widgets that registered" is
your list of silent-no-op bugs.

## Workflow

### 1. Parse the crash log
- `Class:` and `Function:` tell you which mod class/method crashed
- Stack trace shows the mod chain (e.g., `VPPAdminTools -> BaseBuildingPlus -> VanillaPPMap`)
- SEH exception code: `0xC0000005` = access violation, `0x80000101` = Wine-translated SIGSEGV

### 2. Find source code -- check in order
1. **Deployed PBO binary** (`~/games/DayZ/Mods/@<Mod>/addons/*.pbo`) -- the actual running code
2. **Workspace source** (`~/apogrps/`, `~/apogrps_qwen/`, `~/.hermes/your-workspace/apogrps/`) -- may differ from deployed
3. **Temp build output** (`~/.local/share/Steam/steamapps/compatdata/221100/pfx/.../Temp/`) -- intermediate build files

**Important**: Line numbers in crash logs match the DEPLOYED PBO, not workspace source. Always extract from PBO first.

### 3. Extract source from PBO binary
PBOs contain uncompressed script source. Extract with text scanning:

```python
pbo_path = '~/games/DayZ/Mods/@VanillaPPMap/addons/VanillaPPMap.pbo'
with open(pbo_path, 'rb') as f:
    data = f.read()
# Find class by name
idx = data.find(b'class VPPMapMenu extends')
# Extract until next class or marker
source = data[idx:end].decode('ascii', errors='replace')
```

For finding layout files inside PBOs:
```python
# Layout files are stored as readable text
idx = data.find(b'FrameWidgetClass VPPNoBuildAdminUI')
```

### 4. Understand the call chain
DayZ mod chain: multiple mods override the same methods (MissionGameplay::OnUpdate). The crash shows which mod in the chain was executing. Key patterns:
- `EnterScriptedMenu()` -> engine calls `Init()` on the menu class
- `ShowScriptedMenu()` -> calls `OnShow()`
- `OnUpdate()` runs every frame; if it re-creates menus, Init() can be called from OnUpdate context

### Common crash causes on Linux/Proton
- **0x80000101**: Wine/Proton translated SIGSEGV — native C++ crash in engine code (widget allocation, D3D calls)
**Important**: If DayZLauncher.exe runs but does NOT launch DayZ (exits silently, exit code 1 under Wine), the launcher-build reference has a diagnostic checklist and config format guide. See `references/dayz-launcher-build.md`.

## Common crash causes on Linux/Proton (Wine)
- **0x80000101**: Wine/Proton translated SIGSEGV — native C++ crash in engine code (widget allocation, D3D calls)
- **Wine + .NET Launcher crash** (PE32+ WinExe): `Console.ReadKey()`/`Console.ReadLine()` inside a WinExe under Wine crashes with access violation in `kernelbase` → `coreclr` → `System.Console`. Wine does not allocate a console handle for GUI apps, so .NET's Console class has no valid handle. Fix: make the launcher headless — no interactive console I/O, config via CLI args or config.json only. See `references/dayz-launcher-build.md` for the full launcher build workflow.
- Complex widget trees in layouts can trigger Proton edge cases
- Clear shader cache: `rm -rf ~/.local/share/Steam/steamapps/shadercache/221100/`
- Check Proton version (Proton-GE handles DayZ UI better)

### 5b. Distinct crash class: DayZ SERVER binary `0x60` page fault on Zen2 (2026-07-17)

**Symptom:** `wine: Unhandled page fault on read access to 0000000000000060 at address
00000001407F3580` → `Exception code: C0000005 ACCESS_VIOLATION`, Exit 5. Deterministic —
SAME address (`1407F3580`) across EVERY launch config tried: system wine, Proton-Experimental,
Proton-GE Latest, 5 mods, 59 mods, software rendering, DXVK override. Crash happens at
ENGINE LOAD (RPT shows `Addons: DZ_Worlds_*`, `DZ_Weapons_*` before any mission/loot load).

**Key distinguishing fact:** the DayZ **CLIENT** (`DayZ_x64.exe`) boots fine on this box under
Proton-Experimental; only the **SERVER** (`DayZServer_x64.exe`, 14 Dec 2025 build) segfaults.
This is a server-binary-specific incompatibility with the operator's CPU (AMD Ryzen 7 3800X,
Zen2 / 2019). The fault bytes (`48 3B 11` CMP; `48 8D 4A 08` LEA RCX,[RDX+8]) point at a
null-`this` vtable deref in engine init — i.e. the binary itself, not Wine/Proton/mods/loot.

**What does NOT help (all verified to crash identically):** DXVK override, `-noLauncher`,
software rendering, switching Wine/Proton flavor, reducing mod count, reinstalling nothing.

**What to check / try (the operator decides, agent does not guess):**
1. Is this a DIFFERENT crash than the script-compile error? The server can ALSO fail later with
   `Can't compile "World" script module! Apocalypse/scripts/4_World/VPPWebhookManager.c(99):
   Broken expression` — that one is a REAL EnforceScript compile error (see §Compilation Debug)
   and means the engine LOADED fine. The `0x60` page fault is EARLIER and blocks even reaching
   compile. Do not conflate them: page-fault = engine never started; compile error = engine ok.
2. Run the server on a Zen3+ host (Ryzen 5000+ / Intel 11th+) — the same binary likely boots.
3. Try QEMU with `-cpu Skylake` / `-cpu Zen3` emulation wrapping wine (overkill, last resort).
4. A different `DayZServer_x64.exe` build that targets older CPU microarch.

Full reproduction matrix + the exact fault-byte decode in `references/dayz-server-zen2-crash.md`.

### 6. Find source code -- check in order

### 6. Fix approaches
- Add null/layout-exists guards around CreateWidgets calls
- Wrap complex UI initialization in try-catch patterns
- Simplify widget tree depth in .layout files
- Update Proton version or GPU drivers

### File locations
- Client mods: `~/games/DayZ/Mods/@<Mod>/addons/`
- Workshop PBOs: `~/.local/share/Steam/steamapps/workshop/content/221100/`
- Workspace source: `~/apogrps/` (main) or `~/apogrps_qwen/` (Qwen branch)
- Server: `~/games/DayZ/Server/`
- Proton prefix: `~/.local/share/Steam/steamapps/compatdata/221100/pfx/`

## Server Liveness: Silent RPT Log ≠ Server Hanging

**The trap:** DayZ writes C++ init lines (`Updating base class`, `Conflicting addon`, `fsync: up and running`) to the RPT log, then goes **silent** once the engine reaches the "listening for player connections" state. Mission init is deferred until the first player connects. The RPT file mtime can stop updating for 10+ minutes on a healthy server with no clients.

**DO NOT conclude the server is stuck just because:**
- RPT log hasn't updated in N minutes
- `ps` shows process at 0–5% CPU with all threads in `futex_wait_multiple`
- Port 2302 TCP gives "Connection refused"

**DO use this 3-check recipe to confirm liveness:**

```bash
# CRITICAL: get the RIGHT PID. Under Proton, the python/proton parent is a launcher.
# The actual DayZ server is the DayZServer_x64.exe Wine child, and its FDs are NOT
# visible from /proc/<proton_pid>/fd/ (which shows only 3 FDs: /dev/null + stdout+stderr).
DAYZ_PID=$(pgrep -f "DayZServer_x64.exe" | head -1)

# 1. Process alive
ps -p $DAYZ_PID -o pid,pcpu,pmem,etime,cmd
# expect: %CPU small but non-zero over time, etime > 0

# 2. UDP game port listening (DayZ uses UDP for game traffic)
bash -c "echo > /dev/udp/127.0.0.1/2302"   # exit 0 = open
# TCP 2302 is normally REFUSED (DayZ uses TCP only for RCon on a different port)

# 3. Mod PBOs are open in the DayZServer_x64.exe process (proves load + liveness)
ls -la /proc/$DAYZ_PID/fd/ | grep -E "Apocalypse.pbo|VanillaPPMap.pbo"
```

If all three are true, the server is up and waiting. Re-check RPT only after a player connects or admin action.

**About RCon:** DayZ Dedicated Server has no headless mission-start option. The `script_*.log` file is only created on the first player connect. enableRCon + BattlEye RCon + Source-Engine RCon have all been verified NOT to trigger mission load. If the user wants EnforceScript compile verification, they need a real DayZ client connected to the server (or a Python fake client doing the Source-Engine A2S+connect handshake). See `references/linux-proton-server-deploy.md` for the full RCon investigation and the local-RPT evidence (29-minute gap between server start and first connect in the operator's own log).

## Related Skills
- `dayz-mod-ui-dev`: For broader DayZ UI development patterns
- `enforce-script-syntax`: For EnforceScript-specific rules
- `dayz-mod-merge-workflow`: For mod merge workflow
- `dayz-pbo-build-deploy`: For PBO building and deployment
- `dayz-layout-crash-debug`: For GUI layout file issues
- See `references/linux-proton-server-deploy.md` and `references/pbo-format-and-verification.md` in this skill for the full Linux+Proton deploy and PBO verification recipes

### Root Cause
Settings UI and HUD widgets are decoupled — UI stores values locally but nothing bridges to the widget or JSON file.

### Solution: Central HUD Manager Singleton

All HUD state changes must flow through one manager that:
1. Holds `Widget` references to actual HUD elements (PlayerList, Minimap, Chat, Compass)
2. `SetWidgetPos(name, x, y)` — applies to widget live AND writes to settings struct
3. `SaveToFile()` — persists JSON after every change (not batched)
4. Widgets read initial state from saved settings on `Init()`

```c
class VPPHUDManager {
    private static ref VPPHUDManager s_Instance;
    private Widget m_PlayerListRoot;
    private Widget m_MinimapRoot;
    private Widget m_ChatRoot;

    static VPPHUDManager Get() {
        if (!s_Instance) s_Instance = new VPPHUDManager();
        return s_Instance;
    }

    void RegisterWidget(string name, Widget w) {
        if (name == "PlayerList") m_PlayerListRoot = w;
        else if (name == "Minimap") m_MinimapRoot = w;
        else if (name == "Chat") m_ChatRoot = w;
    }

    void SetWidgetPos(string name, float x, float y) {
        VPPClientSettings s = VPPClientManager.GetInstance().GetClientSettings();
        Widget w;
        if (name == "PlayerList") {
            s.pos_PlayerListX = x; s.pos_PlayerListY = y;
            w = m_PlayerListRoot;
        }
        // ... etc
        if (w) w.SetPos(x * 1000.0, y * 1000.0);
        VPPClientManager.GetInstance().SaveClientSettings();
    }
}
```

### Settings UI Integration

Override `OnChange` on sliders/editboxes to call the manager immediately:

```c
override bool OnChange(Widget w, int x, int y, bool finished) {
    if (w == sliderPX || w == sliderPY) {
        string elemName = "PlayerList"; // based on m_SelectedPos
        VPPHUDManager.Get().SetWidgetPos(elemName, sliderPX.GetCurrent(), sliderPY.GetCurrent());
        UpdatePositionPreview();
        return true;
    }
    return false;
}
```

Checkboxes (OnChanged) must also call manager for immediate visibility:
```c
if (chkCompass) { s.CompassEnabled = chkCompass.IsChecked(); VPPHUDManager.Get().SetCompassVisible(s.CompassEnabled); }
```

### Critical: No Widget Owns Its Own State
Widgets must NEVER store position/state independently. Always read from manager at init, always update through manager on change.

---

## LBmaster Admin Menu Layout Architecture

### When to Use
- Building or replicating an admin menu in DayZ that matches LBmaster's visual style
- Creating tabbed admin pages loaded dynamically into a container
- Debugging why page layouts don't render correctly when loaded by a shell

### Architecture: Shell vs Page

LBmaster uses a **two-layer layout system**:

#### Shell Layout (the menu container)
Contains the menu chrome — tab bar, close button, save button, page container.

```
PanelWidgetClass rootFrame {
  color 0.506 0.506 0.506 0.392       // semi-transparent dark background
  style rover_sim_colorable            // applies background rendering
  size 1 1
  halign center_ref
  valign center_ref
  {
    // Page content area — pages are LOADED into here
    PanelWidgetClass pageWidgets {
      ignorepointer 1
      position 0 5
      size 1 1
      halign center_ref
      valign bottom_ref
      scriptclass "LBGapHandler"
      gapHorizontal 10
      gapVertical 85
    }

    // Tab buttons — horizontal wrap, 165px gap
    WrapSpacerWidgetClass buttonWidgets {
      clipchildren 0
      ignorepointer 1
      position 5 5
      size 1 70
      scriptclass "LBGapHandler"
      gapHorizontal 165
    }

    // Close button (top-right)
    ButtonWidgetClass btn_close_admin {
      position 5 5
      size 150 25
      halign right_ref
      hexactpos 1 | vexactpos 1
      hexactsize 1 | vexactsize 1
      style Empty
      {
        PanelWidgetClass close_panel {
          ignorepointer 1
          size 1 1
          color 1 0.196 0.196 1          // red outline
          style LB_Clean_outline
          {
            TextWidgetClass close_text {
              ignorepointer 1 | size 1 1
              text "#close"
              font "gui/fonts/Metron14"
              "text halign" center
              "text valign" center
              color 1 1 1 1
            }
          }
        }
      }
    }

    // Save button (bottom-right)
    ButtonWidgetClass btn_save {
      position 5 5
      size 200 25
      halign right_ref
      valign bottom_ref
      priority 600
      style Empty
      {
        PanelWidgetClass save_panel {
          ignorepointer 1
          size 1 1
          color 0 1 0 1                    // green outline
          style LB_Clean_outline
          {
            TextWidgetClass save_text {
              text "SAVE CONFIG"
              font "gui/fonts/Metron14"
              color 0 0 0 1                 // black text on green
            }
          }
        }
      }
    }

    // Version text
    MultilineTextWidgetClass txt_version {
      ignorepointer 1
      position 5 35
      size 150 15
      halign right_ref
      font "gui/fonts/sdf_MetronBook72"
      "exact text" 1 | "exact text size" 10
      color 0.47 0.47 0.47 1
    }
  }
}
```

#### Page Layout (individual admin page content)
**CRITICAL:** Pages are FLAT `PanelWidgetClass` children loaded into `pageWidgets`. Do NOT add `FrameWidgetClass`, `scriptclass`, or nested panels.

```
PanelWidgetClass AdminPage_YourPage {
  visible 1
  size 500 550                           // standard LBmaster page size
  style blank                            // no background — shell handles that
  {
    // Section header
    TextWidgetClass lbl_title {
      ignorepointer 1
      position 0 0
      size 500 25
      hexactpos 1 | hexactsize 1
      font "gui/fonts/sdf_MetronBook72"
      color 1 1 1 1
      "text halign" center
      text "SECTION TITLE"
    }

    // Checkbox
    CheckBoxWidgetClass chkSomething {
      position 10 35
      size 480 20
      hexactpos 1 | hexactsize 1
      text "Label" | checked 0
    }

    // Label (right-aligned)
    TextWidgetClass lblSomething {
      ignorepointer 1
      position 10 65
      size 250 20
      hexactpos 1 | hexactsize 1
      font "gui/fonts/sdf_MetronBook72"
      color 0.8 0.8 0.8 1                // slightly dimmed
      text "Field Name"
      "text halign" right
    }

    // Edit box
    EditBoxWidgetClass editSomething {
      position 270 65
      size 80 20
      hexactpos 1 | hexactsize 1
      text "default"
    }

    // Slider
    SliderWidgetClass sldSomething {
      color 1 0.5 0 1                    // orange fill
      position 10 90
      size 340 20
      hexactpos 1 | hexactsize 1
      maximum 100
      current 50
      "fill in" 1
    }

    // List
    TextListboxWidgetClass list_items {
      position 10 Y
      size 400 150
      hexactpos 1 | hexactsize 1
      lines 8
    }

    // Button
    ButtonWidgetClass btnAction {
      position X Y
      size 80 20
      hexactpos 1 | hexactsize 1
      text "Label"
    }
  }
}
```

### Common Mistakes

| Mistake | Why It Breaks | Fix |
|---------|---------------|-----|
| Page uses `FrameWidgetClass rootFrame` with `scriptclass "LBMenuPopulator"` | Page already loaded into shell's `pageWidgets`; duplicate structure confuses widget finding | Use flat `PanelWidgetClass` with `style blank` |
| Page nests `panel_left`/`panel_right` containers | Shell expects flat widget list for `FindAnyWidget()` | Put widgets directly inside the PanelWidgetClass |
| Page includes its own background/overlay | Shell's `rover_sim_colorable` already provides background | `style blank` on pages |
| Widgets missing `hexactpos 1` / `hexactsize 1` | LBmaster uses exact pixel positioning; without these, widgets float | Always set both flags |
| Using `size 1 1` for widget-sized elements | Relative sizing wraps to parent; widgets need pixel sizes | Use pixel sizes for child widgets |

### Widget Property Cheat Sheet

| Widget Type | Sizing | Positioning | Notes |
|---|---|---|---|
| `TextWidgetClass` | `size W 20` | `hexactpos 1 hexactsize 1` | Labels: `color 0.8 0.8 0.8 1`, `text halign right` |
| `CheckBoxWidgetClass` | `size 480 20` | `hexactpos 1 hexactsize 1` | Checkbox size is fixed by engine |
| `EditBoxWidgetClass` | `size 80-120 20` | `hexactpos 1 hexactsize 1` | |
| `SliderWidgetClass` | `size 340 20` | `hexactpos 1 hexactsize 1` | Fill color: `1 0.5 0 1` (orange) |
| `TextListboxWidgetClass` | `size W H` | `hexactpos 1 hexactsize 1` | `lines N` for visible row count |
| `ButtonWidgetClass` | `size 80-150 20` | `hexactpos 1 hexactsize 1` | |

### Color Constants

| Element | RGBA | Notes |
|---|---|---|
| Shell background | `0.506 0.506 0.506 0.392` | Semi-transparent dark gray |
| Text (bright) | `1 1 1 1` | White — headers, active labels |
| Text (dim) | `0.8 0.8 0.8 1` | Slightly dimmed — field labels |
| Text (muted) | `0.47 0.47 0.47 1` | Gray — version info |
| Close button | `1 0.196 0.196 1` | Red |
| Save button | `0 1 0 1` | Green, black text `0 0 0 1` |
| Slider fill | `1 0.5 0 1` | Orange |
| Role headers | `1 0.8 0.2 1` | Gold/amber — permission tiers |
| Style: LB_Clean_outline | — | White 1px border on colored backgrounds |
| Style: rover_sim_colorable | — | Shell background rendering |
| Style: blank | — | No background/border |

### Fonts

| Font | Usage |
|---|---|
| `gui/fonts/sdf_MetronBook72` | Main UI font — headers, labels, all text |
| `gui/fonts/Metron14` | Button text (close, save) |

### Variant: Full-Screen Standalone Config Panel (4-Quadrant)

A modal overlay covering the entire screen — NOT loaded into the shell's `pageWidgets`. Used for settings/config that needs maximum space.

#### Layout Root
Placed at ROOT level of the parent menu (e.g., VPPMapMenu), NOT inside any shell container:
```
PanelWidgetClass panel_settings_root {
  visible 0
  position 0 0
  size 1 1
  priority 800              // float above map/markers
  hexactpos 1
  vexactpos 1
  hexactsize 0
  vexactsize 0
  color 0.506 0.506 0.506 0.392    // full-screen overlay
  style rover_sim_colorable
  scriptclass "LBMenuPopulator"
  {
    // 4 quadrants + buttons (see below)
  }
}
```

#### Quadrant Pattern
```
PanelWidgetClass quadrantName {
  ignorepointer 1
  position X Y              // 0 or 0.51 for X, 0 or 0.51+ for Y
  size 0.49 0.46            // ~49% width, ~46% height (1% gap between)
  hexactpos 1
  vexactpos 1|0
  hexactsize 0
  vexactsize 0
  style LB_Clean_outline    // white 1px border
  {
    // Section header
    TextWidgetClass lblName {
      ignorepointer 1
      position 0 5
      size 1 25
      halign center_ref
      hexactpos 1 vexactpos 1 hexactsize 0 vexactsize 1
      font "gui/fonts/MetronBold16"
      color 1 0.6 0.1 1              // amber/gold
      text "Section Title"
      "text halign" center
    }
    // Controls inside...
  }
}
```

#### Quadrant Layout Map
```
+--------------------------+--------------------------+
| position 0 0             | position 0.51 0          |
| size 0.49 0.46           | size 0.49 0.46           |
| (Top-Left)               | (Top-Right)              |
+--------------------------+--------------------------+
| position 0 0.51          | position 0.51 0.51       |
| size 0.49 0.46           | size 0.49 0.46           |
| (Bottom-Left)            | (Bottom-Right)           |
+--------------------------+--------------------------+
```

#### Header Inside Quadrants
Color: `1 0.6 0.1 1` (amber) — matches the gold headers in LBmaster admin panels.

#### Close Button Wiring (Critical Pattern)
When the config panel is a separate layout (`panel_settings_root`) that needs to show/hide sibling widgets:

1. **Panel handler needs parent root reference:**
```cpp
class MyConfigHandler extends ScriptedWidgetEventHandler {
    Widget layoutRoot;
    private Widget m_ParentRoot;

    void Init(Widget root, Widget parentRoot = null) {
        layoutRoot = root;
        m_ParentRoot = parentRoot;
    }

    override bool OnClick(Widget w, int x, int y, int button) {
        if (w == btnClose) {
            if (m_ParentRoot) {
                m_ParentRoot.FindAnyWidget("panel_settings_root").Show(false);
                m_ParentRoot.FindAnyWidget("panel_list_frame").Show(true);
                m_ParentRoot.FindAnyWidget("Sidebar_Root").Show(true);
            }
            return true;
        }
        return false;
    }
}
```

2. **Parent passes its root when creating the handler:**
```cpp
// In VPPMapMenu.c (parent)
m_SettingsHandler = new MyConfigHandler();
m_SettingsUIRoot.SetHandler(m_SettingsHandler);
m_SettingsHandler.Init(m_SettingsUIRoot, layoutRoot);  // <-- pass layoutRoot
```

### Styling Choices

| Element | Color | Notes |
|---|---|---|
| Section headers (inside quadrants) | `1 0.6 0.1 1` | Amber/gold |
| Labels | `0.8 0.8 0.8 1` | Dim white |
| Checkbox labels | `0.2 0.8 0.2 1` | Green |
| Slider colors | Varies per section | Red `1 0 0 1`, Green `0.2 0.8 0.2 1`, Orange `1 0.5 0 1` |
| Separators | `PanelWidgetClass` with `color 1 0.5 0 0.3` | 1px orange line |
| Font (headers) | `gui/fonts/MetronBold16` | Bold 16 |
| Font (body) | `gui/fonts/Metron14` | Regular 14 |
| Close button | `1 0.196 0.196 1` | Red outline |
| Save button | `0 1 0 1` | Green outline |
| Background | `0.506 0.506 0.506 0.392` + `rover_sim_colorable` | Semi-transparent overlay |

### Verification
- [ ] Shell has `pageWidgets` (PanelWidgetClass with `LBGapHandler`) and `buttonWidgets` (WrapSpacerWidgetClass)
- [ ] Each page is a flat `PanelWidgetClass` with `style blank`, `size 500 550`
- [ ] All widgets have `hexactpos 1` and `hexactsize 1`
- [ ] Widget names match what the C# script expects via `FindAnyWidget()`
- [ ] No nested panel containers inside pages
- [ ] Shell background uses `0.506 0.506 0.506 0.392` + `rover_sim_colorable`
- [ ] Standalone config panels use `priority 800`, `visible 0`, `size 1 1` at root level
- [ ] Config panel handler receives parent root via Init() for close/show sibling logic
- [ ] Quadrant panels use `style LB_Clean_outline`, `ignorepointer 1`, 0.49×0.46 sizing

---

## Client-Server Mod Separation

### Core Pattern
Two mods in this architecture:
- **VanillaPPMap** (client mod) — UI, markers, user-facing features
- **VanillaPPMap_Server** (server mod) — group management, server-side state

### Critical Rule: missionServer.c Runs on BOTH
`missionServer.c` executes on the server for ALL connected players. Adding server-side handlers (like GROUP_CREATE) to the client mod's missionServer.c creates **duplicate handlers** — both fire on the server.

### Symptoms of Duplicate Handlers
- "String CORRUPTED - FIX OnStoreLoad()" errors
- `ctx.Read(tag)` fails because first handler consumed the ctx buffer
- Error at line where `ParamsReadContext.Read()` is called

### RPC Routing Chain
```
Client RPC → DayZGame.OnRPC → VanillaPlusPlus.OnRPC (client mod)
    ↓ (if GROUP_RPC_MIN <= rpc <= GROUP_RPC_MAX)
VPPRPCManager.OnRPC → registered handler (GroupServerManager)
```

### What Goes Where

| Component | Client Mod (VanillaPPMap) | Server Mod (VanillaPPMap_Server) |
|-----------|--------------------------|----------------------------------|
| missionServer.c | Only marker RPCs (GetRPCManager) | N/A — no missionServer.c |
| Group RPCs | UI sends via ScriptRPC | GroupServerManager handles |
| VPPRPCManager | Routes to VPPGroupRPCs | N/A — client mod provides |
| Chat/VPPChatManager | Client UI | Server-side state |

### Anti-Patterns
1. ❌ Adding GROUP_CREATE/etc handlers to client mod's missionServer.c
2. ❌ Assuming server mod has its own VPPRPCManager (uses client mod's)
3. ❌ Not clearing compiled script cache after reverting missionServer.c

### RPC Override Order: super.OnRPC() Causes ctx Corruption

When overriding `OnRPC` (e.g., `VanillaPlusPlus.OnRPC`), calling `super.OnRPC()` BEFORE your handler **consumes/corrupts `ParamsReadContext`** data.

**Bad (ctx consumed by super before VPP reads it):**
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    super.OnRPC(sender, target, rpc_type, ctx); // ← ctx may be consumed here
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx); // ← reads corrupted ctx
    }
}
```

**Fix (route VPP RPCs before super, then return):**
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
        return; // ← skip super for VPP-managed RPCs
    }
    super.OnRPC(sender, target, rpc_type, ctx); // ← non-VPP RPCs still get base handling
}
```

**Rule:** If your mod manages its own RPC range, intercept BEFORE calling super. The `return` prevents the base class from touching data your handler needs.

### Fix: Compiled Cache
If String CORRUPTED persists after source revert:
1. Stop server completely
2. Delete `storage_x/` in server profile
3. Delete `.c.cache` files in `mpmissions/`
4. Restart — server recompiles from source

### Debug Check
Look for this in server logs:
```
[VPPGroups] Server-side group handlers registered.
```
If present, your client mod's missionServer.c still has old group code in compiled cache.

---

## Related Skills
- `dayz-mod-ui-dev`: For broader DayZ UI development patterns
- `enforce-script-syntax`: For EnforceScript-specific rules
- `dayz-mod-merge-workflow`: For mod merge workflow
- `dayz-pbo-build-deploy`: For PBO building and deployment
- `dayz-layout-crash-debug`: For GUI layout file issues

## Mazemaker DayZ Topic Sweep (research workflow)

**When to use:** The user asks to "pull everything" about a DayZ topic (weapons, loot, a mod,
deploy facts, anticheat vectors) from the brain — NOT just answer from memory. The operator
explicitly demands a *consequential, exhaustive* sweep, not a single recall.

**Procedure (do all, in order):**
1. **Multi-angle recall** — `mazemaker_recall_multi` with 2–5 phrasings per angle
   (entity wording, time framing, implicit vs explicit). Catches memories stored under
   different phrasing than the user's.
2. **Deep layer on hits** — for each hit >= 0.4: `mazemaker_think(memory_id, depth=2-3)`
   for graph neighbours, and `mazemaker_afe_facts(source_id=X)` for the atomic facts
   distilled from that session. Don't stop at the summary.
3. **Cross-check the plate** — actually read the referenced real files under
   `/home/alca/games/DayZ/` (types*.xml, TraderConfig.txt, masterplan/*.md, Mods/*/meta.cpp,
   Spawner*.json). Mazemaker summaries can drift; the live file is ground truth.
   Use `search_files(target='files')` + `read_file` — never trust a classname from memory alone.
4. **Condense into a knowledge bank** — write the extracted facts to
   `references/<topic>.md` (see `references/dayz-weapons-loot-knowledge.md` for the shape:
   invariants, tier/zone maps, gotchas, deploy facts, cross-refs). Keep it concise and for-task.
5. **Persist durable facts to Mazemaker** — `mazemaker_remember` with one label per discrete
   fact (fact:, invariant:, decision:). The plate file is the artifact; Mazemaker is the link.

**Pitfalls:**
- Single `mazemaker_recall` misses sideways-phrased memories. Always multi-angle for "pull everything".
- `afe_facts` on a memory id can return `[]` if that session was only auto-summarized — fall
  through to `think` + plate files, don't assume the fact is absent.
- Don't invent classnames/tiers — verify against the actual types*.xml on disk.

## Prerequisites
- DayZ mod development tools installed
- Access to mod source files
- Understanding of EnforceScript limitations vs standard scripting
- Basic sed/grep proficiency for file manipulation
- Patience for iterative debugging process

## Loot Rebuild Workflow (T1–T4 from scratch)

**When to use:** User wants to REBUILD the loot economy (not just audit it) — new classnames,
new types.xml tree, new 4-pillar distribution. Covers the build + audit procedure end to end.

**CRITICAL WORKFLOW CORRECTIONS (learned 2026-07-17, operator was explicit):**

1. **"von vorne! mit TOTALEM überblick!" — Audit from the FRONT, not incrementally.**
   Do NOT report partial "AUDIT PASS" on a hand-edited subset. After ANY multi-step edit
   spree, re-run ONE complete audit that reads every generated XML fresh from disk:
   well-formed + unique (no duplicate `<type>` entries — Python generators append
   duplicates silently), weapon-chain integrity, tier balance, T4-exclusive-zones, orphan refs.
   One combined `execute_code` block that loads all 7 files and asserts every invariant is
   worth more than 5 piecemeal "PASS" messages that missed the duplicate-T4 bug.

2. **"was ist mit ALL DEN ANDEREN ITEMS? von ALL DEN ANDEREN MODS!" — Inventory ALL mods.**
   The live `mpmissions/.../db/types.xml` (NOT a mod's own types.xml) is the ground-truth full
   item list — it has 5000+ items across every loaded mod (A6_*, FOG_*, BBP_*, MuchStuffPack,
   Munghard, etc.). A curated 100-item build is a STARTING POINT, not the deliverable, when the
   operator wants full coverage. Crawl the LIVE types.xml with `xml.etree` to get the real
   mod-prefix inventory; do not trust a mod-folder types.xml scan (most mods ship items in PBOs
   or server configs, not a loose types.xml — only ~13/59 mods had one).

3. **SINGLE SOURCE OF TRUTH — "nichts steuert es, diese zu renamen!"**
   The operator's exact pain: after iterative XML edits, APX_ classnames were ungoverned and
   renamable, and 6 files (types.xml + 4 distribution + mapgroupproto) could drift out of sync.
   FIX: one `APX_MANIFEST.json` (or `APX_MANIFEST_FULL.json` for the all-mods build) defines
   EVERY classname ONCE (name, category, tier, usages, weapon ammo-chain). A `generate_apx*.py`
   script derives ALL 7 XMLs from it. NO manual XML edits. Renaming = edit manifest + re-run
   generator. Add a `validate_deploy.py` (loads live config, asserts unique/types/rootclasses/
   orphan/T4-zone) and run it as a pre-flight before server start. This is the "Steuermechanismus"
   the operator demanded — embed it in every loot build from now on.

4. **Underground T4 zones MUST be EXCLUSIVE (hard rule).**
   `Underground_*` usage tags are attached to 470+ house/shed MapGroups in the live map as an
   ANNEX — if T4 loot uses `Underground_*` it spawns at EVERY house. Build a SEPARATE
   `mapgroupproto` extension with `APX_Underground_*` groups (own lootmax 4–6, 8 loot points,
   ONLY the `APX_Underground_*` usage) and bind T4 loot to `APX_Underground_*` so it spawns
   EXCLUSIVELY in the 7 real bunkers (Lopatino/Sobor/Sevorgrad/SeaPlatform/Ocean/Skalisty/OilRig).
   MapGroups live in the MISSION (mapgroupproto.xml), NOT in the mod PBO — inject into the live
   mission with a backup, or the live map crashes without the mod.

5. **"weniger ist mehr" STILL APPLIES to the CURATED set** — see User directive below. The
   "all mods" correction means COVER all mods' items in the distribution, not spam 100 dupes of
   one jacket. Curated APX_ items replace Vanilla 1:1; the full build maps existing mod classnames
   into the balanced tier/zone model without renaming them.
pendant 1:1, NO fill-spam. The Apocalyps3nd rebuild produced 92 curated items replacing 5332
Vanilla — that ratio is the goal. Quality over quantity.

**Key technique — use `execute_code`, not agent swarms, for the generation:**
delegate_task with Free-Tier models (nvidia/nemotron-3-*) TIMES OUT at 600s on a 60–90-item XML
write. Generate types_*.xml + the 4 distribution XMLs (cfgspawnabletypes / cfgrandompresets /
events / cfgeventgroups) deterministically with Python `xml.etree` + `minidom` pretty-print
(0.2s, reproducible). Run the audit-loop in the same/follow-up `execute_code` call. The "multi-agent
crew with audit loops" framing is fine as a masterplan, but the mechanical build step is code, not
slow subagents. (Full procedure + APX_ naming + audit scripts in `references/dayz-loot-rebuild-workflow.md`.)

**The 4 spawn pillars (every item lives in exactly one):** static loot (cfgspawnabletypes
attachments), random presets (cfgrandompresets cargo×item weighted), event groups (cfgeventgroups
fixed-coord child loot), dynamic events (events.xml + ce/cfgeconomycore.xml dyn_* defaults).

**Audit-loop (must all PASS before deploy):** (A) well-formed XML; (B) no orphaned ammo — every
`APX_Ammo_<cal>` has `APX_Mag_<cal>_*` in same tier; (C) no dangling APX_ refs in distribution
files (Vanilla world objects in cfgeventgroups are legit, only APX_ children must resolve);
(D) T4 usage 100% Underground_*, Coast/Town never carries Tier3/4; (E) balance ~T1=40/T2=25/T3=20/T4=15%.

**Deploy gate:** build into an ISOLATED mod folder (`@Apocalyps3nd_Loot/`), never write live server
types during a multi-week build. Live deploy = copy + backup + diff + validator + user approval.

## Supporting Reference Files
- `references/dayz-weapons-loot-knowledge.md` — A6 weapon tier tree, OpenClaw loot invariants,
  Trader config gotcha (no `/* */` comments — crashes server), Care-Package/LootChest/Spawner
  systems, TPAD deploy facts, VANGUARD anticheat cross-refs.
- `references/dayz-loot-rebuild-workflow.md` — 4-pillar spawn model, APX_* naming convention,
  types.xml entry shape, full audit-loop Python snippets, execute_code-over-agent-swarm lesson,
  merge + isolated-mod deploy gate.
- `references/dayz-apocalypse-project-layout.md` — where the Apocalypse/VanillaPPMap source,
  scripts, PBOs, and start script live; why you must use build_and_start.sh and not self-assemble
  a launcher; the 0x60-vs-script-compile crash distinction.
- `references/dayz-server-zen2-crash.md` — full reproduction matrix for the DayZ server `0x60`
  page-fault on Zen2, fault-byte decode, and what does/doesn't help.
