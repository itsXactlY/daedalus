"""Packaging must not drift from the code it ships.

The failure this guards against is not theoretical. ``daedalus_state.py`` was
split into ``daedalus_state_common`` / ``_schema`` / ``_search`` /
``_portability`` and imported all four on module load, while
``[tool.setuptools] py-modules`` kept the old hand-written list. A wheel built
from that state contains ``daedalus_state.py`` and none of its imports:

    $ unzip -l daedalus-*.whl | grep daedalus_state
    daedalus_state.py                 <- shipped
    (nothing else)                    <- its four imports are not

Every ``pip install daedalus`` / ``uvx daedalus`` then dies with
``ModuleNotFoundError: No module named 'daedalus_state_common'``. Editable
checkouts only survive because four entry points push the repo root onto
``sys.path`` by hand -- which is exactly why nobody noticed.

So the test derives the reachable module set from the source itself (AST
import closure from the ``[project.scripts]`` entry points) and compares it to
what pyproject declares. Adding a module and importing it from the agent makes
this fail until it is declared. That failure is the whole point: it is cheap
now and it is the difference between a working update and a bricked one.
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from daedalus_cli.install_health import (  # noqa: E402
    ENTRY_MODULES,
    editable_mapping,
    project_root,
    reachable_modules,
    runtime_findings,
    smoke_modules,
    static_findings,
)

ROOT = project_root()


def _declared(key: str) -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(rf"^{key}\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    assert match, f"{key} not found in pyproject.toml"
    return re.findall(r'["\']([^"\']+)["\']', match.group(1))


def test_reachable_set_is_not_empty():
    """Guard the guard: a broken AST walk would make this test vacuous."""
    reachable = reachable_modules(ROOT)
    assert {"daedalus_cli.main", "run_agent", "acp_adapter.entry"} <= reachable
    assert any(m.startswith("daedalus_cli.") for m in reachable)


def test_declared_py_modules_cover_reachable_top_level_modules():
    declared = set(_declared("py-modules"))
    missing = [
        m for m in reachable_modules(ROOT)
        if (ROOT / m).is_file() and m not in declared
    ]
    assert not missing, (
        "These modules are imported by code that ships, but are not in "
        "[tool.setuptools] py-modules. A wheel built now will contain the "
        "importer and not the imported, and the install will fail on first "
        f"use:\n  " + "\n  ".join(missing)
    )


def test_declared_packages_cover_reachable_packages():
    declared = set(_declared("include"))
    missing = [
        m for m in reachable_modules(ROOT)
        if (ROOT / m).is_dir() and m not in declared
    ]
    assert not missing, (
        "These packages are imported by code that ships, but are not in "
        "[tool.setuptools.packages.find] include:\n  " + "\n  ".join(missing)
    )


def test_no_static_packaging_findings():
    findings = static_findings(ROOT)
    assert not findings, "\n".join(str(f) for f in findings)


def test_installed_editable_mapping_covers_the_checkout():
    """A mapping frozen before a module existed breaks every non-repo cwd."""
    findings = runtime_findings(ROOT)
    assert not findings, "\n".join(
        f"{f} -- re-run `pip install -e .` to regenerate the mapping" for f in findings
    )


def test_declared_py_modules_all_exist():
    """A name in py-modules that no longer exists also breaks a build."""
    ghost = [name for name in _declared("py-modules") if not (ROOT / f"{name}.py").is_file()]
    assert not ghost, f"pyproject declares modules that do not exist: {ghost}"


@pytest.mark.slow
def test_installed_harness_imports_outside_the_repository():
    """The check the updater never ran, run by hand."""
    result = smoke_modules(python=sys.executable)
    assert result.ok, f"{result}\n{result.output}"


@pytest.mark.slow
def test_built_wheel_contains_every_reachable_module(tmp_path_factory):
    """Build the real wheel and look inside it. Slower, but conclusive."""
    out = tmp_path_factory.mktemp("wheel")
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"wheel build unavailable: {proc.stderr.strip()[-300:]}")

    wheels = list(out.glob("*.whl"))
    assert wheels, "build reported success but produced no wheel"
    with zipfile.ZipFile(wheels[0]) as zf:
        names = set(zf.namelist())

    required = {f"{m}.py" for m in reachable_modules(ROOT) if (ROOT / m).is_file()}
    # submodules of top-level packages land as <pkg>/<mod>.py
    for dotted in reachable_modules(ROOT):
        if dotted == dotted.split(".")[0] or (ROOT / dotted.split(".")[0]).is_dir():
            required.add(dotted.replace(".", "/") + ".py")

    missing = sorted(n for n in required if n not in names)
    assert not missing, (
        f"Wheel {wheels[0].name} is missing {len(missing)} module(s) that the "
        f"shipped code imports:\n  " + "\n  ".join(missing)
    )