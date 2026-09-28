"""The working plan: <workdir>/.daedalus/PLAN-<task>.md, pinned onto every turn.

The window carries only the last few turns, so a plan the agent wrote five
turns ago is gone unless something puts it back. This does: each turn's API
copy of the user message gets the current file attached. The snapshot is frozen
into that turn's ``api_content`` sidecar, so the prompt-cache prefix stays
byte-stable.

Two agents in one folder used to be fatal: there was exactly one path
(``PLAN.md``), so the second agent's plan overwrote the first one's, and both
then got the survivor pinned on their next turn. Plans are therefore per TASK
(``PLAN-<slug>.md``) and ownership is per SESSION, recorded in
``.daedalus/.owners/<plan>.json`` next to the plan it guards.

Ownership is deliberately a liveness question, not a timestamp: the record
stores the writing pid and the claim dies with the process, so a plan from a
crashed or closed session is adoptable again while a plan a live agent is
working right now is not. When several free plans are ambiguous the harness
refuses to guess and hands the agent an index instead.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import re
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PLAN_DIR = ".daedalus"
PLAN_NAME = "PLAN.md"
OWNER_DIR = ".owners"
PLAN_MAX_CHARS = 4000

# PLAN-<task>.md — the per-task plans. PLAN.md itself is the legacy/default
# name and stays first-class so an existing single-agent setup keeps working.
PLAN_TASK_RE = re.compile(r"^PLAN-[\w][\w.-]*\.md$", re.IGNORECASE)
PLAN_ANY_RE = re.compile(r"^PLAN(?:-[\w][\w.-]*)?\.md$", re.IGNORECASE)
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

logger = logging.getLogger(__name__)

_CLOSED_RE = re.compile(r"^\s*status:\s*(done|abandoned)\b", re.IGNORECASE | re.MULTILINE)


def _workdir(workdir: Optional[str] = None) -> str:
    wd = workdir or os.environ.get("TERMINAL_CWD") or ""
    if not wd:
        try:
            wd = os.getcwd()
        except OSError:
            return ""
    return wd


def plan_dir(workdir: Optional[str] = None) -> Optional[Path]:
    """<workdir>/.daedalus, whether or not it exists yet."""
    wd = _workdir(workdir)
    return Path(wd) / PLAN_DIR if wd else None


def plan_path(workdir: Optional[str] = None) -> Optional[Path]:
    """The legacy single-plan path. Kept: it is the default task plan."""
    d = plan_dir(workdir)
    return (d / PLAN_NAME) if d else None


def slugify_plan_name(title: str, fallback: str = "task") -> str:
    """'Fix boot MCP timeout' -> 'fix-boot-mcp-timeout' (filesystem-safe)."""
    slug = _SLUG_STRIP_RE.sub("-", (title or "").lower()).strip("-")
    if not slug:
        slug = _SLUG_STRIP_RE.sub("-", fallback.lower()).strip("-") or "task"
    return slug[:60].strip("-")


def new_plan_path(title: str, workdir: Optional[str] = None) -> Optional[Path]:
    """A free ``.daedalus/PLAN-<slug>.md`` for a new task. Never clobbers."""
    d = plan_dir(workdir)
    if d is None:
        return None
    slug = slugify_plan_name(title)
    candidate = d / f"PLAN-{slug}.md"
    n = 2
    while candidate.exists():
        candidate = d / f"PLAN-{slug}-{n}.md"
        n += 1
    return candidate


def _owner_file(plan: Path) -> Path:
    return plan.parent / OWNER_DIR / f"{plan.name}.json"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _read_owner(plan: Path) -> dict:
    try:
        raw = _owner_file(plan).read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _owner_is_live(owner: dict, session_id: str) -> bool:
    """True when some OTHER live session holds this plan.

    A claim from another host can never be probed, and a shared filesystem
    between hosts is not a thing here, so it is treated as dead rather than
    blocking the folder forever.
    """
    if not owner:
        return False
    holder = str(owner.get("session_id") or "")
    if holder and holder == (session_id or ""):
        return False
    if str(owner.get("host") or "") != socket.gethostname():
        return False
    return _pid_alive(int(owner.get("pid") or 0))


def _write_owner(plan: Path, session_id: str) -> None:
    """Claim a plan for this session. Per-plan file, so two agents claiming
    two DIFFERENT plans never race on the same bytes."""
    of = _owner_file(plan)
    try:
        of.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "session_id": session_id or "",
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "claimed": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            ensure_ascii=False,
        )
        tmp = of.with_suffix(f".json.tmp{os.getpid()}")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, of)
    except OSError:
        # An unclaimable plan is still usable, it just is not protected.
        logger.debug("plan owner record not written: %s", of, exc_info=True)


def bind_plan(plan: Path, session_id: str) -> bool:
    """Claim ``plan`` for ``session_id``. False when a live session holds it.

    With no session id there is nobody to own the plan, so nothing is written:
    a record with an empty holder would look "alive" to every later session.
    """
    if _owner_is_live(_read_owner(plan), session_id):
        return False
    if not session_id:
        return True
    existing = _read_owner(plan)
    if existing.get("session_id") == session_id and _owner_is_live(existing, session_id):
        return True  # already mine, don't rewrite the record every turn
    _write_owner(plan, session_id)
    return True


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _is_closed(text: str) -> bool:
    return bool(_CLOSED_RE.search(text))


def _title_step(text: str) -> tuple[str, str]:
    title = next((l.lstrip("# ").strip() for l in text.splitlines()
                  if l.startswith("# ")), "")
    step = next((l.split("]", 1)[1].strip() for l in text.splitlines()
                 if l.lstrip().startswith("- [ ]")), "")
    return title, step


@dataclass
class PlanInfo:
    path: Path
    title: str = ""
    step: str = ""
    closed: bool = False
    mtime: float = 0.0
    owner_session: str = ""
    owner_live: bool = False

    @property
    def free(self) -> bool:
        """Nobody live is working this plan."""
        return not self.owner_live


def list_plans(workdir: Optional[str] = None,
               session_id: str = "") -> list[PlanInfo]:
    """Every plan in the folder, newest first, with live ownership resolved."""
    d = plan_dir(workdir)
    if d is None or not d.is_dir():
        return []
    out: list[PlanInfo] = []
    try:
        entries = sorted(d.iterdir())
    except OSError:
        return []
    for p in entries:
        if not p.is_file() or not PLAN_ANY_RE.match(p.name):
            continue
        text = _read_text(p)
        title, step = _title_step(text)
        owner = _read_owner(p)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        out.append(
            PlanInfo(
                path=p,
                title=title or p.stem,
                step=step,
                closed=_is_closed(text),
                mtime=mtime,
                owner_session=str(owner.get("session_id") or ""),
                owner_live=_owner_is_live(owner, session_id),
            )
        )
    out.sort(key=lambda i: i.mtime, reverse=True)
    return out


@dataclass
class PlanResolution:
    """What the harness decided this session's plan is — and why."""
    owned: Optional[Path] = None
    adopted: bool = False
    reason: str = ""
    mine: list[PlanInfo] = field(default_factory=list)
    ambiguous: list[PlanInfo] = field(default_factory=list)
    foreign: list[PlanInfo] = field(default_factory=list)

    @property
    def owns(self) -> bool:
        return self.owned is not None


