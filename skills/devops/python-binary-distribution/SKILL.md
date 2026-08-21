---
name: python-binary-distribution
description: |
  Ship a Python application as a single-file distributable binary (Nuitka --onefile),
  optionally packaged in a FROM scratch container with zero source code in the image.
  Triggers: "compile to single binary", "make this distributable as a single file",
  "FROM scratch container with python", "no source in container", "nukita file",
  "share this as one binary". Covers the full pipeline: build (Nuitka + patchelf +
  venv), container (FROM scratch + glibc lib copy at the right path), runtime
  (locale, DATA_DIR override, onefile extract behavior), and verification.
  Verified pattern: 19.6 MB binary + 13 MB glibc = 33 MB image, zero .py in runtime.
version: 1.0.0
tags: [nuitka, onefile, scratch-container, binary-distribution, glibc, alca-stack]
triggers:
  - "compile python to single file binary"
  - "Nuitka --onefile build"
  - "FROM scratch container with python app"
  - "share this as one binary / nukita file"
  - "no source in runtime container"
  - "ship python app as single distributable"
metadata:
  hermes:
    category: devops
---

# Python → Single-File Binary Distribution

## WHEN TO USE

Trigger this skill when:
- The operator wants to ship a Python app as a single distributable file
  (`scp app.bin user@host && ./app.bin`) — no Python on target required
- A container must contain ZERO Python source / no `.py` files
- "Nukita" pattern (German for "the small one") — shareable single artifact
- The project would benefit from FROM scratch containers for security/size

The pattern was proven on the iris-messenger migration (2026-06-20):
- gateway.py + 4 deps (websockets, pycryptodome, pyyaml, requests) → 19.6 MB ELF
- FROM scratch + 13 MB of glibc libs → 33.3 MB image
- Zero `.py` in the runtime container. The binary IS the runtime.

## CORE PIPELINE (in order)

### Phase 1: BUILD the binary

#### 1a. Isolated build venv (PEP 668 protection)

The system Python on the operator's Garuda is read-only (PEP 668). Never
`pip install --user --break-system-packages`. Always build in a venv.

```bash
python3 -m venv /tmp/iris-build-venv
/tmp/iris-build-venv/bin/pip install --quiet --upgrade pip
/tmp/iris-build-venv/bin/pip install --quiet \
    nuitka ordered-set \
    <runtime-deps: websockets pycryptodome pyyaml requests ...>
```

`ordered-set` is required by Nuitka. Forgetting it gives a confusing error.

#### 1b. patchelf — version matters

Nuitka on Linux REQUIRES `patchelf` for `--onefile` and `--standalone`.

CRITICAL VERSION GOTCHA:
- ❌ **0.18.0 is BUGGY per Nuitka** — fails with "known buggy release and cannot be used"
- ✅ **0.17.2 works** (verified)
- ✅ **0.19.0+ likely works** (test before committing)

Install WITHOUT sudo (binary download):
```bash
curl -fsSL "https://github.com/NixOS/patchelf/releases/download/0.17.2/patchelf-0.17.2-x86_64.tar.gz" \
    -o /tmp/pe.tar.gz
mkdir -p /tmp/pe-extract && tar xzf /tmp/pe.tar.gz -C /tmp/pe-extract
cp /tmp/pe-extract/bin/patchelf ~/.local/bin/patchelf
chmod +x ~/.local/bin/patchelf
export PATH=$HOME/.local/bin:$PATH
~/.local/bin/patchelf --version  # expect: patchelf 0.17.2
```

Verify Nuitka can find it: `which patchelf` after the PATH export. If Nuitka
still says "patchelf not found", your subprocess didn't inherit the PATH —
invoke Nuitka with `env PATH=$HOME/.local/bin:$PATH ...`.

#### 1c. The actual Nuitka invocation

```bash
/tmp/iris-build-venv/bin/python -m nuitka \
    --onefile \
    --output-filename=app.bin \
    --include-package=<package1,package2,...> \
    --remove-output \
    --assume-yes-for-downloads \
    main.py
```

