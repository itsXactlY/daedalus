---
name: chrome-kde-i3-keyring-fix
description: Fix Chrome profile destruction when switching between KDE and i3 on dual-DE Linux systems (Garuda/Arch). Covers root cause diagnosis, PAM keyring setup, Chrome flags, portal config, psd-compatible backups, and KDE→i3 settings sync.
version: 1.0
created: 2026-04-21
---

# Chrome KDE/i3 Keyring Fix

## When to Use
Chrome loses profile, passwords, bookmarks every time you switch between KDE Plasma and i3 (or reboot). Symptoms: "First Run" file reappears, profile resets to 22MB, all tabs/sessions gone.

## Root Cause
1. Chrome stores encryption key via `xdg-desktop-portal` (NOT directly)
2. KDE's portal backend uses kwallet, i3's uses gnome-keyring (or nothing)
3. No shared secret service = encryption key lost on DE switch
4. Common culprit: `keyring-init.sh` **kills** gnome-keyring-daemon at i3 startup instead of starting it
5. `ksecretd` is installed but never started in i3
6. Chrome's `Local State` has no `encrypted_key` field — 100% portal-dependent

## Diagnostic Steps
```bash
# 1. Check Chrome's encryption method
python3 -c "import json; s=json.load(open('$HOME/.config/google-chrome/Local State')); print(s.get('os_crypt',{}))"
# portal + prev_desktop = BAD (no portal in other DE)

# 2. Check keyring-init.sh (the usual villain)
cat ~/.config/i3/keyring-init.sh
# If it contains "pkill gnome-keyring-daemon" = ROOT CAUSE

# 3. Check PAM integration
grep keyring /etc/pam.d/sddm
# Lines starting with # = disabled = NO AUTO-UNLOCK

# 4. Check running secret service
busctl --user call org.freedesktop.secrets /org/freedesktop/secrets org.freedesktop.DBus.Peer Ping
# No response = no secret service = Chrome doomed

# 5. Check psd (profile-sync-daemon) mount
mount | grep psd
# fuse-overlayfs = tar won't work, use rsync
```

## Fix Steps (ordered)

### 1. PAM Keyring Auto-Unlock
```bash
sudo cp /etc/pam.d/sddm /etc/pam.d/sddm.bak.$(date +%s)

# Uncomment pam_gnome_keyring.so (keep kwallet too!)
sudo sed -i 's/^#-auth.*pam_gnome_keyring.so/-auth       optional    pam_gnome_keyring.so/' /etc/pam.d/sddm
sudo sed -i 's/^#-password.*pam_gnome_keyring.so/-password   optional    pam_gnome_keyring.so    use_authtok/' /etc/pam.d/sddm
sudo sed -i 's/^#-session.*pam_gnome_keyring.so/-session    optional    pam_gnome_keyring.so    auto_start/' /etc/pam.d/sddm

# Also for TTY login
if ! grep -q 'pam_gnome_keyring.so' /etc/pam.d/login; then
    sudo tee -a /etc/pam.d/login << 'EOF'
auth       optional    pam_gnome_keyring.so
session    optional    pam_gnome_keyring.so auto_start
EOF
fi
```

### 2. Rewrite keyring-init.sh
```bash
cat > ~/.config/i3/keyring-init.sh << 'SCRIPT'
#!/bin/bash
# DO NOT kill gnome-keyring-daemon! Start it instead.
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval "$(dbus-launch --sh-syntax 2>/dev/null)"
    export DBUS_SESSION_BUS_ADDRESS
fi
if ! pgrep -x gnome-keyring-d > /dev/null; then
    eval "$(echo '' | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null)"
fi
eval "$(gnome-keyring-daemon --start --components=secrets 2>/dev/null)" 2>/dev/null || true
export GNOME_KEYRING_CONTROL SSH_AUTH_SOCK
sleep 1
~/.config/i3/scripts/portal-setup.sh 2>/dev/null &
~/.config/i3/scripts/sync-kde-settings.sh 2>/dev/null &
SCRIPT
chmod +x ~/.config/i3/keyring-init.sh
```

### 3. Chrome Flags
```bash
cat > ~/.config/chrome-flags.conf << 'EOF'
--password-store=gnome
--disable-features=PortalPasswordStore,Vulkan
--disk-cache-size=524288000
--profile-directory=Default
EOF
```

### 4. Portal Config
```bash
mkdir -p ~/.config/xdg-desktop-portal
cat > ~/.config/xdg-desktop-portal/portals.conf << 'EOF'
[preferred]
default=gtk
org.freedesktop.impl.portal.Secret=gnome-keyring
EOF
```

### 5. Portal Setup Script (i3)
```bash
cat > ~/.config/i3/scripts/portal-setup.sh << 'SCRIPT'
#!/bin/bash
pkill -f xdg-desktop-portal 2>/dev/null; sleep 0.5
/usr/lib/xdg-desktop-portal-gtk &; sleep 1
/usr/lib/xdg-desktop-portal &; sleep 1
SCRIPT
chmod +x ~/.config/i3/scripts/portal-setup.sh
```

### 6. Chrome Backup (rsync, NOT tar)
tar FAILS on psd fuse-overlayfs (only captures 1 file). Always use rsync:
```bash
# Backup (skip caches)
rsync -a --exclude='Cache/' --exclude='GPUCache/' --exclude='ShaderCache/' \
  --exclude='Crash Reports/' --exclude='BrowserMetrics/' \
  "$HOME/.config/google-chrome/" "$BACKUP_DIR/chrome-$(date +%Y%m%d_%H%M%S)/"
```

### 7. xprofile for i3
Add to `~/.xprofile`:
```bash
export XDG_CURRENT_DESKTOP=i3
export XDG_SESSION_TYPE=x11
export KDE_SESSION_VERSION=6
export GTK_USE_PORTAL=1
export QT_QPA_PLATFORMTHEME=kvantum
export QT_STYLE_OVERRIDE=kvantum-dark
```

## Pitfalls
- **NEVER kill gnome-keyring-daemon** in i3 — it must run alongside kwallet
- **tar fails on psd** (fuse-overlayfs) — use rsync always
- **Don't use `--password-store=kwallet`** in Chrome — kwallet isn't a D-Bus secret service in i3
- **ksecretd doesn't self-start** in i3 — gnome-keyring-daemon does (via PAM)
- **Check `os_crypt` in Local State** before assuming the profile is intact
- Both PAM lines (gnome-keyring + kwallet) must coexist — they're complementary

## Verification
```bash
# 1. After login, check secret service is running
busctl --user call org.freedesktop.secrets /org/freedesktop/secrets org.freedesktop.DBus.Peer Ping

# 2. Check gnome-keyring-daemon
pgrep -x gnome-keyring-d && echo "OK" || echo "FAIL"

# 3. Check Chrome can see the service
# Launch Chrome, check chrome://version for "Password store" line

# 4. Check backup works
~/.local/bin/chrome-backup.sh
```

## Related
- Neural memories: chrome-profile-keyring-fix-kde-i3 (24500), psd-fuse-overlayfs-tar-breaks (24501), chrome-os-crypt-portal-encryption (24502)
- Scripts: ~/.config/i3/keyring-init.sh, ~/.config/i3/scripts/portal-setup.sh, ~/.config/i3/scripts/sync-kde-settings.sh, ~/.local/bin/chrome-backup.sh, ~/.local/bin/chrome-restore.sh
- Cron: chrome-backup.sh every 30 min, keep 5 backups
