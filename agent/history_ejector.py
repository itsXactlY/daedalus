"""HistoryEjector - tell the server a rebase happened, and give the bytes back.

WHY THIS EXISTS
A rebase replaces the history under the live conversation. Two sides have to
agree about that, and until now neither did:

  * The server was never told. Strata had no way to learn that the cells of the
    dropped epoch are unreachable, so it kept every one of them mapped and
    faulted in. The prefix did not vanish when the messages were discarded; it
    stopped being *read* and stayed resident, which is how dropped history ends
    up sitting in swap long after the agent moved on.
  * Daedalus never released its own copy. The compressed list is a fresh object
    graph, but CPython's pymalloc does not hand freed arenas back to the OS
    eagerly, so the old messages became garbage that was still mapped, and still
    a swap candidate under pressure.

So the eject is two calls that must happen at the same boundary: a synchronous
"forget everything before cell N" to the server, and a heap trim here. Doing
only the first leaves our own pages; doing only the second leaves the KV.

WHY IT IS SAFE TO SEND A CUT WE ARE UNSURE ABOUT
The server validates the cut against its own live write position and refuses a
cut that is ahead of it, because releasing a cell the current step still needs
would corrupt that step. That check lives where the knowledge is, not here. This
class therefore treats a refusal as a normal outcome, not an error: a remote
backend, an engine without the command, or a cut past the live position all mean
"nothing was released", which is the pre-existing behaviour and is safe.

It is deliberately fire-and-report. A failed eject costs memory that would
otherwise have been released; it must never cost the turn.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import json
import os
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_MADV_DONTNEED = 4


def server_root(base_url: str) -> Optional[str]:
    """The engine's root for a local base_url, or None for anything remote.

    Same rule as agent/kv_watermarks.server_root: control signals only go to a
    loopback engine, because they address host state (slots, KV) that a remote
    API does not expose and that we must not pretend to control.
    """
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    low = base.lower()
    if "127.0.0.1" not in low and "localhost" not in low:
        return None
    return base


@dataclass
class EjectResult:
    """What the last eject achieved. Every field is a fact, not an assumption."""

    ok: bool = False
    reason: str = ""
    cut_cells: int = 0
    pages: int = 0
    released_mib: int = 0
    pinned_mib: int = 0
    heap_trimmed: bool = False
    raw: str = ""

    def __str__(self) -> str:
        return (f"cut={self.cut_cells} pages={self.pages} "
                f"released={self.released_mib}MiB pinned={self.pinned_mib}MiB "
                f"heap_trimmed={self.heap_trimmed} ({self.reason})")


class HistoryEjector:
    """Release a replaced epoch: the server's KV prefix and our own heap.

    One instance per agent. It is cheap and stateless apart from the counters,
    so there is nothing to share and nothing to lock - but the heap trim is a
    process-wide operation (malloc_trim), so it is the one call here that must
    not fire on every turn by accident; the caller decides when.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url or ""
        self.timeout = timeout
        self.ejects_sent = 0
        self.ejects_refused = 0
        self.ejects_unsupported = 0
        self._libc = None

    # -- server side -------------------------------------------------

    def eject_kv(self, cut_cells: int) -> EjectResult:
        """Ask the engine to release the KV cells before ``cut_cells``.

        Synchronous on purpose: the caller is at a rebase boundary, and the next
        render must not be able to match the old bytes against a KV that is
        about to disappear. Returns a result describing what happened; never
        raises, because a memory optimisation is not worth failing a turn over.
        """
        res = EjectResult(cut_cells=int(cut_cells or 0))
        if res.cut_cells <= 0:
            res.ok = True
            res.reason = "nothing to eject"
            return res
        root = server_root(self.base_url)
        if not root:
            res.reason = "remote backend: no local KV to eject"
            self.ejects_unsupported += 1
            return res
        req = urllib.request.Request(
            f"{root}/v1/kv/eject",
            data=json.dumps({"cut_cells": res.cut_cells}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            # 409 is the engine's own refusal (cut ahead of the live position);
            # 404/503 mean the endpoint is not there or the engine is not up.
            res.reason = f"server refused: HTTP {exc.code}"
            res.raw = exc.reason
            self.ejects_refused += 1
            logger.info("history eject: %s (cut=%d)", res.reason, res.cut_cells)
            return res
        except Exception as exc:
            res.reason = f"{type(exc).__name__}: {exc}"
            self.ejects_unsupported += 1
            logger.info("history eject: %s (cut=%d)", res.reason, res.cut_cells)
            return res
        res.ok = bool(body.get("ok"))
        res.raw = str(body.get("raw", ""))
        res.pages = int(body.get("pages") or 0)
        res.released_mib = int(body.get("released_mib") or 0)
        res.pinned_mib = int(body.get("pinned_mib") or 0)
        res.reason = "ok" if res.ok else "engine reported no release"
        if res.ok:
            self.ejects_sent += 1
        else:
            self.ejects_refused += 1
        return res

    # -- our side ----------------------------------------------------

    def _libc_handle(self):
        if self._libc is None:
            try:
                self._libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6",
                                          use_errno=True)
            except Exception:
                self._libc = False       # remember the failure; do not retry every call
        return self._libc or None

    def release_heap(self) -> bool:
        """Hand freed pages back to the OS: collect, then trim the allocator.

        CPython returns freed objects to its own arenas and keeps those arenas
        mapped. malloc_trim is what actually returns the underlying pages, which
        is what keeps a discarded epoch from becoming a swap candidate. Returns
        whether the trim was performed; the collect always runs.
        """
        gc.collect()
        libc = self._libc_handle()
        if libc is None or not hasattr(libc, "malloc_trim"):
            return False
        try:
            libc.malloc_trim(0)
            return True
        except Exception as exc:
            logger.debug("history eject: malloc_trim failed: %s", exc)
            return False

    def advice(self, addr: int, length: int) -> bool:
        """madvise(MADV_DONTNEED) an address range this process owns.

        Exposed for a caller that holds a large mapping it is about to drop
        (a spill buffer, a snapshot). Not used by the rebase path itself: the
        pages that matter there are CPython's own, which malloc_trim already
        covers and which we cannot safely advise on individually.
        """
        libc = self._libc_handle()
        if libc is None or not hasattr(libc, "madvise") or length <= 0:
            return False
        try:
            rc = libc.madvise(ctypes.c_void_p(addr), ctypes.c_size_t(length),
                              _MADV_DONTNEED)
            return rc == 0
        except Exception:
            return False

    # -- the boundary ------------------------------------------------

    def on_rebase(self, kept_messages: list, cut_cells: int = 0,
                  trim_heap: bool = True) -> EjectResult:
        """The rebase hook: drop the replaced epoch on both sides.

        ``kept_messages`` is the surviving conversation. It is accepted so a
        caller can pass what it has and so a future variant can derive the cut
        from it; the cut itself is a cell position the engine understands, so it
        is taken from the argument rather than guessed from Python lengths (a
        message is not a cell, and mistaking one for the other would cut the
        wrong history).
        """
        # The engine eject is OPT-IN. The cut passed here is the whole pre-compression
        # length, which covers the head the next epoch REUSES; the engine's own request
        # path already treats every cell from the reused prefix on as stale and rewrites
        # it, and the clock reclaims stale device slots, so the call frees nothing the
        # tape needs freed. Set DAEDALUS_KV_EJECT=1 to experiment.
        if os.environ.get("DAEDALUS_KV_EJECT", "").strip() == "1":
            res = self.eject_kv(cut_cells)
        else:
            res = EjectResult(ok=False, cut_cells=cut_cells,
                              reason="engine eject off (DAEDALUS_KV_EJECT=1 enables it)")
        if trim_heap:
            res.heap_trimmed = self.release_heap()
        logger.info("history eject: %s (kept %d messages)",
                    res, len(kept_messages) if kept_messages is not None else 0)
        return res