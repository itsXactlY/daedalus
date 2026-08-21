"""
Checkpoint Manager — Transparent filesystem snapshots via shadow git repos.

Creates automatic snapshots of working directories before file-mutating
operations (write_file, patch), triggered once per conversation turn.
Provides rollback to any previous checkpoint.

This is NOT a tool — the LLM never sees it.  It's transparent infrastructure
controlled by the ``checkpoints`` config flag or ``--checkpoints`` CLI flag.

Architecture:
    ~/.daedalus/checkpoints/{sha256(abs_dir)[:16]}/   — shadow git repo
        HEAD, refs/, objects/                        — standard git internals
        DAEDALUS_WORKDIR                               — original dir path
        info/exclude                                 — default excludes

The shadow repo uses GIT_DIR + GIT_WORK_TREE so no git state leaks
into the user's project directory.
"""

import hashlib
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from daedalus_constants import get_daedalus_home
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHECKPOINT_BASE = get_daedalus_home() / "checkpoints"

DEFAULT_EXCLUDES = [
    "node_modules/",
    "dist/",
    "build/",
    ".env",
    ".env.*",
    ".env.local",
    ".env.*.local",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "*.log",
    ".cache/",
    ".next/",
    ".nuxt/",
    "coverage/",
    ".pytest_cache/",
    ".venv/",
    "venv/",
    ".git/",
]

# Git subprocess timeout (seconds).
_GIT_TIMEOUT: int = max(10, min(60, int(os.getenv("DAEDALUS_CHECKPOINT_TIMEOUT", "30"))))

# Max files to snapshot — skip huge directories to avoid slowdowns.
_MAX_FILES = 50_000


# ---------------------------------------------------------------------------
# Shadow repo helpers
# ---------------------------------------------------------------------------

def _shadow_repo_path(working_dir: str) -> Path:
    """Deterministic shadow repo path: sha256(abs_path)[:16]."""
    abs_path = str(Path(working_dir).resolve())
    dir_hash = hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    return CHECKPOINT_BASE / dir_hash


def _git_env(shadow_repo: Path, working_dir: str) -> dict:
    """Build env dict that redirects git to the shadow repo."""
    env = os.environ.copy()
    env["GIT_DIR"] = str(shadow_repo)
    env["GIT_WORK_TREE"] = str(Path(working_dir).resolve())
    env.pop("GIT_INDEX_FILE", None)
    env.pop("GIT_NAMESPACE", None)
    env.pop("GIT_ALTERNATE_OBJECT_DIRECTORIES", None)
    return env


def _run_git(
    args: List[str],
    shadow_repo: Path,
    working_dir: str,
    timeout: int = _GIT_TIMEOUT,
    allowed_returncodes: Optional[Set[int]] = None,
    input_text: Optional[str] = None,
    env_extra: Optional[Dict[str, str]] = None,
) -> tuple:
    """Run a git command against the shadow repo.  Returns (ok, stdout, stderr).

    ``allowed_returncodes`` suppresses error logging for known/expected non-zero
    exits while preserving the normal ``ok = (returncode == 0)`` contract.
    Example: ``git diff --cached --quiet`` returns 1 when changes exist.
    ``input_text`` feeds stdin (used by ``git commit-tree -F -``).
    ``env_extra`` merges extra environment variables (identity overrides).
    """
    env = _git_env(shadow_repo, working_dir)
    if env_extra:
        env.update(env_extra)
    cmd = ["git"] + list(args)
    allowed_returncodes = allowed_returncodes or set()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(Path(working_dir).resolve()),
            input=input_text,
        )
        ok = result.returncode == 0
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if not ok and result.returncode not in allowed_returncodes:
            logger.error(
                "Git command failed: %s (rc=%d) stderr=%s",
                " ".join(cmd), result.returncode, stderr,
            )
        return ok, stdout, stderr
    except subprocess.TimeoutExpired:
        msg = f"git timed out after {timeout}s: {' '.join(cmd)}"
        logger.error(msg, exc_info=True)
        return False, "", msg
    except FileNotFoundError:
        logger.error("Git executable not found: %s", " ".join(cmd), exc_info=True)
        return False, "", "git not found"
    except Exception as exc:
        logger.error("Unexpected git error running %s: %s", " ".join(cmd), exc, exc_info=True)
        return False, "", str(exc)


