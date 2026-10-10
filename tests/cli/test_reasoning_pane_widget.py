"""Reasoning renders as a layout widget, not as prints on top of the skin.

The skin was being shattered by reasoning, and the colours were not the cause.
The cause is that reasoning was printed. Every _cprint is a
print_formatted_text, which prompt_toolkit routes through run_in_terminal:
renderer.erase(), renderer.reset(), a cursor-position request and a full redraw
of the skin-painted TUI. Reasoning flushed every 80 characters, so a 4k-token
thinking block cost roughly one teardown-and-rebuild of the whole UI per wrapped
line. With show_reasoning off the callback is None, none of this runs, and the
skin is intact - which is why it presented as a switch rather than a
degradation.

These tests pin the two properties that actually fix it:

  - reasoning text lands in a list that the layout's FormattedTextControl reads,
    so the pane is repainted WITH the skin instead of over it;
  - closing the pane empties that list and flushes the deferred response, so the
    handoff to the answer happens in the same repaint.

They also assert that the reasoning path never calls _cprint, because that is
the mechanism being removed; a future edit that reintroduces a print here would
restore the bug without failing any behavioural test.
"""

import sys
import types

import pytest
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import FormattedTextControl

sys.path.insert(0, "/home/alca/.daedalus/daedalus-agent")

import cli as C


class _Fake:
    """Just enough CLI state for the reasoning path."""

    def __init__(self):
        self._reasoning_stream_started = False
        self._reasoning_shown_this_turn = False
        self._stream_box_opened = False
        self._reasoning_box_opened = False
        self._reasoning_buf = ""
        self._reasoning_fragments = []
        self._reasoning_lines_seen = 0
        self._deferred_content = ""
        self._stream_buf = ""
        self._emitted = []
        self.printed = []
        self.invalidates = 0
        self._REASONING_PANE_MAX_LINES = 8
        self._app = None
        self._last_invalidate = 0.0
        for name in ("_reasoning_width",
                     "_refresh_reasoning_pane", "_stream_reasoning_delta",
                     "_close_reasoning_box"):
            setattr(self, name, types.MethodType(getattr(C.DaedalusCLI, name), self))

    def _emit_stream_text(self, text):
        self._emitted.append(text)

    def _invalidate(self, min_interval: float = 0.25):
        self.invalidates += 1


@pytest.fixture()
def fake(monkeypatch):
    printed = []
    monkeypatch.setattr(C, "_cprint", lambda t: printed.append(t))
    f = _Fake()
    f.printed = printed
    return f


class TestReasoningGoesIntoTheLayout:
    def test_reasoning_lands_in_fragments_not_on_stdout(self, fake):
        # Long enough to flush on width; a short delta legitimately waits in the
        # buffer, so nothing is rendered and nothing is repainted.
        fake._stream_reasoning_delta("weaving the solution together " * 8)
        assert fake._reasoning_fragments, "reasoning produced no fragments"
        assert not fake.printed, "reasoning printed instead of using the layout"

    def test_no_print_on_a_long_newline_free_block(self, fake):
        # The exact shape that used to overrun the frame: one long paragraph.
        fake._stream_reasoning_delta("thinking " * 400)
        assert len(fake._reasoning_fragments) > 1, "long paragraph was not wrapped"
        assert not fake.printed

    def test_one_invalidate_per_call_not_one_per_line(self, fake):
        fake._stream_reasoning_delta("a line\n" * 6)
        # Six lines arrive, but the pane costs a single repaint.
        assert fake.invalidates == 1
        assert len(fake._reasoning_fragments) >= 6

    def test_pane_is_bounded(self, fake):
        fake._stream_reasoning_delta("line\n" * 40)
        assert len(fake._reasoning_fragments) <= fake._REASONING_PANE_MAX_LINES

    def test_suppressed_once_the_response_box_is_open(self, fake):
        fake._stream_box_opened = True
        fake._stream_reasoning_delta("late thinking")
        assert not fake._reasoning_fragments
        assert not fake.printed

    def test_empty_delta_is_a_noop(self, fake):
        fake._stream_reasoning_delta("")
        assert not fake._reasoning_fragments
        assert fake.invalidates == 0


class TestClosingThePane:
    def test_close_empties_the_pane(self, fake):
        fake._stream_reasoning_delta("some reasoning here")
        fake._close_reasoning_box()
        assert fake._reasoning_fragments == []
        assert fake._reasoning_box_opened is False

    def test_close_is_safe_when_never_opened(self, fake):
        fake._close_reasoning_box()          # must not raise
        assert fake._reasoning_fragments == []

    def test_deferred_response_is_flushed_on_close(self, fake):
        fake._stream_reasoning_delta("thinking")
        fake._deferred_content = "the answer so far"
        fake._close_reasoning_box()
        assert fake._emitted == ["the answer so far"]
        assert fake._deferred_content == ""

    def test_close_repaints(self, fake):
        fake._stream_reasoning_delta("thinking")
        before = fake.invalidates
        fake._close_reasoning_box()
        assert fake.invalidates > before


