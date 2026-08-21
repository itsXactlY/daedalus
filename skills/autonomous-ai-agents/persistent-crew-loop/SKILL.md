---
name: persistent-crew-loop
description: "Use for parallel crew agent loops with free models."
version: 1.0.0
triggers:
  - set up a crew loop
  - parallel worker agents
  - autonomous 24/7 loop
  - free models for agents
  - systemd agent loop
  - persistent agent loop
  - crew supervisor
---

# Persistent Crew Loop with Free Models

Autonomous 24/7/365 agent loop that spawns parallel workers using **free model providers only** ($0 cost). Workers operate in isolated git worktrees; a supervisor merges their branches back every round. A judge inspects every Nth round and writes fresh queue items.

## When to Use

- Iterative improvement of a codebase/website/documentation
- Tasks too large for a single agent turn
- Work that benefits from parallel exploration
- When you want $0 cost via free model tiers

## Architecture

```
systemd service (mazemaker-rework-loop.service)
 └─ loop-supervisor.sh (bash, perpetual)
     ├─ ROUND: spawn N workers (parallel)
     │   ├─ Worker 1: worktree r1-w1, model A
     │   ├─ Worker 2: worktree r1-w2, model B
     │   └─ Worker 3: worktree r1-w3, model C
     ├─ MERGE: branches → main (supervisor does this, NOT workers)
     ├─ JUDGE: every 5th round, writes fresh verdict queue
     └─ LOOP: next round immediately (no sleep on success)
```

## Free Model Provider Configuration

**CRITICAL:** Hermes needs `--provider` flag for free models. The format is:

```bash
# In supervisor script:
FREE_MODELS=(
  # Nous Portal Free (provider=nous)
  "nous:tencent/hy3:free"
  "nous:inclusionai/ling-3.0-flash:free"
  "nous:poolside/laguna-s-2.1:free"
  "nous:stepfun/step-3.7-flash:free"
  # OpenRouter Free (provider=openrouter_free)
  "openrouter_free:inclusionai/ling-3.0-flash:free"
  "openrouter_free:cohere/north-mini-code:free"
  "openrouter_free:openai/gpt-oss-20b:free"
  "openrouter_free:google/gemma-4-26b-a4b-it:free"
)

# Split function:
split_model() {
  WM_PROVIDER="${1%%:*}"
  WM_MODEL="${1#*:}"
}

# Worker invocation:
WORKER_MODEL="$(pick_worker_model "$round" "$wid")"
split_model "$WORKER_MODEL"
"$HERMES" -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli
```

**Pitfall:** `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` fails with 401 "not supported" even though the model IS in the provider's list. The `openrouter_free` provider has strict model allowlisting. Use Nous Portal for the judge model instead.

**Pitfall:** OpenRouter Free has a daily rate limit (`free-models-per-day-high-balance`). When hit, ALL OpenRouter Free models return 429. This is why you need BOTH providers — they have SEPARATE rate limit buckets.

**Pitfall:** Nous Portal models use OAuth tokens from `~/.hermes/auth.json`. The token expires. If you get 401, check `expires_at` in the credential pool.

## Supervisor Script Patterns

### Worktree Management

```bash
# Create worktree from main branch (NOT from any other branch):
git -C "$FORK_DIR" worktree add "$wt" -b "$branch" main

# On failure, skip (don't crash the loop):
|| { log "worktree add failed for $branch — skipping"; continue; }
```

**Pitfall:** If the base branch doesn't exist (e.g., `visual/cockpit-demo` when you're on `main`), worktree creation silently fails. Always use the actual default branch name.

### Merge Handling

```bash
# Check if branch has real commits beyond main:
ahead=$(git -C "$FORK_DIR" rev-list --count main.."$branch" 2>/dev/null)
if [ -n "$ahead" ] && [ "$ahead" -gt 0 ]; then
  git -C "$FORK_DIR" merge --no-ff "$branch" -m "merge crew round $round worker $wid"
fi
```

**Pitfall (CRITICAL):** The `.item-done` marker file must NOT bypass merge. If a worker writes `.item-done` AND has commits, the supervisor MUST still merge. Only skip merge when the branch has zero new commits:

