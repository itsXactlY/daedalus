# podroid KVM pod architecture (post-proot pivot)

## Why this exists
proot is DEAD as the podroid runtime on the Pixel 7 Pro:
- proot spawned FROM the app dies `execve(): Bad address` (EFAULT) on every
  config — Android 16 kills proot's execve emulation in the app context
  (proven via `ptrace_test.c`: ptrace itself works, so the death is in proot's
  execve translation, not ptrace).
- The `adb shell run-as` path that worked for proot is not available for a
  production app.
User directive killed all bridge shortcuts ("podroid -> linux -> hermes. period.")
and qemu-user emulation. Pivot: a **real arm64 KVM virtual machine**.

## The VM (a real hypervisor, not an emulator)
`qemu-system-aarch64 -machine virt -cpu host -enable-kvm` boots an Alpine arm64
kernel + an initramfs RAM root that contains the hermes-agent venv. This is
native arm64 virtualization on the phone's Silicon — NOT qemu-user-static.

Artifact build (host, via `podman` + `qemu-aarch64-static`, binfmt registered):
1. Kernel: `podman run --platform=linux/arm64 arm64v8/alpine:3.23` then extract
   `/boot/vmlinuz-virt` -> `Image` (6.18.38-0-virt) + its modules. Must match the
   rootfs's musl/libc version.
2. RAM root: build the COMPLETE Alpine rootfs (see build_rootfs_native.sh skill
   section), add `Image`'s kernel modules, then `cd rootfs && find . | cpio -o
   -H newc | gzip -9 > initramfs.cpio.gz`. rootfs dir MUST be `chmod 755` or
   `cp`/init fails. Rename to `initramfs.cpio` for the APK (see aapt2 gotcha).
3. `/init` PID-1 wrapper: mounts `/proc /sys /dev`, exports `API_SERVER_*`,
   execs `/opt/hermes/start.sh` (which runs `hermes gateway run` on guest
   `0.0.0.0:8088`).
4. qemu musl bundle: extract `qemu-system-aarch64` (10.1.5) + its `lib/` from
   alpine arm64. **Dereference symlinks** (`cp -L`) — Alpine's
   `libc.musl.so` <-> `ld-musl` symlink loop breaks extraction otherwise.
   `patchelf --set-rpath '$ORIGIN/../lib'` so qemu finds its musl deps.
   Smoke test on host: `qemu-aarch64-static -L . ./lib/ld-musl-aarch64.so.1
   ./bin/qemu-system-aarch64 -version` -> "QEMU emulator version 10.1.5".

## App architecture (Kotlin)
- `HermesPodExtractor`: recursive `AssetManager` tree copy
  (`assets/hermes-pod/` -> `filesDir/hermes-pod/`), sets +x on
  `qemu/bin/qemu-system-aarch64` + `qemu/lib/ld-musl-aarch64.so.1`. No tar
  extractor (initramfs is a blob the guest kernel unpacks). Sentinel
  `.extracted-v2` for idempotency.
- `HermesPodSupervisor.launchQemu()`: builds the qemu cmdline
  (`-kernel Image -initrd initramfs.cpio -append "rdinit=/init console=ttyAMA0"
  -display none -serial file:vmserial.log -netdev
  user,id=n0,hostfwd=tcp::8088-:8088 -device virtio-net-device,netdev=n0`),
  `LD_LIBRARY_PATH=$qemuLibDir`, `Runtime.exec` from `qemuBin.parentFile`.
  Polls `/health` on `127.0.0.1:8088` (qemu user-net forwards guest 8088 -> host
  loopback 8088). State: `ExtractingAssets -> StartingVM -> WaitingGateway ->
  Ready`.
- `HermesPodService`: resolves `qemuBin/imageFile/initramfsFile/qemuLibDir` from
  `filesDir/hermes-pod/` and instantiates the Supervisor.

## The Android exec wall (still blocks DEPLOY, not BUILD)
Even though the code is complete:
- `Runtime.exec()` of ANY binary from `filesDir` (app_data_file) hits SELinux
  **EACCES** at forkAndExec on Android 10+. This is the same wall that killed
  proot-from-Java.
- `/dev/kvm` on the Pixel is **666 (world-open)** -> KVM itself needs NO root.
  The blocker is purely the SELinux exec restriction on spawning the qemu
  process.
- `unshare --user --map-root-user` -> "Invalid argument" (Android 16 gates
  userns) -> podman rootless is dead on the phone too.

## Deploy decision (OPEN — user has not chosen)
To actually run qemu on the unrooted Pixel 7 Pro (cheetah, serial
2B231FDH3005LL), one of:
1. **Root** (OEM unlock + Magisk, wipes the device) -> `Runtime.exec` works as-is.
   Robust, destructive.
2. **JNI exec helper** (fork()+execve() of qemu from `nativeLibraryDir`, the
   Termux approach) -> fragile, ~1-2 weeks of C++, and in-process qemu risks
   JVM signal conflicts (SIGSEGV/SIGBUS on KVM/MMIO).

BUILD is green (`assembleDebug` SUCCESSFUL, APK ~125 MB, initramfs byte-identical
to source). DEPLOY is gated on the root-vs-JNI choice. P20 is explicitly
out of scope (don't pollute it).

## build-all.sh
- `noCompress += listOf("hermes-pod/Image","hermes-pod/initramfs.cpio","hermes-pod/qemu")`
- `pod` target syncs from `vm-image/kvm/` (Image + initramfs.cpio + qemu/).
- `verify_assets` checks Image / initramfs.cpio / qemu/bin/qemu-system-aarch64.
- Removed 261 MB `rootfs.tar.bak` from assets (initramfs replaces the old
  proot rootfs). Removed dead `libproot.so` + proot deps from `jniLibs`.