def resolve_plan(workdir: Optional[str] = None,
                 session_id: Optional[str] = None) -> PlanResolution:
    """Pick this session's plan. Never guesses between several free plans."""
    plans = list_plans(workdir, session_id or "")
    if not plans:
        return PlanResolution(reason="no plans in this folder")

    # 1. What I already hold wins, even if it is closed (that is history).
    for info in plans:
        if info.owner_session and info.owner_session == (session_id or ""):
            return PlanResolution(
                owned=info.path, adopted=True, reason="held by this session",
                foreign=[i for i in plans if not i.free and i.path != info.path])

    # 2. Plans a live other session is working right now are off limits.
    free = [i for i in plans if i.free]
    foreign = [i for i in plans if not i.free]

    open_free = [i for i in free if not i.closed]
    if len(open_free) == 1:
        chosen = open_free[0]
        bind_plan(chosen.path, session_id or "")
        return PlanResolution(owned=chosen.path, adopted=True, reason="only free open plan",
                              foreign=foreign)
    if len(open_free) > 1:
        return PlanResolution(reason="several free open plans — not guessing",
                              ambiguous=open_free, foreign=foreign)
    # Nothing open is free. A single free plan that is closed is still worth
    # naming once, so the agent is told to start a new one instead of silently
    # reopening history.
    if len(free) == 1:
        bind_plan(free[0].path, session_id or "")
        return PlanResolution(owned=free[0].path, adopted=True,
                              reason="only free plan, already closed", foreign=foreign)
    return PlanResolution(reason="no open plan", mine=free, foreign=foreign)


