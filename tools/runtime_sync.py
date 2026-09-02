from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

SYNCED_TREES: Tuple[str, ...] = ("plugins", "scripts", "skins", "cron")
SYNCED_FILES: Tuple[str, ...] = ("SOUL.md",)

MANIFEST_NAME = ".bundled_runtime_manifest"

_SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules"}
_SKIP_SUFFIXES = (".pyc", ".pyo")


def _home() -> Path:
    from daedalus_constants import get_daedalus_home
    return get_daedalus_home()


def _source() -> Path:
    from daedalus_constants import get_code_root
    return get_code_root()


def _manifest_path() -> Path:
    return _home() / MANIFEST_NAME


def _read_manifest() -> Dict[str, str]:
    try:
        with _manifest_path().open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_manifest(entries: Dict[str, str]) -> None:
    path = _manifest_path()
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except Exception as exc:
        logger.debug("runtime manifest write failed: %s", exc)
        try:
            os.unlink(tmp)
        except Exception:
            pass


def _file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _wanted(path: Path) -> bool:
    if path.suffix in _SKIP_SUFFIXES:
        return False
    return not any(part in _SKIP_DIRS for part in path.parts)


def _bundled_files() -> List[Tuple[str, Path]]:
    src = _source()
    out: List[Tuple[str, Path]] = []
    for name in SYNCED_FILES:
        candidate = src / name
        if candidate.is_file():
            out.append((name, candidate))
    for tree in SYNCED_TREES:
        root = src / tree
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and _wanted(path.relative_to(src)):
                out.append((str(path.relative_to(src)), path))
    return out


def sync_runtime(quiet: bool = False, apply: bool = True,
                 force: bool = False) -> Dict[str, Any]:
    """Reconcile the distribution's runtime trees into DAEDALUS_HOME.

    plugins/, scripts/, skins/, cron/ and SOUL.md exist twice after the
    repository was split out of the runtime home: the repository ships them and
    the running agent loads them from DAEDALUS_HOME. Without a reconcile the two
    drift, and the drift is silent — the memory provider's circuit breaker sat
    in the repository for a day while the agent kept loading the copy without
    it.

    An operator edit always wins. A destination whose hash no longer matches
    what was last synced is reported and left alone, exactly as skills_sync
    treats a user-modified skill; nothing in the runtime that the distribution
    does not ship is ever removed.
    """
    src = _source()
    dest_root = _home()
    result: Dict[str, Any] = {
        "copied": [], "updated": [], "user_modified": [], "skipped": 0,
        "total_bundled": 0, "source": str(src), "home": str(dest_root),
        "applied": bool(apply),
    }
    if src.resolve() == dest_root.resolve():
        result["skipped"] = -1
        return result

    manifest = _read_manifest()
    bundled = _bundled_files()
    result["total_bundled"] = len(bundled)

    for rel, source_path in bundled:
        dest = dest_root / rel
        bundled_hash = _file_hash(source_path)
        if not bundled_hash:
            continue

        if not dest.exists():
            if apply:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest)
                except Exception as exc:
                    logger.warning("runtime sync could not place %s: %s", rel, exc)
                    continue
            manifest[rel] = bundled_hash
            result["copied"].append(rel)
            if not quiet:
                print(f"  + {rel}")
            continue

        dest_hash = _file_hash(dest)
        if dest_hash == bundled_hash:
            manifest[rel] = bundled_hash
            result["skipped"] += 1
            continue

        origin = manifest.get(rel, "")
        if origin and dest_hash != origin:
            result["user_modified"].append(rel)
            if not quiet:
                print(f"  ~ {rel} (locally modified, kept)")
            continue
        if not origin and not force:
            manifest[rel] = dest_hash
            result["user_modified"].append(rel)
            if not quiet:
                print(f"  ~ {rel} (untracked, kept — --force takes the bundled one)")
            continue

        if apply:
            try:
                shutil.copy2(source_path, dest)
            except Exception as exc:
                logger.warning("runtime sync could not update %s: %s", rel, exc)
                continue
        manifest[rel] = bundled_hash
        result["updated"].append(rel)
        if not quiet:
            print(f"  ↑ {rel}")

    if apply:
        _write_manifest(manifest)
    return result


def adopt_runtime(quiet: bool = False) -> Dict[str, Any]:
    """Record the runtime's current state as the sync baseline.

    Run once after a split or a manual copy: it claims every destination that
    matches nothing yet, so the next sync can tell a real operator edit from a
    file that was simply never tracked.
    """
    manifest = _read_manifest()
    adopted = []
    for rel, _source_path in _bundled_files():
        dest = _home() / rel
        if dest.is_file():
            h = _file_hash(dest)
            if h and manifest.get(rel) != h:
                manifest[rel] = h
                adopted.append(rel)
    _write_manifest(manifest)
    if not quiet:
        print(f"  adopted {len(adopted)} runtime file(s) as the sync baseline")
    return {"adopted": adopted}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Reconcile bundled runtime trees into DAEDALUS_HOME.")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--adopt", action="store_true",
                    help="record the runtime as the baseline instead of syncing")
    ap.add_argument("--force", action="store_true",
                    help="for untracked destinations take the bundled file "
                         "(first reconcile after a split); a tracked local edit "
                         "is still kept")
    args = ap.parse_args()

    if args.adopt:
        adopt_runtime()
        return 0

    r = sync_runtime(quiet=False, apply=args.apply, force=args.force)
    if r["skipped"] == -1:
        print("  source and runtime are the same directory — nothing to sync")
        return 0
    print(f"\n  source {r['source']}\n  home   {r['home']}")
    print(f"  bundled {r['total_bundled']} · copied {len(r['copied'])} · "
          f"updated {len(r['updated'])} · kept {len(r['user_modified'])} · "
          f"unchanged {r['skipped']}")
    if not args.apply:
        print("  (dry run — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
