# Discord 100-Command Cap — Two-Layer Resilience Pattern

Session reference for the 2026-06-18 fix: `itsXactlY/hermes-agent` PR #3 (`fix/discord-slash-100-cap-resilience`). Covers the failure mode, the precise fix, the test-mock pitfall, and the architectural quirk in `_run_post_connect_initialization`.

## The failure mode in one paragraph

Discord caps global application (slash) commands at 100 per app. The adapter's `_safe_sync_slash_commands` syncs them on connect. If the cap is hit (either because the local set is already >100, or a race between `fetch_commands()` and `upsert_global_command()` pushes the count over mid-sync), Discord returns `HTTPException(400, code=30032)`. The exception propagated all the way out of `_safe_sync_slash_commands` → through `_run_post_connect_initialization` → the outer `try` only catches `TimeoutError`/`CancelledError` → gateway task died. User had to manually `hermes gateway run --replace` to recover. Logs looked healthy (`active (running)`) but Discord was silent.

## The two-layer fix (both required)

**Upstream #46078** (merged 2026-06-14 in NousResearch/hermes-agent) caps REGISTRATION so the tree never has >100 commands on a fresh install. That fix is necessary but not sufficient — it doesn't help with race conditions, external pushes, or any code path that bypasses the registration cap. Both layers are needed.

### Layer 1 — Pre-flight trim (defense)

Before any mutation, if `len(desired_payloads) > _DISCORD_MAX_APP_COMMANDS`, drop the lowest-priority entries. Sort key: `(0 if key in existing_by_key else 1, name)` — existing commands first, then alphabetical. The API is never called in a state we already know will fail.

```python
if len(desired_payloads) > _DISCORD_MAX_APP_COMMANDS:
    prioritized = sorted(
        desired_by_key.items(),
        key=lambda kv: (0 if kv[0] in existing_by_key else 1, kv[0][1]),
    )
    dropped = len(desired_payloads) - _DISCORD_MAX_APP_COMMANDS
    desired_by_key = dict(prioritized[:_DISCORD_MAX_APP_COMMANDS])
    capped = True
    logger.warning(
        "[%s] Local slash command set has %d commands but Discord caps "
        "global application commands at %d. Dropping %d lower-priority "
        "command(s) (alphabetically after existing commands) so the "
        "sync stays within the cap. To surface them all: remove "
        "unused plugins, trim COMMAND_REGISTRY, or run with "
        "discord.command_sync.policy=bulk.",
        self.name, len(desired_payloads), _DISCORD_MAX_APP_COMMANDS, dropped,
    )
```

Pre-flight drops are silent (no API call made) — `summary["skipped"]` stays 0 in this path. The proof of the trim working is that the dropped command names never appear in `upsert_global_command.await_args_list`.

### Layer 2 — Mutation-level swallow (resilience)

Wrap every HTTP call in a `mutate()` closure that catches the cap error and returns a sentinel:

```python
_DISCORD_COMMAND_CAP_SENTINEL = object()  # module-level, never equal to anything else

async def mutate(call, *args):
    nonlocal mutation_count, capped
    if mutation_count:
        await self._sleep_between_command_sync_mutations()
    try:
        result = await call(*args)
    except Exception as exc:  # Exception, NOT discord.HTTPException — see Pitfall 1
        if self._is_discord_command_cap_error(exc):
            capped = True
            return _DISCORD_COMMAND_CAP_SENTINEL
        raise
    mutation_count += 1
    return result
```

Every call site checks for the sentinel:

```python
result = await mutate(http.upsert_global_command, app_id, desired)
if result is _DISCORD_COMMAND_CAP_SENTINEL:
    skipped += 1
    continue
created += 1
```

### Detection helper

```python
def _is_discord_command_cap_error(self, exc: Any) -> bool:
    if getattr(exc, "code", None) == _DISCORD_COMMAND_CAP_ERROR_CODE:  # 30032
        return True
    response = getattr(exc, "response", None)
    status = getattr(response, "status", None) or getattr(response, "status_code", None)
    if status != 400:
        return False
    text = (getattr(exc, "text", "") or str(exc) or "")
    return "Maximum number of application commands reached" in text
```

### Summary dict shape

```python
return {
    "total": len(desired_payloads),      # original desired set size (pre-trim)
    "kept": len(desired_by_key),         # what the sync actually tried to keep
    "unchanged": unchanged,
    "updated": updated,
    "recreated": recreated,
    "created": created,
    "deleted": deleted,
    "skipped": skipped,                  # ops that hit the cap mid-sync
    "capped": capped,                    # True iff any part of the sync was constrained
}
```

Caller in `_run_post_connect_initialization` logs a single concise warning when `capped=True` — operators can grep the journal for it.

## Pitfall 1 — `except discord.HTTPException` fails in the test environment

In the Hermes test suite, `discord` is installed as a `MagicMock` (see `_ensure_discord_mock()` in `tests/gateway/test_discord_connect.py`). So `discord.HTTPException` is a `MagicMock` attribute, not a real `BaseException` subclass. `except discord.HTTPException` raises `TypeError: catching classes that do not inherit from BaseException is not allowed` at the time the `try` block is entered.

**Fix:** Use `except Exception` and rely on `_is_discord_command_cap_error` for the precise discrimination. This is safe because the helper does duck-typed `getattr` checks — it never assumes the exception is an HTTPException.

Real production code still gets the right behavior because the real `discord.HTTPException` IS an `Exception` subclass.

## Pitfall 2 — Test exception classes must inherit from `Exception`, not `BaseException`

When writing test fixtures for the cap error, the fake exception class must inherit from `Exception` so `except Exception` catches it:

