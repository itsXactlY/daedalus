# phone-as-pod — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Substrates: pick at design time

Two runtime substrates are interchangeable. Pick the one that
matches your threat model, APK-size budget, and cold-start budget.

| | **(A) QEMU VM** (Podroid) | **(B) proot + native ELF** |
|---|---|---|
| Isolation | Real kernel-level VM (Pegasus-grade by design) | ptrace-based fake-chroot; NOT a sandbox |
| APK size | 80-407 MB (kernel + QEMU + rootfs + podman + OCI) | 50-100 MB (proot + rootfs.tar + ELF) |
| Cold start | 35-90s on QEMU TCG, 1-3s on AVF/pKVM (Pixel only) | 5-10s on any arm64 Android |
| Steady-state RAM | 512 MB QEMU guest | ~120 MB native process |
| Multi-container | Yes (podman inside the VM) | No (single ELF per APK) |
| Build env | arm64 host OR qemu-user-static + binfmt_misc (same for both) | same |
| License cascade | Podroid GPL-2.0 + service license (combined work = GPL-2.0) | proot GPL-2.0 (binary only, not linked into Kotlin) |
| Threat model | Service is **untrusted code** OR **high-stakes data** | Service is **user-trusted**; no jailbreak-grade threat |
| Verified on | iris-messenger 2026-06-21 (Huawei P20 Pro) | podroid-hermes 2026-06-23 (scaffold) |

### Decision rubric

Pick **(A) QEMU VM** when ANY of these hold:

- The pod runs untrusted or partially-trusted code (downloaded
  skills, third-party plugins, federated remote code)
- The threat model includes Pegasus/Cellebrite/NSO-grade Android
  compromise and the pod holds private keys, end-to-end-encrypted
  message content, or credentials
- The pod is itself a multi-container deployment (e.g. iris +
  mazemaker + pulse in one VM)
- The user already accepts a 80-400 MB APK (e.g. Tor, GnuPG,
  Signal-desktop class tools where APK size is irrelevant)

Pick **(B) proot + native ELF** when ANY of these hold:

- The pod is **user-trusted code the user installed on purpose**
  (Hermes Agent on a phone you own; a personal chat client; a
  dev tool the user wants to keep around)
- APK size matters (F-Droid, side-loading, low-bandwidth users,
  Play Store 100 MB limit)
- Cold start matters ("tap the icon and chat now", not "tap and
  wait 60s")
- The pod is a single ELF (one Python process, one Go binary,
  one Rust executable) — no multi-container orchestration
- The user runs on a non-Pixel device where AVF/pKVM is unavailable
  (QEMU TCG is the only Podroid option, which is the slow path)

### Both share the same client-side code shape

The Kotlin/Compose side is identical between substrates:

- `MainActivity` (single-Activity Compose host)
- `*PodService` (foreground service holding partial wake lock)
- `*PodSupervisor` (ProcessBuilder + child reaping + log streaming)
- `*PodExtractor` (one-shot asset extraction with sentinel marker)
- `*GatewayClient` (OkHttp REST + SSE to `127.0.0.1:NNNN`)
- `*PodStateRepository` (StateFlow state machine for the UI)
- `*ChatScreen` (Compose UI, observes the repo)

The ONLY thing that changes between substrates is what
`*PodSupervisor.launchProcess()` actually `exec()`s:

- Substrate A: `adb shell am start -n com.excp.podroid.debug/...`
  (the user starts the VM from the Podroid UI; the foreground
  service waits for the hostfwd to come up)
- Substrate B: `ProcessBuilder("proot", "--link2symlink",
  "--rootfs=...", "/opt/hermes/hermes-agent.bin", ...).start()`

You can refactor from A to B (or vice versa) by swapping one file.
The podroid-hermes scaffold is the Substrate-B shape; the
iris-messenger scaffold is the Substrate-A shape.

### Build pipeline is identical at the cross-compile layer

Both substrates produce the same artifact at build time: a
**compiled aarch64 ELF** of the userland service. The path:

```
x86_64 host (Garuda)
   │
   │  qemu-user-static + binfmt_misc (REQUIRED on x86_64)
   │
   ├─► podman build --platform=linux/arm64 -f Containerfile.<svc>
   │     └─► debian:bookworm arm64 (qemu-aarch64 emulated)
   │         ├─► git clone <svc> at pinned ref
   │         ├─► pip install deps into a venv
   │         ├─► python -m nuitka --onefile --standalone --arch=arm64
   │         │       --include-package=cryptography
   │         │       --include-module=_cffi_backend
   │         └─► strip --strip-all <svc>.bin
   │             └─► ~25 MB aarch64 ELF
   │
   └─► output: <svc>-arm64 artifact
         │
         ├─► (A) bake into OCI image → load via podman inside the VM
         │
         └─► (B) bundle with minimal Alpine rootfs + proot binary
                 → ship as APK assets/, extract to filesDir/
```

So QEMU shows up in BOTH pipelines at build time. The user's
mental model is: "QEMU is the cross-compile hammer; whether you
ship the result in a VM or as a bare ELF is the substrate
choice."

The user's framing on this is exact (2026-06-23): **"use that
QEMU vm to compile native needed shit!"** — QEMU is build-time
tooling, not a runtime component unless you chose substrate A.

See `references/native-elf-proot-substrate.md` for the full
substrate-B recipe (proot commandline, asset extraction,
sentinel-marker pattern, bundle layout, end-to-end build script).

## Architecture decisions (locked in by the iris-messenger
implementation; re-evaluate per project)

### 1. Static-vendor vs dynamic IPC

**Pick (a) static-vendor - bundle everything in one APK.** Alternatives:

- (b) Two APKs (Podroid + your app), user installs both, your app
  detects missing Podroid, Play Store, install, return. Friction
  is high, adoption is low.
- (c) Process isolation via Activity intent - your app launches
  Podroid as a separate process. Complex IPC, broken user flow.

Static-vendor means you vendor Podroid as a git submodule and the
OCI image as a bundled asset. License cascade: your app inherits
GPL-2.0 from Podroid (Section 2 of GPL v2.0, combined work). That's
fine for privacy/security tools (Tor, GnuPG, Signal-desktop are all
GPL-family).

For substrate B (proot + ELF), there is no static-vendor: proot is
`exec()`'d as a separate process, not linked. See pitfall 16 for the
license difference.

### 2. Git submodule vs fork

**Pick git submodule (vendored, unmodified) for substrate A.** Podroid
updates come via `git submodule update --remote`. You do not maintain
a fork. If you need to modify Podroid, do it in a `patches/` subdir +
a rebase script, not in the submodule.

This is the disciplined pattern: rebases are clean, security
updates flow upstream, your diff against upstream Podroid is one
`git diff` away.

**Submodule push pitfall (iris-messenger 2026-06-20):** the Podroid
submodule points to `https://github.com/ExTV/Podroid.git` (upstream
maintainer). If you commit changes inside the submodule (e.g. the
iris-pod OpenRC integration), `git push` from the parent repo WILL
succeed (the parent commit captures the new submodule pointer),
but the submodule's new commit is local-only — pushing it upstream
requires maintainer access to `ExTV/Podroid.git` (the upstream
rejects with HTTP 403 if you're not a maintainer).

**Three options to actually get CI to use the changes:**

1. **Fork Podroid** to `git@github.com:itsXactlY/Podroid.git`,
   update `.gitmodules` URL in the parent, push the submodule to
   your fork. CI fetches the fork. Loses upstream sync (you merge
   upstream manually).
2. **Mirror the changes** into the parent's tree (e.g. copy
   `build-rootfs/files/etc/init.d/iris-pod` to a top-level path,
   reference it from build-rootfs.sh with a relative path). The
   parent's CI builds Podroid from the local copy. Awkward but
   works without any external dependency.
