"""The transcript: an append-only log of a conversation, rendered as Markdown.

Why this exists
---------------
Everything the agent says or does used to be printed with ``_cprint``, which is
``prompt_toolkit.print_formatted_text``. prompt_toolkit implements that by
tearing the UI down (``renderer.erase()``, ``renderer.reset()``) and rebuilding
it, so every line of assistant text and every tool result cost a full repaint of
the skin-painted interface -- and, worse, repainted on top of it, which is what
made the skin look shattered during long turns.

A transcript is the alternative: a plain data structure that owns an ordered
list of blocks, and a widget that paints those blocks as part of the layout.
Nothing is printed, so there is nothing to tear down.

The design in one paragraph
---------------------------
:class:`Transcript` is the model, a list of :class:`Block` objects. A block knows
its source text and how to turn itself into prompt_toolkit fragments; it never
knows about the terminal, the skin, or when it is painted. Rendering is *lazy*
and *cached*: a block that has not changed returns its previous fragments, so a
token arriving every 20ms costs a dictionary lookup, not a Markdown parse.
Only a block whose text actually changed re-renders, and only when the widget
is next painted. That is what makes live Markdown streaming affordable.

Why Markdown
------------
Tool results are the part of an agent's output that most needs real formatting:
a JSON payload wants a fence and syntax highlighting, a file listing wants a
block, an error wants to be readable rather than buried. ``agent/display.py``
solved this with a ~180-line ``if``/``elif`` chain over ~24 tools that emitted
hand-built ANSI strings, and every new tool meant another branch. A Markdown
renderer is not per-tool, so it does not need per-tool branches: the tool's own
result text is already Markdown, and it renders as Markdown.

Blocks
------
``MarkdownBlock``   assistant text and tool results. The workhorse.
``ToolCallBlock``   the one-line ``| read foo.py`` header with its duration.
``DiffBlock``       a unified diff, coloured per line, capped.
``NoticeBlock``     status lines and errors that are not tool output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

__all__ = [
    "Block",
    "MarkdownBlock",
    "ToolCallBlock",
    "DiffBlock",
    "NoticeBlock",
    "Transcript",
    "TranscriptTheme",
    "render_markdown",
]


# --------------------------------------------------------------------------
# Theme
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TranscriptTheme:
    """Colours for the transcript, resolved from the active skin.

    Held as hex strings rather than prompt_toolkit style classes so the theme
    can be built and asserted without a running application. The widget turns
    these into style classes once, at layout build time.
    """

    label: str = "#DAA520"          # tool name, block headers
    accent: str = "#CD7F32"         # rules, prefixes
    dim: str = "#8B8682"            # durations, timestamps, chrome
    text: str = "#FFF8DC"           # body text
    error: str = "#ef5350"          # failures
    ok: str = "#4caf50"             # success markers
    diff_add: str = "#4caf50"
    diff_del: str = "#ef5350"
    diff_meta: str = "#4dd0e1"      # file headers, @@ hunks

    @classmethod
    def from_skin(cls, skin=None) -> "TranscriptTheme":
        """Build a theme from a skin, falling back to the defaults.

        Every lookup is tolerant: a skin that omits a key gets the default
        rather than an exception, so a partial custom skin cannot blank the
        conversation.
        """
        if skin is None:
            try:
                from daedalus_cli.skin_engine import get_active_skin
                skin = get_active_skin()
            except Exception:
                return cls()
        d = cls()
        try:
            return cls(
                label=skin.get_color("session_label", d.label),
                accent=skin.get_color("input_rule", d.accent),
                dim=skin.get_color("banner_dim", d.dim),
                text=skin.get_color("prompt", d.text),
                error=skin.get_color("ui_error", d.error),
                ok=skin.get_color("ui_ok", d.ok),
            )
        except Exception:
            return d


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove SGR escape sequences, leaving the printable text."""
    return _ANSI_RE.sub("", text or "")


def render_markdown(text: str, *, width: int = 80) -> str:
    """Render Markdown to ANSI-coloured plain text.

    Deliberately returns a *string*, not a rich renderable: the caller needs
    ANSI text to hand to prompt_toolkit's ``FormattedTextControl``, and going
    through rich's own buffer is the only way to get truecolor output without a
    live console.

    Width is explicit rather than read from the terminal because the transcript
    is laid out against prompt_toolkit's own width, which can disagree with
    ``shutil.get_terminal_size`` mid-resize.
    """
    text = text or ""
    if not text.strip():
        return ""
    try:
        from io import StringIO
        from rich.console import Console
        from rich.markdown import Markdown

        buf = StringIO()
        console = Console(
            file=buf,
            width=max(int(width), 20),
            force_terminal=True,
            color_system="truecolor",
            highlight=False,
            legacy_windows=False,
            soft_wrap=False,
        )
        console.print(Markdown(text))
        return buf.getvalue().rstrip("\n")
    except Exception:
        # A Markdown failure must never take the conversation down with it.
        # Plain text still communicates the content.
        return text


