---
name: discord-client-splash-stuck
description: Debug Discord desktop client stuck on splash screen (Linux, especially tiling WMs like i3)
category: software-development
---

# Discord Client Splash Screen Stuck (Linux/i3)

## When to Use
Discord desktop client shows splash screen ("Hold Tight — Loading Discord") but never transitions to the main window. Common on i3 and other tiling window managers.

## Diagnosis Steps

### 1. Check Discord logs for the key indicator
```bash
discord --no-sandbox 2>&1 | grep -E "launchMainWindow|connected|splashScreen" | tail -20
```

**Critical signal:** `splashScreen.launchMainWindow: false` — means the splash decided NOT to open the main window despite module updates being complete.

### 2. Check window mapping state
```bash
xdotool search --name "Discord" | while read w; do
    GEO=$(xdotool getwindowgeometry $w 2>/dev/null)
    MAP=$(xwininfo -id $w 2>/dev/null | grep "Map State")
    echo "$w: $GEO | $MAP"
done
```

**Key finding:** The main Discord window (typically 948x1039) shows `Map State: IsUnMapped` — it exists but the WM never maps it to screen.

### 3. Understand the failure chain
1. Discord splash starts, checks for module updates
2. Updates complete (or none needed)
3. `splashScreen.launchMainWindow: false` — THE BUG
4. Main window is CREATED (win2 "Discord") but never MAPPED
5. Splash stays in `updateCountdownSeconds` loop forever
6. Gateway connects (`[FAST CONNECT] connected in Nms`) but UI never shows

## Root Cause
Electron/i3 compatibility issue. The splash screen's IPC handshake with the main window fails — the splash expects the main renderer to signal "ready", but on tiling WMs the window lifecycle differs from floating WMs, breaking this protocol.

## Approaches (in order of likelihood to work)

### A. Environment variable injection
```bash
export XDG_CURRENT_DESKTOP=GNOME
export DESKTOP_SESSION=gnome
discord --no-sandbox
```
Mixed effectiveness — helps some setups, does nothing on others.

### B. Clear module state
```bash
rm -rf ~/.config/discord/0.0.133/modules/pending
rm -rf ~/.config/discord/Cache ~/.config/discord/GPUCache ~/.config/discord/Code\ Cache
discord
```
Usually doesn't fix the splash bug, but clears corruption.

### C. Force window mapping (risky — may crash renderer)
```bash
# Move splash offscreen, map main window manually
xdotool windowmove $(xdotool search --name "discord" | head -1) 5000 5000
xdotool windowmap <main_window_id>
xdotool windowactivate <main_window_id>
```
Risk: Often crashes Electron because the renderer isn't actually ready.

### D. Discord Web as immediate workaround
```bash
chromium --app="https://discord.com/channels/@me" &
```
Always works. No splash, no Electron issues.

### E. Discord Canary / PTB
Newer Electron version may have the bug fixed.
```bash
yay -S discord-canary
```

### F. i3 config adjustments
Add to `~/.config/i3/config`:
```
for_window [class="discord"] floating enable
assign [class="discord"] → $ws1
```

## Log Patterns

**Broken (this bug):**
```
splashScreen.launchMainWindow: false
blackbox: N ✅ webContents.created web2 ""
blackbox: N ✅ window.created win2 "Discord"
Splash.updateCountdownSeconds: undefined  ← LOOP FOREVER
```

## Window Size Reference
| Window | Typical Size | Role |
|--------|-------------|------|
| win1 (discord) | 300x350 | Splash screen |
| win2 (Discord) | 948x1039 | Main app window |
| Small 19x19 | 19x19 | Tray/notification icon |

## Notes
- `--disable-splash-screen` is IGNORED by Discord
- Killing the splash window often kills the main window too (parent-child)
- Gateway connects fine — this is purely a UI/Electron issue
- SSL errors on `dc-telemetry.net` are normal, NOT the root cause
