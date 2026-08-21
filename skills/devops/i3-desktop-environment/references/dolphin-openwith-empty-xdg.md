# Dolphin "Öffnen mit → Andere…" — Empty Dropdown under i3 Session

Real session transcripts (2026-06-18, two rounds) showing the full diagnosis path. The user's first message was "fix my i3 context menu on right click, open with... etc. is still complete broken. it was fixed, and then, somehow, it all gets magically broken again!" The agent built a jgmenu install. The user then sent a screenshot of Dolphin's internal "Programm auswählen" dialog with an empty dropdown, and a strong German profanity indicating "THIS is what I mean, you idiot." The user then escalated: "war schon mal flawless gefixed von opus" — meaning a previous Opus session had already done a partial fix that silently re-broke.

## Lesson at the top

**When the user reports a "right-click context menu" problem under i3 + KDE, ALWAYS ask which menu before touching anything.** The ambiguity between i3-root-window menu (jgmenu), Dolphin/Thunar Open With dialog, and app-internal menus causes exactly this kind of wasted turn. Screenshot first, fix second.

**The fix has to cover THREE env-propagation layers.** A previous fix that only touched one of them will silently re-break. See "The Three-Layer Env Config Architecture" in the main SKILL.md.

## What the broken state looked like

Screenshot: `clip_20260618_011300_1.png`
- Title: `Programm auswählen — Dolphin`
- Input field text: "Dolphin"
- Dropdown / list of applications: EMPTY (zero entries)
- Checkbox: `Programm allen Daten dieses Typs fest zuordnen` (KDE standard label)
- Buttons: `Abbrechen` and `OK` both greyed out / inactive

## Diagnostic steps that worked

```bash
# 1. Confirm kio-extras and dolphin are installed
pacman -Qi kio-extras dolphin
# kio-extras 26.04.2-1, dolphin 26.04.2-1 — both present

# 2. Confirm .desktop files exist (should be hundreds)
ls /usr/share/applications/*.desktop | wc -l    # got 174
ls ~/.local/share/applications/*.desktop | wc -l  # got 18-22

# 3. Verify the .desktop files have valid Exec= lines
for f in ~/.local/share/applications/*.desktop; do
  exec=$(grep "^Exec=" "$f" | head -1 | cut -d= -f2 | awk '{print $1}')
  command -v "$exec" >/dev/null 2>&1 && echo "OK $exec" || echo "MISS $exec in $(basename $f)"
done
# All valid except one stale claude-code-url-handler.desktop (irrelevant)

# 4. Check the local mimeinfo.cache timestamp
ls -la ~/.local/share/applications/mimeinfo.cache
# Showed: -rw-r--r-- 1 alca alca 959 24. Mär 02:15  STALE 3 months

# 5. THE SMOKING GUN (round 1): check the session env vars
env | grep -E "XDG_CURRENT_DESKTOP|XDG_SESSION_DESKTOP|DESKTOP_SESSION"
# Showed:
# XDG_CURRENT_DESKTOP=i3       WRONG. Should be KDE.
# XDG_SESSION_DESKTOP=i3       WRONG.
# DESKTOP_SESSION=i3           WRONG.
# No XDG_MENU_PREFIX at all.

# 6. Trace to source
cat ~/.xprofile | head -10
# Confirmed: user had set XDG_CURRENT_DESKTOP=i3 in their own .xprofile
# months ago, presumably to suppress GNOME-app quirks.
# (No XDG_MENU_PREFIX set anywhere.)

# 7. THE SECOND SMOKING GUN (round 2): check ksycoca6 cache size
ls -la ~/.cache/ksycoca6_*
# Showed: 232715 bytes — suspiciously small
# Healthy caches are 500KB–2MB
# After kbuildsycoca6 with correct env: 569875 bytes (2.4x) — still
# smaller than a fully-loaded KDE cache, but populated with apps

# 8. Trace the second env var to its source
ls -la /etc/xdg/menus/
# Only one file: gnome-applications.menu
# No plasma-applications.menu, no applications.menu
# So XDG_MENU_PREFIX must be "gnome-" for kbuildsycoca6 to find it
```

## Why the env vars kill the dropdown

