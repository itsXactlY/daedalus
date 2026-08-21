# PodWebSocket lifecycle + Gradle verification (mazemaker-mobile client)

Applies to the mazemaker-mobile Android client's realtime layer:
`android/app/src/main/java/dev/mazemaker/mobile/data/realtime/PodWebSocket.kt`
(OkHttp `WebSocketListener` wrapping the pod's `ws://<host>/ws` stream).

## WebSocket reconnect-lifecycle bug class (H2 / M10)

Symptom: the WS can't be turned off — after `disconnect()` it still reconnects,
and switching hosts produces a duplicate connection to the OLD host. Root cause:
`onClosed`/`onFailure` scheduled `connect(host)` with the CAPTURED `host`
parameter and no way to know the user had called `disconnect()`.

Fix pattern (minimal-invasive, keeps all public signatures):
- Add a `@Volatile private var closed = false` and a `private var generation = 0`.
- In `connect(host)`: `generation++; closed = false; val myGen = generation`,
  then `webSocket?.close(1000, "Replacing connection")` before opening the new
  socket (M10: don't leak a running socket).
- In the listener callbacks, capture `myGen` and guard every reconnect with
  `!closed && currentHost == host && myGen == generation`. Never call
  `connect(host)` with the captured param — call
  `connect(currentHost ?: return@launch)`.
- In `disconnect()`: `closed = true; generation++` BEFORE nulling the socket, so
  any in-flight reconnect callback is invalidated (generation bump is the
  "cancel all queued reconnects" signal).
- OkHttp `onClosed` fires when the socket actually closes, which can be AFTER a
  new `connect()` already ran. The generation check is what prevents that stale
  `onClosed` from killing/reconnecting the new cycle.

## Plaintext-URL hardening (H3)

- Blank host → bail with `state="failed"`/`"disabled"` instead of building the
  broken `ws:///ws` (that string parses as host-less).
- If host is an `https://` origin, build `wss://`:
  `val scheme = if (host.startsWith("https://")) "wss" else "ws"`
  then strip the scheme prefix before interpolating.
  If `certPem`/token pinning is unavailable, scheme-by-prefix is the minimal
  safe change.

## HTTP-status handling (M11)

- `onFailure` receives `response?.code`. Treat `401` as
  `_wsAvailable=false; state="auth_required"; return` — same terminal handling
  as `403`/`404` (`unavailable`). Do NOT let a 401 fall through into the
  `retryCount++` network-error path (previously: 6 useless retries).
- Keep the `asJsonObject` parse failure in `onMessage` as a logged `catch` — do
  not silently drop malformed frames.

## Verification workflow for THIS Gradle project

There is NO `package.json` / `npm test` — it's a Gradle Android project
(`android/` dir with `gradlew`). `npm run test` does not exist. Use:

```bash
cd <repo>/android
./gradlew :app:compileDebugKotlin          # type-check the changed file
./gradlew :app:testDebugUnitTest --tests "dev.mazemaker.mobile.data.realtime.*"
```

- Unit tests live under `app/src/test/java/...`; the WS backoff test is
  `PodWebSocketBackoffTest.kt`. It only covers the pure `backoffDelayMs()`
  function — lifecycle changes are exercised by compile + OkHttp/MockWebServer
  tests, not by that backoff unit test.
- The `:app:compileDebugKotlin` task type-checks the WHOLE module; if an
  UNRELATED file (e.g. `PreferencesManager.kt`) has pre-existing errors, the
  build fails but your file can still be clean. Grep the output for your file
  name + for `e: ` errors and attribute them correctly.
- **Multi-agent dirty tree**: check `git status --short` first — in a
  concurrently-modified worktree (parallel subagents), errors in files you did
  NOT touch belong to other agents' in-flight edits (e.g. a model file made
  nullable while a screen still expects non-null). Don't chase them; grep the
  error list for YOUR file only.
- **Never run two `./gradlew` builds in parallel**: daemon contention produces
  a bogus `e: Daemon compilation failed: null` with no real errors. Serialize
  builds; add `--no-daemon` for one-shot verification runs.
- **`UP-TO-DATE` is not fresh evidence**: `compileDebugKotlin` short-circuits
  with `UP-TO-DATE` when inputs are unchanged — fine for a quick check, but a
  verifier demanding proof of a fresh compile needs
  `./gradlew :app:compileDebugKotlin --rerun-tasks` (task line WITHOUT the
  `UP-TO-DATE` marker + `BUILD SUCCESSFUL` = the evidence). Same for tests:
  `testDebugUnitTest` can report `UP-TO-DATE` even after source changes —
  force a real run with `./gradlew :app:testDebugUnitTest --rerun`, then sum
  `tests=`/`failures=`/`errors=` from
  `app/build/test-results/testDebugUnitTest/*.xml`.
- Stale `app/build/tmp/kotlin-classes/debug` locks from a previous daemon cause
  a bogus `IOException: Unable to delete directory ... kotlin-classes/debug`
  failure. Fix: `./gradlew --stop && rm -rf app/build/tmp/kotlin-classes/debug`.
- Sibling daemon-lock failure (2026-08-07): `Could not delete
  '.../app/build/kotlin/compileDebugKotlin/cacheable/caches-jvm'` after a
  "multiple Kotlin daemon sessions" warning. `./gradlew --stop` alone can fail
  on a wedged daemon — kill the PID (`pgrep -fa GradleDaemon` → `kill <pid>`),
  `rm -rf app/build/kotlin/compileDebugKotlin/cacheable/caches-jvm`, rebuild.
- **Do NOT `pkill -f 'KotlinCompileDaemon'`** — the pattern matches the shell's
  OWN command line, killing the shell silently (exit -15). Always `pgrep -fa`
  first, then kill the specific PIDs.

## Differential debugging: hand-built kotlinc harness vs real toolchain

To type-check a single Kotlin file in isolation with a hand-built classpath
(`kotlin-compiler-embeddable` + stdlib + trove4j + deps + `android.jar`), the
IR codegen can throw `Backend Internal error: Exception during IR lowering` in
an UNMODIFIED method (e.g. the primary constructor storing a `CoroutineScope`).
This is a classpath/metadata artifact of the manual harness, NOT a source bug.

Prove it's environmental by compiling the ORIGINAL file from git with the
IDENTICAL harness:
```bash
git show HEAD:path/to/File.kt > /tmp/orig.kt
# run the same kotlinc command on /tmp/orig.kt
```
If the original reproduces the identical backend error, the harness is at
fault — trust the project's own `./gradlew :app:compileDebugKotlin` as the
authoritative signal instead. (Attempting `npm test` or chasing the isolated
IR-lowering error would have wasted turns.)
