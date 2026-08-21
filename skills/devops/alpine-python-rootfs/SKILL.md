---
name: alpine-python-rootfs
description: Build/port a Python application as a native venv into a minimal Alpine Linux (musl) arm64 rootfs for Android/podroid/embedded deployment. Covers the venv-relocation traps (a venv is NOT self-contained — it needs system python3 + stdlib + libpython INSIDE the rootfs), proot/SELinux build blockers on the phone, shebang-path hardcoding, read-only source mount failures, and the reliable host+qemu cross-build path. Use when the user wants a Python app (e.g. daedalus-agent) to actually RUN inside a minimal Alpine arm64 image that boots on a device via proot or a VM.
---

# Build a Python venv into an Alpine (musl) arm64 rootfs

## When to use
You need a Python app to actually RUN inside a minimal Alpine arm64 rootfs that
boots on a phone/embedded device via proot or a VM (podroid). This is NOT
"pip install in a container" — the artifact must be a self-contained rootfs.tar
(or squashfs) that carries its own interpreter + deps and launches with no
network/pip at boot.

## The architecture that works (do NOT skip python3 in the rootfs)
A Python `venv` is a thin layer: it symlinks `bin/python3` -> the SYSTEM
interpreter and carries only `site-packages` + console scripts. It does NOT
contain the stdlib or `libpython`. So the rootfs MUST `apk add python3` (giving
`/usr/bin/python3.12`, `/usr/lib/python3.12` stdlib, and
`/usr/lib/libpython3.12.so.1.0`), and the venv lives on top at e.g.
`/opt/hermes/venv`. The venv's `hermes` script shebangs
`#!/opt/hermes/venv/bin/python3` -> symlink -> `/usr/bin/python3.12` (which
exists in the rootfs). Fully self-contained at runtime.

`python3 -m venv --copies` does NOT fix the relocation problem: Alpine's
python3 has its prefix (`/usr`) compiled in, so the copied binary still believes
prefix=`/usr` and looks for the stdlib at `/usr/lib/python3.12` — which a
minimal rootfs lacks. Shipping `libpython3.12.so.1.0` alone is not enough; the
stdlib dir is also required. **Install python3 in the rootfs; don't try to make
the venv standalone.**

## Build host
- Native arm64 (Pixel 7 Pro etc.) is fastest, BUT `proot -S` chroot emulation
  needs ptrace, which SELinux blocks from the `adb shell` (u:r:shell:s0)
  context. proot only ever worked via `adb shell run-as <debuggable-app>` (app
  context with ptrace). If no such context is reachable, proot-chroot on the
  phone is a dead end — pivot to the host.
- Reliable fallback: the x86_64 host with `podman`/`docker` +
  `qemu-aarch64-static` + binfmt_misc (registers qemu-aarch64).
  `podman run --platform=linux/arm64 arm64v8/alpine:3.23 uname -m` prints
  `aarch64`. pip installs under qemu are wheel-downloads + light compile — fine
  (only Nuitka's AST analysis is too slow under qemu). See
  references/build_rootfs_native.md.

## Pitfalls (all hit in practice — see references/pitfalls.md)
1. **Read-only source mount**: `pip install /src[extra]` with `/src:ro` fails —
   "Cannot update time stamp of directory 'hermes_agent.egg-info'". Copy the
   source to a writable dir inside the container first.
2. **Shebang path hardcoding**: console-script shebangs embed the BUILD path
   (`#!/out/venv/bin/python3`). Build the venv at its FINAL deployment path
   (e.g. `/opt/hermes/venv`) so the shebang matches the rootfs, or the launched
   binary errors "not found".
3. **Don't shadow /usr/lib during verify**: mounting collected runtime .so over
   `/usr/lib` hides the container's stdlib and breaks Python
   ("No module named 'encodings'"). Verify via `chroot /r ...`, not bind-mounts.
4. **Pick the right install extra**: hermes-agent ships a `[termux]` extra — the
   Android-curated subset (telegram, cron, cli, pty, mcp, honcho, acp) that
   deliberately EXCLUDES numpy/fastembed/onnxruntime. Use it; it removes the
   musl onnxruntime wheel risk entirely.

## Verification (HARD, not just "it built")
Extract the artifact and `chroot` into it on the host under qemu:
```
mkdir -p /tmp/verify && tar xf rootfs.tar -C /tmp/verify
podman run --rm --platform=linux/arm64 -v /tmp/verify:/r arm64v8/alpine:3.23 \
  chroot /r /opt/hermes/venv/bin/hermes --version
podman run --rm --platform=linux/arm64 -v /tmp/verify:/r arm64v8/alpine:3.23 \
  chroot /r /opt/hermes/venv/bin/python -c "import psutil,cryptography,openai,hermes_cli,gateway;print('OK')"
```
chroot makes the venv's `/usr/bin/python3.12` resolve to the rootfs's own
interpreter — a true end-to-end check that stdlib + libpython + venv are coherent.

## References
- references/build_rootfs_native.md — full one-shot build script (host+qemu) +
  slim-source-tarball prep + proot-on-phone note.
- references/pitfalls.md — expanded debugging notes with exact error strings.
