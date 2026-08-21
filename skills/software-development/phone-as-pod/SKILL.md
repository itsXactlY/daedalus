---
name: phone-as-pod
description: >
  Bundle a Linux userland service (Python/Go/Rust/anything) into a
  self-contained Android app. The APK contains a Kotlin/Compose shell
  and one of two interchangeable runtime substrates: (A) a QEMU VM
  (Podroid: Alpine + QEMU + podman, no root) for high-threat-model
  backends, or (B) proot + a compiled aarch64 ELF for lean
  user-trusted backends. Both share the same client-side code shape;
  pick at design time. Triggers when the user says "self-host on my
  phone", "phone-as-pod", "phone is the server", "all-in-one APK
  with backend", "sandbox-in-a-sandbox", "ship a Linux service to
  Android", "we don't need a VPS my phone IS the pod", "build a
  native APK for <service>", or names a backend that needs Android
  deployment (iris-messenger, pulse, mazemaker-mcp, hermes-agent, etc.).
  Verified on iris-messenger (2026-06-20) and podroid-hermes scaffold
  (2026-06-23). See "Podroid-Hermes (substrate B) build" for the full
  Hermes-Agent-on-Android recipe (native build + local LLM).
category: software-development
---

# Phone-as-pod: ship a Linux service as one Android APK

## What this pattern is

A single Android APK that contains:

1. A **native Kotlin/Compose chat client** (or UI of any kind)
2. A **runtime substrate** that hosts the Linux userland on Android.
   **Two interchangeable substrates** — pick at design time (see
   "Substrates" below):
   - **(A) QEMU VM** — Podroid (Alpine + QEMU + podman, no root). High
     isolation, big APK, slow cold start. Used by iris-messenger.
   - **(B) proot + native ELF** — proot provides a ptrace-based
     fake-chroot; the userland is a single compiled aarch64 binary
     (Nuitka --onefile --arch=arm64) + minimal Alpine rootfs. Small
     APK, fast cold start, no real sandbox. Used by podroid-hermes.
3. A **per-arch OCI image of the backend service** (substrate A) **or
   a compiled arm64 ELF + rootfs tarball** (substrate B)
4. An **init / launch mechanism** — OpenRC service in the VM (A) or
   `proot --link2symlink` + ProcessBuilder from the foreground
   service (B)
5. **Port-bridging** — Podroid hostfwd (A) or proot's loopback
   passthrough (B). Both put the pod on `127.0.0.1:NNNN` of the phone

The user installs ONE APK. Tapping the icon either boots the VM
(~5-90s depending on engine) or starts the proot-hosted ELF
(~5-10s), and the client UI shows "ready." No root, no cloud, no
separate downloads at install time.

```
SUBSTRATE A: QEMU VM (Podroid)
+-------------------------------------------------------------+
| Android OS (potentially compromised - Pegasus, Cellebrite)  |
|                                                             |
|   +-----------------------------------------------------+   |
|   | iris-android (Kotlin/Compose)                       |   |
|   |   - 127.0.0.1:9091/9092 <-- this is the pod API     |   |
|   |   +---------------------------------------------+   |   |
|   |   | Podroid VM (QEMU TCG or AVF/pKVM)            |   |   |
|   |   |   Alpine 3.23 + Podman + ext4 overlay       |   |   |
|   |   |   +-------------------------------------+   |   |   |
|   |   |   | iris-messenger pod (OCI arm64)      |   |   |   |
|   |   |   +-------------------------------------+   |   |   |
|   |   +---------------------------------------------+   |   |
|   +-----------------------------------------------------+   |
+-------------------------------------------------------------+

SUBSTRATE B: proot + native ELF (podroid-hermes)
+-------------------------------------------------------------+
| Android OS                                                  |
|                                                             |
|   +-----------------------------------------------------+   |
|   | hermes-android (Kotlin/Compose)                     |   |
|   |   - HermesPodService (foreground)                  |   |
|   |     - HermesPodSupervisor: ProcessBuilder           |   |
|   |       - proot --link2symlink --rootfs=... --bind=…  |   |
|   |         - /opt/hermes/hermes-agent.bin              |   |
|   |           --gateway --host=0.0.0.0 --port=8088      |   |
|   |     - 127.0.0.1:8088  <-- this is the pod API       |   |
|   +-----------------------------------------------------+   |
+-------------------------------------------------------------+
```

