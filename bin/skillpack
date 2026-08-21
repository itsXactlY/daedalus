#!/usr/bin/env python3
"""
skillpack — bundle Daedalus skills into portable, verifiable skillpacks.

A skillpack is a single .zip archive containing a manifest.json plus the
skill directories (SKILL.md + references/scripts/templates/assets). It can
be copied to another machine and installed with one command, with checksums
so the contents can be verified before and after installation.

Commands
--------
  list [--category CAT]        List available skills (for packing)
  pack <name> <skill>...       Pack named skills into <name>.skillpack.zip
       [--version V] [--description D] [--out DIR]
  pack <name> --category CAT   Pack every skill in a category
  pack <name> --all            Pack the entire skills library
  info <archive>               Show the manifest of an archive
  verify <archive>             Validate zip + manifest + checksums + frontmatter
  unpack <archive> [--dir D]   Install into a skills dir (default ~/.daedalus/skills)
         [--force]             Overwrite existing skill directories

Exit codes: 0 ok, 1 error, 2 user input error.

Examples
--------
  python3 skillpack.py pack backend-dev github-code-review test-driven-development \
      --description "Backend dev toolkit"
  python3 skillpack.py pack devops-kit --category devops
  python3 skillpack.py pack full-library --all
  python3 skillpack.py verify backend-dev.skillpack.zip
  python3 skillpack.py unpack backend-dev.skillpack.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import signal
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_VERSION = "1.0.0"
FORMAT_NAME = "daedalus-skillpack"
FORMAT_VERSION = 1

HOME = Path.home()
DEFAULT_SKILLS_DIR = HOME / ".daedalus" / "skills"
DEFAULT_OUT_DIR = HOME / ".daedalus" / "skillpacks"

# Files never packed / installed.
SKIP_NAMES = {"__pycache__", ".DS_Store", ".git", "node_modules"}
# Extension that the archive must end in.
PACK_SUFFIX = ".skillpack.zip"

_FRONTMATTER_VERSION = re.compile(
    r"^---\s*\n(.*?)\n---\s*", re.MULTILINE | re.DOTALL
)


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------

def discover_skills(skills_dir: Path) -> Dict[str, Dict]:
    """Map skill name -> {path, category, version, description}.

    Walks the whole tree for SKILL.md files — the layout is mixed:
      skills/<skill>/SKILL.md                    flat (category = "")
      skills/<cat>/<skill>/SKILL.md              one level
      skills/<cat>/<subcat>/<skill>/SKILL.md     nested (category = cat/subcat)
    A skill is registered under its directory name; duplicates across
    categories keep the first (alphabetical).
    """
    out: Dict[str, Dict] = {}
    if not skills_dir.exists():
        return out
    for sk in sorted(skills_dir.rglob("SKILL.md")):
        parts = sk.relative_to(skills_dir).parts  # (…, <skill>, SKILL.md)
        if len(parts) < 2:
            continue
        name = parts[-2]
        category = "/".join(parts[:-2])  # "" for flat skills
        if name in SKIP_NAMES:
            continue
        version, description = read_frontmatter(sk)
        out.setdefault(name, {
            "name": name,
            "category": category,
            "path": str(sk.parent),
            "version": version,
            "description": description,
        })
    return out


def read_frontmatter(skill_md: Path) -> Tuple[str, str]:
    """Return (version, description) from a SKILL.md frontmatter."""
    version, description = "1.0.0", ""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return version, description
    m = _FRONTMATTER_VERSION.search(text)
    if not m:
        return version, description
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip().strip("'\"")
            if key == "version" and value:
                version = value
            elif key == "description" and value:
                description = value
    return version, description


def resolve_skill(name: str, skills: Dict[str, Dict],
                  category: Optional[str] = None) -> Dict:
    """Resolve a skill name to its record; raise with candidates on ambiguity."""
    if name in skills:
        rec = skills[name]
        if category and rec["category"] != category:
            raise LookupError(
                f"skill '{name}' exists in category '{rec['category']}', "
                f"not '{category}'"
            )
        return rec
    # Partial match as a fallback hint.
    hints = [n for n in skills if name in n]
    if len(hints) == 1:
        return skills[hints[0]]
    if hints:
        raise LookupError(
            f"skill '{name}' not found. Did you mean: {', '.join(sorted(hints))}"
        )
    raise LookupError(f"skill '{name}' not found in {skills}")


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------

def arc_prefix(category: str, name: str) -> str:
    """Archive path prefix for a skill: category/name, or just name when flat."""
    if category:
        return f"skills/{category}/{name}"
    return f"skills/{name}"


def _is_nested_skill_file(skill_dir: Path, file_path: Path) -> bool:
    """True if file_path lives inside a subdirectory that is itself a skill.

    Some flat skills (e.g. skills/dogfood/SKILL.md) share their directory
    with categorized sibling skills (skills/dogfood/clean-restart/…). Those
    nested skills are packed as their own entries — never as part of the
    flat skill's file set.
    """
    rel = file_path.relative_to(skill_dir).parts[:-1]  # dirs only
    for depth in range(1, len(rel) + 1):
        candidate = skill_dir.joinpath(*rel[:depth])
        if (candidate / "SKILL.md").exists():
            return True
    return False


def collect_files(skill_dir: Path) -> List[Path]:
    """All packable files under a skill dir, relative to the dir, sorted.

    Never descends into nested skill directories (subdirs with their own
    SKILL.md) — those belong to a different skill entry.
    """
    files = []
    for p in sorted(skill_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(skill_dir)
        if any(part in SKIP_NAMES for part in rel.parts):
            continue
        if _is_nested_skill_file(skill_dir, p):
            continue
        files.append(rel)
    return files


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(name: str, version: str, description: str,
                   skills: List[Dict], author: str) -> Dict:
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "name": name,
        "version": version,
        "description": description,
        "author": author,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "packed_by": f"skillpack/{TOOL_VERSION}",
        "total_skills": len(skills),
        "skills": skills,
    }
    return manifest


def pack_skills(name: str, records: List[Dict], version: str, description: str,
                out_dir: Path, author: str) -> Path:
    """Write a skillpack zip for the given skill records. Returns the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{name}{PACK_SUFFIX}"

    manifest_skills = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in records:
            skill_dir = Path(rec["path"])
            files = collect_files(skill_dir)
            if not files:
                continue
            checksums: Dict[str, str] = {}
            for rel in files:
                abs_path = skill_dir / rel
                arc = f"{arc_prefix(rec['category'], rec['name'])}/{rel}"
                zf.write(abs_path, arc)
                checksums[str(rel)] = "sha256:" + sha256_of(abs_path)
            manifest_skills.append({
                "name": rec["name"],
                "category": rec["category"],
                "version": rec["version"],
                "description": rec["description"],
                "files": [str(f) for f in files],
                "checksums": checksums,
            })
        manifest = build_manifest(name, version, description,
                                  manifest_skills, author)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return archive


