# Slot hot-swap: moving compaction cost off the live turn

Implemented in `run_agent.py`. Tests: `tests/run_agent/test_hot_swap.py`.

## Problem

`ContextCompressor` compacts history when a turn crosses `threshold_tokens`.
The summarization is an LLM call made inline: `_compress_context` is invoked
from the turn loop and the turn cannot continue until it returns.

On Qwen3.5 (`QWEN35`, IMROPE RoPE, `n_pos_per_embd() == 4`) the compacted
prompt also cannot reuse the previous KV cache. Any edit other than a tail
truncation forces a full reprocess, because `seq_add()` — the position-shift
primitive `n_cache_reuse` and cache splicing both need — asserts on non-scalar
RoPE positions (see `bad7199cd` in `llama.cpp-adaptive-kv-streaming`).

So a compaction costs the turn a summarization call plus a full re-prefill.
Neither can be removed on this model. Both can be moved off the turn.

## How it works

Prep, in a daemon thread, when a turn reaches `_hot_swap_prep_ratio` (0.75) of
the compaction threshold:

1. `context_compressor.compress()` on a snapshot of `messages` produces the
   compacted list. This is the expensive part.
2. `_prime_slot_with_messages()` sends that list to the sidekick slot with
   `max_tokens=1`, which makes llama-server prefill it into that slot's cache.
3. The result is parked in `_hot_swap_ready`.

Apply, at the start of the next turn, before anything sizes the request:

4. `_apply_pending_hot_swap_if_ready()` merges the prepared compaction with
   whatever arrived since, and promotes the warm slot to main.
5. `_compress_context(..., precomputed=merged)` runs the remaining bookkeeping
   with the summarization skipped.

Prep deliberately calls `context_compressor.compress()` and not
`_compress_context()`. The latter ends the SQLite session, rotates
`session_id`, and archives to mazemaker; none of that may happen speculatively
for a compaction that might be discarded. Those steps stay on the turn, where
they are cheap.

## Merging, not replacing

A prep describes a prefix of the conversation. Between prep and apply the user
adds turns, so applying it as a wholesale replacement would drop them.
`_apply_pending_hot_swap_if_ready` records `snapshot_len` at prep time and
merges:

    merged = prepared_compressed + messages[snapshot_len:]

If `len(messages) < snapshot_len` the history no longer contains that prefix
and the prep is refused.

## Invalidation

`_compaction_generation` increments on every `_compress_context` call. Prep
records the generation it started under and is discarded if it no longer
matches — checked both after summarization and again after the prefill. This
is what stops a prep from being applied over a history that an inline
compaction already replaced.

## Slot assignment

`_pinned_id_slot` holds main's slot (1 by default); `_sidekick_id_slot()`
derives the other. A swap sets `_pinned_id_slot` to the warmed slot and calls
`auxiliary_client.set_sidekick_id_slot()` with the old one, so hygiene and
compression calls follow rather than landing on top of main.
`_spawn_background_review` derives its slot the same way.

If the prefill failed, `slot` is `None`: the summary is still applied, no swap
happens, and main stays where it is.

## Failure behavior

Every failure path leaves the session running as if the feature were absent,
with `ContextCompressor`'s inline compaction as the fallback:

- Summarization raises: `_hot_swap_ready` stays `None`, `_hot_swap_in_progress`
  is cleared in a `finally`, a later turn can try again.
- Prefill fails or the backend is not local: summary kept, no swap.
- A compaction lands mid-prep: prep discarded on the generation check.
- Prep still running when the threshold is crossed: the turn takes the normal
  blocking path. Prep is not waited on anywhere.
- `_hot_swap_in_progress` prevents concurrent preps, matching the liveness
  guard `_spawn_background_review` already uses.

## Known rough edges

- A discarded prep still increments `context_compressor.compression_count`,
  because the counter lives inside `compress()`. Display only.
- After a swap the demoted slot still holds the pre-compaction cache until
  something else reuses it. An explicit `prompt_clear()`-equivalent
  (`mem.seq_rm(id, -1, -1)`, which shifts no positions and is safe on IMROPE)
  would reclaim it sooner.
- A prefill queued behind real sidekick work waits for it. Acceptable, since
  nothing on the live path depends on it, but worth measuring whether it
  delays the following prep cycle.
- `_hot_swap_prep_ratio` is untuned. Too early and the snapshot is stale by
  apply time; too late and prep does not finish before the threshold.

## Turning it off

Set `self._hot_swap_enabled = False`. Prep never starts and the blocking path
behaves exactly as before.
