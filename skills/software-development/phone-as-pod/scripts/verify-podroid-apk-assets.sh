#!/usr/bin/env bash
# ============================================================================
# verify-podroid-apk-assets.sh — APK sanity check for phone-as-pod APKs
# ============================================================================
# Run this AFTER ./build-all.sh to confirm the APK actually contains the
# bundled native binaries the pod needs at runtime. Catches the most
# common packaging mistakes before the user installs a broken APK.
#
# Usage:
#   ./scripts/verify-podroid-apk-assets.sh                # debug APK by default
#   ./scripts/verify-podroid-apk-assets.sh release        # release APK
#   APK=/path/to/app.apk ./scripts/verify-podroid-apk-assets.sh
#
# Exit codes:
#   0  all required assets present
#   1  one or more required assets missing
#   2  APK not found
#
# Substrate B (proot + native ELF) defaults. For substrate A (Podroid/VM),
# change REQUIRED to:
#   "lib/arm64-v8a/libqemu-system-aarch64.so"
#   "assets/vmlinuz-virt"  "assets/initrd.img"
#   "assets/alpine-rootfs.squashfs"  "assets/<svc>/<svc>-arm64.tar"
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VARIANT="${1:-debug}"
APK="${APK:-${SCRIPT_DIR}/../android/hermes-android/app/build/outputs/apk/${VARIANT}/app-${VARIANT}.apk}"

if [[ ! -f "$APK" ]]; then
    echo "APK not found: $APK" >&2
    echo "" >&2
    echo "Usage: $0 [debug|release]" >&2
    echo "   or: APK=/path/to/app.apk $0" >&2
    exit 2
fi

echo "Verifying: $APK"
echo "Size:      $(stat -c %s "$APK") bytes"
echo ""

REQUIRED=(
    "assets/hermes-pod/hermes-agent.bin"
    "assets/hermes-pod/proot"
    "assets/hermes-pod/rootfs.tar"
    "classes.dex"
    "AndroidManifest.xml"
)

FAIL=0
for f in "${REQUIRED[@]}"; do
    if unzip -l "$APK" 2>/dev/null | grep -q "$f"; then
        size=$(unzip -l "$APK" 2>/dev/null | grep "$f" | awk '{print $1}')
        printf "  \033[1;32m✓\033[0m  %-50s %12s bytes\n" "$f" "$size"
    else
        printf "  \033[1;31m✗\033[0m  %-50s MISSING\n" "$f"
        FAIL=1
    fi
done

echo ""
if (( FAIL )); then
    echo "APK is missing required assets."
    echo ""
    echo "Common causes:"
    echo "  1. Forgot to run the build step that produces the asset"
    echo "     (for substrate A: ./build-all.sh qemu rootfs apk)"
    echo "  2. Asset directory is empty (extraction or download failed)"
    echo "  3. Asset is in app/src/main/assets/ but the path doesn't match"
    echo "  4. androidResources.noCompress in build.gradle.kts has wrong path"
    echo ""
    echo "Inspect with: unzip -l \"$APK\" | grep -E 'hermes|proot|rootfs'"
    exit 1
fi

echo "All required assets present."
echo ""

# Verify the binaries are actually the right architecture.
echo "Hermes-agent ELF header (first 4 bytes; \\x7f\\x45\\x4c\\x46 = ELF magic):"
unzip -p "$APK" assets/hermes-pod/hermes-agent.bin 2>/dev/null | head -c 4 | xxd | head -1
echo ""
echo "Proot binary header:"
unzip -p "$APK" assets/hermes-pod/proot 2>/dev/null | head -c 4 | xxd | head -1
echo ""
echo "Rootfs.tar header (first 16 bytes; 'ustar' magic should be at offset 257):"
unzip -p "$APK" assets/hermes-pod/rootfs.tar 2>/dev/null | head -c 16 | xxd | head -1

echo ""
echo "If the ELF headers above don't show 7f454c46, the binary didn't"
echo "make it into the APK cleanly. Re-run the build."
