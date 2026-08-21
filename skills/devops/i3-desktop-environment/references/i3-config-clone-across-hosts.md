# Cloning i3 Config Across Hosts — rsync + Per-Host Differences

The user has a fleet of Garuda hosts (desk, tpad, and others over time) that should behave as one i3 environment. Naive `scp -r` or `cp -a` is wrong: it ships secrets, ships stale backups, and doesn't update the target's per-host state. The clean pattern is rsync with surgical excludes, then a post-rsync cleanup pass on the target.

## The canonical rsync (tested 2026-06-18, desk → tpad)

```bash
# Pre-flight: backup the target's config so --delete can't lose anything
ssh tpad 'cp -a ~/.config/i3/config ~/.config/i3/config.bak.pre-clone.$(date +%Y%m%d-%H%M%S)'

# Mirror source to target, preserving dir layout
rsync -avz --delete \
    --exclude='.keyring-env' \
    --exclude='keyring-init-FIXED' \
    --exclude='sddm-fixed' \
    --exclude='*.bak.*' \
    --exclude='config.bak*' \
    -e ssh ~/.config/i3/ tpad:.config/i3/
```

**Why these excludes:**
- `.keyring-env`, `keyring-init-FIXED`, `sddm-fixed` — per-host auth tokens / keyring session data. Ship them and the target's PAM keyring stops unlocking correctly on first login.
- `*.bak.*` and `config.bak*` — your local backup files. Don't ship them.