def _init_shadow_repo(shadow_repo: Path, working_dir: str) -> Optional[str]:
    """Initialise shadow repo if needed.  Returns error string or None."""
    if (shadow_repo / "HEAD").exists():
        return None

    shadow_repo.mkdir(parents=True, exist_ok=True)

    ok, _, err = _run_git(["init"], shadow_repo, working_dir)
    if not ok:
        return f"Shadow repo init failed: {err}"

    _run_git(["config", "user.email", "daedalus@local"], shadow_repo, working_dir)
    _run_git(["config", "user.name", "Daedalus Checkpoint"], shadow_repo, working_dir)

    info_dir = shadow_repo / "info"
    info_dir.mkdir(exist_ok=True)
    (info_dir / "exclude").write_text(
        "\n".join(DEFAULT_EXCLUDES) + "\n", encoding="utf-8"
    )

    (shadow_repo / "DAEDALUS_WORKDIR").write_text(
        str(Path(working_dir).resolve()) + "\n", encoding="utf-8"
    )

    logger.debug("Initialised checkpoint repo at %s for %s", shadow_repo, working_dir)
    return None


def _dir_file_count(path: str) -> int:
    """Quick file count estimate (stops early if over _MAX_FILES)."""
    count = 0
    try:
        for _ in Path(path).rglob("*"):
            count += 1
            if count > _MAX_FILES:
                return count
    except (PermissionError, OSError):
        pass
    return count


# ---------------------------------------------------------------------------
# CheckpointManager
# ---------------------------------------------------------------------------

