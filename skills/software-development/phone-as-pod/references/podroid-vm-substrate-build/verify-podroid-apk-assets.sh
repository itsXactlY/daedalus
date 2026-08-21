#!/usr/bin/env bash
# verify-podroid-apk-assets.sh
#
# Verify that an APK built by the Podroid build pipeline contains all
# the assets needed to boot the VM. Use this BEFORE `adb install` —
# a missing asset means the VM will hang at boot, and the only way
# to diagnose it is to read console.log (which is empty until the
# kernel boots).
#
# Usage:
#   ./verify-podroid-apk-assets.sh path/to/app-debug.apk
#   ./verify-podroid-apk-assets.sh                       # default: app/build/outputs/apk/debug/app-debug.apk
#
# Exit code:
#   0 = all required assets present
#   1 = one or more assets missing (prints which ones)

set -euo pipefail

APK="${1:-app/build/outputs/apk/debug/app-debug.apk}"

if [ ! -f "$APK" ]; then
    echo "ERROR: APK not found at $APK" >&2
    echo "Usage: $0 path/to/app-debug.apk" >&2
    exit 2
fi

# 7 required assets. If any of these is missing, the VM will not
# boot or the iris-messenger container will not start.
REQUIRED=(
    "assets/vmlinuz-virt"                          # Linux kernel
    "assets/initrd.img"                            # Initramfs (init-podroid)
    "assets/alpine-rootfs.squashfs"                # Alpine 3.23 rootfs (262 MB)
    "lib/arm64-v8a/libqemu-system-aarch64.so"     # QEMU 11.0.0 (38 MB)
    "lib/arm64-v8a/libslirp.so"                    # QEMU user-mode networking (1 MB)
    "assets/iris-messenger/iris-messenger-amd64.tar"  # Vendor container image (26 MB)
    "assets/iris-messenger/iris-messenger.bin"    # Vendor binary (20 MB)
)

# 4 optional assets. Missing = degraded functionality but VM still boots.
OPTIONAL=(
    "assets/qemu/efi-virtio.rom"                  # EFI firmware ROM
    "assets/qemu/keymaps/ar"                      # QEMU keyboard layout
    "lib/arm64-v8a/libpodroid-bridge.so"          # JNI bridge for the Terminal UI
    "lib/arm64-v8a/libpodroid-launcher.so"        # JNI launcher for QEMU process
)

missing_required=0
missing_optional=0

echo "=== Verifying $APK ==="
echo
echo "Required assets:"
for asset in "${REQUIRED[@]}"; do
    if unzip -l "$APK" "$asset" >/dev/null 2>&1; then
        size=$(unzip -l "$APK" "$asset" 2>/dev/null | tail -1 | awk '{print $1}')
        printf "  [OK]   %-55s  (%s bytes)\n" "$asset" "$size"
    else
        printf "  [MISS] %-55s\n" "$asset"
        missing_required=$((missing_required + 1))
    fi
done

echo
echo "Optional assets:"
for asset in "${OPTIONAL[@]}"; do
    if unzip -l "$APK" "$asset" >/dev/null 2>&1; then
        size=$(unzip -l "$APK" "$asset" 2>/dev/null | tail -1 | awk '{print $1}')
        printf "  [OK]   %-55s  (%s bytes)\n" "$asset" "$size"
    else
        printf "  [WARN] %-55s\n" "$asset"
        missing_optional=$((missing_optional + 1))
    fi
done

echo
total_size=$(stat -c %s "$APK" 2>/dev/null || stat -f %z "$APK")
echo "Total APK size: $((total_size / 1024 / 1024)) MB"

if [ "$missing_required" -gt 0 ]; then
    echo
    echo "FAIL: $missing_required required asset(s) missing."
    echo "Re-run the build:"
    echo "  cd /home/alca/projects/jrwl-messenger/android/podroid"
    echo "  ./build-all.sh initramfs   # vmlinuz-virt + initrd.img"
    echo "  ./build-all.sh rootfs      # alpine-rootfs.squashfs"
    echo "  ./build-all.sh qemu        # libqemu-*.so, libslirp.so"
    echo "  ./gradlew assembleDebug"
    exit 1
fi

if [ "$missing_optional" -gt 0 ]; then
    echo
    echo "WARN: $missing_optional optional asset(s) missing. VM will boot but some features may be degraded."
fi

echo
echo "PASS: all required assets present. Safe to install."
