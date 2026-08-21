# Fork Divergence Pitfall — When a PR Diff Becomes the Entire Fork History

## Symptom

A PR you've just opened shows the entire fork's history as the diff. Real
example from a session on `itsXactlY/hermes-agent`:

```
Lines changed: 1,151,913 additions & 98,661 deletions
```

The PR header showed `6482 commits into main from <branch>` because GitHub
compared the new branch's tip against the **fork's** main, not the user's
local main. The branch's base (local main) was 6481 commits ahead of
fork/main, and the diff captured all of it.

User reaction: `delete this PR! then, branch -> fix -> PR! not with the
_WHOLE DIPSHIT MESS_ attached!`

## Root Cause

A forked repo typically has two remotes:

- `origin` → upstream (`https://github.com/NousResearch/hermes-agent.git`)
- `fork` → your own fork (`git@github.com:itsXactlY/hermes-agent.git`)

The `gh pr create` command targets `fork` (your own repo), so the diff
is computed against `fork/main` — NOT your local `main`. The standard
"branch from main" pattern (`git checkout main && git checkout -b fix/x`)
bakes in whatever state your LOCAL main is in, which can be wildly
different from `fork/main` if:

- The user has been pulling upstream into local main but hasn't pushed
  to fork
- The fork was created at an old commit and the local repo has been
  rebased / fast-forwarded since
- The user did `git pull upstream` (renamed `origin`) into local main
  but their fork was last updated weeks ago

The local repo happily shows `git status` as "clean" — there's no
warning that the branch you're about to push is rooted in a totally
different state from the remote that will receive it.

## Diagnosis

If you already pushed the bad branch and need to confirm before nuking
it, run this on the local checkout:

```bash
# Local main tip
git rev-parse main

# The remote you'll actually PR against
git rev-parse fork/main

# Commits in fork not in local (fork is AHEAD of local)
git log --oneline main..fork/main | wc -l

# Commits in local not in fork (local is AHEAD of fork — typical case)
git log --oneline fork/main..main | wc -l
```

If either number is in the thousands, the PR diff will be in the
hundreds of thousands of lines.

## Recovery

1. **Close the bad PR + delete the remote branch:**

   ```bash
   gh pr close <PR_NUMBER> --repo OWNER/REPO --delete-branch
   ```

2. **If cherry-pick conflicts happen** (because the bad branch was rooted
   in stale local main, not `fork/main`), abort and start fresh on the
   correct base:

   ```bash
   git cherry-pick --abort
   git checkout main
   git branch -D fix/short-name
   ```

3. **Base the new branch on the remote ref:**

   ```bash
   git checkout -b fix/short-name fork/main
   ```

4. **Reapply the fix from scratch against the actual current state.**
   Cherry-picking from the old commit may work for small additive
   changes but will conflict for any file that diverged. The adapter
   may have been restructured entirely (it was in the worked example:
   `plugins/platforms/discord/adapter.py` → `gateway/platforms/discord.py`).

5. **Verify the diff stat BEFORE pushing:**

   ```bash
   git diff --stat fork/main...HEAD
   ```

   A real bugfix is typically <500 lines / <10 files. Anything more is
   almost certainly "the whole mess" again.

6. **Push the clean branch + open a clean PR:**

   ```bash
   git push -u fork fix/short-name
   gh pr create --repo OWNER/REPO --base main --head fix/short-name \
     --title "fix: short description" --body "..."
   ```

## Prevention (one-liner per step)

Embed this in any "create a PR" workflow for a forked repo:

```bash
# ALWAYS start with this. If you can't run it, you don't have a remote
# to PR against and you shouldn't be making a branch.
git fetch --all

# ALWAYS base branches on the remote ref, never on local main.
git checkout -b fix/short-name fork/main

# ALWAYS diff against the remote before pushing.
git diff --stat fork/main...HEAD  # must be small

# THEN push + open PR.
git push -u fork fix/short-name
gh pr create --repo OWNER/REPO --base main --head fix/short-name ...
```

## When Local Main IS the Right Base

The above only applies when the PR target is a fork whose main is
**behind** the local main. If the operator has been keeping fork/main
in sync (e.g. via `git push fork main` after every `git pull upstream
main`), then `git checkout main` is fine and the diff stat against
`fork/main...HEAD` will be identical to `main...HEAD`.

Verify sync state quickly:

```bash
git rev-parse main
git rev-parse fork/main
# If these are equal, the standard "branch from main" recipe is safe.
```

## Stale-Local-Main On A Non-Fork Repo

The same pitfall exists for a non-fork repo if the operator has been
working on local main and never pushed — the branch tip is local-only,
and any PR the user makes will show local-but-unpushed history as the
diff. Same fix: `git push origin main` first, OR base the branch on
`origin/main` explicitly.

## Related

- Skill: `github-operations` §3 (this file's umbrella)
- Memory: `bug:discord-30032-gateway-kill` (id 360920) — the original
  session that produced the bad PR
- Memory: `fact:discord-cap-handling-fork-state` (id 360925) — recorded
  the lesson after recovery
