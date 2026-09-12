"""Mazemaker memory provider.

Implements the ``MemoryProvider`` ABC. Enable with ``memory.provider: mazemaker``
in config.yaml. Talks to a Mazemaker pod over HTTP; the endpoint defaults to
``http://127.0.0.1:8765`` and is overridden with ``MM_WONDERLAND_URL``.

Two responsibilities:
  * ``sync_turn``  — writes each completed turn to the pod. Fire-and-forget:
    it never blocks the turn.
  * ``prefetch``   — before each model call, asks the pod for context relevant
    to the current query and injects it.

Degrades safely: if the pod is unreachable both paths fail silently and the
agent runs on its normal context window, so a missing pod is a no-op rather
than an error.

Tunables are the module-level constants below; each is documented inline.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from plugins.memory.mazemaker.distiller import distill_stats, distill_turn
from plugins.memory.mazemaker import mission_briefing

logger = logging.getLogger(__name__)

WONDERLAND_URL = os.environ.get("MM_WONDERLAND_URL", "http://127.0.0.1:8765")
TOOL_CALL_URL = WONDERLAND_URL + "/tools/call"
TOOL_LIST_URL = WONDERLAND_URL + "/tools"
MAX_CONTENT_CHARS = 3200

# The pod speaks ONE endpoint — POST /tools/call {"name":..., "arguments":...}.
# Handing the model 34 separate schemas for that one call cost ~16k tokens of
# prompt and blew past the context window; the previous answer was an allowlist
# that deleted 22 tools from the model's awareness entirely. Neither is needed:
# a tool the model cannot see is unusable, but a tool's ARGUMENT SCHEMA is only
# needed at the moment of use. So the model carries every name (~12 tokens each)
# and fetches a schema on demand through DISPATCH_HELP_TOOL.
DISPATCH_TOOL = "mazemaker"
DISPATCH_HELP_TOOL = "mazemaker_help"
# Reached for on nearly every turn: carrying these natively costs their schema
# but saves the hot path a discovery round trip. Set MM_NATIVE_TOOLS="" for a
# pure dispatcher (smallest possible surface, one extra round trip per tool on
# first use); nothing becomes unreachable either way.
NATIVE_TOOLS = tuple(
    n.strip() for n in os.environ.get(
        "MM_NATIVE_TOOLS",
        "mazemaker_recall,mazemaker_remember,mazemaker_think",
    ).split(",") if n.strip()
)
_CATALOGUE_TTL_S = 900.0
_CATALOGUE_DESC_CLIP = 96
_SLOW_TOOLS = frozenset({
    "mazemaker_recall", "mazemaker_recall_multi", "mazemaker_recall_advanced",
    "mazemaker_think", "mazemaker_get", "mazemaker_health", "mazemaker_graph",
    "mazemaker_dream_stats", "mazemaker_diagnose", "mazemaker_afe_facts",
    "mazemaker_synth_lineage", "mazemaker_supersedes_log",
})

SIM_FLOOR = 0.40
RECALL_LIMIT = 6
RECALL_SHOW = 3
RECALL_CLIP = 230
THINK_DEPTH = 2
THINK_SHOW = 5
AFE_SHOW = 4
PREFETCH_TTL = 5.0
MIN_QUERY_LEN = 2

_SOAK_MIN_INTERVAL = 0.1

RESUME_QUERY = "current task ongoing work open goals status"
RESUME_TAIL_FETCH = 24
RESUME_TAIL_LIMIT = 3
RESUME_GOALS_LIMIT = 3
RESUME_GOAL_PREFIXES = ("decision:", "ops:")
_DAEDALUS_SESSION_RE = re.compile(r"^\d{8}_\d{6}_")
RESUME_BLOCK_CHARS = 2400
RESUME_TIMEOUT = 1.8

_FAILED_SPOOL_MAX = 200
_BRAIN_NEGATIVE_TTL_S = 120.0
# A READY verdict expires too. It used to be trusted for the whole session, so
# a pod that wedged mid-session was never re-probed (2026-08-30: three engine
# stalls of ~2h each, every one of them silent).
_BRAIN_POSITIVE_TTL_S = 60.0
# 1.5s declared a merely-busy pod dead — the logs show READY/OFFLINE/READY
# flapping inside 500ms. A refused connection still fails instantly, so a
# longer budget costs nothing on a pod that is actually down.
_BRAIN_PROBE_TIMEOUT_S = 4.0
# Consecutive failed pod calls before the data path is declared wedged.
_WEDGE_FAIL_THRESHOLD = 3
_BRAIN_BOOT_ATTEMPTS = 1
_BRAIN_BOOT_BACKOFF_S = 0.5
MISSION_TTL_S = 72 * 3600
_THINK_RE = re.compile(
    r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE
)
_THINK_OPEN_RE = re.compile(r"<think(?:ing)?>", re.IGNORECASE)


def _scrub_think(text: str) -> str:
    """Remove chain-of-thought from soak-bound text.

    Closed <think>…</think> spans are dropped. An UNCLOSED opener means the
    generation was truncated mid-thought — everything from the first remaining
    opener onward is reasoning and gets cut too (verify pass 2026-08-24: the
    bare-token strip leaked the body). Note this also removes literal
    '<think>' discussion text; that is the accepted tradeoff for keeping
    reasoning out of the memory graph.
    """
    out = _THINK_RE.sub("", text or "")
    m = _THINK_OPEN_RE.search(out)
    if m:
        out = out[: m.start()]
    return out


_FAILED_WRITE_SPOOL: "deque" = deque(maxlen=_FAILED_SPOOL_MAX)
_SPOOL_LOCK = threading.Lock()


def _spool_file_path() -> Optional[Path]:
    try:
        from daedalus_constants import get_daedalus_home
        d = Path(get_daedalus_home()) / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d / "mazemaker_failed_writes.jsonl"
    except Exception:
        return None


def _persist_spool_locked() -> None:
    """Rewrite the on-disk spool to match the in-memory queue.

    2026-09-11: the spool was pure in-memory (a bare deque), so it only ever
    protected against an outage shorter than this process's own lifetime --
    a daedalus restart while the pod was down (exactly what happened during
    tonight's masked-pod stretch) silently dropped everything still queued,
    with no trace it had ever existed. Caller must hold _SPOOL_LOCK; this
    mirrors the deque's contents 1:1 so a crash between calls loses nothing
    already written and never replays something already claimed.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    path = _spool_file_path()
    if path is None:
        return
    try:
        with path.open("w", encoding="utf-8") as f:
            for label, content in _FAILED_WRITE_SPOOL:
                f.write(json.dumps({"label": label, "content": content}) + "\n")
    except Exception:
        pass


def _load_spool_from_disk() -> None:
    """Seed the in-memory spool from a prior process's leftovers, once at import.

    Covers the gap _persist_spool_locked closes: entries written to disk by a
    process that then exited (crash, restart, `daedalus` relaunch) before the
    pod came back. Best-effort, never raises -- a missing or unreadable file
    just means nothing to recover, not a startup failure.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    path = _spool_file_path()
    if path is None or not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    with _SPOOL_LOCK:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                _FAILED_WRITE_SPOOL.append((entry["label"], entry["content"]))
            except Exception:
                continue


_load_spool_from_disk()


def _spool_write(label: str, content: str) -> None:
    with _SPOOL_LOCK:
        _FAILED_WRITE_SPOOL.append((label, content))
        _persist_spool_locked()


def _replay_failed_writes() -> int:
    """Retry spooled writes oldest-first while the pod accepts them.

    Claim-pop discipline: an entry is popped UNDER the lock before its HTTP
    round-trip and requeued at the tail only on failure, so concurrent
    replays can never double-send one item nor pop a never-sent item
    (verify pass 2026-08-24: peek/send/pop race duplicated writes and lost
    one). Any non-exception answer counts as delivered — see _remember. The
    on-disk mirror is rewritten at the same moment an entry is claimed, so a
    crash mid-replay can duplicate at most the one in-flight item, never the
    whole remaining queue.
    """
    replayed = 0
    while True:
        with _SPOOL_LOCK:
            if not _FAILED_WRITE_SPOOL:
                return replayed
            label, content = _FAILED_WRITE_SPOOL.popleft()
            _persist_spool_locked()
        try:
            _tool("mazemaker_remember", {"label": label, "content": content})
        except Exception:
            _spool_write(label, content)
            return replayed
        replayed += 1


_mc_flags_cache = {"ts": 0.0, "vals": (False, False, 1200)}
_mc_flags_override = None


def _mission_control_flags():
    if _mc_flags_override is not None:
        return _mc_flags_override
    now = time.monotonic()
    if now - _mc_flags_cache["ts"] < 30.0:
        return _mc_flags_cache["vals"]
    vals = (False, False, 1200)
    try:
        from daedalus_cli.config import load_config

        soak = ((load_config().get("memory") or {}).get("soak") or {})
        vals = (
            bool(soak.get("distill_enabled")),
            bool(soak.get("mission_briefing")),
            int(soak.get("briefing_chars") or 1200),
        )
    except Exception:
        pass
    _mc_flags_cache.update(ts=now, vals=vals)
    return vals


def _catalogue_cache_path() -> Optional[Path]:
    """On-disk copy of the pod's tool list, so a down pod does not erase it."""
    try:
        from daedalus_constants import get_daedalus_home
        d = Path(get_daedalus_home()) / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d / "mazemaker_tools.json"
    except Exception:
        return None


_catalogue_state: Dict[str, Any] = {"tools": [], "ts": 0.0}
_catalogue_lock = threading.Lock()

# Last-resort tool surface: used only when the pod is unreachable AND the disk
# cache is cold (a fresh install, or a pod that has been down since before the
# cache existed). Without this the model gets ZERO memory tools and cannot even
# say why — it just answers as if it never had a memory. Names are enough to
# dispatch; the three hot tools carry real arguments so the common path works
# unaided. Everything is replaced by the live catalogue the moment the pod answers.
_FALLBACK_ARGS = {
    "mazemaker_recall": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "limit": {"type": "integer", "description": "Max results."},
            "scope": {"type": "string",
                      "description": "Label namespaces, e.g. 'curated'."},
        },
        "required": ["query"],
    },
    "mazemaker_remember": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Memory content."},
            "label": {"type": "string",
                      "description": "Curated label, e.g. 'decision:topic'."},
        },
        "required": ["content"],
    },
    "mazemaker_think": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer", "description": "Starting memory ID."},
            "depth": {"type": "integer", "description": "Traversal depth 1-5."},
        },
        "required": ["memory_id"],
    },
}
_FALLBACK_TOOL_NAMES = (
    "mazemaker_ablate", "mazemaker_afe_facts", "mazemaker_browse",
    "mazemaker_classify_intent", "mazemaker_connections_import",
    "mazemaker_count_by_label_prefix", "mazemaker_delete_by_labels",
    "mazemaker_diagnose", "mazemaker_dream", "mazemaker_dream_afe",
    "mazemaker_dream_config", "mazemaker_dream_control", "mazemaker_dream_dae",
    "mazemaker_dream_insight", "mazemaker_dream_nrem", "mazemaker_dream_rem",
    "mazemaker_dream_stats", "mazemaker_dream_supersedes",
    "mazemaker_dream_synthesize", "mazemaker_get", "mazemaker_graph",
    "mazemaker_health", "mazemaker_list_by_label_prefix", "mazemaker_prune",
    "mazemaker_quota", "mazemaker_rebake", "mazemaker_recall",
    "mazemaker_recall_advanced", "mazemaker_recall_multi", "mazemaker_remember",
    "mazemaker_stats", "mazemaker_supersedes_log", "mazemaker_synth_lineage",
    "mazemaker_think",
)