def plan_focus(workdir: Optional[str] = None,
               session_id: Optional[str] = None) -> str:
    """'<title> — <first unchecked step>' of this session's active plan."""
    res = resolve_plan(workdir, session_id)
    if res.owned is None:
        return ""
    text = _read_text(res.owned)
    if _is_closed(text):
        return ""
    title, step = _title_step(text)
    return " — ".join(x for x in (title, step) if x)


def _render_index(res: PlanResolution) -> str:
    lines = ["<plan-index>", "This folder has several free open plans and you own "
             "none of them. Do NOT overwrite one to get started — they belong to "
             "other work. Either bind yourself to the one this task continues:",
             ""]
    for info in res.ambiguous:
        lines.append(f"  {info.path}  —  {info.title}"
                     + (f"  (next: {info.step})" if info.step else ""))
    lines += ["", "…by writing your next step into that file, or start a fresh one",
              "at .daedalus/PLAN-<this-task>.md (the write binds it to you).", ""]
    if res.foreign:
        busy = ", ".join(i.path.name for i in res.foreign)
        lines.append(f"In use by a live agent right now: {busy}. Leave them alone.")
        lines.append("")
    lines.append("</plan-index>")
    return "\n".join(lines)


def render_plan_block(workdir: Optional[str] = None,
                      session_id: Optional[str] = None) -> str:
    """The <active-plan> block for this turn, or "" when there is no plan."""
    res = resolve_plan(workdir, session_id)
    if res.owned is None:
        return _render_index(res) if res.ambiguous else ""

    path = res.owned
    text = _read_text(path).strip()
    if not text:
        return ""
    if _is_closed(text):
        # A finished plan is history, not a job: point at it, don't pin it.
        return (
            f"[Last plan is closed: {path}. For a new multi-step task, "
            f"write .daedalus/PLAN-<task>.md instead — one plan per task.]"
        )
    try:
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
    except OSError:
        mtime = "?"
    if len(text) > PLAN_MAX_CHARS:
        text = (
            text[:PLAN_MAX_CHARS].rstrip()
            + f"\n…[plan truncated at {PLAN_MAX_CHARS} chars — read_file the rest, and shorten it]"
        )
    tail = ""
    if res.foreign:
        busy = ", ".join(i.path.name for i in res.foreign)
        tail = (f"\n[Other agents are working {busy} in this folder. Those plans are "
                f"yours to read, never to write. Your own plan is this file.]")
    return (
        f'<active-plan path="{path}" updated="{mtime}">\n{text}\n</active-plan>\n'
        "[Your plan file, re-attached every turn. Continue at the first unchecked "
        "step unless the user changes course. Update the file the moment a step "
        f"finishes, fails or changes.]{tail}"
    )


def _as_plan_path(path: str, workdir: Optional[str] = None) -> Optional[Path]:
    """The plan a write targets, or None when the write is not plan-related.

    Identity comes from the file itself — a PLAN*.md sitting in a .daedalus
    directory — not from the current working directory. A write arriving over
    an ssh/ssh-style backend resolves to a path the local cwd knows nothing
    about, and a gate that only recognizes its own cwd's plans guards nothing.
    """
    if not path:
        return None
    try:
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = Path(_workdir(workdir) or ".") / target
        target = target.resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    if target.parent.name != PLAN_DIR or not PLAN_ANY_RE.match(target.name):
        return None
    return target


def plan_write_conflict(path: str, session_id: Optional[str] = None,
                        workdir: Optional[str] = None) -> Optional[str]:
    """Gate for write_file/patch. None = write may proceed.

    A write to a plan held by another LIVE session is refused: that write is
    exactly the "agent B overwrote agent A's plan" accident. The first write to
    a free plan binds it to this session, so the claim needs no new tool.
    """
    target = _as_plan_path(path, workdir)
    if target is None:
        return None
    sid = session_id if session_id is not None else current_session_id()
    owner = _read_owner(target)
    if _owner_is_live(owner, sid):
        holder = owner.get("session_id") or "another agent"
        return (
            f"REFUSED: {target} belongs to {holder} (pid {owner.get('pid')}), which is "
            f"alive. Writing it would destroy that agent's plan. Start your own at "
            f".daedalus/PLAN-<your-task>.md, or bind to a free plan by writing a step "
            f"into it."
        )
    if sid:
        _write_owner(target, sid)
    return None


def current_session_id() -> str:
    """This process's Daedalus session id, or '' outside a session."""
    try:
        from gateway.session_context import get_session_env

        return get_session_env("DAEDALUS_SESSION_ID")
    except Exception:
        return os.environ.get("DAEDALUS_SESSION_ID", "") or ""
