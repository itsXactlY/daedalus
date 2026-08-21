---
name: i3-desktop-environment
description: Configure, troubleshoot, and maintain i3 window manager desktop environments on Linux (Garuda/Arch primary). Right-click context menus (jgmenu), mouse bindings, daemon lifecycles, and the "X worked before, now it's broken again" failure mode. Triggers when user reports broken right-click/context menu, jgmenu issues, missing bindings, "magical breakage" of previously-working i3 features, or asks to set up a new i3 install.
---

# i3 Desktop Environment

Maintain a stable i3 setup on Linux. The user's environment is Garuda/Arch with Dolphin, Konsole, Rofi (hermelin theme), and picom. The recurring pain point is features that "magically break again" — usually a daemon lifecycle or process-state issue, not a config issue.

## When to Load

Load this skill when the user reports:
- Right-click context menu broken / not appearing / appearing then vanishing
- "It worked before, now it's broken again" on any i3 feature
- A jgmenu, rofi, or picom daemon is misbehaving
- Need to set up i3 mouse bindings (button2, button3, $mod+button3)
- "Open with..." menu missing in Dolphin (this is a kio-extras issue, not i3 — see Pitfalls)

## The "Which Menu Do You Mean?" Rule (READ FIRST)

Under i3 + KDE Plasma there are AT LEAST FIVE completely different "right-click menus." If the user says "context menu is broken" or "right-click broken" without specifying, **ASK** before building anything. The fixes are not interchangeable.

| # | Where the click happens | What should appear | Where to fix |
|---|---|---|---|
| 1 | Desktop / root window (no focused window) | Custom popup menu (jgmenu, etc.) | `~/.config/i3/config` + launcher |
| 2 | File manager (Dolphin, Thunar) file item | "Öffnen mit…" / "Open with Other…" | KDE env (`XDG_CURRENT_DESKTOP`) + `kio-extras` |
| 3 | File manager (Dolphin, Thunar) empty area | View / Sort / New Folder | Dolphin's internal config, not i3 |
| 4 | Inside a GTK app (Chrome, code, mpv) | App's own menu / context menu | The app, not i3 |
| 5 | Inside a Qt/KDE app (Konsole, Kate) | App's own menu | The app, not i3 |

**Failure mode to avoid:** Building the wrong solution. The user reported "context menu broken" and what they meant was case (2). I built case (1) and shipped a jgmenu install — wrong layer entirely. Cost the user a turn. Lesson: when a phrase is ambiguous between i3-layer and app-layer issues, ask. Look at the screenshot. The screenshot IS the answer. If there is no screenshot, ask for one.

**Quick triage question to ask the user (if no screenshot):**
> "When you right-click, is the menu appearing on the desktop background, inside a file manager, or inside an application window? Can you screenshot the broken state?"

## Diagnosis Flow (always run first, in this order)

When something is "broken again," do NOT just retry the previous fix. Diagnose the actual state:

0. **PROVE the config is unchanged first.** The user often assumes the agent broke the i3 config. They didn't — verify before saying so:
   ```bash
   md5sum ~/.config/i3/config
   git -C ~/code/garuda-i3-baseline show origin/main:configs/i3/config | md5sum
   ```
   If the md5s match, the config was not touched. Report that as fact and proceed to daemon/service diagnostics below. Saying "I broke your config" when the md5s match is a hallucination and erodes trust.

1. **Is the binary installed?**
   ```bash
   which jgmenu rofi picom xdotool xdg-open polybar
   ```
   Missing binary = installation problem, not config problem.

2. **Is the binding / service wired?**
   ```bash
   grep -nE "button|bindsym" ~/.config/i3/config
   grep -nE "button|popup|menu" ~/.config/i3/enhancements.conf
   systemctl --user status polybar.service --no-pager
   pgrep -af jgmenu
   ```
   No match = binding was never added or was lost in a config edit. Service `inactive (dead)` = auto-start missing.

