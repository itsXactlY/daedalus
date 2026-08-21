# Substrate B: proot + arm64 ELF

The lean alternative to substrate A (Podroid QEMU VM). The user
ships a single compiled aarch64 binary and runs it inside a
minimal Alpine arm64 rootfs via proot. Verified in the
podroid-hermes scaffold (2026-06-23).

## When to use substrate B

See `phone-as-pod` SKILL.md "Substrates: pick at design time" for
the full rubric. TL;DR: when the pod is **user-trusted** (Hermes
Agent on a phone you own, a personal dev tool, a self-hosted chat
client) AND you want a slim APK / fast cold start / no GPL cascade.

**Do NOT use** for untrusted code, multi-container workloads, or
when you need real kernel isolation. Substrate A (Podroid) is the
right call there.

## The runtime architecture

```
Android phone (arm64 Android 8+)
  hermes-android.apk
    |-- Kotlin HermesChatScreen        <-- UI talks to 127.0.0.1:8088
    |-- HermesPodService (foreground)  <-- owns pod lifecycle
    |     |-- HermesPodExtractor       <-- one-shot asset extraction
    |     +-- HermesPodSupervisor      <-- ProcessBuilder + child reaping
    |           |
    |           v
    |           proot --link2symlink --rootfs=... --bind=...
    |                 |
    |                 v
    |                 /opt/hermes/hermes-agent.bin
    |                       --gateway --host=0.0.0.0 --port=8088
    |
    v
    assets/hermes-pod/
      |-- proot                  (3 MB, statically linked)
      |-- rootfs.tar             (30 MB, Alpine arm64 minimal)
      +-- hermes-agent.bin       (25 MB, compiled aarch64 ELF)
```

`proot` (procfs-based chroot, ptrace-based fake-bind) does NOT
require root on Android. It walks the existing mounts and
**intercepts** syscalls via ptrace to redirect file accesses
into a fake rootfs. The process thinks it ran `chroot alpine-arm64
/opt/<svc>/<svc>.bin`; the kernel sees a regular Android process
running normally.

## The proot commandline (verified 2026-06-23)

```bash
proot \
    --link2symlink \
    --rootfs=/data/user/0/dev.hermes.chat.debug/files/hermes-pod/rootfs \
    --bind=/dev:/dev \
    --bind=/proc:/proc \
    --bind=/sys:/sys \
    /opt/hermes/hermes-agent.bin \
    --gateway --host=0.0.0.0 --port=8088
```

Why each flag is mandatory:

- `--link2symlink`: without this, proot fails to follow symlinks
  in /proc and /sys. Hermes-agent's gateway init will hang
  trying to read /proc/cpuinfo.
- `--rootfs=...`: the chroot-as-fake. proot intercepts `open()`
  and `stat()` and prepends the rootfs path. The process sees
  `/opt/hermes/hermes-agent.bin`; proot serves
  `/data/.../hermes-pod/rootfs/opt/hermes/hermes-agent.bin`.
- `--bind=/dev:/dev`: passthrough so the ELF can read kernel
  state. WITHOUT this, hermes-agent can't enumerate
  `/sys/class/net` and crashes on init with EACCES.
- `--bind=/proc:/proc`: passthrough for the same reason. The
  ELF needs `/proc/cpuinfo`, `/proc/meminfo`, etc.
- `--bind=/sys:/sys`: same, for `/sys/devices/...`.
- The ELF path `/opt/hermes/hermes-agent.bin` is what the
  process sees as its `$0`. proot resolves it to the
  host-side path inside the rootfs.

## The bundle layout (APK assets)

```
app/src/main/assets/hermes-pod/
|-- proot                  (~1 MB, statically linked, must be -static)
|-- rootfs.tar             (~25 MB, Alpine arm64 minimal userland
|                          with the binary already at
|                          /opt/hermes/hermes-agent.bin inside)
+-- (hermes-agent.bin MAY also be in assets separately, but the
    rootfs.tar MUST contain it at /opt/hermes/ for extraction
    to succeed)
```

After first launch, extracted to:
```
filesDir/hermes-pod/
|-- proot
|-- rootfs/
|   |-- bin/  sbin/  usr/  lib/  etc/
|   +-- opt/hermes/
|       |-- hermes-agent.bin
|       +-- hermes-agent-data/        (writable state)
+-- .extracted-v1                      (sentinel marker)
```

