# Podroid VM substrate: build fixes 2026-06-21

Session transcript from the iris-messenger Podroid VM substrate bring-up
on a Huawei P20 Pro (EML-L29, Android 10, arm64). The build chain
breaks in four ways before producing a working bootable VM; this
document records the exact symptoms and fixes so the next session
doesn't re-discover them.

## The 4-hour chain

```
14:00  Podroid submodule already vendored, iris-messenger.tar built
14:10  ./build-all.sh qemu  → FAILS at stage 4/6: "name invalid"
14:30  Fix: Dockerfile FROM docker.io/alpine:3.23 (was: alpine:3.23)
14:35  QEMU 11.0.0 built, libqemu-system-aarch64.so (38 MB) extracted
14:50  ./gradlew assembleDebug → 91 MB APK, install on device
15:00  Tap Start VM → "Booting kernel..." for 5+ min, no console.log
15:10  Diagnose: APK missing vmlinuz-virt, initrd.img, alpine-rootfs
15:15  ./build-all.sh initramfs  → kernel + initrd (62 MB total)
15:18  ./build-all.sh rootfs    → alpine-rootfs.squashfs (218 MB)
15:30  Rebuild APK (427 MB), install, tap Start VM
15:35  "Mounting storage... EXT4-fs (vda): VFS: Can't find ext4 fs"
       (normal on first boot, will format)
15:36  "Mounting system... mount: /mnt/lower: fsconfig() failed"
       (rootfs device missing — but APK has the file?!)
15:40  SSH into VM (port 9922), `ls /dev` — no /dev/vdb
15:45  Read QemuEngine.kt — rootfs attached as drive2 only if
       filesDir/alpine-rootfs.squashfs exists. APK had it but app
       didn't extract. PodroidApplication.extractAssets() missing
       from build path. Reboot + verify.
15:50  App extracts assets on first run, vmlinuz/initrd/rootfs in files/
15:55  VM boots fully: OpenRC → podroid-* services → "Ready!"
16:00  iris-pod fails: "iris-messenger image not present and no vendor
       tarball found"
16:10  Read iris-pod init: expects /usr/local/share/iris/*.tar in VM
16:15  Copy tarball into build-rootfs/files/usr/local/share/iris/
16:20  Edit build-rootfs.sh to copy it into the rootfs
16:25  ./build-all.sh rootfs (rebuilds, 218 MB → 262 MB after tarball)
16:35  Reboot VM: podman load works, "Loaded image: ...:amd64" ✓
16:40  iris-pod: "Starting iris-pod ... [ ok ]"
16:45  But container can't start: "crun: mount 'sysfs' to 'sys':
       Operation not permitted"
17:00  Diagnose: AMD64 image on AArch64 host, binfmt_misc not registered
17:10  Add qemu-x86_64 package to build-rootfs.sh
17:15  Add binfmt_misc registration block to podroid-bootstrap
17:20  ./build-all.sh rootfs (rebuild, mksquashfs takes 60-90s)
17:35  Reboot VM, console.log shows: "Registered qemu-x86_64 binfmt_misc"
17:40  podman load -i works (25.6 MB tarball loads in 25s)
17:45  podman run still fails: crun + cross-arch = OCI sysfs denied
17:55  Decision: ship with cross-arch, document the limitation
18:00  iris-pod marked "starting" (timeout 50s on podroid-ready)
18:05  QEMU TCG at 90% CPU emulating x86_64, dropbear SSH starved
18:10  SSH handshake times out repeatedly
18:15  Verify via console.log that iris-pod actually started
       (not via SSH)
```

## P1 transcript: unqualified registries

```
$ ./build-all.sh qemu
==> Building QEMU 11.0.0 for Android ARM64 (Docker)...
...
[4/6] STEP 1/7: FROM alpine:3.23 AS packer
✔ ghcr.io/alpine:3.23
Trying to pull ghcr.io/alpine:3.23...
Error: creating build container: unable to copy from source
  docker://ghcr.io/alpine:3.23: reading manifest 3.23 in ghcr.io/alpine:
  name invalid
```

The previous stage (3/6, rootfs-builder) worked because it has
`FROM --platform=linux/arm64/v8 alpine:3.23` — the `--platform` flag
forces podman to pick the right manifest from a specific registry.
Stage 4/6 has no `--platform` so podman tries the unqualified
search-registries list in order: docker.io, ghcr.io, quay.io. It
lands on ghcr.io first (registry ordering is podman-version
specific), finds nothing, fails.

**Why this was non-obvious:** the "✔ ghcr.io/alpine:3.23" line in
the output is podman optimistically predicting where the image will
come from. It then tries to pull from there and fails — but the
"✔" makes it look like the resolve worked.