class CheckpointManager:
    """Manages automatic filesystem checkpoints.

    Designed to be owned by AIAgent.  Call ``new_turn()`` at the start of
    each conversation turn and ``ensure_checkpoint(dir, reason)`` before
    any file-mutating tool call.  The manager deduplicates so at most one
    snapshot is taken per directory per turn.

    Parameters
    ----------
    enabled : bool
        Master switch (from config / CLI flag).
    max_snapshots : int
        Keep at most this many checkpoints per directory.
    """

    def __init__(self, enabled: bool = False, max_snapshots: int = 50):
        self.enabled = enabled
        self.max_snapshots = max_snapshots
        self._checkpointed_dirs: Set[str] = set()
        self._git_available: Optional[bool] = None  # lazy probe

    # ------------------------------------------------------------------
    # Turn lifecycle
    # ------------------------------------------------------------------

    def new_turn(self) -> None:
        """Reset per-turn dedup.  Call at the start of each agent iteration."""
        self._checkpointed_dirs.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_checkpoint(self, working_dir: str, reason: str = "auto") -> bool:
        """Take a checkpoint if enabled and not already done this turn.

        Returns True if a checkpoint was taken, False otherwise.
        Never raises — all errors are silently logged.
        """
        if not self.enabled:
            return False

        # Lazy git probe
        if self._git_available is None:
            self._git_available = shutil.which("git") is not None
            if not self._git_available:
                logger.debug("Checkpoints disabled: git not found")
        if not self._git_available:
            return False

        abs_dir = str(Path(working_dir).resolve())

        # Skip root, home, /tmp, and other overly broad directories.
        # /tmp is transient by definition — snapshotting it only burns disk
        # (a shadow repo of /tmp grows to hundreds of MB and is worthless
        # as a rollback target).
        if (
            abs_dir in ("/", str(Path.home()))
            or abs_dir.startswith("/tmp")
        ):
            logger.debug("Checkpoint skipped: directory too broad (%s)", abs_dir)
            return False

        # Already checkpointed this turn?
        if abs_dir in self._checkpointed_dirs:
            return False

        self._checkpointed_dirs.add(abs_dir)

        try:
            return self._take(abs_dir, reason)
        except Exception as e:
            logger.debug("Checkpoint failed (non-fatal): %s", e)
            return False

    def list_checkpoints(self, working_dir: str) -> List[Dict]:
        """List available checkpoints for a directory.

        Returns a list of dicts with keys: hash, short_hash, timestamp, reason,
        files_changed, insertions, deletions.  Most recent first.
        """
        abs_dir = str(Path(working_dir).resolve())
        shadow = _shadow_repo_path(abs_dir)

        if not (shadow / "HEAD").exists():
            return []

        ok, stdout, _ = _run_git(
            ["log", "--format=%H|%h|%aI|%s", "-n", str(self.max_snapshots)],
            shadow, abs_dir,
        )

        if not ok or not stdout:
            return []

        results = []
        for line in stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                entry = {
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "timestamp": parts[2],
                    "reason": parts[3],
                    "files_changed": 0,
                    "insertions": 0,
                    "deletions": 0,
                }
                # Get diffstat for this commit
                stat_ok, stat_out, _ = _run_git(
                    ["diff", "--shortstat", f"{parts[0]}~1", parts[0]],
                    shadow, abs_dir,
                    allowed_returncodes={128, 129},  # first commit has no parent
                )
                if stat_ok and stat_out:
                    self._parse_shortstat(stat_out, entry)
                results.append(entry)
        return results

    @staticmethod
    def _parse_shortstat(stat_line: str, entry: Dict) -> None:
        """Parse git --shortstat output into entry dict."""
        import re
        m = re.search(r'(\d+) file', stat_line)
        if m:
            entry["files_changed"] = int(m.group(1))
        m = re.search(r'(\d+) insertion', stat_line)
        if m:
            entry["insertions"] = int(m.group(1))
        m = re.search(r'(\d+) deletion', stat_line)
        if m:
            entry["deletions"] = int(m.group(1))

    def diff(self, working_dir: str, commit_hash: str) -> Dict:
        """Show diff between a checkpoint and the current working tree.

        Returns dict with success, diff text, and stat summary.
        """
        abs_dir = str(Path(working_dir).resolve())
        shadow = _shadow_repo_path(abs_dir)

        if not (shadow / "HEAD").exists():
            return {"success": False, "error": "No checkpoints exist for this directory"}

        # Verify the commit exists
        ok, _, err = _run_git(
            ["cat-file", "-t", commit_hash], shadow, abs_dir,
        )
        if not ok:
            return {"success": False, "error": f"Checkpoint '{commit_hash}' not found"}

        # Stage current state to compare against checkpoint
        _run_git(["add", "-A"], shadow, abs_dir, timeout=_GIT_TIMEOUT * 2)

        # Get stat summary: checkpoint vs current working tree
        ok_stat, stat_out, _ = _run_git(
            ["diff", "--stat", commit_hash, "--cached"],
            shadow, abs_dir,
        )

        # Get actual diff (limited to avoid terminal flood)
        ok_diff, diff_out, _ = _run_git(
            ["diff", commit_hash, "--cached", "--no-color"],
            shadow, abs_dir,
        )

        # Unstage to avoid polluting the shadow repo index
        _run_git(["reset", "HEAD", "--quiet"], shadow, abs_dir)

        if not ok_stat and not ok_diff:
            return {"success": False, "error": "Could not generate diff"}

        return {
            "success": True,
            "stat": stat_out if ok_stat else "",
            "diff": diff_out if ok_diff else "",
        }

    def restore(self, working_dir: str, commit_hash: str, file_path: str = None) -> Dict:
        """Restore files to a checkpoint state.

        Uses ``git checkout <hash> -- .`` (or a specific file) which restores
        tracked files without moving HEAD — safe and reversible.

        Parameters
        ----------
        file_path : str, optional
            If provided, restore only this file instead of the entire directory.

        Returns dict with success/error info.
        """
        abs_dir = str(Path(working_dir).resolve())
        shadow = _shadow_repo_path(abs_dir)

        if not (shadow / "HEAD").exists():
            return {"success": False, "error": "No checkpoints exist for this directory"}

        # Verify the commit exists
        ok, _, err = _run_git(
            ["cat-file", "-t", commit_hash], shadow, abs_dir,
        )
        if not ok:
            return {"success": False, "error": f"Checkpoint '{commit_hash}' not found", "debug": err or None}

        # Take a checkpoint of current state before restoring (so you can undo the undo)
        self._take(abs_dir, f"pre-rollback snapshot (restoring to {commit_hash[:8]})")

        # Restore — full directory or single file
        restore_target = file_path if file_path else "."
        ok, stdout, err = _run_git(
            ["checkout", commit_hash, "--", restore_target],
            shadow, abs_dir, timeout=_GIT_TIMEOUT * 2,
        )

        if not ok:
            return {"success": False, "error": f"Restore failed: {err}", "debug": err or None}

        # Get info about what was restored
        ok2, reason_out, _ = _run_git(
            ["log", "--format=%s", "-1", commit_hash], shadow, abs_dir,
        )
        reason = reason_out if ok2 else "unknown"

        result = {
            "success": True,
            "restored_to": commit_hash[:8],
            "reason": reason,
            "directory": abs_dir,
        }
        if file_path:
            result["file"] = file_path
        return result

    def get_working_dir_for_path(self, file_path: str) -> str:
        """Resolve a file path to its working directory for checkpointing.

        Walks up from the file's parent to find a reasonable project root
        (directory containing .git, pyproject.toml, package.json, etc.).
        Falls back to the file's parent directory.
        """
        path = Path(file_path).resolve()
        if path.is_dir():
            candidate = path
        else:
            candidate = path.parent

        # Walk up looking for project root markers
        markers = {".git", "pyproject.toml", "package.json", "Cargo.toml",
                    "go.mod", "Makefile", "pom.xml", ".hg", "Gemfile"}
        check = candidate
        while check != check.parent:
            if any((check / m).exists() for m in markers):
                return str(check)
            check = check.parent

        # No project root found — use the file's parent
        return str(candidate)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _take(self, working_dir: str, reason: str) -> bool:
        """Take a snapshot.  Returns True on success."""
        shadow = _shadow_repo_path(working_dir)

        # Init if needed
        err = _init_shadow_repo(shadow, working_dir)
        if err:
            logger.debug("Checkpoint init failed: %s", err)
            return False

        # Quick size guard — don't try to snapshot enormous directories
        if _dir_file_count(working_dir) > _MAX_FILES:
            logger.debug("Checkpoint skipped: >%d files in %s", _MAX_FILES, working_dir)
            return False

        # Stage everything
        ok, _, err = _run_git(
            ["add", "-A"], shadow, working_dir, timeout=_GIT_TIMEOUT * 2,
        )
        if not ok:
            logger.debug("Checkpoint git-add failed: %s", err)
            return False

        # Check if there's anything to commit
        ok_diff, diff_out, _ = _run_git(
            ["diff", "--cached", "--quiet"],
            shadow,
            working_dir,
            allowed_returncodes={1},
        )
        if ok_diff:
            # No changes to commit
            logger.debug("Checkpoint skipped: no changes in %s", working_dir)
            return False

        # Commit
        ok, _, err = _run_git(
            ["commit", "-m", reason, "--allow-empty-message"],
            shadow, working_dir, timeout=_GIT_TIMEOUT * 2,
        )
        if not ok:
            logger.debug("Checkpoint commit failed: %s", err)
            return False

        logger.debug("Checkpoint taken in %s: %s", working_dir, reason)

        # Prune old snapshots
        self._prune(shadow, working_dir)

        return True

    def _prune(self, shadow_repo: Path, working_dir: str) -> None:
        """Keep only the last max_snapshots commits and actually free disk.

        Technique: rebuild the newest ``max_snapshots`` commits as a fresh
        chain via ``git commit-tree`` (oldest-to-newest, each new commit
        carrying the original tree + message + identity), point the branch
        at the new head, then expire reflogs and ``git gc --prune=now`` so
        the dropped old objects are physically deleted.

        Why not ``git filter-branch`` or moving the ref?
        - Moving a ref keeps the ref's *ancestors* (the OLDEST commits) and
          orphans newer descendants — backwards for a snapshot log.
        - ``filter-branch`` refuses to run on a dirty worktree, and the
          checkpointed project dirs are almost always dirty.
        ``commit-tree`` touches neither the index nor the worktree — it only
        creates objects and moves a ref, so it's safe on live projects.
        """
        ok, stdout, _ = _run_git(
            ["rev-list", "--count", "HEAD"], shadow_repo, working_dir,
        )
        if not ok:
            return

        try:
            count = int(stdout)
        except ValueError:
            return

        if count <= self.max_snapshots:
            return

        # Newest max_snapshots commits, newest-first.
        ok, all_commits, _ = _run_git(
            ["rev-list", "HEAD"], shadow_repo, working_dir,
        )
        if not ok or not all_commits:
            logger.debug("Checkpoint prune: could not list commits")
            return
        keep = all_commits.splitlines()[: self.max_snapshots]

        # Rebuild the chain oldest-first so commit-tree can chain parents.
        new_head = None
        for commit in reversed(keep):
            ok, tree, _ = _run_git(
                ["rev-parse", f"{commit}^{{tree}}"], shadow_repo, working_dir,
            )
            if not ok or not tree:
                logger.debug("Checkpoint prune: tree lookup failed for %s", commit[:8])
                return
            ok, msg, _ = _run_git(
                ["log", "-1", "--format=%B", commit], shadow_repo, working_dir,
            )
            if not ok:
                logger.debug("Checkpoint prune: message lookup failed for %s", commit[:8])
                return
            # Preserve original author identity + timestamp so the rewritten
            # commits read like the originals.
            ok, ident, _ = _run_git(
                ["log", "-1", "--format=%an%x00%ae%x00%aI", commit],
                shadow_repo, working_dir,
            )
            ident = ident.split("\x00") if ok and ident else None
            env_extra = {}
            if ident and len(ident) == 3:
                env_extra.update({
                    "GIT_AUTHOR_NAME": ident[0],
                    "GIT_AUTHOR_EMAIL": ident[1],
                    "GIT_AUTHOR_DATE": ident[2],
                    "GIT_COMMITTER_NAME": ident[0],
                    "GIT_COMMITTER_EMAIL": ident[1],
                    "GIT_COMMITTER_DATE": ident[2],
                })

            tree_args = ["commit-tree", tree]
            if new_head:
                tree_args += ["-p", new_head]
            tree_args += ["-F", "-"]
            ok, new_commit, _ = _run_git(
                tree_args, shadow_repo, working_dir,
                input_text=msg + "\n", env_extra=env_extra,
            )
            if not ok or not new_commit:
                logger.debug("Checkpoint prune: commit-tree failed for %s", commit[:8])
                return
            new_head = new_commit

        # Move the branch to the rebuilt head and drop the old chain.
        ok_branch, branch, _ = _run_git(
            ["symbolic-ref", "--short", "HEAD"], shadow_repo, working_dir,
        )
        if not ok_branch or not branch:
            logger.debug("Checkpoint prune: HEAD not on a branch; skipping")
            return
        _run_git(
            ["update-ref", f"refs/heads/{branch}", new_head],
            shadow_repo, working_dir,
        )
        # Expire reflogs and physically delete the orphaned objects.
        _run_git(["reflog", "expire", "--expire=now", "--all"],
                 shadow_repo, working_dir)
        _run_git(["gc", "--prune=now", "--quiet"],
                 shadow_repo, working_dir,
                 timeout=_GIT_TIMEOUT * 10)

        logger.debug(
            "Checkpoint pruned %s: kept %d/%d commits (head %s)",
            shadow_repo.name, len(keep), count, new_head[:8],
        )


