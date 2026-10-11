"""Four things the TUI got wrong on screen, each reproduced from a real screenshot.

1. Agent status lines carry ANSI (the context-pressure warning) and showed up as
   literal ``^[[1m^[[33m`` in the transcript.
2. The reasoning pane painted as ONE long line joined by '│' with the rest of its
   height blank, because the stored lines had no newlines between them.
3. Code and data results were wrapped in literal ``` lines nothing interpreted.
4. execute_code's {"status","output","tool_calls_made","duration_seconds"} envelope
   was shown as a raw JSON dump with escaped newlines instead of the output.
"""

import json

import pytest

from cli import reasoning_pane_fragments
from daedalus_cli.tool_result import ResultKind, classify_result
from daedalus_cli.transcript import ResultBlock, Transcript, TranscriptTheme, strip_ansi
from daedalus_cli.transcript_bridge import TranscriptBridge


def _text(tr, width=100):
    return "\n".join(t for _, t in tr.fragments(width))


def test_status_line_ansi_never_reaches_the_transcript():
    bridge = TranscriptBridge(Transcript(), theme=TranscriptTheme())
    bridge.print_line("  \x1b[1m\x1b[33m⚠ context 85% to compaction\x1b[0m  \x1b[2m32k threshold\x1b[0m\n")
    out = _text(bridge.transcript)
    assert "\x1b" not in out and "^[" not in out
    assert "85% to compaction" in out


def test_partial_status_line_is_stripped_on_flush():
    bridge = TranscriptBridge(Transcript(), theme=TranscriptTheme())
    bridge.print_line("\x1b[2mhalf a line")
    bridge.flush_line()
    assert "\x1b" not in _text(bridge.transcript)


def test_reasoning_pane_lines_are_newline_separated():
    frags = [("class:reasoning-text", "│ first"), ("class:reasoning-text", "│ second"),
             ("class:reasoning-text", "│ third")]
    out = reasoning_pane_fragments(frags)
    assert "".join(t for _, t in out) == "│ first\n│ second\n│ third"
    assert len(out) == 3 and all(style == "class:reasoning-text" for style, _ in out)


def test_reasoning_pane_empty_and_input_untouched():
    assert reasoning_pane_fragments(None) == []
    assert reasoning_pane_fragments([]) == []
    frags = [("s", "a"), ("s", "b")]
    reasoning_pane_fragments(frags)
    assert frags == [("s", "a"), ("s", "b")]


@pytest.mark.parametrize("language", ["python", "json", ""])
def test_code_results_have_no_literal_fences(language):
    block = ResultBlock("x = 1\nprint(x)", language=language, kind="code")
    out = "\n".join(t for _, t in block.fragments(80, TranscriptTheme()))
    assert "```" not in out
    assert "x = 1" in out and "print(x)" in out


def test_execute_code_envelope_is_unwrapped_to_its_output():
    raw = json.dumps({"status": "success", "output": "line one\nline two\nline three",
                      "tool_calls_made": 1, "duration_seconds": 1.03})
    res = classify_result(raw, tool_name="execute_code")
    assert res.kind != ResultKind.DATA
    assert "line one\nline two" in res.text
    assert "tool_calls_made" not in res.text and "duration_seconds" not in res.text


def test_a_failing_envelope_is_not_hidden():
    raw = json.dumps({"status": "error", "output": "boom", "error": "Traceback", "exit_code": 1})
    res = classify_result(raw, tool_name="execute_code")
    assert "exit_code" in res.text and "error" in res.text      # real bookkeeping stays visible


def test_read_file_envelope_is_unwrapped_to_the_file():
    raw = json.dumps({"content": "     1|# Kermit\n     2|Status: active", "total_lines": 66,
                      "file_size": 5644, "truncated": False, "is_binary": False, "is_image": False})
    res = classify_result(raw, tool_name="read_file")
    assert res.kind != ResultKind.DATA
    assert "# Kermit\n" in res.text and "file_size" not in res.text


def test_a_truncated_read_says_so():
    raw = json.dumps({"content": "1|a\n2|b", "total_lines": 9000, "truncated": True})
    assert classify_result(raw, tool_name="read_file").text.endswith("… truncated")


def test_error_fields_are_never_bookkeeping():
    raw = json.dumps({"content": "partial", "error": "permission denied", "total_lines": 3})
    res = classify_result(raw, tool_name="read_file")
    assert "permission denied" in res.text