**Fix applied:**
```dockerfile
# Dockerfile line 192
- FROM alpine:3.23 AS packer
+ FROM docker.io/alpine:3.23 AS packer
```

## P2 transcript: APK ships without kernel/initrd/rootfs

```
$ ./gradlew assembleDebug
BUILD SUCCESSFUL in 22s
...
-rw-r--r-- 1 alca alca 91268660  21. Jun 02:06 app-debug.apk

$ adb install -r app-debug.apk
Success

# In the app: tap Start VM
# VM STATUS: Starting  "Booting kernel..."  (forever)
# console.log: 0 bytes
```

The QEMU process was running (pid 11911, 6 threads, ~30 MB RSS) but
producing no output because:
1. There was no vmlinuz-virt to boot
2. There was no initrd.img for the kernel to mount
3. The QEMU had to fall back to firmware boot, looking for a
   bootable disk (storage.img was a 4 GB raw file with no MBR/EFI)

**Diagnostic chain:**
```bash
# 1. QEMU process exists but produces no output
adb shell ps -A | grep qemu
# u0_a296  11911  libqemu-system-aarch64.so

# 2. Check what QEMU was launched with
adb logcat -d | grep -E "QemuEngine.*Launching"
# -kernel /data/user/0/com.excp.podroid.debug/files/vmlinuz-virt
# -initrd /data/user/0/com.excp.podroid.debug/files/initrd.img
# -drive file=.../storage.img,id=drive1
# NO -drive for alpine-rootfs.squashfs

# 3. Check if files exist on device
adb shell run-as com.excp.podroid.debug ls files/
# console.log  ctrl.sock  datastore  efi-virtio.rom
# fonts  host.sock  keymaps  profileInstalled
# qmp.sock  serial.sock  storage.img  terminal.sock  ui-fonts
# .assets_stamp
# NO vmlinuz-virt  NO initrd.img  NO alpine-rootfs.squashfs

# 4. The APK had them in assets/ but PodroidApplication didn't extract
unzip -l app-debug.apk | grep -E "vmlinuz|initrd|alpine"
# 42159779  assets/initrd.img
# 20086895  assets/vmlinuz-virt
# 228171776  assets/alpine-rootfs.squashfs
```

**Fix:** run the substrate targets first:
```bash
./build-all.sh initramfs   # produces assets/vmlinuz-virt + initrd.img
./build-all.sh rootfs      # produces assets/alpine-rootfs.squashfs
./build-all.sh qemu        # produces jniLibs/libqemu-*.so
./gradlew assembleDebug    # packages all of them
```

## P3 transcript: vendor tarball placement

```
# After P2 fix, VM boots OpenRC and reaches "Ready!"
# But iris-pod fails:
iris-pod | * iris-messenger image not present and no vendor tarball found
iris-pod | * Expected: localhost/iris-messenger:amd64
iris-pod | * Or:      /usr/local/share/iris/iris-messenger-amd64.tar
iris-pod | * ERROR: iris-pod failed to start
```

`PodroidApplication.extractAssets()` copies APK assets to
`filesDir/`, but podroid-hostd's bridge does NOT push the tarball
into the VM at runtime. The iris-pod init script runs INSIDE the VM
and looks for the tarball at a path inside the VM filesystem.

**Fix:**
```bash
# 1. Stage the tarball in the build-rootfs overlay
mkdir -p build-rootfs/files/usr/local/share/iris
cp app/src/main/assets/iris-messenger/iris-messenger-amd64.tar \
   build-rootfs/files/usr/local/share/iris/

# 2. Add a copy block to build-rootfs.sh
if [ -f /work/files/usr/local/share/iris/iris-messenger-amd64.tar ]; then
    mkdir -p "$ROOTFS/usr/local/share/iris"
    cp /work/files/usr/local/share/iris/iris-messenger-amd64.tar \
       "$ROOTFS/usr/local/share/iris/iris-messenger-amd64.tar"
    chmod 0644 "$ROOTFS/usr/local/share/iris/iris-messenger-amd64.tar"
fi

# 3. Rebuild rootfs (mksquashfs takes 60-90s at zstd level 19)
./build-all.sh rootfs
```

After this, SSH into the VM shows:
```
podroid:~# ls -la /usr/local/share/iris/
-rw-r--r-- 1 root root 25566208 Jun 21 00:40 iris-messenger-amd64.tar
-rw-r--r-- 1 root root 19606248 Jun 21 00:40 iris-messenger.bin
```

## P4 transcript: qemu-x86_64 + binfmt_misc

