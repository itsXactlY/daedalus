"""The bridge from agent callbacks to transcript blocks.

The bridge is where the agent's four reporting mechanisms (tool started,
tool complete, streamed text, and its own ``_print_fn``) become rendered
blocks. These tests pin the *translation*, including the two behaviours that
are easy to get subtly wrong:

  - a call block is mutated in place when the tool returns, so the duration
    appears without the header being reprinted or moving; and
  - the print function used for agent status lines never reaches stdout,
    which is the whole reason it is routed here instead of to ``_cprint``.
"""

import sys

import pytest

sys.path.insert(0, "/home/alca/.daedalus/daedalus-agent")

from daedalus_cli.transcript import Transcript, TranscriptTheme
from daedalus_cli.transcript_bridge import TranscriptBridge


@pytest.fixture()
def bridge() -> TranscriptBridge:
    return TranscriptBridge(Transcript(), theme=TranscriptTheme())


def texts(tr: Transcript, width: int = 100) -> str:
    from daedalus_cli.transcript import strip_ansi
    return strip_ansi("\n".join(t for _, t in tr.fragments(width)))


class TestAssistant:
    def test_appends_open_a_block(self, bridge):
        bridge.append_assistant("hello")
        assert "hello" in texts(bridge.transcript)

    def test_multiple_appends_join_one_block(self, bridge):
        bridge.append_assistant("hello ")
        bridge.append_assistant("world")
        assert "hello world" in texts(bridge.transcript)
        assert len(bridge.transcript) == 1, "streaming split into several blocks"

    def test_end_then_start_makes_a_new_block(self, bridge):
        bridge.append_assistant("first")
        bridge.end_assistant()
        bridge.append_assistant("second")
        assert len(bridge.transcript) == 2
        body = texts(bridge.transcript)
        assert "first" in body and "second" in body

    def test_markdown_is_rendered(self, bridge):
        bridge.append_assistant("**bold**")
        assert "**bold**" not in texts(bridge.transcript)

    def test_empty_text_does_nothing(self, bridge):
        bridge.append_assistant("")
        assert len(bridge.transcript) == 0


class TestToolLifecycle:
    def test_started_opens_a_call_block(self, bridge):
        bridge.tool_started("id1", "read", "notes.md")
        body = texts(bridge.transcript)
        assert "read" in body and "notes.md" in body

    def test_completed_fills_the_duration_in_place(self, bridge):
        block = bridge.tool_started("id1", "read", "notes.md")
        assert block.duration is None, "a running tool must not show a duration"
        bridge.tool_completed("id1", "read", "ok", duration=1.5)
        # same block object, now carrying the duration
        assert block.duration == 1.5
        assert "1.5s" in texts(bridge.transcript)

    def test_completed_attaches_the_result(self, bridge):
        bridge.tool_started("id1", "read", "f.md")
        bridge.tool_completed("id1", "read", "the file contents")
        assert "the file contents" in texts(bridge.transcript)

    def test_result_is_indented_under_the_call(self, bridge):
        bridge.tool_started("id1", "read", "f.md")
        bridge.tool_completed("id1", "read", "body text")
        lines = [t for _, t in bridge.transcript.fragments(100)]
        idx = next(i for i, t in enumerate(lines) if "body text" in t)
        assert lines[idx].startswith("  "), "result is not nested under the call"

    def test_failure_marks_the_call(self, bridge):
        bridge.tool_started("id1", "read", "f.md")
        bridge.tool_completed("id1", "read", "boom", failed=True)
        styles = [s for s, t in bridge.transcript.fragments(100) if "read" in t]
        assert "class:transcript-error" in styles

    def test_diff_is_attached(self, bridge):
        bridge.tool_started("id1", "write_file", "f.py")
        bridge.tool_completed("id1", "write_file", "ok",
                              diff="--- a/f.py\n+++ b/f.py\n@@\n-x\n+y")
        body = texts(bridge.transcript)
        assert "-x" in body and "+y" in body

    def test_result_is_capped(self):
        b = TranscriptBridge(Transcript(), result_max_chars=200)
        b.tool_started("id", "terminal", "ls")
        b.tool_completed("id", "terminal", "x" * 5000)
        assert "truncated" in texts(b.transcript)

    def test_unknown_id_still_renders(self, bridge):
        # A completed event without a matching start (a reconnect, a cancelled
        # call) must not silently swallow the result.
        bridge.tool_completed("missing", "read", "output arrived anyway")
        body = texts(bridge.transcript)
        assert "read" in body and "output arrived anyway" in body

    def test_start_without_id_completion_with_id_is_one_block(self, bridge):
        # This is the shape the agent actually emits: tool.started carries the
        # tool name and no id, tool_complete carries tool_call.id. If the two
        # cannot be correlated the tool renders twice -- once as a dangling
        # "started" header and again as an unpaired "completed" one.
        bridge.tool_started("read_file", "read_file", "a.md")
        bridge.tool_completed("call_abc123", "read_file", "body")
        assert len(bridge.transcript) == 1, \
            "a call and its result are ONE block"
        headers = [t for _, t in bridge.transcript.fragments(100)
                   if "read_file" in t]
        assert len(headers) == 1, f"tool header rendered {len(headers)} times"

    def test_concurrent_same_tool_correlates_each_call(self, bridge):
        bridge.tool_started("read_file", "read_file", "a.md")
        bridge.tool_started("read_file", "read_file", "b.md")
        bridge.tool_completed("id_b", "read_file", "second body")
        bridge.tool_completed("id_a", "read_file", "first body")
        bodies = [t for _, t in bridge.transcript.fragments(100)
                  if "body" in t]
        assert len(bodies) == 2, "a concurrent result was dropped"
        assert not any(bridge._open_by_name.values()), "an open call was left behind"
        assert not bridge._open_calls, "an open call was left behind"

    def test_no_dangling_open_calls_after_completion(self, bridge):
        bridge.tool_started("a", "read")
        bridge.tool_started("b", "write")
        bridge.tool_completed("a", "read", "x")
        assert "b" in bridge._open_calls
        bridge.tool_completed("b", "write", "y")
        assert not bridge._open_calls


