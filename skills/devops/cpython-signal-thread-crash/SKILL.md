---
name: cpython-signal-thread-crash
description: Debug and fix Python crashes where "terminate called without an active exception" occurs during Ctrl+C shutdown, caused by SIGINT arriving during thread.join() blocking on _tstate_lock — CPython threading + async-signal internals.
category: devops
version: 1.0
tags: [python, threading, cpython, signal, crash, debugging, hermes-agent]
---

# CPython Signal+Thread Crash: "terminate called without an active exception"

## The Crash Traceback

```
^CTraceback (most recent call last):
  File "/home/alca/.hermes/hermes-agent/hermes_cli/main.py", line 10, in <module>
    sys.exit(main())
  File "/home/alca/.hermes/hermes-agent/hermes_cli/main.py", line 6046, in main
    cmd_chat(args)
  File "/home/alca/.hermes/hermes-agent/cli.py", line 780, in cmd_chat
    cli_main(**kwargs)
  File "/home/alca/.hermes/hermes-agent/cli.py", line 10194, in main
    cli.run()
  File "/home/alca/.hermes/hermes-agent/cli.py", line 9964, in run
    _run_cleanup()
  File "/home/alca/.hermes/hermes-agent/cli.py", line 635, in _run_cleanup
    _active_agent_ref.shutdown_memory_provider(
  File "/home/alca/.hermes/hermes-agent/run_agent.py", line 2944, in shutdown_memory_provider
    self._memory_manager.shutdown_all()
  File "/home/alca/.hermes/hermes-agent/agent/memory_manager.py", line 351, in shutdown_all
    provider.shutdown()
  File "/home/alca/.hermes/hermes-agent/plugins/memory/mazemaker/__init__.py", line 894, in shutdown
    self._dream.stop()
  File "/home/alca/.hermes/hermes-agent/plugins/memory/mazemaker/dream_engine.py", line 648, in stop
    self._thread.join(timeout=3.0)
  File "/home/alca/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/lib/python3.11/threading.py", line 1123, in join
    self._wait_for_tstate_lock(timeout=max(timeout, 0))
  File "/home/alca/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/lib/python3.11/threading.py", line 1139, in join
    if lock.acquire(block, timeout):
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
KeyboardInterrupt
terminate called without an active exception
```

---

## Root Cause Chain (Layer by Layer)

### Layer 1 — Entry Point
```
hermes (shebang → venv python3)
  → from hermes_cli.main import main
       → cmd_chat(args)  [hermes_cli/main.py:6046]
            → from cli import main as cli_main  [relative import → hermes_cli/cli.py]
                 → cli_main(**kwargs)  [hermes-agent/cli.py main()]
                      → HermesCLI.run()  [cli.py:9964]
                           → _run_cleanup()  [line 9964]
```

### Layer 2 — prompt_toolkit installs its own SIGINT handler
`prompt_toolkit` hooks Ctrl+C to implement its own keyboard handling for the TUI.

### Layer 3 — Ctrl+C arrives during cleanup

When Ctrl+C is pressed while cleanup is in progress:

```
MAIN THREAD (_run_cleanup):
  → shutdown_memory_provider()
    → provider.shutdown()
      → self._dream.stop()
        → self._thread.join(timeout=3.0)   ← BLOCKING HERE

DREAM THREAD:
  _dream_loop() exits cleanly (Event.wait() returns immediately)
  CPython thread teardown starts
  _tstate_lock.acquire() by main thread SUCCEEDS
  lock.release()
  self._stop()  ← Thread state cleanup begins

MAIN THREAD (AT THE SAME MOMENT):
  Signal fires during the blocking lock.acquire() in _wait_for_tstate_lock
  → CPython raises KeyboardInterrupt from lock.acquire()
  → bpo-45274 bare except: catches it
  → lock.locked()? → lock was NOT successfully acquired (it timed out)
  → re-raise KeyboardInterrupt
  → propagates through join() → stop() → shutdown() → ...
```

### Layer 4 — Why `lock.acquire()` raises KeyboardInterrupt

CPython's `_thread.lock.acquire()` calls into C code. When a signal arrives during the blocking wait, CPython checks for pending signals and raises `KeyboardInterrupt`. This is standard Python behavior for blocking calls during signal delivery.

The `bpo-45274` fix in `threading.py` handles this:
```python
# threading.py lines 1138-1150 (CPython 3.11+)
try:
    if lock.acquire(block, timeout):
        lock.release()
        self._stop()
except:
    if lock.locked():
        # bpo-45274: lock.acquire() acquired the lock, but the function
        # was interrupted with an exception before reaching lock.release().
        # It can happen if a signal handler raises an exception,
        # like CTRL+C which raises KeyboardInterrupt.
        lock.release()
        self._stop()
    raise
```

