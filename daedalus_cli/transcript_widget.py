"""The scrollable transcript widget: the model's bridge to the terminal.

Why a widget and not a print
----------------------------
The whole reason this exists is that ``print_formatted_text`` (which ``_cprint``
wraps) makes prompt_toolkit tear the interface down and rebuild it on every
call. A ``Window`` whose ``FormattedTextControl`` returns the transcript's
fragments is painted as part of the normal layout, so it inherits the skin and
never triggers a teardown.

Scrolling
---------
prompt_toolkit lays out a ``Window`` with ``height=D(min=…)`` against the space
the layout gives it. Transcript content is usually taller than that, so the
window scrolls: it keeps a scroll offset (in display rows, measured from the
bottom) and shifts the fragment list accordingly. The scrollbar is a separate
narrow window that mirrors that offset, so a reader can see where they are in a
long turn and drag it.

The bottom-sticking behaviour matters for the common case: when the reader has
not scrolled up, the view follows the newest output, exactly like a terminal.
The moment they scroll up to read something, auto-follow stops until they
scroll back down -- otherwise output would keep yanking the view away
mid-read.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent

from daedalus_cli.transcript import Transcript, TranscriptTheme

__all__ = ["TranscriptWidget", "TranscriptControl", "build_transcript_widgets"]


def _make_content(controller: "TranscriptWidget", width: int, height: int) -> UIContent:
    """Build the ``UIContent`` for one paint.

    Not a subclass: ``UIContent`` is a plain container in prompt_toolkit 3.x
    (a list of lines plus a cursor), and composing it directly keeps us on the
    supported surface rather than on internals like ``line_count`` that moved
    between releases.
    """
    fragments = controller.fragments(width, visible_rows=height)

    def get_line(i: int):
        return [fragments[i]] if i < len(fragments) else []

    return UIContent(
        get_line=get_line,
        line_count=len(fragments),
        cursor_position=Point(x=0, y=0),
        show_cursor=False,
    )


class TranscriptControl(UIControl):
    """A prompt_toolkit control that owns the transcript's scroll position."""

    def __init__(self, controller: "TranscriptWidget") -> None:
        self.controller = controller

    def create_content(self, width: int, height: int) -> UIContent:
        return _make_content(self.controller, width, height)

    def preferred_height(self, width: int, max_available_height: int,
                          wrap_lines: bool, get_line_prefix=None) -> int:
        # Claim a share of the available height, not all of it.
        #
        # prompt_toolkit resolves a weighted Window's height before the other
        # fixed-height children of the HSplit, so returning max_available_height
        # makes the transcript take the whole screen: at startup the transcript
        # is empty, and the user gets a blank terminal with no prompt, no
        # status bar and no input line. Reserve the rows the rest of the layout
        # needs (rules, status, spinner, input, completion menu) and take the
        # remainder, which is what makes the transcript the scrollback region
        # without evicting the controls.
        chrome = self.controller.chrome_rows
        return max(max_available_height - chrome, 1)

    def preferred_width(self, max_width: int) -> int:
        return max_width

    def is_focusable(self) -> bool:
        return False

    def get_key_bindings(self) -> KeyBindings:
        return KeyBindings()

    def _mouse_scroll(self, event: MouseEvent) -> None:
        delta = getattr(event, "scroll_up", None), getattr(event, "scroll_down", None)
        up, down = delta
        rows = max(int(getattr(event, "count", 1) or 1), 1)
        if up:
            self.controller.scroll_up(self.controller.visible_rows, rows)
        elif down:
            self.controller.scroll_down(self.controller.visible_rows, rows)

    def mouse_handler(self, mouse_event) -> None:
        self._mouse_scroll(mouse_event)