Key flags:
- `--onefile` — single distributable binary (vs `--standalone` which is a folder)
- `--include-package=<list>` — force-include transitive deps Nuitka can't statically detect (cryptography, websockets, anything with C extensions)
- `--remove-output` — clean up `main.build/`, `main.dist/` after success
- `--assume-yes-for-downloads` — auto-downloads things like `ccache`, `clang-format` if Nuitka thinks they're needed

Build time: 5-15 min for a medium Python project (~5 modules, 1k LOC).
Output size: ~20 MB for a typical web service with crypto + WebSocket.

#### 1d. Verify the binary

Three checks before moving on:

1. **Type**: `file app.bin` → expect `ELF 64-bit LSB pie executable, x86-64`
2. **Help text**: `timeout 3 ./app.bin --help` → expect help output + correct brand string
3. **Smoke run**: `./app.bin --no-network-flag` and grep for `[OK]` / banner text

### Phase 2: CONTAINERIZE (FROM scratch + binary + glibc)

#### 2a. The Containerfile template

See `templates/Containerfile.scratch-binary` for the full template. The core shape:

```dockerfile
FROM scratch

# Dynamic linker + glibc (required: binary is dynamically linked to libc)
COPY lib/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2

# glibc search path on Arch/Garuda is /usr/lib ONLY — see Pitfall #2
COPY lib/libc.so.6         /usr/lib/libc.so.6
COPY lib/libm.so.6         /usr/lib/libm.so.6
COPY lib/libdl.so.2        /usr/lib/libdl.so.2
COPY lib/libpthread.so.0   /usr/lib/libpthread.so.0
COPY lib/librt.so.1        /usr/lib/librt.so.1
COPY lib/libutil.so.1      /usr/lib/libutil.so.1
COPY lib/libresolv.so.2    /usr/lib/libresolv.so.2

# Python stdlib pulls these in transitively
COPY lib/libz.so.1         /usr/lib/libz.so.1
COPY lib/libssl.so.3       /usr/lib/libssl.so.3
COPY lib/libcrypto.so.3    /usr/lib/libcrypto.so.3
COPY lib/libffi.so.8       /usr/lib/libffi.so.8
COPY lib/libexpat.so.1     /usr/lib/libexpat.so.1
COPY lib/libsqlite3.so.0   /usr/lib/libsqlite3.so.0
COPY lib/libgcc_s.so.1     /usr/lib/libgcc_s.so.1

# The binary
COPY app.bin /usr/local/bin/app

# Default config (operators bind-mount over this in prod)
COPY runtime.env /etc/app/runtime.env

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/app"]
CMD ["--help"]
```

#### 2b. Build the `lib/` directory

Pull the glibc libs from the host filesystem into `lib/`. Use `find` with the
`.so` pattern — don't trust `ldd` alone (it misses transitive deps).

**CRITICAL gotcha (iris-messenger 2026-06-20):** the loop below is BROKEN
on distros where the lib is a symlink. Arch/Garuda: libz, libffi, libexpat,
libsqlite3 are all symlinks to a versioned `.so.X.Y.Z`. If you do
`cp -P "$src" lib/...` only, you copy the symlink without the target, and
`podman build` at the COPY step fails with "no such file or directory".

**Fix:** use `cp -L` (follow symlinks, copy target as a regular file) AND
also copy the versioned target. OR use the corrected `lib/copy-libs.sh`
template from `python-binary-runtime-container` which has `[ -L ]`-first
handling.

The minimum fix for the loop:

