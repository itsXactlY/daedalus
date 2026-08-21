#!/usr/bin/env bash
# find-missing-libs.sh
#
# Given a running container that exits with "error while loading shared
# libraries: libXXX.so.6", extract the missing lib name and copy it from
# the host filesystem into ./lib/ for the next build iteration.
#
# Usage:
#   ./scripts/find-missing-libs.sh <missing-lib-name>
# Example:
#   ./scripts/find-missing-libs.sh libssl.so.3
#
# Then add the new lib to your Containerfile and rebuild.

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <missing-lib-name>"
    echo "Example: $0 libssl.so.3"
    exit 1
fi

LIB="$1"
echo "Looking for $LIB on host..."

# Search /usr/lib, /usr/lib64, /lib, /lib64 — but exclude lib32 (32-bit)
FOUND=$(find /usr/lib /usr/lib64 /lib /lib64 \
    -name "${LIB}*" -not -path '*/lib32/*' \
    2>/dev/null | head -1)

if [ -z "$FOUND" ]; then
    echo "  ✗ $LIB NOT FOUND on host."
    echo ""
    echo "Possible causes:"
    echo "  1. The package isn't installed. Try: pacman -Ss <lib-name>"
    echo "  2. The lib name is wrong. Check the exact error message."
    echo "  3. It's a 32-bit lib (excluded by this script)."
    exit 2
fi

# Resolve symlinks — copy the actual file (binary symlinks confuse ld-linux)
REAL=$(readlink -f "$FOUND")
echo "  Found: $FOUND"
echo "  Real:  $REAL"

mkdir -p ./lib
cp "$REAL" "./lib/$LIB"
echo "  ✓ Copied to ./lib/$LIB ($(du -h ./lib/$LIB | cut -f1))"

echo ""
echo "Next steps:"
echo "  1. Add this line to your Containerfile:"
echo "       COPY lib/$LIB /usr/lib/$LIB"
echo "  2. podman build --no-cache -f Containerfile -t localhost/app:latest ."
echo "  3. podman run --rm localhost/app:latest --help"
