# proot on unrooted Android — the App-internal Seccomp:2 SIGSYS wall

This is the SECOND, harder Android wall after the SELinux-EACCES wall
(binary in app `filesDir` can't be exec'd -> must live in `nativeLibraryDir`
as `lib*.so`). This one bites when the **app itself** spawns proot.

## Symptom
App launches proot (from `jniLibs`/`nativeLibraryDir`, so the EACCES wall is
already cleared) -> proot dies immediately with **exit code 159 = 128 + 31
(SIGSYS)**. Under `adb shell run-as dev.hermes.chat.debug` (Seccomp: 0) the
SAME proot + SAME flags boot the Alpine pod cleanly (banner + `/health` 200).

## Root cause
Android apps with targetSdk >= 26 run under a **seccomp filter**
(`/proc/$PID/status` -> `Seccomp: 2`, `CapEff: 0000000000000000`). proot needs
`ptrace` + memory I/O to emulate the chroot. Two syscall families get killed:
- `process_vm_readv` / `process_vm_writev` (proot's fast path for tracee memory)
- the `seccomp()` syscall itself, if proot tries to **install its own seccomp
  filter** ("ptrace acceleration, seccomp mode 2") — this one is the killer
  because it breaks path translation -> every `chdir`/`execve` inside the chroot
  returns `ENOENT` even though the files exist.

Confirm: `adb shell run-as dev.hermes.chat.debug sh -c 'cat /proc/<app_pid>/status'`
-> `Seccomp: 2`. Under plain `run-as` it's `Seccomp: 0`.

## RED HERRING: the Termux prebuilt proot
`https://packages.termux.dev/apt/termux-main/pool/main/p/proot/proot_*_aarch64.deb`
links and runs on the device, BUT it is built **with `HAVE_SECCOMP_FILTER`**, so
at startup it prints `ptrace acceleration (seccomp mode 2, new syscall order)
enabled` and installs a seccomp filter. Under the app that filter is either
blocked or broken on the device kernel -> `can't chdir(".../rootfs/./.") ... No
such file or directory` then `execve("/opt/hermes/start.sh"): No such file or
directory`. The files ARE there (proot even logs `granted execute start.sh`) —
the seccomp filter just mangles the syscall path. There is **no runtime flag**
to disable seccomp acceleration in Termux proot. Don't go down this path.

## FIX: build proot from source, pure ptrace (NDK / bionic)
Disable BOTH `process_vm` and `seccomp_filter` at build time -> proot falls back
to plain `ptrace` PEEKDATA/POKEDATA for memory and never calls `seccomp()`.
`ptrace` is allowed for app children (Termux-proot proves it). This survives
`Seccomp: 2`.

Build on the **host** with the Android NDK clang (cross to aarch64/bionic).
Do NOT use Alpine/musl to build — musl 1.2.6 removed `<sys/queue.h>` and has
header macro collisions with proot's `note.h` enum; you'll rabbit-hole.

### 1. Clone + patch the feature flags
```
cd /home/alca/projects/podroid-hermes/build
git clone --depth 1 https://github.com/proot-me/proot.git proot-src
# proot-src/src/GNUmakefile  line ~136:
#   CHECK_FEATURES = process_vm seccomp_filter
# change to:
CHECK_FEATURES =
# (empty -> build.h defines NEITHER HAVE_PROCESS_VM nor HAVE_SECCOMP_FILTER)
```

### 2. talloc + shm sysroot (Termux packages, host paths)
proot needs `talloc.h` + `<sys/shm.h>` at build time and `libtalloc.so.2` at
runtime. Get them from Termux (bionic-compatible):
```
pkg indexes: https://packages.termux.dev/apt/termux-main/dists/stable/main/binary-aarch64/Packages
talloc : pool/main/libt/libtalloc/libtalloc_2.4.3_aarch64.deb
shmem : pool/main/liba/libandroid-shmem/libandroid-shmem_0.7_aarch64.deb
```
For each: `ar x *.deb && tar -xf data.tar.xz`. Take
`usr/include/talloc.h`, `usr/include/sys/shm.h`, `usr/lib/libtalloc.so.2.4.3`,
`usr/lib/libandroid-shmem.so`. Assemble a sysroot:
```
SYS=/home/alca/projects/podroid-hermes/build/sysroot
mkdir -p $SYS/include/sys $SYS/lib/pkgconfig
cp .../talloc.h                 $SYS/include/
cp .../sys/shm.h                $SYS/include/sys/
cp .../libtalloc.so.2.4.3       $SYS/lib/libtalloc.so      # link name for build
cp .../libandroid-shmem.so      $SYS/lib/
cat > $SYS/lib/pkgconfig/talloc.pc <<'EOF'
prefix=$SYS
includedir=${prefix}/include
libdir=${prefix}/lib
Name: talloc
Version: 2.4.3
Cflags: -I${includedir}
Libs: -L${libdir} -ltalloc
EOF
```
IMPORTANT: `prefix=` MUST be the **absolute** sysroot path. A relative or
`/sysroot` placeholder makes `pkg-config` resolve the HOST talloc instead ->
`talloc.h file not found` even though the file exists.

### 3. bionic source fixes
- `cli/cli.c` uses `basename()` but bionic doesn't declare it via `<string.h>`
  (needs `<libgen.h>`). Add `#include <libgen.h>` near the top includes.
  (`loader/loader.c` defines its OWN static `basename` — leave it alone.)
- NDK clang treats `implicit-function-declaration` as a hard ERROR (C99+).
  proot is old-style C; compile with `CFLAGS=-std=gnu89` to permit it.
  (Don't reach for `-Wno-error=` — it isn't -Werror-driven; gnu89 is the lever.)

### 4. Build
```
cd proot-src/src
NDK=/home/alca/Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64
export PKG_CONFIG_PATH=$SYS/lib/pkgconfig
export CPPFLAGS="-I$SYS/include"      # pkg-config alone resolves HOST talloc
export LDFLAGS="-L$SYS/lib -Wl,--allow-shlib-undefined"
export CFLAGS="-std=gnu89"
make CROSS_COMPILE= \
  CC=$NDK/bin/aarch64-linux-android21-clang \
  STRIP=$NDK/bin/llvm-strip OBJCOPY=$NDK/bin/llvm-objcopy OBJDUMP=$NDK/bin/llvm-objdump \
  HAS_SWIG= HAS_PYTHON_CONFIG=
```
Gotchas baked into the flags above:
- `--allow-shlib-undefined`: lld default `--no-allow-shlib-undefined` rejects
  `libtalloc.so`'s libc symbol refs at LINK time (they resolve at runtime on the
  device). Without it -> `undefined reference: __register_atfork@LIBC` etc.