```bash
mkdir -p lib
for lib in ld-linux-x86-64.so.2 libc.so.6 libm.so.6 libdl.so.2 \
           libpthread.so.0 librt.so.1 libutil.so.1 libresolv.so.2 \
           libz.so.1 libssl.so.3 libcrypto.so.3 libffi.so.8 \
           libexpat.so.1 libsqlite3.so.0 libgcc_s.so.1; do
    src=$(find /usr/lib /usr/lib64 -name "${lib}*" -not -path '*/lib32/*' 2>/dev/null \
          | head -1)
    if [ -n "$src" ]; then
        # cp -L follows symlinks and copies the target as a regular file.
        # Then ALSO copy the versioned target if the source was a symlink.
        cp -L "$src" "lib/$(basename $src)" 2>/dev/null
        if [ -L "$src" ]; then
            real=$(readlink -f "$src")
            [ "$real" != "$src" ] && [ -f "$real" ] && cp "$real" "lib/$(basename $real)"
        fi
    fi
done
```

The list above is sufficient for a typical Python web service. If your binary
needs more (e.g. `libgssapi_krb5.so.2` for kerberos auth), add it and document
why. See `references/glibc-libs-for-scratch-container.md` for the reasoning.

#### 2c. Build and run

The full one-shot pipeline (stage libs + build image + save tarball
+ smoke test + optional --bundle into Podroid APK assets + optional
--push to ghcr.io) is in `templates/build-podman-image.sh`. It is
self-contained — the glibc/libc staging is inlined with the `[ -L ]`
symlink fix, so the script does NOT depend on a separate
`lib/copy-libs.sh` that might be reverted by a sibling subagent.

```bash
podman build -f Containerfile -t localhost/app:latest .
podman run --rm --entrypoint=/usr/local/bin/app localhost/app:latest --help
```

Image size target: 30-40 MB for a typical Python web service.
If your image is >100 MB, you probably copied too many libs (or accidentally
COPYed the wrong files).

To package the image as an OCI tarball for distribution (e.g. bundle
into an Android APK's `assets/` directory for the phone-as-pod
pattern):

```bash
podman save --format=oci-archive -o dist/app-amd64.tar localhost/app:latest
# Smoke test: confirm the .bin inside the container actually starts
# (banner + keypair generated = runtime is real, not a broken stub).
timeout 4 podman run --rm --network=host \
    -e LC_ALL=C.UTF-8 -e LANG=C.UTF-8 -e PYTHONIOENCODING=utf-8 \
    localhost/app:latest 2>&1 | head -12
```

Both steps are wrapped in `templates/build-podman-image.sh` so the
next time you ship the same pattern you don't re-derive the smoke
test or the bundle command.

### Phase 3: RUNTIME hardening

#### 3a. Locale — Unicode banners crash on ASCII default

Any Python binary that prints Unicode (box-drawing chars ╔═╗, em-dashes,
emoji) crashes with `UnicodeEncodeError: 'ascii' codec` in FROM scratch
containers. The default locale there is POSIX/C, not C.UTF-8.

Set in your systemd unit / quadlet / container:
```
Environment=LC_ALL=C.UTF-8
Environment=LANG=C.UTF-8
Environment=PYTHONIOENCODING=utf-8
```

Alternative fix (cleaner, requires rebuild): `sys.stdout.reconfigure(encoding='utf-8')`
at app startup. But the env-var approach is one-line and avoids rebuild.

#### 3b. Data directory — host AND container compatibility

If the app writes to a config-driven path (e.g. `~/.appname/`), make the path
configurable via env var with a sensible default for each environment:

```python
DATA_DIR = Path(os.environ.get('APP_DATA_DIR', Path.home() / '.appname'))
```

Then in the container:
- Container mount: `Volume=%h/.appname/data:/var/lib/app:z`
- Default in Containerfile `ENV`: keep `APP_DATA_DIR=/var/lib/app`
- Operator override: bind-mount `%h/.appname/data` and set `APP_DATA_DIR=/var/lib/app`

This lets the same binary run standalone (uses `~/.appname`) and in a
container (uses `/var/lib/app`) without recompilation.

#### 3c. Onefile extract behavior

`--onefile` binaries extract themselves to `/tmp/onefile_<pid>_<rand>/` on
first run. This means:
- `find /tmp/onefile_*` works for live debugging (you can read the extracted
  Python source — for non-protective uses, this is fine)
- `/tmp` must be writable and have disk space (~binary size × 2)
- The extracted copy is cached — first run is slower than subsequent runs