def format_checkpoint_list(checkpoints: List[Dict], directory: str) -> str:
    """Format checkpoint list for display to user."""
    if not checkpoints:
        return f"No checkpoints found for {directory}"

    lines = [f"📸 Checkpoints for {directory}:\n"]
    for i, cp in enumerate(checkpoints, 1):
        # Parse ISO timestamp to something readable
        ts = cp["timestamp"]
        if "T" in ts:
            ts = ts.split("T")[1].split("+")[0].split("-")[0][:5]  # HH:MM
            date = cp["timestamp"].split("T")[0]
            ts = f"{date} {ts}"

        # Build change summary
        files = cp.get("files_changed", 0)
        ins = cp.get("insertions", 0)
        dele = cp.get("deletions", 0)
        if files:
            stat = f"  ({files} file{'s' if files != 1 else ''}, +{ins}/-{dele})"
        else:
            stat = ""

        lines.append(f"  {i}. {cp['short_hash']}  {ts}  {cp['reason']}{stat}")

    lines.append("\n  /rollback <N>             restore to checkpoint N")
    lines.append("  /rollback diff <N>        preview changes since checkpoint N")
    lines.append("  /rollback <N> <file>      restore a single file from checkpoint N")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Store-wide management — status / prune / clear
#
# Adapted from nousresearch/main's tools/checkpoint_manager.py for this
# fork's simpler layout: CHECKPOINT_BASE/{sha256(abs_dir)[:16]}/ shadow repos
# directly, no "v2 store" migration or legacy-<ts>/ archives. Upstream's
# store_status()/prune_checkpoints()/clear_all()/clear_legacy() assume that
# migrated-store shape; porting it wholesale would mean migrating this
# fork's live checkpoint data to a format it was never written in. These
# adapted versions work against the actual on-disk layout instead, and keep
# upstream's response-dict shape (legacy_size_bytes/legacy_archives always
# empty here) so daedalus_cli/checkpoints.py's CLI layer needs no changes.
# ---------------------------------------------------------------------------

