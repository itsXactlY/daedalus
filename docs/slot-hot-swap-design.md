# Slot hot-swap: background compaction with zero live-turn recompute

Status: **designed, not implemented.** Written 2026-09-12, scoped for a
focused implementation session with fresh context — this touches core
turn/slot lifecycle logic in `run_agent.py` and should not be rushed into a
session that's already deep into unrelated changes.

## The problem

`ContextCompressor` compacts history (drops/summarizes old turns) when usage
crosses a threshold. On this model (Qwen3.5 / `QWEN35`, IMROPE RoPE —
`n_pos_per_embd() == 4`) any edit to history except a pure tail-truncation
forces llama-server to fully reprocess the compacted prompt from the edit
point forward — `seq_add()` (the position-shift primitive both `n_cache_reuse`
and any cache-splice would need) hard-asserts on non-scalar RoPE positions.
See `llama.cpp-adaptive-kv-streaming` commit `bad7199cd` for the full
root-cause writeup.

That reprocessing cost is **structural, not a bug** — there is no
cache-editing trick on this model that avoids it. What *is* avoidable is
*where* it happens. Today it happens inline with a real turn, so whichever
slot is serving the live conversation (main) eats the latency.

## The fix: prepare compacted history on the sidekick, then swap

1. **Trigger**, in the background, well before the real compaction threshold:
   a new, earlier threshold (`hot_swap_prep_threshold_percent`, suggest
   ~70–80% of `ContextCompressor`'s own trigger point) gives the background
   prefill time to finish before compaction would actually need to fire live.
2. **Build** the compacted message list using `ContextCompressor`'s existing
   summarization path (`_compress_context` already returns
   `(compressed_messages, new_system_prompt)` without mutating live state —
   call it on a *snapshot*, same pattern as the `flush_memories` threading fix
   from earlier tonight).
3. **Prefill** that compacted list into the sidekick's own slot from scratch —
   a real (or minimal, e.g. `max_tokens=1`) completion request with
   `id_slot=<sidekick>` forces llama-server to process and cache every token
   of it, on a slot the live conversation never touches.
4. **Swap** which physical slot is "main" — but only at a safe boundary
   (start of the next turn, never mid-generation). The sidekick, now warm
   with the compacted history, becomes main; the old main becomes the new
   sidekick.

The reprocessing cost doesn't disappear (can't, given IMROPE) — it moves
entirely onto spare capacity the live turn was never waiting on.

## State needed

Replace the current static `_pinned_id_slot` (see `run_agent.py`,
`_spawn_background_review`, `auxiliary_client.py`) with a pair that can
change at runtime:

```python
self._main_slot = 1       # was: self._pinned_id_slot = 1
self._sidekick_slot = 0
self._hot_swap_in_progress = False   # guards against overlapping prep attempts
self._hot_swap_ready = None          # None, or (compressed_messages, new_system_prompt)
```

