# Pitfalls encountered building a Python venv into an Alpine arm64 rootfs

## P1 — venv is NOT self-contained (the big one)
A `venv` only carries `site-packages` + console scripts; it symlinks
`bin/python3` -> the SYSTEM interpreter and needs `/usr/lib/python3.12`
(stdlib) + `/usr/lib/libpython3.12.so.1.0` (shared lib) from the rootfs.

- Symptom A (`--copies` build, venv injected, run in rootfs):
  `Error loading shared library libpython3.12.so.1.0: No such file or directory`
  -> the minimal rootfs has no libpython. Fix: ship it (but see B).
- Symptom B (after shipping libpython):
  `Could not find platform independent libraries <prefix>` /
  `ModuleNotFoundError: No module named 'encodings'` with `sys.prefix = '/usr'`
  -> the copied python looks for the stdlib at `/usr/lib/python3.12`, which the
  minimal rootfs lacks. Shipping libpython alone is insufficient.
- ROOT FIX: `apk add python3` INSIDE the rootfs so it has interpreter + stdlib
  + libpython. The venv sits on top at `/opt/hermes/venv`. `python3 -m venv
  --copies` does NOT help (Alpine's python3 has prefix `/usr` compiled in).

## P2 — shebang path hardcoding
Console scripts (hermes, hermes-agent, hermes-acp) embed the BUILD path in
their shebang: `#!/out/venv/bin/python3`. After copying the venv to
`/opt/hermes/venv` the shebang is wrong -> `sh: ...: not found` (kernel can't
find the interpreter at the old path).
Fix: build the venv at its FINAL deployment path (mount output so the venv
lands at `/opt/hermes/venv`, or create it directly at `/opt/hermes/venv` inside
the build container and `cp -a` it out). Then the shebang matches the rootfs.

## P3 — read-only source mount breaks pip
`pip install /src[termux]` with `/src:ro` fails:
`error: Cannot update time stamp of directory 'hermes_agent.egg-info'`
Fix: copy the source to a writable dir inside the container (`tar xzf /src.tgz
-C /build`) and install from there.

## P4 — verify must not shadow /usr/lib
Mounting collected runtime .so over the container's `/usr/lib`
(`-v /tmp/verify/usr/lib:/usr/lib:ro`) hides the container's stdlib and yields
`No module named 'encodings'`. Fix: verify via `chroot /r ...` so the rootfs's
own `/usr/lib` (with stdlib + libpython) is what Python sees.

## P5 — proot-chroot blocked on the phone
`proot -S alpine-rootfs ...` from `adb shell` (u:r:shell:s0) does NOT switch
root: you see the Android host fs, `/sbin/apk` and `/lib/ld-musl` are absent.
Cause: proot's chroot emulation needs ptrace, blocked by SELinux for the shell
context. It only worked via `adb shell run-as <debuggable-app>`. If that
context isn't reachable, pivot to host+qemu (podman + qemu-aarch64-static +
binfmt). On the host, `podman run --platform=linux/arm64 arm64v8/alpine:3.23
uname -m` must print `aarch64`.

## P6 — pick the right install extra
hermes-agent `[termux]` extra = Android-curated deps (telegram, cron, cli, pty,
mcp, honcho, acp) and EXCLUDES numpy/fastembed/onnxruntime. Use it; avoids the
musl onnxruntime wheel risk. Also note `requires-python = ">=3.11,<3.14"` — the
venv interpreter must be py3.12/3.13, never 3.14.
