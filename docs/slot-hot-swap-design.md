# Slot hot-swap: moving compaction recompute off the live turn

Status: designed, not implemented.

## Problem

`ContextCompressor` compacts history when usage crosses a threshold. With
Qwen3.5 (`QWEN35`, IMROPE RoPE, `n_pos_per_embd() == 4`), any edit to history
other than a tail truncation forces llama-server to reprocess the prompt from
the edit point forward. `seq_add()`, the position-shift primitive that
`n_cache_reuse` and any cache splice depend on, asserts on non-scalar RoPE
positions. See commit `bad7199cd` in `llama.cpp-adaptive-kv-streaming`.

That reprocessing cannot be avoided on this model. It can be relocated. Today
it runs inline with a turn, so the slot serving the live conversation absorbs
the latency.

## Approach

1. Trigger in the background ahead of the real compaction threshold. A separate
   earlier threshold (`hot_swap_prep_threshold_percent`, around 70–80% of
   `ContextCompressor`'s trigger) leaves time for the prefill to finish before
   compaction would otherwise fire.
2. Build the compacted message list with `_compress_context`, which returns
   `(compressed_messages, new_system_prompt)` without mutating live state. Call
   it on a snapshot of `messages`, not the live list.
3. Prefill the result into the sidekick slot: a request with
   `id_slot=<sidekick>` (`max_tokens=1` is enough) makes llama-server process
   and cache every token on a slot the live conversation does not use.
4. Swap which slot is main, at the start of the next turn only, never
   mid-generation. The sidekick holds the warm compacted history and becomes
   main; the previous main becomes the sidekick.

## State

Replace the static `_pinned_id_slot` with a mutable pair:

```python
self._main_slot = 1
self._sidekick_slot = 0
self._hot_swap_in_progress = False   # guards overlapping prep attempts
self._hot_swap_ready = None          # None, or (compressed_messages, new_system_prompt)
```

Call sites reading `_pinned_id_slot` — the `extra_body["id_slot"]` assignment in
the main completion path, `_spawn_background_review`'s override, and the two
sites in `auxiliary_client.py` — each already know which role they play, so they
read `_main_slot` or `_sidekick_slot` accordingly. That part is indirection, not
new logic.

## Methods

```python
def _maybe_start_hot_swap_prep(self, messages: list) -> None:
    """Called once per turn, where _compress_context is consulted.

    Returns early in the common case, so it adds no latency to a normal turn.
    """
    if self._hot_swap_in_progress or self._hot_swap_ready is not None:
        return
    if not self._context_compressor:
        return
    usage = self._context_compressor.last_prompt_tokens / self._context_compressor.context_length
    if usage < self._hot_swap_prep_threshold_percent:
        return
    self._hot_swap_in_progress = True
    threading.Thread(
        target=self._run_hot_swap_prep,
        args=(list(messages),),          # snapshot, not the live list
        daemon=True, name="hot-swap-prep",
    ).start()

def _run_hot_swap_prep(self, messages_snapshot: list) -> None:
    try:
        compressed, new_system_prompt = self._compress_context(
            messages_snapshot, self._cached_system_prompt or "",
        )
        # A request against the sidekick slot forces the prefill. Read
        # _sidekick_slot once here; it can change if a swap lands meanwhile.
        self._prime_slot_with_messages(self._sidekick_slot, compressed, new_system_prompt)
        self._hot_swap_ready = (compressed, new_system_prompt)
    except Exception as e:
        logger.debug("hot-swap prep failed, staying on current main: %s", e)
    finally:
        self._hot_swap_in_progress = False

def _apply_pending_hot_swap_if_ready(self) -> None:
    """Called at the start of a turn, before building the request."""
    if self._hot_swap_ready is None:
        return
    compressed, new_system_prompt = self._hot_swap_ready
    self._hot_swap_ready = None
    self._session_messages = compressed
    self._cached_system_prompt = new_system_prompt
    self._main_slot, self._sidekick_slot = self._sidekick_slot, self._main_slot
```

## Edge cases

- A user message arrives while prep is in flight: the turn proceeds on the
  current main slot. This holds as long as `_maybe_start_hot_swap_prep` only
  spawns a detached thread and the live path reads `_hot_swap_ready` only at the
  top of a turn.
- Prep completes mid-generation: the swap waits for
  `_apply_pending_hot_swap_if_ready` at the next turn boundary.
  `_hot_swap_ready` holds the result until then.
- Overlapping prep cycles: `_hot_swap_in_progress` guards this, matching the
  liveness check `_spawn_background_review` uses for overlapping reviews.
- Prep fails (server error, OOM, busy sidekick): log at debug, clear
  `_hot_swap_in_progress`, leave `_hot_swap_ready` as `None`. The session
  behaves as if the feature were absent. `ContextCompressor`'s normal blocking
  compaction remains the fallback and must not be weakened by this feature.
- Sidekick slot busy with `_spawn_background_review` or `auxiliary_client.py`
  work when prep runs: the prime request queues behind it, which is acceptable
  since none of this is on the live path. Worth measuring whether that delays
  the following prep cycle.
- Stale cache on the demoted slot: after a swap the old main still holds the
  pre-compaction history. It is overwritten the next time that slot is used. An
  explicit clear equivalent to `prompt_clear()` (`mem.seq_rm(id, -1, -1)`, which
  shifts no positions and is therefore safe on IMROPE models) would reclaim the
  KV footprint sooner.

## Unchanged by this

- `ContextCompressor`'s trigger threshold and blocking compaction path, which
  remain the fallback when prep has not completed in time.
- `n_cache_reuse` and cache-splice handling, already disabled for this model.
- `flush_memories`'s background dispatch, which is an independent path.

## Implementation order

1. Rename `_pinned_id_slot` to the `_main_slot`/`_sidekick_slot` pair. No swap
   logic, behavior identical to current.
2. Add `_maybe_start_hot_swap_prep` and `_run_hot_swap_prep`, with
   `_apply_pending_hot_swap_if_ready` stubbed to log instead of swapping. Verify
   over a real session that prep fires at the intended threshold, completes, and
   does not delay a turn.
3. Enable the swap, with a test per edge case above. Existing tests in
   `tests/run_agent/test_background_review_slot_pin.py` and
   `tests/cli/test_llama_telemetry.py` show the pattern: bare `AIAgent.__new__`
   instances, stubbed background functions, explicit thread joins rather than
   sleeps.
