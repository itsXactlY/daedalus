"""Automatic context window compression for long conversations.

Self-contained class with its own OpenAI client for summarization.
Uses auxiliary model (cheap/fast) to summarize middle turns while
protecting head and tail context.

Improvements over v1:
  - Structured summary template (Goal, Progress, Decisions, Files, Next Steps)
  - Iterative summary updates (preserves info across multiple compactions)
  - Token-budget tail protection instead of fixed message count
  - Tool output pruning before LLM summarization (cheap pre-pass)
  - Scaled summary budget (proportional to compressed content)
  - Richer tool call/result detail in summarizer input
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from agent.auxiliary_client import call_llm
from agent.model_metadata import (
    get_model_context_length,
    is_local_endpoint,
    estimate_messages_tokens_rough,
)

logger = logging.getLogger(__name__)

SUMMARY_PREFIX = (
    "[CONTEXT COMPACTION] Earlier turns in this conversation were compacted "
    "to save context space. The summary below describes work that was "
    "already completed, and the current session state may still reflect "
    "that work (for example, files may already be changed). Use the summary "
    "and the current state to continue from where things left off, and "
    "avoid repeating work:"
)
LEGACY_SUMMARY_PREFIX = "[CONTEXT SUMMARY]:"

_MIN_SUMMARY_TOKENS = 2000
_SUMMARY_RATIO = 0.20
_SUMMARY_TOKENS_CEILING = 12_000

_PRUNED_TOOL_PLACEHOLDER = "[Old tool output cleared to save context space]"
_PRUNE_START_RATIO = 0.5
_LIVE_WINDOW_MESSAGES = 12
_LIVE_WINDOW_FLOOR = 4
_LIVE_WINDOW_BUDGET_RATIO = 0.5
_PRUNE_MIN_CHARS = 2000
_OFFLOAD_PREFIX = "[offloaded: "
_SPILLED_ARG_KEY = "_spilled_to"
_SPILL_VALUE_MIN_CHARS = 800
_SUBJECT_KEYS = ("file_path", "path", "command", "query", "url", "name")

_CHARS_PER_TOKEN = 4
_SUMMARY_FAILURE_COOLDOWN_SECONDS = 600


class ContextCompressor:
    """Compresses conversation context when approaching the model's context limit.

    Algorithm:
      1. Prune old tool results (cheap, no LLM call)
      2. Protect head messages (system prompt + first exchange)
      3. Protect tail messages by token budget (most recent ~20K tokens)
      4. Summarize middle turns with structured LLM prompt
      5. On subsequent compactions, iteratively update the previous summary
    """

    def __init__(
        self,
        model: str,
        threshold_percent: float = 0.50,
        protect_first_n: int = 3,
        protect_last_n: int = 20,
        summary_target_ratio: float = 0.20,
        quiet_mode: bool = False,
        summary_model_override: str = None,
        base_url: str = "",
        api_key: str = "",
        config_context_length: int | None = None,
        provider: str = "",
        max_tokens: int | None = None,
        archiver: Any = None,
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.provider = provider
        self.threshold_percent = threshold_percent
        self.max_tokens = max_tokens if max_tokens and max_tokens > 0 else None
        self.archiver = archiver
        self.protect_first_n = protect_first_n
        self.protect_last_n = protect_last_n
        self.summary_target_ratio = max(0.10, min(summary_target_ratio, 0.80))
        self.quiet_mode = quiet_mode

        self.context_length = get_model_context_length(
            model, base_url=base_url, api_key=api_key,
            config_context_length=config_context_length,
            provider=provider,
        )
        self.threshold_tokens = self._effective_threshold(self.context_length)
        self.compression_count = 0
        self.session_label = "session"
        self._offload_seq = 0
        self.offloaded: List[Dict[str, Any]] = []
        self.live_window_messages = _LIVE_WINDOW_MESSAGES

        target_tokens = int(self.threshold_tokens * self.summary_target_ratio)
        self.tail_token_budget = target_tokens
        self.max_summary_tokens = min(
            int(self.context_length * 0.05), _SUMMARY_TOKENS_CEILING,
        )

        if not quiet_mode:
            logger.info(
                "Context compressor initialized: model=%s context_length=%d "
                "threshold=%d (%.0f%%) target_ratio=%.0f%% tail_budget=%d "
                "provider=%s base_url=%s",
                model, self.context_length, self.threshold_tokens,
                threshold_percent * 100, self.summary_target_ratio * 100,
                self.tail_token_budget,
                provider or "none", base_url or "none",
            )
        self._context_probed = False
        self._config_context_length = config_context_length
        self._ctx_refreshed_at = time.monotonic()

        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0

        self.summary_model = summary_model_override or ""

        self._previous_summary: Optional[str] = None
        self._summary_failure_cooldown_until: float = 0.0

    CTX_REFRESH_INTERVAL = 300

    def maybe_refresh_context_length(self) -> bool:
        """Re-detect context length from a local server that may have reloaded.

        No-ops unless all of these hold:
          * the endpoint is local (remote model limits do not change under us),
          * no explicit config override is set (the user's number wins),
          * ``_context_probed`` is False -- a step-down from a real context
            error is a discovered hard limit and must never be raised back up,
          * ``CTX_REFRESH_INTERVAL`` has elapsed.

        Returns True when the value actually changed.
        """
        if self._config_context_length is not None or self._context_probed:
            return False
        if not self.base_url or not is_local_endpoint(self.base_url):
            return False
        now = time.monotonic()
        if now - self._ctx_refreshed_at < self.CTX_REFRESH_INTERVAL:
            return False
        self._ctx_refreshed_at = now
        try:
            detected = get_model_context_length(
                self.model, base_url=self.base_url, api_key=self.api_key,
                provider=self.provider,
            )
        except Exception as exc:
            logger.debug("Context length refresh failed: %s", exc)
            return False
        if not detected or detected <= 0 or detected == self.context_length:
            return False
        old = self.context_length
        self.context_length = detected
        self.threshold_tokens = self._effective_threshold(detected)
        self.max_summary_tokens = min(
            int(detected * 0.05), _SUMMARY_TOKENS_CEILING,
        )
        logger.info(
            "Context length re-detected from %s: %s -> %s tokens",
            self.base_url, f"{old:,}", f"{detected:,}",
        )
        return True

    def _effective_threshold(self, context_length: int) -> int:
        """Compression trigger, capped by max_tokens when one is configured.

        A declared window the hardware cannot hold in KV cache makes the
        percentage alone useless: the box swaps long before 95% of a 256K
        window is reached. max_tokens is that hardware ceiling.
        """
        by_percent = int(context_length * self.threshold_percent)
        if self.max_tokens:
            return max(1, min(by_percent, self.max_tokens))
        return by_percent


    def update_from_response(self, usage: Dict[str, Any]):
        """Update tracked token usage from API response.

        Guards against a real usage object with a missing/zero prompt_tokens
        field (seen with some OpenAI-compatible providers, e.g. DeepSeek,
        when a streamed response's usage payload omits prompt_tokens on a
        given call): treating that as "prompt size dropped to 0" silently
        wiped the tracked context size and the status bar showed it reset to
        near-zero until the next fully-populated response. A single call
        missing usage data is far more likely than the actual prompt
        shrinking, so keep the previous value in that case instead of
        overwriting it with a spurious 0.
        """
        self.maybe_refresh_context_length()
        new_prompt_tokens = usage.get("prompt_tokens", 0)
        if new_prompt_tokens:
            self.last_prompt_tokens = new_prompt_tokens
        new_completion_tokens = usage.get("completion_tokens", 0)
        if new_completion_tokens:
            self.last_completion_tokens = new_completion_tokens
        new_total_tokens = usage.get("total_tokens", 0)
        if new_total_tokens:
            self.last_total_tokens = new_total_tokens

    def should_compress(self, prompt_tokens: int = None) -> bool:
        """Check if context exceeds the compression threshold."""
        tokens = prompt_tokens if prompt_tokens is not None else self.last_prompt_tokens
        return tokens >= self.threshold_tokens

    def should_compress_preflight(self, messages: List[Dict[str, Any]]) -> bool:
        """Quick pre-flight check using rough estimate (before API call)."""
        rough_estimate = estimate_messages_tokens_rough(messages)
        return rough_estimate >= self.threshold_tokens

    def get_status(self) -> Dict[str, Any]:
        """Get current compression status for display/logging."""
        return {
            "last_prompt_tokens": self.last_prompt_tokens,
            "threshold_tokens": self.threshold_tokens,
            "context_length": self.context_length,
            "usage_percent": min(100, (self.last_prompt_tokens / self.context_length * 100)) if self.context_length else 0,
            "compression_count": self.compression_count,
        }


    def _prune_old_tool_results(
        self, messages: List[Dict[str, Any]], protect_tail_count: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Replace old tool result contents with a short placeholder.

        Walks backward from the end, protecting the most recent
        ``protect_tail_count`` messages. Older tool results get their
        content replaced with a placeholder string.

        Returns (pruned_messages, pruned_count).
        """
        if not messages:
            return messages, 0

        result = [m.copy() for m in messages]
        pruned = 0
        prune_boundary = len(result) - protect_tail_count

        for i in range(prune_boundary):
            msg = result[i]
            if msg.get("role") != "tool":
                continue
            content = msg.get("content", "")
            if not content or content == _PRUNED_TOOL_PLACEHOLDER:
                continue
            if len(content) > 200:
                result[i] = {**msg, "content": _PRUNED_TOOL_PLACEHOLDER}
                pruned += 1

        return result, pruned


    def prune_stale_tool_results(
        self, messages: List[Dict[str, Any]], current_tokens: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Move bulky tool results out of the live window as soon as they age.

        The harness does not carry its own transcript: only the newest
        ``live_window_messages`` stay in the payload. Anything older that is
        bulky goes to tmpfs immediately -- waiting for a compression threshold
        means hauling every file ever read until the window is nearly full,
        which is the KV-cache problem this exists to avoid. Without an archiver
        there is nowhere to put it, so the old pressure gate still applies.
        """
        if not messages:
            return messages, 0
        if not self.archiver and current_tokens < self.threshold_tokens * _PRUNE_START_RATIO:
            return messages, 0
        tail = self._adaptive_tail(messages)
        if len(messages) <= tail:
            return messages, 0

        names = self._tool_call_names(messages)
        subjects = self._tool_call_subjects(messages)
        result = [m.copy() for m in messages]
        pruned = 0
        archived = 0
        for i in range(len(result) - tail):
            msg = result[i]
            if msg.get("role") != "tool":
                continue
            content = msg.get("content", "")
            if not content or self._is_offloaded(content):
                continue
            if len(content) < _PRUNE_MIN_CHARS:
                continue
            handle = None
            if self.archiver:
                handle = self._offload(names.get(msg.get("tool_call_id")), content,
                                       subjects.get(msg.get("tool_call_id"), ""))
                if handle:
                    archived += 1
            result[i] = {**msg, "content": handle or _PRUNED_TOOL_PLACEHOLDER}
            pruned += 1

        if self.archiver:
            for i in range(len(result) - tail):
                calls = result[i].get("tool_calls")
                if not calls:
                    continue
                new_calls, changed = self._spill_call_arguments(calls)
                if changed:
                    result[i] = {**result[i], "tool_calls": new_calls}
                    pruned += changed

        return (result, pruned) if pruned else (messages, 0)

    def _spill_call_arguments(self, calls: List[Any]) -> Tuple[List[Any], int]:
        """Move the bulky values out of a tool call, keep the identifying ones.

        Once results are spilled the model's own arguments dominate -- a
        write_file call carries the whole file. Spilling the blob wholesale
        would take file_path with it, leaving the model unable to tell one
        call from the next. So only oversized values move; small scalars stay
        inline and the result is still valid JSON, which consumers json.loads.
        """
        out: List[Any] = []
        changed = 0
        for call in calls:
            if not isinstance(call, dict):
                out.append(call)
                continue
            fn = call.get("function") or {}
            raw = fn.get("arguments")
            if not isinstance(raw, str) or len(raw) < _PRUNE_MIN_CHARS:
                out.append(call)
                continue
            if _SPILLED_ARG_KEY in raw:
                out.append(call)
                continue
            name = fn.get("name") or "tool"
            replacement = self._spill_large_values(name, raw)
            if replacement is None:
                out.append(call)
                continue
            out.append({**call, "function": {**fn, "arguments": replacement}})
            changed += 1
        return out, changed

    def _spill_large_values(self, tool_name: str, raw: str) -> Optional[str]:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

        if not isinstance(parsed, dict):
            path = self._write_spill(f"{tool_name}-args", raw)
            if not path:
                return None
            self.offloaded.append({"path": str(path), "chars": len(raw),
                                   "tool": f"{tool_name} (arguments)"})
            return json.dumps({_SPILLED_ARG_KEY: str(path), "bytes": len(raw),
                               "note": "arguments spilled from context; "
                                       "read_file(path) to see them"})

        slim: Dict[str, Any] = {}
        moved = False
        for key, value in parsed.items():
            if isinstance(value, str) and len(value) >= _SPILL_VALUE_MIN_CHARS:
                path = self._write_spill(f"{tool_name}-{key}", value)
                if not path:
                    slim[key] = value
                    continue
                self.offloaded.append({"path": str(path), "chars": len(value),
                                       "tool": f"{tool_name}.{key}"})
                slim[key] = {_SPILLED_ARG_KEY: str(path), "bytes": len(value),
                             "note": "read_file(path) to see this value"}
                moved = True
            else:
                slim[key] = value
        if not moved:
            return None
        return json.dumps(slim)

    def _write_spill(self, tool_name: str, content: str) -> Optional[str]:
        try:
            path = self.archiver(self.session_label, self._offload_seq,
                                 tool_name, content)
        except Exception as exc:
            logger.debug("Spill failed for %s: %s", tool_name, exc)
            return None
        if path:
            self._offload_seq += 1
        return path

    def _adaptive_tail(self, messages: List[Dict[str, Any]]) -> int:
        """How many of the newest messages stay untouched.

        A fixed message count was the wrong unit: after a compaction the list
        is ~10 messages long, so a 12-message tail protected everything while
        those same ten messages carried 40k tokens of freshly re-read files.
        The spill could never engage and compression fired instead, forever
        (observed 2026-09-03). The tail therefore shrinks toward
        _LIVE_WINDOW_FLOOR until what it protects fits the byte budget.
        """
        tail = min(self.live_window_messages, len(messages))
        budget = self.live_window_chars
        if budget <= 0:
            return tail
        while tail > _LIVE_WINDOW_FLOOR and self._payload_chars(messages[-tail:]) > budget:
            tail -= 1
        return tail

    @property
    def live_window_chars(self) -> int:
        if self.threshold_tokens <= 0:
            return 0
        return int(self.threshold_tokens * 4 * _LIVE_WINDOW_BUDGET_RATIO)

    @staticmethod
    def _payload_chars(messages: List[Dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            total += len(str(msg.get("content") or ""))
            for call in (msg.get("tool_calls") or ()):
                if isinstance(call, dict):
                    fn = call.get("function") or {}
                    total += len(str(fn.get("arguments") or ""))
        return total

    @staticmethod
    def _tool_call_names(messages: List[Dict[str, Any]]) -> Dict[str, str]:
        names: Dict[str, str] = {}
        for msg in messages:
            for call in (msg.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                if call.get("id"):
                    names[call["id"]] = fn.get("name") or "tool"
        return names

    @staticmethod
    def _is_offloaded(content: str) -> bool:
        return (content == _PRUNED_TOOL_PLACEHOLDER
                or content.startswith(_OFFLOAD_PREFIX))

    @classmethod
    def _tool_call_subjects(cls, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        """What each call was about, so a spilled result stays identifiable."""
        subjects: Dict[str, str] = {}
        for msg in messages:
            for call in (msg.get("tool_calls") or []):
                if not isinstance(call, dict) or not call.get("id"):
                    continue
                fn = call.get("function") or {}
                subjects[call["id"]] = cls._describe_arguments(fn.get("arguments"))
        return subjects

    @staticmethod
    def _describe_arguments(raw: Any) -> str:
        if not isinstance(raw, str) or not raw.strip():
            return ""
        try:
            parsed = json.loads(raw)
        except Exception:
            return ""
        if not isinstance(parsed, dict):
            return ""
        for key in _SUBJECT_KEYS:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                flat = " ".join(value.split())
                return flat if len(flat) <= 120 else flat[:117] + "..."
        return ""

    def _offload(self, tool_name: str, content: str, subject: str = "") -> Optional[str]:
        """Spill a tool result to tmpfs and keep a path the model can read.

        Deleting it is amnesia, carrying it is the KV cache problem. RAM-backed
        tmpfs is neither: the bytes leave the window, stay one read_file away,
        and never touch disk or long-term memory -- tool churn does not belong
        in a semantic graph.
        """
        tool_name = tool_name or "tool"
        path = self._write_spill(tool_name, content)
        if not path:
            return None
        self.offloaded.append({"path": str(path), "tool": tool_name,
                               "chars": len(content), "subject": subject})
        about = f" for {subject}" if subject else ""
        return (f"{_OFFLOAD_PREFIX}{tool_name}{about} — result ({len(content)} chars) "
                f"spilled to {path}. Retrieve it verbatim with read_file(\"{path}\").]")

    def offload_notice(self, limit: int = 6) -> str:
        """One line naming what left the window, so the model can pull it back."""
        if not self.offloaded:
            return ""
        recent = self.offloaded[-limit:]
        items = ", ".join(f"{o['tool']}→{o['path']}" for o in recent)
        more = len(self.offloaded) - len(recent)
        tail = f" (+{more} older in the same directory)" if more else ""
        return (f"{len(self.offloaded)} bulky tool result(s) were spilled out of context "
                f"to tmpfs this session: {items}{tail}. "
                "Read one back with read_file(path) instead of re-running the tool.")


    def _compute_summary_budget(self, turns_to_summarize: List[Dict[str, Any]]) -> int:
        """Scale summary token budget with the amount of content being compressed.

        The maximum scales with the model's context window (5% of context,
        capped at ``_SUMMARY_TOKENS_CEILING``) so large-context models get
        richer summaries instead of being hard-capped at 8K tokens.
        """
        content_tokens = estimate_messages_tokens_rough(turns_to_summarize)
        budget = int(content_tokens * _SUMMARY_RATIO)
        return max(_MIN_SUMMARY_TOKENS, min(budget, self.max_summary_tokens))

    def _serialize_for_summary(self, turns: List[Dict[str, Any]]) -> str:
        """Serialize conversation turns into labeled text for the summarizer.

        Includes tool call arguments and result content (up to 3000 chars
        per message) so the summarizer can preserve specific details like
        file paths, commands, and outputs.
        """
        parts = []
        for msg in turns:
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""

            if role == "tool":
                tool_id = msg.get("tool_call_id", "")
                if len(content) > 3000:
                    content = content[:2000] + "\n...[truncated]...\n" + content[-800:]
                parts.append(f"[TOOL RESULT {tool_id}]: {content}")
                continue

            if role == "assistant":
                if len(content) > 3000:
                    content = content[:2000] + "\n...[truncated]...\n" + content[-800:]
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    tc_parts = []
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            fn = tc.get("function", {})
                            name = fn.get("name", "?")
                            args = fn.get("arguments", "")
                            if len(args) > 500:
                                args = args[:400] + "..."
                            tc_parts.append(f"  {name}({args})")
                        else:
                            fn = getattr(tc, "function", None)
                            name = getattr(fn, "name", "?") if fn else "?"
                            tc_parts.append(f"  {name}(...)")
                    content += "\n[Tool calls:\n" + "\n".join(tc_parts) + "\n]"
                parts.append(f"[ASSISTANT]: {content}")
                continue

            if len(content) > 3000:
                content = content[:2000] + "\n...[truncated]...\n" + content[-800:]
            parts.append(f"[{role.upper()}]: {content}")

        return "\n\n".join(parts)

    def _generate_summary(self, turns_to_summarize: List[Dict[str, Any]]) -> Optional[str]:
        """Generate a structured summary of conversation turns.

        Uses a structured template (Goal, Progress, Decisions, Files, Next Steps)
        inspired by Pi-mono and OpenCode. When a previous summary exists,
        generates an iterative update instead of summarizing from scratch.

        Returns None if all attempts fail — the caller should drop
        the middle turns without a summary rather than inject a useless
        placeholder.
        """
        now = time.monotonic()
        if now < self._summary_failure_cooldown_until:
            logger.debug(
                "Skipping context summary during cooldown (%.0fs remaining)",
                self._summary_failure_cooldown_until - now,
            )
            return None

        summary_budget = self._compute_summary_budget(turns_to_summarize)
        content_to_summarize = self._serialize_for_summary(turns_to_summarize)

        if self._previous_summary:
            prompt = f"""You are updating a context compaction summary. A previous compaction produced the summary below. New conversation turns have occurred since then and need to be incorporated.

PREVIOUS SUMMARY:
{self._previous_summary}

NEW TURNS TO INCORPORATE:
{content_to_summarize}

Update the summary using this exact structure. PRESERVE all existing information that is still relevant. ADD new progress. Move items from "In Progress" to "Done" when completed. Remove information only if it is clearly obsolete.

## Goal
[What the user is trying to accomplish — preserve from previous summary, update if goal evolved]

## Constraints & Preferences
[User preferences, coding style, constraints, important decisions — accumulate across compactions]

## Progress
### Done
[Completed work — include specific file paths, commands run, results obtained]
### In Progress
[Work currently underway]
### Blocked
[Any blockers or issues encountered]

## Key Decisions
[Important technical decisions and why they were made]

## Relevant Files
[Files read, modified, or created — with brief note on each. Accumulate across compactions.]

## Next Steps
[What needs to happen next to continue the work]

## Critical Context
[Any specific values, error messages, configuration details, or data that would be lost without explicit preservation]

Target ~{summary_budget} tokens. Be specific — include file paths, command outputs, error messages, and concrete values rather than vague descriptions.

Write only the summary body. Do not include any preamble or prefix."""
        else:
            prompt = f"""Create a structured handoff summary for a later assistant that will continue this conversation after earlier turns are compacted.

TURNS TO SUMMARIZE:
{content_to_summarize}

Use this exact structure:

## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
[User preferences, coding style, constraints, important decisions]

## Progress
### Done
[Completed work — include specific file paths, commands run, results obtained]
### In Progress
[Work currently underway]
### Blocked
[Any blockers or issues encountered]

## Key Decisions
[Important technical decisions and why they were made]

## Relevant Files
[Files read, modified, or created — with brief note on each]

## Next Steps
[What needs to happen next to continue the work]

## Critical Context
[Any specific values, error messages, configuration details, or data that would be lost without explicit preservation]

Target ~{summary_budget} tokens. Be specific — include file paths, command outputs, error messages, and concrete values rather than vague descriptions. The goal is to prevent the next assistant from repeating work or losing important details.

Write only the summary body. Do not include any preamble or prefix."""

        try:
            call_kwargs = {
                "task": "compression",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": summary_budget * 2,
            }
            if self.summary_model:
                call_kwargs["model"] = self.summary_model
            response = call_llm(**call_kwargs)
            content = response.choices[0].message.content
            if not isinstance(content, str):
                content = str(content) if content else ""
            summary = content.strip()
            self._previous_summary = summary
            self._summary_failure_cooldown_until = 0.0
            return self._with_summary_prefix(summary)
        except RuntimeError:
            self._summary_failure_cooldown_until = time.monotonic() + _SUMMARY_FAILURE_COOLDOWN_SECONDS
            logging.warning("Context compression: no provider available for "
                            "summary. Middle turns will be dropped without summary "
                            "for %d seconds.",
                            _SUMMARY_FAILURE_COOLDOWN_SECONDS)
            return None
        except Exception as e:
            self._summary_failure_cooldown_until = time.monotonic() + _SUMMARY_FAILURE_COOLDOWN_SECONDS
            logging.warning(
                "Failed to generate context summary: %s. "
                "Further summary attempts paused for %d seconds.",
                e,
                _SUMMARY_FAILURE_COOLDOWN_SECONDS,
            )
            return None

    @staticmethod
    def _with_summary_prefix(summary: str) -> str:
        """Normalize summary text to the current compaction handoff format."""
        text = (summary or "").strip()
        for prefix in (LEGACY_SUMMARY_PREFIX, SUMMARY_PREFIX):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break
        return f"{SUMMARY_PREFIX}\n{text}" if text else SUMMARY_PREFIX


    @staticmethod
    def _get_tool_call_id(tc) -> str:
        """Extract the call ID from a tool_call entry (dict or SimpleNamespace)."""
        if isinstance(tc, dict):
            return tc.get("id", "")
        return getattr(tc, "id", "") or ""

    def _sanitize_tool_pairs(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fix orphaned tool_call / tool_result pairs after compression.

        Two failure modes:
        1. A tool *result* references a call_id whose assistant tool_call was
           removed (summarized/truncated).  The API rejects this with
           "No tool call found for function call output with call_id ...".
        2. An assistant message has tool_calls whose results were dropped.
           The API rejects this because every tool_call must be followed by
           a tool result with the matching call_id.

        This method removes orphaned results and inserts stub results for
        orphaned calls so the message list is always well-formed.
        """
        surviving_call_ids: set = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    cid = self._get_tool_call_id(tc)
                    if cid:
                        surviving_call_ids.add(cid)

        result_call_ids: set = set()
        for msg in messages:
            if msg.get("role") == "tool":
                cid = msg.get("tool_call_id")
                if cid:
                    result_call_ids.add(cid)

        orphaned_results = result_call_ids - surviving_call_ids
        if orphaned_results:
            messages = [
                m for m in messages
                if not (m.get("role") == "tool" and m.get("tool_call_id") in orphaned_results)
            ]
            if not self.quiet_mode:
                logger.info("Compression sanitizer: removed %d orphaned tool result(s)", len(orphaned_results))

        missing_results = surviving_call_ids - result_call_ids
        if missing_results:
            patched: List[Dict[str, Any]] = []
            for msg in messages:
                patched.append(msg)
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls") or []:
                        cid = self._get_tool_call_id(tc)
                        if cid in missing_results:
                            patched.append({
                                "role": "tool",
                                "content": "[Result from earlier conversation — see context summary above]",
                                "tool_call_id": cid,
                            })
            messages = patched
            if not self.quiet_mode:
                logger.info("Compression sanitizer: added %d stub tool result(s)", len(missing_results))

        return messages

    def _align_boundary_forward(self, messages: List[Dict[str, Any]], idx: int) -> int:
        """Push a compress-start boundary forward past any orphan tool results.

        If ``messages[idx]`` is a tool result, slide forward until we hit a
        non-tool message so we don't start the summarised region mid-group.
        """
        while idx < len(messages) and messages[idx].get("role") == "tool":
            idx += 1
        return idx

    def _align_boundary_backward(self, messages: List[Dict[str, Any]], idx: int) -> int:
        """Pull a compress-end boundary backward to avoid splitting a
        tool_call / result group.

        If the boundary falls in the middle of a tool-result group (i.e.
        there are consecutive tool messages before ``idx``), walk backward
        past all of them to find the parent assistant message.  If found,
        move the boundary before the assistant so the entire
        assistant + tool_results group is included in the summarised region
        rather than being split (which causes silent data loss when
        ``_sanitize_tool_pairs`` removes the orphaned tail results).
        """
        if idx <= 0 or idx >= len(messages):
            return idx
        check = idx - 1
        while check >= 0 and messages[check].get("role") == "tool":
            check -= 1
        if check >= 0 and messages[check].get("role") == "assistant" and messages[check].get("tool_calls"):
            idx = check
        return idx


    def _find_tail_cut_by_tokens(
        self, messages: List[Dict[str, Any]], head_end: int,
        token_budget: int | None = None,
    ) -> int:
        """Walk backward from the end of messages, accumulating tokens until
        the budget is reached. Returns the index where the tail starts.

        ``token_budget`` defaults to ``self.tail_token_budget`` which is
        derived from ``summary_target_ratio * context_length``, so it
        scales automatically with the model's context window.

        Never cuts inside a tool_call/result group. Falls back to the old
        ``protect_last_n`` if the budget would protect fewer messages.
        """
        if token_budget is None:
            token_budget = self.tail_token_budget
        n = len(messages)
        min_tail = self.protect_last_n
        accumulated = 0
        cut_idx = n

        for i in range(n - 1, head_end - 1, -1):
            msg = messages[i]
            content = msg.get("content") or ""
            msg_tokens = len(content) // _CHARS_PER_TOKEN + 10
            for tc in msg.get("tool_calls") or []:
                if isinstance(tc, dict):
                    args = tc.get("function", {}).get("arguments", "")
                    msg_tokens += len(args) // _CHARS_PER_TOKEN
            if accumulated + msg_tokens > token_budget and (n - i) >= min_tail:
                break
            accumulated += msg_tokens
            cut_idx = i

        fallback_cut = n - min_tail
        if cut_idx > fallback_cut:
            cut_idx = fallback_cut

        if cut_idx <= head_end:
            cut_idx = fallback_cut

        cut_idx = self._align_boundary_backward(messages, cut_idx)

        return max(cut_idx, head_end + 1)


    def compress(self, messages: List[Dict[str, Any]], current_tokens: int = None) -> List[Dict[str, Any]]:
        """Compress conversation messages by summarizing middle turns.

        Algorithm:
          1. Prune old tool results (cheap pre-pass, no LLM call)
          2. Protect head messages (system prompt + first exchange)
          3. Find tail boundary by token budget (~20K tokens of recent context)
          4. Summarize middle turns with structured LLM prompt
          5. On re-compression, iteratively update the previous summary

        After compression, orphaned tool_call / tool_result pairs are cleaned
        up so the API never receives mismatched IDs.
        """
        n_messages = len(messages)
        if n_messages <= self.protect_first_n + self.protect_last_n + 1:
            if not self.quiet_mode:
                logger.warning(
                    "Cannot compress: only %d messages (need > %d)",
                    n_messages,
                    self.protect_first_n + self.protect_last_n + 1,
                )
            return messages

        display_tokens = current_tokens if current_tokens else self.last_prompt_tokens or estimate_messages_tokens_rough(messages)

        messages, pruned_count = self._prune_old_tool_results(
            messages, protect_tail_count=self.protect_last_n * 3,
        )
        if pruned_count and not self.quiet_mode:
            logger.info("Pre-compression: pruned %d old tool result(s)", pruned_count)

        compress_start = self.protect_first_n
        compress_start = self._align_boundary_forward(messages, compress_start)

        compress_end = self._find_tail_cut_by_tokens(messages, compress_start)

        if compress_start >= compress_end:
            return messages

        turns_to_summarize = messages[compress_start:compress_end]

        if not self.quiet_mode:
            logger.info(
                "Context compression triggered (%d tokens >= %d threshold)",
                display_tokens,
                self.threshold_tokens,
            )
            logger.info(
                "Model context limit: %d tokens (%.0f%% = %d)",
                self.context_length,
                self.threshold_percent * 100,
                self.threshold_tokens,
            )
            tail_msgs = n_messages - compress_end
            logger.info(
                "Summarizing turns %d-%d (%d turns), protecting %d head + %d tail messages",
                compress_start + 1,
                compress_end,
                len(turns_to_summarize),
                compress_start,
                tail_msgs,
            )

        summary = self._generate_summary(turns_to_summarize)

        compressed = []
        for i in range(compress_start):
            msg = messages[i].copy()
            if i == 0 and msg.get("role") == "system" and self.compression_count == 0:
                msg["content"] = (
                    (msg.get("content") or "")
                    + "\n\n[Note: Some earlier conversation turns have been compacted into a handoff summary to preserve context space. The current session state may still reflect earlier work, so build on that summary and state rather than re-doing work.]"
                )
            compressed.append(msg)

        _merge_summary_into_tail = False
        if summary:
            last_head_role = messages[compress_start - 1].get("role", "user") if compress_start > 0 else "user"
            first_tail_role = messages[compress_end].get("role", "user") if compress_end < n_messages else "user"
            if last_head_role in ("assistant", "tool"):
                summary_role = "user"
            else:
                summary_role = "assistant"
            if summary_role == first_tail_role:
                flipped = "assistant" if summary_role == "user" else "user"
                if flipped != last_head_role:
                    summary_role = flipped
                else:
                    _merge_summary_into_tail = True
            if not _merge_summary_into_tail:
                compressed.append({"role": summary_role, "content": summary})
        else:
            if not self.quiet_mode:
                logger.debug("No summary model available — middle turns dropped without summary")

        for i in range(compress_end, n_messages):
            msg = messages[i].copy()
            if _merge_summary_into_tail and i == compress_end:
                original = msg.get("content") or ""
                msg["content"] = summary + "\n\n" + original
                _merge_summary_into_tail = False
            compressed.append(msg)

        self.compression_count += 1

        compressed = self._sanitize_tool_pairs(compressed)

        if not self.quiet_mode:
            new_estimate = estimate_messages_tokens_rough(compressed)
            saved_estimate = display_tokens - new_estimate
            logger.info(
                "Compressed: %d -> %d messages (~%d tokens saved)",
                n_messages,
                len(compressed),
                saved_estimate,
            )
            logger.info("Compression #%d complete", self.compression_count)

        return compressed
