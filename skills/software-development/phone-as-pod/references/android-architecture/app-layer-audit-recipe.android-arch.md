# App-Layer Audit Recipe for mazemaker-mobile

When the user asks "what's missing / what needs refinement" in the Android app at
`/home/alca/projects/mazemaker-mobile`, do not start from feature gap analysis. The
architecture is more complete than it looks: ViewModel + StateFlow + Result<T> repository,
Compose 1.6, Material3, OkHttp/Retrofit, DataStore, navigation graph, biometric,
WebSocket service, offline cache layer, release-signing pipeline, JVM unit tests.

The real gap is almost always **built-but-not-wired**. This file gives the
audit commands and the failure modes they catch.

## Audit Commands (in order)

Run these from `/home/alca/projects/mazemaker-mobile` BEFORE writing any critique.

### 1. LOC map — which files dominate

```bash
find android/app/src/main/java -name "*.kt" -not -path "*/build/*" | xargs wc -l | sort -rn | head -25
```

Smell thresholds for the mazemaker-mobile codebase:
- Any single ViewModel > 1,000 LOC → god-object, split before next feature
- Any single screen > 800 LOC → split into sub-screens or extract a component file
- SettingsScreen > 1,200 LOC with no sub-navigation → junk drawer, add inner NavHost

### 2. Infrastructure class census

```bash
grep -rln "^class\|^\s*class " android/app/src/main/java | sort
```

Then for each class file in `data/` (cache, realtime, notifications, auth, pairing,
crash, api), find its **call sites**:

```bash
# Example: confirm OfflineInterceptor is actually wired
grep -rn "addInterceptor(OfflineInterceptor\|OfflineInterceptor(" android/app/src/main
# If 0 hits in MazemakerViewModel.kt, it's dead code

# Example: confirm PodWebSocket.events has a consumer
grep -rn "podWebSocket.events\|wsEvents.collect\|_events.collect" android/app/src/main
# If 0 hits, the SharedFlow has no listener — events arrive and evaporate

# Example: confirm DreamNotificationManager.notifyDreamComplete is reachable
grep -rn "notifyDreamComplete\|notify(" android/app/src/main
# If the only hits are the declaration and the DreamNotificationManager class,
# the notification channel is created and POST_NOTIFICATIONS is in the manifest
# but nothing ever calls it
```

### 3. OkHttp interceptor chain audit

```bash
grep -n "addInterceptor\|OkHttpClient.Builder\|Retrofit.Builder" android/app/src/main/java/dev/mazemaker/mobile/ui/MazemakerViewModel.kt
```

Count the `.addInterceptor(` lines. Should equal the number of interceptor
classes under `data/cache/` and `data/auth/`. If lower, interceptors exist
but are not registered.

### 4. The stub-body-shape audit

For every OkHttp `Response.Builder().body(...)` call in an interceptor or
fallback path, find the caller and check the expected JSON shape:

```bash
grep -rn "Response.Builder\|toResponseBody" android/app/src/main/java
```

Then trace each stub to its consumer. `parse<List<T>>(json)` requires
`[...]`. `parse<Map<K,V>>(json)` requires `{...}`. A stub returning
`{"offline":true}` to a list consumer will ClassCastException inside Gson.

### 5. The "Search" button trace

If the user mentions the search field, trace the actual call path:

```bash
grep -n "viewModel\.search\|fun search\|onSearchSubmit" android/app/src/main/java/dev/mazemaker/mobile/ui/screen/HomeScreen.kt
grep -n "fun search\b\|fun recall\b\|fun browse\b" android/app/src/main/java/dev/mazemaker/mobile/ui/MazemakerViewModel.kt
```

The button label may say "Recall" but the ViewModel method may call
`repo.browse()` (browse returns recent memories with no semantic ranking).
`mazemaker_recall` vs `mazemaker_browse` are semantically different and the
UI shouldn't claim recall when it's doing browse.

### 6. Dashboard tile drilldown audit

```bash
grep -n "MonitorCard(\"M0" android/app/src/main/java/dev/mazemaker/mobile/ui/screen/DashboardScreen.kt
grep -n "onNavigate\|route\|navArgument" android/app/src/main/java/dev/mazemaker/mobile/ui/navigation/MazemakerNavGraph.kt
```

For each tile:
- Does it have a route? If yes, does the route accept nav arguments?
- Does the receiving screen (Graph, Dream, Hermes) read those arguments and
  pre-populate state? Or does it open in default state?

If routes exist but no arguments are threaded, tiles are display-only and
should either be made non-clickable or have their routes dropped.

### 7. The "is this a real consumer" test

For any SharedFlow, StateFlow, or callback exposed by a manager/service,
grep for `.collect` (coroutine consumer) or `.observe` (lifecycle consumer).
Zero hits = the producer is producing into a black hole.

```bash
# Real pattern in this codebase:
grep -rn "\.events\.collect\|events\.collectLatest\|_events\.collect" android/app/src/main/java

# Anti-pattern: events emitted but no listener ever starts
grep -rn "MutableSharedFlow\|MutableStateFlow" android/app/src/main/java/dev/mazemaker/mobile/data/
```

## Failure-Mode Catalog (the six smells)