KDE's `kio-appinfo` KIO service (which powers Dolphin's "Open with Other" dialog) reads `XDG_CURRENT_DESKTOP` and filters .desktop file discovery against it. When the value is "i3" (not "KDE" or "Plasma"), the service returns an empty application list. The dialog opens, but its model is empty, so the dropdown is blank and OK stays disabled (no selection = nothing to commit).

Separately, `kbuildsycoca6` reads `XDG_MENU_PREFIX` to decide which `<prefix>applications.menu` file in `/etc/xdg/menus/` to use as the registry source. If the var is unset, it defaults to looking for `applications.menu` (no prefix), which does not exist on Garuda. The cache builds, but contains zero .desktop entries, because no menu was found to source them from. Then KOpenWithDialog queries the cache and finds nothing.

The two failures compound: even if you fix `XDG_CURRENT_DESKTOP` but not `XDG_MENU_PREFIX`, the cache is empty so the dropdown is still empty. The fix needs BOTH vars.

This affects more than just "Open with" — it also degrades:
- Dolphin's right-click "Öffnen mit" submenu
- KDE's file-type-to-application associations
- Various KIO `kioclient` calls
- Plasma taskbar / system tray app discovery
- KCM `kcm_filetypes` (File Associations settings) — same empty registry

## The actual fix (no sudo required)

```bash
# LAYER 1: ~/.config/environment.d/ — for systemd user services
cat > ~/.config/environment.d/10-i3-kde.conf <<'EOF'
XDG_CURRENT_DESKTOP=KDE:i3
EOF
cat > ~/.config/environment.d/15-kde-menu-prefix.conf <<'EOF'
XDG_MENU_PREFIX=gnome-
EOF

# LAYER 2: ~/.xprofile — for the login session and all bash-spawned processes
# (Opus's prior fix only did layer 1, which is why the bug came back)
# In .xprofile, change:
#   export XDG_CURRENT_DESKTOP=i3
# To:
#   export XDG_CURRENT_DESKTOP=KDE:i3
#   export XDG_MENU_PREFIX=gnome-

# LAYER 3: current session (without logout)
export XDG_CURRENT_DESKTOP=KDE:i3
export XDG_MENU_PREFIX=gnome-
systemctl --user set-environment \
    XDG_CURRENT_DESKTOP=KDE:i3 \
    XDG_MENU_PREFIX=gnome-
dbus-update-activation-environment --systemd \
    XDG_CURRENT_DESKTOP=KDE:i3 \
    XDG_MENU_PREFIX=gnome-

# Launch a fresh dolphin with correct env (the running one keeps old env)
XDG_CURRENT_DESKTOP=KDE:i3 XDG_MENU_PREFIX=gnome- dolphin &

# Refresh caches
update-desktop-database ~/.local/share/applications/
kbuildsycoca6 --noincremental
# Cache should now be > 500KB
```

## What NOT to do (the dead ends)

- BAD: `sudo pacman -S jgmenu` — completely unrelated, the user wanted Dolphin's internal dialog fixed
- BAD: `sudo pacman -S --reinstall kio-extras dolphin-plugins` — would not have helped, the env was the actual problem
- BAD: Editing `~/.config/mimeapps.list` to add fake associations — would just paper over the symptom; the registry itself is empty
- BAD: `qt5ct` / `qt6ct` settings — env is at the session manager level, not Qt
- BAD: Running `kded6` or `kiod6` as bare commands — on this Garuda install the binaries are at `/usr/lib/kf6/kded6` and `/usr/lib/kf6/kiod6` but they're LIBRARIES, not standalone executables. Bare invocation gives "command not found" or exits silently. They start via the Plasma session / systemd user units, not from a shell.
- BAD: `pkill kiod6 kioexecd6` followed by `kiod6 &` — leaves the system without KIO service; the user-spawned `kiod6` is a different process that doesn't integrate with the system. To "restart" kiod6, log out and back in.
- BAD: A fix that only writes to environment.d and skips .xprofile — appears to work for 1–2 weeks, then breaks when kbuildsycoca6 fires from a fresh shell that doesn't have the var. This is the exact cycle Opus's previous fix went through.
- BAD: `strings ~/.cache/ksycoca6_* | grep .desktop` to verify the cache — the cache is binary Qt format; strings returns zero hits even when the cache is healthy. Use the file size (500KB+ = healthy) as the only signal.
- BAD: Searching for `appinfo.so` in `/usr/lib/qt6/plugins/kf6/kio/` — that was the KF5 name. In Plasma 6 / KF6, the Open-With functionality is part of `libKF6WidgetsAddons.so` (`KOpenWithDialog`) backed by `KApplicationTrader` querying the KService registry. There's no separate "appinfo" plugin to look for; the env var controls whether the registry is populated.