class TranscriptWidget:
    """Owns the transcript's scroll state and builds the layout control."""

    def __init__(self, transcript: Transcript, *, scrollbar: bool = True) -> None:
        self.transcript = transcript
        self._scrollbar_enabled = scrollbar
        #: display-row offset from the bottom; 0 means "stuck to the newest"
        self._offset = 0
        #: total display height of the content, for scrollbar maths
        self._content_height = 0
        #: rows the control was last drawn at, so scroll keys match the view
        self.visible_rows = 20
        #: Rows the rest of the layout needs: two input rules, the status bar,
        #: the spinner/hint line, the input area and the completion menu. The
        #: transcript leaves these alone so it can never push the controls off
        #: the screen -- which is exactly what a full-height request does.
        self.chrome_rows = 8

    # -- scrolling ---------------------------------------------------------

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def follow(self) -> bool:
        """True when the view is pinned to the newest content."""
        return self._offset == 0

    def _max_offset(self, visible_rows: int) -> int:
        return max(self._content_height - visible_rows, 0)

    def _measure(self, width: int) -> int:
        """Total display height of the transcript at *width*.

        Computed from the model alone, not from a prior paint, so the scroll
        clamps work before the first render. The transcript caches per-block
        rendering, so this is cheap after the first call.
        """
        return len(self.transcript.fragments(width))

    def scroll_up(self, visible_rows: int, rows: int = 1, *, width: int = 80) -> None:
        """Move the view toward older content, leaving follow mode."""
        self._content_height = self._measure(width)
        self.visible_rows = visible_rows
        self._offset = min(self._offset + max(rows, 1), self._max_offset(visible_rows))
        self.refresh()

    def scroll_down(self, visible_rows: int, rows: int = 1) -> None:
        """Move toward newer content; reaching the bottom re-enters follow."""
        self.visible_rows = visible_rows
        self._offset = max(self._offset - max(rows, 1), 0)
        self.refresh()

    def scroll_to_bottom(self) -> None:
        self._offset = 0
        self.refresh()

    def scroll_to_top(self, visible_rows: int, *, width: int = 80) -> None:
        self._content_height = self._measure(width)
        self.visible_rows = visible_rows
        self._offset = self._max_offset(visible_rows)
        self.refresh()

    def page_up(self, visible_rows: int, *, width: int = 80) -> None:
        self.scroll_up(visible_rows, max(visible_rows - 1, 1), width=width)

    def page_down(self, visible_rows: int) -> None:
        self.scroll_down(visible_rows, max(visible_rows - 1, 1))

    def refresh(self) -> None:
        try:
            app = get_app()
        except Exception:
            return
        if app is not None:
            app.invalidate()

    # -- rendering ---------------------------------------------------------

    def fragments(self, width: int, visible_rows: int = 0) -> List[Tuple[str, str]]:
        """Content fragments, scrolled to the current offset from the bottom.

        ``_offset`` is "how many rows below the viewport's bottom edge the
        newest content sits". At offset 0 the newest row is flush with the
        bottom (follow mode).
        """
        all_frags = self.transcript.fragments(width)
        self._content_height = len(all_frags)
        if visible_rows:
            self.visible_rows = visible_rows
        if self._offset <= 0:
            if visible_rows and len(all_frags) > visible_rows:
                return all_frags[-visible_rows:]
            return all_frags
        end = max(len(all_frags) - self._offset, 0)
        start = max(end - visible_rows, 0) if visible_rows else 0
        return all_frags[start:end]

    def content_height(self, width: int) -> int:
        return len(self.transcript.fragments(width))

    # -- layout ------------------------------------------------------------

    def build(self, cli_ref=None) -> Window:
        """Return the transcript control wrapped in a ``Window`` for the layout."""
        from prompt_toolkit.layout import Window
        return Window(content=TranscriptControl(self), height=Dimension(min=1, weight=1))


def build_transcript_widgets(cli_ref, transcript: Transcript):
    """Convenience: build the controller and return its window."""
    controller = TranscriptWidget(transcript)
    return controller, controller.build(cli_ref)