def _dir_size_bytes(path: Path) -> int:
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _shadow_repo_git_stats(shadow_repo: Path) -> tuple:
    """(commit_count, last_touch_epoch) for a shadow repo, independent of
    whether its original working_dir still exists on disk — unlike
    ``_run_git``, this never ``cwd``s into the (possibly-gone) workdir."""
    def _git(args):
        try:
            result = subprocess.run(
                ["git", f"--git-dir={shadow_repo}"] + args,
                capture_output=True, text=True, timeout=_GIT_TIMEOUT,
            )
            return result.returncode == 0, result.stdout.strip()
        except Exception:
            return False, ""

    ok, out = _git(["rev-list", "--count", "HEAD"])
    commits = int(out) if ok and out.isdigit() else 0
    ok, out = _git(["log", "-1", "--format=%ct"])
    last_touch = float(out) if ok and out else None
    return commits, last_touch


def store_status(checkpoint_base: Optional[Path] = None) -> Dict:
    """Total size, project count, and per-project breakdown of the store."""
    base = checkpoint_base or CHECKPOINT_BASE
    projects: List[Dict] = []
    total_size = 0
    if base.exists():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            size = _dir_size_bytes(child)
            total_size += size
            workdir_file = child / "DAEDALUS_WORKDIR"
            workdir = None
            if workdir_file.exists():
                try:
                    workdir = workdir_file.read_text(encoding="utf-8").strip() or None
                except OSError:
                    pass
            exists = bool(workdir) and Path(workdir).exists()
            commits, last_touch = _shadow_repo_git_stats(child)
            projects.append({
                "hash": child.name,
                "path": str(child),
                "workdir": workdir,
                "exists": exists,
                "commits": commits,
                "last_touch": last_touch,
                "size_bytes": size,
            })
    return {
        "base": str(base),
        "total_size_bytes": total_size,
        "store_size_bytes": total_size,
        "legacy_size_bytes": 0,
        "project_count": len(projects),
        "projects": projects,
        "pre_v2_projects": [],
        "legacy_archives": [],
    }