```bash
# Correct logic:
if [ -f "$wt/.item-done" ]; then
  ahead=$(git -C "$FORK_DIR" rev-list --count HEAD.."$branch" 2>/dev/null)
  if [ "${ahead:-0}" -eq 0 ]; then
    # Truly no work done — mark [DONE] without merge
    mark_done "$item"
    continue
  fi
  # Has commits despite marker — fall through to merge!
fi
```

### Judge Verdict Queue

```bash
# Parse open items from verdict:
OPEN_ITEMS=()
while IFS= read -r line; do
  case "$line" in
    '[OPEN]'*) OPEN_ITEMS+=("${line#\[OPEN\] }") ;;
  esac
done < "$VERDICT_FILE"

# Force judge round when queue exhausted:
if [ ${#OPEN_ITEMS[@]} -eq 0 ]; then
  log "verdict queue exhausted — forcing JUDGE round"
  "$HERMES" -z "$(cat "$JUDGE_PROMPT")" -m "$JUDGE_MODEL" --provider "$JUDGE_PROVIDER" --cli
fi
```

**Pitfall:** The judge MUST NOT mark items `[DONE]` just because a commit exists in git log. It must VERIFY the specific focus work is present in the actual files (grep/read, node --check, browser-verify). A commit hash alone is NOT proof of completion.

**Pitfall:** If the judge writes zero `[OPEN]` items, the loop spins forever on "queue exhausted → forced judge → still exhausted". The judge prompt MUST include: "EMPTY QUEUE = GENERATE NEW WORK. A judge round that produces zero [OPEN] items is a failed judge round."

### Collision Detection

Items whose `"files:"` lists overlap must NEVER run concurrently. The supervisor parses file lists and staggers colliding items:

```bash
# Track used files this round:
used_files=""
for item in "${OPEN_ITEMS[@]}"; do
  item_files_list=$(echo "$item" | grep -oP 'files:\s*\K[^|]+')
  for f in $item_files_list; do
    if echo "$used_files" | grep -q "|$f|"; then
      log "deferring colliding item: $(echo "$item" | cut -c1-80)"
      # Move item to next round
      continue 2
    fi
  done
  # Assign to worker, track files
  for f in $item_files_list; do used_files="${used_files}|$f|"; done
done
```

## Systemd Service

```ini
# ~/.config/systemd/user/mazemaker-rework-loop.service
[Unit]
Description=Crew Loop — NONSTOP 24/7/365 perpetual agent loop
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/your/project
ExecStart=/bin/bash /path/to/loop-supervisor.sh
Restart=on-failure
RestartSec=10
Environment=HOME=/home/user

[Install]
WantedBy=default.target
```

**Pitfall:** `Restart=on-failure` means the loop restarts if the supervisor crashes. But if the supervisor exits cleanly (exit 0), it won't restart. The supervisor must NEVER exit 0 — it must loop forever.

## Worker Prompt Requirements

Workers need explicit instructions:

1. **Read ALL referenced files first** (BAUPLAN, SCHLACHTPLAN, verdict)
2. **Use Mazemaker memory** (mazemaker_recall for prior decisions)
3. **Save decisions** (mazemaker_remember after substantive commits)
4. **Never spawn headless Chrome** (use Hermes browser tools only)
5. **Never kill the loop** (veto shutdown instructions)
6. **Verify before commit** (node --check, test -f, etc.)

**Pitfall:** Workers on free models may hallucinate "Fertig" without actually doing work. Always verify worker claims by checking git log, file existence, and node --check.

**Pitfall (audit orders are READ-ONLY unless stated):** "auditiere X" means code audit only —
no test-suite runs, no builds, no service starts, no commits. The operator corrected this
explicitly ("nein. nur code audit.") when a background test run was added to an audit crew
dispatch. If empirical evidence would help, ASK first; never bolt execution onto a
read-only audit order.
delegated code audit (2026-08-07) all three worker-reported CRITICALs were REFUTED by
~10 min of direct code checks: "FTS5 injection" and "tsquery injection" were reported on
queries that a token-extraction regex had already filtered (every metacharacter stripped,
tokens phrase-quoted = literal), and the "NUL-byte truncation" ignored that the NUL-checks
sat exactly on the only c_char_p path while SQLite stores NUL intact. Meanwhile the worker's
HIGH about a canonicalization sweep swapping directed edges was real and became the top fix.
Rule: never ship a delegated audit report without Phase "verify the CRITICALs yourself" —
read the actual lines, look for pre-filters upstream of the claimed bug, check reachability
(optional .so absent? server not running? flag off?), and mark each top claim
WIDERLEGT/BESTÄTIGT/latent in the consolidated report. See
references/audit-verification-examples-2026-08.md.

