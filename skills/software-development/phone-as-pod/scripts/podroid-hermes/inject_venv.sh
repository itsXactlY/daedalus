#!/usr/bin/env bash
# ============================================================================
# inject_venv.sh — inject the native-python hermes-agent venv into the
# podroid Alpine rootfs.tar (replacing the Nuitka ELF).
# ============================================================================
# Usage:
#   VENV=/tmp/hermes-build/out/venv \
#   START=/path/to/start_hermes_venv.sh \
#   REPO=/home/alca/projects/podroid-hermes \
#   ./inject_venv.sh
#
# Replaces /opt/hermes/hermes-agent.bin with /opt/hermes/venv + start.sh.
# ============================================================================
set -euo pipefail

REPO="${REPO:-/home/alca/projects/podroid-hermes}"
VENV="${VENV:-/tmp/hermes-build/out/venv}"
START="${START:-$REPO/vm-image/start_hermes_venv.sh}"
ROOTFS_SRC="$REPO/android/hermes-android/app/src/main/assets/hermes-pod/rootfs.tar"

[[ -d "$VENV/bin" ]] || { echo "VENV not found at $VENV"; exit 1; }
[[ -f "$START" ]]    || { echo "START not found at $START"; exit 1; }
[[ -f "$ROOTFS_SRC" ]] || { echo "rootfs.tar not found at $ROOTFS_SRC"; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "[inject] extracting rootfs.tar"
mkdir -p "$WORK/root"
tar -xf "$ROOTFS_SRC" -C "$WORK/root"

echo "[inject] removing old Nuitka ELF"
rm -f "$WORK/root/opt/hermes/hermes-agent.bin"

echo "[inject] copying venv -> /opt/hermes/venv"
mkdir -p "$WORK/root/opt/hermes/venv"
cp -a "$VENV/." "$WORK/root/opt/hermes/venv/"

echo "[inject] installing venv launcher as start.sh"
cp "$START" "$WORK/root/opt/hermes/start.sh"
chmod +x "$WORK/root/opt/hermes/start.sh"

echo "[inject] repacking rootfs.tar"
tar -C "$WORK/root" -cf "$ROOTFS_SRC" .

echo "[inject] repacked rootfs.tar: $(stat -c %s "$ROOTFS_SRC") bytes"
echo "[inject] venv size: $(du -sh "$VENV" | cut -f1)"
echo "[inject] DONE"
