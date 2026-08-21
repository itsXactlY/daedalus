---
name: rework-loop
description: Autonomous PERPETUAL site/artifact improvement loop. Use when supervising a nonstop parallel agent crew (workers in isolated git worktrees + a periodic judge) that continuously improves a repo/site while never ending or self-shutting-down. Covers the systemd supervisor, worker-worktree isolation, file-collision detection, judge rotation, and the loop-safety guards (no-shutdown veto, single-instance browser rule). This is the operator's preferred architecture for "improve this forever" — all freedom, leading-edge (WebGPU), no invented constraints.
---

# Rework Loop — Nonstop Parallel Crew Improvement

A **systemd user service** runs a bash supervisor forever. Each round it dispatches up to
3 **workers**, each in its OWN git worktree (branch `crew/rN-wM`) so they never collide on
files/index. Every N rounds a **judge** scores execution and writes a fresh 5-item queue.
Loop must NEVER end.

This is the evolved architecture. The older single-cron-job cadence is superseded.

## Operator Directive (first-class, overrides every spec rule list)

- **"THE CREW LOOP HAS AND NEEDS ALL FREEDOM."** There are NO inherited design
  constraints — no `no autoplay`, no `no skip`, no `no inline styles`, no `Three.js CDN
  only`, no `WHY in commit` requirement, no `rAF only`/`zero setInterval`. NONE of that
  existed before the loop and it does NOT bind workers or judge. Crew picks the best
  modern technique.
- **"FULL INTERACTIVE WEBGPU EXPERIENCE. BE LEADING — WE DON'T SHIP PRODUCTS OF
  YESTERDAY."** Real-time/graphics work should graduate toward WebGPU (WGSL compute
  shaders, GPU particles, post-FX) wherever it wins; WebGL stays only as a graceful fallback.
- The ONLY hard constraints are the operator's infrastructure orders, which stay:
  - Work only in the rework fork (branch `visual/cockpit-demo`); never live-root/design-import.
  - Any read-only mounts (e.g. `/mnt/...`) are copy-only.
  - WebGPU falls back gracefully to WebGL when `navigator.gpu` is unavailable.
  - **Browser work via Hermes browser tools ONLY** — never spawn headless Chrome/Chromium.
  - Each queue item's `files:` list must be accurate (the collision detector parses it).

## Architecture

```
systemd --user service  →  loop-supervisor.sh (forever loop)
   │  per round: up to 3 workers CONCURRENTLY
   │    each worker: hermes -z "$(built worker prompt)" in its OWN worktree
   │       (branch crew/rN-wM) → delegates a sub-crew → verify → commit [WHY]
   │  file-collision detection: item collisions with same `files:` are deferred to later rounds
   │  after each round: merge each crew branch → mark [DONE] → cleanup
   └─ every 5 rounds (or when queue empty): SOLO 5D JUDGE writes new verdict + Queue Q1..Q5
```

Files (canonical layout, operator home `/home/alca`):
- `loop-supervisor.sh` — the systemd unit `ExecStart`; owns rounds, wait, merge, cleanup, guards.
- `judge-prompt.md` — SOLO judge model-prompt (read fresh each run; edits take effect next round).
- `crew-worker-prompt.md` — worker prompt; placeholders `{{WORKID}}`, `{{FOCUS}}`.
- `judge-verdict.md` — source of truth for the queue; supervisor reads `[OPEN]` items from it.
- `SCHLACHTPLAN.md` — the visual spec; CONTEXT only, older §-rules superseded by the directive above.
- `REWORK_LOOP.md`, `.rework-iter.log` — master log + authoritative iteration log (read-only for workers).

## The Judge — Queen of the loop

- Runs a SOLO 5D judgement: inspects code (node --check /assets), media inventory, architecture;
  scores prior queue execution 0-100; decides DIMENSION verdict + THE BREAKTHROUGH; writes fresh Queue.
- **Judge must design the queue for PARALLELISM:** Q1..Q3 should touch DISJOINT `files:` lists so
  3 workers run concurrently. Mark dependent items "(depends on Qn)" so they stagger.
- Judge must write only OPERATOR DIRECTIVE (the two operator orders), NOT the old §7 rules.

## Guards (operator orders, non-negotiable)