### F1. Dead infrastructure class
**Symptom**: Class file exists, looks correct, no compile errors, but never invoked.
**Detection**: zero call sites in production code.
**Real example from 2026-06-15**: `OfflineInterceptor.kt` is 31 LOC of correct-looking
code, but the OkHttp client only registers `AuthInterceptor`. The whole "graceful
offline" story that v7 hardening was supposed to deliver is invisible.
**Fix**: either wire it (`.addInterceptor(OfflineInterceptor(memoryCache))` in
`sharedClient` builder) or delete it. Dead infrastructure is worse than no
infrastructure because it lies in code review.

### F2. Stub body shape mismatch
**Symptom**: A fallback path returns a JSON object, the consumer expects a JSON array
(or vice versa). App crashes in the offline path it was supposed to survive.
**Detection**: trace every `Response.Builder().body(` to its consumer.
**Real example from 2026-06-15**: `OfflineInterceptor` returns `{"offline":true}`.
The nearest consumer is `parse<List<MemoryResult>>(callTool(...))` which would
JsonSyntaxException on the object. Fix: route-aware stub that returns `[]` for
read tools, a typed error object for write tools.

### F3. God-object ViewModel
**Symptom**: A single ViewModel class > 1,000 LOC, 30+ StateFlows, spans 5+
feature domains (auth, cache, pod, dream, hermes, settings, websocket).
**Detection**: `wc -l MazemakerViewModel.kt` and count StateFlows.
**Real example from 2026-06-15**: 1,207 LOC, 40+ StateFlows, 7 domains.
**Fix**: parent AppContainer (manual DI) + per-domain ViewModels.
**Why it matters**: every new feature that requires invalidating another
domain's state adds direct cross-VM coupling. After ~1,500 LOC this is
unmaintainable.

### F4. Dead SharedFlow / event pipe
**Symptom**: A `MutableSharedFlow<JsonElement>()` or `MutableSharedFlow<Event>()`
is exposed publicly, events are emitted, but `.collect` is never called.
**Detection**: grep for the flow name + `.collect`.
**Real example from 2026-06-15**: `PodWebSocket.events: SharedFlow<JsonElement>`
emits incoming WS messages. Zero `.collect` calls in the codebase. The pod
can push dream-cycle events, new-memory events, anything — the phone never
sees them.

### F5. SettingsScreen junk drawer
**Symptom**: One screen file > 1,200 LOC that has accumulated every config
toggle, every dev mode, every auth flow. No sub-navigation.
**Detection**: count sections, count lines.
**Real example from 2026-06-15**: 1,333 LOC containing host config, biometric,
WS toggle, dream config, hermes settings, about. Sub-navigation does not exist
inside SettingsScreen — it's a top-level route only.
**Fix**: introduce inner NavHost with `settings/connection`, `settings/security`,
`settings/dream`, `settings/hermes`, `settings/about` as sub-routes. Reduces
visible scroll and makes the screen findable.

### F6. Tile with empty subtitle / no real data
**Symptom**: Dashboard monitor with `subtitle = ""` or hardcoded to a count
that doesn't reflect actual state.
**Detection**: read the MonitorCard declarations in DashboardScreen.kt and
verify each subtitle is bound to a live StateFlow.
**Real example from 2026-06-15**: M04 "TOP" has `subtitle = ""`. The endpoint
that should power it (`mazemaker_afe_facts` sorted by salience) exists on the
pod but the tile doesn't call it. M06 "PEERS" similarly has no subtitle even
though PairingManager exists.

## What NOT to suggest (the false-positive patterns)

When auditing this codebase, the following "obvious" suggestions are
**wrong** because the feature is already there:

- "Add offline mode" → OfflineInterceptor exists (just unwired, F1)
- "Add WebSocket support" → PodWebSocket exists (just unwired, F4)
- "Add biometric lock" → wired in MainActivity.kt and SettingsScreen.kt
- "Add dream notifications" → DreamNotificationManager exists (just unreachable, F1)
- "Add remember screen" → RememberScreen.kt exists and is wired
- "Add cache layer" → MemoryCache + OfflineInterceptor exist (F1)
- "Add search" → HomeScreen has the search field; verify it's calling recall
  not browse (F5)

The right critique is always: **what is built but not wired, and what
deeper refactor pays back the next 6 months of feature work** (god-object
ViewModel split, real WebSocket consumer, route-aware offline stub,
inner NavHost in Settings).

## Verification after the critique is acted on

If you (or a future agent) fix any of the above, the verification commands
should return:

```bash
# After wiring OfflineInterceptor
grep -n "addInterceptor" android/app/src/main/java/dev/mazemaker/mobile/ui/MazemakerViewModel.kt
# Expect: 2 hits (AuthInterceptor, OfflineInterceptor)

# After adding WebSocket consumer
grep -rn "podWebSocket.events.collect\|wsEvents.collect" android/app/src/main/java
# Expect: 1+ hits in ViewModel

# After splitting ViewModel
wc -l android/app/src/main/java/dev/mazemaker/mobile/ui/MazemakerViewModel.kt
# Expect: < 400 LOC (the original was 1,207)
```

Persist the fix as a `mazemaker_remember` with label `bug:mazemaker-mobile-<topic>-<date>`
so the next session can recall the work without re-deriving it.