class TestSkinOwnsThePane:
    """The pane is a widget, so its colour has to arrive through the style layer."""

    def test_skin_overrides_reach_the_reasoning_classes(self, monkeypatch):
        from daedalus_cli import skin_engine

        class FakeSkin:
            def get_color(self, key, default=None):
                table = {"reasoning_border": "#B388FF",
                         "reasoning_text": "#E0D4FF",
                         "prompt": "#D0BCFF"}
                return table.get(key, default)

        monkeypatch.setattr(skin_engine, "get_active_skin", lambda: FakeSkin())
        out = skin_engine.get_prompt_toolkit_style_overrides()
        assert out.get("reasoning-border") == "#B388FF"
        assert out.get("reasoning-text") == "#E0D4FF"

    def test_reasoning_text_falls_back_to_the_border(self, monkeypatch):
        from daedalus_cli import skin_engine

        class FakeSkin:
            def get_color(self, key, default=None):
                return {"reasoning_border": "#B388FF"}.get(key, default)

        monkeypatch.setattr(skin_engine, "get_active_skin", lambda: FakeSkin())
        out = skin_engine.get_prompt_toolkit_style_overrides()
        assert out.get("reasoning-text") == "#B388FF"


class TestWrapAndRail:
    def test_every_line_has_a_rail(self, fake):
        fake._stream_reasoning_delta("one\ntwo\nthree")
        for style, text in fake._reasoning_fragments:
            assert style == 'class:reasoning-text'
            assert text.lstrip().startswith("│")

    def test_width_is_bounded(self, fake):
        fake._stream_reasoning_delta("w " * 2000)
        width = fake._reasoning_width()
        for style, text in fake._reasoning_fragments:
            assert len(text) <= width + 4    # rail plus its space


class TestTheLayoutActuallyDrawsIt:
    """The assertions above check the buffer. This checks the screen.

    Populating a list is not the same as rendering it, and the whole point of
    moving reasoning into the layout is that it is drawn WITH the skin instead
    of over it. So drive prompt_toolkit's real renderer and read back what it
    wrote: the reasoning text must appear, the widgets below it must survive,
    and the frame must not be cleared and rebuilt.
    """

    def _render(self, cli_obj, extra_widgets):
        import io
        import re
        import threading
        import time
        from prompt_toolkit.application import Application
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.layout import HSplit, Layout
        from prompt_toolkit.output.vt100 import Vt100_Output

        def frags():
            return list(cli_obj._reasoning_fragments or [])

        def height():
            n = len(cli_obj._reasoning_fragments)
            return min(n, cli_obj._REASONING_PANE_MAX_LINES) if n else 0

        pane = Window(content=FormattedTextControl(frags),
                      height=height, wrap_lines=False)
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

        out = Vt100_Output(Sink(), lambda: Size(rows=24, columns=80),
                           term="xterm-256color")
        with create_pipe_input() as pipe:
            app = Application(layout=Layout(HSplit([pane] + extra_widgets)),
                              input=pipe, output=out)
            t = threading.Thread(target=lambda: app.run(), daemon=True)
            t.start()
            time.sleep(0.6)
            try:
                app.exit()
            except Exception:
                pass
            t.join(timeout=3)

        rendered = buf.getvalue()
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", rendered)
        return rendered, plain

    def test_reasoning_is_drawn_and_the_widgets_below_survive(self, fake):
        below = Window(
            content=FormattedTextControl(
                lambda: [("class:x", "BOTTOM-ROW-OK")]), height=1)

        fake._reasoning_fragments = [
            ("class:reasoning-text", "│ reasoning is inside the layout")] * 3
        rendered, plain = self._render(fake, [below])

        assert "reasoning is inside the layout" in plain, \
            "reasoning never reached the screen"
        # The skin below the pane must still be there. A print-based overlay
        # would push it off / repaint over it.
        assert "BOTTOM-ROW-OK" in plain, \
            "the widget below the reasoning pane was not preserved"

    def test_pane_does_not_clear_the_frame(self, fake):
        below = Window(
            content=FormattedTextControl(
                lambda: [("class:x", "BOTTOM-ROW-OK")]), height=1)

        fake._reasoning_fragments = [
            ("class:reasoning-text", "│ line")] * 5
        rendered, _plain = self._render(fake, [below])

        # run_in_terminal's teardown. One initial draw may clear once; a stream
        # of reasoning must never stack more full-screen clears on top of it.
        assert rendered.count("\x1b[2J") <= 1, \
            "reasoning triggered repeated full-screen clears (the skin bug)"