3. **Are there zombie processes?**
   ```bash
   pgrep -af jgmenu
   pgrep -af rofi
   pgrep -af picom
   pgrep -af polybar
   ```
   Multiple instances of jgmenu/rofi = race condition swallowing clicks. **Zero instances of polybar with `status: code=exited, status=0/SUCCESS`** = systemd killed the cgroup on launcher exit (Type=simple footgun, see "Polybar Won't Auto-Start" section below).

4. **Check the log:**
   ```bash
   tail -30 ~/.cache/jgmenu.log
   ```
   A hardened launcher should log every invocation.

5. **Validate the config:**
   ```bash
   i3 -C -c ~/.config/i3/config
   ```
   No output = valid. Errors = config issue.

6. **Check the right layer for the symptom.** Map the symptom to the menu table at the top of this file. If you can't, ask. Do NOT guess.
   - Desktop root window right-click → i3 binding + jgmenu (case 1)
   - Dolphin "Öffnen mit → Andere…" empty dropdown → **KDE environment vars** (case 2) — see "KDE Apps Under i3" section below
   - Dolphin "Öffnen mit" submenu missing entirely → `kio-extras` not installed
   - Chrome internal menu → GTK/WebKit, not i3
   - App-internal right-click → the app's own config, not i3

## KDE Apps Running Under i3 — The Recurring Footgun

Dolphin, Konsole, Kate, kio-extras-based dialogs, and most KF6 apps all read multiple env vars at startup to decide which features to enable. The "application discovery" services (kio-appinfo, ksycoca, ktrader) return EMPTY RESULTS when these vars are wrong. This is the most common reason i3 + KDE apps silently misbehave.

**Two env vars must be set correctly — not one:**

| Var | Wrong value (breaks Open With) | Correct value | Why |
|---|---|---|---|
| `XDG_CURRENT_DESKTOP` | `i3` | `KDE` or `KDE:i3` | KIO appinfo filter checks this; `i3` returns empty app lists |
| `XDG_MENU_PREFIX` | unset | `gnome-` (Garuda) | kbuildsycoca6 needs this to find `/etc/xdg/menus/gnome-applications.menu`; without it, the cache builds against the non-existent `applications.menu` and contains zero .desktop entries |

**Symptom signature:** Dolphin "Öffnen mit → Andere…" dialog opens but the application dropdown is empty AND the OK button is greyed out. The input field accepts text but no suggestions appear. The "Speichern" / "save association" checkbox does nothing on click. **Additionally** check `ls -la ~/.cache/ksycoca6_*` — if the cache is under 500KB, it's broken; healthy caches are 500KB–2MB.

**Root cause (90% of cases):** The user (or a previous agent) set `XDG_CURRENT_DESKTOP=i3` and/or left `XDG_MENU_PREFIX` unset in `~/.xprofile`, `~/.config/environment.d/*.conf`, or the i3 config. The `XDG_CURRENT_DESKTOP=i3` was a deliberate choice to suppress GNOME-app quirks, but it silently breaks KDE app discovery. The `XDG_MENU_PREFIX` was never set because Garuda's i3-default install doesn't ship `plasma-applications.menu` (only `gnome-applications.menu` exists), but the system still defaults to looking for `applications.menu`.

### The Three-Layer Env Config Architecture (READ THIS)

A "permanent fix" has to cover THREE independent env-propagation layers. **A previous fix that only touched one layer will silently re-break.** This is the actual reason i3+KDE bugs come back "magically."

| Layer | File | Affects | Mechanism |
|---|---|---|---|
| 1. environment.d | `~/.config/environment.d/*.conf` | systemd user services ONLY | PAM `pam_env` reads at login; systemd-environment.d generator propagates to unit env |
| 2. .xprofile | `~/.xprofile` | Login session shell + all children spawned by it | Sourced by SDDM (and similar DMs) before WM starts |
| 3. Running shell | `export VAR=value` | Only the current shell and its direct children | Must be re-typed in any new shell |