The two substrates share the same client-side code shape (Compose
+ foreground service + state repository) — only the pod-launching
piece differs. You can swap them per project.


<!-- moved to references/moved-sections.md: ## Substrates: pick at design time -->


<!-- moved to references/moved-sections.md: ## Architecture decisions (locked in by the iris-messenger -->

## MANDATORY workflow rule — recall BEFORE host tools

**User correction (2026-07-16, repeated, explicit):** when the task touches a
phone/podroid/iris deployment that the operator has worked on before, the FIRST
move is `mcp__mazemaker__mazemaker_recall` (or `recall_multi`), NOT `terminal` /
`adb` / `search_files`. The operator's phone-stack facts live in the memory
graph (gateway IDs, relay URLs, the unique-ID fix, the readonly-overlay bug,
which phone is adb-flaky). Guessing from host state wastes turns and re-breaks
things. Recall the exact path Claude took, then act.

Concrete trigger phrases that MUST route to recall first: "wie hat claude das
gemacht", "recall den weg", "war das nicht schon mal", "stell avf wieder an",
anything about iris federation / pixel 9a / pixel 7 pro / podroid guest.

## Runtime: accessing the live Podroid guest (substrate A)

Once the APK is installed and the VM is up, you often need to poke the Alpine
guest (write iris config, restart a service, inspect mounts). The access paths:

### Path 1 — Podroid app terminal (RELIABLE, Claude's actual method)
Open the Podroid app → Terminal tab → you get a `podroid:~#` shell inside the
crosvm guest. This is how Claude did every guest edit. Type directly on the
phone keyboard; do NOT try to script it unless you must.

### Path 2 — `adb shell input text` (FRAGILE — read the traps)
You CAN drive the guest terminal from the host via:
```
adb shell input text "command with real spaces"
adb shell input keyevent 66    # Enter
```
But the Android IME mangles anything non-trivial:
- **Spaces:** send REAL space characters, NOT `%s`. `%s` is NOT expanded by the
  guest shell — it arrives literally as `%s` and breaks paths (`%s/etc/...`).
- **Pipes / `$()` / `>` / `()` :** unreliable. `input text` sends chars one by
  one to the IME; complex shell constructs get corrupted or dropped. A `mkdir -p
  /etc/iris && echo ... > file` chain often partially fails (mkdir silently
  no-ops, the redirect then reports "No such file or directory").
- **Best practice:** if you must use `input text`, send SHORT commands with
  real spaces and NO pipes/subshells. For anything with `$(...)` or `|`, give
  the user the command and let them type it on the phone (their real keyboard
  has no IME problem). This is exactly why Claude used the app terminal, not adb.

### Path 3 — SSH :2222 (BLOCKED)
The guest sshd listens on :2222 but accepts ONLY a specific key (not the host's
`~/.ssh/*`). Password auth is off. `ssh root@127.0.0.1 -p 2222` → "Permission
denied (publickey,password)". Do not waste time hunting host keys — use Path 1.

### Reading guest output without working vision
If `vision_analyze` / `browser_vision` is erroring (aux-LLM down), you cannot
read a screencap. Fallback: ask the operator to paste the terminal output, OR
verify via the host-side REST channel (`adb forward tcp:9091 tcp:9091` then
`curl 127.0.0.1:9091/api/status`) — the iris pod answers from the host even
though the guest filesystem does not.

### Mount reality (verified 2026-07-16, Pixel 9a)
`/` is an **rw overlay** (upperdir=`/mnt/persist/upper`), so `/etc` IS writable
*if the parent dir exists*. `/mnt/persist` is a writable ext4. The readonly
trap is NOT `/etc` — it's that `mkdir` over a broken `input text` chain silently
fails, so the target dir never appears and the subsequent `echo >` can't create
the file. If `echo > /etc/iris/runtime.env` fails, check the dir exists FIRST
(via a separate short `mkdir -p /etc/iris` command, or just have the user type
the whole block in the app terminal).

## Iris federation triage (cross-phone chat)

