# Self-hosted Android app via vendored Podroid VM + multi-arch CI

(observed 2026-06-20, iris-messenger → iris-android all-in-one APK, 8 commits, 28 MB debug APK on disk, working tree clean)

## What this pattern is

A privacy-critical Android app that ships its own server-side runtime inside a rootless Alpine/QEMU VM (Podroid), bridged to the host's loopback via `podroid-forward`. The Android app is a thin Kotlin/Compose chat client; the heavy lifting (X3DH, federation, message store) happens in the VM. The user installs one APK, opens it, the VM boots, the server starts, the chat client connects to `127.0.0.1`.

This is the "sandbox in a sandbox" threat model: even if the Android OS is compromised (Pegasus-class 0-day, Cellebrite forensic, hostile accessibility app, rooted shell), the iris-side keys and traffic are inside the VM and the Android-side DB only holds ciphertext.

## When to use

- A privacy-critical app where the threat model extends past "the app is sandboxed by Android"
- The user wants to host the server-side runtime on-device (no VPS, no third party)
- An upstream VM project exists (Podroid, Termux, UserLAnd, etc.) that you want to vendor rather than fork
- The user wants `apk install → open → ready` UX (no first-run download, no extra config)

## Architecture

```
android/                                  (subdir, sibling to the rest of the project)
├── podroid/                              git submodule: github.com/ExTV/Podroid
│   ├── app/                              Podroid's Android app (Compose + Hilt + DataStore)
│   ├── build-all.sh                      Docker-cached build (kernel + rootfs + QEMU + APK)
│   ├── build-rootfs/                     Alpine squashfs build
│   └── podroid_kernel.config             custom Linux kernel config
│
├── iris-android/                         STANDALONE Android Studio project (not a
│   ├── app/                              Podroid module — keeps upstream rebaseable)
│   │   ├── src/main/java/.../data/      OkHttp client + Room DB + Android Keystore
│   │   └── src/main/java/.../ui/         Compose screens (Pairing, ChatList, ...)
│   ├── build.gradle.kts                  AGP 8.7.3, Kotlin 2.0.21, Compose BOM 2024.11
│   └── settings.gradle.kts
│
└── vm-image/                             Podroid Alpine overlay + arm64 image build
    ├── overlay/etc/init.d/iris-pod       OpenRC service (Podroid is Alpine, not systemd)
    ├── overlay/etc/iris/runtime.env      config (Iris-ID, ports, DLM, trust)
    ├── scripts/build.sh                  builds iris-messenger:arm64 + overlay tarball
    └── scripts/setup-podroid-forward.sh  runs on Android side after VM boot
```

## Key design decisions (the ones that are easy to get wrong)

1. **Standalone Gradle project, not a module of Podroid's build.** Podroid's `settings.gradle.kts` includes `:app, :terminal-emulator, :terminal-view`. Adding `:iris-android` to it would mean iris-android is rebuilt every time Podroid bumps. Keep them separate; iris-android is its own Android Studio project under `android/iris-android/`.

2. **Podroid as submodule, not fork.** `git submodule add https://github.com/ExTV/Podroid.git android/podroid`. Upstream security fixes come via `git submodule update --remote`. Customisation lives in `android/vm-image/overlay/`, never in `android/podroid/`.

3. **OpenRC, not systemd.** Podroid uses Alpine 3.23 with OpenRC as PID 1. The iris-pod service MUST be an OpenRC init script at `/etc/init.d/iris-pod` (not a systemd unit). The overlay tarball unpacks it at boot.

4. **`--network=host` for the iris-messenger container.** podroid-forward on the Android side already bridges guest eth0 to host loopback. No need for podman-macvlan or slirp4netns.

5. **arm64-only ABIs.** Podroid is arm64-only (QEMU TCG with arm64 guest). Setting `ndk.abiFilters += "arm64-v8a"` in `app/build.gradle.kts` cuts the APK size roughly in half vs. fat APK and avoids shipping x86_64 JNI libs that the device can't use.

## Multi-arch CI matrix (the pattern that beat cross-compile)