`hermes-agent-data/` is the writable persistent state dir
(sessions, conversation history, memory DB, etc.). It is
intentionally inside the rootfs so proot's chroot keeps the
ELF from escaping into the host's actual /opt. To persist
state across app data wipes, the foreground service can
back this up to /sdcard via Storage Access Framework on
user request.

## The build strategy (verified 2026-06-23)

**The build is cross-compile native, NOT QEMU emulation.** QEMU
emulation of the full hermes-agent under Nuitka takes 12+ minutes
for module discovery alone (verified 2026-06-23). The fast
path is to cross-compile a static arm64 binary directly.

**Best option (Go / Rust / Zig / C++):** static cross-compile,
<1 second for Go, a few minutes for C++.

```bash
# Go example — what the deployed podroid-hermes APK uses:
GOOS=linux GOARCH=arm64 CGO_ENABLED=0 \
    go build -ldflags="-s -w" -o hermes-agent.bin hermes.go
# Result: ~5.6 MB static aarch64 ELF, no runtime deps
```

**Python option (Nuitka, for when the service is Python-only):**
still requires --platform=linux/arm64 + qemu-aarch64 emulation
on x86 hosts, but 5-10 minutes for a SLIM entry point (not the
full hermes-agent). The `Containerfile.hermes-nuitka` does:

```dockerfile
# DO NOT ADD `--arch=arm64` — it is NOT a valid Nuitka flag.
# Nuitka picks the host arch automatically. Inside the
# --platform=linux/arm64 container, the host arch IS aarch64.
RUN /opt/hermes-venv/bin/python -m nuitka \
        --onefile --standalone \
        --include-package=cryptography \
        --include-module=_cffi_backend \
        --include-module=openai \
        --enable-plugin=anti-bloat \
        --remove-output \
        -o hermes-agent.bin gateway/run.py
```

**Critical Nuitka flags (DO NOT OMIT):**

- `--include-package=cryptography`: gateway_tls.setup_tls() runs
  unconditionally in Gateway.__init__. Without this flag, Nuitka
  doesn't bundle the cryptography package, the import is
  swallowed, and `_setup_tls` is undefined at runtime ->
  `NameError: name '_setup_tls' is not defined`.
- `--include-module=_cffi_backend`: `_cffi_backend` is a C
  extension imported by cryptography. Nuitka's static analysis
  misses the dynamic import path. Without this flag,
  `ImportError: No module named '_cffi_backend'`.
- `--enable-plugin=anti-bloat`: tells Nuitka to strip unused
  stdlib modules (test, unittest, distutils, etc.). Saves
  ~30 MB on the resulting binary.
- `--onefile --standalone`: bundle into a single ELF that
  embeds the Python interpreter + stdlib. The host (Android +
  proot) does NOT need Python installed.

## The asset extraction pattern

```kotlin
object HermesPodExtractor {
    private const val SENTINEL = ".extracted-v1"
    private const val MAGIC = "hermes-pod-extracted-v1"

    suspend fun ensureExtracted(context: Context): Result<File> =
        withContext(Dispatchers.IO) {
            val podRoot = File(context.filesDir, "hermes-pod").apply { mkdirs() }
            val sentinel = File(podRoot, SENTINEL)
            if (sentinel.exists() && sentinel.readText().trim() == MAGIC) {
                return@withContext Result.success(podRoot)
            }
            runCatching {
                podRoot.deleteRecursively()
                podRoot.mkdirs()

                // 1. Extract proot binary. setExecutable doesn't work
                //    reliably on files extracted from APK assets; use
                //    chmod via runtime.exec.
                val prootFile = File(podRoot, "proot")
                copyAsset(context.assets, "hermes-pod/proot", prootFile)
                Runtime.getRuntime().exec(arrayOf("chmod", "0755", prootFile.absolutePath))

                // 2. Extract + untar rootfs.
                val rootfsDir = File(podRoot, "rootfs").apply { mkdirs() }
                val rootfsTar = File(podRoot, "rootfs.tar")
                copyAsset(context.assets, "hermes-pod/rootfs.tar", rootfsTar)
                extractTar(rootfsTar, rootfsDir)
                rootfsTar.delete()

                // 3. hermes-agent.bin is already inside rootfs; chmod +x.
                val hermesBin = File(rootfsDir, "opt/hermes/hermes-agent.bin")
                if (!hermesBin.exists()) {
                    error("hermes-agent.bin missing from rootfs after extract")
                }
                Runtime.getRuntime().exec(arrayOf("chmod", "0755", hermesBin.absolutePath))

                // 4. Writable state dir.
                File(rootfsDir, "opt/hermes/hermes-agent-data")
                    .apply { mkdirs() }

                // 5. Sentinel - extraction complete.
                sentinel.writeText(MAGIC)
            }.fold(
                onSuccess = { Result.success(podRoot) },
                onFailure = { Result.failure(it) }
            )
        }
}
```