**Critical insight:** environment.d files are honored by PAM and systemd but are NOT inherited by bash shells. If you put `XDG_CURRENT_DESKTOP=KDE` only in environment.d, a new konsole window opened from the desktop will have `XDG_CURRENT_DESKTOP=i3` (the DM default), and any process spawned from that shell sees `i3`. The kbuildsycoca6 cache that such a process builds will be broken.

**The robust fix writes to layers 1 AND 2.** Layer 3 is for the current session only.

### Fix recipe (no sudo required)

1. **Layer 1** — `~/.config/environment.d/10-i3-kde.conf` (systemd services):
   ```ini
   XDG_CURRENT_DESKTOP=KDE:i3
   ```
   `~/.config/environment.d/15-kde-menu-prefix.conf` (ksycoca):
   ```ini
   XDG_MENU_PREFIX=<prefix>-
   ```
   **`<prefix>` is per-HOST, not per-distro.** Different Garuda installs ship different `/etc/xdg/menus/*.menu` files — desk had `gnome-applications.menu` (so `gnome-`) but tpad had `plasma-applications.menu` (so `plasma-`). Always check first: `ls /etc/xdg/menus/`.

2. **Layer 2** — `~/.xprofile` (login session):
   ```bash
   # WRONG — KDE apps return empty app lists:
   # export XDG_CURRENT_DESKTOP=i3
   #
   # RIGHT — KDE apps see themselves as on KDE; i3 still runs as WM:
   export XDG_CURRENT_DESKTOP=KDE:i3
   export XDG_MENU_PREFIX=<per-host-prefix>-
   ```
   This takes effect on next login. i3 is a window manager, not a desktop environment — `XDG_CURRENT_DESKTOP` is the DE name, which can be KDE while the WM is i3. The XDG_MENU_PREFIX value MUST match the prefix used in environment.d (per-host, see Layer 1).

3. **Layer 3** — current session (without logout). Propagate to systemd user env:
   ```bash
   systemctl --user set-environment \
       XDG_CURRENT_DESKTOP=KDE:i3 \
       XDG_MENU_PREFIX=gnome-
   dbus-update-activation-environment --systemd \
       XDG_CURRENT_DESKTOP=KDE:i3 \
       XDG_MENU_PREFIX=gnome-
   ```
   Note: this only affects NEW D-Bus activated services. To launch a single new Dolphin with correct env immediately:
   ```bash
   XDG_CURRENT_DESKTOP=KDE:i3 XDG_MENU_PREFIX=gnome- dolphin &
   ```
   Verify with `cat /proc/$(pgrep -n dolphin)/environ | tr '\0' '\n' | grep -E "XDG_"`.

4. **Restart KDE IO daemons so they pick up the new env.** Do NOT try to launch them as bare commands — `kiod6` and `kioexecd6` are libraries, not binaries in PATH. They start via the Plasma session or systemd:
   ```bash
   # kiod6 is already running (PID 220783 on Garuda) — DO NOT kill it
   # unless you also have a way to restart it. Killing it leaves the
   # system without KIO service, and `kiod6` as a bare command
   # gives "command not found" because it lives in /usr/lib/kf6/.
   # Safest: just log out and back in.
   ```
   For users who refuse to log out: close Dolphin, run the launch command from step 3. The newly-spawned dolphin and its kioworkers inherit the new env. Do not bother trying to restart the global kiod6 — it manages its own lifecycle.

5. **Refresh caches** (cheap, mandatory if cache was built under wrong env):
   ```bash
   update-desktop-database ~/.local/share/applications/
   kbuildsycoca6 --noincremental
   ```
   Run kbuildsycoca6 with the corrected env. If you run it from a shell that still has `XDG_MENU_PREFIX` unset, the new cache is also broken.