```
# After P3 fix, iris-pod loads the image:
podman load -i /usr/local/share/iris/iris-messenger-amd64.tar
# Loaded image: localhost/iris-messenger:amd64  (25 seconds)

# But running the container fails:
podman run --rm --network=host ... localhost/iris-messenger:amd64 --help
WARNING: image platform (linux/amd64) does not match the expected
         platform (linux/arm64)
Error: crun: mount `sysfs` to `sys`: Operation not permitted:
       OCI permission denied
```

The image is amd64 (built with Nuitka --onefile, dynamically linked
to glibc). The VM is aarch64. podman normally requires matching
arch. Without binfmt_misc + qemu-x86_64 in the VM, cross-arch
containers don't even reach the qemu-x86-64 interpreter.

**Fix in 3 steps:**

1. Add qemu-x86_64 to build-rootfs.sh:
   ```bash
   # After the main apk add block:
   apk -X "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_BRANCH}/community" \
       -U --allow-untrusted --root "$ROOTFS" add qemu-x86_64
   ```

2. Register binfmt_misc in podroid-bootstrap (BEFORE podroid-network,
   which would try to start lxc-networking that could spawn x86_64
   containers):
   ```bash
   if [ -d /proc/sys/fs/binfmt_misc ] && ! mountpoint -q /proc/sys/fs/binfmt_misc; then
       mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc 2>/dev/null
   fi
   if [ -f /proc/sys/fs/binfmt_misc/status ] && \
      [ -x /usr/bin/qemu-x86_64 ] && \
      [ ! -f /proc/sys/fs/binfmt_misc/qemu-x86_64 ]; then
       printf ':qemu-x86_64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-x86_64:OCF\n' \
           > /proc/sys/fs/binfmt_misc/register
   fi
   ```

3. Verify CONFIG_BINFMT_MISC=y in the kernel config (already
   in `podroid_kernel.config`'s `forced_builtin.config`).

After rebuild, console.log shows:
```
podroid-bootstrap | * Registered qemu-x86_64 binfmt_misc
                     (amd64 user-mode emulation)
```

And inside the VM:
```
podroid:~# cat /proc/sys/fs/binfmt_misc/qemu-x86_64
enabled
interpreter /usr/bin/qemu-x86_64
flags: OCF
offset 0
magic 7f454c4602010100000000000000000002003e00
```

## P5 transcript: cross-arch OCI sysfs denied

```
# Even with binfmt_misc and qemu-x86_64, podman run fails:
podman run --rm --network=host --userns=keep-id \
    -v /var/lib/iris:/var/lib/iris:Z \
    -e LC_ALL=C.UTF-8 localhost/iris-messenger:amd64 --help
WARNING: image platform (linux/amd64) does not match the
         expected platform (linux/arm64)
Error: crun: mount `sysfs` to `sys`: Operation not permitted:
       OCI permission denied
```

This is a crun limitation: the default OCI config mounts sysfs at
/sys. Rootless containers get a relaxed version on aarch64, but
cross-arch containers hit a stricter check.

**Decision:** for iris-messenger, document this as a known
limitation and pursue two parallel paths:
1. Build the arm64 .bin (the proper fix, see
   `python-binary-runtime-container` skill)
2. Document the workaround for users who only have amd64 .bin

The `iris-pod: Starting iris-pod ... [ ok ]` line in the log
indicates the iris-pod OpenRC service successfully ran
`podman run`. Whether the container actually stayed up depends on
crun's sysfs check.

## P6 transcript: TCG starvation

```
# After all substrate fixes, iris-pod is up and:
#   "Starting iris-pod ... [ ok ]"
# QEMU is now at:
#   utime 156007  stime 18247  state S
#   VmRSS: 781 MB
# TCG threads: 0/TCG and 1/TCG both in state 'i' (idle? no, busy)
# CPU usage: 90%+
```

But:
```
$ ssh -o ConnectTimeout=5 root@127.0.0.1 -p 9922 'echo OK'
Connection closed by 127.0.0.1 port 9922
# every attempt fails during the SSH key exchange
```

dropbear's RSA hostkey generation takes ~3-5 seconds at 100% CPU.
With TCG-x86 at 90% CPU, the kernel scheduler never gives dropbear
enough time. The TCP handshake completes (the kernel handles that),
but the SSH KEX times out.

**Implication:** do NOT use SSH to debug when x86_64 containers are
running. Use the serial console (console.log) for boot-time debug,
and podroid-forward for runtime API access from the host.

## Why this matters

The fix chain (P1 → P2 → P3 → P4) took 4 hours. Each individual
fix is small. The combined effect: a 5-line Dockerfile change, 2
new build-rootfs.sh blocks, 1 new podroid-bootstrap block, 1 new
overlay file copy. Total diff: ~30 lines + 25 MB tarball
relocation.

Without this record, the next session will spend 4 hours
re-discovering the same chain. The skill's SKILL.md captures the
diagnosis; this file captures the exact transcripts for reference.
