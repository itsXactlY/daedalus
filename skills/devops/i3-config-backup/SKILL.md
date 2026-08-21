---
name: i3-config-backup
version: "0.0.2"
description: Maintain and sync the i3 desktop config backup repo (itsXactlY/i3-config-backup.git)
---

# i3 Config Backup

## Repo Location

- Remote: `git@github.com:itsXactlY/i3-config-backup.git`
- Local clone: `~/.config/i3-config-backup/`
- Source configs live in: `~/.config/i3/`

**CRITICAL**: `~/.config/i3/` is NOT a git repo. The backup lives in a separate directory.
Never run `git init` or `git add` inside `~/.config/i3/`.

## Repo Structure

```
i3-config-backup/
├── config/i3/             # main i3 config + wallpapers + keybindings
├── config/i3/scripts/     # all .sh and .py helper scripts
├── config/i3/enhancements/
├── config/i3status-rust/  # bar configuration + themes + scripts
├── config/picom/
├── config/rofi/
├── config/alacritty/
├── config/i3status/
├── config/conky/
├── home/                  # Xresources, xprofile, cheatsheet
├── local/bin/             # chrome-keyring
└── local/share/applications/
```

## What to Backup

All of `~/.config/i3/` EXCEPT:
- `.keyring-env` — contains secrets, must be in .gitignore

Plus: `~/.config/i3status-rust/`, `picom/`, `rofi/`, `alacritty/`, `i3status/`, `conky/`
Dotfiles: `~/.Xresources`, `~/.xprofile`, `~/.cheatsheet`
Local: `~/.local/bin/chrome-keyring`, `~/.local/share/applications/google-chrome.desktop`

## .gitignore

```
# Secrets / tokens
*.key
*.pem
*.token
.env
.keyring-env
# Logs
*.log
# Temp files
*.swp
*.tmp
*~
```

## Manual Sync (One-Time)

If the repo has diverged significantly or is missing its .git directory, use the tar+scp method (see Remote Deploy below).

## Cronjob

The backup runs hourly via cronjob managed by Hermes cron tool.
Script: `~/.hermes/scripts/i3-config-backup-sync.sh`

The sync script:
1. Ensures clone exists at `~/.config/i3-config-backup/`
2. Cleans the repo config directories
3. Copies fresh files from `~/.config/i3/` and other locations
4. `git add -A`, commits with timestamp, pushes

## Remote Deploy (Deploy to Another Machine)

When syncing the i3 config to a different machine (e.g. a laptop via mosh/ssh):

### Problems to Expect
1. `mosh` does NOT work with non-interactive script redirection — `tcgetattr: Unpassender IOCTL` error. Use plain `ssh` instead.
2. `ssh -t` with sudo fails without a real TTY (no password prompt). For sudo, user must run `mosh tpad` interactively.
3. GitHub SSH clone fails on remote machine (private key not available).
4. HTTPS clone fails on remote (no credential helper, private repo or requires auth).
5. Low battery on laptop — keep operations fast and minimal.

### Working Approach: Individual scp (RELIABLE — preferred method)

tar extraction fails on remote /tmp with permission errors (`utime: Die Operation ist nicht erlaubt`). Restore scripts fail when the target directory doesn't exist. rsync needs ssh keys. **Individual `scp` per file/dir pattern is the ONLY reliably working method.**

```bash
# 1. Each file directly
scp local-config tpad:~/.config/i3/config
scp local-enhancements.conf tpad:~/.config/i3/enhancements.conf
scp -r local-scripts/* tpad:~/.config/i3/scripts/

# 2. Each config dir
scp -r local-i3status-rust/* tpad:~/.config/i3status-rust/
scp -r local-picom/* tpad:~/.config/picom/
scp -r local-rofi/* tpad:~/.config/rofi/
scp -r local-alacritty/* tpad:~/.config/alacritty/
scp -r local-i3status/* tpad:~/.config/i3status/
scp -r local-conky/* tpad:~/.config/conky/

# 3. Dotfiles and local
scp local-Xresources tpad:~/.Xresources
scp local-xprofile tpad:~/.xprofile

# 4. Restart
ssh tpad 'i3-msg restart'
```

