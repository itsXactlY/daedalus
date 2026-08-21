# Repository / Cache / Offline-Layer Hardening (the "E-task" pattern)

Hardening playbook for the mazemaker-mobile APK's data layer
(`MazemakerRepository.kt`, `data/cache/MemoryCache.kt`,
`data/cache/OfflineInterceptor.kt`, `data/model/McpModels.kt` — applied
2026-08-07, Aufgaben E1–E7). Each fix is a reusable class-level technique.
Sibling of `kotlin-gateway-client-hardening.android-arch.md` (the F-task:
gateway/pairing/HermesRepository). Note: F already documents `resultCatching`
— E applies it to the Mazemaker side AND to fallback catch-blocks (see §2).

## 1. Idempotency-aware retry in callTool (E1)

Retrying a *write* after a 500 that actually committed server-side duplicates
the write. Rule: retries only for idempotent tools.

```kotlin
private suspend fun callTool(
    toolName: String,
    arguments: Map<String, Any> = emptyMap(),
    slow: Boolean = false,
    idempotent: Boolean = true          // NEW param, default true
): JsonElement = withContext(Dispatchers.IO) {
    val client = if (slow) longApi else api
    var lastError: Exception? = null
    val maxAttempts = if (idempotent) 3 else 1
    repeat(maxAttempts) { attempt ->
        try {
            val response = client.callTool(ToolCallRequest(name = toolName, arguments = arguments))
            val body = response.body()
            if (response.isSuccessful && body != null && body.ok) {
                return@withContext body.result ?: throw PodException("Tool $toolName returned no result")
            }
            val err = body?.error
            lastError = PodException(
                err?.message?.ifBlank { null } ?: "Tool $toolName failed (HTTP ${response.code()})",
                code = err?.code
            )
            val retryable = response.code() in 500..599 || err?.retryable == true   // M13: 5xx range, not just 500
            if (idempotent && retryable && attempt < maxAttempts - 1) {
                Log.w(TAG, "... retrying (attempt ${attempt + 1}/$maxAttempts)")
                kotlinx.coroutines.delay(1000L * (attempt + 1))
            } else {
                throw lastError!!
            }
        } catch (e: IOException) {
            lastError = PodException("Pod unreachable: ${e.message ?: e.javaClass.simpleName}")
            if (idempotent && attempt < maxAttempts - 1) { /* same backoff */ } else throw lastError!!
        }
    }
    throw lastError ?: PodException("Tool $toolName failed after $maxAttempts attempt(s)")
}
```

Call-site mapping (writes → `idempotent = false`): `remember`,
`prune` (`idempotent = dryRun` — dryRun=true is a read), `dreamConfigSet`,
`dreamControl`, `dream`. Everything else keeps the default. The error DTO
(`ToolError`) already carries `retryable: Boolean = false`, so
`err?.retryable == true` compiles against the existing model.

Note: the offline stub returns HTTP 200 with `ok:false` +
`error.retryable:true`, so idempotent tools now burn all 3 attempts
(1s+2s real delays) before failing offline. That is intended per spec
(cap at 3), but expect slower offline failure UX for reads.

## 2. `resultCatching` + the fallback-catch trap (E2)

`kotlin.runCatching` catches `Throwable` including `CancellationException`.
Replace with an inline helper; inline (not `suspend () -> T`) so the lambda
body can still call suspend functions from a suspend caller:

```kotlin
private inline fun <T> resultCatching(block: () -> T): Result<T> =
    try { Result.success(block()) }
    catch (e: kotlinx.coroutines.CancellationException) { throw e }
    catch (e: Exception) { Result.failure(e) }
```

**Trap:** `CancellationException` extends `Exception` — a plain
`catch (e: Exception)` inside a fallback block ALSO swallows cancellation.
Every try/catch fallback added for offline support must rethrow it FIRST:

```kotlin
} catch (e: kotlinx.coroutines.CancellationException) {
    throw e
} catch (e: Exception) {
    val fallback = cache?.getCachedMemories()
    if (fallback != null) { Log.w(TAG, "... offline fallback ..."); fallback } else throw e
}
```

Also update `return@runCatching` labels to `return@resultCatching` when
renaming (browse/graph/stats/podSettings use them).

## 3. SQLite: create ALL tables in init(); never DELETE a maybe-missing table (E3)

