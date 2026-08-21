# ViewModel coroutine race patterns (mazemaker-mobile)

Applies to `MazemakerViewModel.kt` — the single-StateFlow hub of the mazemaker-mobile
Android client (SSE Hermes chat streams, WebSocket collectors, health-failure timers,
timeline pagination). Race classes + fixes applied 2026-08-07 (H11/H12/H2/H5/M13/M14).

## 1. Async cancel race — generation counter (H11/H12)

Symptom: user cancels a streaming Hermes chat request, then sends a new one. The OLD
job's `catch (CancellationException)` appends `[cancelled]` into the NEW conversation's
history, and its `finally` clears `_hermesBusy`/`_streamingDone` while the new stream is
running. `job.cancel()` is asynchronous — a cancelled coroutine's catch/finally can run
AFTER the next job already launched and mutated shared state.

Pattern:
- Field `private var hermesChatGen = 0`. In the sender: `val myGen = ++hermesChatGen`
  BEFORE launching; the launched job captures `myGen`.
- `catch (CancellationException)` AND `catch (Exception)`: first line
  `if (hermesChatGen != myGen) return@launch` — a stale job must not append turns,
  set errors, or mutate history of the newer session.
- `finally`: wrap ALL shared-state resets (timer cancel, `_hermesBusy=false`,
  `_streamingDone=true`, elapsed=0) in `if (hermesChatGen == myGen) { ... }`.
- ALSO guard inside `flow.collect { }`:
  `if (hermesChatGen != myGen) throw CancellationException("stale generation")`.
  Without it, the superseded SSE stream keeps appending chunks into the new stream
  until its next suspension point observes the cancellation.
- A user-cancel that does NOT bump the generation still gets its `[cancelled]` turn
  (gen still current) and its finally still resets busy — this is the desired UX.

## 2. The canceller owns the state reset (H12 subtlety)

If the CANCELING function bumps the generation (e.g. `newHermesSession()` /
`resumeHermesSession()`), the old job's gen-guarded finally will NOT reset
busy/streaming. The canceller must therefore reset the shared state itself:
`hermesChatGen++; hermesChatJob?.cancel(); hermesChatJob = null;
hermesTimerJob?.cancel(); _hermesBusy=false; _streamingDone=true;
_streamingText=""; _hermesElapsedMs=0`.

Rule of thumb: bump the generation ONLY when a new state owner (new session/stream)
must be protected from the stale job. Plain user-cancel keeps the generation, so the
old job finishes its own cleanup.

## 3. Collector jobs in init() — store as fields, cancel before re-attach (H2/H5)

`viewModelScope.launch { flow.collect { ... } }` attached in `init()` and never
stored/cancelled → after N inits, N collectors process every event → N notifications,
N duplicate state writes.

- Two fields: `private var wsStateJob: Job? = null`, `wsEventsJob: Job? = null`.
- In `init()`, before re-attaching: `wsStateJob?.cancel(); wsEventsJob?.cancel()`.
- Do NOT hard-set `_wsState.value = "disabled"` after re-attach when WS is enabled —
  guard it: `if (!podWebSocket.wsEnabled.value)`.

## 4. One-shot timer jobs — single field, cancel before restart (M14)

A 10s `Failed → Disconnected` reset timer restarted on EVERY failure stacks timers
(each fires later and flips state). Keep one field `failResetJob: Job?`;
`failResetJob?.cancel()` before relaunching.

## 5. Pagination hasMore (M13)

- Reset the growing limit on screen re-entry: `loadTimeline()` starts with
  `timelineLimit = 30` (otherwise it re-enters at the loadMore-grown value).
- hasMore criterion: `it.size == limit && it.isNotEmpty()` instead of
  `it.size >= limit` — `>=` stays true when the API returns more than asked (or
  echoes the limit exactly), driving an endless loadMore loop.
- On loadMore failure, roll the limit back (`timelineLimit -= 30`).

## 6. WS reconnect after a drop (H5)

The "auto-enable if not enabled" branch never reconnects once WS is enabled but the
socket dropped. Add an else-branch:
`else if (wsEnabled && wsAvailable && state.value == "disconnected") connect(host)`.
Notes: `PodWebSocket.connect()` no-ops unless enabled; `disconnect()` sets state
`"disconnected"` when enabled (so the check is meaningful after init's disconnect).

## Verification

All changes verified with `./gradlew :app:compileDebugKotlin` — see
`podwebsocket-lifecycle-and-verification.android-arch.md` for the workflow and its
pitfalls (parallel-daemon contention, `--rerun-tasks` for fresh evidence, multi-agent
dirty-tree attribution).
