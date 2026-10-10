"""The transcript widget: scrolling behaviour and proof it reaches the screen.

Two things are being defended here.

1. **Scrolling math.** Offset-from-the-bottom slicing is easy to get subtly
   wrong, and a wrong offset either hides the newest output or scrolls past the
   oldest. These tests pin the boundaries exactly.

2. **It actually paints.** Populating fragments is not rendering. As with the
   reasoning pane, a print-based transcript would pass a buffer-level test and
   still shatter the skin, so the widget is driven through prompt_toolkit's real
   renderer and the output is read back.
"""

import io
import re
import sys
import threading
import time

import pytest

sys.path.insert(0, "/home/alca/.daedalus/daedalus-agent")

from daedalus_cli.transcript import MarkdownBlock, NoticeBlock, ToolCallBlock, Transcript
from daedalus_cli.transcript_widget import TranscriptWidget


def make_transcript(n: int = 5) -> Transcript:
    tr = Transcript()
    for i in range(n):
        tr.append(NoticeBlock(f"line {i}"))
    return tr


class TestScrolling:
    def test_starts_following_the_bottom(self):
        w = TranscriptWidget(make_transcript())
        assert w.offset == 0
        assert w.follow is True

    def test_scroll_up_moves_into_history(self):
        w = TranscriptWidget(make_transcript(20))
        w.scroll_up(visible_rows=10, rows=3)
        assert w.offset == 3
        assert w.follow is False

    def test_scroll_down_returns_toward_follow(self):
        w = TranscriptWidget(make_transcript(20))
        w.scroll_up(visible_rows=10, rows=3)
        w.scroll_down(visible_rows=10, rows=3)
        assert w.offset == 0
        assert w.follow is True

    def test_scroll_down_past_the_bottom_clamps_to_zero(self):
        w = TranscriptWidget(make_transcript(20))
        w.scroll_down(visible_rows=10, rows=100)
        assert w.offset == 0

    def test_scroll_up_past_the_top_clamps_to_content_height(self):
        tr = make_transcript(20)
        w = TranscriptWidget(tr)
        w.scroll_up(visible_rows=10, rows=1000)
        # max offset = content_height - visible. Blocks are separated by blank
        # rows, so the height is not the block count; derive it from the model.
        assert w.offset == w._content_height - 10
        assert w.offset >= 0

    def test_page_up_moves_a_page(self):
        w = TranscriptWidget(make_transcript(50))
        w.page_up(visible_rows=10)
        assert w.offset == 9      # visible_rows - 1

    def test_scroll_to_bottom_and_top(self):
        w = TranscriptWidget(make_transcript(30))
        w.scroll_to_top(visible_rows=10)
        assert w.offset == w._content_height - 10
        w.scroll_to_bottom()
        assert w.offset == 0
        assert w.follow is True

    def test_offset_zero_returns_everything(self):
        tr = make_transcript(5)
        w = TranscriptWidget(tr)
        frags = w.fragments(80)
        assert len(frags) == len(tr.fragments(80))

    def test_offset_hides_the_newest_rows(self):
        w = TranscriptWidget(make_transcript(10))
        full = w.fragments(80)
        w.scroll_up(visible_rows=5, rows=3)
        # offset 3 means the three newest rows sit below the bottom edge, so
        # they must not be in the visible slice any more.
        sliced = w.fragments(80, visible_rows=5)
        newest = full[-1][1]
        assert newest not in [t for _, t in sliced]
        assert len(sliced) == 5

    def test_follow_shows_the_newest_row(self):
        w = TranscriptWidget(make_transcript(10))
        full = w.fragments(80)
        view = w.fragments(80, visible_rows=5)
        assert view[-1] == full[-1]