**Verification (run all):**
```bash
grep -E "XDG_CURRENT_DESKTOP|XDG_MENU_PREFIX" ~/.xprofile     # must show KDE:i3 and gnome-
ls ~/.config/environment.d/                                     # 10-i3-kde.conf + 15-kde-menu-prefix.conf exist
ls -la ~/.cache/ksycoca6_*                                      # must be > 500KB; if smaller, kbuildsycoca6 ran under wrong env
CACHE=$(ls ~/.cache/ksycoca6_* | head -1); stat -c%s "$CACHE"  # explicit size check
dbus-update-activation-environment --systemd | head -3         # env propagated
pgrep -af kiod6 | head -2                                       # kiod6 still running
cat /proc/$(pgrep -n dolphin)/environ | tr '\0' '\n' | grep XDG  # running dolphin sees correct env
```

**Why it "magically breaks again":** Two distinct cycles, both happen:

- **Cycle A (XDG_CURRENT_DESKTOP):** Any time kded6/kiod6 restarts (package update, OOM kill, kbuildsycoca6 run) the service re-reads the env. If `XDG_CURRENT_DESKTOP` is still "i3", the freshly-restarted service returns empty app lists immediately.
- **Cycle B (XDG_MENU_PREFIX) — sneakier:** kbuildsycoca6 is triggered automatically by kded, by pam_env hooks, by `update-desktop-database`, or by any package install that touches /usr/share/applications. If the trigger runs in a process that does NOT have `XDG_MENU_PREFIX=gnome-` in its env (e.g. a shell with bare `i3` session vars), the cache rebuilds against the non-existent `applications.menu`. Cache is now 200–300KB, contains zero .desktop entries, and KOpenWithDialog sees an empty registry. This cycle can fire WITHOUT any daemon restart, so it appears completely out of the blue.
- **A "fix" that only covers layer 1 (environment.d) is not enough** — any new shell will revert to layer 3 defaults, and a kbuildsycoca6 triggered from that shell will break the cache again.

**Anti-pattern to remember:** Never put `export XDG_CURRENT_DESKTOP=i3` in shell rc files assuming it's harmless. The var controls KDE/GNOME feature gating, not the WM. Also: never trust an environment.d-only fix to survive a long-lived session; layer 2 (`.xprofile`) is the durable anchor.

## Standard Right-Click Setup (jgmenu + i3)

### Install
```bash
sudo pacman -S jgmenu
```

### Wire the binding in `~/.config/i3/config`

```i3
# Right-click on root → menu
bindsym --release button3 exec --no-startup-id ~/.config/i3/scripts/jgmenu-run.sh

# Mod+Right-click → toggle floating on focused window
bindsym --release $mod+button3 floating toggle

# Mid-click on root → terminal
bindsym --release button2 exec konsole
```

### Autostart jgmenu daemon
```i3
exec --no-startup-id jgmenu --simple
```

### Config files
- `~/.config/jgmenu/jgmenurc` — colors, fonts, sizing (see templates/jgmenurc)
- `~/.config/jgmenu/append.csv` — menu items (see templates/append.csv)

## Why "Magical Breakage" Happens

The pattern: user installed jgmenu, it worked, then broke mysteriously. Almost always one of:

1. **Zombie jgmenu processes** — picom reload, i3 restart, or screen lock left orphaned instances. They grab the next right-click and die, looking like "menu didn't open."
2. **Race on i3 reload** — `exec --no-startup-id jgmenu --simple` during reload spawns a second daemon before the first cleans up. Two daemons fight for input.
3. **Config file vanished** — a `rm -rf ~/.config/jgmenu` or a sync tool overwrote it. Daemon falls back to defaults that look "broken" (white background, no items).
4. **Stale lock files after sleep/resume** — jgmenu's lock file in `/tmp` survives across sleep. The next click is denied.

**The fix is the hardened launcher pattern:** pkill stale instances, verify config exists, log every invocation. See `scripts/jgmenu-run.sh`.

## Pitfalls

