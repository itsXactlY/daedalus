"""Install-health checks: does the INSTALLED harness actually work?

Every check in here answers one question: would this Daedalus install start
right now for a user who did not happen to run it from the repository root?

The failure class this module exists for: ``pyproject.toml`` declares its
top-level modules by hand. Upstream added ``daedalus_state_common``,
``_schema``, ``_search`` and ``_portability`` (and imported them from
``daedalus_state.py``) without touching that list. A wheel built from that
state ships ``daedalus_state.py`` without its imports, so every
``pip install daedalus`` / ``uvx daedalus`` dies on the first import with
``ModuleNotFoundError: No module named 'daedalus_state_common'``. An editable
checkout survives only because four entry points happen to shove the repo root
onto ``sys.path`` by hand.

So there are three separate things to check:

* ``static_findings``   — repo-declared packaging vs. repo-reachable imports
* ``runtime_findings``  — what the installed distribution actually exposes
* ``smoke_test``        — import the harness from a neutral cwd, for real

Used by ``daedalus update`` (postflight), ``daedalus doctor`` and
``tests/test_packaging_integrity.py`` so all three judge health the same way.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Console entry points from pyproject [project.scripts]. These are the code
# paths that have to import cleanly on a user's machine.
ENTRY_MODULES = ("daedalus_cli.main", "run_agent", "acp_adapter.entry")

# Directories that are never part of the distribution even though they may
# contain importable-looking files.
_SKIP_DIRS = {"tests", "docs", "scripts", "nix", "bin", "build", "dist", "temp_vision_images"}

_IMPORT_MODULE_RE = re.compile(r"""import_module\(\s*["']([A-Za-z0-9_.]+)["']""")


@dataclass
class Finding:
    """One concrete reason the install is not trustworthy."""

    kind: str  # "undeclared-module" | "undeclared-package" | "not-installed" | "import-fails"
    subject: str  # "daedalus_state_common" or "daedalus_cli.main"
    detail: str = ""
    repairable: bool = True

    def __str__(self) -> str:
        return f"[{self.kind}] {self.subject}: {self.detail}" if self.detail else f"[{self.kind}] {self.subject}"


@dataclass
class Health:
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def repairable(self) -> bool:
        return bool(self.findings) and all(f.repairable for f in self.findings)

    def __bool__(self) -> bool:
        return self.ok


# --------------------------------------------------------------------------
# static: what the repository itself declares vs. what it can reach
# --------------------------------------------------------------------------

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _local_module_path(root: Path, dotted: str) -> Path | None:
    """Resolve a dotted name inside the repo, or None if it is not local."""
    parts = dotted.split(".")
    candidate = root.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate
    candidate = root.joinpath(*parts) / "__init__.py"
    if candidate.is_file():
        return candidate
    return None


def _iter_imports(py_file: Path) -> set[str]:
    """Absolute dotted names imported by one file (relative imports resolved)."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"), filename=str(py_file))
    except (SyntaxError, OSError, ValueError):
        return set()

    base = list(py_file.parent.resolve().relative_to(py_file.anchor).parts[:-1])

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                if len(anchor) < node.level - 1:
                    continue
                prefix = ".".join(anchor)
                for alias in node.names:
                    found.add(f"{prefix}.{alias.name}" if prefix else alias.name)
            elif node.module:
                found.add(node.module)
                for alias in node.names:
                    found.add(f"{node.module}.{alias.name}")

    # Dynamic imports never reach ast, but they do reach production.
    try:
        found.update(_IMPORT_MODULE_RE.findall(py_file.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        pass
    return found


def reachable_modules(root: Path | None = None, entries=ENTRY_MODULES) -> set[str]:
    """Top-level modules/packages the shipped entry points can actually reach."""
    root = root or project_root()
    seen: set[str] = set()
    queue: list[str] = list(entries)
    while queue:
        dotted = queue.pop()
        top = dotted.split(".")[0]
        if top in _SKIP_DIRS:
            continue
        path = _local_module_path(root, dotted)
        if path is None or dotted in seen:
            continue
        seen.add(dotted)
        for imported in _iter_imports(path):
            if imported.split(".")[0] in _SKIP_DIRS:
                continue
            if _local_module_path(root, imported) is not None:
                queue.append(imported)
    return seen


def missing_modules(root: Path | None = None, entries=ENTRY_MODULES) -> set[str]:
    """Local-looking imports whose file does not exist in the checkout.

    ``reachable_modules`` skips them silently -- a name with no file cannot be
    queued -- which is how "daedalus_state.py imports daedalus_state_broken_probe,
    and no such file exists" reaches a running harness and crashes it there.
    Third-party imports (openai, httpx, ...) are indistinguishable from missing
    ones by path alone, so only two unambiguous groups are reported: the
    project's own ``daedalus*`` namespace, and anything pyproject still
    declares but no longer ships.
    """
    root = root or project_root()
    declared = set(_declared(root / "pyproject.toml", "py-modules"))
    missing: set[str] = set()
    queue: list[str] = list(entries)
    seen: set[str] = set()
    while queue:
        dotted = queue.pop()
        path = _local_module_path(root, dotted)
        if path is None or dotted in seen:
            continue
        seen.add(dotted)
        for imported in _iter_imports(path):
            head = imported.split(".")[0]
            if head in _SKIP_DIRS or head in missing:
                continue
            if _local_module_path(root, imported) is None:
                # `from pkg import name` resolves to an ATTRIBUTE when there is
                # no submodule of that name. Only a head that does not exist on
                # its own is a genuinely missing module.
                if _local_module_path(root, head) is not None:
                    continue
                if head.startswith("daedalus") or head in declared:
                    missing.add(head)
                continue
            queue.append(imported)
    return missing


def _declared(pyproject: Path, key: str) -> list[str]:
    """Read a pyproject array without requiring a TOML parser on old Pythons."""
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    match = re.search(rf"^{key}\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return re.findall(r'["\']([^"\']+)["\']', match.group(1))


def static_findings(root: Path | None = None) -> list[Finding]:
    """Packaging declarations vs. reachable imports. No install required."""
    root = root or project_root()
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return [Finding("no-pyproject", str(root), "no pyproject.toml at the project root", repairable=False)]

    py_modules = set(_declared(pyproject, "py-modules"))
    packages = set(_declared(pyproject, "include"))

    findings: list[Finding] = []
    for name in sorted(missing_modules(root)):
        findings.append(Finding(
            "missing-module", name,
            "imported by the shipped entry points, but no such file exists in the "
            "checkout — the harness will raise ModuleNotFoundError on first use",
            repairable=False,
        ))
    for dotted in sorted(reachable_modules(root)):
        top = dotted.split(".")[0]
        if (root / top).is_dir():
            # a package dir -- must match packages.find include
            if top not in packages:
                findings.append(Finding(
                    "undeclared-package", top,
                    "imported by the shipped entry points but absent from "
                    "[tool.setuptools.packages.find] include — a wheel built now will not contain it",
                ))
        elif dotted == top:
            # a top-level module file (foo.py) -- must be shipped as py-module
            if top not in py_modules:
                findings.append(Finding(
                    "undeclared-module", top,
                    "imported by the shipped entry points but absent from "
                    "[tool.setuptools] py-modules — a wheel built now will not contain it",
                ))
    return findings


# --------------------------------------------------------------------------
# runtime: what this installation actually exposes
# --------------------------------------------------------------------------

def _site_packages() -> Path:
    return Path(sysconfig.get_paths()["purelib"])


def editable_mapping() -> dict[str, str] | None:
    """The name->path map a setuptools editable install froze at install time.

    None when the install is not editable-mapped (regular wheel install or a
    plain ``.pth`` pointing at the checkout — both resolve everything).
    """
    finder = None
    for candidate in _site_packages().glob("__editable___*_finder.py"):
        finder = candidate
        break
    if finder is None:
        return None
    try:
        source = finder.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"^MAPPING[^=]*=\s*\{(.*?)\}", source, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    return dict(re.findall(r"'([^']+)'\s*:\s*'([^']+)'", match.group(1)))


def runtime_findings(root: Path | None = None) -> list[Finding]:
    """What the running interpreter can import that the repo needs."""
    root = root or project_root()
    mapping = editable_mapping()
    if mapping is None:
        return []  # wheel install: the static check is the one that applies

    needed = {d for d in reachable_modules(root) if d == d.split(".")[0]}
    missing = sorted(n for n in needed if n not in mapping)
    findings: list[Finding] = []
    for name in missing:
        # resolvable anyway when the checkout root is on sys.path
        if name in sys.modules:
            continue
        findings.append(Finding(
            "not-installed", name,
            "present in the checkout but missing from the installed editable mapping "
            f"({len(mapping)} entries, frozen at install time) — imports fail unless the "
            "repository root happens to be the working directory",
        ))
    return findings


# --------------------------------------------------------------------------
# the only check that cannot lie: actually import it, from nowhere
# --------------------------------------------------------------------------

@dataclass
class SmokeResult:
    ok: bool
    failed: list[str] = field(default_factory=list)
    output: str = ""
    returncode: int = 0

    def __str__(self) -> str:
        if self.ok:
            return "install smoke test passed"
        return "install smoke test FAILED: " + ", ".join(self.failed)


def probe_modules(root: Path | None = None) -> list[str]:
    """The names an install has to be able to import: entry points + everything
    they pull in at module level.

    Probing only the console entry points is not enough: ``daedalus_cli.main``
    imports ``daedalus_state`` lazily, from inside functions. A broken
    ``daedulas_state`` therefore passes an entry-point-only probe and still
    crashes on first use. This list is derived from the same AST walk the
    packaging gate uses, so the probe and the gate judge the same set.
    """
    root = root or project_root()
    names = set(ENTRY_MODULES)
    for dotted in reachable_modules(root):
        names.add(dotted.split(".")[0])
    return sorted(names)


def smoke_modules(modules=None, python: str | None = None, timeout: float = 300.0) -> SmokeResult:
    """Import the given modules in a subprocess whose cwd is NOT the repo.

    This is the check the existing code never ran: an update could report
    "✓ Update complete!" while leaving an installation that cannot be
    imported. It has to run outside the checkout or ``sys.path`` from the
    working directory masks the very breakage it is looking for.
    """
    python = python or sys.executable
    modules = list(modules) if modules is not None else probe_modules()
    probe = "import sys\n" + "".join(f"import {m}\n" for m in modules)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    with tempfile.TemporaryDirectory(prefix="daedalus-smoke-") as neutral_cwd:
        try:
            proc = subprocess.run(
                [python, "-c", probe],
                cwd=neutral_cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return SmokeResult(False, list(modules), "import probe timed out", returncode=124)

    if proc.returncode == 0:
        return SmokeResult(True, output=proc.stdout)

    failed = _failed_imports(proc.stderr) or list(modules)
    return SmokeResult(False, failed, (proc.stderr or proc.stdout).strip()[-4000:], proc.returncode)


def _failed_imports(stderr: str) -> list[str]:
    """Names from the FIRST ImportError in a traceback, not all of them.

    Importing 40 modules stops at the first failure, so the names after it were
    never tried; reporting them all would invent breakage that isn't there.
    """
    for line in (stderr or "").splitlines():
        if line.startswith("ModuleNotFoundError") or ": No module named" in line:
            names = re.findall(r"No module named ['\"]([\w.]+)['\"]", line)
            if names:
                return sorted({n.split(".")[0] for n in names})
    return []


def check(root: Path | None = None, *, smoke: bool = True, python: str | None = None) -> Health:
    """Full health picture: static, runtime and a real import from nowhere."""
    health = Health()
    health.findings.extend(static_findings(root))
    health.findings.extend(runtime_findings(root))
    if smoke:
        result = smoke_modules(python=python)
        if not result.ok:
            for name in result.failed:
                health.findings.append(Finding(
                    "import-fails", name,
                    "importing from a neutral working directory raises "
                    f"ModuleNotFoundError — {result.output.splitlines()[-1] if result.output else 'see details'}",
                ))
    return health


# --------------------------------------------------------------------------
# repair
# --------------------------------------------------------------------------

def repair(root: Path | None = None, *, quiet: bool = False) -> tuple[bool, str]:
    """Re-run the editable install so the mapping matches the checkout again.

    This is the one fix that covers both packaging drift (the file was never
    declared) and a stale mapping (it was declared but the install predates
    it): ``pip install -e .`` regenerates the mapping from the current
    ``pyproject.toml``.
    """
    import shutil

    root = root or project_root()
    uv = shutil.which("uv")
    if uv:
        cmd = [uv, "pip", "install", "-e", "."]
        env = {**os.environ}
        prefix = sys.prefix if sys.prefix != sys.base_prefix else None
        if prefix:
            env["VIRTUAL_ENV"] = prefix
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-e", "."]

    proc = subprocess.run(cmd, cwd=root, env=locals().get("env"), capture_output=True, text=True)
    if proc.returncode == 0:
        return True, "reinstalled the editable package"
    tail = (proc.stderr or proc.stdout).strip()[-600:]
    if not quiet:
        print(f"  ✗ {tail}")
    return False, tail or "pip install failed"


if __name__ == "__main__":  # manual use: python -m daedalus_cli.install_health
    root = project_root()
    if "--repair" in sys.argv:
        ok, msg = repair(root)
        print(("✓ " if ok else "✗ ") + msg)
        raise SystemExit(0 if ok else 1)

    health = check(root)
    if health.ok:
        print("✓ installation healthy")
        raise SystemExit(0)
    for finding in health.findings:
        print(f"  ✗ {finding}")
    print("\nFix with: daedalus doctor --fix   (or: python -m daedalus_cli.install_health --repair)")
    raise SystemExit(1)