class TestRendering:
    def _render_to_text(self, widget, rows: int = 24, cols: int = 80) -> str:
        """Drive a real prompt_toolkit Application and return plain output."""
        from prompt_toolkit.application import Application
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.layout import HSplit, Layout
        from prompt_toolkit.output.vt100 import Vt100_Output

        tw = widget.build(None)
        buf = io.StringIO()

        class Sink(io.TextIOBase):
            def write(self, s):
                buf.write(s)
                return len(s)

            def flush(self):
                pass

            def isatty(self):
                return False

            def fileno(self):
                return 2

        out = Vt100_Output(Sink(), lambda: Size(rows=rows, columns=cols),
                           term="xterm-256color")
        with create_pipe_input() as pipe:
            app = Application(layout=Layout(HSplit([tw])), input=pipe, output=out)
            t = threading.Thread(target=lambda: app.run(), daemon=True)
            t.start()
            time.sleep(0.5)
            try:
                app.exit()
            except Exception:
                pass
            t.join(timeout=3)
        return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", buf.getvalue())

    def test_transcript_reaches_the_screen(self):
        tr = Transcript()
        tr.append(NoticeBlock("HELLO-TRANSCRIPT-MARKER"))
        w = TranscriptWidget(tr)
        out = self._render_to_text(w)
        assert "HELLO-TRANSCRIPT-MARKER" in out

    def test_markdown_is_rendered_on_screen(self):
        tr = Transcript()
        tr.append(MarkdownBlock("**bold-marker**"))
        w = TranscriptWidget(tr)
        out = self._render_to_text(w)
        plain = re.sub(r"\*", "", out)
        assert "bold-marker" in plain
        assert "**bold-marker**" not in out, "markdown was not rendered"

    def test_tool_call_reaches_the_screen(self):
        tr = Transcript()
        tr.append(ToolCallBlock("read", emoji="📖", preview="notes.md", duration=1.0))
        w = TranscriptWidget(tr)
        out = self._render_to_text(w)
        assert "read" in out and "notes.md" in out

    def test_rendering_does_not_clear_the_frame(self):
        # The property that would be violated by a print-based transcript.
        tr = Transcript()
        for i in range(30):
            tr.append(NoticeBlock(f"row {i}"))
        w = TranscriptWidget(tr)

        # Render once, then mutate and re-render, counting full-screen clears
        # across both. A normal repaint may clear once at startup; a print
        # stream would stack a clear per line.
        buf = io.StringIO()
        from prompt_toolkit.application import Application
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.layout import HSplit, Layout
        from prompt_toolkit.output.vt100 import Vt100_Output

        tw = w.build(None)

        class Sink(io.TextIOBase):
            def write(self, s):
                buf.write(s)
                return len(s)

            def flush(self):
                pass

            def isatty(self):
                return False

            def fileno(self):
                return 2

        out = Vt100_Output(Sink(), lambda: Size(rows=24, columns=80),
                           term="xterm-256color")
        with create_pipe_input() as pipe:
            app = Application(layout=Layout(HSplit([tw])), input=pipe, output=out)
            t = threading.Thread(target=lambda: app.run(), daemon=True)
            t.start()
            time.sleep(0.4)
            # simulate several app-side updates without tearing down
            for i in range(20):
                tr.append(NoticeBlock(f"live {i}"))
                app.invalidate()
                time.sleep(0.02)
            try:
                app.exit()
            except Exception:
                pass
            t.join(timeout=3)

        rendered = buf.getvalue()
        # prompt_toolkit's renderer may emit a couple of clears on startup and
        # resize, but 20 live updates must not each add one. Keep it small.
        assert rendered.count("\x1b[2J") <= 3, \
            "live transcript updates are stacking full-screen clears"


class TestControllerIsHeadless:
    def test_can_be_constructed_without_an_application(self):
        # Scroll math and fragments must work with no prompt_toolkit app
        # running; only refresh() may no-op.
        w = TranscriptWidget(make_transcript(10))
        w.scroll_up(visible_rows=5, rows=2)
        assert w.offset == 2
        assert w.fragments(80)

    def test_scroll_clamps_work_before_first_paint(self):
        # _content_height must be known from the model alone, not from a prior
        # render, or the clamps would be no-ops on the first keystroke.
        w = TranscriptWidget(make_transcript(20))
        w.scroll_up(visible_rows=10, rows=1000)
        assert w.offset == w._content_height - 10

    def test_refresh_without_app_does_not_raise(self):
        w = TranscriptWidget(make_transcript())
        w.refresh()      # must not raise even with no app
        w.scroll_down(5, 1)