## PITFALLS

### Pitfall #1: COPY libc to /lib — silently fails at runtime

The first instinct is `COPY lib/libc.so.6 /lib/libc.so.6` (Debian/Ubuntu
habit). On Arch/Garuda this fails silently — the build succeeds, the image
contains the file, but the container exits immediately with:

```
/usr/local/bin/app: error while loading shared libraries: libc.so.6: cannot open shared object file
```

**Verify with `LD_DEBUG=libs` inside the container:**
```bash
podman run --rm -e LD_DEBUG=libs localhost/app:latest --help 2>&1 | head -15
```

Look for the "search path=" line. On Arch/Garuda you'll see:
```
search path=/usr/lib/glibc-hwcaps/x86-64-v3:/usr/lib/glibc-hwcaps/x86-64-v2:/usr/lib
```

NOT `/lib` and NOT `/lib64`. Copy everything to `/usr/lib`.

### Pitfall #2: patchelf 0.18.0 silently breaks the build

Build succeeds but the resulting binary won't link. Error:
```
FATAL: Error, patchelf version 0.18.0 is a known buggy release and cannot be used.
```

Pin to 0.17.2 via the GitHub release tarball. Don't trust `pacman -S patchelf`
on Garuda — the version in repos may be 0.18.0 too. Verify with
`patchelf --version` before the build.

### Pitfall #3: Missing transitive deps after libc.so.6 is found

After fixing the libc path, the next error is usually `libm.so.6: cannot open`.
Then `libz.so.1`. Then `libssl.so.3`. Iterate the cycle:

```bash
podman run --rm localhost/app:latest --help 2>&1 | head -5
# Output: error while loading shared libraries: libm.so.6
# Fix: cp /usr/lib/libm.so.6 lib/ + add COPY to Containerfile
# Rebuild + retest
```

Each iteration is ~30 sec. Budget for 3-5 iterations on first build.

### Pitfall #4: Container exits "successfully" but did nothing

`podman run --rm localhost/app:latest` returns immediately with exit code 0
but produces no logs. This usually means:
- The binary crashed at startup (locale issue — see 3a)
- The binary extracted to /tmp successfully but then died
- The ENTRYPOINT/CMD arguments are wrong

**Debug:** `podman run --rm --entrypoint=/usr/local/bin/app localhost/app:latest --help`
forces a known-good command and shows the actual error.

### Pitfall #5: --break-system-packages in PEP 668 land

On Arch/Garuda (and Debian 12+, Ubuntu 23.04+), `pip install` outside a venv
fails with PEP 668 protection. NEVER use `--break-system-packages`. Always venv.

If you accidentally polluted the system Python, `pacman -S --overwrite '*' python-pip`
won't fix it — you have to manually remove the offending packages.

### Pitfall #6: lib/ directory committed to git

The `lib/` directory contains host-specific glibc binaries. NEVER commit it.
Gitignore immediately:
```
# .gitignore
lib/
lib32/
*.bin
gateway.build/
gateway.dist/
gateway.onefile-build/
```

### Pitfall #7: Symlink libs end up dangling (cp -P preserves symlinks)

Same family as Pitfall #1 and #3. `cp -P` is the POSIX-correct way to copy
a symlink, but if you do ONLY that, `$DEST/libz.so.1 -> libz.so.1.3.2` exists
without `libz.so.1.3.2` next to it. `podman build` dereferences at COPY
time and fails. Either `cp -L` (follow) or copy both the symlink AND its
`readlink` target. See the corrected `lib/copy-libs.sh` in
`python-binary-runtime-container` for the canonical fix.

## VERIFICATION

After every build, before claiming "it works":

