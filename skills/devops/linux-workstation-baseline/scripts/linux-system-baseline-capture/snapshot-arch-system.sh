#!/usr/bin/env bash
# snapshot-arch-system.sh — Re-runnable snapshot for Arch-based systems
# Usage: bash snapshot-arch-system.sh <repo-name>
# Creates ~/code/<repo-name>/ with the 7-layer structure.
#
# Idempotent: re-runs only update changed/new files (uses rsync semantics).
# Designed for Arch / Garuda / Manjaro / EndeavourOS / etc.

set -euo pipefail

REPO_NAME="${1:?Usage: $0 <repo-name> [home-dir]}"
HOME_DIR="${2:-${HOME:-/root}}"
REPO="$HOME_DIR/code/$REPO_NAME"

# Detect distro
if [[ -f /etc/os-release ]]; then
    DISTRO=$(grep '^NAME=' /etc/os-release | cut -d= -f2 | tr -d '"' | tr 'A-Z' 'a-z' | sed 's/ .*//')
else
    DISTRO="arch"
fi

echo "Snapshot target: $REPO"
echo "Distro detected: $DISTRO"
echo "Home: $HOME_DIR"
echo

# Create skeleton
mkdir -p "$REPO"/{packages,configs,update-lifecycle,scripts,system-info}
mkdir -p "$REPO"/configs/{i3,polybar,shell,x11,systemd/user,scripts/bin}
mkdir -p "$REPO"/update-lifecycle/{hooks,runner-scripts,lib-$DISTRO,tools,etc}

# ────────────────────────────────────────────────────────────
# Layer 1: Packages
# ────────────────────────────────────────────────────────────
echo "─── Layer 1: Packages ───"
pacman -Qqen > "$REPO/packages/official.txt"
pacman -Qqem > "$REPO/packages/aur.txt"
pacman -Qqet > "$REPO/packages/explicit.txt"
pacman -Qq  > "$REPO/packages/all.txt"
wc -l "$REPO/packages/"*.txt

# ────────────────────────────────────────────────────────────
# Layer 2: Configs (best-effort, skip missing)
# ────────────────────────────────────────────────────────────
echo
echo "─── Layer 2: Configs ───"
copied=0
for src_dst in \
    "$HOME_DIR/.config/i3/config:configs/i3/config" \
    "$HOME_DIR/.config/i3/config.local:configs/i3/config.local" \
    "$HOME_DIR/.config/polybar/config.ini:configs/polybar/config.ini" \
    "$HOME_DIR/.config/polybar/launch.sh:configs/polybar/launch.sh" \
    "$HOME_DIR/.zshrc:configs/shell/zshrc" \
    "$HOME_DIR/.bashrc:configs/shell/bashrc" \
    "$HOME_DIR/.bash_profile:configs/shell/bash_profile" \
    "$HOME_DIR/.xinitrc:configs/x11/xinitrc" \
    "$HOME_DIR/.Xresources:configs/x11/Xresources"; do
    src="${src_dst%:*}"
    dst="${src_dst#*:}"
    if [[ -f "$src" ]]; then
        cp "$src" "$REPO/$dst"
        copied=$((copied + 1))
    fi
done
echo "  Copied $copied user configs"

# CRITICAL: /etc/skel/
echo "  Checking /etc/skel/ (often non-empty)..."
if [[ -n "$(ls -A /etc/skel/ 2>/dev/null)" ]]; then
    mkdir -p "$REPO/configs/skel"
    cp -r /etc/skel/. "$REPO/configs/skel/" 2>/dev/null || true
    echo "    Captured $(ls -A /etc/skel/ | wc -l) files from /etc/skel/"
else
    echo "    /etc/skel/ is empty — no defaults for new users"
fi

# ~/bin scripts
if [[ -d "$HOME_DIR/bin" ]]; then
    cp -r "$HOME_DIR/bin" "$REPO/configs/scripts/"
    echo "  Captured ~/bin/ ($(ls "$HOME_DIR/bin" | wc -l) entries)"
fi