# ---------------------------------------------------------------------------
# Inspection / verification
# ---------------------------------------------------------------------------

def load_manifest(archive: Path) -> Tuple[Dict, Dict[str, bytes]]:
    """Return (manifest, raw_file_map) from a skillpack zip."""
    with zipfile.ZipFile(archive, "r") as zf:
        if "manifest.json" not in zf.namelist():
            raise ValueError("not a skillpack: missing manifest.json")
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if manifest.get("format") != FORMAT_NAME:
            raise ValueError(
                f"not a daedalus skillpack (format={manifest.get('format')!r})"
            )
        raw = {n: zf.read(n) for n in zf.namelist() if n != "manifest.json"}
    return manifest, raw


def verify_archive(archive: Path) -> Tuple[bool, List[str]]:
    """Full integrity check. Returns (ok, messages)."""
    errors: List[str] = []
    info: List[str] = []
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                return False, [f"corrupt member: {bad}"]
            names = zf.namelist()
        manifest, raw = load_manifest(archive)
    except Exception as exc:
        return False, [f"could not read archive: {exc}"]

    info.append(f"pack '{manifest.get('name')}' v{manifest.get('version')} "
                f"({manifest.get('total_skills')} skills, "
                f"{len(raw)} files)")

    # Every manifest entry must exist with matching checksum.
    for sk in manifest.get("skills", []):
        sk_name = sk.get("name", "?")
        prefix = arc_prefix(sk.get("category", ""), sk_name)
        for rel, cksum in (sk.get("checksums") or {}).items():
            arc = f"{prefix}/{rel}"
            if arc not in raw:
                errors.append(f"{sk_name}: missing {arc}")
                continue
            algo, _, expect = cksum.partition(":")
            if algo != "sha256":
                errors.append(f"{sk_name}: unsupported checksum algo {algo}")
                continue
            actual = hashlib.sha256(raw[arc]).hexdigest()
            if actual != expect:
                errors.append(f"{sk_name}: checksum mismatch for {rel}")

    # No checksum, no entry: flag it.
    declared = {
        f"{arc_prefix(sk.get('category', ''), sk.get('name', '?'))}/{f}"
        for sk in manifest.get("skills", [])
        for f in (sk.get("files") or [])
    }
    for n in raw:
        if n not in declared:
            errors.append(f"undeclared file in archive: {n}")

    # Every SKILL.md must have frontmatter.
    for sk in manifest.get("skills", []):
        arc = f"{arc_prefix(sk.get('category', ''), sk.get('name', '?'))}/SKILL.md"
        if arc in raw:
            body = raw[arc].decode("utf-8", errors="replace")
            if not body.startswith("---"):
                errors.append(f"{sk.get('name')}: SKILL.md missing YAML frontmatter")

    return (not errors), info + errors


# ---------------------------------------------------------------------------
# Unpacking / installing
# ---------------------------------------------------------------------------

