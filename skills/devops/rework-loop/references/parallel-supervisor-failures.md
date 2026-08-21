# Parallel Supervisor Failure Signatures (from live operation 2026-08-03)

Concrete failure modes seen running the nonstop parallel crew loop, with the
exact symptoms so a future session can recognize them in minutes.

## 1. sed-delimiter prompt truncation → instant worker crashes

**Setup:** worker prompt built with `sed -e "s|{{FOCUS}}|$item|g"`.

**Queue item format contains `|`:**
`[OPEN] Q1: port engine | why: spec § | how: ... | files: assets/hero-engine.js`

**Failure:** the first `|` inside the item value terminates the sed substitution.
Prompt comes out truncated/garbage. `hermes -z "$prompt" --cli` then receives a
broken focus, starts its TUI, sees `Input is not a terminal (fd=0)`, prints the
welcome banner + "Shutting down…", exits non-zero.

**Log signature:**
```
=== ROUND #1 [CREW] START ===
  worker 1 [crew/r1-w1] focus: Q1: ...
=== ROUND #4 [CREW] END ===      # 26 seconds later
```
Rounds "complete" in seconds. `git branch | grep crew` shows r1..r4 branches
all un-merged. No new commits except ones from a prior sequential run.

**Detect:** log full of hermes TUI banner + "Input is not a terminal".
**Fix:** Python `str.replace` templating, never sed with `|` when values contain `|`.

## 2. no-op merge marked [DONE] with stale hash

`git merge --no-ff <branch>` on a branch identical to HEAD exits 0 ("Already up
to date") WITHOUT creating a commit. Naive `MRC==0 → merged, mark [DONE]` then
marks the item done using the PREVIOUS HEAD's short hash — work never landed.

**Log signature:** `marked [DONE] Q1 in verdict (merged de3f2e9)` where de3f2e9
is an older merge, and `git log` shows no new merge commit for that round.

**Fix:** snapshot `head_before=$(git rev-parse HEAD)` before merge; success only
when `MRC==0 && head_after != head_before`. Else log no-op and keep [OPEN].

## 3. Judge self-termination (the loop killed itself)

After ~30 judge cycles and 16 consecutive 5D verdicts, a judge wrote:
```
[OPEN] Q1: formal loop shutdown — stop the systemd service, archive judge-verdict.md...
```
A worker executed it: `systemctl --user stop mazemaker-rework-loop.service`.
Service died; `systemctl --user is-active` = inactive (dead).

**Why it happens:** judges optimise "the loop has achieved its purpose" →
audit-only queues → "exhaustion" → shutdown. This violates the operator's
"loop. no end. perpetualmobile."

**Defense (all three layers, see SKILL.md):**
1. supervisor veto on shutdown tokens when collecting [OPEN] items
2. judge prompt: "THE LOOP NEVER ENDS" + "if exhausted find NEW work"
3. worker prompt: never touch systemd; write `.item-done` with reason instead

## 4. Empty verdict → seed-queue re-grind

After items all become [DONE] (or are vetoed), falling back to the seed queue
re-runs gaps that are long since done (FILM, INTRO, GLYPH...), producing
`.item-done` no-ops forever.

**Fix:** if verdict file exists but has 0 [OPEN] items → force a JUDGE round
immediately (mint fresh work), not seed queue. Seed queue only when no verdict
file exists at all.

## 5. Browser DDoS risk in multi-worker loops

Queue item "HEADLESS 5D PROOF — open index.html in Chrome, screenshot..." invites
each worker to spawn its own headless Chrome. Over days that accumulates.
Operator order: "wo auch immer fucking chrome headless startet: FFS STOP IT!
WENN, EINE EINZIGE INSTANZ... DIESEN PROZESS DANN AUCH TÖTET AM ENDE!"

**Fix:** no direct chrome spawns anywhere; Hermes browser tools only (single
managed instance); supervisor reaps chrome-family processes under its own tree
after each round:
```bash
all=$( pstree -p "$root_pid" | grep -oE '\(([0-9]+)\)' | tr -d '()' )
for pid in $all; do
  case "$(ps -o comm= -p $pid)" in chrome|chromium|google-chrome*|chrome_crashpad|chrome-sandbox) kill -9 $pid;; esac
done
```
Note: `chrome_crashpad_handler` from VSCode/Discord (Electron) is NOT headless
Chrome and must not be killed.

## 6. Leftover conflicted branches after restarts

Repeated restarts with a running supervisor leave `crew/*` branches (empty or
conflicted) that `startup_cleanup` tries to merge. Audit before dropping:
`git diff --stat visual/cockpit-demo..crew/<b>` — old branches often diff huge
(deletions) because their base is far behind HEAD while their *actual* work is
already merged. Verify with `grep` that the feature exists in main, then
`git worktree remove --force` + `git branch -D`.