- [ ] Binary runs standalone: `./app.bin --help` exits 0
- [ ] Binary self-identifies: banner / version string shows correct brand
- [ ] Image builds: `podman build` exits 0
- [ ] Image size: 25-50 MB (not 200+ MB — too many libs)
- [ ] Container runs: `podman run --rm ... --help` exits 0
- [ ] Zero `.py` in image: `podman save <img> -o /tmp/x.tar && tar tf /tmp/x.tar | grep '\.py$' | wc -l` → 0
- [ ] Container serves traffic: `curl http://localhost:port/api/health` returns 200
- [ ] Locale set: `LC_ALL=C.UTF-8` in the systemd unit / quadlet
- [ ] DATA_DIR override works: `APP_DATA_DIR=/tmp/test ./app.bin` writes to /tmp/test
- [ ] gitignored: `lib/`, `*.bin`, build dirs not in `git status`

## STEPS (summary)

1. Build venv: `python3 -m venv /tmp/build-venv`
2. Install patchelf 0.17.2 (download binary, no sudo)
3. Install Nuitka + ordered-set + runtime deps in venv
4. Run Nuitka --onefile with `--include-package` for transitive deps
5. Verify binary standalone (--help, smoke run)
6. Build `lib/` directory from host glibc (use `find` with .so pattern)
7. Write Containerfile using `templates/Containerfile.scratch-binary`
8. Build container, iterate on missing libs (3-5 rounds typical)
9. Set locale env vars in systemd unit / quadlet
10. Add DATA_DIR env var override to source code (rebuild if needed)
11. Verify with the checklist above
12. Gitignore `lib/`, `*.bin`, build dirs
13. Commit — message should explain the nukita pattern + size wins

## RELATED

- `references/glibc-libs-for-scratch-container.md` — exact libs list with
  per-library justification (what needs what)
- `templates/Containerfile.scratch-binary` — copy-paste starter Containerfile
- `templates/build-podman-image.sh` — one-shot build pipeline:
  stage glibc + system libs (with `[ -L ]`-first symlink fix INLINE so
  it does not depend on a separate `lib/copy-libs.sh`), build the
  podman image, save the OCI tarball, smoke-test, optionally
  `--bundle` into a Podroid APK's `assets/` directory, optionally
  `--push` to ghcr.io. Use this when shipping the binary for
  embedding in another artifact (Android APK, multi-arch image set,
  etc.) — not for local development where `podman build` alone suffices.
- `scripts/find-missing-libs.sh` — automated lib discovery from container errors
- `templates/runtime.env.sample` — minimal runtime env file to ship
- `phone-as-pod` — downstream consumer of the OCI tarball. Embeds
  the image in a Podroid APK's `assets/` so the app boots the
  binary inside an Android-side VM with one install step.

## MULTI-ARCH BUILDS (amd64 + arm64) — merged from python-binary-runtime-container (2026-08-09)

The single-arch pattern above produces an x86_64 binary. For arm64
(phone-as-pod Android deployment, Apple Silicon, Graviton, RPi) you
need a multi-arch build pipeline. Verified on iris-messenger
2026-06-20 (Podroid VM is arm64-only).

### When to use multi-arch
- Same single-file binary must run on x86_64 AND arm64
- Container image must work on both arches (FROM scratch + per-arch glibc)
- Phone-as-pod pattern (see `phone-as-pod` skill) — backend runs in an
  Android VM which is arm64-only

### Step 1 — single Containerfile with TARGETARCH
```dockerfile
FROM scratch
ARG TARGETARCH=amd64

# amd64 glibc + system libs (Arch/Garuda /usr/lib layout)
COPY lib/ld-linux-x86-64.so.2     /lib64/ld-linux-x86-64.so.2
COPY lib/libc.so.6                 /usr/lib/libc.so.6
COPY lib/libssl.so.3               /usr/lib/libssl.so.3

# arm64 glibc + system libs (Alpine/glibc aarch64 layout)
COPY lib-arm64/ld-linux-aarch64.so.1   /lib/ld-linux-aarch64.so.1
COPY lib-arm64/libc.so.6               /usr/lib/libc.so.6
COPY lib-arm64/libssl.so.3             /usr/lib/libssl.so.3

COPY myapp-${TARGETARCH}.bin /usr/local/bin/myapp
ENTRYPOINT ["/usr/local/bin/myapp"]
```
```bash
podman build --arch=amd64 --build-arg TARGETARCH=amd64 -t myapp:amd64 .
podman build --arch=arm64 --build-arg TARGETARCH=arm64 -t myapp:arm64 .
```

