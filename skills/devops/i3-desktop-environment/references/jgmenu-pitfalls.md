# jgmenu Pitfalls & Breakage Modes

This is the field guide for "the menu broke again" — collected from real
sessions. When the user reports right-click / context menu issues, walk this
list top to bottom.

## Quick triage checklist

```bash
# 1. Is jgmenu actually installed?
which jgmenu

# 2. Is the binding wired in i3?
grep -E "button[23]" ~/.config/i3/config

# 3. Are there zombie instances swallowing clicks?
pgrep -af jgmenu
# Expected: 1 process. If you see 2+ → kill the extras.

# 4. Is the daemon even running?
pgrep -af "jgmenu --simple"
# If empty → no daemon, autostart isn't working.

# 5. Validate the i3 config (catches syntax errors silently breaking binds)
i3 -C -c ~/.config/i3/config
```

## Known breakage modes

### 1. Zombie jgmenu processes

**Symptom:** right-click does nothing. Sometimes menu flashes and disappears.
Sometimes menu appears, then a second copy fights for input.

**Cause:** picom reload, i3 restart, or rapid right-click spam left orphaned
jgmenu processes. They hold a grab on the X pointer.

**Fix:**
```bash
pkill -f "jgmenu --simple"
# then right-click — fresh daemon comes up
```

**Prevention:** the hardened launcher script (`scripts/jgmenu-run.sh`) pkill's
stale instances before exec'ing a new one.

### 2. Race on i3 reload

**Symptom:** after `Mod+Shift+R`, the right-click menu either doesn't appear
or appears then vanishes. Often followed by a "menu opened but won't take
input" feel.

**Cause:** `exec --no-startup-id jgmenu --simple` in the i3 config spawns a
new daemon on every reload. The old one is supposed to die from the
`exec_always` semantics, but picom re-attach can race.

**Fix:** ensure the autostart line is `exec --no-startup-id` (not
`exec_always`) so i3 handles the lifecycle. If the line is duplicated in
`enhancements.conf` and the main config, only one will run — but the other
will spawn a process that doesn't die.

**Detection:**
```bash
i3-msg -t get_version
# then check pgrep -af jgmenu — if count > 1, you have the race
```

### 3. Config file vanished or got clobbered

**Symptom:** menu opens but is white/empty/uses wrong colors. Items don't
execute.

**Cause:** the user (or a sync tool like `chezmoi`, `stow`, `restic`) wiped
or overwrote `~/.config/jgmenu/`. The daemon falls back to jgmenu's compiled
defaults.

**Fix:** restore from the templates in this skill (templates/jgmenurc,
templates/append.csv) or from the user's dotfiles repo.

**Detection:**
```bash
ls -la ~/.config/jgmenu/
# If jgmenurc is missing or 0 bytes → corruption
stat ~/.config/jgmenu/jgmenurc
```

### 4. Stale lock files after sleep/resume

**Symptom:** first right-click after wake does nothing. Second click works.

**Cause:** jgmenu's lock file in `/tmp` (default `~/.cache/jgmenu/lock` on
some distros) survives across sleep. The first click is denied as "already
running."

**Fix:**
```bash
rm -f ~/.cache/jgmenu/lock /tmp/jgmenu.lock
```

**Prevention:** add a sleep-resume hook that clears the lock. systemd path:
`/etc/systemd/system/jgmenu-resume.service` with a `Type=oneshot ExecStart=rm
-f ~/.cache/jgmenu/lock`.

### 5. picom swallowed the click

**Symptom:** jgmenu daemon is running, binding is wired, but no menu appears.
Right-click has no effect.

**Cause:** picom's `focus-follows-mouse` or a click-through rule is
intercepting the input event before jgmenu sees it.

**Fix:**
```bash
# 1. Is picom running?
pgrep -af picom
# 2. Is the click being seen at all?
xev | grep -i button
# (right-click in the xev window, look for ButtonPress event)
# 3. If xev sees it but i3/jgmenu don't → picom is eating it
```

**Prevention:** add an exception in picom.conf for jgmenu's window class:
```
rule-class-matches = "jgmenu"
focus = true
focus-exclude = false
```

### 6. i3 config edit didn't take effect

**Symptom:** binding is in the config file but right-click does nothing.

**Cause:** i3 doesn't auto-reload. User (or agent) edited the config but
didn't press `Mod+Shift+R` or run `i3-msg reload`.

**Fix:**
```bash
i3-msg reload
# or press Mod+Shift+R
```

**Validation first** (so you don't break the user's session):
```bash
i3 -C -c ~/.config/i3/config
# empty output = OK
```

## Recovery script

If everything is wedged and you just want it working again:

```bash
pkill -f jgmenu 2>/dev/null
rm -f ~/.cache/jgmenu/lock /tmp/jgmenu.lock
i3-msg reload
# wait 1s, then right-click
```

If that still doesn't work, check the actual config:
```bash
grep -E "button[23]|jgmenu" ~/.config/i3/config
# Should show at least:
#   bindsym --release button3 exec --no-startup-id ~/.config/i3/scripts/jgmenu-run.sh
#   exec --no-startup-id jgmenu --simple
```

## Related: Dolphin "Open with..." is a different problem

If the user reports the "Open with..." submenu missing inside Dolphin
specifically, do NOT chase it through jgmenu/i3. It's a kio-extras issue:

```bash
pacman -Qi kio-extras      # must be installed
ls /usr/share/kio/servicemenus/   # system service menus
ls ~/.local/share/kservices5/ServiceMenus/  # user service menus
# Then check the actual menu in Dolphin:
#   Right-click file → "Open With" submenu
#   If submenu is empty: xdg-mime default hasn't been set
#   If submenu is missing entirely: kio-extras broken
```

Nuclear option for Dolphin: `sudo pacman -S --reinstall kio-extras
dolphin-plugins` then `killall dolphin && dolphin`.
