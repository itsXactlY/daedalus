#!/usr/bin/env bash
# restore.sh template — recover the captured system from this repo
# Usage: bash restore.sh --dry-run | --confirm
#
# Customize per captured package lists and configs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=true
CONFIRM=false

for arg in "$@"; do
    case $arg in
        --confirm) CONFIRM=true; DRY_RUN=false ;;
        --dry-run) DRY_RUN=true ;;
        *) echo "Unknown: $arg"; exit 1 ;;
    esac
done

run() {
    if $DRY_RUN; then
        echo "[DRY-RUN] $*"
    else
        echo "[RUN]     $*"
        eval "$@"
    fi
}

step() {
    echo
    echo "═══ $* ═══"
}

[[ $EUID -ne 0 ]] && { echo "Need root for pacman operations. Use sudo."; exit 1; }

step "Restore from $REPO_ROOT"
echo "  Modus: $( $DRY_RUN && echo 'DRY-RUN' || echo 'CONFIRM')"

#───────────────────────────────────────────────────────────
# 1. Repo setup (chaotic-aur / custom keys)
#───────────────────────────────────────────────────────────

step "1/6 Chaotic-AUR Repo"
if [[ -f /etc/pacman.d/chaotic-mirrorlist ]]; then
    echo "  ✓ chaotic-mirrorlist vorhanden"
else
    run "pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com"
    run "pacman-key --lsign-key 3056513887B78AEB"
    run "pacman -U 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst'"
    run "pacman -U 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst'"
fi

#───────────────────────────────────────────────────────────
# 2. Official packages
#───────────────────────────────────────────────────────────

step "2/6 Offizielle Pakete"
PKG_OFFICIAL="$REPO_ROOT/packages/official.txt"
if [[ -f "$PKG_OFFICIAL" ]]; then
    count=$(wc -l < "$PKG_OFFICIAL")
    echo "  Würde installieren: $count Pakete aus [core]/[extra]/[multilib]"
    run "pacman -S --needed --noconfirm - < $PKG_OFFICIAL"
fi

#───────────────────────────────────────────────────────────
# 3. AUR packages (yay/paru)
#───────────────────────────────────────────────────────────

step "3/6 AUR-Pakete"
PKG_AUR="$REPO_ROOT/packages/aur.txt"
if [[ -f "$PKG_AUR" ]] && [[ -s "$PKG_AUR" ]]; then
    count=$(wc -l < "$PKG_AUR")
    echo "  Würde installieren: $count Pakete"
    if command -v yay >/dev/null; then
        run "yay -S --needed --noconfirm - < $PKG_AUR"
    elif command -v paru >/dev/null; then
        run "paru -S --needed --noconfirm - < $PKG_AUR"
    else
        echo "  ⚠ Kein AUR-Helper — installiere yay oder paru vorher"
    fi
fi

#───────────────────────────────────────────────────────────
# 4. Configs ausrollen
#───────────────────────────────────────────────────────────

step "4/6 Configs ausrollen"
HOME_DIR="${HOME:-/root}"

# Customize per repo's configs/ structure. Example:
# for src in $REPO_ROOT/configs/i3/*; do
#     run "cp $src $HOME_DIR/.config/i3/$(basename $src)"
# done

# System configs (root-owned):
for src in $REPO_ROOT/update-lifecycle/etc/skel/*; do
    [[ -f "$src" ]] && run "cp $src /etc/skel/$(basename $src)"
done

#───────────────────────────────────────────────────────────
# 5. Systemd user services (manual review required)
#───────────────────────────────────────────────────────────

step "5/6 systemd --user Services"
SYSU="$REPO_ROOT/configs/systemd/user"
if [[ -d "$SYSU" ]]; then
    echo "  Verfügbare Services:"
    ls -1 "$SYSU"/*.service 2>/dev/null | sed 's|.*/||' | sed 's/^/    /'
    echo
    echo "  → Manuell aktivieren mit:"
    echo "      systemctl --user daemon-reload"
    echo "      systemctl --user enable <name>.service"
fi

#───────────────────────────────────────────────────────────
# 6. Post-restore verification
#───────────────────────────────────────────────────────────

step "6/6 VERIFY"
echo "  Vergleiche gegen system-info/ Snapshot:"

for f in kernel.txt os-release.txt systemd-enabled.txt; do
    if [[ -f "$REPO_ROOT/system-info/$f" ]]; then
        run "cat $REPO_ROOT/system-info/$f"
    fi
done

echo
echo "✅ Restore dry-run complete. Run with --confirm to actually execute."