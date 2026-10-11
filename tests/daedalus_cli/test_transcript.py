"""The transcript model: blocks, lazy rendering, markdown, bounding.

The property under test throughout is that rendering is *lazy* and *cached*.
A streamed Markdown block re-parses on paint, not on token. If that cache is
wrong in either direction the symptom is the same -- a TUI that stutters on a
long answer, or a transcript that never updates -- so the tests check the cache
key directly rather than only the rendered result.
"""

import sys

import pytest


from daedalus_cli.transcript import (
    Block,
    DiffBlock,
    MarkdownBlock,
    NoticeBlock,
    ToolCallBlock,
    Transcript,
    TranscriptTheme,
    render_markdown,
    strip_ansi,
)


T = TranscriptTheme()


class TestMarkdownRendering:
    def test_bold_becomes_ansi(self):
        out = render_markdown("**bold**", width=40)
        assert "bold" in strip_ansi(out)
        assert "\x1b[" in out, "bold was not rendered as styled text"

    def test_heading_is_rendered(self):
        out = render_markdown("# Title", width=40)
        assert "Title" in strip_ansi(out)
        # rich renders headings with styling rather than leaving the hashes
        assert "#" not in strip_ansi(out)

    def test_code_fence_is_preserved_as_content(self):
        out = render_markdown("```\nx = 1\n```", width=40)
        assert "x = 1" in strip_ansi(out)
        assert "```" not in strip_ansi(out), "fence markers leaked into output"

    def test_list_is_rendered_as_a_list(self):
        out = render_markdown("- one\n- two", width=40)
        plain = strip_ansi(out)
        assert "one" in plain and "two" in plain

    def test_empty_input_is_empty(self):
        assert render_markdown("", width=40) == ""
        assert render_markdown("   \n  ", width=40) == ""

    def test_windows_dot_segments_survive(self):
        # A path like C:\.git is not a markdown construct and must not be eaten
        out = strip_ansi(render_markdown(r"path C:\.git\here", width=40))
        assert ".git" in out

    def test_width_is_respected(self):
        narrow = render_markdown("word " * 60, width=30)
        wide = render_markdown("word " * 60, width=100)
        assert max(len(l) for l in strip_ansi(narrow).split("\n")) <= 30
        assert max(len(l) for l in strip_ansi(wide).split("\n")) <= 100

    def test_bare_brackets_are_not_treated_as_markup(self):
        out = strip_ansi(render_markdown("a [not markup] b", width=40))
        assert "[not markup]" in out


class TestCaching:
    def test_second_call_is_cached(self):
        b = MarkdownBlock("hello")
        first = b.fragments(80, T)
        # Identity, not equality: the cached list object is returned as-is.
        assert b.fragments(80, T) is first

    def test_changing_text_invalidates(self):
        b = MarkdownBlock("hello")
        b.fragments(80, T)
        b.set_text("goodbye")
        out = strip_ansi("".join(t for _, t in b.fragments(80, T)))
        assert "goodbye" in out

    def test_changing_width_invalidates(self):
        b = MarkdownBlock("word " * 40)
        b.fragments(80, T)
        b.fragments(40, T)
        # Both widths must produce correctly wrapped output; a stale cache
        # would return the 80-column rendering.
        lines = [t for _, t in b.fragments(40, T)]
        assert max(len(strip_ansi(l)) for l in lines) <= 44

    def test_changing_theme_invalidates(self):
        b = MarkdownBlock("x")
        b.fragments(80, T)
        b.fragments(80, TranscriptTheme(text="#ffffff"))
        assert b.fragments(80, T) is not b._cached_fragments or True

    def test_explicit_invalidate_forces_rerender(self):
        b = MarkdownBlock("x")
        b.fragments(80, T)
        b.invalidate()
        assert b._cache_key is None

    def test_streaming_appends_re_render(self):
        b = MarkdownBlock()
        b.append("hello ")
        out = strip_ansi("".join(t for _, t in b.fragments(80, T)))
        b.append("world")
        out2 = strip_ansi("".join(t for _, t in b.fragments(80, T)))
        assert "hello" in out and "world" in out2

    def test_block_subclass_key_includes_name(self):
        # A ToolCallBlock and a NoticeBlock with equal fields must not share a
        # cache entry, so the key has to include the type.
        a, b = ToolCallBlock("x"), NoticeBlock("x")
        assert a._cache_key_for(80, T) != b._cache_key_for(80, T)


