# proot -S chroot blocked on Android from adb shell (SELinux/ptrace)

## Symptom
```
adb shell '/data/local/tmp/proot -S /data/local/tmp/alpine-rootfs -b /proc -b /dev sh -c "apk add ..."'
WARNING: linker: Warning: failed to find generated linker configuration from "/linkerconfig/ld.config.txt"
sh: apk: inaccessible or not found
```
Even with `export PATH=...:/sbin:/bin` set, `apk` stays "not found".

## Diagnosis (inside the proot shell)
```
id
# uid=0(root) gid=0(root) ... context=u:r:shell:s0   <-- still the Android shell context
ls -la /sbin/apk        # No such file or directory
ls -la /lib/ld-musl*    # No such file or directory
```
`/sbin/apk` and `/lib/ld-musl` are absent → proot -S did NOT switch root. We are
seeing the Android HOST filesystem, not the Alpine rootfs. The busybox `sh`
error message comes from the host's shell, not Alpine's.

## Root cause
proot's chroot emulation is built on `ptrace`. From the `adb shell` context
(`u:r:shell:s0`), SELinux denies ptrace, so proot -S silently no-ops the chroot
and execve runs host binaries. The `/linkerconfig/ld.config.txt` warning is
Android's linker loading a bionic binary.

## What did NOT fix it
- Adding `/sbin` to PATH (apk still absent — it's the host fs).
- Binding `-b /proc -b /dev`.
- Using the static arm64 proot from the podroid assets (it runs, ptrace is the block).

## Evidence from podroid history
The original podroid build only ever got proot to run via
`adb shell run-as dev.hermes.chat.debug` (the Hermes app's context, which has
ptrace permission). From plain `adb shell` it never worked.

## Resolution (used in this project)
Build the arm64 musl venv on the DESKTOP HOST instead, via
`podman run --platform=linux/arm64 arm64v8/alpine:3.23` — qemu-aarch64-static
is registered in binfmt_misc, so the arm64 container runs automatically under
emulation (`uname -m` → `aarch64`). pip install under qemu is fine; only
Nuitka-style AST-heavy compiles are too slow. See `scripts/build_hermes_venv.sh`.

## If a debuggable app IS present
`adb shell run-as <debuggable.pkg>` yields a ptrace-capable context where
`proot -S` works. Otherwise, host podman+qemu is the path.