For garuda-i3settings package installation, the user must run the pacman command interactively via mosh:
```bash
mosh tpad
sudo pacman -S garuda-i3settings
```

### SCP Nesting Trap
scp of a directory called `i3` into `~/.config/i3/` creates `~/.config/i3/i3/` (nested). Fix by using wildcard (`config/i3/*`) or removing the nested dir after: `rm -rf ~/.config/i3/i3`.

### Deploying garuda-i3-settings (Clean Garuda-i3 Desktop)

When the target machine needs a fresh garuda-i3 install (NOT just config files):

### WARNING: garuda-dr460nized removal BREAKS the desktop — full recovery sequence

Removing `garuda-dr460nized` (KDE Plasma) to install `garuda-i3settings` causes cascading failures:

1. **Essential i3 packages removed**: i3status, dmenu, numlockx, xfce4-power-manager, network-manager-applet, brightnessctl, playerctl, i3exit — all get yanked as runtime dependencies. i3 WILL NOT START without them.
2. **SDDM Autologin stuck on "plasma"**: `/etc/sddm.conf` still says `Session=plasma` but plasma is gone → black screen or dead greeter on login.
3. **KDE Kvantum theme dependencies partially removed**: Setting `QT_STYLE_OVERRIDE=kvantum` in `.xprofile` will crash apps or cause visual corruption. Remove kvantum references from `.xprofile`.

### Full Recovery / Install Sequence (MUST be followed in order)

1. User runs interactively via mosh (requires sudo password):
   ```bash
   mosh tpad
   sudo pacman -S garuda-i3-settings
   ```

2. **Immediately reinstall all removed packages** (i3 WILL NOT START without these):
   ```bash
   sudo pacman -S --noconfirm i3status dmenu numlockx \
       xfce4-power-manager network-manager-applet \
       brightnessctl playerctl feh alacritty \
       picom rofi dunst i3lock
   ```

3. **Fix .xprofile** (remove Kvantum, use plain GTK theme):
   ```bash
   cat > ~/.xprofile << 'EOF'
   export XDG_CURRENT_DESKTOP=i3
   export XDG_SESSION_TYPE=x11
   export GTK_THEME=Adwaita-dark
   export GTK_ICON_THEME=Papirus-Dark
   EOF
   ```

4. **Fix SDDM autologin** (or you get black screen):
   ```bash
   sudo sed -i "s/Session=plasma/Session=i3/" /etc/sddm.conf
   sudo systemctl restart sddm
   ```

5. **Recreate i3exit script** (Garuda-specific, not in any package):
   ```bash
   cat > /usr/local/bin/i3exit << 'I3E'
   #!/bin/bash
   case "$1" in
       lock) i3lock -i /usr/share/wallpapers/garuda-wallpapers/Dr460nized\ Honeycomb.png ;;
       logout) i3-msg exit ;;
       suspend) systemctl suspend ;;
       hibernate) systemctl hibernate ;;
       reboot) systemctl reboot ;;
       shutdown) systemctl poweroff ;;
       switch_user) dm-tool switch-to-greeter ;;
   esac
   I3E
   sudo chmod +x /usr/local/bin/i3exit
   ```

6. Deploy your full Hermes i3 config (see Individual scp method above).

7. **Restart i3**: `Alt+Shift+r` (or `i3-msg restart` if i3 is running).
   If Alt+Shift+e doesn't work for exit: use `Alt+0` → system menu → `e` for exit.

8. **If still broken/dead**: The user wants their full desktop config, not Garuda defaults. Deploy the full Hermes config via individual scp (not tar/rsync scripts which fail on remote).

### Full Restore Script Pattern

For rapid deployment to a machine that has garuda-i3-settings installed but broken config, use a combined restore script:

