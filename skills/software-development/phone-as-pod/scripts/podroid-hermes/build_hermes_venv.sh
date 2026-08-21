#!/usr/bin/env bash
# ============================================================================
# build_hermes_venv.sh — native aarch64 musl venv of hermes-agent[termux]
# ============================================================================
# Primary: build on an x86_64 Linux HOST via podman/docker + qemu-aarch64-static
# (binfmt_misc registers qemu-aarch64, so --platform=linux/arm64 just works).
# The venv is built inside alpine:3.23 (musl) so it drops into the podroid
# Alpine rootfs at /opt/hermes/venv.
#
# Usage:
#   SRC=/home/alca/.hermes/hermes-agent OUT=/tmp/hermes-build/out ./build_hermes_venv.sh
#   CONTAINER_RUNTIME=docker ./build_hermes_venv.sh
#
# Output: $OUT/venv  (copy into the podroid Alpine rootfs)
# ============================================================================
set -euo pipefail

SRC="${SRC:-/home/alca/.hermes/hermes-agent}"
OUT="${OUT:-/tmp/hermes-build/out}"
ALPINE_VER="${ALPINE_VER:-3.23}"
RUNTIME="${CONTAINER_RUNTIME:-$(command -v podman || command -v docker)}"

[[ -n "$RUNTIME" ]] || { echo "no podman/docker found"; exit 1; }
[[ -d "$SRC" ]]      || { echo "SRC not found: $SRC"; exit 1; }
mkdir -p "$OUT"

echo "[build] runtime=$RUNTIME  src=$SRC  out=$OUT  alpine=$ALPINE_VER"
$RUNTIME run --rm --platform=linux/arm64 \
    -v "$SRC:/src:ro" -v "$OUT:/out" \
    "arm64v8/alpine:${ALPINE_VER}" sh -c '
        set -e
        apk add --no-cache python3 py3-pip build-base libgcc libstdc++ openssl \
                ca-certificates sqlite-libs libffi zlib
        python3 -m venv /out/venv
        /out/venv/bin/pip install --upgrade pip wheel setuptools
        /out/venv/bin/pip install /src[termux]
        /out/venv/bin/hermes --version
        echo BUILD_DONE
'
echo "[build] venv at $OUT/venv ($(du -sh "$OUT/venv" | cut -f1))"
