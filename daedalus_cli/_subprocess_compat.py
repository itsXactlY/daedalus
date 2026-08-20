"""Windows subprocess compatibility helpers (minimal port).

This is a minimal subset of the upstream ``daedalus_cli/_subprocess_compat``
module, backported so agent/skill_preprocessing.py can keep the upstream
import shape (``IS_WINDOWS``, ``windows_hide_flags``).

The two helpers here are the only names the skill-preprocessing feature
needs:

* ``IS_WINDOWS`` — cheap platform check used to decide whether to pass
  Win32 ``creationflags`` to ``subprocess.run``.
* ``windows_hide_flags()`` — returns ``CREATE_NO_WINDOW`` on Windows so a
  short-lived helper process doesn't flash a console window, and ``0`` on
  every other platform (a safe no-op).

All helpers are no-ops on non-Windows — calling them in Linux/macOS code
paths is safe by design.
"""

from __future__ import annotations

import sys

__all__ = ["IS_WINDOWS", "windows_hide_flags"]


IS_WINDOWS = sys.platform == "win32"


# Win32 CreationFlag — defined here rather than imported from subprocess
# because CREATE_NO_WINDOW isn't guaranteed to be present on stdlib
# subprocess on older Pythons or non-Windows builds.
_CREATE_NO_WINDOW = 0x08000000


def windows_hide_flags() -> int:
    """Return Win32 creationflags that merely hide the child's console
    window without detaching the child.  0 on non-Windows.

    Use for short-lived console apps spawned as part of a larger
    operation where we want no flash but also want to collect
    stdout/exit code synchronously.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NO_WINDOW