**Tar extractor typeflags (CRITICAL — minimal extractors
silently break the rootfs):**

The Alpine rootfs tar contains ~250 symlinks (`/bin/sh ->
/bin/busybox`, etc.). A minimal tar extractor that only
handles typeflag `0` (regular file) and `5` (directory) will
silently drop all symlinks, leaving the extracted rootfs with
no `/bin/sh`. proot will then fail with
`proot error: '/bin/sh' not found`.

The required typeflags:

- `'0'` (or `'\u0000'`): regular file — copy N bytes
- `'5'`: directory — mkdir
- `'2'`: symbolic link — create with `Files.createSymbolicLink`
  using the **linkname field at offset 157-256** (NOT 135).
  POSIX tar layout: name(100) + mode(8) + uid(8) + gid(8) +
  size(12) + mtime(12) + chksum(8) + typeflag(1) + **linkname(100)**
- `'L'`: GNU long name — read N bytes, then re-parse the next
  header. Optional.
- `'g'`: global pax header. Skip.

Most tar tutorials get the linkname offset wrong (cite 135
instead of 157). The mistake causes
`InvalidPathException: Nul character not allowed` when the
extractor reads chksum/mtime bytes as the linkname.

The sentinel marker (`filesDir/hermes-pod/.extracted-v1`) makes
extraction **idempotent across launches** AND **survives app
updates** (assets are re-read on first launch after update, but
the sentinel on `filesDir` persists, so extraction is skipped).

To force re-extraction when the bundled rootfs changes (e.g. you
ship a new rootfs.tar in an app update), bump the sentinel
magic string: `-v1` -> `-v2`.

## The proot Supervisor (foreground service -> ProcessBuilder)

```kotlin
private fun launchProot(): Process? {
    val cmd = arrayOf(
        prootBin.absolutePath,
        "--link2symlink",
        "--rootfs=${rootfsDir.absolutePath}",
        "--bind=/dev:/dev",
        "--bind=/proc:/proc",
        "--bind=/sys:/sys",
        "/opt/hermes/start.sh"  // wrapper that sets env then execs hermes-agent.bin
    )
    return try {
        // Runtime.exec goes through the same UNIXProcess.forkAndExec as
        // ProcessBuilder.start; both are blocked by Android 10+ SELinux
        // on app_data_file context. See "Hard lessons" below.
        Runtime.getRuntime().exec(cmd, null, rootfsDir)
    } catch (e: Exception) {
        Log.e(TAG, "ProcessBuilder.start failed", e)
        null
    }
}

private suspend fun waitForGatewayReady(): Boolean {
    val deadline = System.currentTimeMillis() + 90_000
    val client = HermesGatewayClient("http://127.0.0.1:8088")
    while (System.currentTimeMillis() < deadline && running.get()) {
        try {
            if (client.healthCheck()) return true
        } catch (_: Exception) { /* keep polling */ }
        delay(750)
    }
    return false
}
```

**Cold-start budget: 5-10s.** If `127.0.0.1:8088/api/health`
doesn't return 200 within 90s, surface
`HermesPodState.Failed("hermes-agent did not become ready
within 90s", recoverable = true)` and let the user retry. The
90s window covers the worst case (slow phone + first-launch
extraction + proot fork+exec + ELF imports + libssl init).

## Gradle config (APK side)

`app/build.gradle.kts`:

```kotlin
android {
    namespace = "dev.hermes.chat"
    defaultConfig {
        // arm64 only - proot + hermes-agent ELF are arm64-v8a
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    androidResources {
        // don't compress the pod assets; the OS reads them straight
        // from the APK as a memory-mapped file, saving 5-10s on
        // first-launch extraction
        noCompress += listOf(
            "hermes-pod/bin",
            "hermes-pod/proot",
            "hermes-pod/rootfs.tar"
        )
    }
    packaging {
        jniLibs { useLegacyPackaging = true }
    }
}
```

`AndroidManifest.xml`:

