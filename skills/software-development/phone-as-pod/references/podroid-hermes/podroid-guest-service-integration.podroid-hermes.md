# podroid-guest-service-integration.md

How to run hermes-agent **inside podroid's existing Alpine VM** as a guest
OpenRC service (the shipped "B + C" integration), instead of booting a
separate qemu VM from the hermes app.

This is the approach that actually SHIPPED and was verified (podroid
`app-debug.apk` = 498,853,299 bytes; `unsquashfs` of the APK's
`assets/alpine-rootfs.squashfs` confirms `etc/init.d/podroid-hermes`,
the runlevel symlink, `opt/hermes/start.sh`, and `opt/hermes/venv/bin/hermes`
are all present).

## Why this, not a separate VM
The standalone hermes app (dev.hermes.chat) tried to boot its OWN
qemu-system-aarch64 VM. That died on the Android SELinux exec wall: a
binary launched via Java `Runtime.exec()` from the app's `filesDir` gets
EACCES (errno 13) under the app context — only a `.so` in
`nativeLibraryDir`, exec'd by native code, is allowed. Fixing that needs
podroid's jniLib-launcher pattern, which is exactly what podroid already
uses to boot ITS VM. So: piggyback on podroid's already-running Alpine VM.
C (Pixel) is free — podroid's AvfEngine auto-selects pKVM/AVF on
Pixel-class Silicon; same guest, same :8088, same forward.

## Files to change (all in `jrwl-messenger/android/podroid`)
1. `build-rootfs/files/etc/init.d/podroid-hermes` — OpenRC service.
2. `build-rootfs/files/opt/hermes/start.sh` — proven launcher.
3. `build-rootfs/build-rootfs.sh` — seed `/opt/hermes` from a vendor
   tarball + install the service + add it to the runlevel symlink loop.
4. `app/src/main/java/com/excp/podroid/service/PodroidService.kt` — add a
   loopback-only `:8088` port forward.
5. `app/build.gradle.kts` — `aaptOptions { noCompress += listOf("squashfs","img") }`.

## 1. OpenRC service (mirrors iris-pod)
```sh
#!/sbin/openrc-run
name="podroid-hermes"
description="Hermes Agent gateway (native Python pod on Podroid)"
command="/opt/hermes/start.sh"
command_background="yes"
pidfile="/run/${name}.pid"
start_stop_daemon_args="--background --make-pidfile --pidfile ${pidfile}"
depend() {
    need net
    after podroid-network podroid-bootstrap
}
start_pre() {
    if [ ! -x /opt/hermes/start.sh ]; then
        eerror "hermes start.sh missing at /opt/hermes/start.sh — seed the venv first"
        return 1
    fi
    mkdir -p /opt/hermes/hermes-agent-data
}
```

## 2. start.sh (launcher — MUST end in `hermes gateway run`)
```sh
#!/bin/sh
export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-8088}"
export API_SERVER_CORS_ORIGINS="${API_SERVER_CORS_ORIGINS:-*}"
export API_SERVER_KEY="${API_SERVER_KEY:-071e4b225f562d036c646d992f231d8a960687a01bfaa80d1742e85f52a64e76}"
export HERMES_HOME="${HERMES_HOME:-/opt/hermes/hermes-agent-data}"
export PYTHONUNBUFFERED=1
mkdir -p "$HERMES_HOME"
# Optional upstream LLM (Wonderland relay): if HERMES_BASE_URL set, write
# ~/.hermes/config.yaml so the agent forwards completions to the real endpoint.
if [ -n "${HERMES_BASE_URL:-}" ]; then
    mkdir -p /root/.hermes
    cat > /root/.hermes/config.yaml <<YAML
default_model: ${HERMES_MODEL:-miniMax-m3}
profiles:
  default:
    base_url: ${HERMES_BASE_URL}
    api_key: ${HERMES_API_KEY:-sk-local}
YAML
fi
exec /opt/hermes/venv/bin/hermes gateway run
```