The iris-messenger container is x86_64-built (FROM scratch + glibc x86). Podroid is arm64-only. Bridging that needs a multi-arch image. The naive approach (cross-compile Nuitka to arm64) is slow and drags in a ~200 MB aarch64 sysroot. The right approach: native builds on the matching GitHub Actions runner.

```yaml
# .github/workflows/build-images.yml
jobs:
  build:
    strategy:
      matrix:
        include:
          - arch: amd64
            runner: ubuntu-latest          # native x86_64
          - arch: arm64
            runner: ubuntu-24.04-arm       # native aarch64 (preview, free for public repos)
    # ... each runner builds Nuitka natively, stages lib/<arch>/, builds the
    # multi-arch Containerfile with TARGETARCH=${{ matrix.arch }}, pushes
    # ghcr.io/itsxactly/iris-messenger:<tag>-<arch>

  manifest:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - docker manifest create \
            ghcr.io/itsxactly/iris-messenger:<tag> \
            --amend \
            ghcr.io/itsxactly/iris-messenger:<tag>-amd64 \
            --amend \
            ghcr.io/itsxactly/iris-messenger:<tag>-arm64
      - docker manifest push ghcr.io/itsxactly/iris-messenger:<tag>
```

Result: `podman pull ghcr.io/itsxactly/iris-messenger` (no tag suffix) returns the right arch automatically. qemu-user emulation never enters the picture.

## Multi-arch Containerfile

Single file, `ARG TARGETARCH` chooses the per-arch lib dir and binary:

```dockerfile
FROM scratch
ARG TARGETARCH=amd64

# x86_64 (amd64) system libs
COPY lib/ld-linux-x86-64.so.2     /lib64/ld-linux-x86-64.so.2
COPY lib/libc.so.6                 /usr/lib/libc.so.6
# ... ~14 libs total

# aarch64 (arm64) system libs
COPY lib-arm64/ld-linux-aarch64.so.1     /lib/ld-linux-aarch64.so.1
COPY lib-arm64/libc.so.6                 /usr/lib/libc.so.6
# ... ~14 libs total

COPY iris-messenger-${TARGETARCH}.bin /usr/local/bin/iris-messenger
```

The `lib/copy-libs.sh {amd64|arm64}` script stages the per-arch glibc + libssl + libcrypto + libsqlite3 + libffi + libexpat + libz + libpthread + libdl + libm + librt + libutil + libresolv + libgcc_s + the dynamic linker from the host's `/usr/lib` (Arch/Garuda) into the right `lib[/arm64]/` dir. Idempotent, safe to re-run.

## Build-iteration pitfalls (first 4 build attempts on a fresh Compose+Hilt+Room+OkHttp project)

These are the 4 errors you will hit on first build, in order, with the fix. If you hit them differently, the cause is the same — read the official docs for the OkHttp / Room / Android Keystore API, not StackOverflow from 2019.

### 1. `KeyGenerator.initialize(spec)` → compile error: "Unresolved reference 'initialize'"

`KeyGenerator` (from `javax.crypto`) has `init(...)` — Java naming convention. `initialize(...)` is on `KeyPairGenerator`, not `KeyGenerator`. Auto-complete suggests both; pick `init`. Affected: any Android Keystore key generation with `KeyGenParameterSpec`.

### 2. `MediaType.parse(...)` deprecation warning → in OkHttp 4.x, the replacement extension needs an explicit import

```kotlin
import okhttp3.MediaType.Companion.toMediaType       // ← required
import okhttp3.RequestBody.Companion.toRequestBody   // ← required

"application/json; charset=utf-8".toMediaType()     // now resolves
"{\"x\":1}".toRequestBody(mediaType)                 // now resolves
```

Defining a local `String.toMediaType()` extension in your own file that calls `MediaType.parse(this)` is a footgun — the deprecated call still fires the deprecation warning. Use the OkHttp 4.x extension directly.

### 3. `KeyGenerator` returns a key but the key is "wrong" → check `setKeySize(256)` for EC, not for AES