3. **Dirty submodule** — leave the parent pointing at upstream
   Podroid but commit the changes locally. CI that runs `git
   submodule update --init --recursive` gets a clean upstream
   Podroid; the iris-pod changes are NOT in CI. Only local
   builds with `git submodule update` (no `--init`) get the
   changes. Acceptable for solo-dev, not for team CI.

The iris-messenger project currently uses option 3 (dirty
submodule) for the iris-pod commit. Production deployment will
need option 1 (fork).

For substrate B there is no submodule — proot is a binary you
download from GitHub releases at build time (or vendor as a small
ELF in `vm-image/proot/`).

### 3. arm64 build strategy

**Pick CI matrix on native arm64 runner. Do not local-cross-compile.**

- `qemu-user` is 5-20x slower than native
- `aarch64-linux-gnu-gcc` cross-compile needs a matching sysroot
  (~200 MB of pacman packages)
- GitHub-hosted `ubuntu-24.04-arm` runner is free for public repos,
  finishes the whole matrix in ~6 min

Local cross-build is documented as a fallback. The CI matrix is
the primary path. See the multi-arch section in
`python-binary-runtime-container` for the Containerfile TARGETARCH
pattern.

Same applies to substrate B — the Nuitka build for the .bin
also benefits from native arm64 runners. The podroid-hermes
`vm-image/hermes-pod-build.sh` works either on a native arm64
host or via qemu-user-static emulation.

### 4. Init system: OpenRC, not systemd (substrate A only)

**Pick OpenRC.** Podroid's Alpine uses OpenRC, your init script
must match. `/etc/init.d/iris-pod` is a 50-line shell script that
calls `podman run` in `start_pre()` (image load) + `start()`
(container start). The script lives in a tarball that Podroid
unpacks at boot onto the persistent ext4 layer.

Substrate B does not need an init system — the foreground service
in the Android app IS the init. `proot --link2symlink
/rootfs /opt/<svc>/<svc>.bin` replaces `/etc/init.d/<svc>` and
OpenRC's `start()`.

### 5. Container networking: --network=host, not slirp4netns
(substrate A only)

**Pick `--network=host` for the backend container.** The whole
point is that podroid-forward (running on the host side) bridges
guest eth0 to host loopback. If you put the container in a
separate network namespace, podroid-forward can't see the WS port
on guest eth0. The podman run wrapper script is
`/usr/local/bin/iris-pod-start.sh` - small and explicit.

For substrate B, the ELF binds 0.0.0.0:NNNN inside the proot
namespace; proot's ptrace-based fake-bind exposes that on the
host loopback at 127.0.0.1:NNNN. No network namespace dance
needed.

### 6. libsignal (or other crypto deps): vendor as subdir, not Maven
coordinate