- **NEVER bind `bindsym button3` without `--release`** — without it, i3 treats the click as a press-and-hold and the menu opens then immediately closes.
- **Do NOT put multiple `exec --no-startup-id jgmenu` lines** — only one daemon should exist. Use the launcher script for per-click invocation.
- **Dolphin "Öffnen mit → Andere…" is NOT an i3 problem** — it's a KDE environment issue. Symptom: dropdown empty, OK button grey. Fix: see "KDE Apps Running Under i3" section above. `XDG_CURRENT_DESKTOP=KDE` in `~/.xprofile` is the START of the fix, not the whole fix — on Garuda you also need `XDG_MENU_PREFIX=gnome-` for kbuildsycoca6 to populate the cache. `kio-extras` reinstall is the WRONG fix (we tried, it didn't help — the env was the problem).
- **kiod6 and kioexecd6 are NOT standalone binaries** — they live in `/usr/lib/kf6/` and are not on PATH. `pkill kiod6` followed by `kiod6 &` does NOT restart them; the binary just isn't there. The daemon is managed by the Plasma session or systemd user units. To "restart" it, log out and back in. Or just leave it running and launch the affected app (Dolphin) directly with the corrected env — only the new app's kioworkers need the new env, not the global kiod6.
- **ksycoca6 cache size is a smoke test** — `ls -la ~/.cache/ksycoca6_*` should show 500KB–2MB. A cache of 200–300KB means kbuildsycoca6 last ran under wrong env and the cache is structurally empty. Re-run kbuildsycoca6 with `XDG_MENU_PREFIX` correctly set. The cache is binary Qt format, so `strings | grep .desktop` returns zero hits even when the cache is healthy — use the size, not content greps, as the signal.
- **environment.d fixes are NOT sufficient on their own** — `~/.config/environment.d/*.conf` only affects systemd user services, not bash-spawned processes. A fix that writes to environment.d but not `.xprofile` will appear to work after login but break as soon as the user opens a fresh terminal. The durable fix writes to BOTH layers.
- **Garuda's `/etc/xdg/menus/` content is per-HOST, not per-distro** — different Garuda installs ship different files. desk had `gnome-applications.menu` (use prefix `gnome-`), tpad had `plasma-applications.menu` (use prefix `plasma-`). Other Garuda installs may ship `kde-applications.menu` or both. Verify on the actual host: `ls /etc/xdg/menus/`. The wrong prefix silently builds an empty ksycoca6 cache with no error message.
- **i3 config edits don't auto-reload** — use `Mod+Shift+R` to restart, or `i3-msg reload` from terminal. Always validate with `i3 -C -c ~/.config/i3/config` before.
- **`~/.config/jgmenu/append.csv` uses 4-column syntax:** `Name,^shortcut(command),exec,icon`. The third column is what actually runs; second is the accelerator hint shown in the menu. Don't confuse them.
- **picom reload can orphan input devices** — if jgmenu stops working after a picom restart, run `pkill -f jgmenu` then trigger right-click again. The hardened launcher does this automatically.
- **Garuda's default `/etc/sddm.conf` may override `~/.config/i3/config` at login** — if a config change doesn't take effect, check that the user's config is actually the one being loaded: `i3-msg -t get_config`.
- **`sed -i 's/...$VAR.../.../'` expands `$VAR` in the OUTER shell before sed sees it** — when scripting sed replacements that contain i3-config variables like `$ws3`, `$mod`, `$term`, either single-quote the sed expression (no expansion) or escape with `\$VAR`. Otherwise the i3 var becomes empty in the replacement and silently corrupts the config. Always validate with `i3 -C -c ~/.config/i3/config` after sed edits.
- **The user yells "config kaputt" but the config is usually fine** — when polybar / a daemon vanishes, the user assumes the i3 config was corrupted. Always run `md5sum` live vs `git show origin/main` FIRST before assuming or apologizing. If they match, report the match as fact and diagnose the service lifecycle instead. The full recipe for polybar + XAUTH + systemd-user is in `references/polybar-systemd-user-xauth.md`.
- **Polybar with `Type=simple` is a silent killer** — `launch.sh` forks polybar with `&` and exits 0; systemd tears down the cgroup. Symptom: `status: code=exited, status=0/SUCCESS` but `pgrep -af polybar` empty. Use `Type=oneshot` + `RemainAfterExit=yes` + `KillMode=process`.
- **`XAUTHORITY=*** — that path does not exist on SDDM-managed sessions. The real path is `/tmp/xauth_<random>` and changes per login. NEVER hardcode it in the service. Use `import-environment` from the live session via a separate `Before=polybar.service` oneshot unit.

## Polybar (Top Status Bar) Won't Auto-Start — the "empty bar" failure mode

This is the most common "magical breakage" report the user files, and the user has yelled about it multiple times ("i3 fixes wieder kaputt", "zum 100sten mal"). The actual root cause is almost never the i3 config — it's that polybar had no systemd-user service, OR the service was malformed, OR XAUTH drift broke auth silently.

**RULE: Before assuming the i3 config is broken, PROVE IT via md5.**

```bash
# Live vs origin — these MUST match
md5sum ~/.config/i3/config
git -C ~/code/garuda-i3-baseline show origin/main:configs/i3/config | md5sum
```

If the md5s match, the i3 config was not touched. The breakage is elsewhere — almost always a daemon/service that stopped auto-starting. Saying "I broke your config" when the md5s match is a hallucination; report the md5 match as fact and continue diagnosing.

**Diagnostic flow (run BEFORE asking the user what they see):**

```bash
# 1. Is polybar running?
pgrep -af polybar | grep -v 'hermes\|pgrep'

