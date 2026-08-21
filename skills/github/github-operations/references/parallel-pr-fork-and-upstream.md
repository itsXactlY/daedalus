# Parallel PR — Ship to Fork AND Upstream

When the fork has diverged 1,000+ commits from upstream (common after
weeks of local-only work), the **same bug almost always exists in
both code paths** because the same logical code got restructured into
two different file trees. Shipping a fix only to the fork leaves the
upstream code path with the bug.

## Symptoms that you need a parallel PR

- `git log --oneline main..origin/main | wc -l` > 1,000 → fork is far
  behind upstream, restructuring is likely
- `git diff fork/main origin/main --stat` shows tens of thousands of
  lines → divergent code paths
- The same logical code lives under different file paths on each side
  (real example: `gateway/platforms/discord.py` on the fork vs
  `plugins/platforms/discord/adapter.py` on upstream — both target
  the same `_run_post_connect_initialization` logic but the fork
  restructured the plugins folder into a flat `gateway/platforms/`
  layout)

## The minimal-viable parallel PR workflow

1. **Identify the fork's file path** (where you just shipped the fix).
2. **Find the upstream equivalent** — usually the file with the same
   class name or the closest semantic match.

   ```bash
   # If the fork's file is at gateway/platforms/discord.py and you
   # can't find it on origin/main, search by class name:
   git grep "class DiscordAdapter" origin/main -- "*.py"
   ```

3. **Base a new branch on upstream**, NOT on the fork's main:

   ```bash
   git checkout -b fix/same-bug-name origin/main
   ```

4. **Apply the same logical fix** to the upstream file. The patch
   will look completely different — different imports, different
   call sites, different surrounding code — but the SEMANTIC change
   is the same. Don't try to literal-cherry-pick the commit; the
   files have diverged too much. Re-author the fix against the
   upstream code shape.

5. **Add tests in the upstream test file** (likely
   `tests/gateway/test_discord_connect.py` or equivalent). Match
   the existing test patterns in that file — they may differ
   significantly from the fork's test patterns.

6. **Run the test suite on the upstream branch** to confirm nothing
   regressed:

   ```bash
   bash scripts/run_tests.sh tests/gateway/test_discord_connect.py -- --tb=short
   bash scripts/run_tests.sh tests/gateway/
   ```

7. **Push the branch to YOUR fork** (you don't have push access to
   upstream directly), then open the PR against upstream:

   ```bash
   git push -u fork fix/same-bug-name
   gh pr create --repo UPSTREAM_OWNER/UPSTREAM_REPO --base main \
     --head YOUR_FORK:fix/same-bug-name --title "..." --body "..."
   ```

8. **Link both PRs in each other's body** so reviewers can see they're
   parallel work. A "Companion PR" section in each is enough.

## Why this matters

The user WILL ask "is the fix live upstream?" if the same bug exists
there. The first session that produced this lesson got it wrong the
first time — shipped a fork fix, got the call-and-response right when
the user pushed back with:

> "compare against nous upstream too, and get a fix live if same 1:1
> crap exist there still!"

Save the round trip by checking the upstream code path proactively as
part of the "fix is complete" definition.

## Cherry-pick across fork ↔ upstream: pre-flight + failure modes

The "minimal-viable parallel PR" recipe above says "apply the same
logical fix" and "don't try to literal-cherry-pick." But sometimes the
user already has the fix committed on local `main` and just wants
those exact commits ported — for a code review gate, a fast smoke
test against the upstream code shape, or a rebase test. In that case
literal cherry-pick is what you do, but it has failure modes the
recipe doesn't cover.

### Pre-flight: verify the file exists on the target branch

Before `git cherry-pick <sha>`, check that every file the commit
touches still exists on the target. A diff against a deleted file is
a `modify/delete` conflict — git will refuse the cherry-pick and
leave the working tree in a half-applied state. The check is
one-liner per file:

```bash
# Does the file the commit touches still exist on the target branch?
git ls-tree --name-only <target> <path/to/file>
# Empty output → file does NOT exist → cherry-pick will conflict
```

