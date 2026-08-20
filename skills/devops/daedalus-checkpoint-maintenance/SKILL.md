---
name: daedalus-checkpoint-maintenance
description: Maintain the deployed checkpoint system (~/.daedalus/checkpoints shadow-git repos) — real autoprune, /tmp skip, storage hygiene
version: 1.0.0
tags: [daedalus, checkpoints, snapshots, git, maintenance]
created: 2026-08-10
---

# Daedalus Checkpoint Maintenance

The DEPLOYED snapshot system is `~/.daedalus/tools/checkpoint_manager.py` — transparent
shadow-git repos. One repo per working dir: `~/.daedalus/checkpoints/{sha256(path)[:16]}/`
with `DAEDALUS_WORKDIR` pointing at the real dir. It snapshots before write_file/patch,
once per turn, capped by `checkpoints.max_snapshots` (default 50).

The old `~/.daedalus/snapshots/` content-addressed design (see runtime-snapshot-engine
skill) is NOT deployed. Storage lives ONLY in `~/.daedalus/checkpoints/` — never anywhere
else. Verify with: `find /home/alca /tmp -maxdepth 4 -name DAEDALUS_WORKDIR` → empty
outside `~/.daedalus/checkpoints`.

## Autoprune — how it works

`CheckpointManager._prune()` runs after every checkpoint and keeps the NEWEST
`max_snapshots` commits. It rebuilds the chain via `git commit-tree`
(oldest-to-newest, preserving tree + message + identity), moves the branch ref,
then `reflog expire --expire=now --all` + `git gc --prune=now` to free disk.

CRITICAL — do NOT "simplify" this back to moving the branch ref. Moving a ref keeps
the ref's ANCESTORS (oldest commits) and orphans the newer descendants — backwards.
`git filter-branch` also fails on dirty worktrees (projects are always dirty).
commit-tree is the only safe option: zero worktree/index interaction.

## Maintenance script

    python3 ~/.daedalus/scripts/prune-checkpoints.py

Enforces the cap across every repo now (no-op for repos under the limit). Run after
big edits, or when `du -sh ~/.daedalus/checkpoints/` looks fat.

## /tmp junk protection

`ensure_checkpoint` skips `/` , `$HOME`, and anything under `/tmp`. The running
process only picks this up after restart — a live session writing to /tmp can still
create a `/tmp` shadow repo (801MB case, Aug 2026). If that happens: delete the repo
matching `sha256(b'/tmp')[:16]` and DON'T write files under /tmp in-session.

## Pitfalls

- Never delete all checkpoints — they're the only rollback for /rollback.
- `ls ~/.daedalus/skills` errors with eza "--icons" nonsense; use `\ls` or find.
- `python3 -c` with json.dumps in terminal() mangles `\n` — write scripts to files
  under ~/.daedalus (NOT /tmp — that re-triggers the /tmp checkpoint bug).