### 1. Perpetual-Loop Guard (the loop NEVER ends)
A judge may decide "the work is exhausted, recommend shutdown" after many 5D verdicts and write
a `Q1: shutdown`/`stop the systemd` item. If executed, the crew kills its own host. Prevent with
THREE independent layers:
1. **Supervisor veto:** when collecting `[OPEN]` items, `grep -qiE 'shutdown|systemctl stop|systemctl disable|stop the service|stop the systemd|formal loop shutdown'` and skip+VETO-log any match — never assign it.
2. **Judge prompt ban:** "THE LOOP NEVER ENDS. Never queue a shutdown... if exhausted, find NEW work."
3. **Worker prompt ban:** a worker must REFUSE/ never touch systemd; write `.item-done` with reason instead.
When a judge legitimately writes "audit-only / human observation only" items for a whole queue, that
empty production pattern is the shutdown smell — the supervisor should force a fresh judge instead.

### 2. Empty-queue → Force a Judge (not seed-queue)
Once a verdict file exists and has 0 `[OPEN]` items left, do NOT fall back to the seed queue
(those seed gaps are long done). Instead run a **forced judge round** to mint fresh work. The
seed queue is only for the very first run ever (no verdict file yet).

### 3. Single-instance browser guard
A multi-worker 24/7 loop would dribble-DDoS the machine with accumulating headless Chrome.
- **No worker/judge/supervisor may spawn headless Chrome/Chromium directly** (`google-chrome`,
  `chromium`, `--headless`, `--remote-debugging-port`, Playwright/Puppeteer binary launches).
- Only the Hermes browser tools (browser_navigate / browser_vision / browser_snapshot /
  browser_console) are permitted — one managed instance, torn down by Hermes.
- Supervisor reaps chrome-family processes under its own tree after each round (kill list).
- Browser-verification queue items MUST instruct "use only Hermes browser tools", never a raw binary.

## Supervisor round logic (key details)

- Worker: `( cd "$WORKTREE_BASE/r{round}-w{wid}" && "$HERMES" -z "$prompt" --cli ) >> log &`
- Collect open items from `judge-verdict.md` lines starting `[OPEN]`.
- File collision: `item_files()` (after `files:`), tokens compared across assigned items; colliders deferred.
- After `wait`, **reap chrome**, then merge each branch `--no-ff` and **only count success if HEAD moved**
  (Pitfall #4), `branch -D`, `worktree remove`, `mark_done` (match leading `Q<n>:` token → `[DONE]`).
- Merge conflict → `merge --abort`, keep branch+worktree for the judge.

## Pitfalls

### 1. sed prompt substitution breaks when the value contains the delimiter
When building a worker prompt by `sed -e "s|{{FOCUS}}|$item|g"`, the queue item text contains `|`
(judge item format: `[OPEN] Q1: goal | why: ... | files: ...`). The first `|` in the value ends the
sed substitution → the resulting prompt is truncated/garbage → the worker gets a broken or empty
focus. **Use Python `str.replace` (or a heredoc via env) for prompt templating, never sed with a
delimiter that appears inside the values.** Symptom: rounds "complete" in seconds; workers print a
TUI banner then immediately "Input is not a terminal... shutdown"; branches are created but never
committed.

### 2. no-op merge must not mark [DONE]
`git merge --no-ff` returns exit 0 with "Already up to date" when the worker committed nothing.
Treat that as NOT a success — it would mark the item [DONE] with the previous HEAD's hash even though
no work landed. Compare `$(git rev-parse HEAD)` before vs after: only `MRC==0 && HEAD changed` counts
as success → mark [DONE]; else leave [OPEN] (worker may have crashed) or log no-op.

### 3. Subagent checker race (editor+checker in same batch)
Spawned together, the checker reads files before the editor's writes flush → false FAILs.
Captain's own re-read is the real gate. Serialize if you need reliable checking. (See
`references/subagent-verification-timing.md`.)

### 4. Parallel workers must never touch the same file
Without worktree isolation + file-collision detection, parallel workers stomp each other.
Worktree-per-worker + deferred colliding items is what makes real parallel progress possible.
Don't naively parallelize onto shared files.

### 5. Stale git state / orphaned cleanup
Run `git status --short && git log --oneline -5` first. On start, `startup_cleanup`:
merge stray `crew/*` that have real work, delete empty/no-op branches, remove stale worktrees.
On repeated restarts leftover branches accumulate (incl. conflicted ones) — audit and drop stale ones.