For ECDH / Curve25519 (Signal X3DH), `setKeySize(256)` is correct. For AES it would be 128 or 256. The default if you forget `setKeySize` is 0 bytes, which causes `KeyStoreException: Invalid key size`. Symptom: identity creation succeeds in code, but the key is unusable for signing/agreement.

### 4. Room `@Database(exportSchema = true)` with no `room.schemaLocation` KSP argument → compile warning, no error

```
[ksp] Schema export directory was not provided to the annotation processor
so Room cannot export the schema. You can either provide `room.schemaLocation`
annotation processor argument by applying the Room Gradle plugin
(id 'androidx.room') OR set exportSchema to false.
```

For Phase 1 (no migrations yet), set `exportSchema = false`. For Phase 2+, add the schema location:

```kotlin
// app/build.gradle.kts
ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}
```

### 5. `/api/*` inside a Kotlin comment closes the comment early → "Unclosed comment" at the next `/*`

The Kotlin lexer treats `*/` as the end-of-comment delimiter. Writing the literal string `/api/*` inside a `/** */` KDoc block (or any `/* ... */` block) causes the first `*/` (which appears as the second-to-last char of `/api/*`) to terminate the comment early. Everything from that point onward in the file is then parsed as Kotlin code, producing errors like "Expecting ';'" or "Unclosed comment" at the next syntax error — NOT at the line where the `*/` actually appeared.

This bit 3 times in one session (2026-06-20, iris-android):

```kotlin
/** PHASE 1 NOTE — ENDPOINT MISMATCH:
 *  The current IrisGateway uses /api/v1/* paths that do not exist
 *  on the real server. Real API is at /api/* and uses X3DH + ECDSA.
 */
```

Compile error points far from the cause:
```
e: .../IrisGateway.kt:226:22 Expecting ';' after the last enum entry
   or '}' to close enum class body
e: .../IrisGateway.kt:237:1 Unclosed comment
```

The "Expecting ';'" is on the enum line; the actual `/api/*` is on the comment line 50 lines earlier. The compiler can't tell you "you wrote `*/` in the middle of a comment" because that's valid Kotlin behavior — it just keeps parsing as code.

**Fix:** avoid the sequence `*/` inside any comment or string literal. Safe rewrites:
- "the api path" (no slashes)
- "api/v1" (no trailing `*`)
- "/api" (no trailing `*`)

**Detection script** (run BEFORE the next build attempt when a "Unclosed comment" error appears):
```bash
for f in $(find . -name '*.kt'); do
  open=$(grep -c '/\*' "$f")
  close=$(grep -c '\*/' "$f")
  if [ "$open" != "$close" ]; then
    echo "MISMATCH: $f  open=$open close=$close"
  fi
done
```

Catches all instances in one pass. Catches the issue immediately on the second and third files after the first has been fixed.

**Trigger pattern:** any Kotlin file that mentions a URL path containing `*` — HTTP `OPTIONS *`, CORS `Access-Control-Allow-Origin: *`, regex `*`, URL wildcards `/api/*`, glob patterns, etc. Either wrap the literal in a non-`*` form, or use a `private const val` String constant and reference it by name in the comment.

## Gradle wrapper pinning

The system gradle (e.g. Gradle 9.5.1 on Arch) is too new for AGP 8.7. Pin via the wrapper:

```bash
gradle wrapper --gradle-version 8.10.2 --distribution-type bin
```

AGP 8.7 supports Gradle 8.9-8.12. AGP 8.10+ supports Gradle 8.11.1+. AGP 9.0+ is needed for Gradle 9.x. Pick AGP version FIRST, then wrapper version matches.

Commit the wrapper (gradlew, gradlew.bat, gradle/wrapper/gradle-wrapper.{jar,properties}) so any host can `./gradlew assembleDebug` without a system gradle install.

## The `lib/` .gitignore collision

When a directory is `.gitignore`d because it holds build artifacts (Nuitka `.so` staging files for the FROM-scratch container), adding scripts INSIDE that directory silently fails. The directory itself is ignored, not the script.

Workarounds (in order of preference):

