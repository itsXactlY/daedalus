# Lint-Suppression Documentation (B-task): silencing deliberate warnings with rationale

## When to use
A task says "document deliberate lint decisions — do NOT change the logic, add
`@SuppressLint` + a justification so lint is quiet AND the next dev sees why."
Common targets: custom X509 trust managers (TOFU, composite trust), deliberate
cleartext in network_security_config.

## The three deliberate decisions (mazemaker-mobile, 2026-08-07)

1. **GatewayPairing.kt `fetchServerCert` — TOFU trust-all**
   The empty `checkServerTrusted`/`checkClientTrusted` methods exist ON PURPOSE:
   the one-shot socket trusts anything only to READ the presented cert off the
   wire; the REAL trust decision is `sha256(SPKI) == fp` against the QR pairing
   code right after. Suppress BOTH IDs, with a `//` comment above the annotation:
   ```kotlin
   @SuppressLint("TrustAllX509TrustManager", "CustomX509TrustManager")
   private fun fetchServerCert(...)
   ```
2. **GatewayClient.kt `systemPlusIsrgContext` — composite trust**
   Tries the SYSTEM store first, falls back to bundled ISRG roots (old Android
   API 29 lacks the 2026 LE hierarchy CF serves). Both delegates are real
   stores, so lint's `CustomX509TrustManager` is a false positive — lint can't
   see the delegation. `@SuppressLint("CustomX509TrustManager")`.
3. **res/xml/network_security_config.xml — cleartext**
   Deliberate (LAN trust boundary, no fixed domain for a domain-config).

## Hard rules

- **Kotlin**: `@SuppressLint("Id1", "Id2")` directly above the function, with a
  `//` rationale comment between the KDoc and the annotation. Add
  `import android.annotation.SuppressLint` (alphabetically first import).
- **XML: a comment alone does NOT silence lint.** You must add
  `xmlns:tools="http://schemas.android.com/tools"` on the root element AND
  `tools:ignore="InsecureBaseConfiguration"` on the offending element
  (`<base-config>`). Do both: the comment documents, tools:ignore silences.
- **Never touch logic** — annotations/comments only. Prove it with
  `git diff -- <files>` and confirm the diff is purely additive annotations.

## Verification (the real proof, not just "build passed")

```bash
cd android && ./gradlew :app:lintDebug --console=plain   # BUILD SUCCESSFUL
grep -ci "TrustAllX509TrustManager\|CustomX509TrustManager\|InsecureBaseConfiguration" \
  app/build/reports/lint-results-debug.txt    # → 0 = suppressions work
grep -E "GatewayPairing|GatewayClient|network_security_config" \
  app/build/reports/lint-results-debug.txt    # → absent = no new findings in your files
```

## Gradle pitfalls on this path

- **Killed daemon mid-build** ("Gradle build daemon has been stopped: stop
  command received" right after `> Task :app:compileDebugKotlin`) → the compile
  never finished. Rerun with `./gradlew --stop` then `--no-daemon`.
- **Stale lint partial results**: after an interrupted lint run,
  `lintAnalyzeDebug` fails with Gradle state-tracking error
  `NoSuchFileException .../app/build/intermediates/lint_partial_results/debug/lintAnalyzeDebug/out/lint-definite.xml`
  — NOT a code error. Fix: `rm -rf app/build/intermediates/lint_partial_results`
  then rerun.
- **Attribution before blame**: an AAPT failure ("resource mipmap/ic_launcher
  not found") can come from a pre-existing dirty tree (e.g. staged renames of
  mipmap files while the manifest still references them), not from your edit.
  Run `git status --short` + `git diff -- <your 3 files>` to prove your diff is
  annotation-only before touching anything outside your task scope. If the
  failure is pre-existing, note it and verify your change in isolation
  (`compileDebugKotlin` + direct resource check) instead of "fixing" it.

## Related
- `references/android-architecture/kotlin-gateway-client-hardening.android-arch.md` —
  the same trust managers' runtime hardening (F-task); this reference documents
  their lint suppressions.
- `references/android-architecture/podwebsocket-lifecycle-and-verification.android-arch.md` —
  sibling Gradle verification notes (`--no-daemon`, dirty-tree attribution).