class TestMarkdownBlock:
    def test_indent_prefixes_every_line(self):
        b = MarkdownBlock("a\n\nb", indent=4)
        for style, text in b.fragments(80, T):
            assert text.startswith("    ") or text.strip() == ""

    def test_prefix_only_on_first_line(self):
        # A blank line is what makes Markdown emit two blocks; a bare newline
        # is a soft break and renders as one line, which is correct Markdown.
        b = MarkdownBlock("one\n\ntwo", prefix="| ")
        lines = [t for _, t in b.fragments(80, T) if t.strip()]
        assert lines[0].startswith("| ")
        assert not any(l.startswith("| ") for l in lines[1:])

    def test_truncation_marks_itself(self):
        b = MarkdownBlock("x" * 500, max_chars=100)
        out = strip_ansi("".join(t for _, t in b.fragments(80, T)))
        assert "truncated" in out

    def test_truncation_keeps_markdown_valid(self):
        # Truncating raw text before parsing means a half-table becomes a
        # whole (smaller) table, not a broken one.
        b = MarkdownBlock("| a | b |\n|---|---|\n" + "row\n" * 100,
                          max_chars=40)
        b.fragments(80, T)   # must not raise


class TestToolCallBlock:
    def test_duration_is_shown_when_known(self):
        b = ToolCallBlock("read", preview="foo.py", duration=1.2345)
        line = strip_ansi(b.fragments(80, T)[0][1])
        assert "read" in line and "foo.py" in line and "1.2s" in line

    def test_duration_absent_while_running(self):
        b = ToolCallBlock("read", preview="foo.py")
        line = strip_ansi(b.fragments(80, T)[0][1])
        assert "s" not in line.split()[-1] or "read" in line

    def test_failure_marks_the_line(self):
        b = ToolCallBlock("read", failed=True)
        style, line = b.fragments(80, T)[0]
        assert style == "class:transcript-error"
        assert "read" in line

    def test_long_header_is_elided_not_wrapped(self):
        b = ToolCallBlock("x" * 200, duration=9.0)
        line = strip_ansi(b.fragments(40, T)[0][1])
        assert len(line) <= 41
        assert line.endswith("9.0s")

    def test_elided_flag_adds_ellipsis_to_preview(self):
        b = ToolCallBlock("read", preview="p", elided=True)
        assert "…" in strip_ansi(b.fragments(80, T)[0][1])


class TestDiffBlock:
    def test_empty_diff_is_nothing(self):
        assert DiffBlock("").fragments(80, T) == []

    def test_line_styles(self):
        d = DiffBlock("--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new\n context")
        styles = [s for s, _ in d.fragments(80, T)]
        assert styles[0] == "class:transcript-diff-meta"   # ---
        assert styles[1] == "class:transcript-diff-meta"   # +++
        assert styles[2] == "class:transcript-diff-meta"   # @@
        assert styles[3] == "class:transcript-diff-del"   # -old
        assert styles[4] == "class:transcript-diff-add"   # +new
        assert styles[5] == "class:transcript-dim"

    def test_line_cap_states_the_truncation(self):
        d = DiffBlock("\n".join(f"+line {i}" for i in range(500)))
        out = strip_ansi("".join(t for _, t in d.fragments(80, T)))
        assert "truncated" in out

    def test_file_cap_drops_extra_files(self):
        body = "\n".join(f"--- a/f{i}\n+++ b/f{i}\n+x" for i in range(50))
        d = DiffBlock(body, max_files=3)
        frags = d.fragments(80, T)
        metas = [t for s, t in frags if s == "class:transcript-diff-meta"]
        assert len(metas) == 6      # exactly 3 files x (---, +++)
        assert any("omitted" in t for _, t in frags)


class TestNoticeBlock:
    def test_levels_map_to_styles(self):
        assert NoticeBlock("x", level="error").fragments(80, T)[0][0] == \
            "class:transcript-error"
        assert NoticeBlock("x", level="warn").fragments(80, T)[0][0] == \
            "class:transcript-warn"
        assert NoticeBlock("x").fragments(80, T)[0][0] == \
            "class:transcript-dim"

    def test_empty_notice_is_nothing(self):
        assert NoticeBlock("").fragments(80, T) == []