def unpack_archive(archive: Path, target: Path, force: bool) -> Tuple[int, List[str]]:
    """Install a verified skillpack into target skills dir. Returns (count, msgs)."""
    ok, msgs = verify_archive(archive)
    if not ok:
        return 0, msgs
    manifest, raw = load_manifest(archive)

    conflicts: List[str] = []
    for sk in manifest.get("skills", []):
        cat, name = sk.get("category", ""), sk.get("name", "?")
        dest = target / name if not cat else target / cat / name
        if dest.exists() and not force:
            conflicts.append(str(dest))

    if conflicts:
        return 0, [
            "refusing to overwrite existing skills (use --force to override):",
            *["  " + c for c in conflicts],
        ]

    installed = 0
    for sk in manifest.get("skills", []):
        cat, name = sk.get("category", ""), sk.get("name", "?")
        sk_dir = target / name if not cat else target / cat / name
        sk_dir.mkdir(parents=True, exist_ok=True)
        prefix = arc_prefix(cat, name)
        for rel, cksum in (sk.get("checksums") or {}).items():
            arc = f"{prefix}/{rel}"
            if arc not in raw:
                continue
            dest = sk_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw[arc])
            installed += 1
    return installed, [f"installed {installed} files into {target}"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    skills = discover_skills(Path(args.dir))
    if args.category:
        skills = {n: r for n, r in skills.items()
                  if r["category"] == args.category}
    if not skills:
        print("no skills found")
        return 1
    for name in sorted(skills):
        rec = skills[name]
        print(f"{rec['category']:<28} {name:<40} v{rec['version']}  {rec['description']}")
    print(f"\n{len(skills)} skills")
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    skills = discover_skills(Path(args.dir))
    if args.all:
        records = sorted(skills.values(), key=lambda r: (r["category"], r["name"]))
        if not records:
            print("no skills found to pack")
            return 1
    elif args.category:
        records = [r for r in skills.values() if r["category"] == args.category]
        if not records:
            print(f"no skills in category '{args.category}'")
            return 1
    else:
        if not args.skills:
            print("error: pass skill names, --category, or --all")
            return 2
        records = []
        for s in args.skills:
            try:
                records.append(resolve_skill(s, skills))
            except LookupError as exc:
                print(f"error: {exc}")
                return 2
    archive = pack_skills(args.name, records, args.version, args.description,
                          Path(args.out), args.author)
    ok, msgs = verify_archive(archive)
    for m in msgs:
        print(m)
    if not ok:
        print("warning: pack failed self-verification")
        return 1
    print(f"packed {len(records)} skills -> {archive}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    try:
        manifest, raw = load_manifest(Path(args.archive))
    except Exception as exc:
        print(f"error: {exc}")
        return 1
    print(f"name       : {manifest.get('name')}")
    print(f"version    : {manifest.get('version')}")
    print(f"description: {manifest.get('description') or '-'}")
    print(f"author     : {manifest.get('author') or '-'}")
    print(f"created    : {manifest.get('created_at')}")
    print(f"format     : {manifest.get('format')} v{manifest.get('format_version')}")
    print(f"files      : {len(raw)}")
    print("skills     :")
    for sk in manifest.get("skills", []):
        print(f"  - {sk.get('name')}  ({sk.get('category')}, "
              f"v{sk.get('version')}, {len(sk.get('files') or [])} files)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    ok, msgs = verify_archive(Path(args.archive))
    for m in msgs:
        print(("OK  " if ok else "ERR ") + m)
    print("VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


def cmd_unpack(args: argparse.Namespace) -> int:
    target = Path(args.dir)
    installed, msgs = unpack_archive(Path(args.archive), target, args.force)
    for m in msgs:
        print(m)
    return 0 if installed else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="skillpack", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("list", help="list available skills")
    pl.add_argument("--dir", default=str(DEFAULT_SKILLS_DIR), help=argparse.SUPPRESS)
    pl.add_argument("--category", help="filter by category")
    pl.set_defaults(func=cmd_list)

    pp = sub.add_parser("pack", help="create a skillpack")
    pp.add_argument("name", help="pack name (file will be <name>.skillpack.zip)")
    pp.add_argument("skills", nargs="*", help="skill names to include")
    pp.add_argument("--category", help="pack all skills in a category")
    pp.add_argument("--all", action="store_true", help="pack every skill")
    pp.add_argument("--version", default="1.0.0", help="pack version")
    pp.add_argument("--description", default="", help="pack description")
    pp.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="output dir")
    pp.add_argument("--author", default="alca", help="author name")
    pp.add_argument("--dir", default=str(DEFAULT_SKILLS_DIR), help=argparse.SUPPRESS)
    pp.set_defaults(func=cmd_pack)

    pi = sub.add_parser("info", help="show archive manifest")
    pi.add_argument("archive")
    pi.set_defaults(func=cmd_info)

    pv = sub.add_parser("verify", help="validate an archive")
    pv.add_argument("archive")
    pv.set_defaults(func=cmd_verify)

    pu = sub.add_parser("unpack", help="install an archive")
    pu.add_argument("archive")
    pu.add_argument("--dir", default=str(DEFAULT_SKILLS_DIR), help="target skills dir")
    pu.add_argument("--force", action="store_true", help="overwrite existing")
    pu.set_defaults(func=cmd_unpack)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    # Die quietly on broken pipes (e.g. `skillpack list | head`).
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(main())
