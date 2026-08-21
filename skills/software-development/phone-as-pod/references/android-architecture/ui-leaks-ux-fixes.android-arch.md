# UI-Leaks + UX-Fixes (G-task, 2026-08-07) — Compose screen fixes for mazemaker-mobile

Task-letter session G (G1–G6), only 5 files touched: CameraX leak + crash
safety (QrScannerScreen), biometric re-lock (MainActivity), stale sessions
panel (HermesScreen), premature "LAST APPLIED" stamp (DreamConfigScreen),
form-clear-on-failure (RememberScreen).

## G1/G2 — CameraX cleanup in a composable (async provider)

`ProcessCameraProvider.getInstance()` resolves ASYNC via `future.addListener`.
By the time the listener fires, the composable may be gone — a synchronous
`provider.unbindAll()` is impossible in the factory, so the camera stays bound
and the analyzer executor thread leaks. Pattern that works (QrScannerScreen.kt):

```kotlin
val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
val providerRef = remember { AtomicReference<ProcessCameraProvider?>(null) }
val disposed = remember { AtomicBoolean(false) }

DisposableEffect(Unit) {
    onDispose {
        disposed.set(true)
        providerRef.get()?.unbindAll()
        analysisExecutor.shutdown()
    }
}
```

In the future listener: bail if disposed BEFORE binding, stash the provider in
providerRef, and wrap the WHOLE body in runCatching — `future.get()` throws
ExecutionException/InterruptedException and ML Kit client setup can throw too;
uncaught = app crash (G2):

```kotlin
future.addListener({
    if (disposed.get()) return@addListener
    runCatching {
        val provider = future.get()
        providerRef.set(provider)
        // ... Preview, BarcodeScanning.getClient, ImageAnalysis, setAnalyzer ...
        provider.unbindAll()
        provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
    }.onFailure { e -> Log.e("QrScannerScreen", "camera init failed", e) }
}, ContextCompat.getMainExecutor(ctx))
```

onDispose order matters: set `disposed` FIRST (races the pending listener),
then `unbindAll()`, then `shutdown()`.

## G3 — Biometric re-lock: observer placement vs conditional composition

Original bug: the `DisposableEffect(lifecycleOwner)` sat INSIDE
`if (authenticated) { ... }`. When ON_STOP set `authenticated = false`, the
gate uncomposed and the observer was disposed — so ON_RESUME never re-triggered
the prompt. **Rule: any lifecycle observer that must fire while the gate is
closed lives OUTSIDE the gate.**

Structure that works (MainActivity):

- `var promptShowing by remember { mutableStateOf(false) }` — double-prompt guard.
- Local `fun triggerBiometricPrompt()` in setContent: bails if
  `!biometricEnabled || authenticated || promptShowing`, else calls an
  extracted `showBiometricPrompt(activity, isPromptShowing, setPromptShowing,
  onSuccess, onError)` helper (Activity member function; BiometricPrompt is
  activity-bound).
- `LaunchedEffect(Unit) { triggerBiometricPrompt() }` for cold start.
- SEPARATE `DisposableEffect(lifecycleOwner)` OUTSIDE the `if (authenticated)`
  gate: `ON_STOP -> if (biometricEnabled) authenticated = false`;
  `ON_RESUME -> triggerBiometricPrompt()`. The original in-gate observer for
  `viewModel.onForegroundResume()` stays where it is.

Subtlety that defuses the stale-closure worry: a local function capturing
`var x by remember { mutableStateOf(...) }` captures the DELEGATE, not the
value — every read is current. An old observer closure calling
`triggerBiometricPrompt()` still sees fresh state after recomposition.

BiometricPrompt error handling: `ERROR_NEGATIVE_BUTTON` (10) and
`ERROR_USER_CANCELED` (13) are USER cancels, not errors — do NOT `finish()`;
leave `authenticated = false` and wait for the next ON_RESUME (the prompt
re-shows then). All other codes (lockout, no hardware, …) keep the old
`finish()` behavior.

## G4 — one-liner

Sessions panel was permanently stale because `loadHermesSessions()` was never
called: `LaunchedEffect(Unit) { viewModel.loadHermesSessions() }` on screen
entry.

## G5 — "stamp only on server success" without callbacks

MazemakerViewModel convention: fire-and-forget functions, ZERO callbacks, all
state in StateFlows. `setDreamConfig()` is only observable via side effects:
`dreamLoading` cycles false→true→false, and on failure `errorMessage` is set
BEFORE the loading flag clears in `finally` (same coroutine, so the error
state is already current when the loading flag flips).

Screen pattern:
```kotlin
var applyPending by remember { mutableStateOf(false) }
LaunchedEffect(dreamLoading, errorMessage) {
    if (applyPending && !dreamLoading) {
        applyPending = false
        if (errorMessage == null) {
            lastAppliedAt = fmt.format(Date())
        }
    }
}
// click: viewModel.setDreamConfig(params); applyPending = true
```
Watch BOTH keys — with only `dreamLoading`, a failed write would still stamp
the timestamp because the flag clears either way. Known limitation: a stale
pre-existing `errorMessage` (e.g. from loadDreamConfig failing at screen start)
also suppresses the stamp on a real success — acceptable, the user sees the
error banner.

## G6 — clear form only on success

RememberScreen cleared content/label in the click handler, so a failed
`remember()` lost the user's text. The ViewModel already provides the success
signal: `lastRememberId` is reset to null when a send STARTS and set only on
success.

```kotlin
var pendingClear by remember { mutableStateOf(false) }
LaunchedEffect(lastRememberId) {
    if (lastRememberId != null) {
        if (pendingClear) {
            pendingClear = false
            content = ""
            label = "fact:mobile"
        }
        showSuccess = true; delay(3000); showSuccess = false
    }
}
// click: pendingClear = true; viewModel.remember(content.trim(), label.trim())
```
The pendingClear flag is REQUIRED: LaunchedEffect fires on composition re-entry
with a stale non-null id from an earlier success — without the flag it would
wipe a freshly typed form. Note the "Not connected" path (repository null)
returns before the launch and never touches lastRememberId, so pendingClear can
only be consumed by a real success.

## Verification

Same as E/F/H rounds: `./gradlew :app:compileDebugKotlin` +
`:app:testDebugUnitTest` + `:app:assembleDebug` (canonical build per EAS
`gradleCommand`). `npm run test` is jest for the Expo JS side — no node_modules,
no jest config, no test files in the repo; it does not cover the Kotlin code.
