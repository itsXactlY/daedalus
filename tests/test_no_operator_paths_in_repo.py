import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

def _operator_homes():
    """Home directories belonging to whoever is building this checkout.

    Documentation and fixtures legitimately use placeholder homes
    (/home/user, /home/alice). What must never ship is the path of the person
    who wrote the commit: it breaks for everyone else and leaks their
    username and project layout into a public repository.
    """
    import getpass
    import os

    names = set()
    try:
        names.add(getpass.getuser())
    except Exception:
        pass
    home = os.path.expanduser("~")
    if home and home != "~":
        names.add(Path(home).name)
    return {n for n in names if n and n not in {"user", "root", "runner", "test"}}


def _tracked_files():
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pytest.skip("git is unavailable or this is not a checkout")
    return [REPO / name for name in out.split("\0") if name]


class TestTheRepoCarriesNobodysHomeDirectory:
    """A hardcoded home path is broken for everyone but its author.

    It also leaks the author's username and project layout into a public
    repository. Paths belong relative to __file__, in an env var, or as a
    generic placeholder.
    """

    def test_no_tracked_file_carries_the_builders_home(self):
        homes = _operator_homes()
        if not homes:
            pytest.skip("cannot determine the current user")
        needles = [f"/home/{name}/" for name in homes]
        offenders = []
        for path in _tracked_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for needle in needles:
                if needle in text:
                    offenders.append(f"{path.relative_to(REPO)}: {needle}")
        assert not offenders, (
            "the builder's own home leaked into tracked files:\n  "
            + "\n  ".join(sorted(set(offenders))[:20])
            + "\nUse a path relative to __file__, an env var, or /home/user/."
        )

    def test_placeholder_homes_are_allowed(self):
        assert "user" not in _operator_homes()


class TestRuntimeStateStaysOutOfTheRepo:
    @pytest.mark.parametrize("name", ["cron/jobs.json", "bin/tirith"])
    def test_operator_state_is_not_tracked(self, name):
        tracked = {str(p.relative_to(REPO)) for p in _tracked_files()}
        assert name not in tracked