def _fallback_catalogue() -> List[Dict[str, Any]]:
    return [
        {"name": n,
         "description": ("(schema unavailable — pod unreachable; arguments as "
                         "documented by the tool itself)"),
         "inputSchema": _FALLBACK_ARGS.get(
             n, {"type": "object", "properties": {}, "additionalProperties": True})}
        for n in _FALLBACK_TOOL_NAMES
    ]


def _fetch_catalogue() -> List[Dict[str, Any]]:
    with urllib.request.urlopen(TOOL_LIST_URL, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tools = data if isinstance(data, list) else (
        data.get("tools") or data.get("result") or []
    )
    return [t for t in tools if isinstance(t, dict) and t.get("name")]


def catalogue(refresh: bool = False) -> List[Dict[str, Any]]:
    """The pod's full tool list — every tool, never filtered.

    Cached in memory for ``_CATALOGUE_TTL_S`` and mirrored to disk. The disk
    copy is what keeps the model's tool surface intact while the pod is down:
    before this, an unreachable pod at boot meant zero mazemaker tools for the
    whole session, which looks identical to "the model forgot how to remember".
    """
    now = time.monotonic()
    with _catalogue_lock:
        fresh = _catalogue_state["tools"] and (
            now - _catalogue_state["ts"] < _CATALOGUE_TTL_S
        )
        if fresh and not refresh:
            return list(_catalogue_state["tools"])
    tools: List[Dict[str, Any]] = []
    try:
        tools = _fetch_catalogue()
    except Exception as exc:
        logger.debug("tool catalogue fetch failed (%s) — falling back to disk", exc)
    path = _catalogue_cache_path()
    if tools:
        if path:
            try:
                path.write_text(json.dumps(tools, ensure_ascii=False))
            except Exception:
                pass
    elif path and path.exists():
        try:
            tools = json.loads(path.read_text())
            logger.info(
                "mazemaker tool catalogue served from disk cache (%d tools) — "
                "pod unreachable", len(tools),
            )
        except Exception:
            tools = []
    if not tools:
        # Do NOT cache this — the next call must retry the real pod.
        logger.warning(
            "mazemaker tool catalogue unavailable (pod down, cache cold) — "
            "serving %d built-in tool names so memory stays callable",
            len(_FALLBACK_TOOL_NAMES),
        )
        return _fallback_catalogue()
    with _catalogue_lock:
        _catalogue_state.update(tools=tools, ts=now)
        return list(tools)


def _fmt_duration(seconds: float) -> str:
    """Human-readable outage length, for log lines a person has to read fast."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"
    return f"{seconds / 3600:.1f}h"


class _PodHealth:
    """Wedge detector driven by real call outcomes, not by ``/health``.

    The wonderland front answers ``GET /health`` out of its own process state —
    it reports the configured upstream URL, session count and vault key, and
    never touches the engine or Postgres. It therefore returns 200 in ~20ms
    straight through an engine stall, which is how three multi-hour outages on
    2026-08-30 went unnoticed.

    Whether real calls are completing is the only honest signal, so that is
    what this counts. Every pod call in this module funnels through :func:`_tool`,
    so instrumenting that one choke point covers the whole data path: recall,
    soak, prefetch, think, browse and the readiness probe itself.

    A run of ``_WEDGE_FAIL_THRESHOLD`` consecutive failures declares a wedge and
    logs it ONCE at ERROR; recovery logs once with the measured outage duration.
    Per-call noise stays at WARNING so the two ERROR lines mean exactly one
    thing each.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._wedged_since: Optional[float] = None
        self._last_ok: Optional[float] = None
        self._last_error = ""
        self._episodes = 0

    def record_ok(self, name: str) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._last_ok = time.monotonic()
            wedged_since = self._wedged_since
            self._wedged_since = None
        if wedged_since is not None:
            logger.error(
                "MEMORY RECOVERED — mazemaker pod completed %s after %s wedged",
                name, _fmt_duration(time.monotonic() - wedged_since),
            )

    def record_fail(self, name: str, exc: BaseException) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            failures = self._consecutive_failures
            detail = self._last_error
            newly_wedged = (
                failures >= _WEDGE_FAIL_THRESHOLD and self._wedged_since is None
            )
            if newly_wedged:
                self._wedged_since = time.monotonic()
                self._episodes += 1
        if newly_wedged:
            logger.error(
                "MEMORY DEGRADED — mazemaker pod failed %d consecutive calls "
                "(last: %s on %s). Recall and soak are dead until it answers. "
                "GET /health cannot see this: it reports the front process only.",
                failures, detail, name,
            )
            _attempt_pod_recovery()
        else:
            logger.warning(
                "mazemaker call %s failed (%d in a row): %s",
                name, failures, detail,
            )

    def wedged_for(self) -> Optional[float]:
        """Seconds since the wedge was declared, or None if calls are landing."""
        with self._lock:
            if self._wedged_since is None:
                return None
            return time.monotonic() - self._wedged_since

    def is_wedged(self) -> bool:
        return self.wedged_for() is not None

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            down = (
                None if self._wedged_since is None
                else time.monotonic() - self._wedged_since
            )
            since_ok = (
                None if self._last_ok is None
                else time.monotonic() - self._last_ok
            )
            return {
                "wedged": self._wedged_since is not None,
                "down_for_seconds": None if down is None else round(down, 1),
                "consecutive_failures": self._consecutive_failures,
                "seconds_since_last_ok": (
                    None if since_ok is None else round(since_ok, 1)
                ),
                "last_error": self._last_error,
                "episodes": self._episodes,
            }


_POD_HEALTH = _PodHealth()


_OFFLINE_BACKOFF_S = (120.0, 300.0, 600.0, 900.0)


_RECOVERY_UNIT = os.environ.get("MM_RECOVERY_UNIT", "mazemaker-wonderland.service")
_RECOVERY_MIN_INTERVAL_S = float(os.environ.get("MM_RECOVERY_MIN_INTERVAL_S", "600"))
_RECOVERY_MAX_ATTEMPTS = int(os.environ.get("MM_RECOVERY_MAX_ATTEMPTS", "3"))
_recovery_lock = threading.Lock()
_recovery_state = {"last": 0.0, "attempts": 0}


def _attempt_pod_recovery() -> bool:
    """Restart the pod's front process once a wedge is confirmed.

    A wedged pod is invisible to every supervisor it has. The container stays
    Up, the unit stays active, the socket stays open, and the front keeps
    accepting connections it never finishes -- observed 2026-09-03, four hours
    of silence with everything reporting healthy. Nothing recovers from that on
    its own, so the layer that can actually tell (this one, because it is the
    thing making the calls) asks systemd for a restart.

    Deliberately conservative: at most _RECOVERY_MAX_ATTEMPTS restarts, never
    closer together than _RECOVERY_MIN_INTERVAL_S, and only when the harness
    can see a user systemd. Set MM_RECOVERY_UNIT="" to switch it off.
    """
    if not _RECOVERY_UNIT:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        # A unit test exercising the wedge detector must not restart a system
        # service. This one did: the suite drove record_fail past the threshold
        # and the recovery brought a deliberately stopped pod back up
        # (2026-09-03). Detection is what the tests are for; the side effect is
        # not theirs to have.
        logger.debug("pod recovery suppressed under pytest")
        return False

    import shutil as _shutil
    import subprocess as _subprocess

    # The pytest guard above caught the test-suite instance of this; it did
    # not catch the real one. `mazemaker off` stops this exact unit on
    # purpose (systemctl --job-mode=replace-irreversibly, specifically so a
    # Restart=on-failure policy cannot requeue it) -- and this function,
    # seeing "unreachable", restarted it right back. Observed live
    # 2026-09-11: the operator ran `mazemaker off`, this fired on the next
    # failed call, and the pod came back up regardless. A unit systemd
    # cleanly stopped reports "inactive", not "active" or "failed" -- only
    # the wedge this function exists for (container Up, unit active, socket
    # open, front hung -- 2026-09-03) or a genuine crash looks like either of
    # those while unreachable. Check state before touching anything.
    _systemctl_probe = _shutil.which("systemctl")
    if _systemctl_probe:
        try:
            _state = _subprocess.run(
                [_systemctl_probe, "--user", "is-active", _RECOVERY_UNIT],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except Exception:
            _state = ""
        if _state == "inactive":
            logger.info(
                "pod recovery skipped — %s is cleanly inactive (deliberately "
                "stopped, e.g. `mazemaker off`), not restarting it",
                _RECOVERY_UNIT,
            )
            return False

    now = time.monotonic()
    with _recovery_lock:
        since = now - _recovery_state["last"]
        if _recovery_state["last"] and since < _RECOVERY_MIN_INTERVAL_S:
            logger.info(
                "pod recovery skipped — last attempt %.0fs ago, waiting %.0fs between tries",
                since, _RECOVERY_MIN_INTERVAL_S,
            )
            return False
        if _recovery_state["attempts"] >= _RECOVERY_MAX_ATTEMPTS:
            logger.error(
                "pod recovery giving up after %d attempts on %s — restarting it "
                "is not fixing whatever is wrong. Look at the pod by hand.",
                _recovery_state["attempts"], _RECOVERY_UNIT,
            )
            return False
        _recovery_state["last"] = now
        _recovery_state["attempts"] += 1
        attempt = _recovery_state["attempts"]

    import shutil
    import subprocess

    systemctl = shutil.which("systemctl")
    if not systemctl:
        logger.warning("pod recovery unavailable — no systemctl on PATH")
        return False

    logger.error(
        "attempting pod recovery (%d/%d): systemctl --user restart %s",
        attempt, _RECOVERY_MAX_ATTEMPTS, _RECOVERY_UNIT,
    )
    try:
        proc = subprocess.run(
            [systemctl, "--user", "restart", _RECOVERY_UNIT],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:
        logger.error("pod recovery failed to run: %s", exc)
        return False
    if proc.returncode != 0:
        logger.error(
            "pod recovery restart returned %d: %s",
            proc.returncode, (proc.stderr or "").strip()[:200],
        )
        return False
    logger.error("pod recovery: %s restarted — next call decides whether it took",
                 _RECOVERY_UNIT)
    return True


class _Breaker:
    def __init__(self) -> None:
        self._open_since: Optional[float] = None
        self._level = 0
        self._suppressed = 0

    def trip(self) -> None:
        if self._open_since is None:
            self._open_since = time.monotonic()
            logger.warning(
                "mazemaker pod unreachable — going cold. No further calls will "
                "be attempted for %.0fs; recall, soak and prefetch are no-ops "
                "until it answers.", _OFFLINE_BACKOFF_S[0])

    def reset(self) -> None:
        if self._open_since is not None:
            logger.info("mazemaker pod answering again after %d suppressed call(s)",
                        self._suppressed)
        self._open_since = None
        self._level = 0
        self._suppressed = 0

    def is_open(self) -> bool:
        if self._open_since is None:
            return False
        wait = _OFFLINE_BACKOFF_S[min(self._level, len(_OFFLINE_BACKOFF_S) - 1)]
        if time.monotonic() - self._open_since >= wait:
            self._open_since = time.monotonic()
            self._level += 1
            return False
        self._suppressed += 1
        return True

    def snapshot(self) -> Dict[str, Any]:
        if self._open_since is None:
            return {"open": False}
        return {
            "open": True,
            "for_s": round(time.monotonic() - self._open_since, 1),
            "suppressed": self._suppressed,
            "next_probe_s": _OFFLINE_BACKOFF_S[min(self._level, len(_OFFLINE_BACKOFF_S) - 1)],
        }


_BREAKER = _Breaker()


class PodOffline(RuntimeError):
    pass


def _tool(name: str, arguments: dict, timeout: float = 8.0) -> Any:
    """Call a wonderland tool and return its ``result``. Raises on failure.

    Also the single instrumentation point for :class:`_PodHealth` — see there
    for why call outcomes, and not ``/health``, are what we trust.
    """
    if _BREAKER.is_open():
        raise PodOffline(f"mazemaker pod is cold — {name} not attempted")
    body = json.dumps({"name": name, "arguments": arguments}).encode()
    req = urllib.request.Request(
        TOOL_CALL_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # A 4xx means the engine answered and rejected the request — bad args,
        # not a wedge. Counting those would declare an outage over a typo.
        if exc.code >= 500:
            _POD_HEALTH.record_fail(name, exc)
        else:
            _POD_HEALTH.record_ok(name)
        raise
    except Exception as exc:
        _POD_HEALTH.record_fail(name, exc)
        if _POD_HEALTH.is_wedged():
            _BREAKER.trip()
        raise
    _POD_HEALTH.record_ok(name)
    _BREAKER.reset()
    result = data.get("result") if isinstance(data, dict) else None
    return result


def _remember(label: str, content: str) -> Optional[int]:
    """POST a mazemaker_remember call to the local wonderland pod.

    Failures are WARN-visible and spooled for replay instead of vanishing —
    drop-on-error was permanent amnesia for those turns (2026-08-24 audit).
    """
    try:
        res = _tool("mazemaker_remember", {"label": label, "content": content})
        if isinstance(res, dict):
            return res.get("id")
        logger.info(
            "mazemaker_remember odd payload (%s) — assuming delivered",
            str(res)[:120],
        )
        return None
    except Exception as e:
        logger.warning("mazemaker_remember failed (%s) — spooled for retry", e)
        _spool_write(label, str(content))
        return None


def _turn_sort_key(label: str) -> int:
    """Order soaked turns by the hex timestamp their label ends with."""
    tail = label.rsplit(":", 1)[-1] if label else ""
    try:
        return int(tail, 16)
    except ValueError:
        return 0


_BROWSE_MAX_LIMIT = 200
_RESTORE_MAX_TURNS = 20


def _split_soaked_turn(content: str) -> tuple:
    """Split a soaked turn back into (user, assistant)."""
    if not content:
        return "", ""
    body = content
    marker = "=== USER ==="
    if marker in body:
        body = body.split(marker, 1)[1]
    user, assistant = body, ""
    if "=== ASSISTANT ===" in body:
        user, assistant = body.split("=== ASSISTANT ===", 1)
    user = user.strip()
    assistant = assistant.replace("\n…[truncated]", "").strip()
    return user, assistant


class MazemakerMemoryProvider(MemoryProvider):
    """Soak + on-demand recall against the local mazemaker pod."""

    def __init__(self, **kwargs) -> None:
        self._session_id = ""
        self._turn_count = 0
        self._prefetch_cache: Dict[str, tuple] = {}
        self._cache_lock = threading.Lock()
        self._last_soak_ts = 0.0
        self._resume_block = ""
        self._brain_ready: Optional[bool] = None
        self._brain_checked_at: float = 0.0
        self._mission_key: Optional[str] = None
        self._dcfg_cache: Optional[dict] = None
        self._dcfg_ts: float = 0.0

    def _ensure_mission_key(self) -> str:
        if self._mission_key:
            return self._mission_key
        try:
            res = _tool("mazemaker_browse", {"label_prefix": "mission:", "limit": 5})
            rows = (res.get("memories") or []) if isinstance(res, dict) else (res or [])
            now = time.time()
            for r in rows:
                label = str(r.get("label", ""))
                key = label[len("mission:"):]
                created = float(r.get("created_at") or 0)
                if key and created and now - created < MISSION_TTL_S:
                    self._mission_key = key
                    return key
        except Exception:
            pass
        import secrets as _secrets

        self._mission_key = _secrets.token_hex(4)
        try:
            _remember(
                f"mission:{self._mission_key}",
                f"mission namespace opened "
                f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            )
        except Exception:
            pass
        return self._mission_key

    @staticmethod
    def _load_delegation_config() -> dict:
        """Read the ``delegation`` config block the same way delegate_tool does.

        Used by the route-out distiller, which summarises a finished turn — not
        to be confused with routing tool CALLS through a model, which this
        provider no longer does at all.
        """
        try:
            from cli import CLI_CONFIG
            dcfg = CLI_CONFIG.get("delegation") or {}
        except Exception:
            dcfg = {}
        if not dcfg:
            try:
                from daedalus_cli.config import load_config
                dcfg = load_config().get("delegation") or {}
            except Exception:
                dcfg = {}
        return dcfg or {}

    def _delegation_cached(self, ttl: float = 300.0) -> dict:
        """Delegation config with a TTL cache — the distiller path runs per
        turn; re-resolving full config each time was measured as waste."""
        now = time.monotonic()
        if self._dcfg_cache is None or now - self._dcfg_ts > ttl:
            try:
                self._dcfg_cache = self._load_delegation_config()
            except Exception:
                self._dcfg_cache = {}
            self._dcfg_ts = now
        return self._dcfg_cache


    @property
    def name(self) -> str:
        return "mazemaker"

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id or ""
        self._turn_count = 0
        self._resume_block = ""
        for attempt in range(_BRAIN_BOOT_ATTEMPTS):
            self._brain_ready = self.brain_ready(refresh=True)
            if self._brain_ready:
                break
            if attempt < _BRAIN_BOOT_ATTEMPTS - 1:
                time.sleep(_BRAIN_BOOT_BACKOFF_S * (attempt + 1))
        logger.info(
            "mazemaker provider: brain %s (session=%s)",
            "READY" if self._brain_ready else "OFFLINE", self._session_id,
        )
        if not self._brain_ready:
            logger.warning(
                "mazemaker pod unreachable at init — soak/prefetch degrade to "
                "no-ops until it answers (auto re-probe every %.0fs)",
                _BRAIN_NEGATIVE_TTL_S,
            )
        if _FAILED_WRITE_SPOOL:
            try:
                _replay_failed_writes()
            except Exception:
                pass

    def brain_ready(self, refresh: bool = False) -> bool:
        """Readiness probe for the mazemaker brain.

        Probes ``mazemaker_stats``, which runs through the front to the engine
        and the store. The front's own ``GET /health`` is not used and must not
        be: it answers from process state and stays green through an engine
        wedge.

        BOTH verdicts expire. A READY verdict was previously trusted for the
        rest of the session, so a pod that wedged after a good boot was never
        re-probed and the provider kept reporting itself available while every
        call failed — three silent multi-hour outages on 2026-08-30. READY now
        expires after ``_BRAIN_POSITIVE_TTL_S``, OFFLINE after
        ``_BRAIN_NEGATIVE_TTL_S``.

        A live wedge on the data path outranks any cached verdict, but is still
        re-probed on the negative TTL so an outage can end on its own.
        """
        now = time.monotonic()
        if not refresh and self._brain_ready is not None:
            age = now - self._brain_checked_at
            if _POD_HEALTH.is_wedged():
                if age < _BRAIN_NEGATIVE_TTL_S:
                    self._brain_ready = False
                    return False
            else:
                ttl = (
                    _BRAIN_POSITIVE_TTL_S if self._brain_ready
                    else _BRAIN_NEGATIVE_TTL_S
                )
                if age < ttl:
                    return self._brain_ready
        try:
            res = _tool("mazemaker_stats", {}, timeout=_BRAIN_PROBE_TIMEOUT_S)
            # A wedged engine can still return a shaped-but-empty payload;
            # require a real count before calling the brain ready.
            self._brain_ready = (
                isinstance(res, dict) and isinstance(res.get("memories"), int)
            )
        except Exception:
            self._brain_ready = False
        self._brain_checked_at = now
        return self._brain_ready

    def is_available(self) -> bool:
        return self.brain_ready()

    def memory_status(self) -> Dict[str, Any]:
        """Current memory health, for callers that need to report it."""
        status = _POD_HEALTH.snapshot()
        status["brain_ready"] = bool(self._brain_ready)
        return status

    def _degraded_banner(self) -> str:
        """Context line injected while the pod is wedged.

        Silence is what made the outages expensive: with no recall block the
        model answered from nothing and sounded exactly as confident as usual.
        """
        down = _POD_HEALTH.wedged_for() or 0.0
        return (
            "[memory unavailable] The mazemaker pod has not completed a call "
            f"for {_fmt_duration(down)}, so no recall context could be loaded "
            "for this turn. If the answer depends on remembered context, say "
            "that memory is down — do not present an unremembered answer as a "
            "remembered one."
        )

    def _degraded_payload(self, tool_name: str, detail: str) -> Dict[str, Any]:
        """Tool-result body for a failed pod call, carrying the outage state."""
        status = _POD_HEALTH.snapshot()
        message = f"mazemaker tool {tool_name} failed: {detail}"
        if status["wedged"]:
            message = (
                "MEMORY DEGRADED — the mazemaker pod has not completed a call "
                f"for {_fmt_duration(status['down_for_seconds'] or 0.0)} "
                f"({status['consecutive_failures']} consecutive failures). "
                f"{message}. Tell the user memory is down rather than "
                "answering as if the corpus were empty."
            )
        return {"error": message, "memory_status": status}

    def get_config_schema(self) -> List[Dict[str, Any]]:
        """Zero-config provider — no setup prompts needed."""
        return []


# Only harness notices, and only when the message LEADS with one. "No
# response was needed here, so I moved on to the shader" is an answer;
# matching a bare "no response" anywhere would have dropped it.
_NON_ANSWER_RE = re.compile(
    r"^\s*(operation interrupted\b|\[?request interrupted\b|"
    r"interrupted by user\b)", re.I)


def _is_non_answer(text: str) -> bool:
    """True when this turn produced no answer worth remembering.

    These are harness notices, not content: an interrupt, a retry, a wait
    that timed out. Soaking them fills the graph with rows that match a
    recall and say nothing, which is how a session gets its own question
    handed back to it and starts over from zero.
    """
    if not text or not text.strip():
        return True
    return bool(_NON_ANSWER_RE.match(text.strip()))


    def soak_reasoning(self, text: str, *, session_id: str = "",
                       spill_path: str = "") -> None:
        """Keep a reasoning chain that aged out of the context window.

        Tools and their output are deliberately not soaked: that is working
        material, it belongs in the project's own workpath, and a semantic
        graph full of build logs is a graph that cannot find anything. The
        thinking is the opposite -- it is what accumulates over days and
        weeks of work, and the one thing a later session cannot rebuild by
        reading the files.

        The full block stays in the spill file; what goes in the graph is
        the text plus a pointer to it. mazemaker is the signpost, not the
        warehouse -- so a long chain is searchable here and readable in full
        from the path, rather than half-stored in both places.
        """
        body = _scrub_think((text or "")).strip()
        if not body:
            return
        sid = session_id or self._session_id
        ts = int(time.time())
        label = f"auto:reasoning:{sid}:{ts:x}"
        head = (f"session:{sid} @ "
                f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
        if spill_path:
            head += f"\nfull text: {spill_path}"
        if len(body) > MAX_CONTENT_CHARS:
            body = body[:MAX_CONTENT_CHARS] + "\n…[truncated — read the full text at the path above]"
        _remember(label, f"{head}\n\n=== REASONING ===\n{body}")

    def sync_turn(self, user: str, asst: str, **kwargs) -> None:
        """SOAK this turn into the mazemaker pod (fire-and-forget).

        Called by the MemoryManager after every assistant response.
        Writes label ``auto:turn:<session_id>:<ts>`` so the full history
        lives in the graph — recallable on demand, not carried in context.
        """
        self._turn_count += 1
        now = time.time()
        if _FAILED_WRITE_SPOOL:
            try:
                _replay_failed_writes()
            except Exception:
                pass
        if now - self._last_soak_ts < _SOAK_MIN_INTERVAL:
            logger.debug("soak rate-limited this turn — turn skipped")
            return
        self._last_soak_ts = now

        clean_asst = _scrub_think((asst or "")[:MAX_CONTENT_CHARS]).strip()
        if _is_non_answer(clean_asst):
            # Nothing was produced, so there is nothing worth recalling. The
            # old behaviour stored the user's question with
            # "Operation interrupted: waiting for model response (43.3s
            # elapsed)" as the assistant side -- 236 to 440 characters that
            # carry no information at all, yet score as a hit on recall and
            # hand a future session its own question back. That is worse than
            # a miss: a miss tells the agent to look elsewhere.
            logger.debug("soak skipped: assistant produced no answer this turn")
            return

        ts = int(now)
        label = f"auto:turn:{self._session_id}:{ts:x}"
        content = (
            f"session:{self._session_id} @ "
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n"
            f"=== USER ===\n{user}\n\n"
            f"=== ASSISTANT ===\n{clean_asst}"
        )
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n…[truncated]"
        _remember(label, content)

        distill_on, _, _ = _mission_control_flags()
        if distill_on and user and asst:
            try:
                d = self._delegation_cached()
                base_url = str(d.get("base_url") or "").strip()
                if base_url:
                    writes = distill_turn(
                        user, clean_asst,
                        base_url=base_url,
                        api_key=str(d.get("api_key") or "").strip(),
                        model=str(d.get("model") or "local-distiller"),
                    )
                    if writes:
                        key = self._ensure_mission_key()
                        for i, (prefix, item) in enumerate(writes):
                            _remember(f"{prefix}{key}:{ts:x}:{i}", item)
                        mission_briefing.invalidate(self._session_id)
                        logger.info(
                            "route-out distilled %d item(s) from turn %d",
                            len(writes), self._turn_count,
                        )
            except Exception as exc:
                logger.debug("route-out distillation skipped: %s", exc)

    def prefetch(self, query: str, *, session_id: str = "", **kwargs) -> str:
        """Inject the recall hit PLUS its graph neighbours and AFE facts.

        Returns plain text (the MemoryManager wraps it in <memory-context>).
        Cached per query for PREFETCH_TTL so the repeated API calls inside
        one agent turn don't re-hit the pod. Never raises — any failure
        degrades to fewer layers or an empty string.
        """
        if not query or len(query.strip()) < MIN_QUERY_LEN:
            return ""
        if _POD_HEALTH.is_wedged():
            # Not cached: the banner has to track the live outage duration and
            # disappear the moment the pod answers again.
            return self._degraded_banner()
        q = query.strip()
        cache_key = f"{session_id or ''}|{q}"
        now = time.time()
        with self._cache_lock:
            cached = self._prefetch_cache.get(cache_key)
            if cached and now - cached[0] < PREFETCH_TTL:
                return cached[1]

        block = self._build_enriched_context(q)

        _, briefing_on, bchars = _mission_control_flags()
        if briefing_on and session_id:
            brief = mission_briefing.cached_briefing(
                session_id, self._browse_rows, max_chars=bchars,
                label_contains=self._ensure_mission_key(),
            )
            if brief:
                block = f"{brief}\n\n{block}" if block else brief

        with self._cache_lock:
            self._prefetch_cache[cache_key] = (now, block)
        return block

    def _browse_rows(self, label_prefix: str, limit: int):
        """Browse rows by label prefix (newest-first); raises through."""
        res = _tool("mazemaker_browse",
                    {"label_prefix": label_prefix, "limit": limit})
        if isinstance(res, dict):
            return res.get("memories") or []
        if isinstance(res, list):
            return res
        return []

    def queue_prefetch(self, query: str, *, session_id: str = "", **kwargs) -> None:
        """Prefetch now; the cache makes the loop's later prefetch calls free."""
        self.prefetch(query, session_id=session_id)

    def history_pointer(self, session_id: str = "") -> str:
        """Return a compact pointer to this conversation's soaked history.

        The full transcript lives in the pod as ``auto:turn:<session>:*``
        memories (see sync_turn). Instead of carrying it in context, the agent
        ships this pointer — the model knows the history is recallable on
        demand via mazemaker_get / mazemaker_recall / the pod's tools.

        This is the contract that makes trim-and-recall safe, so it must not
        claim the safety net exists when it doesn't: sync_turn's writes funnel
        through _tool(), the same choke point _PodHealth watches, so a wedged
        (or deliberately stopped, e.g. `mazemaker off`) pod is already visible
        here via is_wedged() -- same signal prefetch() already checks below.
        While wedged, sync_turn's writes are landing in the local retry spool
        (_spool_write), not the graph, so mazemaker_get/mazemaker_recall
        cannot see this session's turns until the pod is back and the spool
        replays. Observed live 2026-09-11: this returned the "safely stored"
        pointer for an entire session while the pod was masked off on purpose.
        """
        sid = session_id or self._session_id
        if not sid:
            return ""
        if _POD_HEALTH.is_wedged():
            down = _POD_HEALTH.wedged_for() or 0.0
            return (
                f"[memory unavailable] The mazemaker pod has not completed a call "
                f"for {_fmt_duration(down)}. This session's turns are queued in a "
                f"local retry spool, NOT stored in mazemaker yet -- mazemaker_get "
                f"and mazemaker_recall cannot see anything from this session until "
                f"the pod is back up and the spool replays. Do not tell the user "
                f"older turns are safely archived; if something outside the "
                f"current context window is needed, say memory is down instead of "
                f"answering as if it were recallable."
            )
        return (
            f"Full conversation history for this session ({sid}) is stored in "
            f"mazemaker as auto:turn:{sid}:* memories. It is NOT carried in "
            f"context — recall specific turns with mazemaker_get, or ask the pod "
            f"via mazemaker_recall when you need something from earlier in this "
            f"conversation."
        )

    def on_session_switch(
        self, new_session_id: str, *, parent_session_id: str = "", reset: bool = False, **kwargs
    ) -> None:
        """Update internal session_id when compression or /resume rotates it."""
        self._session_id = new_session_id or ""
        if reset:
            self._resume_block = ""
        with self._cache_lock:
            self._prefetch_cache.clear()

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """Archive conversation turns before compression discards them."""
        try:
            ts = int(time.time())
            label = f"auto:compression:{ts:x}"
            content = (
                f"Compression archive at "
                f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n"
            )
            turn_pairs = []
            for msg in reversed(messages):
                role = msg.get("role", "")
                body = msg.get("content", "") or ""
                if role == "assistant":
                    body = _scrub_think(body).strip()
                if role in ("user", "assistant") and body:
                    turn_pairs.insert(0, f"=== {role.upper()} ===\n{body}")
                if len(turn_pairs) >= 12:
                    break
            if turn_pairs:
                content += "\n\n".join(turn_pairs)
            _remember(label, content[:MAX_CONTENT_CHARS])
            return f"[{len(messages)} messages archived to mazemaker before compression]"
        except Exception as e:
            logger.warning("on_pre_compress archive failed: %s", e)
            return ""


    def _previous_session_turns(self, exclude: set) -> dict:
        try:
            rows = self._browse_rows("auto:turn:", _BROWSE_MAX_LIMIT)
        except Exception as exc:
            logger.warning("previous-session lookup failed (%s)", exc)
            return {}
        groups = {}
        for row in rows or []:
            label = str(row.get("label") or "")
            if not label.startswith("auto:turn:"):
                continue
            sid = label[len("auto:turn:"):].rsplit(":", 1)[0]
            if sid in exclude or not _DAEDALUS_SESSION_RE.match(sid):
                continue
            groups.setdefault(sid, {})[label] = str(row.get("content") or "")
        if not groups:
            return {}
        newest = max(
            groups,
            key=lambda sid: max(_turn_sort_key(l) for l in groups[sid]),
        )
        logger.info("restoring from the previous session in the graph: %s", newest)
        return groups[newest]

    def restore_conversation(self, session_id: str = "", ancestors=(),
                             limit: int = 0, allow_previous: bool = True) -> list:
        ids = [session_id or self._session_id or ""]
        ids.extend(str(a) for a in (ancestors or ()) if a)
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return []

        collected = {}
        for sid in ids:
            for attempt in (limit if limit > 0 else _BROWSE_MAX_LIMIT, _BROWSE_MAX_LIMIT, 50):
                if attempt <= 0:
                    continue
                try:
                    rows = self._browse_rows(f"auto:turn:{sid}", attempt)
                except Exception as exc:
                    logger.warning(
                        "restore_conversation: browse(limit=%d) failed for %s (%s)",
                        attempt, sid, exc,
                    )
                    continue
                for row in rows or []:
                    label = str(row.get("label") or "")
                    if label.startswith("auto:turn:"):
                        collected[label] = str(row.get("content") or "")
                break

        if not collected and allow_previous:
            collected = self._previous_session_turns(set(ids))

        turns = []
        for label, content in collected.items():
            user, assistant = _split_soaked_turn(content)
            if not user and not assistant:
                continue
            turns.append((_turn_sort_key(label), user, assistant))

        turns.sort(key=lambda t: t[0])
        if len(turns) > _RESTORE_MAX_TURNS:
            logger.info("restore trimmed to the newest %d of %d turns",
                        _RESTORE_MAX_TURNS, len(turns))
            turns = turns[-_RESTORE_MAX_TURNS:]
        messages = []
        for _key, user, assistant in turns:
            if user:
                messages.append({"role": "user", "content": user})
            if assistant:
                messages.append({"role": "assistant", "content": assistant})
        return messages

    def continuity_context(self, session_id: str = "") -> str:
        """Return the cross-session resume block (previous tail + open goals)."""
        return self.session_resume_context(session_id=session_id)

    def session_resume_context(self, session_id: str = "") -> str:
        """Compose the resume block once per session; cache the result.

        Tail: the last few soaked ``auto:turn`` rows (this session's own on
        continuation, else the most recent other session). Goals: curated
        status/decision/project/ops/fact memories about the current task.
        Hard-clipped to RESUME_BLOCK_CHARS. Never raises — pod down yields "".
        """
        if self._resume_block:
            return self._resume_block
        if self._brain_ready is False:
            self.brain_ready()
        block = self._compose_resume(session_id or self._session_id or "")
        self._resume_block = block
        return block

    def _compose_resume(self, session_id: str) -> str:
        parts = []

        tail_lines = []
        try:
            res = _tool("mazemaker_browse", {
                "label_prefix": "auto:turn:", "limit": RESUME_TAIL_FETCH,
            }, timeout=RESUME_TIMEOUT)
            rows = []
            if isinstance(res, dict):
                rows = res.get("memories") or res.get("result") or []
            elif isinstance(res, list):
                rows = res
            turns = []
            for m in rows:
                label = str(m.get("label", "") or "")
                content = str(m.get("content", "") or "")
                if not label.startswith("auto:turn:"):
                    continue
                if "Review the conversation above" in content:
                    continue
                _sid = label[len("auto:turn:"):].rsplit(":", 1)[0]
                if not _DAEDALUS_SESSION_RE.match(_sid):
                    continue
                turns.append((_sid, content))
            if turns:
                for _s, c in turns[:RESUME_TAIL_LIMIT]:
                    body = c.split("\n", 1)[1] if "\n" in c else c
                    body = self._clip(self._clean(body), RECALL_CLIP)
                    if body:
                        tail_lines.append(f"[session {_s[:16]}] {body}")
        except Exception as e:
            logger.debug("session_resume tail failed: %s", e)

        if not tail_lines:
            return ""

        parts.append("Previous session — last turns (recalled from mazemaker):")
        parts.extend(tail_lines)

        goal_lines = []
        try:
            seen = set()
            for prefix in RESUME_GOAL_PREFIXES:
                res = _tool("mazemaker_browse", {
                    "label_prefix": prefix, "limit": RESUME_GOALS_LIMIT + 2,
                }, timeout=RESUME_TIMEOUT)
                rows = []
                if isinstance(res, dict):
                    rows = res.get("memories") or res.get("result") or []
                elif isinstance(res, list):
                    rows = res
                for m in rows:
                    if len(goal_lines) >= RESUME_GOALS_LIMIT:
                        break
                    label = str(m.get("label", "") or "")
                    body = self._clip(self._clean(m.get("content", "")), RECALL_CLIP)
                    if body and label not in seen:
                        seen.add(label)
                        goal_lines.append(f"[{label}] {body}")
                if len(goal_lines) >= RESUME_GOALS_LIMIT:
                    break
        except Exception as e:
            logger.debug("session_resume goals failed: %s", e)

        if goal_lines:
            parts.append("Open work / ongoing goals (curated from mazemaker):")
            parts.extend(goal_lines)

        parts.append(
            "[Prior-session context only — not new user input. Continue the work "
            "above; full history is recallable on demand via mazemaker_recall / "
            "mazemaker_get.]"
        )
        block = "\n".join(parts)
        return block[:RESUME_BLOCK_CHARS]

    @staticmethod
    def _one_line(text: str, limit: int = _CATALOGUE_DESC_CLIP) -> str:
        """First sentence of a tool description, clipped — this is what the
        model reads to know a tool exists and roughly what it does."""
        flat = " ".join(str(text or "").split())
        head = flat.split(". ")[0].strip().rstrip(".")
        return head[: limit - 1] + "…" if len(head) > limit else head

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return the pod surface as a dispatcher plus a few native tools.

        Every pod tool stays reachable and every pod tool stays VISIBLE — the
        dispatcher's enum and description list all of them by name. What is no
        longer shipped is 30-odd full argument schemas the model does not need
        until the moment it calls one; ``mazemaker_help(tool)`` returns those
        on demand. Measured: ~16k tokens of schema down to a few hundred, with
        nothing removed from the model's reach.
        """
        tools = catalogue()
        if not tools:
            logger.debug("no mazemaker tool catalogue available (pod down, no cache)")
            return []

        by_name = {t["name"]: t for t in tools}
        schemas: List[Dict[str, Any]] = []
        for name in NATIVE_TOOLS:
            t = by_name.get(name)
            if t:
                schemas.append({
                    "name": name,
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {
                        "type": "object", "properties": {},
                    }),
                })

        names = sorted(by_name)
        listing = "\n".join(
            f"  {n} — {self._one_line(by_name[n].get('description'))}"
            for n in names if n not in NATIVE_TOOLS
        )
        schemas.append({
            "name": DISPATCH_TOOL,
            "description": (
                "Call any mazemaker memory tool by name. The pod exposes a "
                "single endpoint and this is it — every tool below is fully "
                f"available. If you are unsure of a tool's arguments, call "
                f"{DISPATCH_HELP_TOOL} first; do not guess.\n"
                f"Tools (the {len(NATIVE_TOOLS)} hottest have their own "
                f"top-level tools and are not repeated here):\n" + listing
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "description": "Which mazemaker tool to invoke.",
                        "enum": names,
                    },
                    "args": {
                        "type": "object",
                        "description": (
                            "Arguments for that tool, as its own schema "
                            f"defines them. Get the schema with {DISPATCH_HELP_TOOL}."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": ["tool"],
            },
        })
        schemas.append({
            "name": DISPATCH_HELP_TOOL,
            "description": (
                "Return the full argument schema for one mazemaker tool. Use "
                f"before calling {DISPATCH_TOOL} with a tool you have not used "
                "in this session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # Deliberately no enum here: the dispatcher already carries
                    # one, and repeating 30-odd names would double the cost of
                    # the very thing this exists to shrink. Unknown names come
                    # back with a nearest-match suggestion instead.
                    "tool": {"type": "string",
                             "description": "Tool name, as listed by "
                                            f"{DISPATCH_TOOL}."},
                },
                "required": ["tool"],
            },
        })
        return schemas

    def _tool_help(self, name: str) -> str:
        """Schema lookup for one tool — local, no pod call."""
        tools = {t["name"]: t for t in catalogue()}
        if not tools:
            return json.dumps({"error": "tool catalogue unavailable"})
        if name not in tools:
            near = difflib.get_close_matches(name, sorted(tools), n=3, cutoff=0.4)
            return json.dumps({
                "error": f"unknown mazemaker tool '{name}'",
                "did_you_mean": near or sorted(tools)[:5],
            })
        t = tools[name]
        return json.dumps({
            "tool": name,
            "description": t.get("description", ""),
            "parameters": t.get("inputSchema", {}),
        }, ensure_ascii=False)

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """Dispatch a mazemaker tool call to the pod and return its result.

        Accepts both the native tool names and the ``mazemaker(tool, args)``
        dispatcher; the two are the same call once unwrapped.
        """
        args = args if isinstance(args, dict) else {}
        if tool_name == DISPATCH_HELP_TOOL:
            return self._tool_help(str(args.get("tool") or "").strip())
        if tool_name == DISPATCH_TOOL:
            inner = str(args.get("tool") or "").strip()
            inner_args = args.get("args") or {}
            if isinstance(inner_args, str):
                try:
                    inner_args = json.loads(inner_args)
                except Exception:
                    inner_args = {}
            if not isinstance(inner_args, dict):
                inner_args = {}
            if not inner:
                return json.dumps({
                    "error": f"{DISPATCH_TOOL} requires a 'tool' name",
                    "hint": f"call {DISPATCH_HELP_TOOL} to see a tool's arguments",
                })
            known = {t["name"] for t in catalogue()}
            if known and inner not in known:
                near = difflib.get_close_matches(inner, sorted(known), n=3, cutoff=0.4)
                return json.dumps({
                    "error": f"unknown mazemaker tool '{inner}'",
                    "did_you_mean": near,
                })
            tool_name, args = inner, inner_args

        _timeout = 30.0 if tool_name in _SLOW_TOOLS else 8.0
        try:
            result = _tool(tool_name, args, timeout=_timeout)
        except Exception as exc:
            # The MemoryManager would otherwise flatten this to a bare
            # "tool failed" string and the outage state would never reach
            # the model.
            return json.dumps(self._degraded_payload(tool_name, str(exc)))
        if result is None:
            return json.dumps(self._degraded_payload(tool_name, "empty result"))
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    def shutdown(self) -> None:
        pass


    def _multi_angle_recall(self, query: str) -> List[Dict[str, Any]]:
        """Recall with a couple of rephrasings and fuse the results.

        The angles are built deterministically and go straight to the pod. A
        router model used to sit in front of this; it was measured to add zero
        retrieval value, return unparseable replies 88% of the time and cost
        +27% latency, and when its service was down every call still paid a
        connect-retry-sleep before failing open. Removed 2026-08-30.

        Mission scoping (roadmap P0-2): when this provider holds a mission
        key, recalls carry `scope=*<key>*` so one task's state cannot drown
        out another's. Curated globals are topped up separately, and an
        old-engine rejection of the unknown arg falls back to unscoped.
        """
        angles = [
            query,
            self._angles(query),
        ]
        scope = self._scoped_recall_args()

        def _merge_curated(hits):
            if not scope or len(hits) >= RECALL_LIMIT:
                return hits
            try:
                res = _tool("mazemaker_recall",
                            {"query": query, "limit": RECALL_LIMIT - len(hits),
                             "scope": "curated"}, timeout=30.0)
                got = res if isinstance(res, list) else (
                    res.get("result") if isinstance(res, dict) else None) or []
                ids = {h.get("id") for h in hits}
                hits = hits + [g for g in got if g.get("id") not in ids]
            except Exception:
                pass
            return hits

        try:
            args = {"angles": angles, "k": RECALL_LIMIT}
            if scope:
                args["scope"] = scope
            res = _tool("mazemaker_recall_multi", args, timeout=30.0)
            err_txt = "" if not isinstance(res, dict) else json.dumps(
                res.get("error") or res.get("detail") or "")
            if scope and self._looks_like_scope_rejection(err_txt):
                logger.info("pod rejected recall scope — falling back to unscoped")
                self._scope_unsupported = True
                res = _tool("mazemaker_recall_multi",
                            {"angles": angles, "k": RECALL_LIMIT}, timeout=30.0)
            if isinstance(res, list):
                return _merge_curated(res)
            if isinstance(res, dict) and "result" in res:
                r = res["result"]
                if isinstance(r, list):
                    return r
        except Exception as e:
            logger.debug("mazemaker_recall_multi failed: %s", e)
        try:
            args = {"query": query, "limit": RECALL_LIMIT}
            if scope and not getattr(self, "_scope_unsupported", False):
                args["scope"] = scope
            res = _tool("mazemaker_recall", args, timeout=30.0)
            if isinstance(res, list):
                return _merge_curated(res)
        except Exception as e:
            logger.debug("mazemaker_recall failed: %s", e)
        return []

    def _scoped_recall_args(self) -> Optional[str]:
        """Label glob scoping this mission's recall, when a key exists."""
        if getattr(self, "_scope_unsupported", False):
            return None
        key = getattr(self, "_mission_key", None)
        return f"*{key}*" if key else None

    @staticmethod
    def _looks_like_scope_rejection(err_text: str) -> bool:
        t = (err_text or "").lower()
        return "scope" in t and any(
            w in t for w in ("unexpected", "invalid", "unknown", "extra"))

    def _angles(self, query: str) -> str:
        """A mild rephrasing for the multi-angle recall."""
        stripped = query.strip()
        if not stripped:
            return query
        return f"{stripped} context history past decisions"

    def _think_neighbours(self, memory_id: int) -> List[Dict[str, Any]]:
        """Graph-connected neighbours around a memory id (spreading activation)."""
        try:
            res = _tool(
                "mazemaker_think",
                {"memory_id": int(memory_id), "depth": THINK_DEPTH},
                timeout=30.0,
            )
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                for key in ("nodes", "result", "neighbours"):
                    val = res.get(key)
                    if isinstance(val, list):
                        return val
        except Exception as e:
            logger.debug("mazemaker_think failed: %s", e)
        return []

    def _afe_facts(self, memory_id: int) -> List[Dict[str, Any]]:
        """Atomic facts extracted from the top hit."""
        try:
            res = _tool(
                "mazemaker_afe_facts",
                {"source_id": int(memory_id), "limit": AFE_SHOW},
            )
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                val = res.get("facts") or res.get("result")
                if isinstance(val, list):
                    return val
        except Exception as e:
            logger.debug("mazemaker_afe_facts failed: %s", e)
        return []

    def _build_enriched_context(self, query: str) -> str:
        """Compose the recall block: hits + neighbours + AFE facts."""
        parts = []
        hits = self._multi_angle_recall(query)
        strong = [h for h in hits if float(h.get("similarity", 0) or 0) >= SIM_FLOOR]
        weak_fallback = not strong
        shown = strong[:RECALL_SHOW] if strong else hits[:RECALL_SHOW]

        if shown:
            header = (
                "WEAK MEMORY MATCHES (below relevance floor — treat as hints, "
                "not established facts):\n"
                if weak_fallback
                else "RECALLED FROM MAZEMAKER:\n"
            )
            hit_lines = []
            for h in shown:
                cid = h.get("id")
                sim = h.get("similarity", 0)
                body = self._clean(h.get("content", ""))
                preview = self._clip(body, RECALL_CLIP)
                hit_lines.append(
                    f"[id {cid}, sim {sim:.2f}] {preview}"
                )
            parts.append(header + "\n".join(hit_lines))

            top_id = shown[0].get("id")
            if top_id is not None:
                neighbours = self._think_neighbours(top_id)
                if neighbours:
                    nb_lines = []
                    for n in neighbours[:THINK_SHOW]:
                        nb_lines.append(
                            self._clip(self._clean(n.get("content", "")), RECALL_CLIP)
                        )
                    parts.append("RELATED (graph neighbours):\n" + "\n".join(nb_lines))

                facts = self._afe_facts(top_id)
                if facts:
                    fact_lines = []
                    for f in facts[:AFE_SHOW]:
                        fact_lines.append(self._clip(self._clean(str(f.get("fact", f))), RECALL_CLIP))
                    parts.append("ATOMIC FACTS:\n" + "\n".join(fact_lines))

        if not parts:
            return ""
        return "\n\n".join(parts)

    @staticmethod
    def _clean(text: Any) -> str:
        if not text:
            return ""
        return str(text).replace("\x00", "")

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "…[truncated]"