- `HAS_SWIG= HAS_PYTHON_CONFIG=`: the host has `python3-config`, so the
  Makefile otherwise adds the Python-extension objects (needs swig) -> unbuildable
  `.o` files -> link failure. Disable explicitly.
- `git describe` prints a harmless German `Keine Namen gefunden` warning (shallow
  clone, no tags). Ignore it.
- Verify the result: `readelf -d proot | grep NEEDED` -> `libtalloc.so.2`,
  `libdl.so`, `libc.so` (NO `libandroid-shmem.so` — this build doesn't link it).
  `grep -E "HAVE_PROCESS_VM|HAVE_SECCOMP_FILTER" build.h` -> MUST print nothing.

### 5. Package for the app (jniLibs)
Android only extracts `lib*.so` from `jniLibs/arm64-v8a/` — a file named
`libtalloc.so.2` is SKIPPED. Fix the NEEDED name + RUNPATH:
```
patchelf --replace-needed libtalloc.so.2 libtalloc.so proot
patchelf --set-rpath '$ORIGIN' proot
cp proot  android/.../app/src/main/jniLibs/arm64-v8a/libproot.so
# jniLibs MUST also contain the lib it needs, named libtalloc.so:
cp $SYS/lib/libtalloc.so  android/.../app/src/main/jniLibs/arm64-v8a/libtalloc.so
# libandroid-shmem.so is NOT needed by this build — drop it.
```
`$ORIGIN` (the executable's dir = nativeLibraryDir) lets proot find
`libtalloc.so` next to itself; the app's `LD_LIBRARY_PATH` set to
nativeLibraryDir is a harmless belt-and-suspenders. Rebuild the APK
(`./gradlew assembleDebug`), install, launch. proot now boots the pod under the
app's `Seccomp: 2` with no SIGSYS.

## Diagnostic one-liners
- app seccomp state: `adb shell run-as dev.hermes.chat.debug sh -c 'cat /proc/$(pidof ...)/status' | grep Seccomp`
- reproduce the app's exact proot under run-as (proven-good context) to isolate
  whether a failure is seccomp vs rootfs:
  ```
  PROOT=$(adb shell ... | grep libproot.so)   # the hashed /data/app/.../lib/arm64/libproot.so
  adb shell run-as dev.hermes.chat.debug "sh -c 'export PROOT_TMP_DIR=.../tmp; mkdir -p \$PROOT_TMP_DIR; $PROOT -v 1 --link2symlink --rootfs=/data/data/<pkg>/files/hermes-pod/rootfs --bind=/dev:/dev --bind=/proc:/proc --bind=/sys:/sys /bin/echo OK'"
  ```
  (Termux `-v` takes an integer: `-v 1`, space-separated.)
- If proot logs `granted execute start.sh` but then `execve(...): No such file
  or directory`, the script interpreter (`/bin/sh` -> `/bin/busybox`) or the
  chroot path translation is broken — NOT a missing file. Usually seccomp
  acceleration (use the pure-ptrace build above).