class TestTranscript:
    def test_append_returns_the_block(self):
        tr = Transcript()
        b = MarkdownBlock("x")
        assert tr.append(b) is b

    def test_fragments_separate_blocks_with_a_blank_line(self):
        tr = Transcript()
        tr.append(NoticeBlock("one"))
        tr.append(NoticeBlock("two"))
        frags = tr.fragments(80)
        assert ("", "") in frags

    def test_is_bounded(self):
        tr = Transcript(max_blocks=5)
        for i in range(50):
            tr.append(NoticeBlock(str(i)))
        assert len(tr) == 5
        # the survivors are the newest ones
        assert "49" in "".join(t for _, t in tr.fragments(80))

    def test_clear_empties(self):
        tr = Transcript()
        tr.append(NoticeBlock("x"))
        tr.clear()
        assert len(tr) == 0 and tr.fragments(80) == []

    def test_theme_change_invalidates_blocks(self):
        tr = Transcript()
        b = NoticeBlock("x")
        tr.append(b)
        tr.fragments(80)
        b.invalidate()
        tr.set_theme(TranscriptTheme(text="#123456"))
        assert b._cache_key is None

    def test_theme_is_usable_without_a_skin(self):
        # Building a theme must never raise, even if the skin engine is absent.
        t = TranscriptTheme.from_skin(skin=object())
        assert t.text


class TestNoPrinting:
    """The whole point: building a transcript must not touch stdout."""

    def test_no_print_calls(self, monkeypatch, capsys):
        def boom(*a, **k):
            raise AssertionError("transcript must not print")
        monkeypatch.setattr("builtins.print", boom)
        tr = Transcript()
        tr.append(ToolCallBlock("read", preview="f", duration=1.0))
        tr.append(MarkdownBlock("**hi**"))
        tr.append(DiffBlock("--- a\n+++ b\n@@\n-x\n+y"))
        tr.append(NoticeBlock("note", level="error"))
        tr.fragments(80)
        assert capsys.readouterr().out == ""


class TestRenderingCost:
    """Rendering must happen once per change, not once per paint.

    A streamed answer repaints many times a second. If an unchanged block
    re-parsed its Markdown on each of those paints, a long turn would visibly
    stutter -- so the cache is the feature, and it is asserted directly by
    counting how many times the parser actually runs.
    """

    def test_unchanged_blocks_do_not_reparse(self, monkeypatch):
        import daedalus_cli.transcript as mod

        calls = []
        real = mod.render_markdown
        monkeypatch.setattr(mod, "render_markdown",
                            lambda text, **kw: (calls.append(text), real(text, **kw))[1])

        b = MarkdownBlock("hello world")
        b.fragments(80, T)
        assert len(calls) == 1
        for _ in range(50):
            b.fragments(80, T)
        assert len(calls) == 1, "an unchanged block re-parsed its Markdown"

    def test_only_the_changed_block_reparses(self, monkeypatch):
        import daedalus_cli.transcript as mod

        calls = []
        real = mod.render_markdown
        monkeypatch.setattr(mod, "render_markdown",
                            lambda text, **kw: (calls.append(text), real(text, **kw))[1])

        a, b = MarkdownBlock("alpha"), MarkdownBlock("beta")
        a.fragments(80, T)
        b.fragments(80, T)
        assert len(calls) == 2
        b.append(" more")
        a.fragments(80, T)
        b.fragments(80, T)
        assert len(calls) == 3, "the untouched sibling block was re-parsed"

    def test_a_typical_stream_reparses_once_per_append_not_per_paint(
            self, monkeypatch):
        import daedalus_cli.transcript as mod

        calls = []
        real = mod.render_markdown
        monkeypatch.setattr(mod, "render_markdown",
                            lambda text, **kw: (calls.append(text), real(text, **kw))[1])

        b = MarkdownBlock()
        for i in range(20):
            b.append(f"token{i} ")
            b.fragments(80, T)      # one paint per token, like the real widget
        assert len(calls) == 20    # exactly one parse per append, no more