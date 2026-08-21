# Mobile/Android Code Audit — field lessons (2026-08-07, mazemaker-mobile)

Second application of the parallel-readonly-audit methodology (see
parallel-readonly-audit-2026-08-07.md) — this time on an Android/Kotlin + APK
installer + iOS SPM + TypeScript monorepo instead of a Python backend. The
HOCH/RUNTER/INTEGRATION data-flow split transfers cleanly; this file records
what the "engines" become on mobile and which new checks paid off.

## Adapting the stream split to an Android/mobile monorepo

| Stream | Direction | Files | Focus |
|--------|-----------|-------|-------|
| HOCH (bottom-up) | Persistence → API → Crypto | data/ layer: SQLite cache, DataStore, EncryptedSharedPreferences, Retrofit/OkHttp clients, AES-GCM envelope, gateway TLS pinning, auth, pairing, websocket | storage-at-rest consistency, interceptor chains, retry reachability, TLS trust decisions, token handling |
| RUNTER (top-down) | Activity → ViewModel → Screens | MainActivity, ViewModel (ALL state), screens, navigation, theme | state leaks, error paths, lifecycle, silent fallbacks, "dumb screens" claim vs reality |
| INTEGRATION (cross-layer) | Installer + other platforms + tooling | jackbox installer APK + auto-update, iOS SPM, TS src/, build scripts, Gradle/manifests, docs-vs-code, git branch/worktree topology, secrets history | update-pipeline security, dead code on other platforms, release coordination, "README lies" at scale |

Workers got exact file lists + line counts, the project's own philosophy quote
as lens, and "report EVERY issue, even LOW" — same brief requirements as the
original reference.

## New audit checks that paid off (all verified by the main session)

1. **Storage-encryption consistency check.** The app encrypts the pod token
   (EncryptedSharedPreferences in AuthManager) but stores the GATEWAY token —
   the secret for the encrypted gateway channel — in PLAINTEXT DataStore
   (PreferencesManager). Same class of secret, two storage mechanisms, and the
   project's own comments claimed "stored encrypted". Rule: inventory WHERE
   each secret lives (EncryptedSharedPreferences vs DataStore vs plain
   SharedPreferences) and diff against the project's security claims. Cheap
   grep: `grep -rn "stringPreferencesKey\|GATEWAY_TOKEN"` + compare with
   `EncryptedSharedPreferences`.

2. **Interceptor-swallowed retry = dead retry path.** OfflineInterceptor
   catches every IOException and returns HTTP 200 stubs with
   `ok:false`/`retryable:true`. The repository's retry loop only retries on
   `code == 500`, so the IOException retry branch is unreachable and the
   `retryable:true` flag is never evaluated. Rule: when auditing retry or
   fallback logic, check whether an interceptor/middleware upstream already
   converted the exception into a success-coded response — the retry path may
   be dead code while looking correct.

3. **SQLite table-creation ordering bug.** `MemoryCache.clear()` issues
   `DELETE FROM cache_meta`, but the table is only created lazily by
   `ensureMetaTable()`, which `clear()` never calls → `SQLiteException: no
   such table` on fresh installs if clear() runs before any metadata access.
   Rule: for every SQL statement in a class, verify the table's creation path
   runs first (or is idempotent-guarded in the same code path).

4. **Worktree/branch topology is an INTEGRATION finding.** `git worktree list`
   revealed a second checkout on `feat/hermes-upstream-config` containing
   files (LocalPodHermes, LocalPodMcpProxy, HermesUpstreamConfig) ABSENT from
   the main checkout. `git merge-base --is-ancestor` proved: neither feature
   branch is merged into origin/main (main = docs only), and the release
   branch `release/android-1.4.0` (versionCode 7) is NOT an ancestor of the
   live checkout (versionCode 6). Findings: divergent parallel work lines,
   unmerged release, version drift between what the build script bundles and
   what the checkout contains. Commands: `git worktree list`, `git merge-base
   --is-ancestor <tip> <branch>`, `git log --oneline --left-right
   A...B`, `git diff --name-only A B -- <path>`.

5. **Dormant crypto: wires-not-wired mitigates severity.** `src/crypto/
   jrwl_crypto.ts` implements fake X3DH (ECDSA keys instead of ECDH, a zero
   array as "placeholder for combined DH output", double-HMAC instead of HKDF)
   and iOS `X3DH.swift` uses `kSecAttrIsPermanent: false` (keys do not survive
   restart) — BUT `grep -rn "import"` showed nothing imports either. Dead code
   → severity downgraded, but flagged as a bomb if ever wired. Rule: grep for
   importers before assigning CRITICAL to bad crypto. Same check killed a
   would-be CRITICAL on `WebSocketService.swift` (raw `NWConnection(.tcp)`
   is not a WebSocket — but it's never called).

6. **"signed-ish" auto-update manifest without a signature.** The installer's
   Updater fetches an unsigned manifest over HTTPS and verifies the APK
   SHA-256 against a hash FROM THE SAME manifest — no code-signing check, no
   manifest signature, `apkUrl` fully attacker-controlled once the manifest
   host is compromised. Comment said "signed-ish"; reality is HTTPS +
   checksum only. Rule: audit update pipelines for where the trust anchor
   actually lives; a self-referential hash is not authentication.

7. **Docs-vs-code at scale (cheap proof).** README architecture section
   described 9 files that don't exist (McpService.kt, McpRetrofitClient.kt,
   AppModule.kt, MemoryRepository.kt, NavGraph.kt, MemoryViewModel.kt,
   UiState.kt, MazemakerApplication.kt, Typography.kt). One-liner loop:
   `for f in <names>; do find android/app/src/main -name "$f" | grep -q . &&
   echo EXISTIERT || echo "FEHLT (README lügt)"; done`. Confirms the existing
   "READMEs lie" pitfall and shows the cheap way to prove it.

8. **Split-brain settings storage.** `biometric_enabled` lives in plain
   SharedPreferences named "mazemaker_settings" while the rest of settings
   live in DataStore with the SAME name — two separate stores; the reset
   handler clears only DataStore, leaving the biometric flag behind.

## Process note

While the 3-stream crew ran (~5-6 min), the main session independently read
the highest-risk files (crypto, auth, pairing, gateway client, installer
updater, websocket, TS/iOS crypto). This parallel-verification window is cheap
and paid off: the plaintext-token and dead-retry findings were found before
the crew reported, giving the consolidated report a verified-findings section
independent of sub-agent self-reports. Then the crew CRITICALs were verified
against these notes (same as the original reference's §5).

Reports go in `benchmarks/audit/` per the mazemaker-pro convention; the
monorepo had no such dir, so it was created.