# User systemd services
if [[ -d "$HOME_DIR/.config/systemd/user" ]] && [[ -n "$(ls -A "$HOME_DIR/.config/systemd/user" 2>/dev/null)" ]]; then
    cp -r "$HOME_DIR/.config/systemd/user" "$REPO/configs/systemd/"
    echo "  Captured systemd/user/ ($(find "$HOME_DIR/.config/systemd/user" -maxdepth 2 -type f | wc -l) files)"
fi

# ────────────────────────────────────────────────────────────
# Layer 3: Distro machinery
# ────────────────────────────────────────────────────────────
echo
echo "─── Layer 3: $DISTRO machinery ───"

# Capture distro-named dirs (best-effort)
for path in \
    "/usr/lib/$DISTRO" \
    "/usr/bin/${DISTRO}-"* \
    "/etc/$DISTRO" \
    "/etc/${DISTRO}-settings" \
    "/etc/default/grub.d/*${DISTRO}*" \
    "/etc/logrotate.d/${DISTRO}-*" \
    "/etc/xdg/autostart/${DISTRO}-*.desktop" \
    "/etc/snapper/config-templates/$DISTRO"; do
    for expanded in $path; do
        if [[ -e "$expanded" ]]; then
            target="$REPO/update-lifecycle/$(basename "$expanded")"
            if [[ -d "$expanded" ]]; then
                [[ -d "$target" ]] || mkdir -p "$target"
                cp -rn "$expanded"/* "$target/" 2>/dev/null || true
            else
                cp "$expanded" "$target" 2>/dev/null || true
            fi
        fi
    done
done

# Pacman hooks (distro-related + general update lifecycle)
echo "  Pacman hooks:"
for hook in /usr/share/libalpm/hooks/*${DISTRO}* \
            /usr/share/libalpm/hooks/snap-pac* \
            /usr/share/libalpm/hooks/*linux-modules* \
            /usr/share/libalpm/hooks/*dracut* \
            /usr/share/libalpm/hooks/*grub-install* \
            /usr/share/libalpm/hooks/*lsb-release* \
            /usr/share/libalpm/hooks/*os-release* \
            /usr/share/libalpm/hooks/*systemd-sysctl*; do
    if [[ -f "$hook" ]]; then
        cp "$hook" "$REPO/update-lifecycle/hooks/"
        echo "    $(basename "$hook")"
    fi
done

# Runner scripts
echo "  Runner scripts:"
for s in /usr/share/libalpm/scripts/*${DISTRO}*; do
    if [[ -x "$s" ]]; then
        cp "$s" "$REPO/update-lifecycle/runner-scripts/"
        chmod +x "$REPO/update-lifecycle/runner-scripts/$(basename "$s")"
        echo "    $(basename "$s")"
    fi
done

# ────────────────────────────────────────────────────────────
# Layer 6: Runtime snapshot
# ────────────────────────────────────────────────────────────
echo
echo "─── Layer 6: Runtime snapshot ───"
uname -a                       > "$REPO/system-info/kernel.txt"
cat /etc/os-release            > "$REPO/system-info/os-release.txt"
lsblk -f                       > "$REPO/system-info/lsblk.txt" 2>/dev/null || echo "(lsblk failed)" > "$REPO/system-info/lsblk.txt"
cat /etc/fstab                 > "$REPO/system-info/fstab.txt"
systemctl list-unit-files --state=enabled > "$REPO/system-info/systemd-enabled.txt" 2>/dev/null || true

# ────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────
echo
echo "═══ Snapshot complete ═══"
echo "  Repo:   $REPO"
echo "  Files:  $(find "$REPO" -type f | wc -l)"
echo "  Size:   $(du -sh "$REPO" | cut -f1)"
echo
echo "Next steps:"
echo "  1. Write README.md with Profil + Restore-Anleitung + Pitfalls"
echo "  2. Write restore.sh (copy from templates/restore-script.sh)"
echo "  3. (Optional) Write install-${DISTRO}-on-arch.sh for blank-install path"
echo "  4. Write update-lifecycle/LIFECYCLE.md enumerating every hook"
echo "  5. git init -b main && git add -A"
echo "  6. git -c commit.gpgsign=false commit -m 'Initial baseline snapshot'"
echo "  7. gh repo create $REPO_NAME --private --source=. --push"