# --------------------------------------------------------------------------
# Blocks
# --------------------------------------------------------------------------

class Block:
    """One addressable piece of the conversation.

    Subclasses provide :meth:`_render`; this class handles the caching that
    makes repeated painting free. ``_cache_key`` must change whenever the
    block's visible content would change -- for a streamed block that is the
    text plus the width, because the same text wraps differently at a different
    width.
    """

    __slots__ = ("_cache_key", "_cached_fragments")

    def __init__(self) -> None:
        self._cache_key: object = None
        self._cached_fragments: List[Tuple[str, str]] = []

    # -- subclass hooks ----------------------------------------------------

    def _render(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        raise NotImplementedError

    def _cache_key_for(self, width: int, theme: TranscriptTheme) -> object:
        """Identity of the rendered output. Change it when content changes."""
        return (type(self).__name__, width)

    # -- public ------------------------------------------------------------

    def fragments(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        """Cached fragments for this block at *width*.

        This is the hot path: it runs on every repaint of every visible block,
        so the common path must be a comparison and a list return, not work.
        """
        key = self._cache_key_for(width, theme)
        if key == self._cache_key:
            return self._cached_fragments
        self._cache_key = key
        self._cached_fragments = self._render(width, theme)
        return self._cached_fragments

    def invalidate(self) -> None:
        """Force the next :meth:`fragments` call to re-render."""
        self._cache_key = None


class MarkdownBlock(Block):
    """Assistant text or a tool result, rendered as Markdown.

    The streaming case is the reason rendering is deferred rather than eager.
    Markdown is not parseable incrementally -- a half-received table or fence is
    not valid Markdown -- so the only correct way to show live Markdown is to
    hold the raw text and re-parse the whole block when it is painted. That is
    affordable because it happens once per paint, not once per token, and
    because :class:`Block` skips it entirely when the text has not changed.
    """

    __slots__ = ("text", "indent", "prefix", "style", "max_chars")

    def __init__(
        self,
        text: str = "",
        *,
        indent: int = 0,
        prefix: str = "",
        style: Optional[str] = None,
        max_chars: int = 0,
    ) -> None:
        super().__init__()
        self.text = text or ""
        #: leading spaces, so a tool result reads as nested under its call
        self.indent = indent
        #: a marker drawn on the first line, e.g. the skin's tool prefix
        self.prefix = prefix
        #: prompt_toolkit style class for the whole block, or None for theme text
        self.style = style
        #: 0 means unlimited. Truncation happens on the *raw* text, before
        #: Markdown parsing, so a truncated block still renders as valid
        #: Markdown rather than a broken half-table.
        self.max_chars = max_chars

    def append(self, text: str) -> None:
        """Add streamed text. The next paint re-renders the block."""
        self.text += text or ""

    def set_text(self, text: str) -> None:
        self.text = text or ""

    def _truncated(self) -> str:
        if self.max_chars and len(self.text) > self.max_chars:
            return self.text[: self.max_chars] + "\n… truncated"
        return self.text

    def _cache_key_for(self, width: int, theme: TranscriptTheme) -> object:
        return ("md", self.text, width, self.style, self.indent, self.prefix,
                self.max_chars, theme)

    def _render(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        body = render_markdown(self._truncated(), width=width)
        if not body:
            return []
        pad = " " * self.indent
        out: List[Tuple[str, str]] = []
        for i, line in enumerate(body.split("\n")):
            lead = self.prefix if (i == 0 and self.prefix) else ""
            text = f"{pad}{lead}{line}" if (pad or lead) else line
            style = self.style or "class:transcript-text"
            out.append((style, text))
        return out


class ResultBlock(Block):
    """A tool result, rendered according to what kind of thing it is.

    This exists because running every tool result through the Markdown parser
    is wrong for almost all of them. A Markdown renderer reflows prose: it
    joins what it considers a soft-wrapped line and re-wraps at the viewport
    width. Given a shell listing or a stack trace that produces the unreadable
    wall the TUI showed -- a source file squeezed into a single paragraph, and
    the ``\\n`` sequences inside a JSON result printed as literal characters.

    So the result is classified first (:mod:`daedalus_cli.tool_result`) and
    fenced accordingly. Prose still goes through Markdown; code and data are
    fenced, which preserves their line structure exactly and lets the theme
    colour them.
    """

    __slots__ = ("text", "language", "kind", "indent", "max_chars", "max_lines")

    def __init__(
        self,
        text: str = "",
        *,
        language: str = "",
        kind: str = "code",
        indent: int = 2,
        max_chars: int = 0,
        max_lines: int = 0,
    ) -> None:
        super().__init__()
        self.text = text or ""
        self.language = language
        self.kind = kind
        self.indent = indent
        #: 0 = unlimited. Applied to the raw text before rendering so a
        #: truncated result is still valid rather than half a fence.
        self.max_chars = max_chars
        #: 0 = unlimited. Rows shown before an explicit truncation note.
        self.max_lines = max_lines

    def set_text(self, text: str) -> None:
        self.text = text or ""

    def _prepared(self) -> str:
        body = self.text
        if self.max_chars and len(body) > self.max_chars:
            body = body[: self.max_chars]
            body += "\n… truncated"
        if self.max_lines:
            lines = body.split("\n")
            if len(lines) > self.max_lines:
                lines = lines[: self.max_lines]
                lines.append(f"… {len(body.split(chr(10))) - self.max_lines} "
                             f"more line(s)")
                body = "\n".join(lines)
        return body

    def _cache_key_for(self, width: int, theme: TranscriptTheme) -> object:
        return ("result", self.text, self.language, self.kind, self.indent,
                self.max_chars, self.max_lines, width)

    def _render(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        body = self._prepared()
        if not body.strip():
            return []

        pad = " " * self.indent
        style = "class:transcript-code"
        lines = body.rstrip("\n").split("\n")

        # Prose is the one case that benefits from the Markdown renderer.
        if self.kind == "markdown":
            rendered = render_markdown(body, width=max(width - self.indent, 20))
            return [(style, f"{pad}{ln}".rstrip() if ln.strip() else "")
                    for ln in rendered.split("\n")]

        # No fence markers: nothing here interprets them, so they used to be
        # printed as literal ``` lines around every code/data result.
        out: List[Tuple[str, str]] = []
        for ln in lines:
            # Code is never re-wrapped: its line structure is the content.
            out.append((style, f"{pad}{ln}" if ln.strip() else pad))
        return out


class ToolCallBlock(Block):
    """The header line for a tool call: emoji, name, preview, duration.

    Kept separate from the result so the call stays visible as a one-line
    summary even when the result below it is long and elided. The duration is
    mutable because it is only known once the tool returns; before that the
    block renders without it.
    """

    __slots__ = ("emoji", "name", "preview", "duration", "failed", "elided")

    def __init__(
        self,
        name: str,
        *,
        emoji: str = "",
        preview: str = "",
        duration: Optional[float] = None,
        failed: bool = False,
        elided: bool = False,
    ) -> None:
        super().__init__()
        self.name = name or ""
        self.emoji = emoji or ""
        self.preview = preview or ""
        self.duration = duration
        self.failed = failed
        #: True when the preview was cut short; drives the trailing ellipsis
        self.elided = elided

    def _cache_key_for(self, width: int, theme: TranscriptTheme) -> object:
        return ("call", self.name, self.emoji, self.preview, self.duration,
                self.failed, self.elided, width, theme)

    def _render(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        style = "class:transcript-error" if self.failed else "class:transcript-label"
        marker = "✗ " if self.failed else ""
        head = f"{marker}{self.emoji} {self.name}".strip()
        if self.preview:
            head += f" {self.preview}{'…' if self.elided else ''}"
        tail = ""
        if self.duration is not None:
            tail = f"  {self.duration:.1f}s"
        # The duration is right-aligned so a column of calls lines up, but the
        # budget is shared: if the header plus the duration would not fit, the
        # header is elided rather than wrapping the line.
        budget = max(width - len(tail) - 1, 12)
        if len(head) > budget:
            head = head[: max(budget - 1, 4)] + "…"
        return [(style, head + tail)]


class DiffBlock(Block):
    """A unified diff, coloured per line and capped.

    Diffs are not Markdown, so this stays a line-oriented block. The cap keeps
    a large edit from pushing the whole conversation off the screen; the
    truncation is stated in the output rather than being silent, because a
    diff that quietly stops halfway is worse than one that says so.
    """

    __slots__ = ("diff", "max_files", "max_lines", "_truncation_note")

    def __init__(self, diff: str, *, max_files: int = 6, max_lines: int = 80) -> None:
        super().__init__()
        self.diff = diff or ""
        self.max_files = max_files
        self.max_lines = max_lines
        self._truncation_note = ""

    def _cache_key_for(self, width: int, theme: TranscriptTheme) -> object:
        return ("diff", self.diff, self.max_files, self.max_lines, width, theme)

    def _render(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        if not self.diff.strip():
            return []
        out: List[Tuple[str, str]] = []
        files_seen = 0
        # True once we are past the last file the cap allows; every remaining
        # line of that file and all later files are dropped.
        past_cap = False
        dropped_files = 0
        for raw in self.diff.split("\n"):
            if out and len(out) >= self.max_lines:
                out.append(("class:transcript-dim",
                            f"… diff truncated after {self.max_lines} lines"))
                break
            if raw.startswith("--- "):
                files_seen += 1
                if files_seen > self.max_files:
                    # Count this file so the note can say how many were hidden.
                    dropped_files += 1
                    past_cap = True
                else:
                    past_cap = False
            if past_cap:
                continue
            out.append((_diff_style(raw, theme), raw))
        if dropped_files:
            out.append(("class:transcript-dim",
                        f"… {dropped_files} more file(s) omitted"))
        return out


def _diff_style(line: str, theme: TranscriptTheme) -> str:
    if line.startswith(("+++", "---")):
        return "class:transcript-diff-meta"
    if line.startswith("@@"):
        return "class:transcript-diff-meta"
    if line.startswith("+"):
        return "class:transcript-diff-add"
    if line.startswith("-"):
        return "class:transcript-diff-del"
    return "class:transcript-dim"


class NoticeBlock(Block):
    """A status line or error that is not a tool result."""

    __slots__ = ("text", "level")

    def __init__(self, text: str, *, level: str = "info") -> None:
        super().__init__()
        self.text = text or ""
        self.level = level

    def _cache_key_for(self, width: int, theme: TranscriptTheme) -> object:
        return ("notice", self.text, self.level, width)

    def _render(self, width: int, theme: TranscriptTheme) -> List[Tuple[str, str]]:
        if not self.text:
            return []
        style = {
            "error": "class:transcript-error",
            "warn": "class:transcript-warn",
        }.get(self.level, "class:transcript-dim")
        return [(style, line) for line in self.text.split("\n")]


# --------------------------------------------------------------------------
# Transcript
# --------------------------------------------------------------------------

class Transcript:
    """An ordered, bounded log of blocks, rendered as one scrollable region.

    Bounded because a long session would otherwise grow without limit and force
    the layout to allocate for the whole history on every repaint. Old blocks
    are dropped whole, never truncated mid-block, so a reader is never shown a
    half-rendered diff.
    """

    def __init__(self, *, max_blocks: int = 200) -> None:
        self._blocks: List[Block] = []
        self._max_blocks = max_blocks
        self._theme = TranscriptTheme()

    # -- content -----------------------------------------------------------

    def append(self, block: Block) -> Block:
        self._blocks.append(block)
        self._trim()
        return block

    def extend(self, blocks: Iterable[Block]) -> None:
        for b in blocks:
            self.append(b)

    def clear(self) -> None:
        self._blocks.clear()

    def _trim(self) -> None:
        if self._max_blocks and len(self._blocks) > self._max_blocks:
            del self._blocks[: len(self._blocks) - self._max_blocks]

    @property
    def blocks(self) -> Sequence[Block]:
        return tuple(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)

    def __iter__(self) -> Iterator[Block]:
        return iter(self._blocks)

    # -- rendering ---------------------------------------------------------

    @property
    def theme(self) -> TranscriptTheme:
        return self._theme

    def set_theme(self, theme: TranscriptTheme) -> None:
        if theme != self._theme:
            self._theme = theme
            for b in self._blocks:
                b.invalidate()

    def fragments(self, width: int) -> List[Tuple[str, str]]:
        """All blocks as fragments, with a blank line between them."""
        out: List[Tuple[str, str]] = []
        for i, block in enumerate(self._blocks):
            if i:
                out.append(("", ""))
            out.extend(block.fragments(width, self._theme))
        return out