### 6. .item-done + real commit = lost work
A worker can commit real work AND write `.item-done` (it verified the result and concluded
"done"). The `.item-done` handler checks for the marker FIRST and marks `[DONE]` without
merging — the commit sits on the orphaned branch forever, never reaching HEAD. The judge
keeps scoring "ABSENT from HEAD" cycle after cycle because the merge never happened.
**Fix:** before treating `.item-done` as "no change", check
`git rev-list --count HEAD..$branch` — if > 0, the branch has real commits and MUST be
merged despite the marker. Only treat `.item-done` as no-change when the branch is NOT
ahead of HEAD. Log: "worker wrote .item-done BUT has N commit(s) — merging branch first".
Symptom: work built in Round N, judge sees it missing in Round N+1, queues "merge it" again,
repeat for 3+ cycles.

### 7. HUMAN-TASK veto (items only a human on a GPU machine can do)
Items requiring a real GPU browser (screenshots on RTX, visual proof on hardware) must NEVER
be assigned to crew workers — headless has no GPU, workers would loop on them forever.
Add `is_human_task_item()` grep for `human task|operator task|requires operator|rtx|take N
screenshots|visual proof on gpu|needs a human` → skip+log as "OPERATOR-PENDING", never assign.
These items stay `[OPEN]` in the verdict for the operator to execute manually. The operator's
explicit correction: "I WANT ONE AGENT TODO THIS, NOT ALL OF THEM" — a single human does it,
not the parallel crew. `[HUMAN TASK]` prefix in the verdict (instead of `[OPEN]`) also works
— the supervisor's `[OPEN]` filter skips it automatically.

### 8. Free-model outsourcing — ALL loop components must be $0
The operator requires EVERY component (workers AND judge) on free/$0 models. Running the
judge on the main paid model while workers are free is unacceptable — "NO PAID MODEL FFS".
Pattern: define `FREE_MODELS` array, `pick_worker_model()` round-robin function, and a
`JUDGE_MODEL` (use the biggest free model, e.g. `nvidia/nemotron-3-ultra-550b-a55b:free`).
Worker start: `"$HERMES" -z "$prompt" -m "$WORKER_MODEL" --cli`. Judge start:
`"$HERMES" -z "$(cat "$JUDGE_PROMPT")" -m "$JUDGE_MODEL" --cli`. Different workers in the
same round get different models (round-robin by `round*WORKERS+wid`), so a rate-limit on
one model only blocks 1 of 3 workers.

### 9. Rate-limit circuit breaker (429 → exit=0 → infinite loop)
When free models hit HTTP 429 ("free-models-per-day-high-balance"), `hermes -z` returns
exit=0 with an error MESSAGE but no actual output. The supervisor treats exit=0 as success,
the queue stays empty, and the forced-judge loop fires infinitely: "queue exhausted → judge
→ 429 → exit=0 → queue still exhausted → repeat". **Fix:** track consecutive judge failures
(a judge that exits 0 but writes no new verdict = failure). After N consecutive failures
(e.g. 3), pause the loop with a long backoff (30min+) instead of spinning. Log:
"CONSECUTIVE JUDGE FAILURES — likely rate-limited, pausing". Alternatively, check the
judge's log output for "429" or "Rate limit" strings and treat that as a failure even
with exit=0.

## Failure signatures (quick reference)
See `references/parallel-supervisor-failures.md` for the exact log signatures and
fixes of the six failure modes seen in live operation: sed-prompt truncation,
no-op-merge [DONE], judge self-termination, empty-queue seed re-grind, browser
DDoS, and leftover conflicted branches. Recognize them by their log patterns —
each fix is a one-line policy in the supervisor or prompt.

## Status check (how to check the loop alive)

- `systemctl --user is-active mazemaker-rework-loop.service` → `active`
- `pstree -p $(systemctl --user show -p MainPID --value <svc>)` → shows `bash(...)-hermes(theme...)...`
- tail the supervisor log; workers should live minutes, not seconds.
- `grep '\[OPEN\]' judge-verdict.md` → current queue.

## For this operator specifically
- Communication direct, German when they write German; no fluff.
- "lass laufen" = never stop the production supervisope loop. Reboot-aware: it's a systemd user service.
- After substantive outcomes, `mazemaker_remember(label="decision:rework-judge-<N>"/ops:rework-*", ...)`