# DECIDE Phase Saturation & [SILENT] Delivery (2026-06-22 12:48Z)

This is a concrete worked example of a **saturated** DECIDE cycle — one where
the discovery pool is fully covered by recent decisions and there is genuinely
nothing new to act on. It pairs with `decide-phase-skip-rule-2026-06-21.md`
which covers the busy-cycle case.

## The Saturation Pattern

When the cron runs every 60 minutes and each cycle writes its full 3-rank
quota, the discovery pool can become fully covered within the 2-hour dedup
window. At that point, every subsequent cycle will see all its candidate
discoveries mapped to recent `decision:rank-*` memories and have nothing left
to rank.

This is normal and healthy system behavior, not a failure. The right action
is to **report [SILENT]** so the cron delivery system suppresses output rather
than spamming the user with "no action" updates.

## Concrete Example: 2026-06-22 12:48Z Cycle

**Current UTC time**: 2026-06-22 12:48:14 (cron timestamp `20260622_124814`)

**Decision cycles in the prior 4h window** (each writing its full 3-rank quota):

| Cycle time (UTC) | Decisions written | Theme |
|-----------------|-------------------|-------|
| 11:00 | 826305, 826307 (+ 1) | Lean4 / formal-verification / DAC-CEJA |
| 11:15 | 826314, 826315, 826316 | EconcsLib Lean4 / Auto-Conjecture / Chiplet IP |
| 11:30 | 826318, 826319, 826320 | Kimi K2.5 AMA / vukrosic / Boötes3 neutrino |
| 11:45 | 826323 (+ 2) | EUROPA consortium + QEC + BH-explode |
| 12:00 | 826328, 826329, 826330 | Polymarket Mythos / FERC grid / OpenAI age-prediction |
| 12:33 | 826339, 826340, 826341 | Aleniglipron GLP-1 / Masi embodiment / Cuzzolin ToM |

**Today's 3 discovery memories**:
- 826311 — `discovery:pulse-wurm-20260622_freshdir-vukrosic-osai` → ranked at 11:30 (decision 826319)
- 826312 — `discovery:pulse-wurm-20260622_freshdir-europa-granch` → ranked at 11:45 (decision 826323)
- 826313 — `discovery:pulse-wurm-20260622_freshdir-kimi-k25-ama` → ranked at 11:30 (decision 826318)

ALL three of today's discoveries are already covered. The 2-hour dedup window
(10:48 UTC → 12:48 UTC) overlaps with 6 prior cycles writing 18 decisions.
No new discoveries have been created since 12:33 UTC (the most recent decision
was 15 minutes before this cycle).

**Verdict**: nothing to rank. Report `[SILENT]`.

## How to Detect Saturation

A DECIDE cycle is saturated when ALL of these are true:

1. The 24h discovery pool (from `mazemaker_browse(label_prefix="discovery:")`)
   contains ≤ 3 unranked discoveries.
2. Every unranked discovery has a corresponding `decision:rank-*` memory
   whose `content` references the discovery's ID.
3. All those decision memories were created within the 2h dedup window
   (i.e., `< (current UTC - 2h)`).
4. No new discoveries have been created since the most recent decision
   timestamp.

When all 4 hold, there is genuinely nothing actionable. Skip the
mazemaker_remember calls entirely.

## The [SILENT] Cron-Delivery Rule

When the DECIDE phase has nothing actionable, the response must be exactly:

```
[SILENT]
```

Followed by **nothing else**. No markdown, no commentary, no "no action
required" note. Per the cron delivery contract:

> "SILENT: If there is genuinely nothing new to report, respond with exactly
> '[SILENT]' (nothing else) to suppress delivery. Never combine [SILENT] with
> content — either report your findings normally, or say [SILENT] and nothing
> more."

The delivery system treats `[SILENT]` as a magic token and suppresses the
output. Anything appended to `[SILENT]` defeats this and causes an empty
or noise message to be delivered.

## What NOT To Do In A Saturated Cycle

Common mistakes when a cycle finds nothing actionable:

1. **Padding with low-quality items**: Writing decisions for NICE_TO_KNOW
   items that score below threshold just to fill 3 ranks. The 3-rank limit
   is a maximum, not a quota. A 0-rank cycle is valid. See
   `references/decision-label-format.md` ("When a Cycle Has < 3 Ranks").
2. **Re-ranking already-thoroughly-decided items**: A discovery from 4h ago
   already has a full decision with action items. Re-ranking it is duplicate
   work. The 2h dedup window is the minimum bar, not the only filter —
   also ask "is there new evidence since the decision was written?"
3. **Reporting "no action" as content**: Writing `[SILENT] — no discoveries
   to rank this cycle` or similar. This is the most common pitfall. It
   defeats the magic token. Just write `[SILENT]` and stop.
4. **Skipping the [SILENT] check entirely and writing empty decisions**:
   Writing `decision:rank-...-nothing-to-act-on` defeats the purpose and
   pollutes the graph.

## Frequency Of Saturated Cycles

In the 2026-06-22 cadence, saturation is rare but observable. With a
60-minute cycle and a healthy discovery rate of ~3-6 novel findings/day,
the pool usually drains over 1-2 cycles. Saturation occurs when:

- Multiple consecutive cycles hit the same axis cluster (e.g., 3 cycles
  all on Lean4/formal-verification topics).
- The discover phase has a quiet tick (e.g., 0-novel dual-phase ticks
  like `discovery:pulse-wurm-20260621_1721_tick`).
- The corpus has been thoroughly mined and the current period's novel
  content has all been processed.

Expect 1-2 saturated cycles per day as normal background state. More than
3 consecutive saturated cycles suggests the discover phase is starving —
check pulse-wurm2 health and tick logs.

## Parsing Large Persisted Recall Outputs

When `mazemaker_recall` returns >500KB of results, the tool saves the
output to `/tmp/hermes-results/call_<id>.txt`. The persisted file has a
nested JSON structure that's easy to misparse:

- **Recall tool**: top-level keys are `result` (JSON STRING) and
  `structuredContent` (DICT).
  ```python
  with open(path) as f:
      data = json.loads(f.read())
  results = json.loads(data['result'])  # data['result'] is a string
  # OR: results = data['structuredContent']['results']  # already a list
  ```
- **Browse tool**: top-level keys are `result` (string) and
  `structuredContent` (DICT containing `memories` key).
  ```python
  with open(path) as f:
      data = json.loads(f.read())
  memories = data['structuredContent']['memories']  # list, NOT data['memories']
  ```

Always inspect the top-level keys first. The two tools use different
internal shapes and a copy-paste from one to the other will silently
return empty data.

## How To Verify Saturation Quickly

Three mazemaker calls, in this order, are sufficient:

1. `mazemaker_browse(label_prefix="discovery:", limit=30)` → check the
   30 most recent discoveries for any unranked items.
2. `mazemaker_recall(query="decision:rank-<YYYYMMDD>", limit=20)` →
   check the current day's decisions, parse their `created_at` and the
   discovery IDs they reference.
3. Cross-reference: any discovery in (1) whose ID appears in any decision
   from (2) AND whose decision was created in the last 2h → SKIP.

If all discoveries in (1) are skipped, the cycle is saturated → `[SILENT]`.

This 3-call pattern runs in <30 seconds and produces a definitive
saturation verdict without needing to inspect the 2-hour window's full
decision history.