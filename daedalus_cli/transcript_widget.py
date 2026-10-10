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

from typing import List, Tuple

from prompt_toolkit.application import get_app
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

from daedalus_cli.transcript import Transcript, TranscriptTheme

__all__ = ["TranscriptWidget", "build_transcript_widgets"]


class TranscriptWidget:
    """Owns the transcript's scroll state and builds the layout controls.

    This is a controller, not a container: it does not subclass anything
    prompt_toolkit-specific, so it can be unit-tested with no running
    application, and the layout just asks it for two ``Window``s.
    """

    def __init__(self, transcript: Transcript, *, scrollbar: bool = True) -> None:
        self.transcript = transcript
        self._scrollbar_enabled = scrollbar
        #: display-row offset from the bottom; 0 means "stuck to the newest"
        self._offset = 0
        #: total display height of the content, for scrollbar maths
        self._content_height = 0

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

        Computed from the block fragment counts without touching the widget's
        own scroll state, so the scroll clamps work before the first paint.
        The transcript caches per-block rendering, so this is cheap after the
        first call.
        """
        return len(self.transcript.fragments(width))

    def scroll_up(self, visible_rows: int, rows: int = 1, *, width: int = 80) -> None:
        """Move the view toward older content, leaving follow mode."""
        self._content_height = self._measure(width)
        new = self._offset + max(rows, 1)
        self._offset = min(new, self._max_offset(visible_rows))
        self.refresh()

    def scroll_down(self, visible_rows: int, rows: int = 1) -> None:
        """Move toward newer content; reaching the bottom re-enters follow."""
        new = self._offset - max(rows, 1)
        self._offset = max(new, 0)
        self.refresh()

    def scroll_to_bottom(self) -> None:
        self._offset = 0
        self.refresh()

    def scroll_to_top(self, visible_rows: int, *, width: int = 80) -> None:
        self._content_height = self._measure(width)
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
        bottom (follow mode). The visible slice therefore runs from
        ``len - visible_rows - offset`` to ``len - offset``: the newest rows
        below the edge are withheld, and older rows above the top edge are cut
        by the caller via ``visible_rows``.
        """
        all_frags = self.transcript.fragments(width)
        self._content_height = len(all_frags)
        if self._offset <= 0:
            if visible_rows and len(all_frags) > visible_rows:
                return all_frags[-visible_rows:]
            return all_frags
        end = max(len(all_frags) - self._offset, 0)
        if visible_rows:
            start = max(end - visible_rows, 0)
        else:
            start = 0
        return all_frags[start:end]

    def content_height(self, width: int) -> int:
        return len(self.transcript.fragments(width))

    # -- layout ------------------------------------------------------------

    def build(self, cli_ref) -> Tuple[Window, Window]:
        """Return ``(transcript_window, scrollbar_window)`` for the layout."""
        widget = self

        def get_frags():
            try:
                app = get_app()
                cols = app.output.get_size().columns
                rows = app.output.get_size().rows
            except Exception:
                cols, rows = 80, 24
            # Reserve rows for the other layout children so the transcript's
            # scroll maths matches the space it is actually given.
            visible = max(rows - 10, 3)
            return widget.fragments(max(cols - 2, 20), visible_rows=visible)

        transcript_window = Window(
            content=FormattedTextControl(get_frags),
            wrap_lines=False,
            always_hide_cursor=True,
            # The transcript fills whatever vertical space the layout gives it
            # and scrolls internally; the other widgets keep their own heights.
            height=Dimension(min=3, weight=1),
        )

        def get_scrollbar_chars():
            # One character per display row, from the bottom up, matching how
            # fragments() slices. A '#' marks the visible band.
            total = widget._content_height
            visible = max(total - widget._offset, 1)
            # We do not know the exact window height here, so approximate the
            # band with a fixed recent slice; prompt_toolkit re-renders often
            # enough that a rough marker is honest and never misleading about
            # direction.
            window_rows = 12
            if total <= window_rows or widget._offset == 0:
                return [("class:transcript-scrollbar", " ")] * min(total, window_rows)
            chars = []
            top_hidden = widget._offset
            for i in range(window_rows):
                row_from_bottom = i
                row_from_top = total - 1 - row_from_bottom
                if row_from_top < top_hidden:
                    chars.append(("class:transcript-scrollbar-thumb", "█"))
                else:
                    chars.append(("class:transcript-scrollbar", "│"))
            return list(reversed(chars))

        scrollbar_window = Window(
            content=FormattedTextControl(get_scrollbar_chars),
            width=1,
            char=" ",
            height=Dimension(min=1),
            always_hide_cursor=True,
        )

        return transcript_window, scrollbar_window


def build_transcript_widgets(cli_ref, transcript: Transcript):
    """Convenience: build the controller and return its two windows."""
    controller = TranscriptWidget(transcript)
    return controller, *controller.build(cli_ref)