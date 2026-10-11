"""Strata keeps ONE conversation live and parks the others; this is Daedalus's side of the hot-swap on it.

On the llama.cpp fork the hot-swap uses two real slots: the sidekick slot is prewarmed with the next epoch, then
promoted to main, and the demoted slot is erased. Strata has no second slot, but it parks the conversation the
engine moves away from and resumes a parked one by exact prefix, so:

  prewarm  = a max_tokens=1 request with the next epoch's exact prompt. It runs live in the engine (main is
             parked meanwhile) and leaves the next epoch parked, ready to be resumed in ~60 ms.
  cancel   = the engine is single-sequence, so a prewarm that is still reading when main wants in must stop:
             closing the connection makes the server STOP it (progress survives as checkpoints).
  promote  = main's next request matches the parked next epoch; the engine parks the OLD epoch in its place.
  evict    = POST /v1/cache/drop_parked drops that old epoch for good, the Strata counterpart of the fork's
             erase_slot(previous).
"""

from __future__ import annotations

import http.client
import json
import logging
import threading
import urllib.parse
from typing import Callable, Optional

from agent.kv_watermarks import server_root

logger = logging.getLogger(__name__)

DONE, CANCELLED, FAILED = "done", "cancelled", "failed"


def cancellable_post(url: str, body: dict, should_cancel: Callable[[], bool], *,
                     timeout: float = 900.0, poll: float = 0.4) -> str:
    """POST `body` as JSON and wait for the answer, closing the connection if `should_cancel()` turns true.

    Returns DONE (HTTP 2xx), CANCELLED (we closed it) or FAILED (anything else). Never raises."""
    parts = urllib.parse.urlsplit(url)
    if not parts.hostname:
        return FAILED
    conn = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
    finished = threading.Event()
    cancelled = threading.Event()

    def watch() -> None:
        while not finished.wait(poll):
            try:
                if should_cancel():
                    cancelled.set()
                    sock = conn.sock
                    if sock is not None:
                        try:
                            sock.shutdown(2)       # SHUT_RDWR: unblocks the reader, the server sees a disconnect
                        except OSError:
                            pass
                    conn.close()
                    return
            except Exception:
                logger.debug("cancel check failed", exc_info=True)

    watcher = threading.Thread(target=watch, daemon=True, name="prewarm-cancel-watch")
    watcher.start()
    try:
        conn.request("POST", parts.path or "/", body=json.dumps(body).encode("utf-8"),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        return DONE if 200 <= resp.status < 300 else FAILED
    except Exception as exc:
        if cancelled.is_set():
            return CANCELLED
        logger.debug("prewarm request failed: %s", exc)
        return FAILED
    finally:
        finished.set()
        try:
            conn.close()
        except Exception:
            pass


def drop_parked(base_url: str, timeout: float = 35.0) -> Optional[dict]:
    """Evict every parked conversation on a local Strata (the dead epoch after a promotion).

    None when the endpoint is not there (not Strata, remote, an older engine) or unreachable."""
    root = server_root(base_url)
    if not root:
        return None
    parts = urllib.parse.urlsplit(root)
    try:
        conn = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
        conn.request("POST", "/v1/cache/drop_parked", body=b"{}", headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        if resp.status != 200:
            return None
        out = json.loads(data or b"{}")
        return out if isinstance(out, dict) else None
    except Exception as exc:
        logger.debug("drop_parked failed: %s", exc)
        return None
