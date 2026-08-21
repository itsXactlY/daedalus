# Lint pass + dependency freeze — mazemaker-mobile 2026-08-07

Closing gate of the production-readiness fix campaign (after 3 fix waves + release
merge + version bump 1.4.1/code 8). Operator order: "biglint error in der app, etc.
vollständig übernehmen, autonom."

## What the pass produced

- `./gradlew :app:lintDebug` → 0 Errors, 25 Warnings, 2 Informations.
- After triage: **17× GradleDependency (frozen, documented), 1× OldTargetApi
  (documented freeze)** — zero actionable code issues remain. Lint "green enough".

## Issue-by-issue

| Issue | Fix | Verdict |
|---|---|---|
| OldTargetApi (build.gradle:26) | compileSdk+targetSdk 34→35 together (targetSdk never > compileSdk); comment documents the 35-freeze vs 36 | real fix + documented freeze |
| GradleDependency ×17 | only appcompat 1.7.0→1.7.1 (pure patch); Compose 1.7.6/Kotlin 1.9.24/AGP 8.4.2 frozen — major bumps break the tuned set | frozen by decision |
| ObsoleteSdkInt (mipmap-anydpi-v26) | `git mv` → `mipmap-anydpi` (minSdk 26 makes -v26 redundant) | real fix |
| DataExtractionRules (Manifest) | `tools:targetApi="31"` + `android:fullBackupContent="false"` (API-26–30 gap) | real fix |
| TrustAllX509TrustManager (GatewayPairing:143-144) | @SuppressLint — TOFU fetch-server-cert trusts all ON PURPOSE; real anchor is sha256(SPKI)==fp check in resolve() right after | suppress + reason |
| CustomX509TrustManager (GatewayClient composite) | @SuppressLint — composite delegates to real System + ISRG stores; Lint can't see delegation | suppress + reason |
| InsecureBaseConfiguration (network_security_config.xml) | documented trade-off (pod speaks plaintext HTTP in LAN trust boundary, no fixed domain) — comment only | suppress by comment |
| AutoboxingStateCreation (ThinkScreen:46, PullToRefresh:28) | `mutableLongStateOf(0L)` / `mutableFloatStateOf(0f)` | real fix |

## The Gradle stale-cache trap (bit TWICE)

Sequence: crew moved `res/mipmap-anydpi-v26` → `res/mipmap-anydpi` (git mv). Then:

1. First build after the move: `AAPT: error: resource mipmap/ic_launcher not found`
   → looked like the rename broke resource resolution.
2. `git add` rename + `./gradlew --stop` + retry with `--rerun-tasks` →
   `Failed to create MD5 hash for file: .../kotlin-classes/debug/...class
   (Datei oder Verzeichnis nicht gefunden)` + `Cannot access output property
   'destinationDirectory'` → classic stale incremental state.
3. Real fix: `./gradlew --stop` + `./gradlew clean` + NORMAL build (no
   `--rerun-tasks`) → BUILD SUCCESSFUL, 27/27 tests, lint clean.

Lesson: after any build-visible rename/move, a `--rerun-tasks`-forced compile
failing on missing MD5 hashes means CLEAN, not code fix. Verify with clean first.
