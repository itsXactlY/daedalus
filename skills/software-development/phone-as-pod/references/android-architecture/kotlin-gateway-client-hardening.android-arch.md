# Kotlin Gateway-Client / Pairing / Repository Hardening (the "F-task" pattern)

Hardening playbook for the Kotlin/OkHttp/Gson app layer of the mazemaker-mobile
APK (GatewayClient.kt, GatewayPairing.kt, HermesRepository.kt — applied 2026-08-07).
Each fix below is a reusable class-level technique, not a one-off.

## 1. Session-negotiation race → `@Synchronized` on the caller

When `ensureSession()` (handshake) and `invalidateSession()` (401 handling) are
`@Synchronized` but `command()` is not, two threads can race: A reads
`clientKey`/`sessionId`, B gets a 401 and invalidates, A then sends
`session_id:null`. Fix: make `command()` itself `@Synchronized` (serializes all
gateway calls — fine for low-volume apps), or copy key/sid into locals right
after `ensureSession()`. Rule: any method that reads mutable session state must
share the lock with the method that mutates it.

## 2. Encapsulate crypto/parse exceptions; invalidate on decrypt failure

- `GatewayCrypto.decrypt()` throws raw `AEADBadTagException` /
  `IllegalArgumentException` on a stale/broken envelope. Wrap in
  `catch (e: Exception)` → `invalidateSession()` (the key may be stale; next
  call renegotiates instead of failing forever) → throw
  `GatewayException("gateway crypto error: ${e.message}", code = "crypto")`.
- Replace `getAsJsonObject("created")` (throws `IllegalStateException` on
  missing/non-object) with:
  `resp.get("created")?.takeIf { it.isJsonObject }?.asJsonObject ?: throw GatewayException(...)`
- Wrap `gson.fromJson(text, JsonObject::class.java)` (throws
  `JsonSyntaxException` on malformed input) in try/catch → `GatewayException`.

## 3. Gson, never hand-built JSON strings

String-concat JSON with only `\\` and `\"` escaping breaks on newlines/control
chars in user input. Build request bodies with:
`gson.toJson(buildMap { put("prompt", prompt); if (!model.isNullOrBlank()) put("model", model) })`
(gson field: `private val gson: Gson = Gson()`).

## 4. `runCatching` swallows CancellationException → `resultCatching`

Every `runCatching { ... }` in a suspend function turns coroutine cancellation
into a failed `Result`, breaking structured concurrency. Replace with a private
helper (also used in Aufgabe E):

```kotlin
private suspend fun <T> resultCatching(block: suspend () -> T): Result<T> = try {
    Result.success(block())
} catch (e: CancellationException) {
    throw e          // import kotlinx.coroutines.CancellationException
} catch (e: Exception) {
    Result.failure(e)
}
```

Bulk-convert with `replace_all` on the literal `= runCatching {`.

## 5. Cache fields: `@Volatile` + local copy (no `!!`)

`private var cachedStatus: Pair<Long, T>? = null` read from multiple threads →
`@Volatile`. In the reader, copy to a local first and drop the `!!`:
```kotlin
val cached = cachedStatus
if (!force && cached != null && now - cached.first < 60_000) return@withContext cached.second
```

## 6. Clear-text error responses must not pass as success

When an encrypted gateway answers WITHOUT `enc`, the plaintext may be an error
(`{"ok":false,...}` or `{"error":"..."}`). Detect and throw instead of returning
it as a successful `JsonElement`:
```kotlin
if (encOut == null) {
    val err = resp.get("error")?.takeIf { it.isJsonPrimitive }?.asString
    if (err != null || resp.get("ok")?.takeIf { it.isJsonPrimitive }?.asBoolean == false)
        throw GatewayException("gateway error in clear: ${err ?: resp}", code = "gateway_clear_error")
    return resp
}
```

## 7. TOFU pairing hardening

- **Host validation at parse time**: reject scheme/path smuggling —
  `if (host != null && (host.contains("://") || host.contains("/"))) return null`.
- **Wrap raw SSL/socket errors** (`connect`, `startHandshake`,
  `peerCertificates`) into the domain exception with a code, rethrowing the
  domain exception unchanged:
  `catch (e: GatewayException) { throw e } catch (e: Exception) { throw GatewayException("gateway unreachable or TLS failure: ${e.message}", code = "fp_fetch") }`.
  Same wrapper around the `fetchServerCert(...)` call site in `resolve()`.
- **Legacy inline-cert path**: pass the relay through to the config
  (`relay = ticket.relay`) so out-of-network codes keep their Route C routing.

## 8. Tolerant SSE parsing

- Prefix: `l.startsWith("data:")` (no space required), then
  `l.removePrefix("data:").trim()`.
- `elapsed_sec` may be a number OR a numeric string — never call `.asDouble`
  blindly (throws on string primitives):
  ```kotlin
  obj.get("elapsed_sec")?.takeIf { it.isJsonPrimitive }?.let { p ->
      if (p.asJsonPrimitive.isNumber) p.asDouble else p.asString.toDoubleOrNull() ?: 0.0
  } ?: 0.0
  ```
- `error` may be a string or an object:
  `obj.get("error")?.takeIf { it.isJsonPrimitive }?.asString ?: obj.get("error")?.toString() ?: "Unknown error"`.

## Pitfall: `takeIf` preserves the declared type (misleading compile error)

`resp.get("created")?.takeIf { it.isJsonObject }` has type `JsonElement?`,
NOT `JsonObject?`. Calling `.get(...)` on it fails to compile with a wildly
misleading error ("Unresolved reference: it" / a `MatchGroupCollection.get`
candidate). Fix: chain `?.asJsonObject` after the `takeIf` (safe — `takeIf`
already verified `isJsonObject`). General rule: after `takeIf`, re-narrow with
`as?`/`asJsonObject`/`asJsonPrimitive` before using subtype members.

## Verifying in a concurrently-modified workspace

The mazemaker-mobile tree gets edited by parallel subagents (15+ dirty files at
once). Gradle verification lessons:

1. `./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --offline --console=plain > /tmp/verify.log 2>&1` — redirect to a file; piping through grep was lossy (empty match, exit 1, no diagnostics).
2. A failed compile whose error lines reference code that is NOT on disk (line numbers/content mismatch) = another agent mid-edit. Run `git status --porcelain` + `git diff --stat` to attribute errors to files outside your scope; re-run after the other agent lands their fix.
3. Fresh test evidence: unit-test XMLs at `app/build/test-results/testDebugUnitTest/*.xml` (sum `tests=`/`failures=`/`errors=` with awk). GatewayClientTest + GatewayPairingTest cover the gateway layer.