```bash
#!/bin/bash
set -euo pipefail
# Run as sudo on target machine
# Expects /tmp/i3-config-backup-sync/ with repo contents

# 1. Missing packages
pacman -S --noconfirm i3status dmenu numlockx xfce4-power-manager network-manager-applet brightnessctl playerctl feh alacritty picom rofi dunst i3lock

# 2. Restore configs
cd /tmp/i3-config-backup-sync
rsync -a config/i3/ "$HOME/.config/i3/"
rsync -a config/i3status-rust/ "$HOME/.config/i3status-rust/"
rsync -a config/picom/ "$HOME/.config/picom/"
rsync -a config/rofi/ "$HOME/.config/rofi/"
rsync -a config/alacritty/ "$HOME/.config/alacritty/"
rsync -a config/i3status/ "$HOME/.config/i3status/"
rsync -a config/conky/ "$HOME/.config/conky/"
cp home/Xresources "$HOME/.Xresources" 2>/dev/null || true
cp home/xprofile "$HOME/.xprofile" 2>/dev/null || true

# 3. i3exit + SDDM fix
# (see above)

# 4. Restart
sudo systemctl restart sddm
```

### Garuda Default as Skeleton

3. Build your custom config ON TOP of the Garuda skeleton:
   - Change `set $mod` to your preference (e.g., `Mod1` for Alt key)
   - Replace Garuda default apps (kitty, firedragon, thunar, geary, geany) with what's actually installed
   - Common Garuda app gaps: kitty → alacritty, thunar → dolphin, geany → nano
   - Include `enhancements.conf` at the bottom for scratchpads, etc.

4. Run `i3 -C` to validate the config before deploying.

### Keybinding Duplicate Pitfall with `$mod`

When `$mod = Mod1`, any binding like `bindsym $mod+Mod1+c` resolves to `Mod1+c` — which conflicts with `bindsym $mod+c`. This causes `i3 -C` duplicate keybinding errors.

**Rule**: Never use `$mod+Mod1+x` when `$mod = Mod1`. Use `$mod+Control+x` or `$mod+Shift+x` instead.

Always validate with `i3 -C` after generating the config:
```bash
ssh tpad 'i3 -C 2>&1 | grep "ERROR" || echo "OK"'
```