# 2. Is there a service for it?
systemctl --user status polybar.service --no-pager

# 3. What did launch.sh log?
ls /tmp/polybar-*.log 2>/dev/null && tail -20 /tmp/polybar-HDMI-0.log

# 4. Can polybar talk to X?
systemctl --user show-environment | grep -E '^(DISPLAY|XAUTHORITY)='

# 5. Config files present?
ls -la ~/.config/polybar/launch.sh ~/.config/polybar/config.ini
```

**The three root causes (in frequency order):**

1. **No service at all.** Polybar wasn't in the i3 `exec` block, wasn't a systemd service. It worked when the user ran `~/.config/polybar/launch.sh` once after login, then vanished on next reboot.
2. **`Type=simple` kills the cgroup.** `launch.sh` forks polybar into background with `&` then exits. systemd tracks launch.sh as the main PID, and on exit kills the entire cgroup — taking the real polybars with it. Symptom: `status: code=exited, status=0/SUCCESS` but `pgrep -af polybar` returns empty.
3. **XAUTHORITY drift.** `/tmp/xauth_<random>` changes per login. systemd --user doesn't inherit it from the i3 session. Symptom: launch.sh exits 0 but launch log shows `Can't open display :0` and `Authorization required, but no authorization protocol specified`.

**The correct recipe** (verified 2026-06-20, garuda-i3-baseline commits 64dabec + 327c3c4):

File 1 — `~/.config/systemd/user/polybar.service`:
```ini
[Unit]
Description=Polybar status bar (mazemaker profile)
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.config/polybar/launch.sh
RemainAfterExit=yes
KillMode=process
Environment=DISPLAY=:0
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
```

File 2 — `~/.config/systemd/user/import-x-env.service` (runs first):
```ini
[Unit]
Description=Import DISPLAY + XAUTHORITY into systemd --user
After=graphical-session.target
Before=polybar.service
PartOf=graphical-session.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/systemctl --user import-environment DISPLAY XAUTHORITY

[Install]
WantedBy=graphical-session.target
```

Then:
```bash
systemctl --user daemon-reload
systemctl --user enable --now import-x-env.service
systemctl --user enable --now polybar.service
```

**Critical pitfalls:**
- **DO NOT use `Type=simple`** with a forking launcher — systemd kills the cgroup when the parent exits. Use `Type=oneshot` + `RemainAfterExit=yes` + `KillMode=process`.
- **DO NOT hardcode `XAUTHORITY=%h/.Xauthority`** — that file does not exist on SDDM-managed sessions; the real path is `/tmp/xauth_<random>` and changes per login. Use `import-environment` from the live session.
- **DO NOT skip `Before=polybar.service`** in import-x-env — order matters; without it polybar may start before DISPLAY/XAUTHORITY are imported.
- **DO verify with `xdotool search --classname polybar`** after enabling, not just `pgrep polybar` — pgrep can show the cgroup but no actual X window if launch failed silently.