**Pick vendor.** For the iris-messenger client, libsignal's
Maven coordinates are unreliable (Signal Foundation doesn't publish
to Maven Central; the Tinder mirror is unmaintained; Signal's
official `org.thoughtcrime.securesms:signal-protocol` drags in
Tink, which the project explicitly doesn't want).

The pattern: `android/libsignal/` is a sibling subdir with a mirror
of `github.com/signalapp/libsignal`. Gradle `includeBuild()` consumes
it. Auditable, no external build dependency, can patch locally.

## Workflow (substrate A — Podroid VM)

### Step 1 - License cascade analysis

Before writing any code, run a license analysis. For each component
that will be statically linked or bundled:

| Component                    | License                  | Effect on combined work                |
|------------------------------|--------------------------|---------------------------------------|
| Your app (Kotlin)            | AGPL-3.0 + PolyForm-NC   | inherited                             |
| Podroid (vendored)           | GPL-2.0                  | combined work inherits GPL-2.0 + AGPL |
| libsignal (vendored)         | AGPL-3.0                 | no change                             |
| Backend OCI image            | (your app's license)     | no change                             |

Document the cascade in `android/LICENSE` (combined-work notice).
Pointers to each upstream LICENSE in `NOTICE`. Section 5 and
Section 6 of GPL-2.0 require source pointer + copyright notice;
both are satisfied by the `LICENSE` + `NOTICE` files.

If your service's threat model REQUIRES MIT or closed-source
backend, consider substrate B (pitfall 16) or pick (b) dynamic IPC
(two APKs).

### Step 2 - Submodule + skeleton

```bash
cd /path/to/your-project
mkdir -p android
git submodule add https://github.com/ExTV/Podroid.git android/podroid
mkdir -p android/your-app
```

Podroid ships its own Gradle project. Do NOT make your app a module
of Podroid's build - keep them separate. Your app is its own Android
Studio project. Rebasing Podroid upstream is then a one-liner:
`git submodule update --remote android/podroid`.

### Step 3 - Compose chat client (or UI of any kind)

Standard Android Studio project (this is the substrate-A scaffold;
substrate-B has the same structure but with `HermesPodService`
replacing the Podroid-bind logic — see `references/native-elf-proot-substrate.md`):

```
android/your-app/
+- app/
|  +- build.gradle.kts
|  +- src/main/
|  |  +- AndroidManifest.xml
|  |  +- java/dev/yourorg/yourapp/
|  |  |  +- YourApplication.kt      (@HiltAndroidApp)
|  |  |  +- MainActivity.kt          (single Activity, Compose)
|  |  |  +- data/
|  |  |  |  +- YourGateway.kt       (OkHttp REST + WS to 127.0.0.1:NNNN)
|  |  |  |  +- IdentityStore.kt     (Android Keystore-backed keypair)
|  |  |  |  +- CryptoEngine.kt      (Phase 2: wire libsignal subdir)
|  |  |  +- ui/screens/              (pairing, list, conversation, settings)
|  |  +- res/
|  |     +- xml/network_security_config.xml   (cleartext ONLY to 127.0.0.1)
|  |     +- xml/backup_rules.xml               (exclude identity prefs)
|  |     +- xml/data_extraction_rules.xml
|  +- build.gradle.kts
|  +- proguard-rules.pro
+- build.gradle.kts
+- settings.gradle.kts
+- gradle/libs.versions.toml
+- gradle.properties
+- gradle/wrapper/gradle-wrapper.properties
```

Key deps (version catalog):
- AGP 8.7+, Kotlin 2.0+, Compose BOM 2024.11+
- Hilt 2.52+, KSP, Room 2.6+, DataStore 1.1+
- OkHttp 4.12+ (REST + WS, both client-side)
- libsignal placeholder (Phase 2 wires the vendored copy)
- CameraX + ML Kit (QR pairing, Phase 1.5)
- Biometric (Phase 3)
- WorkManager + Foreground Service (WS keep-alive)
- security-crypto 1.1.0-alpha06 (EncryptedSharedPreferences)

### Step 4 - Multi-arch backend OCI image

See `python-binary-runtime-container` for the multi-arch section.
The TL;DR:

- `Containerfile.multiarch` with `ARG TARGETARCH=amd64`
- `lib/` for amd64 glibc + system libs (existing per-arch)
- `lib-arm64/` for arm64 glibc + system libs (new)
- `iris-messenger-${TARGETARCH}.bin` per-arch binary
- GitHub Actions matrix: amd64 on `ubuntu-latest`, arm64 on
  `ubuntu-24.04-arm` (both native, no qemu-user)
- Push to `ghcr.io/yourorg/your-service:${arch}`

### 5. Podroid Alpine overlay (OpenRC init + start script)

```
android/vm-image/overlay/
+- etc/
|  +- init.d/iris-pod              # OpenRC service (start_pre + start)
|  +- iris/runtime.env             # config (identity, ports, DLM bootstrap)
+- usr/local/bin/iris-pod-start.sh  # plain 'podman run' wrapper
```

The OpenRC service depends on `podman` and `net`. start_pre ensures
the image is loaded (`podman load -i` from the vendor tarball).
start() execs the wrapper script, which does `podman run
--network=host --userns=keep-id -v /var/lib/iris:/var/lib/iris:Z ...`.

Build a tarball of `overlay/` and inject at `/` on the persistent
ext4 layer at boot. Podroid's `app/src/main/assets/` is the natural
delivery channel.

**UPDATE (2026-08-07): the CURRENT mechanism is staging in
`android/podroid/build-rootfs/files/` — `build-rootfs.sh` copies those files
into the squashfs at build time (init.d scripts Z.107–129, vendor tarballs
Z.175–200, runlevel symlinks Z.280–286). The hermes-agent integration is the
canonical example: vendored venv tarball → `/opt/hermes` + `podroid-hermes` /
`podroid-hermes-mcp` OpenRC services + Android-side loopback forward
`8088→8088`. For the full verified map of the rootfs (apk inventory, ports,
code-injection paths, RAM/GPU limits, what's missing for a native mazemaker
stack) read `references/podroid-vm-rootfs-current-state.md` FIRST.**

**The iris-pod init MUST be added to the default OpenRC runlevel,
otherwise it never starts.** This is a Podroid-specific quirk: the
build-rootfs script builds the squashfs with a runlevel symlink
loop, and `iris-pod` is NOT in the default list. Add it (or fork
Podroid to add it). Verified on iris-messenger 2026-06-20:
without the runlevel symlink, the init script is in `/etc/init.d/`
but OpenRC never executes it on boot. The fix is in
`android/podroid/build-rootfs/build-rootfs.sh`:

```bash
for svc in podroid-migrate podroid-bootstrap podroid-network \
           podroid-resize dropbear docker lxc dnsmasq.lxcbr0 \
           podroid-x11 podroid-vsock podroid-hostd podroid-ready \
           iris-pod; do   # <-- ADD iris-pod HERE
    if [ -e "$ROOTFS/etc/init.d/$svc" ]; then
        ln -sf "/etc/init.d/$svc" "$ROOTFS/etc/runlevels/default/$svc"
    fi
done
```

Same loop also needs to copy the iris-pod init from
`build-rootfs/files/etc/init.d/iris-pod` into the rootfs (the
build-rootfs script copies podroid-* init scripts but NOT custom
overlays). Add these lines BEFORE the podroid-* copy block:

```bash
if [ -f /work/files/etc/init.d/iris-pod ]; then
    cp /work/files/etc/init.d/iris-pod "$ROOTFS/etc/init.d/"
    chmod +x "$ROOTFS/etc/init.d/iris-pod"
fi
if [ -f /work/files/usr/local/bin/iris-pod-start.sh ]; then
    mkdir -p "$ROOTFS/usr/local/bin"
    cp /work/files/usr/local/bin/iris-pod-start.sh "$ROOTFS/usr/local/bin/"
    chmod +x "$ROOTFS/usr/local/bin/iris-pod-start.sh"
fi
if [ -d /work/files/etc/iris ]; then
    mkdir -p "$ROOTFS/etc/iris"
    cp -a /work/files/etc/iris/. "$ROOTFS/etc/iris/"
fi
```

The build-rootfs/files/ directory is the input staging area; copy
your overlay files there BEFORE building the rootfs.

### Step 6 - podroid-forward setup script (Android side)

After Podroid's `BootStageDetector` reports `Ready!`, your app's
MainActivity runs `setup-podroid-forward.sh` via `ProcessBuilder`:

```bash
podroid-forward add 9091 9091 tcp
podroid-forward add 9092 9092 tcp
```

This is the bridge from guest eth0:NNNN to host 127.0.0.1:NNNN. The
guest sees its own eth0 as the default gateway (QEMU SLIRP default
is `10.0.2.2`); the host sees `127.0.0.1`.

For substrate B, skip this step — proot's loopback passthrough is
automatic.

### Step 7 - All-in-one APK build

```bash
# Build the backend OCI image
make build-multiarch       # or let CI do it

# Build the Podroid overlay tarball
bash android/vm-image/scripts/build.sh
#   > dist/iris-messenger-arm64.tar          (OCI image)
#   > dist/iris-messenger-arm64-overlay.tar  (Alpine overlay)
#   > both copied into android/podroid/app/src/main/assets/iris-messenger/

# Build the Podroid APK (includes the bundled assets)
cd android/podroid
./build-all.sh apk
#   > app/build/outputs/apk/release/podroid-release.apk
```

The Podroid APK is now self-contained: install, open, VM boots,
iris-pod starts, podroid-forward registered, ready for pairing.

### Step 8 - End-to-end verify

```bash
# 1. Install the APK on a device or emulator
adb install -r android/podroid/app/build/outputs/apk/release/podroid-release.apk

# 2. Open the app, watch logcat for boot markers
adb logcat -s PodroidQemu:V YourService:V

# 3. After ~10s, verify the REST endpoint is reachable from the host
adb shell run-as com.excp.podroid curl -s http://127.0.0.1:9091/api/v1/health

# 4. Pair a second device, exchange a 6-digit code, send a message
# 5. Pull /var/lib/iris from inside the VM (NOT from /sdcard):
adb shell run-as com.excp.podroid ls files/upper/var/lib/iris/
```

## Pitfalls

These WILL bite. Read them before you start.

### 1. Local cross-compile vs CI matrix

Do NOT `pacman -S aarch64-linux-gnu-gcc aarch64-linux-gnu-glibc`
locally and try to cross-build the arm64 Nuitka binary. The
sysroot is ~200 MB, qemu-user is slow, and CI does it for free.

**Wrong:**
```bash
# x86_64 host, "let me just cross-compile" - wastes hours
aarch64-linux-gnu-gcc -o iris-messenger-arm64.bin ...
```

**Right:** push to GitHub, let `ubuntu-24.04-arm` build it natively
in ~6 min. Document local cross-build as a fallback in the build
script.

### 2. The .gitignore / scripts-in-build-dir bug

If your build artifact directory is `.gitignore`d (e.g. `lib/` for
runtime glibc .so files), any SCRIPT you put in that dir is also
gitignored. `git add lib/` silently drops it. Use `git add -f` to
bypass for individual files, OR rename the script to a non-ignored
location (e.g. `scripts/copy-libs.sh` instead of `lib/copy-libs.sh`).

### 3. OpenRC service file mode

OpenRC refuses to run scripts that are not executable. The build
script for the overlay tarball must `chmod 0755` the init script
BEFORE tar'ing it. If you tar it as `0644`, the VM boots, OpenRC
fails silently with `permission denied`, and your service is
mysteriously not running.

### 4. podroid-forward timing

podroid-forward must be invoked AFTER the VM is fully booted AND
the iris-pod container is up. The signal chain is:
- `BootStageDetector` matches "Ready!" in console.log
- THEN the container finishes starting (~1-3s after Ready!)
- THEN podroid-forward rules take effect

If you call podroid-forward before the container is up, the
forward rule is registered but the destination is empty. The
`setup-podroid-forward.sh` script's smoke test catches this: if
`curl /api/v1/health` fails, it returns non-zero and the app
retries with backoff.

### 5. Compose / ViewModel Hilt wiring in single-Activity nav

The single-Activity + Compose + Hilt + Navigation pattern works,
but `hiltViewModel()` needs a `@HiltViewModel` ViewModel per
screen. Each ViewModel takes the screen's SavedStateHandle for
nav arguments (`savedStateHandle.get<String>("chatId")`). Don't
hand-roll a ViewModelFactory.

### 6. libsignal dependency coordinate

There is NO good Maven coordinate for libsignal that:
- is published to Maven Central
- is officially maintained
- doesn't drag in unwanted deps (Tink, Bouncy Castle, etc.)

Vendor it as a sibling subdir: `android/libsignal/`, with
`includeBuild()` in your settings.gradle.kts. Phase 1 placeholder
in libs.versions.toml is fine; resolve at Phase 2 with the vendor.

### 7. Network security config

The Android app's `network_security_config.xml` must allow
cleartext to `127.0.0.1` and `localhost` ONLY. All other domains
must be HTTPS. Podroid forwards 9091/9092 to the host loopback
and never exposes them to the LAN by default. If you add LAN
federation later, document the threat-model change explicitly.

For substrate B (proot), the same rule applies: 127.0.0.1 only
in cleartext; everything else HTTPS.

### 8. Backup rules

`android:allowBackup="false"` is the safer default. The user
restores identity via the Iris-ID + 6-digit-code flow, not via
cloud backup. Excluding the encrypted prefs + Room DB from
backup_rules.xml + data_extraction_rules.xml makes this enforced.

### 9. Huawei / older Samsung TEE only supports RSA in AndroidKeyStore

EC keypair generation in AndroidKeyStore throws
`NoSuchAlgorithmException: no such algorithm: EC for provider
AndroidKeyStore` on devices whose TEE/StrongBox doesn't expose EC
(verified: Huawei P20 Pro EML-L29 on Android 10). If your Compose
UI calls `IdentityStore.createIdentity()` at first render, the
whole app crashes before showing anything.

**Fix pattern (IdentityStore.kt, ~30 lines):**

```kotlin
fun createIdentity(): String {
    val keypairGenerated = try {
        generateInAndroidKeyStore()
    } catch (e: Exception) {
        Log.w("IdentityStore", "AndroidKeyStore EC failed, falling back to software KeyStore", e)
        generateInSoftwareKeyStore()
    }
    if (!keypairGenerated) throw IllegalStateException("Failed to create identity keypair")

    val irisId = UUID.randomUUID().toString().replace("-", "").substring(0, 8)
    prefs.edit().putString(KEY_IRIS_ID, irisId).apply()
    return irisId
}

private fun generateInAndroidKeyStore(): Boolean {
    // Original code: KeyGenerator.getInstance(KEY_ALGORITHM_EC, "AndroidKeyStore")
    // ... throws on devices without TEE EC
}

private fun generateInSoftwareKeyStore(): Boolean {
    val kpg = KeyPairGenerator.getInstance("EC")
    kpg.initialize(ECGenParameterSpec("secp256r1"))
    val kp = kpg.generateKeyPair()
    Log.i("IdentityStore", "Software fallback keypair generated: pub=${kp.public.encoded.size} bytes")
    return true
}
```

Logcat signals (good) after the fix:
```
W IdentityStore: AndroidKeyStore EC failed (NoSuchAlgorithmException: ...
  no such algorithm: EC for provider AndroidKeyStore), falling back
  to software KeyStore
I IdentityStore: Software fallback keypair generated: pub=91 bytes
```

No regression on devices that DO support TEE EC: the try block
succeeds and the fallback never runs.

### 10. The QEMU binary is not in the gradle-only build (substrate A only)

A `./gradlew assembleDebug` in `android/podroid/` produces an APK
WITHOUT the QEMU binary. The Podroid UI then shows
"ERROR: QEMU binary not found." when you tap Start VM.

QEMU is built by `./build-all.sh qemu` (uses Docker, compiles
QEMU from source, copies `libqemu-system-aarch64.so` into
`app/src/main/jniLibs/arm64-v8a/`). The gradle build then picks
up the .so from jniLibs and packages it. First build is 15-30 min
on a fast host; incremental is seconds.

**Verify the QEMU binary is in the APK** before you install:
```bash
unzip -l android/podroid/app/build/outputs/apk/debug/app-debug.apk | grep -E "libqemu|libslirp"
# libqemu-system-aarch64.so   (~16 MB, present = good)
# libslirp.so                  (~1 MB, present = good)
# libpodroid-bridge.so         (~50 KB, present = good)
# libpodroid-launcher.so       (~10 KB, present = good)
```

If any of these is missing, the gradle build succeeded but the
QEMU step was skipped. Run `./build-all.sh qemu` first.

### 11. The launchable activity has `.debug` in debug builds

`adb shell am start -n com.excp.podroid/com.excp.podroid.MainActivity` fails
with "Error: Activity class does not exist" because the debug
applicationId is `com.excp.podroid.debug`, not
`com.excp.podroid`. The activity class is at
`<applicationId>.<ClassName>` = `com.excp.podroid.debug/com.excp.podroid.MainActivity`.

Always look up the real name with one of:
```bash
adb shell pm dump <pkg> | grep -A 1 MAIN
adb shell cmd package resolve-activity --brief <pkg>
```

The second is shorter. The output ends with the launchable name
you should pass to `am start -n`. See
`references/android-deployment-commands.md` for the full
workflow.

### 12. NEVER bypass the runtime substrate with `adb reverse`

**Hard rule (user pushback 2026-06-21, "NEIN! PODROID → PODMAN →
OBFUSCATED .BIN! ENDE!"):** the substrate choice is sacred. If
the client needs to talk to a pod, the path is ALWAYS through
the chosen substrate:

```
SUBSTRATE A:  client → phone's 127.0.0.1:NNNN → QEMU hostfwd
              → Podroid VM eth0:NNNN → podman container → .bin

SUBSTRATE B:  client → phone's 127.0.0.1:NNNN → proot loopback
              → /opt/hermes/elf-binary
```

The WRONG path (do NOT do this even as a "test" or "shortcut"):

```
client → adb reverse tcp:NNNN tcp:NNNN → host's pod on the LAN
```

Why this is wrong:
- The whole point of the phone-as-pod pattern is that the phone
  IS the pod. Bypassing it invalidates the threat model
  (sandbox-in-a-sandbox is no longer sandboxed).
- It bypasses the obfuscated .bin / ELF that ships in the APK
  (the artifact whose existence the project was built around).
- It leaks the client's traffic to whatever the host's network
  stack does (NAT, VPN, mDNS, etc.) — the host might be
  compromised; that's the whole reason the substrate exists.
- It creates a false-positive "it works" signal that masks
  substrate bugs (P5 regressions in Podroid, proot startup
  failures, .bin cold-start, etc.).

When the substrate is broken, the fix is ALWAYS inside the
substrate (Podroid: P5 workarounds in
`podroid-vm-substrate-build`; proot: re-extract assets, check
link2symlink flags, validate the ELF's RPATH). Not an adb
reverse to the host.

The only legitimate use of `adb reverse` is to bridge a
unix-domain socket on the device that adbd can't access via
the filesystem (e.g. QMP at
`/data/user/0/<pkg>/files/qmp.sock` — and even that fails
with `Permission denied` because adbd lacks the app-private
permissions, so the bridge never comes up).

### 13. adb input to Compose OutlinedTextField: parse the field,
not the label

When driving a Compose `OutlinedTextField` dialog via
`adb shell input tap` and `adb shell input text`, the label TEXT
("Android port") and the actual EditText input area are at
DIFFERENT y-coordinates. Tapping the label position puts focus
on the wrong field or no field. Tapping the right position with
the wrong number appended to a previous tap produces values
like "90919091" or "9091000000009091p".

**Correct workflow for the "Add port forward" dialog in Podroid
Settings (Huawei P20 Pro, 720x1600):**

1. Dump the UI: `adb shell uiautomator dump && adb shell cat
   /sdcard/window_dump.xml`
2. Find the EditText center with this Python regex (returns
   bounds, not the human-readable label):
   ```python
   import re
   xml = open('/tmp/dump.xml').read()
   for m in re.finditer(
       r'class="android\.widget\.EditText"[^>]*?text="([^"]*)"'
       r'[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
       x = (int(m.group(2)) + int(m.group(4))) // 2
       y = (int(m.group(3)) + int(m.group(5))) // 2
       print(f'  value={m.group(1)!r} center=({x},{y})')
   ```
3. Tap the center, type, then re-dump and verify the value
   before tapping Add.
4. For "Add port forward" specifically:
   - Android port field center: `(360, 429)` (NOT `(360, 606)`
     which is the label)
   - VM port field center: `(360, 585)`
   - Add button center: variable depending on keyboard state;
     re-dump to find it

**If the field already has stale text** (e.g. "9092" from a
prior failed tap), tap into the field, then use
`adb shell input keyevent KEYCODE_DEL` to clear, then type.
`adb shell input keyevent KEYCODE_9 KEYCODE_0 KEYCODE_9
KEYCODE_1` works as a numeric alternative to
`adb shell input text "9091"`.

**Diagnostic for "Add button didn't add the rule":** dump the
UI after the Add tap. If the dialog reopens (or the
"Port forwards (N)" count is unchanged), the typed value
failed validation. Most common cause: doubled input from a
prior tap. Look at the EditText value in the dump.

See `references/podroid-pairing-and-runtime-2026-06-21.md`
Step 7 for the exact verified sequence on a real device.

### 14. Don't reach for the QEMU VM by default — match the
substrate to the need

**User pushback 2026-06-23, "no. do NOT ship an qemu VM! lol,
use that QEMU vm to compile native needed shit!":** the
QEMU-VM-in-APK shape (substrate A) is the iris-messenger
pattern. It is the right call for high-threat-model backends,
but it is the WRONG default for "ship a Python service to a
phone."

Default assumptions to challenge:

- **"We need a real sandbox"** — only true if the pod runs
  untrusted code or holds high-stakes secrets. A user's own
  Hermes Agent, a personal note-taking backend, a dev tool —
  these are user-trusted code the user installed on purpose.
- **"Podman gives us multi-container"** — only true if you
  actually need >1 container. Most "phone-as-pod" projects are
  one Python process.
- **"The QEMU overhead is fine"** — 35-90s cold start on QEMU
  TCG (non-Pixel devices), 512 MB RAM, 407 MB APK. Not fine if
  the user is going to tap the app, wait a minute, then
  remember what they wanted to ask.
- **"QEMU gives us a familiar Linux userland"** — proot gives
  you the same. `proot --link2symlink --rootfs=alpine-arm64
  /opt/<svc>/<svc>.bin` is functionally equivalent to `chroot
  alpine-arm64 /opt/<svc>/<svc>.bin` for the use case of
  running a single pre-built binary.

**Test before reaching for the VM stack:**

1. Is the pod holding private keys / E2EE message content that
   the user cannot afford to lose to Android compromise? → VM
2. Is the pod running code the user didn't write themselves?
   → VM
3. Is the pod a single ELF / single process? → proot
4. Does the user tap the app expecting "ready now"? → proot
5. Is APK size a constraint? → proot
6. Are we on a non-Pixel device? → proot (QEMU TCG is the only
   Podroid option on non-Pixel, which is the slow path)

Two or more "proot" answers = use substrate B. Don't reach for
the QEMU VM by default. The QEMU VM is the heavy option; the
proot ELF is the lean option. Match the weight to the need.

### 15. proot + arm64 ELF: the recipe (substrate B)

The exact pattern that podroid-hermes uses (2026-06-23). All
defaults are what worked; tweak with care.

**Build-time QEMU VM (the build infrastructure, not shipped):**

```dockerfile
# Containerfile.<svc> — build context: <svc> source repo
FROM --platform=linux/arm64/v8 docker.io/debian:bookworm
ARG HERMES_REPO=https://github.com/NousResearch/hermes-agent.git
ARG HERMES_REF=main

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc g++ make git curl ca-certificates \
        python3 python3-dev python3-pip python3-venv \
        libssl-dev zlib1g-dev libffi-dev libsqlite3-dev patchelf

RUN git clone --depth 1 --branch "$HERMES_REPO" "$HERMES_REF" /build/<svc>
WORKDIR /build/<svc>
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install -U pip wheel \
    && /opt/venv/bin/pip install nuitka ordered-set \
        aiohttp websockets httpx openai tiktoken cryptography \
        pyyaml pydantic rich click python-dotenv jinja2 \
        requests urllib3 tqdm tenacity

# The two CRITICAL Nuitka flags (verified on iris-messenger 2026-06-22,
# commit 17a535e): --include-package=cryptography, --include-module=_cffi_backend
# Without these, setup_tls() at gateway init throws NameError on _setup_tls
#
# DO NOT ADD `--arch=arm64` — it is NOT a valid Nuitka flag (verified
# 2026-06-23: __main__.py: error: no such option: --arch). Nuitka picks
# the host arch automatically. Inside the --platform=linux/arm64
# container the host arch is aarch64. Just omit the flag.
RUN /opt/venv/bin/python -m nuitka --onefile --standalone \
        --include-package=cryptography --include-module=_cffi_backend \
        --include-module=openai --enable-plugin=anti-bloat \
        --no-pyi-file --remove-output \
        -o <svc>.bin gateway/run.py

RUN file <svc>.bin | grep -q "ARM aarch64"
RUN strip --strip-all <svc>.bin
```

**Runtime launch (foreground service → ProcessBuilder):**

```kotlin
val prootBin = File(podRoot, "proot")
val rootfsDir = File(podRoot, "rootfs")
val hermesBin = File(rootfsDir, "opt/hermes/hermes-agent.bin")

val cmd = listOf(
    prootBin.absolutePath,
    "--link2symlink",                      // critical: makes /proc, /dev, /sys work
    "--rootfs=${rootfsDir.absolutePath}",  // the chroot-as-fake
    "--bind=/dev:/dev",                    // passthrough so the ELF can talk to hardware
    "--bind=/proc:/proc",
    "--bind=/sys:/sys",
    "/opt/hermes/hermes-agent.bin",        // the compiled ELF
    "--gateway",
    "--host=0.0.0.0",                      // proot exposes this on 127.0.0.1:8088
    "--port=8088"
)
ProcessBuilder(cmd).directory(rootfsDir).start()
```

**Asset extraction pattern (idempotent with sentinel):**

```kotlin
object PodExtractor {
    private const val SENTINEL = ".extracted-v1"
    private const val MAGIC = "<svc>-pod-extracted-v1"

    suspend fun ensureExtracted(context: Context): Result<File> = withContext(Dispatchers.IO) {
        val podRoot = File(context.filesDir, "<svc>-pod").apply { mkdirs() }
        val sentinel = File(podRoot, SENTINEL)
        if (sentinel.exists() && sentinel.readText().trim() == MAGIC) {
            return@withContext Result.success(podRoot)
        }
        // copy assets/proot, assets/rootfs.tar, extract tar, set +x
        // write sentinel at the end
    }
}
```

Bundle layout in `app/src/main/assets/<svc>-pod/`:
- `proot` (statically linked arm64, ~3 MB)
- `rootfs.tar` (Alpine arm64 minimal, ~30 MB; contains
  `/opt/<svc>/<svc>.bin` and writable `/opt/<svc>/<svc>-data/`)
- After first launch: extracted to `filesDir/<svc>-pod/`

**Wiring details that bite:**

- `proot` MUST be statically linked. The dynamically-linked
  build on Alpine is missing the libc it needs to run on
  Android bionic. Pin to the GitHub release with
  `-static` in the name.
- The `--bind=/dev:/dev --bind=/proc:/proc --bind=/sys:/sys`
  flags are MANDATORY. Without them, hermes-agent can't read
  `/proc/cpuinfo` etc. and may crash on init.
- The Android `networkSecurityConfig` must allow cleartext to
  `127.0.0.1` ONLY. The gateway binds 0.0.0.0:8088 inside
  proot; proot exposes that on 127.0.0.1:8088. Other domains
  are HTTPS-only.
- Cold-start budget is 5-10s. If the gateway doesn't respond
  on `127.0.0.1:8088/api/health` within 90s, surface a
  `HermesPodState.Failed("hermes-agent did not become ready
  within 90s", recoverable = true)` and let the user retry.
- Wake lock: acquire a 6-hour `PARTIAL_WAKE_LOCK` while the pod
  is in `Ready` state, release on `Idle` / `Stopping`. Without
  the wake lock, Doze will pause the process and the gateway
  becomes unreachable mid-conversation.
- The sentinel-marker pattern makes extraction idempotent AND
  survives app updates (assets are re-read on first launch
  after update, sentinel survives, extraction is skipped).
  To force re-extraction (e.g. to pick up a new rootfs in an
  app update), bump the sentinel magic (`-v1` → `-v2`).

### 16. APK assets must be uncompressed for fast extraction
(substrate B)

`androidResources.noCompress` in `app/build.gradle.kts`:

```kotlin
androidResources {
    noCompress += listOf("hermes-agent/bin", "hermes-agent/proot", "hermes-agent/rootfs.tar")
}
```

If the assets are stored compressed in the APK, Android's
`AssetManager.open()` returns a `InflaterInputStream`. proot
reads from the extracted file in `filesDir/`, not from
`AssetManager`, so compression is fine for the COPY. But
extracting a 30 MB rootfs tar through an `InflaterInputStream`
adds ~5-10s to first launch. Use `noCompress` so the APK
stores them raw; the OS still reads them straight from the
APK as a memory-mapped file.

Same applies to jniLibs:

```kotlin
packaging {
    jniLibs { useLegacyPackaging = true }
}
```

Default 16KB page alignment (Android 13+) is enforced
automatically when AGP 8.0+ packages JNI; no linker flag
needed for our binaries (the ones we ship are pre-built with
the right flags by their build systems).

### 17. The proot binary is GPL-2.0; the bundled ELF inherits
its own license (substrate B)

License cascade per substrate:

- **(A) QEMU VM (Podroid):** combined work inherits
  `Podroid GPL-2.0 + <svc> license`. If your service is
  AGPL-3.0 or MIT, the combined work is now
  `GPL-2.0 + AGPL-3.0` (or `GPL-2.0` for the MIT case,
  due to GPL's "no add restrictions" clause). Document
  in `android/LICENSE`.

- **(B) proot + ELF:** Kotlin code does NOT link proot —
  it `exec()`s proot as a separate process. The Kotlin
  combined work does NOT inherit GPL-2.0 from proot. The
  bundled proot binary retains GPL-2.0; its source is at
  the URL. The bundled `<svc>.bin` retains `<svc>`'s
  license (e.g. MIT for hermes-agent). Your Kotlin code
  can be MIT, Apache-2.0, AGPL-3.0, whatever.

**This is a real reason to pick substrate B for some
projects.** If your service is MIT and you cannot accept
the GPL cascade that comes with vendoring Podroid,
substrate B lets you keep your service's permissive
license. The proot binary is a process, not a library.

### 18. QEMU at build time, not runtime: the cross-compile
hammer

Both substrates need an arm64 build. The build pipeline
is the same:

- x86_64 host with `qemu-user-static` + `binfmt_misc` for
  arm64 emulation (Arch: `systemd-binfmt`, not
  `update-binfmts`)
- Native arm64 host (RPi 5, Graviton, GitHub
  `ubuntu-24.04-arm` runner) — 5-10x faster
- The QEMU at build time is a TOOL, not part of the
  product. Don't conflate "we use QEMU to build" with
  "we ship QEMU."

If the user complains about build speed, fix the build
host (use a native arm64 runner, or pre-warm
qemu-user-static caches). Don't add a runtime VM as a
"build acceleration" — that's the wrong direction.

### 19. proot is NOT a sandbox (substrate B)

proot is ptrace-based fake-chroot. An attacker on the
phone who can ptrace the proot process can escape. The
substrate B is appropriate for **user-trusted code the
user installed on purpose**, not for sandboxing hostile
workloads.

If you need a real sandbox, use substrate A (Podroid) or
build a custom seccomp/cgroup/namespace hardening on top
of proot. The podroid-hermes scaffold does NOT do this —
it's a quick start, not a security boundary.

### 20. Android 10+ SELinux blocks exec from app_data_file
(substrate B runtime blocker)

**THE showstopper for substrate B on a stock non-rooted
Android 10+ phone. Verified on Huawei P20 Pro (EML-L29,
Android 10) with the podroid-hermes APK (2026-06-23).**

```kotlin
// Both Runtime.exec() and ProcessBuilder.start() fail with:
java.io.IOException: Cannot run program "..."
  error=13, Permission denied
  at java.lang.UNIXProcess.forkAndExec(Native Method)
```

The proot binary IS +x, the path IS valid, the SELinux
context IS `app_data_file`. The kernel still refuses
because Android 10+ SELinux policy
(`neverallow untrusted_app exec_file`) blocks any exec from
`app_data_file` context. Runtime.exec and ProcessBuilder
both go through `UNIXProcess.forkAndExec` which performs
the SELinux check. **Neither bypasses it.** Verified by
testing both — same error, same stack frame.

**This is a HARD kernel-level block**, not a config issue.
Same restriction that forced Termux/Andronix to ship
their own app_process fork.

**Workarounds (in order of effort):**

1. **Root the phone** (`adb root` then `adb shell` can
   launch proot directly). Fastest path if the device is
   yours.
2. **`adb shell run-as <pkg> /data/.../proot ...`** —
   works without root because run-as impersonates the
   app user but bypasses the SELinux check via the
   `runas` domain. Useful for smoke-testing on non-rooted
   devices; does NOT help the actual app runtime.
3. **Reimplement proot in a JNI .so library** — ship
   `lib/arm64-v8a/libhermes_pod.so` containing the ptrace
   logic in C, `System.loadLibrary("hermes_pod")` from
   HermesPodService, call a JNI method that fork+execs.
   The `lib/arm64-v8a/` dir IS on the SELinux whitelist
   for exec. **This is the production answer for non-rooted
   devices.** 1-2 weeks of C work to port proot.
4. **MANAGE_EXTERNAL_STORAGE + Termux-style app_process
   trick** — heaviest lift, requires user to grant the
   permission. Not recommended.

**Document this constraint up front** in the project
README before promising "works on any Android phone." The
current podroid-hermes scaffold does NOT solve it. The
deployed APK works on rooted devices or via `adb shell
run-as`; it does NOT work on a stock non-rooted Android
10+ phone despite the binary being +x.

### 21. QEMU emulation is too slow for big-codebase Nuitka
builds (build-time pitfall, both substrates)

**Verified 2026-06-23.** Building hermes-agent's full
`gateway/run.py` (the entire CLI + plugins + tools +
acp_adapter + tui_gateway) under qemu-aarch64 emulation
took 12+ minutes of module discovery with no end in
sight. The slimmer `gateway/platforms/api_server.py` entry
took 5+ minutes for the same reason.

The reason: hermes-agent is a HUGE codebase. Nuitka does
heavy AST analysis on every reachable module. Under qemu
emulation each arm64 instruction is interpreted on the
x86 host at ~5-20x slower than native.

**Pivots that work:**

- **Go static cross-compile: <1 second.** `GOOS=linux
  GOARCH=arm64 CGO_ENABLED=0 go build -o svc.bin svc.go`,
  ship a 5-6 MB static aarch64 ELF. No QEMU needed.
- **C/C++ cross-compile with aarch64-linux-gnu-gcc: a few
  minutes.** `aarch64-linux-gnu-gcc -static` produces a
  static aarch64 binary directly. No QEMU.
- **Nuitka slim (api_server.py only): 5+ min under QEMU.**
  Acceptable for one-off builds.

**The lesson:** if the service is written in Python, write
a Go/Rust/Zig shim for the build pipeline and
cross-compile natively. Reserve QEMU emulation for one-off
slim entry points or for host packages that are already
arm64. For large Python codebases, the production answer
is a native arm64 GitHub runner (ubuntu-24.04-arm, free
for public repos).

### 22. Nuitka `--arch=arm64` is NOT a valid flag (build-time
pitfall)

**Verified 2026-06-23.**

```text
__main__.py: error: no such option: --arch
```

Despite being widely cited in old tutorials, `--arch` is
not a Nuitka option. Nuitka picks the host arch
automatically. Inside a `--platform=linux/arm64`
container, the host arch IS aarch64. Just omit the flag.

If you do see `--arch=arm64` in older docs / Containerfile
templates / generated build scripts, REMOVE it. It will
break the build.

## Companion: Podroid-Hermes (substrate B) build

The **podroid-hermes** project is the concrete application of substrate B
(proot + compiled aarch64 ELF) to **Hermes Agent** itself. This subsection
absorbs the former `podroid-hermes-native-build` and `podroid-local-llm`
skills. When the user wants Hermes Agent (optionally with a local LLM) running
on their phone, follow the recipe below and consult the re-homed references.

### What gets built
- A statically-linked **proot** arm64 ELF (process, not linked library — no
  GPL cascade on the Kotlin side).
- A minimal **Alpine arm64 rootfs** containing the compiled Hermes Agent ELF
  (`/opt/hermes/hermes-agent.bin`) plus its venv.
- A Kotlin/Compose `HermesPodService` (foreground service, partial wake lock)
  that `ProcessBuilder` → `proot --link2symlink --rootfs=... /opt/hermes/hermes-agent.bin --gateway --host=0.0.0.0 --port=8088`. proot exposes it on `127.0.0.1:8088`.
- For a local LLM: a **Vulkan-enabled Alpine build** so the pod can run GGUF
  models (see `references/podroid-hermes/vulkan-alpine-build.podroid-local-llm.md`).

### Build recipe (TL;DR)
1. Cross-compile Hermes Agent to a onefile aarch64 ELF with Nuitka inside a
   `--platform=linux/arm64` Debian container (qemu-user-static + binfmt_misc on
   x86_64 host, OR a native arm64 runner). CRITICAL Nuitka flags:
   `--include-package=cryptography --include-module=_cffi_backend`. Do NOT pass
   `--arch=arm64` (not a valid Nuitka flag). See the full build script in
   `references/podroid-hermes/build-recipe.podroid-hermes.md` and
   `references/podroid-hermes/build-pipeline.podroid-hermes.md`.
2. Bundle `proot` (statically linked, `-static` release), `rootfs.tar`
   (Alpine arm64 with the ELF at `/opt/hermes/`), and `start_hermes_venv.sh`
   into `app/src/main/assets/hermes-pod/`. Mark them `noCompress` in
   `build.gradle.kts` for fast first launch.
3. Idempotent asset extraction with a sentinel marker
   (`references/podroid-hermes/aapt2-gz-asset-gotcha.podroid-hermes.md` covers
   the aapt2 `.gz` asset gotcha that breaks extraction).
4. `HermesPodService` launches proot with
   `--bind=/dev:/dev --bind=/proc:/proc --bind=/sys:/sys` (mandatory or the ELF
   can't read `/proc/cpuinfo` and may crash on init).

### Hard blockers / pitfalls (all verified, full detail in references)
- **Android 10+ SELinux `neverallow untrusted_app exec_file`** blocks
  `exec()`/`ProcessBuilder` from `app_data_file` context even when the binary is
  `+x`. Neither `Runtime.exec` nor `ProcessBuilder` bypass it. Workarounds:
  root the phone, `adb shell run-as <pkg>` (smoke test only), reimplement proot
  in a JNI `.so` (production answer for non-rooted), or MANAGE_EXTERNAL_STORAGE +
  Termux-style `app_process` trick. Document this up front — the scaffold does
  NOT solve it on stock non-rooted Android 10+.
  (`references/podroid-hermes/proot-selinux-pitfall.podroid-hermes.md`,
  `references/podroid-hermes/proot-seccomp-sigsys-app.podroid-hermes.md`)
- **proot is NOT a sandbox** — ptrace-based fake-chroot; appropriate only for
  user-trusted code (the user's own Hermes Agent), not hostile workloads.
- **QEMU at build time, not runtime**: the cross-compile hammer. For large
  Python codebases, prefer a Go/Rust shim or native arm64 GitHub runner; QEMU
  TCG emulation is 5-20x slower and times out Nuitka on big trees.
- **Guest service integration** (how the ELF's gateway wires to the Compose UI
  and the relay) is in
  `references/podroid-hermes/podroid-guest-service-integration.podroid-hermes.md`.
- **API-server entry point gotchas** (the slim `api_server.py` vs full
  `gateway/run.py`) in
  `references/podroid-hermes/api-server-gotchas.podroid-hermes.md`.
- **QEMU/KVM pod architecture notes** (if you later want a VM pod of Hermes)
  in `references/podroid-hermes/qemu-kvm-pod-architecture.podroid-hermes.md`.

### Local LLM on the pod
Running a GGUF model inside the pod needs a Vulkan-capable Alpine build. See
`references/podroid-hermes/vulkan-alpine-build.podroid-local-llm.md` for the
Mesa/Vulkan APK + env-var wiring (`VK_ICD_FILENAMES`,
`LD_LIBRARY_PATH=/opt/hermes/venv/lib`). Keep VRAM coexisting with any
always-on processes (NMM/Wonderland on the host) — see `tts-local-generation`
for the VRAM-budgeting discipline.

### Build scripts / templates (re-homed)
- `scripts/podroid-hermes/build_hermes_venv.sh` — venv + Nuitka onefile build
- `scripts/podroid-hermes/inject_venv.sh` — inject built ELF into rootfs tar
- `templates/podroid-hermes/start_hermes_venv.sh` — pod launch wrapper

## Companion: Android app architecture (foundation)

The `phone-as-pod` pattern sits on top of general Android app architecture
(Kotlin/Compose, single-Activity navigation, Hilt, foreground services,
process supervision, MTP deploy, MCP-over-USB bridge). The former
`android-mobile-architecture` skill is absorbed here as reference material;
consult it when you need the underlying app-structure recipes rather than the
pod-packaging specifics.

### Reference library (re-homed from `android-mobile-architecture`)
- `references/android-architecture/mcp-protocol.android-arch.md` — MCP
  transport/protocol notes for driving an Android app from the agent.
- `references/android-architecture/mtp-linux-android-deploy.android-arch.md` —
  deploying build artifacts to the phone over MTP from Linux.
- `references/android-architecture/mazemaker-hermes-bridge-troubleshooting.android-arch.md` —
  Mazemaker↔Hermes bridge debugging on-device.
- `references/android-architecture/app-layer-audit-recipe.android-arch.md` —
  auditing the app layer (permissions, components, exposed surfaces).
- `references/android-architecture/navigation-trap-fix-20260616.android-arch.md` —
  Compose navigation trap fix (2026-06-16).
- `references/android-architecture/podroid-vm-all-in-one-apk.android-arch.md` —
  the all-in-one APK shape (this is exactly the substrate-A phone-as-pod build).
- `references/android-architecture/podwebsocket-lifecycle-and-verification.android-arch.md` —
  PodWebSocket reconnect-lifecycle bug class (closed-flag + generation counter
  to kill stale reconnects, close-old-before-open), wss:///empty-host URL
  hardening, 401→auth_required, the `compileDebugKotlin`/`testDebugUnitTest`
  Gradle verification workflow for THIS project (no npm test; multi-agent
  dirty-tree attribution, parallel-daemon contention → `--no-daemon`,
  `--rerun-tasks` for fresh evidence), and the differential-compile trick to
  prove a hand-built kotlinc IR-lowering error is a harness artifact, not a
  source bug.
- `references/android-architecture/viewmodel-coroutine-races.android-arch.md` —
  ViewModel-level coroutine race fixes for `MazemakerViewModel.kt` (2026-08-07,
  H11/H12/H2/H5/M13/M14): generation counter for async job-cancel races
  (stale job's catch/finally must not clobber a newer job's busy/streaming/
  history; guard inside `collect {}` too), the canceller-owns-the-state-reset
  subtlety, WS collector jobs as fields with cancel-before-re-attach,
  one-shot timer-job dedup, pagination hasMore criterion + limit reset,
  WS reconnect-when-dropped condition.
- `references/android-architecture/kotlin-gateway-client-hardening.android-arch.md` —
  gateway-client/pairing/repository hardening playbook (the "F-task" pattern):
  `@Synchronized` around session-negotiation state, crypto-exception
  encapsulation + `invalidateSession()`, Gson `toJson` instead of hand-built
  JSON, `resultCatching` (CancellationException rethrow) vs `runCatching`,
  `@Volatile` cache + local copy, clear-text error detection, TOFU pairing
  hardening (host validation, wrapped SSL/socket errors, relay passthrough),
  tolerant SSE parsing; plus the `takeIf`/`asJsonObject` type pitfall and
  verification in a concurrently-modified multi-agent worktree.
- `references/android-architecture/repository-cache-offline-hardening.android-arch.md` —
  repository/cache/offline-layer hardening (the "E-task" pattern, 2026-08-07,
  E1–E7): idempotency-aware retry in `callTool` (retry only idempotent tools,
  5xx range + `retryable` flag; writes get 1 attempt), `resultCatching` AND the
  trap that plain `catch (e: Exception)` also swallows CancellationException in
  fallback blocks, MemoryCache fixes (CREATE TABLE all in `init()` so `clear()`
  can't hit a missing table; one ReentrantLock around every public method —
  must be reentrant because publics call each other), offline cache fallback in
  browse/recall/graph/stats, offline stub markers (`"offline":true`) + path
  precision (`/memory/` → `/memory/list`), Gson null-reflection → `String?`
  fields + grep-driven usage-site fixes (`?: ""`, `.orEmpty()`,
  `isNullOrBlank()`), and the `MazemakerRepositoryTest.kt` regression net.
- `references/android-architecture/ui-leaks-ux-fixes.android-arch.md` —
  Compose UI-leak/UX-fix playbook (the "G-task" pattern, 2026-08-07, G1–G6):
  CameraX async-provider cleanup (AtomicReference + disposed AtomicBoolean +
  DisposableEffect; `runCatching` around `future.get()`; disposed-check before
  bind), the lifecycle-observer-placement rule (re-lock observers must live
  OUTSIDE conditional composition gates or they die with the gate),
  BiometricPrompt user-cancel codes (ERROR_NEGATIVE_BUTTON=10 /
  ERROR_USER_CANCELED=13) are not errors, callback-less server-success
  detection via the dreamLoading cycle + errorMessage ordering (watch BOTH
  keys), and clear-form-only-on-success via the ViewModel's lastRememberId
  success signal + pendingClear flag.
- `references/android-architecture/gateway-pairing-mdns-relay.android-arch.md` —
  QR-pairing → mDNS → Route-C-relay debug for "app hits the WRONG endpoint /
  api.mazemaker.dev / 404 'only serves /api/*'". Root context: the pairing code
  is HOST-LESS by design (`{v,token,fp}`, host found via mDNS); a dead/disabled
  mDNS advertise unit silently drops the app onto the relay fallback (v2),
  which 404s if not deployed. Sequence: decode `/pair.json` (QR is base64 JSON),
  check `mazemaker-apk-gateway-mdns.service` is active (gateway up ≠ advertised),
  confirm LAN subnet, grep `MM_RELAY_*` in the systemd drop-in, read logcat.
  Fixes: enable the mdns unit; comment out relay vars in
  `service.d/relay.conf` + daemon-reload + restart; re-scan QR. Comment-in-place
  over delete for the drop-in.
- `references/android-architecture/lint-suppression-documentation.android-arch.md` —
  the B-task pattern: silencing DELIBERATE lint warnings with rationale instead
  of changing logic. `@SuppressLint` + `//` comment in Kotlin (TOFU trust-all,
  composite trust); **XML comment alone does NOT silence lint** — needs
  `xmlns:tools` on the root + `tools:ignore` on the element. Verification:
  `:app:lintDebug` then `grep -c` the three lint IDs in `lint-results-debug.txt`
  (must be 0). Pitfalls: stale `lint_partial_results` after a killed daemon
  (`rm -rf app/build/intermediates/lint_partial_results`), daemon-stop mid-build
  (`--stop` + `--no-daemon`), and attributing pre-existing dirty-tree AAPT
  failures via `git status` before blaming your edit.

### When to reach for this
- The user wants a Kotlin/Compose app structure, not a pod — use these refs
  for the app skeleton, then layer the `phone-as-pod` packaging on top.
- Debugging the Android app layer (navigation, MTP deploy, MCP bridge) outside
  the pod-substrate concern.