```xml
<uses-feature android:name="android.hardware.cpu.arm64"
              android:required="true" />

<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.WAKE_LOCK" />

<application
    android:name=".HermesChatApplication"
    ...>
    <activity android:name=".MainActivity" .../>
    <service android:name=".pod.HermesPodService"
             android:exported="false"
             android:foregroundServiceType="dataSync" />
</application>
```

Two manifest gotchas that silently break first launch (verified
2026-06-23):

1. `<application android:name=".HermesChatApplication">` MUST be
   declared, otherwise the
   `(application as HermesChatApplication)` cast in MainActivity
   throws `ClassCastException: android.app.Application cannot
   be cast to dev.hermes.chat.HermesChatApplication`.

2. `<service android:name=".pod.HermesPodService">` needs the
   FULL package path relative to the manifest's `package`
   attribute. `.HermesPodService` resolves to
   `dev.hermes.chat.HermesPodService` (the manifest package);
   if the class is in a sub-package like `dev.hermes.chat.pod`,
   use `.pod.HermesPodService`. Otherwise `ActivityManager:
   Unable to start service ... not found`.

`res/xml/network_security_config.xml`:

```xml
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

The hermes-agent gateway binds 0.0.0.0:8088 *inside the proot
namespace*. proot's ptrace-based fake-bind exposes this on the
host loopback at 127.0.0.1:8088. HermesGatewayClient hits
127.0.0.1:8088 directly - no LAN exposure, no INTERNET
permission required for the gateway hop.

## Build pipeline (orchestrator: vm-image/hermes-pod-build.sh)

```
x86_64 host (Garuda)
   |
   |  qemu-user-static + binfmt_misc (NOT required for static
   |  cross-compile of Go/Rust/Zig; only required for Nuitka
   |  builds on x86_64 hosts)
   |  Arch: systemctl enable systemd-binfmt (NOT update-binfmts)
   |
   +-> stage A: build the aarch64 ELF
   |     OPTION 1: cross-compile Go/Rust/Zig natively
   |       GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build ...
   |       <1 second, no QEMU
   |     OPTION 2: Nuitka under qemu-aarch64
   |       podman build --platform=linux/arm64 -f Containerfile.hermes-nuitka
   |         -> debian:bookworm arm64 (qemu-aarch64 emulated, 5-10x slower)
   |           -> pip install deps into a venv
   |           -> python -m nuitka --onefile --standalone
   |              --include-package=cryptography --include-module=_cffi_backend
   |         -> strip --strip-all hermes-agent.bin
   |       -> ~25 MB aarch64 ELF (slim entry; full hermes-agent too slow)
   |
   +-> stage B: build the minimal Alpine rootfs
   |     podman run --rm --platform=linux/arm64 alpine:3.23
   |       -> apk add bash openssl sqlite-libs libstdc++ tini
   |       -> tar -cf rootfs.tar .
   |       -> ~25 MB Alpine arm64 userland
   |     CRITICAL: inject hermes-agent.bin INTO the rootfs at
   |     /opt/hermes/ BEFORE tarring (or extraction will fail
   |     with "hermes-agent.bin missing from rootfs after extract")
   |
   +-> stage C: build static proot (build from source, not fetch)
   |     proot-me/proot GitHub releases no longer attach arm64 binaries
   |     Alpine's apk-add proot is musl-linked (won't run on bionic)
   |     Containerfile:
   |       FROM --platform=linux/arm64/v8 debian:bookworm
   |       RUN apt-get install -y build-essential autoconf automake \
   |               libtool pkg-config libarchive-dev libtalloc-dev file
   |       COPY . /build/proot
   |       # NB: proot uses plain `make -j4` from src/, NO autogen.sh
   |       RUN cd src && LDFLAGS="-static -s" make -j4 proot GIT=false
   |     -> ~1 MB static aarch64 ELF, no runtime deps
   |
   +-> stage D: bundle into dist/hermes-agent-arm64.tar
         tar -cf dist/hermes-agent-arm64.tar {proot, hermes-agent.bin, rootfs.tar}
```

Total: ~55 MB tarball, all native aarch64.

## End-to-end build & deploy

```bash
# 1. Build the arm pod
cd vm-image
./hermes-pod-build.sh           # ~30-60 min via qemu-aarch64 emulation
# -> dist/hermes-agent-arm64.tar

# 2. Populate APK assets
cp dist/hermes-agent-arm64.tar android/hermes-android/app/src/main/assets/
cd android/hermes-android/app/src/main/assets
mkdir -p hermes-pod && tar -xf hermes-agent-arm64.tar -C hermes-pod