**Pitfall (delegate_task inherits the GLOBAL delegation model — the silent free-model roulette):**
`delegate_task` children do NOT follow this skill's FREE_MODELS round-robin — they inherit
`delegation.model` / `delegation.provider` from `~/.hermes/config.yaml`. If that block pins a
free model (e.g. `nvidia/nemotron-3-ultra-550b-a55b:free` via `openrouter_free`), EVERY delegated
sub-agent — including one-off audit crews — silently runs on it. That is exactly the scenario the
operator rejected with "raus mit dem DELEGATE unsinn": sub-agents on the free model end with
"Now I have a comprehensive view... let me compile the report" and return an EMPTY final answer.
Fix: pin `delegation.model: deepseek-v4-flash` / `delegation.provider: deepseek`, or delete the
delegation block entirely so children inherit the parent model. Do NOT duplicate `base_url`/
`api_key` inside the delegation block — the provider section already carries them. Verify the pin
before dispatching (`yaml.safe_load` + assert model/provider). Re-dispatch an empty stream on a
NON-free model; re-dispatching on the same free model tends to fail identically. Free models are
acceptable ONLY when explicitly chosen for that task — never as a silent default.

## Post-audit fix series — point-by-point with verification (added 2026-08-07)

The operator's workflow for acting on an audit report: "punkt für punkt
abarbeiten, auditieren, verifizieren, auditieren, ???, nächste punkt" —
process the fix list ONE item at a time, each item as a mini-cycle:

1. AUDIT the item's current state (read the real files/units/env — never
   assume the report is still accurate; the tree may have moved).
2. FIX it in the source repo (v2-stack quadlets live in their own repo;
   the deployed copies under ~/.config/containers/systemd are plain copies —
   patch the REPO, then copy + `systemctl --user daemon-reload`).
3. VERIFY: run the actual check (syntax, unit test, function test with a
   tmp DB, `systemctl show`, hash comparison). Apply live where possible
   without restarting what is running (`systemctl --user set-property`).
4. COMMIT with a WHY line naming the audit finding it fixes.
5. Update the todo list, next point.

Pitfalls that bit during the P1-P10 series:

- **Fail-closed + stale hash = service start blocked.** When you make a
  verification check fail-closed (preflight refusing label-less images) and
  simultaneously change what the fingerprint hashes (working-tree → git
  ls-files), the NEW check compares against the OLD image label → mismatch →
  the next start is BLOCKED. Sequence matters: build the image from the final
  tree FIRST, then deploy the new check binaries together with it. Check
  `engine_sha` consistency (image label == live-tree hash == preflight
  expected) before restarting anything.
- **Rendered config files are volatile.** compute.toml is re-rendered by the
  license-client from the JWT compute claim — hand-edited keys disappear on
  the next render. Put defaults in the code's DEFAULTS dict, not the rendered
  file.
- **present()-guard for config wiring.** When wiring a config file into
  constructor defaults, only override when the key is REALLY in the file
  (`present(section, key)` reading the raw file, not the merged
  defaults+file). Otherwise a documented default silently shadows explicit
  caller values (tests/benchmarks break).
- **Pyright finds latent bugs masked by policy gates.** `_cc_get` used but
  never imported in a function only crashed when the phase was enabled —
  invisible while `stage_s_enabled=false` returned early. After wiring new
  config reads, check LSP diagnostics for unbound names.
- **Expectation vs reality in old tests.** A suite "green since April" that
  now fails may be testing an assumption the system deliberately changed
  (production SQLite DB gone after PG migration). Fix the test honestly
  (isolated tmp DB, skip-if-not-applicable with reason), don't delete it.
