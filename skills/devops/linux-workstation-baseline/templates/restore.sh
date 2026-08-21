#!/usr/bin/env bash
# restore.sh — Baseline-Wiederherstellung aus diesem Repo.
#
# Voraussetzung: Arch-basiertes Basissystem ist bereits installiert
# (entweder archinstall, pacstrap oder Distro-ISO).
#
# Verwendung:
#   bash restore.sh --dry-run    # zeigt nur, was es tun würde (default)
#   bash restore.sh --confirm    # führt aus

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=true
CONFIRM=false

for arg in "$@"; do
    case $arg in
        --confirm) CONFIRM=true; DRY_RUN=false ;;
        --dry-run) DRY_RUN=true ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
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

echo "═══════════════════════════════════════════════════════"
echo " Baseline Restore"
echo " Repo:   $REPO_ROOT"
echo " Modus:  $( $DRY_RUN && echo 'DRY-RUN (use --confirm to execute)' || echo 'CONFIRM (executing)')"
echo "═══════════════════════════════════════════════════════"
echo

# ─── 1. CUSTOM REPO AKTIVIEREN ───
echo "─── 1/N Custom Repo aktivieren ───"
# Anpassen je nach Distro (chaotic-aur für Garuda, CachyOS-Repo für CachyOS, etc.)
KEY="3056513887B78AEB"
KEYSERVER="keyserver.ubuntu.com"
MIRROR="https://cdn-mirror.chaotic.cx"
if [[ -f /etc/pacman.d/chaotic-mirrorlist ]]; then
    echo "  ✓ Repo bereits konfiguriert"
else
    run "pacman-key --recv-key $KEY --keyserver $KEYSERVER"
    run "pacman-key --lsign-key $KEY"
    run "pacman -U '$MIRROR/chaotic-aur/chaotic-keyring.pkg.tar.zst'"
    run "pacman -U '$MIRROR/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst'"
fi
echo

# ─── 2. OFFIZIELLE PAKETE ───
echo "─── 2/N Offizielle Pakete installieren ───"
PKG_OFFICIAL="$REPO_ROOT/packages/official.txt"
if [[ -f "$PKG_OFFICIAL" ]]; then
    count=$(wc -l < "$PKG_OFFICIAL")
    echo "  Würde installieren: $count Pakete aus [core]/[extra]/[multilib]"
    run "pacman -S --needed --noconfirm - < $PKG_OFFICIAL"
else
    echo "  ✗ $PKG_OFFICIAL fehlt"; exit 1
fi
echo

# ─── 3. AUR-PAKETE ───
echo "─── 3/N AUR-Pakete installieren ───"
PKG_AUR="$REPO_ROOT/packages/aur.txt"
if [[ -f "$PKG_AUR" ]] && [[ -s "$PKG_AUR" ]]; then
    count=$(wc -l < "$PKG_AUR")
    echo "  Würde installieren: $count Pakete aus AUR/custom"
    cat "$PKG_AUR"
    if command -v yay >/dev/null; then
        run "yay -S --needed --noconfirm - < $PKG_AUR"
    elif command -v paru >/dev/null; then
        run "paru -S --needed --noconfirm - < $PKG_AUR"
    else
        echo "  ⚠ Kein AUR-Helper gefunden. Installiere yay vorher:"
        echo "      pacman -S --needed git base-devel"
        echo "      git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si"
    fi
else
    echo "  Keine AUR-Pakete oder Datei leer."
fi
echo

# ─── 4. CONFIGS AUSROLLEN ───
echo "─── 4/N Configs ausrollen ───"
run "mkdir -p ~/.config/i3 ~/.config/polybar"
run "cp $REPO_ROOT/configs/i3/config ~/.config/i3/config"
run "cp $REPO_ROOT/configs/polybar/config.ini ~/.config/polybar/config.ini"
run "cp $REPO_ROOT/configs/polybar/launch.sh ~/.config/polybar/launch.sh && chmod +x ~/.config/polybar/launch.sh"
run "cp $REPO_ROOT/configs/shell/bashrc ~/.bashrc"
run "cp $REPO_ROOT/configs/shell/bash_profile ~/.bash_profile"
run "cp $REPO_ROOT/configs/x11/Xresources ~/.Xresources"
run "cp $REPO_ROOT/configs/x11/xprofile ~/.xprofile"

if [[ -d "$REPO_ROOT/configs/scripts/bin" ]]; then
    run "mkdir -p ~/bin"
    run "cp $REPO_ROOT/configs/scripts/bin/* ~/bin/ && chmod +x ~/bin/*"
fi
echo

# ─── 5. SYSTEMD-USER-SERVICES ───
echo "─── 5/N systemd --user Services (gewünschte reaktivieren) ───"
SYSU="$REPO_ROOT/configs/systemd/user"
if [[ -d "$SYSU" ]]; then
    echo "  Verfügbare Services:"
    ls -1 "$SYSU"/*.service 2>/dev/null | sed 's|.*/||' | sed 's/^/    /'
    echo
    echo "  → Manuell aktivieren mit:"
    echo "      systemctl --user daemon-reload"
    echo "      systemctl --user enable <name>.service"
    echo "  ⚠ NICHT alles blind enablen — projekt-spezifisch prüfen!"
fi
echo

# ─── 6. POST-RESTART DISTRO-UPDATE ───
echo "─── 6/N Distro-Tweak-Layer anwerfen ───"
if command -v garuda-update >/dev/null; then
    run "sudo garuda-update"
elif command -v <distro>-update >/dev/null; then
    run "sudo <distro>-update"
else
    echo "  Distro-Update-Tool nicht gefunden — eventuell Metapakete fehlen."
fi
echo

echo "═══════════════════════════════════════════════════════"
echo " Fertig. Verifiziere mit:"
echo "   systemctl --user list-unit-files --state=enabled"
echo "   pacman -Qqen | diff - $REPO_ROOT/packages/official.txt"
echo "═══════════════════════════════════════════════════════"