See `references/polybar-systemd-user-xauth.md` for the full reproduction recipe including the launch.sh shape, the verification matrix, and what `polybar|error:` log lines mean.

## Cloning the i3 Setup Between Hosts (rsync + cleanup)

The user maintains a near-identical i3 environment across multiple hosts (e.g. desk, tpad). Cloning is a one-shot rsync, but two things trip up the naive copy:

**1. Secret files must be excluded.** `~/.config/i3/` accumulates per-host secrets that must NOT be synced:
- `.keyring-env` (PAM keyring session env)
- `keyring-init-FIXED` (keyring unlock script)
- `sddm-fixed` (SDDM login token)

```bash
# Recommended rsync — preserves the dir layout, mirrors the rest exactly
rsync -avz --delete \
    --exclude='.keyring-env' \
    --exclude='keyring-init-FIXED' \
    --exclude='sddm-fixed' \
    --exclude='*.bak.*' \
    --exclude='config.bak*' \
    -e ssh ~/.config/i3/ tpad:.config/i3/
```

The `*.bak.*` and `config.bak*` excludes prevent shipping your local backup files to the new host. `--delete` mirrors the source exactly (so files deleted on the source are deleted on the target) — only do this AFTER backing up the target's config first: `ssh tpad 'cp -a ~/.config/i3/config ~/.config/i3/config.bak.pre-clone.$(date +%Y%m%d-%H%M%S)'`.

**2. The user considers these "autostart Müll" — strip them on the target after rsync.** The user has explicit preferences about cosmetic autostart (see "User Autostart Preferences" section below):
- `matrix-dashboard.sh` — interactive alacritty matrix-rain launcher
- `matrix-desktop.sh` — older matrix rain variant (root-level, not in scripts/)
- `neural-desktop-layer.sh` — 3D neural-memory graph as wallpaper
- `enhancements/neural-dashboard.conf` — the binding include for the above

To remove, on the target host:
```bash
ssh tpad 'cd ~/.config/i3; \
    rm -v scripts/matrix-dashboard.sh scripts/neural-desktop-layer.sh \
          matrix-desktop.sh enhancements/neural-dashboard.conf'

# Edit config: remove the include line, the binding, the auto-launch exec
ssh tpad 'cd ~/.config/i3; \
    sed -i "/^include \"enhancements\/neural-dashboard.conf\"$/d" config; \
    sed -i "/^bindsym \$mod+Shift+m exec --no-startup-id ~\/.config\/i3\/scripts\/matrix-dashboard.sh$/d" config; \
    sed -i "/^# Auto-launch neural desktop layer/,/^exec --no-startup-id sh -c .sleep 6 && \[ ! -f \/tmp\/neural-dashboard-desktop/d" config'

# Validate (MUST be silent = valid)
i3 -C -c ~/.config/i3/config
```

The user has a hard distinction: the **80s Retro Boot Sequence** (`boot-sequence.sh` / `boot-sequence.py`) is NOT matrix garbage — it's an aesthetic choice, keep it. The matrix/neural cluster is the disposable cosmetic stuff. Don't conflate them.

**3. Per-host configs that may need to differ after clone:**
- `XDG_MENU_PREFIX` in `.xprofile` (per-host, see Pitfalls)
- `set $ws8 "8:  neural"` → rename to neutral after stripping the neural include
- `for_window [class="Google-chrome" title="^(?!.*Neural Memory).*"]` regex → simplify once Neural Memory chrome will never exist
- `keybinds-rofi.sh` cheatsheet may have entries for bindings you just removed (e.g. "Alt+Shift+M Matrix wallpaper toggle") — strip those too

## User Autostart Preferences (per-host overrides)

When setting up or auditing the i3 autostart block, the user has explicit preferences:

