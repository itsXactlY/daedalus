"""Classifying tool results.

The cases here are the ones that actually broke the TUI, quoted from a real
session: a JSON-wrapped ``ls`` listing whose newlines arrived escaped, an
``execute_code`` result whose source got reflowed into one paragraph, and a
context bar whose ANSI codes were printed as literal characters.
"""

import sys

import pytest

sys.path.insert(0, "/home/alca/.daedalus/daedalus-agent")

from daedalus_cli.tool_result import ResultKind, classify_result


class TestTheCasesThatBrokeTheTUI:
    def test_json_wrapped_ls_listing_is_decoded_not_printed(self):
        # What execute_code returns: the listing inside a JSON envelope, so its
        # newlines are backslash-n in a single line of text.
        raw = (r'{"status": "success", "output": '
               r'"build_diag2.log\n-rw-r--r-- 1 alca alca 1.8k Sep 04:32 build.log\n'
               r'-rw-r--r-- 1 alca alca 5.3k Sep 06:20 gateway.log"}')
        result = classify_result(raw)
        # The envelope is unwrapped, so what gets rendered is the listing --
        # code, not the bookkeeping object around it.
        assert result.kind is ResultKind.CODE
        assert "build_diag2.log" in result.text
        assert "gateway.log" in result.text
        assert "\\n" not in result.text, \
            "escaped newlines survived into the rendered text"
        assert len(result.text.split("\n")) >= 3, "listing lines were joined"

    def test_source_code_is_not_reflowed_into_one_paragraph(self):
        raw = ("from daedalus_tools import terminal, read_file\n"
               "import re\n"
               "r = terminal(\"cd /home/alca && grep -nE 'A|B' .\")")
        result = classify_result(raw)
        assert result.kind is ResultKind.CODE
        assert result.language == "python"
        # every source line is still its own line
        assert len(result.text.split("\n")) == 3

    def test_ansi_codes_are_stripped_not_printed(self):
        raw = "\x1b[33mcontext compacted\x1b[0m\x1b[90m 94% to compaction\x1b[0m"
        result = classify_result(raw)
        assert "\x1b" not in result.text, "ANSI escape reached the screen as text"
        assert "context compacted" in result.text

    def test_lone_path_is_output_not_prose(self):
        result = classify_result("/home/alca/projects/jrwl-messenger")
        assert result.kind is ResultKind.CODE


class TestJSON:
    def test_json_object_is_pretty_printed(self):
        result = classify_result('{"b":2,"a":1}')
        assert result.kind is ResultKind.DATA
        assert result.text.startswith("{\n")
        assert '"a": 1' in result.text

    def test_json_array(self):
        result = classify_result("[1, 2, 3]")
        assert result.kind is ResultKind.DATA
        assert result.language == "json"

    def test_malformed_json_is_not_crashed_on(self):
        result = classify_result('{"broken": ')
        assert result.kind in (ResultKind.CODE, ResultKind.MARKDOWN)

    def test_json_inside_json_does_not_get_double_unescaped(self):
        raw = r'{"output": "{\"nested\": true}"}'
        result = classify_result(raw)
        assert result.kind is ResultKind.DATA
        assert '"nested": true' in result.text


class TestCode:
    def test_diff_is_code(self):
        result = classify_result("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-x\n+y")
        assert result.kind is ResultKind.CODE
        assert len(result.text.split("\n")) == 5

    def test_grep_line_numbers_are_code(self):
        result = classify_result("53:WIRE_FRAME_MAX = 4096\n54:BLOCK_SIZE = 3018")
        assert result.kind is ResultKind.CODE

    def test_git_status_is_code(self):
        result = classify_result(" M cli.py\n?? new.py")
        assert result.kind is ResultKind.CODE

    def test_traceback_is_python(self):
        raw = ("Traceback (most recent call last):\n"
               '  File "x.py", line 1, in <module>\nValueError: nope')
        result = classify_result(raw)
        assert result.kind is ResultKind.CODE
        assert result.language == "python"

    def test_shell_script_detected(self):
        result = classify_result("#!/bin/bash\nset -e\necho hi")
        assert result.language == "bash"

    def test_trailing_newline_does_not_create_a_blank_row(self):
        result = classify_result("a\nb\n")
        assert not result.text.endswith("\n")


class TestProse:
    def test_real_prose_stays_markdown(self):
        result = classify_result("The build failed because the port was busy.")
        assert result.kind is ResultKind.MARKDOWN

    def test_prose_with_punctuation_is_not_code(self):
        result = classify_result("Here is what I found in the file, line by line.")
        assert result.kind is ResultKind.MARKDOWN


class TestEmpty:
    def test_none_is_empty(self):
        assert classify_result(None).kind is ResultKind.EMPTY

    def test_blank_is_empty(self):
        assert classify_result("   \n  \n").kind is ResultKind.EMPTY

    def test_ansi_only_is_empty(self):
        assert classify_result("\x1b[0m\x1b[2J").kind is ResultKind.EMPTY


class TestEscapedNewlines:
    def test_decoded_into_real_lines(self):
        result = classify_result(r"-rw-r--r-- 1 alca alca 1.8k x.log\n-rw-r--r-- 2 alca alca 2k y.log")
        assert "\n" in result.text
        assert result.kind is ResultKind.CODE

    def test_a_literal_backslash_n_in_prose_is_left_alone(self):
        # Prose that talks about the escape sequence must not be mangled.
        result = classify_result(r"Use \n to break a line in printf.")
        assert result.kind is ResultKind.MARKDOWN


class TestNeverRaises:
    @pytest.mark.parametrize("raw", [
        "", " ", "\x00", "{", "[", "\\", "a" * 10000,
        "{" * 500, "\n" * 100, "\t\t\t", "🎉" * 200,
    ])
    def test_classification_is_total(self, raw):
        result = classify_result(raw)
        assert result.kind in tuple(ResultKind)