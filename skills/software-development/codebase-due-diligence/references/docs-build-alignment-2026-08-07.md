# Docs & Build-Script Reality Alignment — mazemaker-mobile, 2026-08-07

Post-audit "AUFGABE H" fix wave: align docs/build scripts with the verified
reality after the 2026-08-07 audit (2 CRITICAL + 15 HIGH). Companion to
`references/mobile-app-audit-2026-08-07.md`. Only 5 files were allowed to
change; everything else was reported, not fixed.

## The 5 changed files

| File | Change |
|---|---|
| `README.md` | Architecture tree rebuilt from real `find` output; Tech-Stack from real build.gradle; MCP section from real tools/endpoints; Security section de-fantasized; Version 1.4.1 |
| `android/README.md` | Same pattern; removed all fantasy files; build section = assembleDebug/assembleRelease/testDebugUnitTest |
| `android/PRODUCTION_CHECKLIST.md` | Updated: 2026-08-07; added post-audit hardening items as done; test count 21→27; QR pairing + pull-to-refresh moved from "Next" to shipped |
| `jackbox/build-box.sh` | `REF[mazemaker]="release/android-1.4.0"` → `"LIVE"` (release carrier is now the live branch) |
| `android/install.sh` | hardcoded `build-tools/35.0.0` → highest installed (`ls "$ANDROID_HOME"/build-tools \| sort -V \| tail -1` + empty guard) |

## Verified current state (facts to trust in future sessions)

- **Release carrier**: branch `feat/thebox-autoupdate`, versionName 1.4.1,
  versionCode 8 (monotonic over 1.4.0/code 7; merged on-device-pod features
  from `release/android-1.4.0`). `release/android-1.4.0` is superseded —
  build scripts must NOT pin it.
- **Real architecture** (`android/app/src/main/java/dev/mazemaker/mobile/`):
  `MainActivity.kt` (no DI framework) + `data/{api,auth,cache,crash,crypto,
  gateway,model,notifications,pairing,preferences,realtime}` + `ui/` with
  `MazemakerViewModel.kt` at ui root (NOT ui/viewmodel/), `Theme.kt` at ui
  root, `ui/navigation/MazemakerNavGraph.kt`, `ui/theme/Glow.kt`, 15 screens.
  Key classes: `GatewayClient`, `HermesRepository`, `MazemakerRepository`,
  `LocalPodHermes`, `LocalPodMcpProxy`, `GatewayCrypto`, `PodWebSocket`,
  `AuthManager`, `PreferencesManager`.
- **Real deps** (android/app/build.gradle): Kotlin 1.9.24, AGP 8.4.2,
  Compose 1.7.6 + material3 1.3.1, Navigation-Compose 2.8.5, Retrofit 2.11.0
  + converter-gson, OkHttp 4.12.0, Gson 2.10.1, coroutines 1.8.1, DataStore
  1.1.1, security-crypto 1.1.0-alpha06, biometric 1.2.0-alpha05, CameraX
  **1.4.2** (1.3.4 BANNED: 4 KB-aligned JNI lib rejected on Android 15+
  16 KB-page devices), ML Kit barcode-scanning 17.3.0. No Hilt/Firebase/
  BouncyCastle. minSdk 26 / targetSdk 34, Java 17.
- **Real MCP surface**: `POST /tools/call` envelope `{ok, tool, result,
  error{code,message,retryable}}`; tools recall/remember/think/graph/stats/
  dream/dream_stats/dream_config/dream_control/supersedes_log/afe_facts/
  diagnose/prune/health/quota/dream_nrem/dream_rem/dream_insight; browse via
  `GET /memory/list`, settings via `GET /pod/settings`. No `/mcp`, no `/sse`
  in the app's Wonderland API. Three transports: direct LAN (:8765), secure
  gateway (cmd:pod proxy, TLS+token+AES), Route-C relay (no SSE passthrough;
  chat via buffered cmd:bridge /chat).
- **Secrets**: auth token + gateway secrets in EncryptedSharedPreferences
  (Keystore master key); plain fallback only on KeyStore failure.
- **Tests**: 27 JVM unit tests, 5 files (GatewayCryptoTest, GatewayClientTest,
  GatewayPairingTest, MazemakerRepositoryTest, PodWebSocketBackoffTest).
  androidTest dir exists but is EMPTY — no instrumented tests.
- **Stale scaffold (finding, not fixed)**: root `package.json` describes an
  Expo/React-Native app that does not exist (no node_modules, no jest tests,
  no app/ dir). It is the source of the old "Android/iOS + Expo" README
  fantasy. Candidate for deletion.

## Fantasy-file list — never reintroduce in docs

McpService.kt, McpRetrofitClient.kt, di/AppModule.kt, MemoryRepository.kt,
NavGraph.kt, MemoryViewModel.kt, UiState.kt, MazemakerApplication.kt,
Typography.kt (root README); McpHttpClient.kt, McpApiImpl.kt,
SettingsRepository.kt, Uicomponents.kt, JRWCrypto.kt (android/README).
Also fake claims: Hilt DI, Firebase Messaging, Bouncy Castle, "iOS app",
"X3DH/Double Ratchet wired in UI" (that layer is JVM-tested only; the wired
crypto is GatewayCrypto AES-256-GCM).

## Verification commands that worked

```bash
bash -n jackbox/build-box.sh && bash -n android/install.sh
# install.sh setup-lines execution (stop before `adb wait-for-device`):
bash -c 'set -u; source <(sed -n "1,9p" android/install.sh); echo "$BUILD_TOOLS"'
# build-box.sh table dispatch test (vars must be pre-set, in script order):
bash -c 'set -euo pipefail; JRWL_REPO=...; MZM_REPO="$(pwd)"; \
  eval "$(sed -n "/^declare -A REPO REF MODULE/,/^NEEDS\[iris\]/p" jackbox/build-box.sh)"; \
  [[ "${REF[mazemaker]}" == "LIVE" ]]'
# anchored version extraction (unanchored matches comments with empty capture):
sed -n "s/^[[:space:]]*versionCode \([0-9]*\).*/\1/p" app/build.gradle
```

## Gotchas hit (all resolved)

1. `set -u` + eval of extracted table block → unset var errors until the
   harness pre-set `JRWL_REPO`/`MZM_REPO` exactly as the real script does.
2. Unanchored `.*versionCode \([0-9]*\).*` matched the comment line
   "Monotonic versionCode so it" with a zero-digit capture → `head -1` empty.
   Anchor with `^[[:space:]]*`.
3. `npm run test` fails (`jest: command not found`) — vestigial Expo
   scaffold, not a real harness; shell-level verification is the honest one.
