#!/usr/bin/env bash
# Idempotent installer template
# Copy this file, rename it install-<distro>-on-<base>.sh, and customize:
#   - $KEYS        — GPG keys to import (Garuda: F77A8D43C9CDB9A3, Chaotic: 3056513887B78AEB)
#   - $REPO_BLOCKS — pacman.conf blocks to add (or apt sources for Debian)
#   - $BASE_PKGS   — packages to install (idempotent via --needed)
#   - $VERIFY_TARGETS — files to verify in the final step
#
# Conventions:
#   - Every --dry-run output is prefixed with [DRY-RUN]
#   - Every --confirm output is prefixed with [RUN]
#   - Final step lists every expected component with ✓/✗
#   - Script is bash -n clean

set -euo pipefail

#───────────────────────────────────────────────────────────
# Configuration — customize per installer
#───────────────────────────────────────────────────────────

KEYS=( )
REPO_BLOCKS=""
BASE_PKGS=( )
VERIFY_TARGETS=( )

#───────────────────────────────────────────────────────────
# CLI parsing
#───────────────────────────────────────────────────────────

DRY_RUN=true
CONFIRM=false
EDITION="default"

for arg in "$@"; do
    case $arg in
        --confirm)         CONFIRM=true; DRY_RUN=false ;;
        --dry-run)         DRY_RUN=true ;;
        --edition=*)       EDITION="${arg#*=}" ;;
        --help|-h)
            sed -n '2,5p' "$0"
            exit 0
            ;;
        *) echo "Unbekanntes Argument: $arg"; exit 1 ;;
    esac
done

#───────────────────────────────────────────────────────────
# Helpers
#───────────────────────────────────────────────────────────

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

#───────────────────────────────────────────────────────────
# Pre-flight
#───────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    echo "FEHLER: Bitte als root ausführen (oder mit sudo)."
    exit 1
fi

if ! command -v pacman >/dev/null 2>&1; then
    echo "FEHLER: pacman nicht gefunden — kein Arch-basiertes System."
    exit 1
fi

step "Installer — Konfiguration"
echo "  Edition:   $EDITION"
echo "  Modus:     $( $DRY_RUN && echo 'DRY-RUN (use --confirm)' || echo 'CONFIRM (läuft)')"
echo "  Keys:      ${KEYS[*]:-(none)}"
echo "  Base-Pkgs: ${BASE_PKGS[*]:-(none)}"

#───────────────────────────────────────────────────────────
# Step 1/N: Backup configs
#───────────────────────────────────────────────────────────

step "1/N pacman.conf sichern"
BACKUP="/etc/pacman.conf.bak.$(basename "$0" .sh).$(date +%F)"
if [[ -f "$BACKUP" ]]; then
    echo "  ✓ Backup existiert bereits: $BACKUP"
else
    run "cp /etc/pacman.conf $BACKUP"
fi

#───────────────────────────────────────────────────────────
# Step 2/N: Import keys
#───────────────────────────────────────────────────────────

step "2/N GPG-Keys importieren"
run "pacman-key --init"
run "pacman-key --populate archlinux"
for key in "${KEYS[@]}"; do
    run "pacman-key --recv-key $key --keyserver keyserver.ubuntu.com"
    run "pacman-key --lsign-key $key"
done

#───────────────────────────────────────────────────────────
# Step 3/N: Add repo blocks
#───────────────────────────────────────────────────────────

step "3/N Repo-Blöcke anhängen"
if [[ -n "$REPO_BLOCKS" ]]; then
    # Idempotent: only append if not already present
    if grep -q "^\[custom-repo\]" /etc/pacman.conf 2>/dev/null; then
        echo "  ✓ Repo-Block bereits in pacman.conf"
    else
        run "bash -c 'cat >> /etc/pacman.conf <<EOF
$REPO_BLOCKS
EOF'"
    fi
fi

#───────────────────────────────────────────────────────────
# Step 4/N: pacman -Sy
#───────────────────────────────────────────────────────────

step "4/N pacman-Datenbanken synchronisieren"
run "pacman -Sy"

#───────────────────────────────────────────────────────────
# Step 5/N: Install packages (idempotent via --needed)
#───────────────────────────────────────────────────────────

step "5/N Pakete installieren (idempotent)"
if [[ ${#BASE_PKGS[@]} -gt 0 ]]; then
    run "pacman -S --needed --noconfirm ${BASE_PKGS[*]}"
fi

#───────────────────────────────────────────────────────────
# Step 6/N: Run post-install commands
#───────────────────────────────────────────────────────────

step "6/N Post-Install"
# Add custom post-install commands here. Examples:
# run "systemctl enable <service>"
# run "<distro>-update --no-update --auto"

#───────────────────────────────────────────────────────────
# Step N/N: VERIFY all expected components
#───────────────────────────────────────────────────────────

step "VERIFY: alle Komponenten prüfen"

missing=0
total=${#VERIFY_TARGETS[@]}

for target in "${VERIFY_TARGETS[@]}"; do
    if [[ -e "$target" ]]; then
        echo "  ✓ $target"
    else
        echo "  ✗ $target FEHLT"
        missing=$((missing + 1))
    fi
done

echo
if [[ $missing -eq 0 ]]; then
    echo "  ✅ Alle $total Komponenten vorhanden."
else
    echo "  ⚠ $missing von $total Komponenten fehlen."
fi

#───────────────────────────────────────────────────────────
# Zusammenfassung
#───────────────────────────────────────────────────────────

step "Fertig"
cat <<EOF

✅ Installation abgeschlossen.

   Backup: $BACKUP
   Edition: $EDITION

NÄCHSTE SCHRITTE:

  1) Reboot: sudo reboot
  2) Verifizieren: pacman -Q | grep <distro>
  3) Bei Problemen: $0 --dry-run erneut laufen lassen

EOF