**Why `--delete`:** the target should converge to the source exactly. Local-only files (e.g. tpad-specific brightness-manager.sh that desk doesn't have) are deleted. If that's wrong for your use case, drop `--delete` and the target becomes a superset.

**Why the order matters:** backup FIRST, rsync second. If rsync dies mid-flight, the backup is your rollback.

## Post-rsync cleanup (target-side)

After rsync, two things are wrong:
1. The source's `.xprofile` has the source's `XDG_MENU_PREFIX` (per-host — different Garuda installs ship different `/etc/xdg/menus/*.menu`).
2. The source's i3 config has matrix+neural scripts the user considers autostart Müll (see "User Autostart Preferences" in SKILL.md).

Fix per-host XDG_MENU_PREFIX on target:

```bash
# 1. Discover the target's actual menu prefix
ssh tpad 'ls /etc/xdg/menus/'

# 2. Patch the target's .xprofile and environment.d
#    (replace "plasma-" with whatever you discovered)
ssh tpad 'sed -i "s|XDG_MENU_PREFIX=gnome-|XDG_MENU_PREFIX=plasma-|" ~/.xprofile ~/.config/environment.d/15-kde-menu-prefix.conf'

# 3. Rebuild ksycoca6 with the right env
ssh tpad 'export XDG_MENU_PREFIX=plasma- XDG_CURRENT_DESKTOP=KDE:i3
          rm -f ~/.cache/ksycoca6_*
          kbuildsycoca6 --noincremental
          ls -la ~/.cache/ksycoca6_*'   # should be > 500KB
```

Strip the autostart Müll:

```bash
ssh tpad 'cd ~/.config/i3
    rm -v scripts/matrix-dashboard.sh scripts/neural-desktop-layer.sh \
          matrix-desktop.sh enhancements/neural-dashboard.conf

    # Remove the include + binding + auto-launch exec block from i3 config
    sed -i "/^include \"enhancements\/neural-dashboard.conf\"$/d" config
    sed -i "/^bindsym \$mod+Shift+m exec --no-startup-id ~\/.config\/i3\/scripts\/matrix-dashboard.sh$/d" config
    sed -i "/^# Auto-launch neural desktop layer/,/^exec --no-startup-id sh -c .sleep 6 && \[ ! -f \/tmp\/neural-dashboard-desktop/d" config

    # Rename ws8 label from "neural" to neutral
    sed -i "s|set \$ws8  \"8:  neural\"|set \$ws8  \"8:  \"|" config

    # Simplify the chrome-to-ws3 rule (the negative-lookahead for Neural Memory
    # title was only needed because Neural Memory chrome used to exist)
    sed -i "s|for_window \[class=\"Google-chrome\" title=\"\^(?!.\*Neural Memory).\*\$\"\] move to workspace \$ws3|for_window [class=\"Google-chrome\"] move to workspace \$ws3|" enhancements.conf

    # Strip the cheatsheet line for the deleted binding
    sed -i "/^Alt+Shift+M        Matrix wallpaper toggle$/d" scripts/keybinds-rofi.sh

    # Validate (MUST be silent = valid)
    i3 -C -c ~/.config/i3/config'
```

**Sed `$variable` gotcha (real cost, hit this 2026-06-18):** the i3 config uses `$ws3`, `$mod`, `$term` etc. as variables. When you do `ssh tpad "sed -i 's/...$ws3.../.../' config"`, the OUTER shell (your agent's shell) expands `$ws3` BEFORE the command reaches the target. If the outer shell has no `$ws3`, the sed replacement string gets a literal empty space. Result: the chrome-to-ws3 line becomes `for_window [class="Google-chrome"] move to workspace ` (no workspace, broken).

Fix: single-quote the sed expression (no expansion), or escape with `\$ws3`. Always validate with `i3 -C -c ~/.config/i3/config` after every sed edit.

## Companion config files to also sync (optional but typical)

If the user wants full visual consistency across hosts:

```bash
# picom config (shadows, blur)
rsync -avz -e ssh ~/.config/picom/picom.conf tpad:.config/picom/

# rofi theme (hermelin)
rsync -avz -e ssh ~/.config/rofi/ tpad:.config/rofi/

# dunst notifications
rsync -avz -e ssh ~/.config/dunst/ tpad:.config/dunst/

# Kvantum theme + gtk-3.0 colors
rsync -avz -e ssh ~/.config/Kvantum/ tpad:.config/Kvantum/
rsync -avz -e ssh ~/.config/gtk-3.0/ tpad:.config/gtk-3.0/

# .Xresources (xrdb loads this at i3 startup)
rsync -avz -e ssh ~/.Xresources tpad:.Xresources
```

The .xprofile + environment.d files are NOT typically rsynced because they have per-host values (XDG_MENU_PREFIX). Patch them instead.

## What never to ship

Always per-host, never sync:
- `~/.config/i3/.keyring-env`
- `~/.config/i3/keyring-init-FIXED`
- `~/.config/i3/sddm-fixed`
- `~/.config/BraveSoftware`, `~/.config/google-chrome`, `~/.config/Code/User/globalStorage` — browser/editor profiles
- `~/.ssh/id_*`, `~/.ssh/known_hosts`
- Anything matching `*.bak.*` and `config.bak*`

## Verification after a full clone

```bash
ssh tpad '
    echo "=== i3 config valid? ==="
    i3 -C -c ~/.config/i3/config            # silent = OK
    echo
    echo "=== env vars in shell? ==="
    grep -E "XDG_CURRENT_DESKTOP|XDG_MENU_PREFIX" ~/.xprofile
    echo
    echo "=== ksycoca6 cache size? ==="
    CACHE=$(ls ~/.cache/ksycoca6_* | head -1)
    echo "$(stat -c%s "$CACHE") bytes"      # > 500KB = healthy
    echo
    echo "=== matrix/neural residue? ==="
    find ~/.config/i3/ -name "*matrix*" -o -name "*neural*"
    grep -riE "matrix|neural" ~/.config/i3/config ~/.config/i3/enhancements.conf
    # (empty = clean)
'
```

## Common errors and recovery

| Error | Cause | Fix |
|---|---|---|
| `rsync: connection unexpectedly closed` | tpad rebooted or ssh key not loaded | `ssh-add ~/.ssh/id_ed25519` then retry |
| `Permission denied` on the target dir | target's .config is owned by another user (e.g. an old uid from a re-install) | `ssh tpad 'sudo chown -R alca:alca ~/.config/i3'` (requires sudo on target) |
| `i3 -C -c ~/.config/i3/config` reports errors | sed replaced a `$VAR` literally | `cp` the .bak file back, redo with single-quoted sed, validate |
| After reload, ws8 still shows "neural" label | missed the `set $ws8` line | re-run that sed, then `i3-msg reload` |
| Open-With dialog still empty on target | the `i3 -C` was silent but ksycoca6 wasn't rebuilt | re-run the kbuildsycoca6 step with corrected env, then close+reopen any running KDE app |