class TestPrintFunction:
    def test_prints_land_in_the_transcript(self, bridge):
        bridge.print_line("running 3 commands\n")
        assert "running 3 commands" in texts(bridge.transcript)

    def test_nothing_reaches_stdout(self, bridge, capsys):
        bridge.print_line("a status line\n")
        bridge.flush_line()
        assert capsys.readouterr().out == ""

    def test_partial_lines_are_buffered_until_a_newline(self, bridge):
        bridge.print_line("half")
        assert len(bridge.transcript) == 0, "a partial line was committed early"
        bridge.print_line(" a whole line\n")
        assert len(bridge.transcript) == 1
        assert "half a whole line" in texts(bridge.transcript)

    def test_flush_commits_the_remainder(self, bridge):
        bridge.print_line("no trailing newline")
        bridge.flush_line()
        assert "no trailing newline" in texts(bridge.transcript)

    def test_blank_lines_are_dropped(self, bridge):
        bridge.print_line("\n   \n")
        bridge.flush_line()
        assert len(bridge.transcript) == 0

    def test_several_lines_in_one_call(self, bridge):
        bridge.print_line("one\ntwo\nthree\n")
        body = texts(bridge.transcript)
        for expected in ("one", "two", "three"):
            assert expected in body


class TestLifecycle:
    def test_clear_drops_open_state(self, bridge):
        bridge.tool_started("a", "read")
        bridge.append_assistant("x")
        bridge.print_line("buf")
        bridge.clear()
        assert not bridge._open_calls
        assert bridge._assistant_block is None
        assert bridge._line_buffer == ""
        # The transcript itself is kept: clear() resets per-turn state, not
        # the visible history.

    def test_bridge_never_raises_on_bad_input(self, bridge):
        bridge.tool_started("", "", "")
        bridge.tool_completed("", "", "")
        bridge.print_line(None)
        bridge.print_line("")
        bridge.append_assistant(None)
        bridge.flush_line()

    def test_invalidate_is_safe_without_an_app(self, bridge):
        bridge.invalidate()   # must not raise

    def test_theme_is_pushed_into_the_transcript(self):
        tr = Transcript()
        theme = TranscriptTheme(text="#abcdef")
        TranscriptBridge(tr, theme=theme)
        assert tr.theme == theme

class TestOneBlockPerCall:
    """Parallel calls used to render [call A][call B][result A][result B]."""

    def test_each_result_sits_under_its_own_call(self, bridge):
        bridge.tool_started("a", "mazemaker_recall", "stealth plan")
        bridge.tool_started("b", "read_file", "PLAN.md")
        bridge.tool_completed("b", "read_file", "BODY-OF-B")
        bridge.tool_completed("a", "mazemaker_recall", "BODY-OF-A")
        lines = [t for _, t in bridge.transcript.fragments(100)]
        order = [next(i for i, t in enumerate(lines) if m in t)
                 for m in ("mazemaker_recall", "BODY-OF-A", "read_file", "BODY-OF-B")]
        assert order == sorted(order), f"results detached from their calls: {lines}"

    def test_preparing_is_upgraded_in_place_not_repeated(self, bridge):
        prep = bridge.tool_preparing("read_file")
        assert prep.state == "preparing"
        started = bridge.tool_started("x", "read_file", "a.md")
        assert started is prep and prep.state == "running"
        bridge.tool_completed("x", "read_file", "body")
        headers = [t for _, t in bridge.transcript.fragments(100) if "read_file" in t]
        assert len(headers) == 1 and len(bridge.transcript) == 1

    def test_duration_is_measured_when_the_caller_has_none(self, bridge):
        block = bridge.tool_started("x", "terminal", "ls")
        bridge.tool_completed("x", "terminal", "out")
        assert block.duration is not None and block.duration >= 0.0
        assert "s" in "".join(t for _, t in block.fragments(100, bridge.transcript.theme))

    def test_clear_forgets_preparing_calls(self, bridge):
        bridge.tool_preparing("read_file")
        bridge.clear()
        assert not any(bridge._preparing.values())
