"""The working plan: <workdir>/.daedalus/PLAN.md, pinned onto every user turn.

The window carries only the last few turns, so a plan the agent wrote five
turns ago is gone unless something puts it back. This does: each turn's API
copy of the user message gets the current file attached. The snapshot is frozen
into that turn's ``api_content`` sidecar, so the prompt-cache prefix stays
byte-stable.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional

PLAN_DIR = ".daedalus"
PLAN_NAME = "PLAN.md"
PLAN_MAX_CHARS = 4000

_CLOSED_RE = re.compile(r"^\s*status:\s*(done|abandoned)\b", re.IGNORECASE | re.MULTILINE)


def plan_path(workdir: Optional[str] = None) -> Optional[Path]:
    """<workdir>/.daedalus/PLAN.md; workdir defaults to TERMINAL_CWD, then cwd."""
    wd = workdir or os.environ.get("TERMINAL_CWD") or ""
    if not wd:
        try:
            wd = os.getcwd()
        except OSError:
            return None
    return Path(wd) / PLAN_DIR / PLAN_NAME


def plan_focus(workdir: Optional[str] = None) -> str:
    """'<title> — <first unchecked step>' of an active plan, else ""."""
    path = plan_path(workdir)
    if path is None or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if _CLOSED_RE.search(text):
        return ""
    title = next((l.lstrip("# ").strip() for l in text.splitlines()
                  if l.startswith("# ")), "")
    step = next((l.split("]", 1)[1].strip() for l in text.splitlines()
                 if l.lstrip().startswith("- [ ]")), "")
    return " — ".join(x for x in (title, step) if x)


def render_plan_block(workdir: Optional[str] = None) -> str:
    """The <active-plan> block for this turn, or "" when there is no plan."""
    path = plan_path(workdir)
    if path is None or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
    except OSError:
        return ""
    if not text:
        return ""
    if _CLOSED_RE.search(text):
        # A finished plan is history, not a job: point at it, don't pin it.
        return (
            f"[Last plan is closed: {path}. For a new multi-step task, "
            "overwrite it with a fresh plan.]"
        )
    if len(text) > PLAN_MAX_CHARS:
        text = (
            text[:PLAN_MAX_CHARS].rstrip()
            + f"\n…[plan truncated at {PLAN_MAX_CHARS} chars — read_file the rest, and shorten it]"
        )
    return (
        f'<active-plan path="{path}" updated="{mtime}">\n{text}\n</active-plan>\n'
        "[Your plan file, re-attached every turn. Continue at the first unchecked "
        "step unless the user changes course. Update the file the moment a step "
        "finishes, fails or changes.]"
    )