Every place that currently reads `self._pinned_id_slot` (the `extra_body["id_slot"]`
assignment in the main completion path, `_spawn_background_review`'s override,
`auxiliary_client.py`'s two sites) needs to read `self._main_slot` /
`self._sidekick_slot` instead of a single fixed value — those call sites
already know which role they're playing (main vs. sidekick), so this is a
rename plus indirection, not new logic there.

## New methods (sketch)

```python
def _maybe_start_hot_swap_prep(self, messages: list) -> None:
    """Called once per turn, same place _compress_context is consulted.

    Cheap check + early return in the common case (below threshold, or a
    prep already in flight) -- this must never add latency to a normal turn.
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
        args=(list(messages),),          # snapshot -- same safety rule as flush_memories
        daemon=True, name="hot-swap-prep",
    ).start()

def _run_hot_swap_prep(self, messages_snapshot: list) -> None:
    try:
        compressed, new_system_prompt = self._compress_context(
            messages_snapshot, self._cached_system_prompt or "",
        )
        # Prime the sidekick slot: a real request against it forces the
        # prefill. id_slot must be self._sidekick_slot explicitly here --
        # do NOT read self._main_slot/_sidekick_slot again after this point
        # without re-checking they haven't changed (see race note below).
        self._prime_slot_with_messages(self._sidekick_slot, compressed, new_system_prompt)
        self._hot_swap_ready = (compressed, new_system_prompt)
    except Exception as e:
        logger.debug("hot-swap prep failed (non-fatal, stays on current main): %s", e)
    finally:
        self._hot_swap_in_progress = False

def _apply_pending_hot_swap_if_ready(self) -> None:
    """Call at the START of a turn, before building this turn's request --
    never mid-generation. Applies the prepared compaction and flips which
    slot is main."""
    if self._hot_swap_ready is None:
        return
    compressed, new_system_prompt = self._hot_swap_ready
    self._hot_swap_ready = None
    self._session_messages = compressed
    self._cached_system_prompt = new_system_prompt
    self._main_slot, self._sidekick_slot = self._sidekick_slot, self._main_slot
```

## Edge cases that need real handling, not hand-waving

- **A new user message arrives while prep is in flight.** Must proceed
  normally on the *current* main slot — never block waiting for prep. This
  falls out naturally if `_maybe_start_hot_swap_prep` only ever spawns a
  detached thread and the live turn path never reads `_hot_swap_ready` except
  at the top of the next turn.
- **Prep finishes mid-generation of an unrelated turn.** Don't apply the swap
  until `_apply_pending_hot_swap_if_ready` runs at the *next* turn boundary.
  `_hot_swap_ready` just sits there as a flag in the meantime.
- **Two prep cycles overlapping.** `_hot_swap_in_progress` guards this the
  same way `_bg_review_thread`'s liveness check already guards overlapping
  background reviews (see `_spawn_background_review`) — copy that pattern,
  don't invent a new one.
- **Prep fails** (server error, OOM, sidekick slot busy with real background
  work at that moment). Fail closed: log at debug, clear
  `_hot_swap_in_progress`, leave `_hot_swap_ready` as `None`. The session
  continues exactly as if hot-swap didn't exist; `ContextCompressor`'s normal
  (live, blocking) compaction is still the fallback safety net and must not
  be disabled or weakened by this feature existing.
- **Sidekick slot is legitimately busy** with real background work
  (`_spawn_background_review`, `auxiliary_client.py` hygiene calls) when prep
  wants to prime it. The prime request just queues behind that on the
  sidekick slot like any other request would — acceptable, since none of this
  is on the live-turn critical path. No special coordination needed, but
  worth confirming empirically it doesn't produce surprising latency for the
  *next* real hot-swap-prep cycle.
- **The demoted slot's stale cache.** After a swap, the old main slot still
  holds the pre-compaction history in its KV cache, now unused. Not urgent —
  it'll get reused/evicted the next time that slot is asked to do anything
  else — but an explicit `mem.seq_rm(id, -1, -1)`-equivalent clear (see
  `prompt_clear()` in the llama.cpp fork, already proven safe on IMROPE
  models since it never shifts positions) would reclaim that KV footprint
  immediately instead of leaving it to be overwritten organically.

## What this does NOT change

- `ContextCompressor`'s own trigger threshold and live (blocking-path)
  compaction logic stay exactly as they are — the fallback safety net if
  hot-swap prep hasn't completed in time.
- No change to `n_cache_reuse` or any cache-splice logic — irrelevant here,
  already disabled for this model.
- No change to `flush_memories`'s threading fix from earlier tonight — hot-swap
  prep is a parallel, independent background path, not a replacement for it.

## Suggested implementation order

1. Land the `_main_slot`/`_sidekick_slot` rename (mechanical, low-risk,
   testable in isolation — no swap logic yet, behavior identical to today).
2. Add `_maybe_start_hot_swap_prep` + `_run_hot_swap_prep`, but stub
   `_apply_pending_hot_swap_if_ready` to just log "would swap here" instead
   of actually swapping — verify prep fires at the right threshold, completes
   without errors, and never delays a live turn, over a real session, before
   wiring in the actual swap.
3. Wire in `_apply_pending_hot_swap_if_ready` for real, with the edge cases
   above each covered by a dedicated test (mirroring the style of
   `tests/run_agent/test_background_review_slot_pin.py` and
   `tests/cli/test_llama_telemetry.py` — bare `AIAgent.__new__` instances,
   stubbed background functions, explicit thread-join in tests rather than
   sleeping).
