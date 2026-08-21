---
name: chrome-profile-protection
title: Chrome Profile Protection — Multi-DE Secret Service Setup
category: software-development
description: Fix Chrome profile destruction when switching between KDE Plasma and i3 (or other WMs) on Linux. Root cause is missing secret service daemon + PAM integration. Covers PAM setup, portal config, keyring init, Chrome flags, and backup system.
---

# Chrome Profile Protection on Dual Desktop Environments (KDE + i3)

## Problem
Chrome loses its entire profile (bookmarks, passwords, sessions) when switching between KDE Plasma and i3 (or other WM sessions). Chrome's `Local State` has `os_crypt.portal` with no `encrypted_key` — it relies entirely on `xdg-desktop-portal` for secret storage.

### Root Causes Found
1. **`keyring-init.sh` kills gnome-keyring-daemon** but nothing replaces it in i3 → Chrome has NO secret service → can't decrypt → profile nukes itself
2. **PAM config has `pam_gnome_keyring.so` commented out** — keyring never auto-unlocks at login
3. **Portal backend mismatch**: KDE uses `xdg-desktop-portal-kde` (kwallet), i3 needs `xdg-desktop-portal-gtk` (gnome-keyring)
4. **No `encrypted_key` in Local State** — Chrome 100% depends on portal working

## Diagnosis Steps
```bash
# 1. Check Chrome's encryption method
python3 -c "import json; s=json.load(open('/home/user/.config/google-chrome/Local State')); print(json.dumps(s.get('os_crypt',{}), indent=2))"
# If "portal" and no "encrypted_key" → portal-dependent

# 2. Check PAM keyring integration
grep keyring /etc/pam.d/sddm
# Lines with #- are commented out = broken

# 3. Check running secret service
busctl --user list | grep -iE "secret|keyring|kwallet"
# If nothing → no secret service = Chrome will break

# 4. Check if keyring-init.sh is killing the daemon
grep -n "pkill.*keyring" ~/.config/i3/keyring-init.sh
```

## Fix — Step by Step

### 1. PAM Auto-Unlock (requires sudo)
Uncomment all keyring lines in `/etc/pam.d/sddm`. **Note: Lines use `-#` prefix, NOT `-##`:**
```bash
# Check current state first
grep -E 'keyring|kwallet' /etc/pam.d/sddm

# If lines start with -# (commented out), fix them:
sudo sed -i 's/^-#auth/#auth/' /etc/pam.d/sddm
sudo sed -i 's/^-#password/#password/' /etc/pam.d/sddm  
sudo sed -i 's/^-#session/#session/' /etc/pam.d/sddm

# Alternative: Use a pre-made file
# sudo cp /home/$USER/.config/i3/sddm-fixed /etc/pam.d/sddm
```
Both `pam_kwallet5.so` AND `pam_gnome_keyring.so` should be active — KDE uses kwallet, i3 uses gnome-keyring.
Both `pam_kwallet5.so` AND `pam_gnome_keyring.so` should be active — KDE uses kwallet, i3 uses gnome-keyring.

### 2. Fix keyring-init.sh (DO NOT kill gnome-keyring!)
Replace any `pkill gnome-keyring` with proper init:
```bash
# ~/.config/i3/keyring-init.sh
# Start gnome-keyring-daemon if not running
if ! pgrep -x gnome-keyring-d > /dev/null; then
    eval "$(echo '' | gnome-keyring-daemon --unlock --components=secrets)"
fi
eval "$(gnome-keyring-daemon --start --components=secrets)" 2>/dev/null || true
export GNOME_KEYRING_CONTROL SSH_AUTH_SOCK
```

### 3. Portal Config for i3
```bash
mkdir -p ~/.config/xdg-desktop-portal
cat > ~/.config/xdg-desktop-portal/portals.conf << 'EOF'
[preferred]
default=gtk
org.freedesktop.impl.portal.Secret=gnome-keyring
EOF
```

### 4. Portal Autostart in i3
```bash
# ~/.config/i3/scripts/portal-setup.sh
pkill -f xdg-desktop-portal 2>/dev/null
sleep 0.5
/usr/lib/xdg-desktop-portal-gtk &
sleep 1
/usr/lib/xdg-desktop-portal &
```

