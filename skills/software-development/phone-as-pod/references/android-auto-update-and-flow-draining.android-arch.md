# Android auto-update hardening + Kotlin Flow draining (jackbox TheBox, 2026-08)

Repair lessons from fixing the TheBox self-updater in `jackbox` (mazemaker-mobile).
Three durable patterns: a Flow-draining bug, honest security-model KDoc, and
manifest/APK input hardening. All are general to any Kotlin/Android app that
auto-updates itself or sibling APKs via `PackageInstaller`.

## 1. The `.first()` vs `.collect { }` Flow-draining bug (the big one)

**Anti-pattern** — draining a status-emitting flow with `.first()`:

```kotlin
// WRONG: installUpdate() emits Installing → Success/Failure, but .first()
// cancels the collection after the FIRST emit (Installing), so the coroutine
// is cancelled and downloadApk / verifySha256 / commitSession NEVER run.
runCatching { Updater.installUpdate(ctx, update).first() }
```

`.first()` returns as soon as the first value arrives and **cancels the
downstream collection**. If the flow emits an intermediate status before doing
its real work, `.first()` silently skips all of it. This is a real, easy-to-miss
bug because the code looks fine and nothing crashes — updates just never apply.

**Correct** — drain to completion with `.collect { }`:

```kotlin
runCatching { Updater.installUpdate(ctx, update).collect { } }
```

`.collect { }` consumes every emit to completion (Installing → Success/Failure),
so the side effects (download, checksum verify, commit) actually run.

**Resolution note (no ambiguity error):** `Flow.collect(FlowCollector)` is a
*member* function; Kotlin's `collect { }` lambda SAM-converts to `FlowCollector`.
Members always win over extensions, so adding the explicit
`import kotlinx.coroutines.flow.collect` (the inline `collect(action)` extension)
is **harmless** — it compiles, it just isn't the overload used. Match surrounding
style: if the rest of the codebase calls `.collect { }` without that import (e.g.
MainActivity), an explicit import is optional. Only `.first()`/`.firstOrNull()` on
a status-emitting flow is the bug.

**Pattern to apply anywhere:** any `Flow<Status>` that emits an "in progress"
state before its side effect must be consumed with `.collect {}` (or the side
effect must live in the `flow {}` builder, which it should). `.first()` is only
correct when you genuinely want the first value and to stop — i.e. the flow has
exactly one emit and no downstream work.

## 2. Honest security-model KDoc (no signature)

When an updater has **no signature field** (no crypto signing of the manifest),
the KDoc must say so plainly — "signed-ish" is misleading:

- Integrity = (a) each APK's SHA-256 checked against the value *inside the
  manifest itself* (self-referential, not a trust anchor), and (b) manifest +
  APK fetched over TLS.
- First-ever install therefore **trusts TLS to the manifest host** for both
  authenticity and freshness. No public-key pinning. A hijacked/compromised
  host can mint its own valid-looking manifest.
- State it explicitly: this protects against corruption/transmission errors,
  **not** against a malicious server. Don't overclaim.

## 3. Manifest / APK input hardening

Validate remote input before acting on it:

- **Manifest size cap:** read via a bounded stream (e.g. `readLimited(input,
  256*1024)` that throws `IllegalStateException` if the byte total exceeds the
  cap) instead of `bufferedReader().readText()` (unbounded memory). Use a
  `ByteArrayOutputStream` + fixed chunk loop.
- **https-only apkUrl:** reject any `apkUrl` that doesn't start with
  `https://` (throws `IllegalStateException`) — blocks `http://`, `file://`,
  and scheme smuggling. Do this at parse time in `fetchManifest` so a bad
  entry fails the whole check (caught upstream → empty result).
- **APK size cap pre-download:** `if (remote.sizeBytes > MAX_APK_BYTES)` throw
  before opening the connection. 1 GB = `1_073_741_824L` (keep it a `Long`).
- **Post-download length check:** if `sizeBytes > 0 && out.length() !=
  remote.sizeBytes`, `delete()` the file and throw. Cheap integrity guard that
  catches truncation before the (expensive) SHA-256 pass.

All these throw `IllegalStateException`, which the surrounding
`checkForUpdates` / worker already catches → silent skip, matching the
"never surface an error to the user" robustness contract.

## Worked example paths
- `jackbox/app/src/main/AndroidManifest.xml` — missing `android.permission.INTERNET`
  (add after `REQUEST_INSTALL_PACKAGES`).
- `jackbox/app/src/main/java/dev/mazemaker/thebox/UpdateWorker.kt` — the
  `.first()` → `.collect { }` fix.
- `jackbox/app/src/main/java/dev/mazemaker/thebox/Updater.kt` — KDoc + hardening.