The federation stack has THREE independent states that the operator conflates.
Diagnose in order:

1. **Pod alive** — `curl 127.0.0.1:9091/api/status` returns 200 with
   `gateway_id`. If 000/empty → iris-pod not running in guest (see bug
   `podroid-guest-podman-readonly-db-kills-iris`: podman may be dead, cascading
   iris down; hermes is independent and still healthy).
2. **Unique gateway_id** — each phone MUST have a distinct `gateway_id`. The
   shipped default is `gateway-1` for EVERY install → two phones collide →
   "cannot pair with self". Fix (Podroid PR #1 `fix/unique-gateway-id`, OR
   runtime workaround): write a unique `IRIS_DLM_IDENTITY=gw-<12hex>` into the
   guest `/etc/iris/runtime.env` and `rc-service iris-pod restart`. Without
   this, pairing is structurally impossible.
3. **Relay wired** — `runtime.env` needs (per phone, unique ID):
   ```
   IRIS_DLM_IDENTITY=gw-<unique>
   IRIS_FEDERATION_RELAY_URL=wss://iris.mazemaker.online/circuit
   IRIS_FEDERATION_RELAY_HTTP=https://iris.mazemaker.online
   ```
   Then `rc-service iris-pod restart`. The relay `iris.mazemaker.online` is
   LIVE (cloudflared tunnel → prod podman container, verified 2026-07-16).
   After this, `/api/status` shows the gateway registered at the relay
   ("federated").
4. **federated ≠ paired** — "federated" means both gateways registered at the
   relay. It does NOT mean they are peers. `federation_peers` stays 0 until the
   APP adds the other phone's `iris://gw-XXXX#key` handshake (PeersScreen →
   paste/add) on BOTH sides (mutual). No mutual peer entry → no conversation
   list entry.
5. **paired ≠ chat-able (known app gap)** — even after mutual peer pairing, the
   NATIVE iris app (dev.itsxactly.iris) may not open a conversation against a
   federated peer. The federation BACKEND works (pod→relay→pod proven); the
   native app's "compose message to federated peer" UI was incomplete as of
   2026-07 (PeersScreen shows handshake + paste-to-pair, but message-compose
   against a federated peer was not verified). If pairing succeeds but no chat
   starts, the blocker is app-side, not infra.

**Triage order for "kein chat geht":** pod alive? → unique ID? → relay wired? →
mutual peer paired in app? → app can compose federated chat? (last one = dev
work, not config).

See `references/iris-federation-runtime.md` for the endpoint reference and the
exact runtime.env block.


<!-- moved to references/moved-sections.md: ## Workflow (substrate A — Podroid VM) -->


<!-- moved to references/moved-sections.md: ## Pitfalls -->

## When the user pushes back

- [ ] APK installs cleanly on a Pixel-class device (substrate A
      on AVF/pKVM, substrate B anywhere)
- [ ] APK installs cleanly on a non-Pixel arm64 device (QEMU
      TCG or proot — both work)
- [ ] Substrate A on QEMU TCG: VM boots in <90s; on AVF: <3s
- [ ] Substrate B: proot launches ELF in <10s
- [ ] Container / ELF starts in <3s after substrate ready
- [ ] REST endpoint responds at `http://127.0.0.1:NNNN/api/health`
- [ ] WS endpoint connects from the Compose UI
- [ ] Pairing flow completes (or whatever the service's
      equivalent is)
- [ ] `/var/lib/<svc>/` is INSIDE the substrate, not visible
      to ADB
- [ ] `adb shell run-as <pkg> ls /sdcard/` does NOT show pod
      state contents
- [ ] APK is reasonable size (substrate A: <400 MB; substrate
      B: <100 MB)
- [ ] Build is deterministic (same hash on repeated builds)
- [ ] Both arm64 and amd64 build paths work in CI

## Step 9 - Real-device deployment (adb workflow)

The Step 8 verify commands assume a Pixel-class device with AVF/pKVM
and clean state. For real phones (Huawei, Samsung, Xiaomi) the actual
deployment workflow has 3 specific gotchas that bit the iris-messenger
ship on a Huawei P20 Pro (EML-L29, Android 10, arm64-v8a). All three
have verified fixes; the full adb command reference is in
`references/android-deployment-commands.md`. The summary:

