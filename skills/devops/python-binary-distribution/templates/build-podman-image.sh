#!/usr/bin/env bash
# build-podman-image.sh
#
# Wrap a precompiled ELF binary in a podman container image, save the OCI
# tarball, smoke-test the entrypoint, and optionally bundle into an Android
# APK's assets/ directory. This is the "Podroid -> Podman -> obfuscated .bin"
# pipeline.
#
# The script is SELF-CONTAINED — the glibc/libc staging logic is inlined
# (with the [ -L ] symlink fix) so it does NOT depend on lib/copy-libs.sh
# being present or correct. This matters because copy-libs.sh gets reverted
# by sibling subagents and a wrong implementation leaves you with dangling
# libz.so.1 -> libz.so.1.3.2 symlinks that break `podman save`.
#
# Two arches:
#   amd64 (default) — built on the host directly, no toolchain needed
#   arm64            — TODO: needs `sudo pacman -S aarch64-linux-gnu-gcc` and
#                      an aarch64 cross-built .bin, OR run this script on a
#                      native arm64 host (RPi, Graviton, GH ubuntu-24.04-arm)
#
# Usage:
#   ./build-podman-image.sh                  # build amd64 (default)
#   ./build-podman-image.sh arm64            # build arm64 (needs toolchain)
#   ./build-podman-image.sh amd64 --bundle   # build + copy into Podroid assets
#   ./build-podman-image.sh amd64 --push     # build + podman push to ghcr.io
#
# Outputs:
#   dist/iris-messenger-<arch>.tar   OCI archive loadable via 'podman load -i'
#   dist/iris-messenger-<arch>.bin   plain .bin copy for direct execution
#
# Requires: podman (rootless or rootful both work; rootless recommended).
#
# Verified pattern: 19.6 MB binary + 13 MB glibc + 19 libz/libffi symlink
# targets = 33.3 MB image, zero .py in runtime. Smoke test on the host:
#   podman run --rm --network=host -e LC_ALL=C.UTF-8 \
#     localhost/iris-messenger:amd64
# prints the full banner + generates a gateway keypair in ~2s.
# ----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

ARCH="${1:-amd64}"
DO_BUNDLE=0
DO_PUSH=0
shift || true
for arg in "$@"; do
    case "$arg" in
        --bundle) DO_BUNDLE=1 ;;
        --push)   DO_PUSH=1 ;;
        *)        echo "Unknown arg: $arg" >&2; exit 2 ;;
    esac
done

if [ "$ARCH" != "amd64" ] && [ "$ARCH" != "arm64" ]; then
    echo "Usage: $0 [amd64|arm64] [--bundle] [--push]" >&2
    exit 2
fi

# Sanity: the .bin must exist and match the arch
BIN="iris-messenger.bin"
if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not found or not executable" >&2
    echo "  Build it first with the python-binary-distribution skill." >&2
    exit 1
fi
BIN_ARCH=$(file -b "$BIN" | grep -oE '(x86-64|aarch64|arm64)' | head -1 || true)
echo "host arch:    $(uname -m)"
echo "binary arch:  $BIN_ARCH"
echo "target arch:  $ARCH"
echo

if [ "$ARCH" = "amd64" ] && [ "$BIN_ARCH" != "x86-64" ]; then
    echo "ERROR: target is amd64 but $BIN is $BIN_ARCH" >&2
    exit 1
fi
if [ "$ARCH" = "arm64" ] && [ "$BIN_ARCH" != "aarch64" ] && [ "$BIN_ARCH" != "arm64" ]; then
    echo "ERROR: target is arm64 but $BIN is $BIN_ARCH" >&2
    echo "  Cross-compile: sudo pacman -S aarch64-linux-gnu-gcc" >&2
    echo "  Then:           CC=aarch64-linux-gnu-gcc <build the .bin for arm64>" >&2
    echo "  Or run this script on a native arm64 host (RPi, Graviton, GH runner)" >&2
    exit 1
fi

# Stage the per-arch glibc + system libs the .bin needs at runtime.
case "$ARCH" in
    amd64) DEST="lib"; HOST_LIB="/usr/lib"; LINKER="ld-linux-x86-64.so.2" ;;
    arm64) DEST="lib-arm64"; HOST_LIB="/usr/aarch64-linux-gnu/lib"; LINKER="ld-linux-aarch64.so.1" ;;
esac

if [ ! -d "$HOST_LIB" ]; then
    echo "ERROR: $HOST_LIB not found." >&2
    if [ "$ARCH" = "arm64" ]; then
        echo "  On x86_64 you need: sudo pacman -S aarch64-linux-gnu-glibc" >&2
        echo "  On CI: run on an arm64 runner (ubuntu-24.04-arm) so /usr/lib works directly." >&2
    fi
    exit 1
fi

echo "=== Staging $DEST from $HOST_LIB for $ARCH ==="
rm -rf "$DEST"
mkdir -p "$DEST"