1. Move the script OUT of the ignored directory (e.g. `scripts/copy-libs.sh` instead of `lib/copy-libs.sh`). Cleanest.
2. `git add -f lib/script.sh` to bypass the ignore. Document with a leading comment.
3. Add an exception to `.gitignore`: `lib/ !lib/copy-libs.sh`. Fine, but adds a per-file exception that has to be remembered.

The iris-messenger repo landed on option 2 (`git add -f lib/copy-libs.sh`) and added a follow-up commit explaining the choice. Future rebrands: if you add a script to a `.gitignore`d directory, the first `git add` will silently drop it. Check `git status` after staging.

## Compose + Hilt + OkHttp + Room dep-version recipe (the set that compiled 2026-06-20)

```toml
# gradle/libs.versions.toml
[versions]
agp = "8.7.3"
kotlin = "2.0.21"
ksp = "2.0.21-1.0.27"

hilt = "2.52"
hiltNavigationCompose = "1.2.0"
coroutines = "1.9.0"
okhttp = "4.12.0"
room = "2.6.1"
datastore = "1.1.1"
work = "2.9.1"
security-crypto = "1.1.0-alpha06"   # for EncryptedSharedPreferences

composeBom = "2024.11.00"
activityCompose = "1.9.3"
navigationCompose = "2.8.4"
```

