"""Phase-B dependency-closure shim for ``agent.conversation_compression``.

IMPORTANT: this is NOT the 0.20 ``conversation_compression`` module.  The
local tree deliberately uses ``agent/context_compressor.py`` as its
compression engine; the 4,014-line origin ``conversation_compression.py``
is ported in a later phase as a separate decision.

This file exists ONLY to make the module-level imports of the ported
``agent.turn_context`` resolve during Phase B of the 0.20 CLI rework.  It
carries the exact subset of symbols ``turn_context`` imports at module
level, extracted verbatim from ``origin/main``.  When the real module is
ported, this file is replaced wholesale.

Symbols:
  - ``PREFLIGHT_COMPRESSION_STATUS_TEMPLATE``, ``IDLE_COMPACTION_STATUS_TEMPLATE``
  - ``compression_skipped_due_to_lock``
  - ``conversation_history_after_compression``
  - ``recover_rotated_compression_session`` (+ its internal helpers
    ``_session_was_rotated_by_compression`` and ``_adopt_live_compression_child``)

All functions are defensive (``getattr`` / ``try-except`` based) so they are
safe to run against the local agent objects even when the underlying
compression/session attributes are absent.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PREFLIGHT_COMPRESSION_STATUS_TEMPLATE = (
    "📦 Preflight compression: ~{tokens:,} tokens "
    ">= {threshold:,} threshold. This may take a moment."
)
IDLE_COMPACTION_STATUS_TEMPLATE = (
    "💤 Resumed after {idle_seconds}s idle — compacting "
    "~{tokens:,} tokens before continuing."
)


def compression_skipped_due_to_lock(agent: Any) -> bool:
    """Type-pinned read of the #69870 lock-skip signal.

    ``agent._compression_skipped_due_to_lock`` is set by ``compress_context``
    when a compression pass no-ops because another path holds the per-session
    compression lock (holder string when the holder was confirmed, ``True``
    otherwise) and cleared to ``None`` at the entry of every call.

    The read MUST be type-pinned (``is True or isinstance(x, str)``), never
    bare truthiness: MagicMock test-double agents auto-create truthy
    attributes, and a bare ``if getattr(agent, ...)`` would hijack every
    mocked agent in sibling suites into the lock-skip branch (the
    #69870 × #69840 type-ahead incident).
    """
    _sig = getattr(agent, "_compression_skipped_due_to_lock", None)
    return _sig is True or isinstance(_sig, str)


def _session_was_rotated_by_compression(session_db: Any, session_id: str) -> bool:
    """Return whether another path already rotated this compression parent."""
    getter = getattr(type(session_db), "get_session", None)
    if not callable(getter):
        return False
    session = getter(session_db, session_id)
    return bool(
        session
        and session.get("ended_at") is not None
        and session.get("end_reason") == "compression"
    )


def _adopt_live_compression_child(
    agent: Any,
    session_db: Any,
    parent_session_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Move a stale compression contender onto the unique durable child.

    Resolve and load first, then mutate the live agent. This ordering keeps the
    stale contender fail-closed when lineage is ambiguous or the compacted
    handoff cannot be read.
    """
    finder = getattr(type(session_db), "find_live_compression_child", None)
    loader = getattr(type(session_db), "get_messages_as_conversation", None)
    if not callable(finder) or not callable(loader):
        return None
    child = finder(session_db, parent_session_id)
    if not child or not child.get("id"):
        return None
    child_session_id = str(child["id"])
    recovered = loader(session_db, child_session_id)
    if not isinstance(recovered, list) or not recovered:
        return None
    # Revalidate after loading: the child may have rotated or a competing
    # continuation may have appeared between the two DB reads.
    confirmed = finder(session_db, parent_session_id)
    if not confirmed or str(confirmed.get("id") or "") != child_session_id:
        return None

    agent.session_id = child_session_id
    try:
        from gateway.session_context import set_current_session_id

        set_current_session_id(child_session_id)
    except Exception:
        os.environ["DAEDALUS_SESSION_ID"] = child_session_id
    try:
        from daedalus_logging import set_session_context

        set_session_context(child_session_id)
    except Exception:
        pass

    agent._session_db_created = True
    if child.get("system_prompt"):
        agent._cached_system_prompt = child["system_prompt"]
    agent._last_flushed_db_idx = len(recovered)
    agent._flushed_db_message_session_id = child_session_id
    agent._flushed_db_message_ids = {
        id(message) for message in recovered if isinstance(message, dict)
    }

    on_session_start = getattr(agent.context_compressor, "on_session_start", None)
    if callable(on_session_start):
        try:
            on_session_start(
                child_session_id,
                boundary_reason="compression",
                old_session_id=parent_session_id,
                session_db=session_db,
                platform=getattr(agent, "platform", None) or "cli",
                conversation_id=getattr(agent, "_gateway_session_key", None),
            )
        except Exception as exc:
            logger.debug("context engine compression-child adoption failed: %s", exc)
    else:
        bind_state = getattr(agent.context_compressor, "bind_session_state", None)
        if callable(bind_state):
            try:
                bind_state(session_db=session_db, session_id=child_session_id)
            except Exception:
                pass
    try:
        if agent._memory_manager:
            agent._memory_manager.on_session_switch(
                child_session_id,
                parent_session_id=parent_session_id,
                reset=False,
                reason="compression",
            )
    except Exception as exc:
        logger.debug("memory manager compression-child adoption failed: %s", exc)

    return recovered


def recover_rotated_compression_session(
    agent: Any,
) -> Optional[List[Dict[str, Any]]]:
    """Recover a stale live agent before a new turn writes to its old parent."""
    session_db = getattr(agent, "_session_db", None)
    session_id = getattr(agent, "session_id", None) or ""
    if session_db is None or not session_id:
        return None
    try:
        if not _session_was_rotated_by_compression(session_db, session_id):
            return None
        # Rotation publication holds the parent compression lease until the
        # child handoff is durable. A concurrent turn waits briefly rather than
        # observing the intentional parent-ended/child-empty intermediate state.
        holder_getter = getattr(session_db, "get_compression_lock_holder", None)
        for attempt in range(21):
            recovered = _adopt_live_compression_child(agent, session_db, session_id)
            if recovered is not None:
                return recovered
            holder = holder_getter(session_id) if callable(holder_getter) else None
            if not holder or attempt == 20:
                return None
            time.sleep(0.05)
        return None
    except Exception as exc:
        logger.warning(
            "compression session recovery failed for session=%s (%s: %s)",
            session_id,
            type(exc).__name__,
            exc,
        )
        return None


def conversation_history_after_compression(
    agent: Any,
    messages: list,
    previous_history: Optional[list] = None,
) -> Optional[list]:
    """Return the correct flush baseline after a compression boundary.

    Legacy compression rotates to a fresh child session. That child has not
    seen the compacted transcript through the normal same-turn flush path yet,
    so callers must clear ``conversation_history`` to ``None`` and let the next
    persistence call write the whole compacted list.

    In-place compaction is different: ``archive_and_compact()`` has already
    soft-archived the previous active rows and inserted ``messages`` as the new
    active live transcript under the same session id. If the same agent turn
    continues with ``conversation_history=None``, the identity-based flush path
    treats those already-persisted compacted dicts as new and appends them a
    second time, doubling the active context and retriggering compression.

    A shallow copy is intentional: it captures the current compacted dict
    identities as history while allowing later same-turn appends to remain new.

    An aborted or no-op attempt after an earlier in-place compaction must retain
    the pre-attempt baseline.  Treating all current messages as persisted would
    drop any later, unflushed turns on restart; clearing the baseline would
    append the already-persisted compacted rows a second time.
    """
    if bool(getattr(agent, "_last_compression_attempt_recorded", False)):
        attempt_in_place = getattr(agent, "_last_compression_attempt_in_place", None)
        if attempt_in_place is True:
            return list(messages)
        if attempt_in_place is False:
            return None
        return previous_history
    if bool(getattr(agent, "_last_compaction_in_place", False)):
        return list(messages)
    return None


__all__ = [
    "PREFLIGHT_COMPRESSION_STATUS_TEMPLATE",
    "IDLE_COMPACTION_STATUS_TEMPLATE",
    "compression_skipped_due_to_lock",
    "conversation_history_after_compression",
    "recover_rotated_compression_session",
]