1. **The QEMU binary is NOT in the gradle-only build (substrate A).**
   A pure `./gradlew assembleDebug` in `android/podroid/` produces
   a 37 MB APK with no QEMU. The "ERROR: QEMU binary not found"
   message in the Podroid UI comes from this. Fix: run
   `./build-all.sh qemu` (uses Docker, 15-30 min first time) before
   the gradle build. The full APK with QEMU is ~83 MB. Document
   this in your README so users don't waste an hour on it.

2. **The launchable activity is `<applicationId>.<ClassName>`, not
   `com.yourorg.yourapp.MainActivity`.** Debug builds have `.debug`
   appended to applicationId. Use `adb shell pm dump <pkg> | grep
   -A 1 MAIN` or `adb shell cmd package resolve-activity --brief
   <pkg>` to get the correct name. See the reference for the
   one-liner.

3. **Huawei (EML-L29) and older Samsung TEEs only support RSA in
   AndroidKeyStore.** Any `KeyGenerator.getInstance("EC",
   "AndroidKeyStore")` throws `NoSuchAlgorithmException` and the
   app crashes at the first Compose render that touches the
   identity store. Fix: try the AndroidKeyStore first, fall back
   to a software EC keypair from the default JCA provider. The
   `IdentityStore.kt` change is ~30 lines and adds zero regressions
   on devices that DO have TEE EC. See the reference for the
   exact code + logcat signals.

The `references/android-deployment-commands.md` file has the full
adb command set: pre-flight, install, find-activity, uiautomator
dump, screencap, crash diagnosis, `/dev/kvm` reality check, and
post-install smoke test. The Huawei Keystore fix is in there with
the full code snippet.

## When the user pushes back

This pattern is opinionated. The user might want different choices:

