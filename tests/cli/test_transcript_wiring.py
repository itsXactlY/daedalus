"""The CLI's tool callbacks must feed the transcript, not the print path.

This is the integration test for the change that moved tool rendering out of
``_cprint``. The unit tests on the bridge prove the translation is correct;
these prove the CLI actually uses it -- that wiring the bridge in is what
happens when a tool runs, not something the tests assume.

The failure mode this guards against is silent: if a callback falls back to
``_cprint`` the tool output still appears, so nothing looks broken, but the
skin is being torn down again. So these tests assert the negative directly --
``_cprint`` is made to raise, and a tool run must still complete.
"""

import sys
import types

import pytest

sys.path.insert(0, "/home/alca/.daedalus/daedalus-agent")

import cli as C


class _FakeCLI:
    """A CLI with just enough state for the transcript callbacks."""

    def __init__(self, transcript=None):
        self._transcript = transcript
        self._transcript_bridge = None
        self._transcript_widget = None
        self._transcript_windows = None
        self._spinner_text = ""
        self._stream_box_opened = False
        self._reasoning_box_opened = False
        self._reasoning_fragments = []
        self._stream_buf = ""
        self.show_reasoning = False
        self.tool_progress_mode = "new"
        self._voice_mode = False
        self._pending_edit_snapshots = {}
        self.invalidates = 0
        self.printed = []

        # bind the real methods we are testing
        for name in ("_get_transcript", "_get_transcript_bridge",
                     "_transcript_notice", "_transcript_print",
                     "_on_tool_progress", "_on_tool_complete", "_close_reasoning_box"):
            setattr(self, name, types.MethodType(getattr(C.DaedalusCLI, name), self))

    def _invalidate(self, min_interval: float = 0.25):
        self.invalidates += 1

    def _cprint(self, text):
        self.printed.append(text)


@pytest.fixture()
def fake(monkeypatch):
    """A CLI whose _cprint raises, so any print-path fallback fails loudly."""
    from daedalus_cli.transcript import Transcript, TranscriptTheme

    f = _FakeCLI()
    f._transcript = Transcript()
    f._transcript.set_theme(TranscriptTheme())

    def boom(*a, **k):
        raise AssertionError("tool rendering fell back to the print path")

    monkeypatch.setattr(C, "_cprint", boom)
    return f


def body(f) -> str:
    from daedalus_cli.transcript import strip_ansi
    return strip_ansi("\n".join(t for _, t in f._transcript.fragments(100)))


def body_of(f) -> str:
    return body(f)


class TestToolProgressGoesToTheTranscript:
    def test_started_opens_a_call(self, fake):
        fake._on_tool_progress("tool.started", "read_file", preview="notes.md")
        assert "read_file" in body(fake)
        assert "notes.md" in body(fake)

    def test_started_also_drives_the_spinner(self, fake):
        fake._on_tool_progress("tool.started", "read_file", preview="notes.md")
        assert "notes.md" in fake._spinner_text

    def test_internal_tools_are_skipped(self, fake):
        fake._on_tool_progress("tool.started", "_internal_thing")
        assert len(fake._transcript) == 0

    def test_completion_attaches_result_and_no_print(self, fake):
        fake._on_tool_progress("tool.started", "read_file", preview="a.md")
        fake._on_tool_complete("id", "read_file", {"path": "a.md"}, "the body")
        text = body(fake)
        assert "the body" in text
        assert fake.printed == []