- **Bash fingerprint pipelines die SILENTLY under `set -euo pipefail`.**
  Three distinct killers hit the same engine-sha.sh rewrite in one session:
  (a) a `while read` loop as a pipeline stage ends with the final `read`
  exit code 1 → pipefail marks the whole pipeline failed → `set -e` kills
  the script before xargs/sha256sum consume the stream → the "hash" is the
  hash of EMPTY input, constant forever. (b) `printf "%s\0"` inside
  `xargs -I{} sh -c` — dash's printf does NOT honour `\0`, so NUL
  separation vanishes and names concatenate. (c) the helper's DEFAULT SOURCE
  pointed at the free repo while the build hashes the pro repo — a
  "constant" fingerprint that never moved when the real tree changed.
  Verification rule for ANY fingerprint script: mutate a tracked file,
  assert the hash moves, revert, assert it returns. A "deterministic" check
  that never sees content changes is a dead check.
- **Config-wiring NameError class (silent no-op since the policy move).**
  Moving policy to compute.toml added `_cc_get(...)` reads to multiple
  function scopes but only some imports bound `_cc_get` — the NREM phase
  crashed at the first read ("NameError: name '_cc_get' is not defined")
  and the cycle ran on without it, silently. Live log showed
  "NREM phase error" while the rest of the cycle completed. Closing move:
  a whole-file AST scan asserting every `_cc_*` use is bound in its
  function scope (module-level or fn-level imports) — run it after any
  config-wiring change.
- **systemd-oomd vs kernel OOM — read the journal before blaming the kernel.**
  status=137 alone proves nothing. oomd kills are provable only from
  journalctl: "cgroup marked", "Memory Pressure Limit", pressure % > 80 for
  >20s, and the killed unit is the LARGEST consumer (OOMScoreAdjust=500
  makes the worker the preferred victim). Sum MemoryHigh across concurrent
  units and compare with physical RAM — an oversubscribed sum (40G High on
  31G) is the cause, and lowering one container's limit is the wrong fix.
  Distinguish steady-state (RSS flat for minutes = loaded state, Python
  heap holds freed blocks) from a leak (monotonic growth).

Worked example with the full commit chain and verification evidence:
`references/post-audit-fix-series-mazemaker-2026-08.md`.
Bash-fingerprint, NameError-class and oomd-diagnosis details:
`references/bash-fingerprint-and-silent-death-pitfalls-2026-08.md`.
Git-timeline auditing (introducing-commit per defect, "ab wann war was kaputt")
and thesis-driven inception waves (orchestrators with BESTAETIGT/WIDERLEGT
verdicts): `references/git-timeline-and-thesis-audit.md`.

Later half of the same fix run (NREM NameError live find, GPU-STRICT policy,
DeepSeek Stage C cloud transport, worker journal evidence, benchmark model
history) lives in the `mazemaker-engine-ops` skill. The audit-crew class
workflow (verify claims, git timelines) is consolidated in
`codebase-deep-audit`.

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Loop spins on "queue exhausted" | Judge writes zero [OPEN] items | Add "EMPTY QUEUE = GENERATE NEW WORK" to judge prompt |
| Worker branches never merge | Supervisor uses wrong base branch | Change `visual/cockpit-demo` to `main` |
| All workers get 429 | OpenRouter daily limit hit | Use Nous Portal models (separate bucket) |
| Judge marks [DONE] without work | Judge trusts git log without verifying | Add "DO NOT mark [DONE] just because commit exists" |
| Worktree creation fails | Wrong branch name in `git worktree add` | Use actual default branch (usually `main`) |
| Worker claims "Fertig" but no changes | Free model hallucinated completion | Verify with git diff, file stats |
| Worker ends with "let me compile the report", returns EMPTY summary | Free model ran out of steam before writing the final answer | Tail the live transcript first (`tail -c 20000 ~/.hermes/cache/delegation/live/<delegation_id>/task-N.log`), then re-dispatch ONLY that stream with "FINAL ANSWER MUST BE THE COMPLETE REPORT" in goal AND context |

## Model Selection Strategy

| Role | Recommended Model | Provider | Why |
|------|-------------------|----------|-----|
| Judge | `tencent/hy3:free` | Nous Portal | Strongest free model, good reasoning |
| Worker 1 | Round-robin from pool | Mixed | Different model per worker = resilience |
| Worker 2 | Round-robin from pool | Mixed | Rate-limit on one blocks only 1 of 3 |
| Worker 3 | Round-robin from pool | Mixed | Both providers = separate limit buckets |