```python
# WRONG — `except Exception` won't catch this
class _CapHTTPException(BaseException):
    code = 30032
    response = SimpleNamespace(status=400, status_code=400)
    text = "Maximum number of application commands reached (100)."

# RIGHT
class _CapHTTPException(Exception):
    code = 30032
    response = SimpleNamespace(status=400, status_code=400)
    text = "Maximum number of application commands reached (100)."
```

(The real `discord.HTTPException` inherits from `Exception` → `ClientException` → `DiscordException` → `Exception`. Test fixtures should mirror this.)

## Pitfall 3 — Existing `assert summary == {...}` exact-equality tests break when adding fields

The existing tests in `tests/gateway/test_discord_connect.py` use exact-equality assertions on the summary dict. Adding `kept`/`skipped`/`capped` fields requires updating those assertions — and there are three of them (lines 447, 523, 809 on the pre-fix version). Forgetting any of them causes a test failure that's easy to miss because it's "just" a dict-inequality.

## Pitfall 4 — Mocking `tree.fetch_commands` is required in end-to-end tests

The end-to-end "gateway survives 30032" test mocks `adapter._client` as a SimpleNamespace. The `tree` needs both `get_commands` AND `fetch_commands` (the latter is an `AsyncMock(return_value=[])`). Forgetting `fetch_commands` gives a confusing `AttributeError` deep in the production code that looks like a code bug but is actually a test-setup omission.

## Architectural quirk in `_run_post_connect_initialization`

The function has nested try/excepts:

```python
async def _run_post_connect_initialization(self) -> None:
    if not self._client:
        return
    try:                                              # ← outer
        sync_policy = self._get_discord_command_sync_policy()
        ...
        try:                                          # ← inner
            summary = await asyncio.wait_for(
                self._safe_sync_slash_commands(), timeout=600
            )
        except Exception as e:
            if not self._is_discord_rate_limit(e):
                raise                                 # ← THIS is the gateway-killer
            ...
        ...
    except asyncio.TimeoutError:                      # ← outer only catches these
        logger.warning(...)
    except asyncio.CancelledError:
        raise
```

The inner `try` only handles rate-limits. The outer `try` only handles timeouts and cancellation. Any other exception tears down the gateway task.

**Implication for the fix:** Don't try to add the resilience at the call site (in `_run_post_connect_initialization`) — that would mean another broad `except Exception` that hides real bugs. Fix it at the source (in `_safe_sync_slash_commands` / `mutate()`) so the helper returns a soft-fail summary instead of raising.

## Test coverage for the fix

Four pytest tests in `tests/gateway/test_discord_connect.py` (added 2026-06-18):

| Test | Proves |
|---|---|
| `test_safe_sync_trims_local_set_over_100_pre_flight` | Pre-flight trim drops the right commands and never calls the API for them |
| `test_safe_sync_swallows_30032_cap_error_during_upsert` | A 30032 mid-sync is caught; the loop continues; second create succeeds |
| `test_is_discord_command_cap_error_detects_code_30032` | Helper distinguishes cap errors from generic 400s and 429s (false-positive guard) |
| `test_post_connect_initialization_does_not_kill_gateway_on_30032` | End-to-end: a 30032 in `_run_post_connect_initialization` does NOT re-raise; sync state still records success |

Test pattern for the cap error:

```python
class _CapHTTPException(Exception):
    code = 30032
    response = SimpleNamespace(status=400, status_code=400)
    text = "Maximum number of application commands reached (100)."
```

Test pattern for the trim (use a small cap so the test runs fast):

```python
monkeypatch.setattr(discord_platform, "_DISCORD_MAX_APP_COMMANDS", 10)
# 15 desired, 8 existing on Discord → pre-flight drops 5 net-new,
# 8 existing unchanged, 2 net-new created. summary: capped=True, kept=10.
```

## Verification commands (post-deploy)

```bash
# 1. Run the new tests in isolation
bash scripts/run_tests.sh tests/gateway/test_discord_connect.py -- --tb=short

# 2. Run the full gateway test sweep
bash scripts/run_tests.sh tests/gateway/

# 3. After deploying to the live gateway, check that the cap error no longer
#    appears AND the gateway stays alive even if the cap is hit
journalctl --user -u hermes-gateway.service -n 200 --no-pager \
  | grep -E "(30032|capped|hit the.*command cap|slash command sync failed)"
# Expected: "kept=100 skipped=N" warnings are OK (cap hit, gateway survived);
# "Slash command sync failed:" with a traceback is NOT OK (old behavior).
```

## Reusable pattern (not just Discord)

The two-layer pattern generalizes to ANY external API with a hard cap that could fire mid-loop:

- **Layer 1 (pre-flight trim):** compute the post-state from the diff. If it would exceed the cap, drop the lowest-priority entries BEFORE any mutation. Log once with the count.
- **Layer 2 (sentinel return):** wrap mutations in a closure that catches the cap error, returns a sentinel, and lets the loop continue. Use a unique `object()` sentinel (not `None` or a string) so call sites can use `is` for comparison.

Caveats:
- Catching `Exception` broadly is OK when the discrimination is precise (`_is_X_cap_error` helper that checks both `code` and `text`). It is NOT OK as a general "swallow errors" pattern.
- The sentinel must be a true singleton (module-level `object()`) — never reuse a domain value like `None` or `False` because those have legitimate meanings in the result.
- The summary dict should expose `capped`/`skipped` so callers can log it instead of being surprised by missing commands.

Files of the actual fix:
- `plugins/platforms/discord/adapter.py` (160 lines added)
- `tests/gateway/test_discord_connect.py` (286 lines added: 4 new tests + 3 existing summary assertions updated)
- Branch: `fix/discord-slash-100-cap-resilience`
- PR: https://github.com/itsXactlY/hermes-agent/pull/3
