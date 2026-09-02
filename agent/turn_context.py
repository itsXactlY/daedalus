"""Per-turn setup for ``run_conversation`` (the turn prologue).

``run_conversation`` opened with ~470 lines of straight-line setup before the
tool-calling loop ever started: stdio guarding, runtime-main wiring, retry-counter
resets, user-message sanitization, todo/nudge-counter hydration, system-prompt
restore-or-build, session-row creation (before compression, whose DB writes
reference the row), preflight context compression, the ``pre_llm_call`` plugin
hook, external-memory prefetch, and crash-resilience persistence (last, so the
user row is written once with its final ``api_content`` sidecar).

All of that is *prologue* — it runs once per turn, has no back-references into the
loop, and produces a fixed set of values the loop then consumes. ``TurnContext``
captures those produced values; ``build_turn_context`` performs the setup work and
returns one. ``run_conversation`` is left to unpack the context and run the loop,
shrinking the orchestrator by the full prologue.

The builder still mutates ``agent`` heavily (counters, thread id, cached prompt,
session DB) exactly as the inline code did — those side effects are the point. The
``TurnContext`` it returns carries only the *locals* the loop reads back.

Behavior is identical to the original inline prologue; this is a pure
move-and-name refactor with no semantic change.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from agent.conversation_compression import (
    IDLE_COMPACTION_STATUS_TEMPLATE,
    PREFLIGHT_COMPRESSION_STATUS_TEMPLATE,
    compression_skipped_due_to_lock,
    conversation_history_after_compression,
    recover_rotated_compression_session,
)
from agent.context_engine import automatic_compaction_status_message
from agent.iteration_budget import IterationBudget
from agent.memory_manager import build_memory_context_block
from agent.memory_provider import is_trivial_prompt
from agent.model_metadata import (
    estimate_messages_tokens_rough,
    estimate_request_tokens_rough,
)

logger = logging.getLogger(__name__)


def compose_user_api_content(
    content: Any,
    ext_prefetch_cache: str,
    plugin_user_context: str,
) -> Optional[str]:
    """Compose the API-bound content of the current turn's user message.

    Sources: memory-manager prefetch + ``pre_llm_call`` plugin context with
    target="user_message" (the default). Both are appended to the *API copy*
    of the user message only — the stored content stays clean.

    This is the single source of that composition. The prologue stamps the
    result onto the live message as ``api_content`` (persisted alongside the
    clean content) and the ``api_messages`` build in ``conversation_loop``
    sends the same helper's output, so the persisted sidecar can never drift
    from the bytes on the wire — which is the whole prompt-cache invariant:
    what turn N sends must be what turn N+1 replays.

    Returns ``None`` when nothing is injected (multimodal/non-string content,
    or no ephemeral context), meaning the message is sent as-is.
    """
    if not isinstance(content, str):
        return None
    injections = []
    if ext_prefetch_cache:
        fenced = build_memory_context_block(ext_prefetch_cache)
        if fenced:
            injections.append(fenced)
    if plugin_user_context:
        injections.append(plugin_user_context)
    if not injections:
        return None
    return content + "\n\n" + "\n\n".join(injections)


def substitute_api_content(api_msg: Dict[str, Any]) -> Optional[str]:
    """Pop the ``api_content`` sidecar and substitute it into ``content``.

    Used at every API-bound message-build site (the ``api_messages`` build in
    ``conversation_loop``, the max-iterations summary in
    ``chat_completion_helpers``, the chat-completions transport). The sidecar
    carries the exact bytes previously sent to the API for this message when
    they differ from the clean stored content; substituting it here keeps the
    provider prompt-cache prefix byte-stable across turns.

    Returns the popped sidecar string (for callers that need the value for
    current-turn composition logic) or ``None`` when absent.
    """
    sidecar = api_msg.pop("api_content", None)
    if (
        isinstance(sidecar, str)
        and sidecar
        and api_msg.get("role") in ("user", "assistant")
    ):
        api_msg["content"] = sidecar
    return sidecar


def drop_stale_api_content(msg: Dict[str, Any]) -> None:
    """Drop the ``api_content`` sidecar from a message whose content was rewritten.

    Called from every content-rewrite path (historical image strip,
    merge-summary-into-tail, consecutive-user repair merge, stale-confirmation
    redaction). Replaying the pre-rewrite sidecar would resend exactly what
    the rewrite removed, so it must be dropped — the cost is one cache
    boundary miss, never wrong content.
    """
    msg.pop("api_content", None)


def extract_api_content_sidecar(msg: Mapping[str, Any]) -> Optional[str]:
    """Extract the ``api_content`` sidecar from a message dict for persistence.

    Shared by the gateway/branch forwarding sites that copy the sidecar into a
    new row. Returns the string sidecar or ``None`` when absent/non-string.
    """
    v = msg.get("api_content")
    return v if isinstance(v, str) else None


def consume_gateway_turn_context_notes(agent: Any) -> str:
    """Pop the gateway's per-turn must-deliver notes off the agent (one-shot).

    The gateway relocates volatile per-turn facts OUT of the ephemeral system
    prompt (auto-reset notes, the first-contact intro, voice-channel changes)
    and delivers them on the current user message via the api_content sidecar
    instead, so the composed system prompt stays byte-stable turn-over-turn.
    It stages the rendered notes on ``agent._gateway_turn_context_notes``
    right before ``run_conversation``; this consumes them so a cached agent
    can never replay a stale note on a later turn.
    """
    notes = getattr(agent, "_gateway_turn_context_notes", "") or ""
    if hasattr(agent, "_gateway_turn_context_notes"):
        try:
            agent._gateway_turn_context_notes = ""
        except Exception:
            pass
    return notes if isinstance(notes, str) else ""


def append_notes_to_multimodal_content(content: Any, notes: str) -> bool:
    """Deliver must-deliver notes on a multimodal (list) user message.

    ``compose_user_api_content`` returns ``None`` for non-string content, so
    sidecar-borne facts would silently drop on image/attachment turns.  For
    gateway must-deliver notes we instead append a text part to the content
    list in place — the part becomes durable message content (persisted and
    replayed as-is), which keeps the wire and the transcript byte-identical.

    Returns ``True`` when a part was appended.
    """
    if not notes or not isinstance(content, list):
        return False
    try:
        content.append({"type": "text", "text": notes})
        return True
    except Exception:
        return False


def reanchor_current_turn_user_idx(messages: List[Any], user_message: Any) -> int:
    """Locate this turn's user message after compaction rebuilt ``messages``.

    Compression replaces list entries with fresh copies (and may append a
    todo-snapshot user message or a restored user turn AFTER the surviving
    copy of the current turn's message), so a pre-compression index is
    meaningless. Prefer the LAST user message whose content exactly matches
    this turn's text — the surviving copy in the common case — so the
    injection stamp and the #48677 persist override can't land on a
    todo-snapshot or historical row. Fall back to the last user message when
    no exact match survives (merge-summary-into-tail rewrites the content but
    the trackers still need a live anchor) — but the fallback must skip
    synthetic rows (``display_kind`` set, e.g. the todo-snapshot
    ``_compress_context`` appends AFTER the real turn): confirmed reachable
    when a merge-summary-into-tail rewrite changes the real turn's content
    (so the exact-match above misses it) while a todo-snapshot survives
    later in the list — without this guard the fallback lands on the
    snapshot instead of the real, rewritten turn. Returns -1 when the list
    has no genuine user message at all.
    """
    fallback = -1
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if not (isinstance(msg, dict) and msg.get("role") == "user"):
            continue
        if msg.get("content") == user_message:
            return i
        if fallback < 0 and not msg.get("display_kind"):
            fallback = i
    return fallback


def compression_made_progress(
    orig_len: int, new_len: int, orig_tokens: int, new_tokens: int
) -> bool:
    """Return ``True`` if a compression pass materially reduced the request.

    Compression can succeed by summarising message contents — reducing the
    estimated request token count — without reducing the message row
    count.  Treating row count as the sole progress signal false-positives
    on size-only wins and surfaces a misleading "Cannot compress further"
    failure even when post-compression tokens are well below the model
    context window.  See issue #39548 for an observed case: 220 → 220
    messages, ~288k → ~183k tokens on a 1M-context model still triggered
    auto-reset.

    The token reduction must be *material* (>5%) to count as progress — the
    same floor the overflow-handler retry path uses (conversation_loop.py,
    #39550) — so a sub-5% wobble doesn't keep the multi-pass loop spinning.
    """
    if new_len < orig_len:
        return True
    return orig_tokens > 0 and new_tokens < orig_tokens * 0.95


_compression_made_progress = compression_made_progress


def _compression_warrants_another_preflight_pass(
    orig_tokens: int, new_tokens: int, threshold_tokens: int
) -> bool:
    """Whether an over-threshold request merits another immediate summary.

    Row-count progress is enough to prove that a compression boundary was real,
    but not enough to justify another expensive pass before trying the provider.
    Continue only when the request remains over threshold *and* the previous pass
    materially reduced its estimated token pressure (>5%).
    """
    return (
        new_tokens >= threshold_tokens
        and orig_tokens > 0
        and new_tokens < orig_tokens * 0.95
    )


def _should_run_preflight_estimate(
    messages: List[Dict[str, Any]],
    protect_first_n: int,
    protect_last_n: int,
    threshold_tokens: int,
) -> bool:
    """Cheap gate for the (expensive) full preflight token estimate.

    Returns ``True`` when either:
      (a) message count exceeds the protected ranges (the historical gate), or
      (b) a cheap char-based estimate already crosses the configured threshold
          — the few-but-huge case from issue #27405 that the count-only gate
          would silently skip (a handful of very large messages never trips
          the count condition, so compression was never attempted and the
          turn hit a hard context-overflow error).

    Branch (b) uses ``estimate_messages_tokens_rough`` (the shared char-based
    estimator) so a single large base64 image isn't mistaken for ~250K tokens.
    It intentionally undercounts vs. the full request estimate — it omits the
    system prompt and tool schemas — because it is only a *hint* deciding
    whether to pay for the authoritative ``estimate_request_tokens_rough``,
    which (together with ``should_compress``) makes the real decision.
    """
    if len(messages) > protect_first_n + protect_last_n + 1:
        return True
    return estimate_messages_tokens_rough(messages) >= threshold_tokens


def _should_idle_compact(
    *,
    enabled: bool,
    idle_after_seconds: int,
    idle_gap_seconds: float,
    tokens: int,
    floor_tokens: int,
    cooldown_active: bool,
) -> bool:
    """Decide whether an idle-triggered compaction should run this turn.

    Idle compaction is opt-in (``idle_after_seconds <= 0`` disables it). It
    fires when a session resumes after a wall-clock gap of at least
    ``idle_after_seconds`` since its last activity, so a long-lived thread
    that is paused and later resumed compacts its accumulated history up
    front instead of re-reading it on every subsequent turn.

    It is orthogonal to the token-threshold trigger: it does NOT require the
    context to exceed ``threshold_tokens``. It still skips work when the
    context is at or below ``floor_tokens`` (the size compaction would reduce
    *to*), so a small idle thread never pays for a summarisation that saves
    nothing, and it defers to an active compression-failure cooldown.

    Pure predicate so the policy is unit-testable without a live agent.
    """
    if not enabled or idle_after_seconds <= 0:
        return False
    if idle_gap_seconds < idle_after_seconds:
        return False
    if cooldown_active:
        return False
    return tokens > floor_tokens


@dataclass
class TurnContext:
    """Values produced by the turn prologue and consumed by the turn loop."""

    user_message: str
    original_user_message: Any
    messages: List[Dict[str, Any]]
    conversation_history: Optional[List[Dict[str, Any]]]
    active_system_prompt: Optional[str]
    effective_task_id: str
    turn_id: str
    current_turn_user_idx: int
    should_review_memory: bool = False
    plugin_user_context: str = ""
    ext_prefetch_cache: str = ""
    preflight_compression_blocked: bool = False


def build_turn_context(
    agent,
    user_message: Any,
    system_message: Optional[str],
    conversation_history: Optional[List[Dict[str, Any]]],
    task_id: Optional[str],
    stream_callback,
    persist_user_message: Optional[Any],
    persist_user_timestamp: Optional[float] = None,
    *,
    persist_user_display_kind: Optional[str] = None,
    persist_user_display_metadata: Optional[Dict[str, Any]] = None,
    restore_or_build_system_prompt,
    install_safe_stdio,
    sanitize_surrogates,
    summarize_user_message_for_log,
    set_session_context,
    set_current_write_origin,
    ra,
    moa_active: bool = False,
) -> TurnContext:
    """Run the once-per-turn setup and return the loop's input context.

    The callables/helpers the original prologue referenced from the
    ``conversation_loop`` module are passed in explicitly to keep this module
    free of an import cycle with ``agent.conversation_loop``.
    """
    install_safe_stdio()

    recovered_history = recover_rotated_compression_session(agent)
    if recovered_history is not None:
        conversation_history = recovered_history


    set_session_context(agent.session_id)

    set_current_write_origin(getattr(agent, "_memory_write_origin", "assistant_tool"))

    agent._restore_primary_runtime()

    try:
        from agent.auxiliary_client import set_runtime_main
        set_runtime_main(
            getattr(agent, "provider", "") or "",
            getattr(agent, "model", "") or "",
            requested_provider=getattr(agent, "requested_provider", "") or "",
            base_url=getattr(agent, "base_url", "") or "",
            api_key=getattr(agent, "api_key", "") or "",
            api_mode=getattr(agent, "api_mode", "") or "",
            auth_mode=getattr(agent, "auth_mode", "") or "",
            session_id=getattr(agent, "session_id", "") or "",
        )
    except Exception:
        pass

    try:
        if not getattr(agent, "_skip_mcp_refresh", False):
            import sys as _sys
            if "tools.mcp_tool" in _sys.modules:
                from tools.mcp_tool import has_registered_mcp_tools, refresh_agent_mcp_tools
                if has_registered_mcp_tools():
                    refresh_agent_mcp_tools(agent, quiet_mode=True)
    except Exception:
        logger.debug("between-turns MCP tool refresh skipped", exc_info=True)

    if isinstance(user_message, str):
        user_message = sanitize_surrogates(user_message)
    if isinstance(persist_user_message, str):
        persist_user_message = sanitize_surrogates(persist_user_message)

    agent._stream_callback = stream_callback
    agent._persist_user_message_idx = None
    agent._persist_user_message_override = persist_user_message
    agent._persist_user_message_timestamp = persist_user_timestamp
    effective_task_id = task_id or str(uuid.uuid4())
    agent._current_task_id = effective_task_id
    turn_id = str(getattr(agent, "_relay_pending_turn_id", "") or "")
    if not turn_id:
        turn_id = (
            f"{agent.session_id or 'session'}:{effective_task_id}:{uuid.uuid4().hex[:8]}"
        )
    agent._relay_pending_turn_id = None
    agent._current_turn_id = turn_id
    agent._current_api_request_id = ""
    from agent.agent_runtime_helpers import note_turn_start
    note_turn_start(agent, turn_id)

    agent._invalid_tool_retries = 0
    agent._invalid_json_retries = 0
    agent._empty_content_retries = 0
    agent._incomplete_scratchpad_retries = 0
    agent._codex_incomplete_retries = 0
    agent._thinking_prefill_retries = 0
    agent._post_tool_empty_retried = False
    agent._last_content_with_tools = None
    agent._last_content_tools_all_housekeeping = False
    agent._mute_post_response = False
    agent._unicode_sanitization_passes = 0
    agent._tool_guardrails.reset_for_turn()
    agent._tool_guardrail_halt_decision = None
    _reset_consol = getattr(agent._memory_store, "reset_consolidation_failures", None)
    if callable(_reset_consol):
        _reset_consol()
    agent._vision_supported = True

    if agent.api_mode != "anthropic_messages":
        try:
            if agent._cleanup_dead_connections():
                agent._emit_status(
                    "🔌 Detected stale connections from a previous provider "
                    "issue — cleaned up automatically. Proceeding with fresh "
                    "connection."
                )
        except Exception:
            pass
    if agent._compression_warning:
        agent._replay_compression_warning()
        agent._compression_warning = None

    agent.iteration_budget = IterationBudget(agent.max_iterations)

    _preview_text = summarize_user_message_for_log(user_message)
    _msg_preview = (_preview_text[:80] + "...") if len(_preview_text) > 80 else _preview_text
    _msg_preview = _msg_preview.replace("\n", " ")
    logger.info(
        "conversation turn: session=%s model=%s provider=%s platform=%s history=%d msg=%r",
        agent.session_id or "none", agent.model, agent.provider or "unknown",
        agent.platform or "unknown", len(conversation_history or []),
        _msg_preview,
    )

    messages = list(conversation_history) if conversation_history else []

    pending_cli_message = getattr(agent, "_pending_cli_user_message", None)
    expected_persist_content = (
        persist_user_message if persist_user_message is not None else user_message
    )
    if (
        isinstance(pending_cli_message, dict)
        and pending_cli_message.get("content") == expected_persist_content
    ):
        user_msg = pending_cli_message
        user_msg["content"] = user_message
    else:
        user_msg = {"role": "user", "content": user_message}
        if isinstance(pending_cli_message, dict):
            agent._pending_cli_user_message = None

    if conversation_history and not agent._todo_store.has_items():
        agent._hydrate_todo_store(conversation_history)

    if conversation_history and agent._user_turn_count == 0:
        prior_user_turns = sum(
            1 for m in conversation_history if m.get("role") == "user"
        )
        if prior_user_turns > 0:
            agent._user_turn_count = prior_user_turns
            if agent._memory_nudge_interval > 0 and agent._turns_since_memory == 0:
                agent._turns_since_memory = prior_user_turns % agent._memory_nudge_interval

    if persist_user_display_kind:
        user_msg["display_kind"] = persist_user_display_kind
        if persist_user_display_metadata:
            user_msg["display_metadata"] = persist_user_display_metadata

    messages.append(user_msg)
    current_turn_user_idx = len(messages) - 1
    agent._persist_user_message_idx = current_turn_user_idx

    agent._user_turn_count += 1
    agent._is_user_initiated_turn = True

    scrubber = getattr(agent, "_stream_context_scrubber", None)
    if scrubber is not None:
        scrubber.reset()
    think_scrubber = getattr(agent, "_stream_think_scrubber", None)
    if think_scrubber is not None:
        think_scrubber.reset()

    original_user_message = persist_user_message if persist_user_message is not None else user_message

    should_review_memory = False
    if (agent._memory_nudge_interval > 0
            and "memory" in agent.valid_tool_names
            and agent._memory_store):
        agent._turns_since_memory += 1
        if agent._turns_since_memory >= agent._memory_nudge_interval:
            should_review_memory = True
            agent._turns_since_memory = 0

    reaction_callback = getattr(agent, "reaction_callback", None)
    if reaction_callback is not None:
        try:
            from agent.reactions import detect_reaction

            kind = detect_reaction(original_user_message)
            if kind:
                reaction_callback(kind)
        except Exception:
            pass

    if not agent.quiet_mode:
        _print_preview = summarize_user_message_for_log(user_message)
        agent._safe_print(
            f"💬 Starting conversation: '{_print_preview[:60]}"
            f"{'...' if len(_print_preview) > 60 else ''}'"
        )

    if agent._cached_system_prompt is None:
        restore_or_build_system_prompt(agent, system_message, conversation_history)

    active_system_prompt = agent._cached_system_prompt

    persist_lock = getattr(agent, "_session_persist_lock", None)
    try:
        if persist_lock is None:
            agent._ensure_db_session()
        else:
            with persist_lock:
                agent._ensure_db_session()
    except Exception:
        logger.warning(
            "Turn-start session row creation failed for session=%s",
            agent.session_id or "none",
            exc_info=True,
        )
    finally:
        if not isinstance(pending_cli_message, dict) or pending_cli_message.get("_db_persisted"):
            agent._pending_cli_user_message = None

    _idle_after = getattr(agent, "compression_idle_compact_after_seconds", 0)
    if agent.compression_enabled and _idle_after > 0 and messages:
        _idle_gap = time.time() - getattr(agent, "_last_activity_ts", time.time())
        if _idle_gap >= _idle_after:
            _compressor = agent.context_compressor
            _idle_tokens = estimate_request_tokens_rough(
                messages,
                system_prompt=active_system_prompt or "",
                tools=agent.tools or None,
            )
            _idle_floor = int(
                _compressor.threshold_tokens * _compressor.summary_target_ratio
            )
            _idle_cooldown = getattr(
                _compressor, "get_active_compression_failure_cooldown", lambda: None
            )()
            if _should_idle_compact(
                enabled=agent.compression_enabled,
                idle_after_seconds=_idle_after,
                idle_gap_seconds=_idle_gap,
                tokens=_idle_tokens,
                floor_tokens=_idle_floor,
                cooldown_active=bool(_idle_cooldown),
            ):
                logger.info(
                    "Idle compaction: %ss idle >= %ss, ~%s tokens > %s floor "
                    "(session %s)",
                    int(_idle_gap),
                    _idle_after,
                    f"{_idle_tokens:,}",
                    f"{_idle_floor:,}",
                    agent.session_id or "none",
                )
                _idle_status = automatic_compaction_status_message(
                    _compressor,
                    phase="idle",
                    default_message=IDLE_COMPACTION_STATUS_TEMPLATE.format(
                        idle_seconds=int(_idle_gap), tokens=_idle_tokens
                    ),
                    approx_tokens=_idle_tokens,
                    idle_seconds=int(_idle_gap),
                    model=agent.model,
                )
                if _idle_status:
                    agent._emit_status(_idle_status)
                _idle_input = messages
                messages, active_system_prompt = agent._compress_context(
                    messages, system_message, approx_tokens=_idle_tokens,
                    task_id=effective_task_id,
                )
                if messages is not _idle_input:
                    conversation_history = conversation_history_after_compression(
                        agent, messages, conversation_history
                    )
                    current_turn_user_idx = reanchor_current_turn_user_idx(
                        messages, user_message
                    )
                    agent._persist_user_message_idx = current_turn_user_idx

    _preflight_compressed = False
    _preflight_compression_blocked = False
    agent._turn_received_provider_response = False
    agent._turn_preflight_display_snapshot = None
    if agent.compression_enabled and _should_run_preflight_estimate(
        messages,
        agent.context_compressor.protect_first_n,
        agent.context_compressor.protect_last_n,
        agent.context_compressor.threshold_tokens,
    ):
        _preflight_tokens = estimate_request_tokens_rough(
            messages,
            system_prompt=active_system_prompt or "",
            tools=agent.tools or None,
        )
        _compressor = agent.context_compressor
        _snapshot_fn = getattr(
            _compressor, "snapshot_preflight_display_tokens", None
        )
        if callable(_snapshot_fn):
            _snapshot_val = _snapshot_fn()
            if isinstance(_snapshot_val, int) and not isinstance(
                _snapshot_val, bool
            ):
                agent._turn_preflight_display_snapshot = _snapshot_val
        _defer_preflight = getattr(
            _compressor,
            "should_defer_preflight_to_real_usage",
            lambda _tokens: False,
        )
        _preflight_deferred = _defer_preflight(_preflight_tokens)
        _codex_native_auto = (
            getattr(agent, "api_mode", None) == "codex_app_server"
            and str(
                getattr(
                    agent,
                    "codex_app_server_auto_compaction",
                    "native",
                )
                or "native"
            ).lower()
            in {"native", "off"}
        )

        if not _preflight_deferred:
            _last = _compressor.last_prompt_tokens
            if _last >= 0 and _preflight_tokens > _last:
                _compressor.last_prompt_tokens = _preflight_tokens

        _compression_cooldown = getattr(
            _compressor,
            "get_active_compression_failure_cooldown",
            lambda: None,
        )()

        _should_compress_now = False
        _compress_block_reason = None
        if _preflight_deferred:
            logger.info(
                "Skipping preflight compression: rough estimate ~%s >= %s, "
                "but last real provider prompt was %s after compression",
                f"{_preflight_tokens:,}",
                f"{_compressor.threshold_tokens:,}",
                f"{_compressor.last_real_prompt_tokens:,}",
            )
        elif _compression_cooldown:
            logger.info(
                "Skipping preflight compression: same-session cooldown active "
                "(~%s seconds remaining, session %s)",
                int(_compression_cooldown.get("remaining_seconds", 0.0)),
                agent.session_id or "none",
            )
            if _preflight_tokens >= _compressor.threshold_tokens:
                _cooldown_secs = _compression_cooldown.get("remaining_seconds", 0.0)
                _compress_block_reason = f"cooldown:{_cooldown_secs:.0f}"
        elif _codex_native_auto:
            logger.info(
                "Skipping Daedalus preflight compression for codex app-server "
                "(mode=%s); Daedalus will not start thread compaction here.",
                getattr(agent, "codex_app_server_auto_compaction", "native"),
            )
        else:
            _should_compress_now = _compressor.should_compress(_preflight_tokens)
            if not _should_compress_now:
                _info = getattr(_compressor, "should_compress_info", None)
                if callable(_info):
                    try:
                        _compress_block_reason = _info(_preflight_tokens)[1]
                    except Exception:
                        _compress_block_reason = None
        if _should_compress_now:
            _preflight_compressed = True
            _clear_warn = getattr(agent, "_clear_context_overflow_warn", None)
            if callable(_clear_warn):
                _clear_warn()
            logger.info(
                "Preflight compression: ~%s tokens >= %s threshold (model %s, ctx %s)",
                f"{_preflight_tokens:,}",
                f"{_compressor.threshold_tokens:,}",
                agent.model,
                f"{_compressor.context_length:,}",
            )
            _preflight_status = automatic_compaction_status_message(
                _compressor,
                phase="preflight",
                default_message=PREFLIGHT_COMPRESSION_STATUS_TEMPLATE.format(
                    tokens=_preflight_tokens,
                    threshold=_compressor.threshold_tokens,
                ),
                approx_tokens=_preflight_tokens,
                threshold_tokens=_compressor.threshold_tokens,
                context_length=_compressor.context_length,
                model=agent.model,
            )
            if _preflight_status:
                agent._emit_status(_preflight_status)
            _max_preflight_passes = max(
                1, int(getattr(agent, "max_compression_attempts", 3) or 3)
            )
            for _pass in range(_max_preflight_passes):
                _orig_len = len(messages)
                _orig_tokens = _preflight_tokens
                _preflight_input = messages
                messages, active_system_prompt = agent._compress_context(
                    messages, system_message, approx_tokens=_preflight_tokens,
                    task_id=effective_task_id,
                )
                if (
                    messages is _preflight_input
                    and compression_skipped_due_to_lock(agent)
                ):
                    logger.info(
                        "Preflight compression deferred: compression lock "
                        "held by another path (session %s)",
                        agent.session_id or "none",
                    )
                    break
                _preflight_tokens = estimate_request_tokens_rough(
                    messages,
                    system_prompt=active_system_prompt or "",
                    tools=agent.tools or None,
                )
                if not _compression_made_progress(
                    _orig_len, len(messages), _orig_tokens, _preflight_tokens
                ):
                    _preflight_compression_blocked = True
                    break
                conversation_history = conversation_history_after_compression(
                    agent, messages, conversation_history
                )
                agent._empty_content_retries = 0
                agent._thinking_prefill_retries = 0
                agent._last_content_with_tools = None
                agent._last_content_tools_all_housekeeping = False
                agent._mute_post_response = False
                if not _compressor.should_compress(_preflight_tokens):
                    break
                if not _compression_warrants_another_preflight_pass(
                    _orig_tokens,
                    _preflight_tokens,
                    _compressor.threshold_tokens,
                ):
                    _preflight_compression_blocked = True
                    logger.warning(
                        "Preflight compression made insufficient progress: "
                        "~%s -> ~%s request tokens; skipping additional passes",
                        f"{_orig_tokens:,}",
                        f"{_preflight_tokens:,}",
                    )
                    break
        elif _compress_block_reason:
            agent._warn_context_overflow_blocked(
                _compress_block_reason,
                _preflight_tokens,
                _compressor.threshold_tokens,
            )
        else:
            _clear_warn = getattr(agent, "_clear_context_overflow_warn", None)
            if callable(_clear_warn):
                _clear_warn()
            if _compression_cooldown or _preflight_deferred or _codex_native_auto:
                _engine_preflight = None
            else:
                _engine_preflight = getattr(
                    _compressor, "should_compress_preflight", None
                )
            _wants_engine_preflight = False
            if callable(_engine_preflight):
                try:
                    _wants_engine_preflight = bool(_engine_preflight(messages))
                except Exception as _preflight_exc:
                    logger.debug(
                        "should_compress_preflight raised %s; skipping "
                        "engine-driven preflight maintenance",
                        _preflight_exc,
                    )
                    _wants_engine_preflight = False
            if _wants_engine_preflight:
                logger.info(
                    "Engine-driven preflight maintenance: %s requested "
                    "compress() at ~%s tokens (below %s threshold)",
                    getattr(_compressor, "name", type(_compressor).__name__),
                    f"{_preflight_tokens:,}",
                    f"{getattr(_compressor, 'threshold_tokens', 0):,}",
                )
                _engine_input = messages
                messages, active_system_prompt = agent._compress_context(
                    messages, system_message, approx_tokens=_preflight_tokens,
                    task_id=effective_task_id,
                )
                if messages is not _engine_input:
                    _preflight_compressed = True
                    conversation_history = conversation_history_after_compression(
                        agent, messages
                    )
                    agent._empty_content_retries = 0
                    agent._thinking_prefill_retries = 0
                    agent._last_content_with_tools = None
                    agent._last_content_tools_all_housekeeping = False
                    agent._mute_post_response = False

    if _preflight_compressed:
        current_turn_user_idx = reanchor_current_turn_user_idx(
            messages, user_message
        )
        agent._persist_user_message_idx = current_turn_user_idx

    plugin_user_context = ""
    try:
        from daedalus_cli.lifecycle import invoke_hook as _invoke_hook
        _pre_results = _invoke_hook(
            "pre_llm_call",
            session_id=agent.session_id,
            task_id=effective_task_id,
            turn_id=turn_id,
            user_message=original_user_message,
            conversation_history=list(messages),
            is_first_turn=(not bool(conversation_history)),
            model=agent.model,
            platform=getattr(agent, "platform", None) or "",
            parent_session_id=getattr(agent, "_parent_session_id", None) or "",
            sender_id=getattr(agent, "_user_id", None) or "",
        )
        _ctx_parts: list[str] = []
        try:
            from tools.hook_output_spill import (
                get_spill_config as _spill_cfg,
                spill_if_oversized as _spill_if_oversized,
            )
            _spill_config_cached = _spill_cfg()
        except Exception:
            _spill_if_oversized = None  # type: ignore[assignment]
            _spill_config_cached = None
        for r in _pre_results:
            _piece: str = ""
            if isinstance(r, dict) and r.get("context"):
                _piece = str(r["context"])
            elif isinstance(r, str) and r.strip():
                _piece = r
            else:
                continue
            if _spill_if_oversized is not None:
                try:
                    _piece = _spill_if_oversized(
                        _piece,
                        session_id=agent.session_id,
                        source="plugin hook",
                        config=_spill_config_cached,
                    )
                except Exception as _spill_exc:
                    logger.warning("hook context spill failed: %s", _spill_exc)
            _ctx_parts.append(_piece)
        if _ctx_parts:
            plugin_user_context = "\n\n".join(_ctx_parts)
    except Exception as exc:
        logger.warning("pre_llm_call hook failed: %s", exc)

    _gateway_notes = consume_gateway_turn_context_notes(agent)
    if _gateway_notes:
        _gw_turn_content = (
            messages[current_turn_user_idx].get("content")
            if 0 <= current_turn_user_idx < len(messages)
            and isinstance(messages[current_turn_user_idx], dict)
            else None
        )
        if isinstance(_gw_turn_content, list):
            append_notes_to_multimodal_content(_gw_turn_content, _gateway_notes)
        else:
            plugin_user_context = (
                plugin_user_context + "\n\n" + _gateway_notes
                if plugin_user_context
                else _gateway_notes
            )

    agent._turn_failed_file_mutations = {}
    agent._turn_file_mutation_paths = set()
    agent._verification_stop_nudges = 0
    agent._pre_verify_nudges = 0

    agent._execution_thread_id = threading.current_thread().ident

    ra()._set_interrupt(False, agent._execution_thread_id)
    if agent._interrupt_requested:
        ra()._set_interrupt(True, agent._execution_thread_id)
        agent._interrupt_thread_signal_pending = False
    else:
        agent._interrupt_message = None
        agent._interrupt_thread_signal_pending = False

    if agent._memory_manager:
        try:
            _turn_msg = original_user_message if isinstance(original_user_message, str) else ""
            agent._memory_manager.on_turn_start(agent._user_turn_count, _turn_msg)
        except Exception:
            pass

    ext_prefetch_cache = ""
    _pony = getattr(agent, "_pony_mode", None)
    if _pony is not None and getattr(_pony, "enabled", False):
        try:
            _pq = original_user_message if isinstance(original_user_message, str) else ""
            if not is_trivial_prompt(_pq):
                ext_prefetch_cache = _pony.material_for(_pq) or ""
        except Exception:
            ext_prefetch_cache = ""
    if not ext_prefetch_cache and agent._memory_manager:
        try:
            _query = original_user_message if isinstance(original_user_message, str) else ""
            if not is_trivial_prompt(_query):
                ext_prefetch_cache = agent._memory_manager.prefetch_all(_query) or ""
        except Exception:
            pass

    if (
        not moa_active
        and getattr(agent, "api_mode", None) != "codex_app_server"
        and 0 <= current_turn_user_idx < len(messages)
        and messages[current_turn_user_idx].get("role") == "user"
    ):
        _turn_user_msg = messages[current_turn_user_idx]
        _api_content = compose_user_api_content(
            _turn_user_msg.get("content", ""), ext_prefetch_cache, plugin_user_context
        )
        if _api_content is not None and _api_content != _turn_user_msg.get("content"):
            _turn_user_msg["api_content"] = _api_content
            if _preflight_compressed and bool(
                getattr(agent, "_last_compaction_in_place", False)
            ):
                _db = getattr(agent, "_session_db", None)
                if _db is not None:
                    try:
                        _db.set_latest_user_api_content(
                            agent.session_id,
                            _turn_user_msg.get("content"),
                            _api_content,
                        )
                    except Exception:
                        logger.warning(
                            "in-place compaction api_content backfill failed "
                            "for session=%s",
                            agent.session_id or "none",
                            exc_info=True,
                        )

    def _ensure_and_persist() -> None:
        agent._ensure_db_session()
        agent._persist_session(messages, conversation_history)

    try:
        if persist_lock is None:
            _ensure_and_persist()
        else:
            with persist_lock:
                _ensure_and_persist()
    except Exception:
        logger.warning(
            "Early turn-start session persistence failed for session=%s",
            agent.session_id or "none",
            exc_info=True,
        )
    finally:
        if not isinstance(pending_cli_message, dict) or pending_cli_message.get("_db_persisted"):
            agent._pending_cli_user_message = None

    return TurnContext(
        user_message=user_message,
        original_user_message=original_user_message,
        messages=messages,
        conversation_history=conversation_history,
        active_system_prompt=active_system_prompt,
        effective_task_id=effective_task_id,
        turn_id=turn_id,
        current_turn_user_idx=current_turn_user_idx,
        should_review_memory=should_review_memory,
        plugin_user_context=plugin_user_context,
        ext_prefetch_cache=ext_prefetch_cache,
        preflight_compression_blocked=_preflight_compression_blocked,
    )