### Step 2 — lib/copy-libs.sh per-arch staging (SYMLINK GOTCHA)
CRITICAL gotcha (iris-messenger 2026-06-20): the naive loop
`for f in libz.so.1 ...; do cp -a "$HOST_LIB/$f" "$DEST/$f"; done`
BREAKS on distros where the lib is a symlink (Arch/Garuda: libz,
libffi, libexpat, libsqlite3 are ALL symlinks to versioned .so.X.Y.Z).
Result: `$DEST/libz.so.1 -> libz.so.1.3.2` with NO target file, then
`podman build` fails at COPY: "copier: stat: '/lib/libz.so.1.3.2': no
such file or directory". Two causes: `[ -f ]` FOLLOWS symlinks (returns
TRUE), and `cp -a` PRESERVES the symlink (-a includes -d). Fix:
check `[ -L ]` FIRST, copy symlink AND target:
```bash
copy_if_present() {
  local name="$1"
  if [ -L "$HOST_LIB/$name" ]; then
    cp -a "$HOST_LIB/$name" "$DEST/$name"
    local target; target=$(readlink "$HOST_LIB/$name")
    if [ -n "$target" ] && [ ! -e "$DEST/$target" ] && [ -f "$HOST_LIB/$target" ]; then
      cp -a "$HOST_LIB/$target" "$DEST/$target"
    fi
  elif [ -f "$HOST_LIB/$name" ]; then
    cp -a "$HOST_LIB/$name" "$DEST/$name"
  else
    echo "WARN: $HOST_LIB/$name missing, skipping" >&2
  fi
}
```
Idempotent (rm -rf destination first). Safe to re-run.

### Step 3 — CI matrix on NATIVE arm64 runner (NO qemu-user, NO cross-compile)
GitHub-hosted `ubuntu-24.04-arm` is free for public repos and runs
NATIVE aarch64. Matrix include: `{arch: amd64, runner: ubuntu-latest,
platform: linux/amd64, binary_name: myapp-amd64.bin, lib_dir: lib}`
and `{arch: arm64, runner: ubuntu-24.04-arm, platform: linux/arm64,
binary_name: myapp-arm64.bin, lib_dir: lib-arm64}`. Build Nuitka with
`CC: ${{ matrix.arch == 'arm64' && 'aarch64-linux-gnu-gcc' || 'gcc' }}`,
stage libs with `bash lib/copy-libs.sh ${{ matrix.arch }}`, then
build-push-action with `platforms: ${{ matrix.platform }}` and
`build-args: TARGETARCH=${{ matrix.arch }}`. arm64 job finishes in
~6 min natively.

### Pitfall — lib/ .gitignore conflict
If top-level `.gitignore` has `lib/` (runtime glibc staging dir), any
SCRIPT inside lib/ is silently gitignored — `git add lib/copy-libs.sh`
fails with NO error. Fix: `git add -f`, or rename to scripts/ and
adjust paths. Defensive pattern for sibling agents: inline the
symlink-aware copy logic INTO the driver script (build-podman-image.sh)
so the pipeline is self-contained.

### Pitfall — distroless vs scratch
`gcr.io/distroless/base-debian12` handles multi-arch via manifest list
automatically but loses the ~30MB size advantage. Phone-as-pod's
80-120MB APK constraint favors FROM scratch + per-arch glibc. Stay on
scratch unless you need a shell in the container.

### Portability rule
Nuitka --onefile produces host-arch binaries. An amd64 binary will NOT
run on arm64. Never ship one binary for both — the COPY path picks per
TARGETARCH. The OCI manifest list can combine them later.

### When to skip multi-arch
- Service deploys only to x86_64 servers (no phone/ARM/Apple Silicon)
- CLI tool users build themselves on their host (no container)
- phone-as-pod pattern not in scope