- "I don't want GPL-2.0 in the license stack" -> substrate B
  (proot is a process, not a linked library, so the cascade
  doesn't apply), or dynamic IPC for substrate A (two APKs).
- "I want the app smaller" -> substrate B (~50-100 MB vs 80-407).
  Or drop the Compose UI entirely, ship a webview pointing at
  `http://127.0.0.1:NNNN/ui`. Substrate A drops to ~75 MB.
- "I want to use my own VM" -> don't. Podroid is 3 years of work.
  Vendoring is the right call. If you have a SPECIFIC reason (e.g.
  your threat model requires pKVM-only and Podroid has a bug),
  fork it (NOT recommended) or use a different engine.
- "I want hermes-agent / pulse / mazemaker-mcp on my phone" ->
  substrate B with the respective service as the ELF. See
  `references/native-elf-proot-substrate.md` for the recipe.

The pattern is REUSABLE across backend services and across
substrates. iris-messenger is substrate A; podroid-hermes is
substrate B. pulse / mazemaker-mcp / any future "self-hostable
on phone" backend should pick substrate A or B per the rubric
and follow the same recipe.

## Worked example

iris-messenger all-in-one APK, 2026-06-20, 4 commits (substrate A):

```
64e4a0b  android: scaffold + iris-android skeleton + Podroid submodule
e9821bb  build: multi-arch support (amd64 + arm64) for Podroid/iris-android
9d8e2f7  build: include lib/copy-libs.sh in repo (was gitignored)
22c9621  vm-image: Podroid overlay + arm64 image build for all-in-one APK
```

46 files, 2981 insertions. Architecture decisions documented in
each commit message. License cascade in `android/LICENSE`. Threat
model in `android/README.md`. Boot flow diagram in
`android/vm-image/README.md`.

podroid-hermes scaffold, 2026-06-23 (substrate B):

```
fd38cf8  podroid-hermes: scaffold native APK + arm pod build
```

39 source files, 600 KB. QEMU only at build time (Containerfile
runs `python -m nuitka --onefile --standalone --arch=arm64` inside
a qemu-aarch64-emulated Debian arm64 container). At runtime,
HermesPodService execs proot, proot execs the compiled ELF, ELF
binds 0.0.0.0:8088, proot exposes on 127.0.0.1:8088 to the
host. See `references/native-elf-proot-substrate.md` for the
end-to-end recipe and `references/podroid-hermes-architecture.md`
for the design.

## Related skills

- `podroid-vm-substrate-build` - substrate A internals:
  kernel/QEMU/rootfs build, OpenRC services, the 6 failure
  modes (unqualified registries, missing initramfs, vendor
  tarball placement, cross-arch binfmt, crun sysfs, TCG slowness).
  Use when the VM is broken; not the right skill for the
  substrate decision itself.
- `python-binary-runtime-container` - the per-arch Nuitka +
  FROM scratch + multi-arch Containerfile pattern that produces
  the OCI image (A) or the standalone ELF (B). THIS skill picks
  up at the artifact and goes "now what do I do with it on
  Android."
- `full-project-rebrand` - license cascade + combined-work
  LICENSE pattern is documented in detail there (rebrand
  + license switch is the same move).
- `agent-delivery-integrity` - the "do the whole plan" lesson
  applies: when the user says "go" with a multi-step plan,
  do the whole plan, don't ask per-step.
- `subagent-driven-development` - if the project is large enough,
  dispatch subagents to write the per-arch Containerfile,
  the Compose UI, the OpenRC service / HermesPodService, in
  parallel after the substrate + skeleton is in place.

## References

- `references/architecture-decisions.md` - the locked-in choices
  for the iris-messenger implementation, with rationale and
  alternatives that were considered
- `references/boot-flow-diagram.md` - ASCII diagram of the full
  install-to-ready path, with timing estimates
- `references/threat-model.md` - sandbox-in-a-sandbox attack
  classes that substrate A addresses, and the one class it
  doesn't (kernel compromise)
- `references/oci-image-bundling.md` - how to embed the arm64
  OCI image in the Podroid APK assets/ directory
- `references/native-elf-proot-substrate.md` - **substrate B
  recipe**: proot commandline, Nuitka arm64 build, asset
  extraction, sentinel-marker pattern, bundle layout,
  end-to-end build script. The full podroid-hermes scaffold
  distilled into reference form. Use this when you're
  building substrate B.
- `references/podroid-hermes-architecture.md` - the design
  doc for the podroid-hermes project itself (substrate B
  applied to hermes-agent), with build pipeline + cold-start
  measurements.
- `references/android-deployment-commands.md` - concrete adb
  command reference for shipping the APK to a real device:
  pre-flight checks, install, finding the launchable activity
  class, uiautomator dump, screencap, logcat crash diagnosis,
  the Huawei AndroidKeyStore EC NoSuchAlgorithmException fix
  with full code, and post-install smoke test from inside the
  device. Verified on Huawei P20 Pro EML-L29.
- `references/iris-federation-runtime.md` - iris gateway endpoint map,
  the gateway-ID collision bug + unique-id fix, the live
  `iris.mazemaker.online` relay config block, and the
  federated/pairing/chat triage for cross-phone chat.
- `references/podroid-vm-rootfs-current-state.md` - verified map of the
  substrate-A rootfs as of 2026-08-07: apk inventory (`build-rootfs.sh`),
  the hermes-agent-native integration (venv tarball → /opt/hermes, gateway
  :8088, per-install key), the mazemaker MCP-client wiring (NO engine in the
  VM — :8790 app proxy → desktop :8765), full port/service table, the three
  code-injection paths, hard limits (RAM 512 MB default, no GPU), and the
  gap list for a native mazemaker stack. Read before "add X natively to the
  Podroid VM" tasks.

## Companion: the Podroid VM substrate (absorbed from `podroid-vm-substrate-build`)

The lower-level **Podroid VM substrate** — the custom Linux userland substrate that
`phone-as-pod` packages and ships — was absorbed from `podroid-vm-substrate-build`.
When you need to (re)build the substrate itself rather than package an existing service
into a pod, consult the re-homed build notes/scripts:

- `references/podroid-vm-substrate-build/` — substrate build recipe, layout, and
  end-to-end build script.

This skill (`phone-as-pod`) is the *packaging* layer; the substrate build is the
foundation it depends on.


<!-- moved to references/moved-sections.md: ## Companion: Podroid-Hermes (substrate B) build -->


<!-- moved to references/moved-sections.md: ## Companion: Android app architecture (foundation) -->
