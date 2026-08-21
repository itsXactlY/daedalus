"""Resolve DAEDALUS_HOME for standalone skill scripts.

Skill scripts may run outside the Daedalus process (system Python, nix env,
CI) where ``daedalus_constants`` is not importable.  This module provides the
same ``get_daedalus_home()`` contract without requiring it on ``sys.path``.

When ``daedalus_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from daedalus_constants import get_daedalus_home as get_daedalus_home
except (ModuleNotFoundError, ImportError):

    def get_daedalus_home() -> Path:
        """Return the Daedalus home directory (default: ``~/.daedalus``)."""
        val = os.environ.get("DAEDALUS_HOME", "").strip()
        return Path(val) if val else Path.home() / ".daedalus"