# 3. Build the APK
cd android
./build-all.sh                  # ~2 min, uses cached gradle
# -> hermes-android/app/build/outputs/apk/debug/app-debug.apk

# 4. Install + launch
DEV="<your-adb-serial>"
adb -s $DEV install -r hermes-android/app/build/outputs/apk/debug/app-debug.apk
adb -s $DEV shell am start -n dev.hermes.chat.debug/dev.hermes.chat.MainActivity

# 5. Watch logs
adb -s $DEV logcat -s HermesPodSupervisor:V HermesPodService:V \
                        hermes-pod-stdout:V hermes-pod-stderr:V
```

## Diagnosing issues

### Pod never reaches READY

```bash
adb -s $DEV logcat -s HermesPodSupervisor:V
```

Common errors and fixes:

- `proot: error: failed to exec: No such file or directory` ->
  rootfs didn't extract. Wipe `filesDir/hermes-pod/` and retry.
- `proot: cannot start new ptrace tracee` -> another instance
  is already running. `adb shell run-as <pkg> ps -A | grep
  proot` to confirm; if so, kill it.
- `error while loading shared libraries: libcrypt.so.1` -> rootfs
  is missing a lib. Rebuild the rootfs in stage B; double-check
  `apk add` includes `openssl` and the ELF's actual deps.
- `OSError: [Errno 2] No such file or directory: '/proc/cpuinfo'`
  -> forgot `--bind=/proc:/proc` in the proot commandline. Fix
  in HermesPodSupervisor.
- `proot error: '/bin/sh' not found` -> tar extractor dropped
  symlinks. Add the `'2'` (symlink) typeflag case to the
  extractor; linkname field is at offset 157, not 135.

### Gateway returns 200 but no chat response

```bash
# Check hermes-agent is actually serving, not crashing on the
# first message:
adb -s $DEV logcat -s hermes-pod-stdout:V hermes-pod-stderr:V
```

If you see `hermes-agent` stack traces on stderr, the gateway
init succeeded but the chat path is broken. The most common
cause is missing API keys - hermes-agent reads
`HERMES_API_KEY` from env or `~/.hermes/.env` on first chat.
Inject these via a config overlay in the rootfs (step 2 in
the build) or expose a settings UI in the Compose app.

## Migration path to substrate A

If a project starts on substrate B and needs to graduate to
substrate A (e.g. to add a second container, or to harden the
threat model):

1. Add `vm-image/Dockerfile.podroid` (lift the one from
   iris-messenger).
2. Replace `assets/hermes-pod/` with `assets/podroid/` (the
   existing iris-messenger layout).
3. Add `assets/hermes-agent-arm64.tar` to the Podroid rootfs
   (so podman inside the VM can `podman load -i` it).
4. Replace `HermesPodSupervisor` with a PodroidEngine wrapper
   that waits for `BootStageDetector.Ready` and runs
   `podroid-forward add 8088 8088 tcp`.

The Hermes Chat UI stays the same - only the substrate changes.

## Hard lessons from first deploy (podroid-hermes 2026-06-23)

These were not in the original design and broke the first build
end-to-end. Capture them before they bite the next person.

### Android 10+ SELinux blocks exec from app_data_file

**THE runtime blocker on unrooted Android 10+. Verified on
Huawei P20 Pro (EML-L29, Android 10).**

```kotlin
// ProcessBuilder(cmd).start() OR Runtime.exec(cmd)
java.io.IOException: Cannot run program "..."
  error=13, Permission denied
  at java.lang.UNIXProcess.forkAndExec(Native Method)
