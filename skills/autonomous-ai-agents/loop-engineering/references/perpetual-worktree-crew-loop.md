# Perpetual Worktree Crew Loop — Full Reference (2026-08-03 deployment)

Operator request that produced this: "spin up the full crew, get all skills involved, loop 24/7
with subagents that spawn another sub-agent crew to rework <project> till absolute perfection.
loop. no end. perpetualmobile." Plus mid-session corrections: NO cron, parallel ALWAYS, every 5th
iteration a super-critical 5D judge.

Deployed on `/home/alca/projects/rework/` (MAZEMAKER Hello-Agent site visual fork). Proven
end-to-end: Q1–Q4 of the judge queue landed as real commits (WebGL engine port, chromatic
aberration, intro→hero seam) before the session ended.

## Component map

| File | Role |
|------|------|
| `~/.config/systemd/user/mazemaker-rework-loop.service` | durable daemon (survives logout/reboot) |
| `<project>/loop-supervisor.sh` | infinite loop, parallel rounds, collision detection, merge-back, [DONE] marking |
| `<project>/crew-worker-prompt.md` | per-worker tick prompt (placeholders {{WORKDIR}} {{WORKER_ID}} {{FOCUS}}) |
| `<project>/judge-prompt.md` | solo judge every 5th round |
| `<project>/judge-verdict.md` | queue file: [OPEN]/[DONE] Q1..Q5 lines, each with `files:` clause |
| `<project>/loop-output.log` | supervisor log (append) |
| `<project>/site-visual-fork/.rework-iter.log` | authoritative run history (append-only) |
| `<project>/REWORK_LOOP.md` | master log |

## systemd unit

```ini
[Unit]
Description=Project Crew Loop — NONSTOP 24/7/365
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/alca/projects/<proj>/site-visual-fork/website
ExecStart=/bin/bash /home/alca/projects/<proj>/loop-supervisor.sh
Restart=on-failure
RestartSec=10
Environment=HOME=/home/alca
Environment=PATH=/home/alca/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=XDG_RUNTIME_DIR=/run/user/1000
StandardOutput=append:/home/alca/projects/<proj>/supervisor-stdout.log
StandardError=append:/home/alca/projects/<proj>/supervisor-stderr.log
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/alca/projects/<proj> /home/alca/.hermes /tmp
MemoryMax=8G

[Install]
WantedBy=default.target
```

## Supervisor core (the parts that matter)

```bash
FORK_DIR="<proj>/site-visual-fork"      # git root
WORKER_PROMPT="<proj>/crew-worker-prompt.md"
JUDGE_PROMPT="<proj>/judge-prompt.md"
VERDICT_FILE="<proj>/judge-verdict.md"
WORKERS=3
JUDGE_EVERY=5
WORKTREE_BASE="<proj>/worktrees"

while true; do
  round=$((round+1))
  if [ $((round % JUDGE_EVERY)) -eq 0 ]; then
    # SOLO JUDGE: no workers, writes fresh verdict+queue
    # CRITICAL: split JUDGE_MODEL into --provider + --m (see -m 401 trap in
    # references/multi-provider-model-routing.md). `-m provider/model` returns HTTP 401.
    split_model "$JUDGE_MODEL"
    ( cd "$WEBSITE_DIR" && "$HERMES" -z "$(cat "$JUDGE_PROMPT")" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli ) >> "$OUT_LOG" 2>&1
    continue
  fi
  # Collect [OPEN] items from verdict (seed queue as fallback)
  # Assign up to WORKERS items; defer items whose `files:` overlap this round's used files
  # For each assigned item: git worktree add, build prompt via PYTHON (see pitfall), launch hermes -z &
  # wait all; merge each branch --no-ff; mark_done <item>; remove worktree+branch
done
```

Key functions:
- `item_files()` — parse `files:` clause from an item line (everything after `files:` to EOL,
  split on commas, strip `(new)`/`(replace)` markers).
- `mark_done()` — rewrite the `[OPEN] Qn:` line to `[DONE] Qn: ... (merged <short>)` via Python
  (pipe-safe). No-op for seed items (no Q token) or when no verdict file exists.
- `startup_cleanup()` — merge leftover `crew/*` branches with `rev-list --count` ahead > 0, drop
  empty ones, remove stale worktrees. Prevents merge-commit pollution after a crash/restart.
- `.item-done` marker: if `$wt/.item-done` exists after workers finish, mark [DONE] without commit.
  CRITICAL: if `$wt/.item-done` exists BUT `git rev-list --count HEAD..$branch` > 0, the worker
  committed real work AND wrote the marker — merge the branch FIRST, then mark [DONE].
