"""Whole-collection, LLM-free self-audit of the installed skills.

``tools.skill_linter`` answers "is this one SKILL.md well-formed?". It cannot
answer the questions a skill cannot see about itself:

  * does the hub's member index still match the directories on disk?
  * does a member exist that the hub never lists (invisible to the index)?
  * do two skills claim the same ``name``?
  * does a skill call a tool that the harness does not actually expose?
  * has the collection drifted from the recorded manifest?

Those are collection-level invariants, so they live here. This module is
deterministic by construction — stdlib only, no network, no model call, no
import of harness runtime modules beyond the pure frontmatter parser. The same
tree in produces the same report out, which is what makes it usable as a
regression gate instead of a vibe check.

Deliberately NOT here: anything needing judgement ("is this description
useful?", "is this advice correct?"). Those stay with the LLM. The split is
the point — spend the deterministic half on the 409 files, spend the model on
the handful of findings a human still has to look at.

CLI::

    python3 -m tools.skills_selfaudit <skills-root> [--harness DIR] [--json]
                                         [--lint] [--manifest FILE]

Exit code 1 if any ERROR-severity finding, else 0. ``--lint`` additionally runs
the per-skill advisory linter (noisy by design: ~2000 convention warnings).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from agent.skill_utils import parse_frontmatter
from tools.skill_linter import ERROR, WARNING, LintFinding, lint_skill

# Directories under a skills root that hold no live skill.
_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    ".curator_backups", "index-cache", "_consolidate",
}

# ``- **member-name** — description`` in a hub's "## Members" list.
_MEMBER_RE = re.compile(r"^\s*[-*]\s+\*\*([A-Za-z0-9][A-Za-z0-9_.-]*)\*\*")

# "This hub aggregates 20 member skills under references/."
_HUB_COUNT_RE = re.compile(r"aggregates\s+(\d+)\s+member\s+skills?", re.I)

# A backticked token that is being *called*: `browser_navigate(url=...)`.
# This fires on every `fetch(` and `queue(` in every code sample, so on its own
# it is noise. A finding is only raised when the name is a near-miss of a real
# tool — see check_tool_references for why that subset is the provable one.
_TOOL_CALL_RE = re.compile(r"`([a-z][a-z0-9_]{2,40})\s*\(")

# A whole markdown table cell that is just a tool name: | `browser_click` | ... |
_TOOL_CELL_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_]{2,40})`\s*\|")

# Identifiers that look like tool calls but never are.
_TOOL_STOPLIST = {
    "self", "cls", "args", "kwargs", "init", "main", "str", "int", "float",
    "bool", "list", "dict", "set", "tuple", "len", "open", "print", "type",
    "super", "isinstance", "getattr", "setattr", "hasattr", "range", "enumerate",
    "zip", "sorted", "sum", "min", "max", "abs", "any", "all", "map", "filter",
    "json", "yaml", "os", "sys", "re", "io", "shutil", "subprocess", "pathlib",
    "dataclass", "field", "asyncio", "threading", "logging", "time", "math",
    "random", "glob", "shlex", "textwrap", "itertools", "functools", "typing",
    "collections", "datetime", "tempfile", "traceback", "warnings", "copy",
    "inspect", "hashlib", "base64", "urllib", "http", "socket", "sqlite3",
    "pytest", "unittest", "assert", "setup", "install", "pip", "npm", "bash",
    "python", "python3", "node", "npm", "git", "curl", "wget", "chmod", "mkdir",
    "true", "false", "null", "none", "nan", "inf", "todo", "fixme", "xxx",
}

# Tool names that exist but are not visible in a static scan of the harness:
# MCP-provided tools and memory-provider tools resolve at runtime.
_DYNAMIC_TOOL_PREFIXES = ("mcp__", "mazemaker_", "memory_")

# Where harness tool names live, relative to the harness root.
_TOOL_SOURCE_DIRS = ("tools", "plugins", "agent", "daedalus_cli")

# This module sits in <harness>/tools/, so the checkout is two levels up.
# Deriving it keeps the tool portable instead of hardcoding one operator's home.
_HARNESS_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Report:
    """Collection-level findings, plus whatever per-skill lint produced."""

    findings: List[LintFinding] = field(default_factory=list)
    skill_count: int = 0
    hub_count: int = 0
    by_rule: Dict[str, int] = field(default_factory=dict)

    def add(
        self,
        severity: str,
        rule: str,
        message: str,
        where: str = "",
        skill: str = "",
    ) -> None:
        prefix = f"{where}: " if where else ""
        self.findings.append(LintFinding(severity, rule, prefix + message, skill))

    def finalize(self) -> "Report":
        counts: Dict[str, int] = defaultdict(int)
        for f in self.findings:
            counts[f.rule] += 1
        self.by_rule = dict(counts)
        return self

    @property
    def has_errors(self) -> bool:
        return any(f.severity == ERROR for f in self.findings)

    def to_json(self) -> str:
        return json.dumps(
            {
                "skill_count": self.skill_count,
                "hub_count": self.hub_count,
                "total": len(self.findings),
                "errors": sum(1 for f in self.findings if f.severity == ERROR),
                "by_rule": dict(sorted(self.by_rule.items(), key=lambda kv: -kv[1])),
                "findings": [
                    {
                        "severity": f.severity,
                        "rule": f.rule,
                        "skill": f.skill,
                        "message": f.message,
                    }
                    for f in self.findings
                ],
            },
            indent=2,
            sort_keys=False,
        )


def discover_skills(root: Path) -> List[Path]:
    """Every live SKILL.md under ``root``, sorted, deterministic."""
    out: List[Path] = []
    for path in root.rglob("SKILL.md"):
        rel_parts = path.relative_to(root).parts
        if any(part in _SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        out.append(path)
    return sorted(out)


def _read(path: Path) -> Tuple[Dict, str]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}, ""
    return parse_frontmatter(content)


def _members_section(body: str) -> str:
    """The text under a hub's '## Members' heading, or '' when there is none."""
    match = re.search(r"^##\s+Members\s*$", body, re.M)
    if not match:
        return ""
    rest = body[match.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def collect_hub_members(body: str) -> List[str]:
    section = _members_section(body)
    if not section:
        return []
    names: List[str] = []
    for line in section.splitlines():
        m = _MEMBER_RE.match(line)
        if m:
            names.append(m.group(1))
    return names


def check_hub_index(report: Report, root: Path, skill_paths: List[Path]) -> None:
    """Hub '## Members' list vs the directories actually under references/.

    Both directions matter. A listed-but-absent member is a dead index entry —
    the model is told the skill exists and gets nothing back. An on-disk member
    the hub never lists is worse in a quiet way: the skill loads fine when
    named directly but never appears in the hub's description, so routing
    almost never finds it.

    Driven by the HUBS, not by their members. A member-driven loop cannot check
    the worst case at all: when every listed member is missing there is no
    member file to iterate, so the hub that needs checking most is the one that
    is skipped.
    """
    for hub_md in skill_paths:
        rel = hub_md.relative_to(root)
        if len(rel.parts) != 2:  # a hub is <category>/SKILL.md
            continue
        hub_dir = hub_md.parent
        hub_rel = str(rel.parent)
        _, hub_body = _read(hub_md)
        listed = collect_hub_members(hub_body)
        on_disk = {
            p.parent.name
            for p in (hub_dir / "references").glob("*/SKILL.md")
            if p.is_file()
        }
        if not listed and not on_disk:
            continue  # a standalone skill that happens to sit at depth 2
        if not listed:
            report.add(
                WARNING, "hub-no-member-list",
                f"has {len(on_disk)} member(s) under references/ but no '## Members' list "
                f"— nothing to route on",
                where=hub_rel,
            )
            continue
        for name in listed:
            if name not in on_disk:
                report.add(
                    ERROR, "hub-member-missing",
                    f"lists member '{name}' but references/{name}/SKILL.md does not exist",
                    where=hub_rel,
                )
        for name in sorted(on_disk - set(listed)):
            report.add(
                WARNING, "hub-member-unlisted",
                f"references/{name}/ exists but the hub never lists it "
                f"— unreachable via the index",
                where=hub_rel,
            )
        declared = _HUB_COUNT_RE.search(hub_body)
        if declared and int(declared.group(1)) != len(on_disk):
            report.add(
                WARNING, "hub-count-drift",
                f"header says '{declared.group(0)}' but {len(on_disk)} member(s) on disk",
                where=hub_rel,
            )


def check_duplicate_names(report: Report, root: Path, skill_paths: List[Path]) -> None:
    """Two skills claiming the same name — routing cannot pick between them."""
    seen: Dict[str, List[str]] = defaultdict(list)
    for skill_md in skill_paths:
        fm, _ = _read(skill_md)
        name = str(fm.get("name", "")).strip()
        if name:
            seen[name].append(str(skill_md.relative_to(root).parent))
    for name, dirs in sorted(seen.items()):
        if len(dirs) > 1:
            report.add(
                ERROR, "duplicate-skill-name",
                f"'{name}' is claimed by {len(dirs)} skills: {', '.join(sorted(dirs))}",
            )


def harvest_tool_names(harness_root: Path) -> Set[str]:
    """Tool names the harness actually exposes, found statically.

    Two shapes cover the codebase: a schema dict entry (``"name": "browser_click"``)
    and the callable itself (``def browser_click(``). Only ``tools/`` and
    ``plugins/`` are scanned — ``agent/`` and ``daedalus_cli/`` hold internals
    whose function names are not part of the model's tool surface and would
    pollute the near-miss matching below.

    Static scanning keeps the audit import-free: importing the tool stack has
    side effects, which would make the audit slow and stateful — exactly what an
    audit must not be.
    """
    names: Set[str] = set()
    schema_re = re.compile(r'["\']name["\']\s*:\s*["\']([a-z][a-z0-9_]{2,40})["\']')
    # Indented on purpose: the tool surface includes methods, not just
    # module-level functions. `plugins/memory/__init__.py` registers
    # `register_memory_provider` as a *method*, and a column-0-only pattern
    # reports that skill as wrong when the skill is right.
    def_re = re.compile(r"^\s*(?:async\s+)?def\s+([a-z][a-z0-9_]{2,40})\s*\(", re.M)
    for rel_dir in ("tools", "plugins", "agent", "daedalus_cli"):
        base = harness_root / rel_dir
        if not base.is_dir():
            continue
        for py in base.rglob("*.py"):
            if set(py.parts) & _SKIP_DIRS:
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            names.update(schema_re.findall(text))
            names.update(def_re.findall(text))
    return names


def collect_tool_calls(body: str) -> Set[str]:
    """Tool names a skill body appears to invoke."""
    found: Set[str] = set()
    for m in _TOOL_CALL_RE.finditer(body):
        found.add(m.group(1))
    for line in body.splitlines():
        m = _TOOL_CELL_RE.match(line)
        if m:
            found.add(m.group(1))
    return found


def check_tool_references(
    report: Report, root: Path, skill_paths: List[Path], known_tools: Set[str]
) -> None:
    """A skill calling a tool that no longer exists — the rename-drift check.

    Scoping matters here. Flagging every unknown ``name(`` gives 400+ false
    positives, because skills legitimately quote Cloudflare's ``fetch(``, PIL's
    ``rgba(`` and a hundred other foreign APIs in their examples. What is
    *provable* is narrower and far more useful: the skill names something that
    is one edit away from a tool this harness actually registers. That is a
    renamed or removed tool, and it is the failure that silently breaks a skill
    at runtime while the prose still reads perfectly.
    """
    for skill_md in skill_paths:
        _, body = _read(skill_md)
        rel = str(skill_md.relative_to(root).parent)
        for name in sorted(collect_tool_calls(body)):
            if name in _TOOL_STOPLIST or name in known_tools:
                continue
            if name.startswith(_DYNAMIC_TOOL_PREFIXES):
                continue
            close = difflib.get_close_matches(name, known_tools, n=1, cutoff=0.82)
            if not close:
                continue  # a foreign API, not harness drift
            # Require the same leading token. `browser_navigat` next to
            # `browser_navigate` is drift; `background` next to `is_background`
            # is a coincidence between two unrelated vocabularies.
            if name.split("_", 1)[0] != close[0].split("_", 1)[0]:
                continue
            report.add(
                WARNING, "tool-reference-drift",
                f"calls `{name}(` but the harness registers `{close[0]}` — "
                f"renamed or removed?",
                where=rel,
            )


def parse_manifest_names(manifest: Path) -> Set[str]:
    """Skill names out of a ``.audit/manifest.txt``.

    The file is a human-readable report, not a path list::

        == (uncategorized) ==
          agent-orchestration  [2983b, 0 refs]  Autonomous agent orchestration hub: ...

    So the name is the first token of an indented line under a ``== category ==``
    header. Anything else in the file (headers, blank lines) is ignored. An
    earlier version of this audit assumed paths and reported 456 phantom
    removals, which is what a wrong assumption costs.
    """
    names: Set[str] = set()
    try:
        text = manifest.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return names
    for line in text.splitlines():
        if not line.startswith((" ", "\t")):
            continue
        m = re.match(r"^\s+([A-Za-z0-9][A-Za-z0-9_.-]*)\s+\[", line)
        if m:
            names.add(m.group(1))
    return names


def check_manifest_drift(
    report: Report, root: Path, skill_paths: List[Path], manifest: Path
) -> None:
    """The recorded manifest vs what is on disk right now.

    The manifest is a point-in-time census. If it has drifted, every conclusion
    drawn from it — "0 duplicates", "quarantine list empty" — is stale, and
    nobody notices because the file is not regenerated by anything.
    """
    if not manifest.is_file():
        report.add(
            WARNING, "manifest-missing",
            f"no manifest at {manifest} — the collection has never been recorded",
        )
        return
    recorded = parse_manifest_names(manifest)
    if not recorded:
        report.add(
            WARNING, "manifest-unreadable",
            f"{manifest} has no recognisable skill entries — format changed?",
        )
        return
    current: Set[str] = set()
    for skill_md in skill_paths:
        fm, _ = _read(skill_md)
        name = str(fm.get("name", "")).strip()
        if name:
            current.add(name)
    gone = sorted(recorded - current)
    new = sorted(current - recorded)
    if gone:
        report.add(
            WARNING, "manifest-drift-removed",
            f"{len(gone)} name(s) in the manifest are gone from disk: "
            f"{', '.join(gone[:8])}" + (" ..." if len(gone) > 8 else ""),
        )
    if new:
        report.add(
            WARNING, "manifest-drift-added",
            f"{len(new)} skill(s) on disk are not in the manifest: "
            f"{', '.join(new[:8])}" + (" ..." if len(new) > 8 else ""),
        )


def audit_collection(
    root: Path,
    harness_root: Optional[Path] = None,
    manifest: Optional[Path] = None,
    run_lint: bool = False,
) -> Report:
    """Audit every skill under ``root``. Deterministic, no LLM, no network."""
    root = Path(root)
    report = Report()
    if not root.is_dir():
        report.add(ERROR, "skills-root-missing", f"{root} is not a directory")
        return report.finalize()

    skill_paths = discover_skills(root)
    report.skill_count = len(skill_paths)
    report.hub_count = sum(
        1 for p in skill_paths if len(p.relative_to(root).parts) == 2
    )

    check_hub_index(report, root, skill_paths)
    check_duplicate_names(report, root, skill_paths)

    if harness_root is not None:
        check_tool_references(
            report, root, skill_paths, harvest_tool_names(Path(harness_root))
        )

    if manifest is not None:
        check_manifest_drift(report, root, skill_paths, Path(manifest))

    if run_lint:
        for skill_md in skill_paths:
            meta, _ = _read(skill_md)
            who = str(meta.get("name") or skill_md.parent.name)
            for f in lint_skill(skill_md):
                report.findings.append(
                    LintFinding(f.severity, f.rule, f.message, who)
                )

    return report.finalize()


def format_report(report: Report, root: Path) -> str:
    lines = [
        f"Skills self-audit: {root}",
        f"  {report.skill_count} SKILL.md, {report.hub_count} hub(s), "
        f"{len(report.findings)} finding(s)",
    ]
    if report.by_rule:
        lines.append("  by rule:")
        for rule, count in sorted(report.by_rule.items(), key=lambda kv: -kv[1]):
            lines.append(f"    {count:5d}  {rule}")
    errors = [f for f in report.findings if f.severity == ERROR]
    warnings = [f for f in report.findings if f.severity == WARNING]
    for title, group in (("ERRORS", errors), ("WARNINGS", warnings)):
        if not group:
            continue
        lines.append(f"\n  {title} ({len(group)}):")
        for f in group[:200]:
            lines.append(f"    {f.format()}")
        if len(group) > 200:
            lines.append(f"    ... {len(group) - 200} more")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. Named ``main`` (not ``_main``) so the CLI can call it."""
    parser = argparse.ArgumentParser(
        prog="daedalus skills selfaudit",
        description="Deterministic, LLM-free audit of a skills collection.",
    )
    parser.add_argument("root", help="skills root, e.g. ~/.daedalus/skills")
    parser.add_argument(
        "--harness",
        default=str(_HARNESS_ROOT),
        help="harness root used to harvest the real tool surface "
             "(default: the checkout this module lives in)",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="manifest.txt to diff against (default: <root>/.audit/manifest.txt)",
    )
    parser.add_argument(
        "--no-tool-check", action="store_true", help="skip the tool-reference check"
    )
    parser.add_argument(
        "--lint", action="store_true", help="also run the per-skill advisory linter"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser()
    manifest = (
        Path(args.manifest).expanduser()
        if args.manifest
        else root / ".audit" / "manifest.txt"
    )
    report = audit_collection(
        root,
        harness_root=None if args.no_tool_check else Path(args.harness).expanduser(),
        manifest=manifest if manifest.is_file() or manifest.parent.is_dir() else None,
        run_lint=args.lint,
    )
    print(report.to_json() if args.json else format_report(report, root))
    return 1 if report.has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