**Strip these (the user considers them cosmetic clutter):**
- `matrix-dashboard.sh`, `matrix-desktop.sh` (matrix-rain launchers)
- `neural-desktop-layer.sh`, `enhancements/neural-dashboard.conf` (3D graph as wallpaper, includes the `architect-mirror` binding to ws10)
- Auto-launch exec lines for the above
- The `include "enhancements/neural-dashboard.conf"` line

**Keep these (the user actively wants):**
- `boot-sequence.sh` / `boot-sequence.py` (80s Retro Animation on ws1 at login)
- `safe-exit.sh` / `safe-reboot.sh` / `safe-poweroff.sh`
- All standard autostart (xrdb, polkit, picom, dunst, greenclip, nm-applet, blueman-applet, snixembed)
- i3-resurrect session save/restore
- The hermelin-themed status bar

When the user says "ausmisten" (clean up) about autostart, the matrix+neural cluster is the canonical target. The boot-sequence is a separate aesthetic decision; do not strip unless explicitly asked.

## Forcing Logout From a Status-Bar Click Handler

Some apps' own logout triggers are unreliable across switch directions
(e.g. optimus-manager's `auto_logout` logs out on integrated->nvidia but NOT on
nvidia->integrated). To get a uniform logout from an i3status-rust bar click,
disable the app's auto-logout and force it yourself from the click handler:

```bash
# in the block's click-handler script, after performing the action:
sleep 1
SOCK=$(ls /run/user/1000/i3/ipc-socket.* 2>/dev/null | head -1)
if [ -n "$SOCK" ]; then i3-msg -s "$SOCK" exit; else i3-msg exit; fi
```

`i3-msg exit` terminates the i3 session and returns to SDDM (logout). Use the
socket-path form because the handler runs as a subprocess of i3bar/i3status-rust
and `$I3SOCK` may not be set. Prefer `i3-msg exit` over `loginctl terminate-user`
— the latter also kills unrelated sessions (e.g. your SSH session to the host).

**IMPORTANT caveat (Optimus / GPU-switch case):** if the click handler must
make the display manager re-apply a GPU mode (optimus-manager removes/loads the
dGPU in its Xorg pre-start hook, which only runs when X actually RESTARTS),
`i3-msg exit` is NOT enough — SDDM often REUSES the existing X session on
re-login, so the hook never re-runs and the dGPU stays on the bus. In that case
force a real X restart with `systemctl restart sddm` (passwordless via a polkit
rule). Full pattern + polkit rule: see `linux-optimus-gpu-power`.

## Verification

After any change:
1. `i3 -C -c ~/.config/i3/config` → no output = valid
2. `which jgmenu` → path returned
3. `pgrep -af jgmenu` → single daemon process running
4. Reload i3 (`Mod+Shift+R`)
5. Right-click on desktop → menu appears
6. Click an item → it executes
7. Right-click again → menu reappears (proves no zombie)

For KDE-under-i3 issues specifically:
8. `grep XDG_CURRENT_DESKTOP ~/.xprofile` → must be `=KDE`
9. `dbus-update-activation-environment --systemd | head` → env propagated
10. `pgrep -af kiod6` → fresh PID (proves it restarted)
11. Open Dolphin → right-click file → "Öffnen mit → Andere…" → dropdown populated

## Related

- The hardened launcher script: `scripts/jgmenu-run.sh`
- Known-good jgmenu config: `templates/jgmenurc`
- Known-good menu items: `templates/append.csv`
- Common failure modes and recovery: `references/jgmenu-pitfalls.md`
- **Polybar / status bar won't auto-start (Type=simple cgroup kill, XAUTH drift, no service): `references/polybar-systemd-user-xauth.md`**
- **Dolphin "Öffnen mit" empty dropdown worked example: `references/dolphin-openwith-empty-xdg.md`**
- **One-shot read-only diagnostic for "Open With empty" reports: `scripts/diagnose-kde-openwith.sh`** — checks all three env layers + ksycoca6 cache health + running dolphin env. Use this FIRST on any "KDE app returns empty list" complaint before guessing.