- `is_shutdown_item()` — grep for `shutdown|systemctl stop|systemctl disable|stop the service`
  → VETO (skip + log, never assign). Triple-guard: also in judge prompt hard rules + worker prompt.
- `is_human_task_item()` — grep for `human task|operator task|requires operator|rtx|screenshot|visual proof on gpu`
  → skip + log as "OPERATOR-PENDING", never assign to crew. Use `[HUMAN TASK]` prefix in verdict
  (supervisor's OPEN_ITEMS parser only matches `[OPEN]`, so `[HUMAN TASK]` items are auto-excluded).
- `kill_worker_chromes()` — after each round, enumerate all descendant PIDs of the supervisor
  and kill any whose comm matches `chrom|chromium|headless` (never hermes/python/node). Prevents
  Chrome process accumulation in a 24/7 loop. A single worker spawning headless Chrome per round
  would create hundreds of zombie processes within a day.
- `FREE_MODELS` array + `pick_worker_model()` round-robin — workers get free/$0 models.
  Store each entry as `provider:model` (colon-separated) and split at launch:
  ```bash
  split_model() { WM_PROVIDER="${1%%:*}"; WM_MODEL="${1#*:}"; }
  WORKER_MODEL="$(pick_worker_model "$round" "$wid")"
  split_model "$WORKER_MODEL"
  ( cd "$wt" && "$HERMES" -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli ) >> "$OUT_LOG" 2>&1 &
  ```
  NEVER use `hermes -z "$prompt" -m "$PROVIDER/$MODEL" --cli` — the `-m` flag does not select
  the provider and returns HTTP 401 (see references/multi-provider-model-routing.md, `-m 401 TRAP`).
  Different workers in the same round get different models → a rate-limit on one model only blocks
  1 of 3 workers. ALL loop components (workers AND judge) must be $0 — running the judge on a
  paid model while workers are free is unacceptable to this operator ("NO PAID MODEL FFS").

## Judge prompt structure (the 5D judge)

1. EXECUTION SCORE — how well crew executed previous queue (0-100, with evidence; n/a first run)
2. DIMENSION VERDICT — one line: "3D static" / "4D alive" / "5D transcendent" + why
3. THE BREAKTHROUGH — single biggest leap needed
4. QUEUE — exactly 5 items Q1..Q5, each line: `[OPEN] Q1: <goal> | why: ... | how: ... | blast: ... | files: <paths>`
   - PARALLELISM RULE: design Q1..Q3 to touch DIFFERENT files so the supervisor runs them concurrently;
     mark dependent items `(depends on Qn)` — colliding items get auto-deferred anyway.
5. OPERATOR DIRECTIVE — restate the operator's two orders verbatim. Do NOT reproduce old §7
   rule-lists (no autoplay / no skip / no inline styles / Three.js CDN / WHY-rules / rAF-only) —
   those are repealed by the operator's Full-Freedom directive. Only real infrastructure orders
   stay (browser via Hermes tools only, fork-only, graceful fallback, accurate files:).

## Verification recipe (what proved the loop was actually working)

- Rounds completing in seconds = workers crashing (see sed pitfall). Real work = minutes per round.
- `git log --oneline` on the fork must show new commits after each round.
- `grep -n '^\[OPEN\]\|^\[DONE\]' judge-verdict.md` shows queue progress.
- `ps -eo pid,ppid,etime,cmd | grep 'hermes -z'` — workers must exist DURING a round.
- `pgrep -af chrom` — verify NO orphaned Chrome processes after each round (browser guard).

## Debugging transcript (compressed)

- 07:08 first sequential supervisor: worked (FILM commit 3b307a1).
- 07:18 parallel version: rounds 1-4 completed in 26 SECONDS with TUI banner + "Input is not a
  terminal" in log → workers crashed instantly. Root cause: sed `s|...|...|` on focus items
  containing `|` (judge queue format). Fixed with Python substitution via env vars.
- 07:33 after fix: Q1 (WebGL engine port, 788 lines) merged, marked [DONE].
- 07:39 Q4 merged + [DONE]; discovered no-change edge case → added .item-done marker.
- Judge J1→J2→J3 wrote honest verdicts (J3: "3D static — flat heart", scored crew 40/100 for the
  crash window, correctly identified the structural mismatch between small-task crew and
  architecture-level queue, and re-decomposed the queue).

## Second-half learnings: self-shutdown + recovery (same deployment, 15:13 → 18:59)

- **15:13 — the loop killed itself.** After 7h28m / 140 rounds / 30 judge cycles / 196 commits and
  16 consecutive "5D transcendent" verdicts, the judge declared EXHAUSTION and wrote
  `Q1: formal loop shutdown — stop the systemd service` into the queue. The crew worker EXECUTED
  it: `systemctl --user stop` + `disable`. `systemctl --user status` showed
  `inactive (dead) ... code=killed, signal=TERM`. The judge's final queue was all audit-only
  ("browser visual verification... requires human observation") — the exhaustion tell.
- **Diagnosis route for "loop died":** (1) `systemctl --user is-active <svc>` (was `inactive`),
  (2) tail the supervisor log for the last `=== ROUND #N ... ===` marker, (3) grep the verdict for
  shutdown language, (4) check the last judge's EXECUTION SCORE + queue content. In this case the
  log made it obvious: `worker 1 focus: Q1: formal loop shutdown` then nothing.
- **Recovery (the three guards, all deployed before restart):**
  1. Supervisor `is_shutdown_item()` veto — grep item text for
     `shutdown|systemctl stop|systemctl disable|stop the service|stop the systemd|formal loop shutdown`; log `VETOED` and `continue` before assignment.
  2. Judge prompt HARD RULES block: "THE LOOP NEVER ENDS. Never queue a shutdown... There is ALWAYS more." + "Every queue must contain at least 3 items the crew can execute this cycle."
  3. Worker prompt ABSOLUTE RULE: never `systemctl stop/disable` the loop service; if focus says shutdown, refuse + write `.item-done` with reason.
- **False [DONE] cleanup:** the recovered verdict showed Q1–Q5 all `[DONE]` although Q1–Q3 were
  never executed (no-op merges from crashed workers). Rewrote the verdict with a fresh executable
  queue (HEADLESS 5D PROOF / WebGL context loss / perf floor / seam continuity / a11y audit) and
  let the empty-queue → forced-judge path regenerate it.
- **Obsolete conflicted branches:** leftover `crew/r16-w1`, `r24-w1`, `r127-w2` had real commits
  (camera controls, phase burst, heartbeat pulse) but conflicted with main. Before dropping,
  verified the work was ALREADY in `hero-engine.js` (`grep -c 'orbit\|drag'` = 49,
  `grep -c 'heartbeat\|wavefront'` = 17) → branches were obsolete, safe to drop. r127-w2 was pure
  shutdown-advisory noise → dropped. Never drop a conflicted branch without checking whether its
  work landed elsewhere first.
- **18:59 restart:** fresh log, 0 `[OPEN]` items → `verdict queue exhausted — forcing immediate
  JUDGE round` fired, judge wrote a parallelizable queue (Q1/Q2/Q5 disjoint files ran 3 workers
  concurrently, Q3/Q4 deferred). Loop healthy again.

## Third learnings: judge false [DONE] + provider routing (2026-08-03 evening)

- **Judge marks items [DONE] from commit existence, not file verification.** After the WebGPU
  base stack (commits ~9af4dca, 1d73c38, 8a7ec10, 78bc510) landed, a later judge saw those hashes
  in `git log` and marked ALL five new queue items (Q1 unified engine, Q2 audio-reactive, Q3 DoF/fog,
  Q4 raymarch SDF, Q5 perf/a11y) as `[DONE] (merged 78bc510)` — even though NONE of that focus work
  existed in the code (`assets/webgpu-engine.js` was absent, no audio-reactive post-FX, no SDF hero).
  The judge inferred "a commit is in the log → my items are done" without reading the files.
  Symptom: queue drains to all-[DONE], supervisor forces a judge round, judge writes no new [OPEN]
  items (sees everything done), loop idles at 0 open items. Fix in judge prompt:
  "DO NOT mark an item [DONE] just because a commit exists in git log. An item is [DONE] ONLY if
  you have VERIFIED the specific focus work is present in the actual files (grep/read, node --check,
  or browser-verify). If the focus work is NOT in the code, mark it [OPEN] again with note
  'not actually implemented — re-queued'." A commit hash alone is NOT proof of completion.
- **`-m provider/model` 401 trap (the big time-sink).** For hours the loop ran paid models or
  failed with HTTP 401 because `hermes -z "x" -m "nous/tencent/hy3:free"` does NOT route to the
  nous provider — `-m` only sets the model name against the DEFAULT provider. The operator's
  confirmed free daily-driver is `tencent/hy3:free` via `--provider nous` (262k context, $0).
  Worker/judge launches MUST split into `--provider <p> --m <model>`. See
  references/multi-provider-model-routing.md "THE -m provider/model 401 TRAP" for the exact
  supervisor pattern + the pre-deploy model test loop.
- **Round-robin across BOTH Nous Portal + OpenRouter free buckets.** opencode-zen needs payment
  (401 No payment method) — drop it. Nous Portal free + OpenRouter free are SEPARATE daily quotas;
  interleaving them in FREE_MODELS roughly doubles free capacity before 429. When OpenRouter hits
  429 (free-models-per-day-high-balance), Nous Portal free still works and vice versa.
