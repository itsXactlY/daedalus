# One-shot native rootfs build (host + qemu)

Reliable path when the phone's proot-chroot is blocked by SELinux (see
pitfalls.md). Requires on the x86_64 host: `podman` (or docker),
`qemu-aarch64-static`, and binfmt_misc registering qemu-aarch64.

## 0. Prep: a slim source tarball (avoids shipping .git / tests / ui-tui)
```
cd /home/alca/.hermes/hermes-agent
tar czf /tmp/hermes-agent-src.tgz \
  --exclude='.git' --exclude='venv' --exclude='.venv' --exclude='__pycache__' \
  --exclude='tests' --exclude='website' --exclude='ui-tui' --exclude='node_modules' \
  --exclude='*.pyc' --exclude='.mypy_cache' --exclude='.ruff_cache' .
```

## 1. Build script — `vm-image/build_rootfs_native.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO="${REPO:-/home/alca/projects/podroid-hermes}"
SRC_TGZ="${SRC_TGZ:-/tmp/hermes-agent-src.tgz}"
START="${START:-$REPO/vm-image/start_hermes_venv.sh}"
OUT="${OUT:-$REPO/android/hermes-android/app/src/main/assets/hermes-pod/rootfs.tar}"
[ -f "$SRC_TGZ" ] || { echo "SRC_TGZ missing: $SRC_TGZ"; exit 1; }
[ -f "$START" ]   || { echo "START missing: $START"; exit 1; }
echo "[build] podman alpine:3.23 arm64 (qemu) -> $OUT"
podman run --rm --platform=linux/arm64 \
  -v "$SRC_TGZ:/src.tgz:ro" \
  -v "$START:/start.sh:ro" \
  -v "$(dirname "$OUT"):/outdir" \
  arm64v8/alpine:3.23 sh -c '
    set -e
    apk add --no-cache python3 py3-pip libgcc libstdc++ openssl ca-certificates \
                      sqlite-libs libffi zlib bash tini
    mkdir -p /build && tar xzf /src.tgz -C /build
    python3 -m venv /opt/hermes/venv
    /opt/hermes/venv/bin/pip install --upgrade pip wheel setuptools
    /opt/hermes/venv/bin/pip install /build[termux]
    /opt/hermes/venv/bin/hermes --version
    cp /start.sh /opt/hermes/start.sh && chmod +x /opt/hermes/start.sh
    mkdir -p /opt/hermes/hermes-agent-data /root /tmp /var/log
    echo "root:x:0:0:root:/root:/bin/bash" > /etc/passwd
    echo "root:x:0:" > /etc/group
    echo "hermes-pod" > /etc/hostname
    echo "[build] packing rootfs.tar"
    cd /
    tar --exclude=./proc --exclude=./sys --exclude=./dev \
        --exclude=./build --exclude=./src.tgz --exclude=./outdir \
        -cf /outdir/rootfs.tar .
  '
echo "[build] wrote $OUT ($(stat -c %s "$OUT") bytes)"
```
Run: `bash vm-image/build_rootfs_native.sh` (background + notify; pip under
qemu takes a few minutes).

## 2. The launcher `vm-image/start_hermes_venv.sh` (mounted in as /start.sh)
Exports `API_SERVER_*` (gateway/config.py enables the OpenAI-compatible
api_server platform) and execs `/opt/hermes/venv/bin/hermes gateway`.
Optional `HERMES_BASE_URL/KEY/MODEL` env -> writes `~/.hermes/config.yaml`
for the upstream LLM (gateway-2 / Wonderland relay).

## 3. HARD verify (chroot, not bind-mount)
```
mkdir -p /tmp/verify && tar xf "$OUT" -C /tmp/verify
podman run --rm --platform=linux/arm64 -v /tmp/verify:/r arm64v8/alpine:3.23 \
  chroot /r /opt/hermes/venv/bin/hermes --version
podman run --rm --platform=linux/arm64 -v /tmp/verify:/r arm64v8/alpine:3.23 \
  chroot /r /opt/hermes/venv/bin/python -c "import psutil,cryptography,openai,hermes_cli,gateway;print('OK')"
```

## Phone-native alternative (when reachable)
If a ptrace-capable app context exists (`adb shell run-as dev.hermes.chat.debug`),
proot can chroot and you can build the same rootfs natively on the Pixel.
From the plain `adb shell` (u:r:shell:s0) proot `-S` silently fails to switch
root — verify by checking that `/sbin/apk` and `/lib/ld-musl` are visible
INSIDE the proot; if you instead see the Android host fs, SELinux blocked
ptrace and you must pivot to the host+qemu path above.