`com.android.application` plugin + `kotlin-android` + `kotlin-compose` + `kotlin-ksp` + `hilt-android`. Java 17, jvmTarget "17", compileSdk 35, minSdk 26 (matches Podroid's minSdk).

## Boot flow (the "apk install → open → ready" UX)

1. User taps iris-android icon
2. Podroid VM boots (QEMU TCG or AVF pKVM)
3. Podroid unpacks `assets/iris-messenger/*-overlay.tar` at `/`
4. OpenRC starts `iris-pod` service
5. `iris-pod` (start_pre): `podman load -i /usr/local/share/iris/iris-messenger-arm64.tar`
6. `iris-pod` (start): `podman run --name=iris-messenger --detach --network=host --userns=keep-id -v /var/lib/iris:/var/lib/iris:Z -v /etc/iris/runtime.env:/etc/iris/runtime.env:ro,Z localhost/iris-messenger:arm64`
7. iris-android sees Podroid's `BootStageDetector` report "Ready!", runs `setup-podroid-forward.sh`
8. `podroid-forward add 9091 9091 tcp ; add 9092 9092 tcp`
9. PairingScreen, 6-digit code, ready for messaging

## Threat-model table (when arguing for this architecture)

| Attack class                    | Bare Android messenger | iris-android + Podroid VM |
|---------------------------------|------------------------|---------------------------|
| Pegasus-class Android 0-day     | Full access to messages + keys | VM isolated, no host-OS access |
| Cellebrite-style forensic       | IndexedDB / SharedPreferences readable | /var/lib/iris is inside the VM's ext4, not visible to ADB |
| Hostile accessibility app       | Reads chat on screen    | Compose UI is in foreground but WS traffic is in the VM's network |
| Rooted Android shell            | Full access to app data | QEMU TCG / pKVM barrier; pKVM escape is a separate research problem |
| Kernel-level compromise         | Full access             | Out of scope (no userspace container can help) |

The kernel-compromise case is the one this architecture does NOT cover. State it explicitly when pitching the design.

## What this pattern does NOT solve (and what the next pattern would be)

- **libsignal Java port as a vendored subdir**: `RatchetEngine.kt` is stubbed for Phase 1. Phase 2 vendors the libsignal source as `android/libsignal/` and uses Gradle `includeBuild()` to consume it. Stub vs real is a drop-in replacement at the call site; the surrounding code (Hilt singleton, IdentityStore integration) is fully wired.
- **QR pairing flow**: CameraX + ML Kit dependencies are in the catalog but the screen logic is Phase 2. Pairing via 6-digit code from the host is the Phase 1 fallback.
- **FCM push** (requires gateway-side support — server sends FCM messages to the device's Iris-ID)
- **Biometric app lock** (Phase 3 — `androidx.biometric` is already in the catalog)
- **APK signing config**: `signing.properties.example` template is committed; the `signing.properties` is in `.gitignore` and never committed.

## REAL/MOCK_FALLBACK gateway mode (Phase 1 transition strategy)

The real iris-messenger API lives at `/api/*` and uses X3DH + ECDSA-signed auth challenges — `POST /api/identity/create`, `POST /api/auth/challenge`, `POST /api/auth/login` (with `signature` over `nonce || timestamp`), `POST /api/pairing/create`, `POST /api/pairing/accept`, `POST /api/auth/verify`, then `Authorization: Bearer <token>` for the rest. NONE of these exist at `/api/v1/*` — that was a placeholder assumption that needs correction.

Until libsignal is vendored (Phase 2), the Android client can't produce the ECDSA signature, so it can't complete the real auth flow. The Phase 1 fix is a two-mode gateway:

```kotlin
@Singleton
class IrisGateway @Inject constructor() {
    private val _mode = MutableStateFlow(Mode.MOCK_FALLBACK)
    val mode: StateFlow<Mode> = _mode.asStateFlow()

    /** Single GET to a known-stable endpoint decides which mode we're in. */
    suspend fun probe(baseUrl: String = DEFAULT_BASE_URL): Mode =
        withContext(Dispatchers.IO) {
            try {
                val req = Request.Builder().url("$baseUrl/api/status").get().build()
                client.newCall(req).execute().use { resp ->
                    _mode.value = if (resp.isSuccessful) Mode.REAL else Mode.MOCK_FALLBACK
                    _connectionState.value = if (resp.isSuccessful) ConnectionState.CONNECTED
                                            else ConnectionState.DISCONNECTED
                    _mode.value
                }
            } catch (_: Throwable) {
                _mode.value = Mode.MOCK_FALLBACK
                ConnectionState.DISCONNECTED
                Mode.MOCK_FALLBACK
            }
        }

    suspend fun sendMessage(peer: String, body: String, token: String, baseUrl: String = DEFAULT_BASE_URL): String {
        return if (_mode.value == Mode.REAL) {
            // POST /api/message/send with bearer token, real X3DH ciphertext
            realPost("$baseUrl/api/message/send", token, peer, body)
        } else {
            // MOCK_FALLBACK: pretend the server accepted it
            "mock-${System.currentTimeMillis()}-$peer"
        }
    }

    enum class Mode { REAL, MOCK_FALLBACK }
}
```

Called from `MainViewModel.init { viewModelScope.launch { gateway.probe() } }` once on app start. The UI's `SettingsScreen` shows the current mode as a one-liner + a "Refresh" button that re-runs `probe()`.

**The honest move:** `PairingScreen` calls `vm.fakePairForDemo(irisId)` which stores a fake token in `IdentityStore` and proceeds to the chat list. Without a clear comment, future readers will think the real auth flow runs. The `ViewModel` body has a numbered TODO listing the 7 real steps (identity create → challenge → ECDSA-sign → login → persist token → setup-podroid-forward.sh → start ForegroundService). Phase 2 replaces the shim line-for-line.

**Why this beats the alternatives:**
- Hardcoding `MOCK_FALLBACK` permanently leaves the client un-validated against the real server
- A "demo mode" toggle in settings adds a permanent UI surface for what's really a Phase 1 implementation gap
- The probe() pattern auto-promotes the client to REAL mode the moment the real auth is wired, with no UI change

## Production data flow (ForegroundService → MessageRepository → Room → Compose)

The full WebSocket-to-screen path, end-to-end. Worth getting right in Phase 1 because it's the actual delivery mechanism, not a placeholder:

```
GatewayForegroundService.onCreate()
  └─ IdentityStore.registrationToken()        // Hilt-injected, EncryptedSharedPreferences
  └─ IrisGateway.connectWebSocket(token, onMessage)   // OkHttp WebSocket on 127.0.0.1:9092
  └─ startForeground(NOTIF_ID, notif, FOREGROUND_SERVICE_TYPE_DATA_SYNC)
                                                       // Doze won't kill us

onMessage callback (background coroutine):
  └─ parse {type: 'message', peer, ciphertext, id}   // JSON envelope
  └─ Base64.decode(ciphertext)
  └─ MessageRepository.onIncoming(peer, ciphertext, id)
       └─ MessageDao.insert(MessageEntity(...))      // Room INSERT

ConversationViewModel.messages: StateFlow<List<MessageEntity>> =
  messageRepository.observeChat(chatId)               // Flow<List<MessageEntity>> from Room
       .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

ConversationScreen { ... }
  items(messages, key = { it.id }) { msg -> Text(String(msg.ciphertext, UTF_8), ...) }
                                                  // Phase 1: ciphertext is plaintext bytes
                                                  // Phase 2: RatchetEngine.decrypt() goes here
```

**Key wiring points** (each can be broken independently):

1. `GatewayForegroundService` is `@AndroidEntryPoint` (Hilt) so it can inject `IrisGateway`, `IdentityStore`, `MessageRepository`, `MessageDao`. Without `@AndroidEntryPoint` the service's `@Inject lateinit var` fields stay null.

2. `onCreate` is the right place to call `connectWebSocket`. NOT `onStartCommand` — onStartCommand is called on every restart and would re-open a new WS for each restart. onCreate runs once per service instance.

3. The coroutine scope for `handleIncoming` is `CoroutineScope(SupervisorJob() + Dispatchers.IO)` created as a field. On `onDestroy` the scope is `scope.cancel()`'d. NEVER use `GlobalScope` — when the service dies, the coroutines keep running and the next service instance has a different WebSocket. Coroutine leaks across service restarts.

4. The `onMessage` callback is called on OkHttp's internal thread pool, NOT the main thread. The callback must `scope.launch { handleIncoming(text) }` to move to a coroutine context, then parse + persist. Doing the parse on OkHttp's thread blocks the WS.

5. `MessageDao.insert` is `suspend` — Room enforces that all DAO calls run on the IO dispatcher. Calling it from `handleIncoming` (already on IO via `scope.launch(Dispatchers.IO)`) is correct; calling it from a non-suspend context will fail at compile time.

6. `MessageEntity.ciphertext: ByteArray` is stored verbatim. NO plaintext. The Compose UI does `String(msg.ciphertext, Charsets.UTF_8)` for display — that works for Phase 1 (plaintext-as-bytes shim), and Phase 2 swaps it for `RatchetEngine.decrypt(peer, msg.ciphertext)` returning the decrypted ByteArray.

7. The ViewModel's `stateIn` on `observeChat` uses `SharingStarted.WhileSubscribed(5_000)` — 5-second grace after the last collector unsubscribes. This means a rotation or quick back-and-forth navigation doesn't tear down the Room flow. Pure `Eagerly` would keep the DB query live forever (memory leak); pure `Lazily` would re-query every time the screen returns (jank).

**Failure modes to grep for after this wiring lands:**
- `class.*Service` files with no `@AndroidEntryPoint` (Hilt fields stay null)
- `connectWebSocket` calls outside `onCreate` (WS reopened on every restart)
- `GlobalScope.launch` in service code (coroutine leaks)
- `_messages = MutableStateFlow<List<X>>` in screens that bypass `observeChat()` (Room writes are invisible to the UI)
- `MessageRepository` not `@Singleton` (per-ViewModel instances hold their own DB connection pool)

## Reference files used

- `android/podroid/CLAUDE.md` — deep map of Podroid's engine abstraction, boot pipeline, host-bridge vsock
- `android/podroid/build-all.sh` — orchestrates kernel + rootfs + QEMU + APK
- `android/podroid/build-rootfs/Dockerfile.rootfs` — example of cross-compile with qemu-user under the hood
- `android/podroid/gradle.properties` — pinned `podroidQemuVersion`, `podroidKernelVersion`, minSdk 26, arm64 only
- `Containerfile.multiarch` — the per-arch staging pattern
- `.github/workflows/build-images.yml` — multi-arch matrix + manifest list job