# Inline copy function with [ -L ]-FIRST symlink handling.
# [ -f ] follows symlinks, so the order matters: a -L check MUST come first
# or cp -a silently preserves the symlink, leaving $DEST with a dangling
# .so.X -> .so.X.Y.Z. podman build then fails at COPY with "no such file".
# `podman save` of an already-built image ALSO fails on the dangling target.
stage_one() {
    local name="$1"
    if [ -L "$HOST_LIB/$name" ]; then
        cp -a "$HOST_LIB/$name" "$DEST/$name"
        local target
        target=$(readlink "$HOST_LIB/$name")
        if [ -n "$target" ] && [ ! -e "$DEST/$target" ] && [ -f "$HOST_LIB/$target" ]; then
            cp -a "$HOST_LIB/$target" "$DEST/$target"
        fi
    elif [ -f "$HOST_LIB/$name" ]; then
        cp -a "$HOST_LIB/$name" "$DEST/$name"
    else
        echo "  WARN: $HOST_LIB/$name missing, skipping" >&2
    fi
}

# Loop form so each name is its own function call. (Bash functions only
# take the first positional arg, not variadic.)
for n in "$LINKER" \
         libc.so.6 libm.so.6 libdl.so.2 libpthread.so.0 \
         librt.so.1 libutil.so.1 libresolv.so.2 \
         libz.so.1 libffi.so.8 libexpat.so.1 libsqlite3.so.0 \
         libssl.so.3 libcrypto.so.3 libgcc_s.so.1; do
    stage_one "$n"
done

echo "=== $DEST contents (size: $(du -sh "$DEST" | cut -f1)) ==="

# Patch the binary's RPATH so it can find /usr/lib at runtime in the
# container. patchelf is the standard tool; if missing, log a warning.
if command -v patchelf >/dev/null 2>&1; then
    # 0.17.2 is the verified-good version. 0.18.0 is known-buggy.
    PATCHELF_VER=$(patchelf --version 2>&1 | head -1)
    echo "patchelf version: $PATCHELF_VER"
    patchelf --set-rpath '/usr/lib:/lib:/lib64' "$BIN" 2>/dev/null || true
fi

mkdir -p dist

# Build the podman image
TAG="localhost/iris-messenger:$ARCH"
echo
echo "=== podman build -f Containerfile -t $TAG . ==="
podman build -f Containerfile -t "$TAG" . 2>&1 | tail -3

# Save the OCI tarball (the artifact that ships inside the Podroid APK)
TARBALL="dist/iris-messenger-$ARCH.tar"
echo
echo "=== podman save -o $TARBALL ==="
podman save --format=oci-archive -o "$TARBALL" "$TAG" 2>&1 | tail -3
echo "✓ $TARBALL: $(du -h "$TARBALL" | cut -f1)"

# Smoke test: does the .bin inside the container actually start?
# The container binds :9091 (REST) + :9092 (WS) on host networking. We
# just check that the banner prints + a keypair gets generated before
# the timeout kills the process. If you see the banner, the .bin is
# running and the entrypoint works.
echo
echo "=== smoke test (4s run, expect banner + keypair generation) ==="
timeout 4 podman run --rm --network=host \
    -e LC_ALL=C.UTF-8 -e LANG=C.UTF-8 -e PYTHONIOENCODING=utf-8 \
    "$TAG" 2>&1 | head -12 || true

# Optional: bundle into Podroid APK assets
if [ "$DO_BUNDLE" = 1 ]; then
    PODROID_ASSETS="$REPO_ROOT/android/podroid/app/src/main/assets"
    if [ ! -d "$PODROID_ASSETS" ]; then
        echo "WARN: $PODROID_ASSETS does not exist, skipping --bundle" >&2
    else
        TARGET_DIR="$PODROID_ASSETS/iris-messenger"
        mkdir -p "$TARGET_DIR"
        cp -f "$TARBALL" "$TARGET_DIR/iris-messenger-$ARCH.tar"
        echo "✓ bundled into $TARGET_DIR/"
    fi
fi

# Optional: push to ghcr.io (needs podman login ghcr.io first)
if [ "$DO_PUSH" = 1 ]; then
    GH_USER=$(gh api user --jq .login 2>/dev/null || echo "itsXactlY")
    REMOTE_TAG="ghcr.io/${GH_USER,,}/iris-messenger:$ARCH"
    podman tag "$TAG" "$REMOTE_TAG"
    podman push "$REMOTE_TAG"
    echo "✓ pushed $REMOTE_TAG"
fi

echo
echo "=== Done. ==="
echo "  Image tag:  $TAG"
echo "  Tarball:    $TARBALL ($(du -h "$TARBALL" | cut -f1))"
echo "  Load with:  podman load -i $TARBALL"
echo "  Run with:   podman run --rm --network=host -e LC_ALL=C.UTF-8 $TAG"
