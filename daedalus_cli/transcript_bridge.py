"""Bridges the agent's callbacks to the transcript.

Why a bridge
------------
The agent reports what it is doing through four plain callbacks -- tool
started, tool generating, tool complete, and a print function for its own
status lines. Turning those into rendered output is a translation, and it does
not belong in ``cli.py``: that file is already 9k lines of mixed concerns, and a
translation layer is exactly the kind of thing that needs its own tests.

This module owns that translation and nothing else. It never touches
prompt_toolkit, never prints, and never raises -- a rendering problem must not
be able to break a turn.

The shape of a tool in the transcript
-------------------------------------
    | read  notes.md  0.4s          <- ToolCallBlock
      <result rendered as Markdown>  <- MarkdownBlock, indented
      <diff, if the tool wrote>      <- DiffBlock

The call block is created when the tool starts and mutated when it finishes,
so a tool that is still running shows its header without a duration, and the
duration and failure marker appear in place when the result arrives. Nothing is
re-printed; the block just re-renders.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from daedalus_cli.tool_result import ResultKind, classify_result
from daedalus_cli.transcript import (
    DiffBlock,
    MarkdownBlock,
    NoticeBlock,
    ResultBlock,
    ToolCallBlock,
    Transcript,
    TranscriptTheme,
    strip_ansi,
)

__all__ = ["TranscriptBridge"]


#: Tool results longer than this are truncated before Markdown parsing. Tool
#: output is routinely megabytes (a directory listing, a JSON API response) and
#: rendering all of it would stall the UI on every paint.
DEFAULT_RESULT_MAX_CHARS = 8000


class TranscriptBridge:
    """Translates agent callbacks into transcript blocks."""

    def __init__(
        self,
        transcript: Transcript,
        *,
        theme: Optional[TranscriptTheme] = None,
        result_max_chars: int = DEFAULT_RESULT_MAX_CHARS,
        result_max_lines: int = 0,
        result_indent: int = 2,
        max_diff_files: int = 6,
        max_diff_lines: int = 80,
    ) -> None:
        self.transcript = transcript
        if theme is not None:
            transcript.set_theme(theme)
        self._result_max_chars = result_max_chars
        #: 0 = show every line. A cap belongs here rather than being implied by
        #: a character budget, because a result of many short lines can be
        #: small in characters and still taller than the screen.
        self._result_max_lines = result_max_lines
        self._result_indent = result_indent
        self._max_diff_files = max_diff_files
        self._max_diff_lines = max_diff_lines
        #: tool_call_id -> the call block being built, so its duration can be
        #: filled in when the tool returns
        self._open_calls: Dict[str, ToolCallBlock] = {}
        #: tool name -> the block currently running, because tool.started does
        #: not carry a call id while tool_complete does
        #: (a queue, so two parallel calls to the same tool cannot collide)
        self._open_by_name: Dict[str, List[ToolCallBlock]] = {}
        #: tool name -> calls whose arguments are still being written
        self._preparing: Dict[str, List[ToolCallBlock]] = {}
        #: the assistant block currently receiving streamed tokens
        self._assistant_block: Optional[MarkdownBlock] = None
        #: buffers for the pretty-printed status line the agent prints
        self._line_buffer = ""

    # -- assistant text ----------------------------------------------------

    def begin_assistant(self) -> MarkdownBlock:
        """Start a new assistant block and make it the stream target."""
        block = MarkdownBlock(style="class:transcript-text")
        self.transcript.append(block)
        self._assistant_block = block
        return block

    def append_assistant(self, text: str) -> None:
        """Append streamed assistant text, opening a block on demand."""
        if not text:
            return
        if self._assistant_block is None:
            self.begin_assistant()
        self._assistant_block.append(text)
        self.invalidate()

    def end_assistant(self) -> None:
        self._assistant_block = None

    # -- tool lifecycle ----------------------------------------------------

    def tool_preparing(self, name: str) -> ToolCallBlock:
        """The model has started writing a call's arguments: show it, dimmed."""
        block = ToolCallBlock(name, emoji=_emoji(name), state="preparing")
        self.transcript.append(block)
        self._preparing.setdefault(name, []).append(block)
        self.invalidate()
        return block

    def tool_started(self, tool_call_id: str, name: str, preview: str = "") -> ToolCallBlock:
        """The tool is executing. Upgrades the block that was preparing, if any.

        One call is one block from first mention to result; nothing is appended
        a second time.
        """
        queue = self._preparing.get(name)
        if queue:
            block = queue.pop(0)
            block.preview = preview
            block.state = "running"
            block.invalidate()
        else:
            block = ToolCallBlock(name, emoji=_emoji(name), preview=preview)
            self.transcript.append(block)
        block.started_at = time.monotonic()
        # The agent's tool.started event carries no id -- only the tool name --
        # while tool_complete carries tool_call.id, so open calls are findable
        # by either.
        self._open_calls[tool_call_id or name] = block
        self._open_by_name.setdefault(name, []).append(block)
        self.invalidate()
        return block

    def _take_open(self, tool_call_id: str, name: str) -> Optional[ToolCallBlock]:
        block = self._open_calls.pop(tool_call_id, None)
        queue = self._open_by_name.get(name) or []
        if block is None:
            block = queue.pop(0) if queue else None
        else:
            for i, candidate in enumerate(queue):
                if candidate is block:
                    del queue[i]
                    break
        if block is not None:
            for key in [k for k, v in self._open_calls.items() if v is block]:
                del self._open_calls[key]
        return block

    def tool_completed(
        self,
        tool_call_id: str,
        name: str,
        result: str = "",
        *,
        failed: bool = False,
        duration: Optional[float] = None,
        diff: str = "",
    ) -> None:
        """Close a call and attach its result and diff to it.

        The result lives INSIDE the call block, so it renders under its own
        header however many tools ran in parallel and in whatever order they
        finished. The duration is measured here when the caller has none.
        """
        block = self._take_open(tool_call_id, name)
        if block is None:
            block = ToolCallBlock(name, emoji=_emoji(name))
            self.transcript.append(block)
        if duration is None and block.started_at is not None:
            duration = time.monotonic() - block.started_at
        block.duration = duration
        block.failed = failed
        block.state = "done"

        result = (result or "").strip()
        if result:
            block.add_child(self._result_block(name, result))
        if diff and diff.strip():
            block.add_child(DiffBlock(
                diff,
                max_files=self._max_diff_files,
                max_lines=self._max_diff_lines,
            ))
        block.invalidate()
        self.invalidate()

    def _result_block(self, name: str, result: str) -> ResultBlock:
        """Classify a result and build the block that shows it.

        Classification is not cosmetic. Handing a shell listing to the Markdown
        renderer reflowed it into an unreadable paragraph and printed the ``\\n``
        escapes inside a JSON result as literal characters; the same was true of
        every stack trace and diff. Fencing code and data preserves their line
        structure, and keeps prose on the Markdown path where it belongs.
        """
        classified = classify_result(result, tool_name=name)
        if classified.kind is ResultKind.EMPTY:
            return ResultBlock("", kind="code")
        return ResultBlock(
            classified.text,
            language=classified.language,
            kind=classified.kind.value,
            indent=self._result_indent,
            max_chars=self._result_max_chars,
            max_lines=self._result_max_lines,
        )

    # -- status lines ------------------------------------------------------

    def notice(self, text: str, *, level: str = "info") -> None:
        for line in (text or "").rstrip("\n").split("\n"):
            if line.strip():
                self.transcript.append(NoticeBlock(line, level=level))
        self.invalidate()

    def print_line(self, text: str) -> None:
        """Stand-in for the agent's ``_print_fn``.

        The agent prints its own status lines ("running 3 commands…") through
        a callable it was handed. Pointing that at the transcript instead of
        ``_cprint`` is what keeps tool chatter out of the print path, and
        therefore out of the renderer teardown that shatters the skin.

        Lines are buffered until a newline arrives so a status line that is
        printed in pieces still lands as one block.
        """
        if text is None:
            return
        self._line_buffer += str(text)
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            if line.strip():
                self.transcript.append(
                    MarkdownBlock(strip_ansi(line), indent=2, style="class:transcript-dim"))
        self.invalidate()

    def flush_line(self) -> None:
        """Emit any buffered partial status line."""
        if self._line_buffer.strip():
            self.transcript.append(MarkdownBlock(
                strip_ansi(self._line_buffer), indent=2, style="class:transcript-dim"))
        self._line_buffer = ""
        self.invalidate()

    # -- misc --------------------------------------------------------------

    def clear(self) -> None:
        self._open_calls.clear()
        self._open_by_name.clear()
        self._preparing.clear()
        self._assistant_block = None
        self._line_buffer = ""

    def invalidate(self) -> None:
        """Ask the UI to repaint. No-op outside a running application."""
        try:
            from prompt_toolkit.application import get_app
            app = get_app()
        except Exception:
            return
        if app is not None:
            app.invalidate()


def _emoji(name: str) -> str:
    try:
        from agent.display import get_tool_emoji
        return get_tool_emoji(name, default="")
    except Exception:
        return ""