`clear()` ran `DELETE FROM cache_meta` while `cache_meta` was only created
lazily by `ensureMetaTable()` — crash (`no such table`) on first clear.
Fix: create every table in `init()` (idempotent `CREATE TABLE IF NOT EXISTS`
including `cache_meta`), keep `ensureMetaTable()` as the idempotent rest.

## 4. Single ReentrantLock around every public SQLite method (E4)

SQLiteDatabase is not thread-safe; UI thread and background sync hit the
cache concurrently. Minimal-invasive fix: one `ReentrantLock` +
`kotlin.concurrent.withLock` around every public method (cacheMemories,
getCachedMemories, cacheStats, getCachedStats, clear, getCacheAge,
getCacheSize, getCacheHits/Misses, incrementHits/Misses,
cacheMemoriesWithTimestamp). MUST be `ReentrantLock` because public methods
call each other (incrementHits → getCacheHits; cacheMemoriesWithTimestamp →
cacheMemories) — a plain mutex would self-deadlock.

## 5. Offline cache fallback in browse/recall/graph/stats (E5)

Never let the UI see "pod unreachable" when the disk cache has data:

- `browse()`: `catch (e: IOException)` → `cache?.getCachedMemories()` →
  `return@resultCatching fallback` (log `offline fallback`), else rethrow
  the PodException.
- `recall()`: catch ALL exceptions around parse+callTool (per §2 rethrow
  order) → `cache?.getCachedMemories()`.
- `graph()`/`stats()`: catch → `cache?.getCachedStats("graph"|"stats")` →
  `gson.fromJson(cached, GraphOverview::class.java)?.let { ... return@resultCatching it }`,
  else `throw e` (original error preserved if cache missing or unparseable).
- No cache-age check — keep it simple, fallback is better than empty.

## 6. Offline stub markers + path precision (E6)

Stubs must be distinguishable from genuine empty data:
- `/memory/list` stub gains `"offline":true` (keep `pod_id:"offline"` for
  `/pod/settings`, `ok:false` + `error.code:"offline"` for `/tools/call`).
- Path check `startsWith("/memory/")` → `startsWith("/memory/list")` —
  broad prefixes can shadow later, more specific routes.

## 7. Gson reflects null into non-null fields → String? + fix usage sites (E7)

Gson sets `null` into `String` fields when JSON explicitly has `null`,
bypassing the `= ""` default → NPE at usage sites like `.take(300)`.
Rejected options: TypeAdapter<String> null→"" (fiddly with a
test-injected gson), init-block normalization (impossible for `val`).

Chosen fix (grep-driven, compile errors are the checklist):
1. In the data classes, change ONLY the string fields that screens touch:
   `MemoryResult.content/label/created_at`, `MemoryDetail.content/label/created_at`,
   `ThinkResult.content/label`, `AfeFact.content/label` → `String? = null`.
2. Grep the whole `src/main/java` for `.content` / `.label` / `.created_at`
   and fix every usage on those types:
   - `.take(N)` → `(x ?: "").take(N)`
   - `.isNotBlank()` → `!x.isNullOrBlank()`; `.ifBlank {}` → `x.orEmpty().ifBlank {}`
   - `Text(x)` / non-null params → `x ?: ""`; `formatCreatedAt(x)` →
     `x.orEmpty()`
   - string interpolation `"${f.label}"` compiles but prints "null" → `.orEmpty()`
3. Don't touch Hermes DTOs (separate task) and don't touch already-safe
   chains like `topFact?.label?.removePrefix(...) ?: ""`.
4. Writer side: `stmt.bindString(n, m.label ?: "")` in MemoryCache — a
   nullable field no longer type-checks into `bindString`.

## Verification notes

- `MazemakerRepositoryTest.kt` (app/src/test) covers recall/graph/stats/dream/
  browse/get with captured wire JSON — the authoritative regression net.
- The 502-test (`httpError = 502`) now exercises the new 5xx retry path:
  callTool runs on `Dispatchers.IO`, so `runTest` virtual time does NOT skip
  the retry delays — the test still passes but takes ~3s longer. Expected.
- Forced fresh runs: `./gradlew :app:testDebugUnitTest --rerun` (see
  `podwebsocket-lifecycle-and-verification.android-arch.md` for the full
  project verification workflow).