## 3. build-rootfs.sh wiring (mirror the iris-pod blocks)
Seed the venv from a vendor tarball (paths relative to `/`, so
`tar -C $ROOTFS -xf` drops it at `/opt/hermes`):
```sh
if [ -f /work/files/usr/local/share/hermes/hermes-podroid.tar ]; then
    mkdir -p "$ROOTFS/opt/hermes"
    tar -xf /work/files/usr/local/share/hermes/hermes-podroid.tar -C "$ROOTFS"
    chmod +x "$ROOTFS/opt/hermes/start.sh" 2>/dev/null || true
    chmod +x "$ROOTFS/opt/hermes/hermes-agent.bin" 2>/dev/null || true
fi
```
Install the service (next to the other `cp .../etc/init.d/podroid-*` lines):
```sh
if [ -f /work/files/etc/init.d/podroid-hermes ]; then
    cp /work/files/etc/init.d/podroid-hermes "$ROOTFS/etc/init.d/"
    chmod +x "$ROOTFS/etc/init.d/podroid-hermes"
fi
```
Add to the runlevel symlink loop (the `for svc in podroid-migrate ...` line):
append `podroid-hermes` to the service list.

Build the seed tarball once from a prebuilt venv root (`opt/hermes/...`):
```sh
tar -cf hermes-podroid.tar -C /path/to/kvm-rootfs opt/hermes
# place at build-rootfs/files/usr/local/share/hermes/hermes-podroid.tar
```

## 4. PodroidService.kt — :8088 loopback forward
Add the constant in the `companion object`:
```kotlin
// Hermes Agent gateway pod (B): host 127.0.0.1:8088 -> guest :8088.
const val HERMES_GATEWAY_PORT = 8088
```
Add the rule right after the IRIS_REST_PORT / IRIS_WS_PORT block:
```kotlin
if (rules.none { it.hostPort == HERMES_GATEWAY_PORT }) {
    rules.add(com.excp.podroid.data.repository.PortForwardRule(
        HERMES_GATEWAY_PORT, HERMES_GATEWAY_PORT, "tcp", loopbackOnly = true))
}
```
This makes the mazemaker app reach the local gateway at `127.0.0.1:8088`
without exposing it to the LAN (same trust model as the iris pod).

## 5. build.gradle.kts — noCompress for big binary assets
```kotlin
aaptOptions {
    noCompress += listOf("squashfs", "img")
}
```
Without this, AAPT2 re-deflate-compresses the already-gzip'd 390 MB
squashfs ("double compression") — burns minutes for zero size benefit and
looks like the build is "stuck on compress". NOTE: this is SEPARATE from
the `*.gz` auto-DECOMPRESS bug (see aapt2-gz-asset-gotcha.md) — the
squashfs is NOT `.gz`, so it is not silently decompressed; it is merely
redundantly re-compressed. `noCompress` stores it uncompressed.

## Build + verify (proven 2026-07-12)
```sh
# 1. rootfs squashfs (contains podroid-hermes + seeded /opt/hermes venv)
./build-all.sh rootfs          # -> app/src/main/assets/alpine-rootfs.squashfs

# 2. full APK (NDK libtermux + 390 MB squashfs asset)
export ANDROID_HOME=/home/alca/Android/Sdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
./gradlew :app:assembleDebug    # BUILD SUCCESSFUL, ~499 MB APK

# 3. prove hermes shipped INSIDE the APK's squashfs
APK=$(find app/build/outputs/apk/debug -name '*.apk' | head -1)
rm -rf /tmp/c && mkdir -p /tmp/c && unzip -o -q "$APK" assets/alpine-rootfs.squashfs -d /tmp/c
docker run --rm -v /tmp/c/assets/alpine-rootfs.squashfs:/d/sq alpine sh -c '
  apk add -q squashfs-tools; unsquashfs -l /d/sq | grep -E "podroid-hermes|opt/hermes"'
# expect: etc/init.d/podroid-hermes, etc/runlevels/default/podroid-hermes,
#         opt/hermes/start.sh, opt/hermes/venv/bin/hermes
```
(If `unsquashfs` is absent on the host, run the check inside a docker/podman
alpine container with `apk add squashfs-tools` — the host has no
unsquashfs binary.)

## Remaining (not done in the integration session)
- Physical deploy + boot on P20 (TCG) or Pixel (AVF) + `curl
  127.0.0.1:8088/health`. The hermes venv serving :8088 was already proven
  independently via chroot (`/health` → 200).
- Wire mazemaker-mobile (RN/Expo, dev.mazemaker.mobile) HermesScreen to hit
  `127.0.0.1:8088` when podroid is running — the "hermes native on unrooted
  phone, bundled with the mazemaker app" glue.