## Why the user kept seeing it "magically re-break"

Two distinct cycles, both deterministic:

**Cycle A (XDG_CURRENT_DESKTOP) — the obvious one:**
- kded6 / kiod6 gets restarted (package upgrade, OOM, manual restart)
- kbuildsycoca6 rebuilds the cache
- kded picks up the new cache
- KIO `appinfo` re-queries KDE's app registry
- Filter `XDG_CURRENT_DESKTOP != "KDE"` returns []
- Dropdown immediately empty

**Cycle B (XDG_MENU_PREFIX) — the sneakier one (this is the new lesson from 2026-06-18):**
- Something triggers kbuildsycoca6 — could be kded, could be a package install, could be `update-desktop-database` from a hook
- The triggering process doesn't have `XDG_MENU_PREFIX=gnome-` in its env (e.g. a freshly-opened terminal that bypassed .xprofile)
- kbuildsycoca6 looks for `/etc/xdg/menus/applications.menu` (the default if prefix is unset)
- That file doesn't exist on Garuda
- Cache builds anyway (because kbuildsycoca6 doesn't fail loudly), but contains zero .desktop entries
- File size is 200–300KB instead of 500KB–2MB
- KIO appinfo queries the empty cache and returns []
- Dropdown empty

Cycle B can fire WITHOUT any daemon restart, so the user sees "I didn't change anything, why is it broken again?" That's the "magical" part.

**The architectural fix:** write to BOTH layer 1 (environment.d) AND layer 2 (.xprofile), and make sure .xprofile is the source of truth for shells. A previous Opus fix that only did layer 1 is exactly the situation where Cycle B eventually fires.

## Verification after fix

```bash
# Layer 1: environment.d files exist and have correct content
cat ~/.config/environment.d/10-i3-kde.conf
cat ~/.config/environment.d/15-kde-menu-prefix.conf

# Layer 2: .xprofile has both vars
grep -E "XDG_CURRENT_DESKTOP|XDG_MENU_PREFIX" ~/.xprofile

# Layer 3: current shell has both vars
echo "XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
echo "XDG_MENU_PREFIX=$XDG_MENU_PREFIX"

# Cache health smoke test
CACHE=$(ls ~/.cache/ksycoca6_* | head -1)
echo "Cache size: $(stat -c%s "$CACHE") bytes"
# Healthy: 500000–2000000. Broken: < 400000.

# Running dolphin has the right env
DPID=$(pgrep -n dolphin | head -1)
cat /proc/$DPID/environ | tr '\0' '\n' | grep -E "XDG_CURRENT_DESKTOP|XDG_MENU_PREFIX"

# Open Dolphin, right-click any file, "Öffnen mit → Andere…"
# Dropdown should now be populated; OK button activates on selection
```

## Related upstream context

- KDE bug tracker has multiple reports of empty app lists under non-KDE XDG_CURRENT_DESKTOP — all closed "not a bug, fix your env"
- Garuda's default i3 session on a fresh install does NOT set XDG_CURRENT_DESKTOP=i3; the user (or a previous agent) added this line themselves to `.xprofile`. If unsure, `cat ~/.xprofile` before assuming it's the distro default.
- KDE Plasma 6 / KF6 changed the kio-extras package layout; the openwith kio plugin is no longer a separate "openwith.so" — it's part of kio-appinfo and is enabled by the env var being correct.
- Garuda's `/etc/xdg/menus/` ships DIFFERENT files per Garuda install — desk has `gnome-applications.menu` (so `XDG_MENU_PREFIX=gnome-`), tpad has `plasma-applications.menu` (so `XDG_MENU_PREFIX=plasma-`). It's **per-host, not per-distro**. Other Garuda installs may ship `kde-applications.menu` or both. The 15-kde-menu-prefix.conf pattern with the correct prefix is mandatory — verify on yours: `ls /etc/xdg/menus/`. The wrong prefix silently builds an empty ksycoca6 cache.