def prune_checkpoints(
    retention_days: int = 7,
    delete_orphans: bool = True,
    max_total_size_mb: int = 500,
    orphan_allowlist: Optional[Set[str]] = None,
    checkpoint_base: Optional[Path] = None,
) -> Dict:
    """Delete orphan/stale project shadow repos and cap total store size.

    Orphan = workdir no longer exists on disk. Stale = last_touch older than
    ``retention_days``. After that pass, if the store still exceeds
    ``max_total_size_mb``, drops whole projects (oldest last_touch first)
    until it fits — this fork has no per-commit GC finer than that.
    """
    base = checkpoint_base or CHECKPOINT_BASE
    result = {"scanned": 0, "deleted_orphan": 0, "deleted_stale": 0, "errors": 0, "bytes_freed": 0}
    if not base.exists():
        return result

    info = store_status(base)
    result["scanned"] = info["project_count"]
    now = time.time()
    stale_cutoff = now - (retention_days * 86400)
    remaining: List[Dict] = []

    for p in info["projects"]:
        is_orphan = not p["exists"]
        is_stale = p["last_touch"] is not None and p["last_touch"] < stale_cutoff
        should_delete = False
        reason = None
        if is_orphan and delete_orphans:
            if orphan_allowlist is None or p["hash"] in orphan_allowlist:
                should_delete = True
                reason = "orphan"
        if not should_delete and is_stale:
            should_delete = True
            reason = "stale"
        if should_delete:
            try:
                shutil.rmtree(p["path"])
                result["bytes_freed"] += p["size_bytes"]
                if reason == "orphan":
                    result["deleted_orphan"] += 1
                else:
                    result["deleted_stale"] += 1
            except OSError:
                logger.warning("Failed to prune checkpoint project %s", p["path"], exc_info=True)
                result["errors"] += 1
                remaining.append(p)
        else:
            remaining.append(p)

    max_bytes = max_total_size_mb * 1024 * 1024
    total = sum(p["size_bytes"] for p in remaining)
    if total > max_bytes:
        for p in sorted(remaining, key=lambda x: (x["last_touch"] or 0)):
            if total <= max_bytes:
                break
            try:
                shutil.rmtree(p["path"])
                total -= p["size_bytes"]
                result["bytes_freed"] += p["size_bytes"]
                result["deleted_stale"] += 1
            except OSError:
                logger.warning("Failed to prune checkpoint project %s (size cap)", p["path"], exc_info=True)
                result["errors"] += 1

    return result


def clear_all(checkpoint_base: Optional[Path] = None) -> Dict[str, int]:
    """Delete the entire checkpoint base. All /rollback history is lost."""
    base = checkpoint_base or CHECKPOINT_BASE
    if not base.exists():
        return {"deleted": False, "bytes_freed": 0}
    size = _dir_size_bytes(base)
    try:
        shutil.rmtree(base)
        return {"deleted": True, "bytes_freed": size}
    except OSError:
        logger.error("Failed to clear checkpoint base %s", base, exc_info=True)
        return {"deleted": False, "bytes_freed": 0}


def clear_legacy(checkpoint_base: Optional[Path] = None) -> Dict[str, int]:
    """No-op on this fork's layout — there is no legacy-<ts>/ archive
    format here (that's an artifact of upstream's v1->v2 store migration,
    which this fork's flat per-project layout never went through). Kept so
    ``daedalus checkpoints clear-legacy`` behaves sanely (reports nothing to
    clear) instead of erroring, matching upstream's CLI surface."""
    return {"deleted": 0, "bytes_freed": 0}