```

The proot binary IS +x (`-rwxr-xr-x`), the path IS valid, the
SELinux context IS `app_data_file`. The kernel still refuses
because Android 10+ SELinux policy (`neverallow untrusted_app
exec_file`) blocks any exec from `app_data_file` context. The
same block that forced Termux/Andronix to ship their own
app_process fork.

This is a HARD kernel-level block. Runtime.exec and
ProcessBuilder both go through `UNIXProcess.forkAndExec` which
performs the SELinux check. Neither bypasses it.

**Workarounds (in order of effort):**

1. **Root the phone** (`adb root` then `adb shell` can launch
   proot directly). Fastest path if the device is yours.
2. **`adb shell run-as <pkg> /data/.../proot ...`** — works
   without root because run-as impersonates the app user but
   bypasses the SELinux check via the `runas` domain. Useful
   for smoke-testing on non-rooted devices.
3. **Reimplement proot in a JNI .so library** — ship
   `lib/arm64-v8a/libhermes_pod.so` containing the ptrace logic
   in C, `System.loadLibrary("hermes_pod")` from HermesPodService,
   call a `Java_dev_hermes_chat_pod_HermesPodService_nativeStart()`
   to fork+exec. The `lib/arm64-v8a/` dir is on the SELinux
   whitelist for exec. **This is the production answer for
   non-rooted devices.** 1-2 weeks of C work to port proot.
4. **MANAGE_EXTERNAL_STORAGE + Termux-style app_process
   trick** — heaviest lift, requires user to grant the
   permission. Not recommended.

**Document this constraint up front** in the project README.
The current podroid-hermes scaffold does NOT solve it. The
deployed APK works on rooted devices or via `adb shell
run-as`; it does NOT work on a stock non-rooted Android 10+
phone despite the binary being +x.

### QEMU is too slow for the full hermes-agent Nuitka build

**Verified 2026-06-23.** Building hermes-agent's full
`gateway/run.py` (the entire CLI + plugins + tools + acp_adapter
+ tui_gateway) under qemu-aarch64 emulation took 12+ minutes
of module discovery with no end in sight. Building the
slimmer `gateway/platforms/api_server.py` entry took 5+
minutes for the same reason.

The reason: hermes-agent is a HUGE codebase (gateway + cli +
plugins + tools + scripts). Nuitka does heavy AST analysis
on every reachable module. Under qemu emulation each arm64
instruction is interpreted on the x86 host at ~5-20x slower
than native.

**Pivots that work:**

- **Go static cross-compile: <1 second.** Write the
  service in Go (or Rust, or Zig), `GOOS=linux GOARCH=arm64
  CGO_ENABLED=0 go build -o svc.bin svc.go`, ship a 5-6 MB
  static aarch64 ELF. No QEMU needed at all. This is what
  the deployed podroid-hermes APK actually uses (the
  `hermes-placeholder.go` is the production placeholder
  until the real hermes-agent ELF is built natively on
  arm64 hardware).
- **C/C++ cross-compile with aarch64-linux-gnu-gcc: a few
  minutes.** `aarch64-linux-gnu-gcc -static` produces a
  static aarch64 binary directly. No QEMU.
- **Nuitka slim (api_server.py only): 5+ min under QEMU.**
  Acceptable for one-off builds. Do NOT attempt the full
  hermes-agent build under QEMU; use a native arm64 runner
  (github ubuntu-24.04-arm is free for public repos).

**The lesson:** if the service is written in Python, write
a Go/Rust/Zig shim for the build pipeline and cross-compile
natively. Reserve QEMU emulation for one-off slim entry points
or for host packages that are already arm64.

### proot static build: build from source, do not fetch

**Verified 2026-06-23.** The proot-me/proot GitHub releases
page has no attached binaries for arm64 (the URLs in earlier
docs all return 404). Alpine's `apk add proot` ships a
binary dynamically linked against `ld-musl-aarch64.so.1`
which is NOT present on Android bionic — running it on
Android gives `Could not open '/lib/ld-musl-aarch64.so.1':
No such file or directory`.

**The recipe (works):**

```dockerfile
# Pre-clone on the HOST (TLS cert in qemu container was
# broken — fatal: server certificate verification failed).
# Then bind-mount the source into the container.
git clone --depth 1 https://github.com/proot-me/proot.git
# Build a tiny Dockerfile that just COPYs + makes:
FROM --platform=linux/arm64/v8 debian:bookworm
RUN apt-get install -y build-essential autoconf automake \
        libtool pkg-config libarchive-dev libtalloc-dev file
COPY . /build/proot
WORKDIR /build/proot
# NB: proot-me/proot uses plain `make -j4` from src/. NO
# autogen.sh, NO configure. The CI does `make -C src proot`.
# With LDFLAGS="-static -s" for a fully static stripped binary.
RUN cd src && LDFLAGS="-static -s" make -j4 proot GIT=false
```

The result: ~936 KB fully static aarch64 ELF, dynamically
links to NOTHING, runs on Android bionic without any musl
loader.

## Related references

- `phone-as-pod` SKILL.md - the umbrella skill; this
  reference is its substrate-B appendix.
- `podroid-vm-substrate-build` SKILL.md - substrate A internals,
  the 6 failure modes to be aware of if you ever cross
  substrates.
- `python-binary-runtime-container` SKILL.md - the Nuitka
  multi-arch Containerfile pattern that produces the .bin
  in the first place.
