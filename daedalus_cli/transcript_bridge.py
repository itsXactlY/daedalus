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

from typing import Dict, Optional

from daedalus_cli.tool_result import ResultKind, classify_result
from daedalus_cli.transcript import (
    DiffBlock,
    MarkdownBlock,
    NoticeBlock,
    ResultBlock,
    ToolCallBlock,
    Transcript,
    TranscriptTheme,
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
        self._open_by_name: Dict[str, ToolCallBlock] = {}
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

    def tool_started(self, tool_call_id: str, name: str, preview: str = "") -> ToolCallBlock:
        """Open a call block. The duration stays unset until the tool returns."""
        block = ToolCallBlock(name, emoji=_emoji(name), preview=preview)
        self.transcript.append(block)
        # The agent's tool.started event carries no id -- only the tool name --
        # while tool_complete carries tool_call.id. Keying the open calls by
        # name as well as by id is what lets the completion find the header it
        # belongs to; otherwise every tool renders twice, once as a dangling
        # "started" line and again as an unpaired "completed" line.
        self._open_calls[tool_call_id or name] = block
        self._open_by_name[name] = block
        self.invalidate()
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
        """Close a call block and attach its result, and any diff it produced.

        The call block is mutated in place rather than replaced, so a reader
        watching a running tool sees the duration appear without the header
        moving or being reprinted.
        """
        block = self._open_calls.pop(tool_call_id, None)
        if block is None:
            # tool.started carries no call id, so fall back to the name.
            block = self._open_by_name.pop(name, None)
        else:
            self._open_by_name.pop(name, None)
        if block is None:
            block = ToolCallBlock(name, emoji=_emoji(name))
            self.transcript.append(block)
        block.duration = duration
        block.failed = failed

        result = (result or "").strip()
        if result:
            self.transcript.append(self._result_block(name, result))
        if diff and diff.strip():
            self.transcript.append(DiffBlock(
                diff,
                max_files=self._max_diff_files,
                max_lines=self._max_diff_lines,
            ))
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
                    MarkdownBlock(line, indent=2, style="class:transcript-dim"))
        self.invalidate()

    def flush_line(self) -> None:
        """Emit any buffered partial status line."""
        if self._line_buffer.strip():
            self.transcript.append(MarkdownBlock(
                self._line_buffer, indent=2, style="class:transcript-dim"))
        self._line_buffer = ""
        self.invalidate()

    # -- misc --------------------------------------------------------------

    def clear(self) -> None:
        self._open_calls.clear()
        self._open_by_name.clear()
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