BUT: the crash occurs because `lock.locked()` returns `False` (lock was NOT acquired — the exception was raised BEFORE acquisition succeeded), so the `except:` re-raises `KeyboardInterrupt`. It propagates up, eventually reaches `sys.exit()` → `Py_Finalize()` → interpreter shutdown → `PyThreadState_Delete()` on already-cleaned state → **`std::terminate()`**.

---

## Why `Event.wait()` doesn't prevent the race

`dream_engine._dream_loop()`:
```python
while not self._stop_event.is_set():
    if self._stop_event.wait(timeout=30.0):  # ← wakes immediately when set
        break
    # ... dream work ...
```

When `stop()` is called: `_stop_event.set()` → `wait()` returns immediately → `_dream_loop()` exits cleanly → thread starts teardown.

The race is NOT in the loop — it's in `join()`. The dream thread exits, starts C-level teardown, and the main thread is blocked on `join()`. The signal arrives DURING the blocking `join()` call, specifically inside `lock.acquire()` waiting for the thread state to be fully cleaned up.

---

## Fixes

### Fix 1 — Signal guard in `dream_engine.stop()` (PRIMARY)

**File:** `~/projects/neural-memory-adapter/python/dream_engine.py` (line 644-649)

```python
def stop(self) -> None:
    """Stop the dream daemon."""
    self._stop_event.set()
    if self._thread and self._thread.is_alive():
        import signal
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            self._thread.join(timeout=3.0)
        finally:
            signal.signal(signal.SIGINT, old_handler)
    logger.info("Dream engine stopped after %d cycles", self._dream_count)
```

**Why this works:** Signal.SIG_IGN prevents the signal handler from firing during `join()`. The signal remains pending and will be delivered after `join()` returns. This is the standard pattern for making blocking calls signal-safe.

### Fix 2 — Signal guard in `NeuralMemoryProvider.shutdown()`

**File:** `~/projects/neural-memory-adapter/python/__init__.py` (line 889-907)

```python
def shutdown(self) -> None:
    """Clean shutdown."""
    if hasattr(self, '_dream') and self._dream:
        try:
            import signal
            old = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                self._dream.stop()
            finally:
                signal.signal(signal.SIGINT, old)
        except Exception:
            pass
        self._dream = None
    self._consolidation_stop.set()
    if self._consolidation_thread and self._consolidation_thread.is_alive():
        self._consolidation_thread.join(timeout=2.0)
    if self._memory:
        try:
            self._memory.close()
        except Exception:
            pass
        self._memory = None
```

### Fix 3 — KeyboardInterrupt boundary in `_run_cleanup()`

**File:** `hermes-agent/cli.py` (line 634-639)

```python
try:
    if _active_agent_ref and hasattr(_active_agent_ref, 'shutdown_memory_provider'):
        _active_agent_ref.shutdown_memory_provider(
            getattr(_active_agent_ref, 'conversation_history', None) or []
        )
except KeyboardInterrupt:
    # Guard against signal during shutdown — the interrupt
    # will propagate up and be handled by the outer handler
    raise
except Exception:
    pass
```

---

## Key Files to Edit

| File | Line | Change |
|------|------|--------|
| `~/projects/neural-memory-adapter/python/dream_engine.py` | 644-649 | Add signal.SIG_IGN around `join()` |
| `~/projects/neural-memory-adapter/python/__init__.py` | 889-907 | Add signal.SIG_IGN around `_dream.stop()` |
| `~/.hermes/hermes-agent/cli.py` | 634-639 | Add `except KeyboardInterrupt: raise` |

After editing `python/`, redeploy:
```bash
cd ~/projects/neural-memory-adapter && bash install.sh install
```

---

## Forensic Tracing Technique

When debugging similar crashes, trace the FULL call stack from signal to crash:

1. **Identify entry point**: `hermes` shebang → `hermes_cli/main.py` → `cli.py` (relative import)
2. **Find signal handler**: prompt_toolkit installs its own SIGINT handler
3. **Trace the cleanup chain**: `_run_cleanup()` → `shutdown_memory_provider()` → `provider.shutdown()` → `_dream.stop()` → `thread.join()`
4. **Read CPython threading source**: `/home/alca/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/lib/python3.11/threading.py` lines 1125-1150
5. **Identify the blocking call**: `lock.acquire(block, timeout)` in `_wait_for_tstate_lock`
6. **Check the bpo-45274 fix**: bare `except:` catches signal → checks `lock.locked()` → either releases+stops OR re-raises
7. **Trace propagation**: re-raised KeyboardInterrupt → `sys.exit()` → `Py_Finalize()` → `std::terminate()`

**The crash is NOT in the except block — it's in what happens AFTER the interrupt propagates to interpreter shutdown.**

---

## Note on Python Version

This was analyzed on:
```
Python: 3.11.15 (main, Mar 10 2026, [Clang 21.1.4])
Threading module: /home/alca/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/lib/python3.11/threading.py
```

The `bpo-45274` fix IS present (added in Python 3.11). The crash still occurs because the lock was NOT acquired when the signal fired, so the `except:` re-raises instead of swallowing.
