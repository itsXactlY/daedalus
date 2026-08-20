#!/usr/bin/env python3
"""Checkpoint maintenance: enforce max_snapshots per shadow repo.

Runs the real prune from checkpoint_manager._prune over every checkpoint
repo under ~/.daedalus/checkpoints — keeping only the newest max_snapshots
commits per directory and freeing the disk of dropped objects.

Safe to run anytime; no-op for repos already under the limit.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkpoint_manager import CheckpointManager

MAX_SNAPSHOTS = 50


def count(repo: Path) -> int:
    r = subprocess.run(
        ["git", "--git-dir", str(repo), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return -1


def main() -> int:
    mgr = CheckpointManager(enabled=True, max_snapshots=MAX_SNAPSHOTS)
    total_before = 0
    total_after = 0
    for repo in sorted(Path.home().joinpath(".daedalus/checkpoints").glob("*/")):
        wd_file = repo / "DAEDALUS_WORKDIR"
        wd = wd_file.read_text().strip() if wd_file.exists() else ""
        before = count(repo)
        total_before += max(before, 0)
        if not wd or before < 0:
            print(f"{repo.name}: SKIP (no workdir or invalid repo)")
            continue
        mgr._prune(repo, wd)
        after = count(repo)
        total_after += max(after, 0)
        flag = "" if after <= MAX_SNAPSHOTS else "  <-- STILL OVER LIMIT"
        print(f"{repo.name}: {before} -> {after} commits  ({wd}){flag}")
    print(f"\nTotal commits: {total_before} -> {total_after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