### Garuda-i3 Post-Install
- Garuda-i3 does NOT install cronie by default — user must run `sudo pacman -S cronie && sudo systemctl enable --now cronie` for hourly backup cronjobs
- garuda-i3-settings default config uses `$super = Mod4` (Windows key) and `$alt = Mod1` — if you want Alt as primary mod, change `$mod` to `Mod1` and adjust all keybindings
- **Alt+Shift+e** does NOT exit i3 (it's a Garuda default that gets overridden). Use **Alt+0** → system menu → `e` for exit/swap_user, or `i3-msg exit` from terminal.

### Laptop i3status-rust — Battery, Backlight, Optimus Switcher

Essential blocks for laptop config (add to `config.toml`):

```toml
# ── Battery ──
[[block]]
block = "battery"
format = " $icon $percentage {$time |}"
interval = 10
[[block.click]]
button = "left"
cmd = "xfce4-power-manager-settings"

# ── Backlight ──
[[block]]
block = "backlight"
device = "intel_backlight"    # check /sys/class/backlight/ for actual device
format = " $icon $brightness "
step_width = 10

# ── Optimus GPU Switcher ──
[[block]]
block = "custom"
command = "bash ~/.config/i3/scripts/optimus-status.sh"
interval = 6
json = false
[[block.click]]
button = "left"
cmd = "bash ~/.config/i3/scripts/optimus-switcher.sh"
```

Optimus status script (`~/.config/i3/scripts/optimus-status.sh`):
```bash
#!/bin/bash
MODE=$(optimus-manager --print-mode 2>/dev/null | tr '[:upper:]' '[:lower:]' | head -1)
case "$MODE" in
    nvidia*)     echo "🎮 NVIDIA" ;;
    hybrid*)     echo "🔀 HYBRID" ;;
    integrated*) echo "🖥 IGPU" ;;
    *)           echo "🖥 IGPU (no manager)" ;;
esac
```

Optimus switcher script (`~/.config/i3/scripts/optimus-switcher.sh`):
```bash
#!/bin/bash
CHOICE=$(echo -e "🖥 Integrated\n🔀 Hybrid\n🎮 NVIDIA" | rofi -dmenu -i -p "GPU Mode:" -theme ~/.config/rofi/config.rasi)
case "$CHOICE" in
    *"Integrated"*) MODE="integrated" ;;
    *"Hybrid"*)     MODE="hybrid" ;;
    *"NVIDIA"*)     MODE="nvidia" ;;
    *) exit 0 ;;
esac
CURRENT=$(optimus-manager --print-mode 2>/dev/null | tr '[:upper:]' '[:lower:]')
[ "$MODE" = "$CURRENT" ] && notify-send "Optimus Manager" "Already in $MODE" && exit 0
CONFIRM=$(echo -e "Yes\nNo" | rofi -dmenu -i -p "Switch to $MODE? (reboot!):" -theme ~/.config/rofi/config.rasi)
[ "$CONFIRM" != "Yes" ] && exit 0
pkexec optimus-manager --switch "$MODE" 2>&1 && \
    notify-send "Optimus Manager" "GPU set to $MODE. Please reboot." -u critical || \
    notify-send "Optimus Manager" "Failed — run: sudo optimus-manager --switch $MODE" -u critical
```

### i3status-rust `icons_format` Trap

i3status-rust 0.36.1 on some setups rejects `icons_format = " {icon} "` at parse time with: `no such option 'icons_format'`. If the bar shows errors or empty blocks, remove this line from config.toml. The icons still render via the `awesome6` icon set.

### Config Rollback from Git History

If a wrong config version was pushed to the backup repo, restore from a known-good commit:
```bash
cd /tmp/i3-config-backup-fresh
git log --oneline                    # find the good commit
git checkout <commit> -- config/i3/config config/i3/enhancements.conf
scp config/i3/config tpad:~/.config/i3/config
```

### GPU Status Script — Hybrid/Optimus Fallback

When the NVIDIA driver is not loaded (hybrid mode, Intel-only, or driver not loaded), `nvidia-smi` outputs an error string instead of data. This error gets rendered directly in the i3status-rust bar without validation.

**Fix**: Validate the output before parsing:
```bash
RESULT=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>&1)
# Check if result contains valid data (numbers + MiB), not an error string
if echo "$RESULT" | grep -qE '[0-9]+ %.*MiB'; then
    echo "$RESULT" | awk -F', ' '{ gsub(/ %/, "", $1); gsub(/ MiB/, "", $2); gsub(/ MiB/, "", $3); gsub(/ C/, "", $4); printf " GPU %s%% | %s/%sMiB | %s°C", $1, $2, $3, $4 }'
else
    echo " GPU off"
fi
```

### Git Rollback — Restore Config from Old Commit

If you accidentally push a wrong version (e.g., a "Garuda basis" config instead of the full Hermelin config), restore from a known-good commit:
```bash
cd /tmp/i3-config-backup-fresh
git checkout 006225b -- config/i3/config config/i3/enhancements.conf
# Then scp to target machine
```

## Pitfalls

- DO NOT initialize git in `~/.config/i3/`
- DO NOT use `git add .` from inside `~/.config/i3/`
- The `backup.sh` script in the repo expects to be run from inside the repo directory (REPO var = script's dirname)
- `.keyring-env` must never be committed — verify .gitignore includes it
- Large binary files (wallpapers ~3MB) are tracked — this is intentional
- If push fails, the commit stays local and will be pushed on next run
- When restoring to another machine, garuda-i3settings may not be installed — user needs to install it manually via mosh
- Mosh doesn't work for non-interactive script execution — use ssh for that, mosh only for interactive sudo work