If the file doesn't exist on the target, the right move is to skip
the cherry-pick for that commit (`git cherry-pick --skip` after
abort) and re-author the change against the new file shape — or
decide with the user that the commit is a no-op on this target and
shouldn't be ported at all. **Do not** `--strategy=theirs` past a
delete without confirming the user wants the change dropped.

### Modify/delete conflict resolution

When `git cherry-pick` dies with `KONFLIKT (ändern/löschen): <file>
gelöscht in HEAD und geändert in <sha>`:

1. **Abort the cherry-pick** to get a clean working tree:
   ```bash
   git cherry-pick --abort
   ```
2. **Decide per-commit** whether the change is still meaningful on
   the new target:
   - **Comment-only change** (e.g. `docs:` commits that just
     reference URLs / add monkeypatch disclaimers): almost always a
     no-op on the new target because the file no longer exists.
     Skip.
   - **Lockfile / config tweak** (e.g. `chore(deps):` on
     `package-lock.json`): usually applies cleanly. Re-cherry-pick
     it.
   - **Feature / behavior change** (e.g. capture return value and
     inject as system note): the underlying code was probably
     restructured into a different file. Re-author against the
     new shape, don't cherry-pick.
3. **Report the decision back to the user with the actual file
   state on the target** — don't silently pick one branch. The
   user knows whether the feature is needed there.

A real session hit this exact failure on the
`agent/conversation_compression.py` → `run_agent.py:6778` move
between `fork/main` and upstream. The functional code on
`run_agent.py:6778` did NOT have the return-value capture the
commit annotated — the whole feature was never ported upstream.
Cherry-picking the comment-only commit would have produced a PR
that described code that didn't exist.

### The "PREPARE but don't open" review-gate pattern

When the user says `PREPARE(!) open a PR. dont open the PR. leave
it for review to me`, they want everything up to but not including
the `gh pr create` call. Concrete shape:

1. Create the branch (off the right base — see the divergence
   pitfall).
2. Cherry-pick / commit / rebase as needed.
3. Push the branch to the target remote.
4. **Write the PR title and body**, but DO NOT run `gh pr create`.
5. **Run the test suite on the branch** to confirm the diff is
   real and green.
6. **Present the following in chat, in this exact shape**:
   - Branch name
   - Base / head SHAs (local `HEAD` + remote target tip)
   - `git diff --stat <target>...HEAD` output
   - Test summary
   - The proposed PR title
   - The proposed PR body (in a fenced block, ready to copy)
   - The `gh pr create` command line to run verbatim when approved

Why this matters: `gh pr create` opens a public PR with a
description, links, and review assignments. Once opened, the
diff is live and reviewable by anyone with the link. The user
wants a final eyeball on the body wording and the diff scope
before that happens. The cost of NOT preparing everything is the
user has to do `git diff` themselves to know what they're
approving — defeats the purpose of the review gate.

**Anti-pattern**: opening the PR because the work feels "done" and
sending "here it is, close it if you don't like it." That's not a
review gate, that's a fait accompli. The user is going to close
the bad PR and yell at you.

## Anti-pattern: doing it after the user asks

Shipping the fork fix first and waiting for the user to call out the
gap is fine for the first time, but once you've been burned by it,
always check upstream proactively. The minimum check is:

```bash
# After fixing the fork:
git fetch origin main
git log --oneline main..origin/main | wc -l  # if > 1000, you owe a parallel PR
git diff --stat fork/main origin/main -- <relevant-path-glob>
```

If the diff shows the same file restructuring in two different places,
you owe a parallel PR. Don't wait to be told.

## Related

- Skill: `github-operations` §3 (umbrella, contains the inline pitfall)
- Skill reference: `references/fork-divergence-pitfall.md` (the FIRST
  part of this lesson — preventing the 1.15M-line PR by basing on
  `fork/main`)
- Memory: `fact:discord-cap-detect-prs-live` (id 360933) — the live
  example of two parallel PRs (itsXactlY/hermes-agent#5 +
  NousResearch/hermes-agent#48087)
- Memory: `fact:local-main-state-resolved` (id 360946) — the
  cherry-pick modify/delete conflict on `agent/conversation_compression.py`
  → `run_agent.py:6778` and the "PREPARE but don't open" review-gate
  pattern that was the source of this section.