class TestCompletionRendersDiffAsBlocks:
    def test_write_file_produces_a_diff(self, fake, tmp_path, monkeypatch):
        target = tmp_path / "f.py"
        target.write_text("x = 1\n")

        # capture the before-state the way the real flow does
        from agent.display import capture_local_edit_snapshot
        snap = capture_local_edit_snapshot("write_file", {"path": str(target)})
        fake._pending_edit_snapshots["id"] = snap

        target.write_text("x = 2\n")
        fake._on_tool_complete("id", "write_file",
                              {"path": str(target)}, '{"success": true}')
        text = body(fake)
        assert "-x = 1" in text or "x = 1" in text
        assert "+x = 2" in text or "x = 2" in text

    def test_failed_tool_is_marked(self, fake):
        # _detect_tool_failure recognises failures from the JSON-shaped results
        # tools actually return, not free-form prose like "command exited 1".
        fake._on_tool_progress("tool.started", "read_file", preview="a.md")
        fake._on_tool_complete(
            "id", "read_file", {"path": "a.md"},
            '{"error": "File not found: a.md"}')
        styles = [s for s, t in fake._transcript.fragments(100)]
        assert "class:transcript-error" in styles

    def test_successful_tool_is_not_marked_failed(self, fake):
        fake._on_tool_progress("tool.started", "read_file", preview="a.md")
        fake._on_tool_complete("id", "read_file", {}, '{"success": true}')
        styles = [s for s, t in fake._transcript.fragments(100)]
        assert "class:transcript-error" not in styles


class TestPrintFunnel:
    def test_agent_print_fn_target_goes_to_the_transcript(self, fake):
        fake._transcript_print("running 3 commands")
        fake._transcript_print("\n")
        assert "running 3 commands" in body(fake)
        assert fake.printed == []

    def test_result_markdown_is_rendered_not_raw(self, fake):
        fake._on_tool_progress("tool.started", "terminal", preview="ls")
        fake._on_tool_complete("id", "terminal", {},
                               '```\n{"ok": true}\n```')
        # the fence markers must be gone: the result went through Markdown
        assert "```" not in body(fake)
        assert '"ok": true' in body(fake)


class TestSpinnerFramesDoNotFloodTheTranscript:
    """A minute of spinner animation must not become a screenful of blocks.

    The KawaiiSpinner is constructed with the agent's print_fn, which is this
    transcript. It animates with a carriage return and no newline at roughly
    8 Hz. Before this was filtered, each frame became its own block: after a
    minute of thinking the transcript was hundreds of frames tall, and the
    conversation itself was scrolled out of view. That is the whole screen of
    nothing the TUI showed.
    """

    def _frames(self, fake, count: int):
        for i in range(count):
            # exactly what KawaiiSpinner._animate emits: \r, content, padding
            fake._transcript_print(f"\r  . thinking... ({i}.0s){' ' * 8}")

    def test_a_minute_of_spinner_adds_nothing(self, fake):
        self._frames(fake, 8 * 60)
        # Without the filter each frame buffered separately, so this was 480
        # blocks. Assert on both the block count and the buffer, because the
        # failure mode was an ever-growing backlog rather than a wrong line.
        assert len(fake._transcript) == 0, \
            f"a minute of spinner produced {len(fake._transcript)} blocks"
        assert fake._get_transcript_bridge()._line_buffer == "", \
            "spinner frames were buffered instead of discarded"

    def test_spinner_frames_are_dropped_but_real_text_is_not(self, fake):
        self._frames(fake, 20)
        fake._transcript_print("running 3 commands\n")
        body = body_of(fake)
        assert "running 3 commands" in body
        assert "thinking..." not in body
        assert len(fake._transcript) == 1

    def test_carriage_return_lines_never_become_blocks(self, fake):
        fake._transcript_print("progress 50%\rprogress 99%\n")
        assert "progress" not in body_of(fake)

    def test_plain_multiline_status_still_lands(self, fake):
        fake._transcript_print("first line\nsecond line\n")
        text = body_of(fake)
        assert "first line" in text and "second line" in text

    def test_each_plain_line_is_its_own_block(self, fake):
        # Two lines in one write must not collapse into a single block, and
        # must not leave a stray partial line behind either.
        fake._transcript_print("first line\nsecond line\n")
        assert len(fake._transcript) == 2
        assert fake._get_transcript_bridge()._line_buffer == ""


class TestGracefulDegradation:
    def test_no_transcript_falls_back_to_print(self, monkeypatch):
        # If the transcript cannot be built, output must still be shown rather
        # than swallowed. This is the one case where _cprint is correct.
        printed = []
        monkeypatch.setattr(C, "_cprint", lambda t: printed.append(t))

        f = _FakeCLI()
        f._transcript = False      # simulate construction failure
        f._print_fn_fallback = True
        f._transcript_print("a status line\n")
        assert printed, "output was swallowed when the transcript was unavailable"