### 5. Chrome Flags (prevent Vulkan/Wayland issues in X11)
```bash
# ~/.config/chrome-flags.conf
--password-store=gnome
--disable-features=Vulkan
--disk-cache-size=524288000
```

### 6. xprofile Environment for i3
Key exports in `~/.xprofile`:
```bash
export XDG_CURRENT_DESKTOP=i3
export XDG_SESSION_TYPE=x11
export GTK_USE_PORTAL=1
export QT_QPA_PLATFORMTHEME=kvantum
export KDE_SESSION_VERSION=6
export XDG_CONFIG_DIRS="$HOME/.config/kdedefaults:/etc/xdg"
```

### 7. Chrome Profile Backup (Safety Net)
Cron job every 30 min — only backs up when Chrome is NOT running:
```bash
# ~/bin/chrome-backup.sh — MUST use rsync (tar breaks on psd FUSE overlay)
# Keeps last 5 backups in ~/.local/backups/chrome/
# Restore: chrome-restore.sh
```

**CRITICAL: Backup script must use rsync, NOT tar:**
```bash
rsync -a --exclude='Cache/' --exclude='GPUCache/' \
  ~/.config/google-chrome/ ~/.local/backups/chrome/chrome-$TIMESTAMP/
```

**CRITICAL: Chrome-running detection with profile-sync-daemon.**
`psd` wraps Chrome in `fuse-overlayfs` with name like `alca-google-chrome`. The process detection MUST use exact names:
```bash
# BAD: pgrep -f "chrome$" misses real Chrome and may match fuse-overlayfs
# GOOD: Check exact process names used by Chrome in your distro
if pgrep -x "google-chrome" >/dev/null 2>&1 || pgrep -x "chrome" >/dev/null 2>&1; then
  echo "Chrome running — skipping backup"
  exit 0
fi
```
Also check what process names are actually used:
```bash
ps aux | grep -E "[/]chrome|[/](google-chrome|chromium)" | grep -v grep
```
```bash
if pgrep -x chrome >/dev/null 2>&1 || pgrep -x google-chrome-stable >/dev/null 2>&1; then
  echo "Chrome running — skipping backup"
  exit 0
fi
```

### 8. Profile-Sync-Daemon (psd) — FUSE Overlay Issue
Garuda runs `profile-sync-daemon` which mounts `~/.config/google-chrome/` as a **fuse-overlayfs**. This breaks `tar` — it only captures the directory entry, not the contents.

```bash
# Check if psd is active
mount | grep psd
# fuse-overlayfs on /run/user/1000/psd/alca-google-chrome type fuse.fuse-overlayfs
```

**Always use `rsync` instead of `tar` for Chrome backups:**
```bash
# BAD: tar sees only 1 file on fuse-overlayfs
tar --zstd -cf backup.tar.zst ~/.config/google-chrome/  # → 112 bytes

# GOOD: rsync handles fuse mounts correctly
rsync -a ~/.config/google-chrome/ /path/to/backup/  # → 13MB full profile
```

## Pitfalls
- **Never kill gnome-keyring-daemon in i3** unless you start ksecretd AND kwallet AND ensure they provide `org.freedesktop.secrets`
- **PAM must be set up** — without auto-unlock, the keyring starts locked and Chrome still can't decrypt
- **Wayland vs X11 matters** — i3 on X11 needs `--ozone-platform=x11` hint, but Chrome auto-detects; Vulkan conflicts with Wayland
- **Portal config must come AFTER keyring-daemon starts** — the daemon must register on DBus before portal tries to use it
- **If Chrome already lost its profile** — all encrypted data (passwords, cookies) is GONE. Only bookmarks/session from Google sync can be recovered
- **`pam_kwallet5.so` stays** — don't remove it, KDE still needs kwallet for KDE-specific secrets
- **profile-sync-daemon (psd) breaks `tar`** — Chrome profiles are on fuse-overlayfs, use `rsync` for backups, never `tar`
- **Chrome flags path**: `~/.config/chrome-flags.conf` (Arch/Garuda convention), not inside `~/.config/google-chrome/`
- **Portal init order**: Start gnome-keyring-daemon FIRST, wait 1s for DBus registration, THEN start xdg-desktop-portal backends
